"""Publicacion de la hoja de ruta en Google Calendar.

Convierte una Ruta optimizada en una agenda: un evento por parada, con
bloques de viaje intercalados, ubicacion navegable y la tarea en la
descripcion.

    08:00 - 09:30   1. Mantenimiento Flota Porta - Freyre
                    Servicio 250 Hs electrico. Contacto: Pablo Ortiz
    09:30 - 10:40   Viaje a Sunchales (74 km)
    10:40 - 12:10   2. Lacteos Santa Rosa - Sunchales

IMPORTANTE: un service account NO puede escribir en un calendario personal
salvo que el calendario este compartido con su email, con permiso
"Realizar cambios en los eventos".

Requiere:
    pip install google-auth requests
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.config import Settings
from app.duraciones import estimar_minutos, redondear_a
from app.ruteador import Ruta, Parada, formato_duracion
from app.utils import clean_text


API_BASE = "https://www.googleapis.com/calendar/v3"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Clave usada para reconocer los eventos creados por el sistema y poder
# regenerar la agenda sin duplicar.
PROP_ORIGEN = "hoja_ruta"
PROP_LOTE = "hoja_ruta_lote"

COLOR_PARADA = "10"   # verde
COLOR_VIAJE = "8"     # gris
COLOR_TALLER = "5"    # amarillo


class CalendarNoConfigurado(RuntimeError):
    """Falta configuracion o permisos para escribir en el calendario."""


@dataclass
class EventoAgenda:
    titulo: str
    inicio: datetime
    fin: datetime
    descripcion: str = ""
    ubicacion: str = ""
    color: str = COLOR_PARADA
    tipo: str = "parada"   # "parada" | "viaje" | "taller"


@dataclass
class ResultadoSync:
    creados: int = 0
    borrados: int = 0
    calendario: str = ""
    link: str = ""
    eventos: list[EventoAgenda] = None

    def __post_init__(self):
        if self.eventos is None:
            self.eventos = []


# ------------------------------------------------------------------ sesion


def _sesion(settings: Settings):
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.service_account import Credentials
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise CalendarNoConfigurado(
            "Falta instalar dependencias: pip install google-auth requests"
        ) from exc

    ruta = settings.google_credentials_path
    if not ruta or not ruta.exists():
        raise CalendarNoConfigurado(
            f"No se encontro el JSON de credenciales en: {ruta}"
        )
    creds = Credentials.from_service_account_file(str(ruta), scopes=SCOPES)
    return AuthorizedSession(creds), creds.service_account_email


# ------------------------------------------- calendarios guardados por la app

# Clave interna del calendario por defecto (cuando no hay uno por mecanico)
CLAVE_DEFECTO = "*"


def _conectar(settings: Settings):
    import sqlite3

    conn = sqlite3.connect(settings.services_db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calendarios_mecanico (
            mecanico    TEXT PRIMARY KEY,
            calendar_id TEXT NOT NULL,
            fecha       TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    return conn


def guardar_calendario_mecanico(settings: Settings, mecanico: str, calendar_id: str) -> None:
    """Recuerda a que calendario van las hojas de ruta de este mecanico.

    Si mecanico viene vacio se guarda como calendario por defecto.
    """
    nombre = clean_text(mecanico).lower() or CLAVE_DEFECTO
    calendar_id = clean_text(calendar_id)
    with _conectar(settings) as conn:
        if calendar_id:
            conn.execute(
                "INSERT OR REPLACE INTO calendarios_mecanico (mecanico, calendar_id) "
                "VALUES (?, ?)",
                (nombre, calendar_id),
            )
        else:
            conn.execute("DELETE FROM calendarios_mecanico WHERE mecanico = ?", (nombre,))
        conn.commit()


def leer_calendario_mecanico(settings: Settings, mecanico: str) -> str:
    """Calendario guardado para ese mecanico. Vacio si no hay."""
    nombre = clean_text(mecanico).lower() or CLAVE_DEFECTO
    with _conectar(settings) as conn:
        fila = conn.execute(
            "SELECT calendar_id FROM calendarios_mecanico WHERE mecanico = ?", (nombre,)
        ).fetchone()
    return fila[0] if fila else ""


def leer_calendario_defecto(settings: Settings) -> str:
    return leer_calendario_mecanico(settings, CLAVE_DEFECTO)


def listar_calendarios_mecanico(settings: Settings) -> dict[str, str]:
    with _conectar(settings) as conn:
        filas = conn.execute(
            "SELECT mecanico, calendar_id FROM calendarios_mecanico"
        ).fetchall()
    return {m: c for m, c in filas}


def calendario_de(settings: Settings, mecanico: str) -> str:
    """Devuelve el calendarId que corresponde a un mecanico.

    Orden de prioridad:
      1. Lo guardado desde la app para ese mecanico
      2. El calendario por defecto guardado desde la app (clave CLAVE_DEFECTO)
      3. CALENDAR_MECANICOS del .env  ("Pablo=mail1;Emiliano=mail2")
      4. CALENDAR_ID_DEFECTO del .env
    """
    guardado = leer_calendario_mecanico(settings, mecanico)
    if guardado:
        return guardado

    nombre = clean_text(mecanico).lower()
    for parte in (settings.calendar_mecanicos or "").split(";"):
        parte = parte.strip()
        if not parte or "=" not in parte:
            continue
        clave, _, valor = parte.partition("=")
        if clave.strip().lower() == nombre and valor.strip():
            return valor.strip()

    por_defecto = leer_calendario_defecto(settings)
    if por_defecto:
        return por_defecto

    if not settings.calendar_id_defecto:
        raise CalendarNoConfigurado(
            f"No hay calendario definido para '{mecanico}'.\n\n"
            "Escribí el mail del calendario en el campo 'Calendario' de la ventana, "
            "o configurá CALENDAR_ID_DEFECTO en el .env."
        )
    return settings.calendar_id_defecto


# ------------------------------------------------------------- construccion


def _hora_inicio(settings: Settings, dia: date) -> datetime:
    texto = clean_text(settings.jornada_inicio) or "08:00"
    try:
        horas, _, minutos = texto.partition(":")
        return datetime.combine(dia, time(int(horas), int(minutos or 0)))
    except ValueError:
        return datetime.combine(dia, time(8, 0))


def construir_agenda(
    settings: Settings,
    ruta: Ruta,
    dia: date,
    trabajos_taller: list[Parada] | None = None,
) -> list[EventoAgenda]:
    """Arma la lista de eventos con horarios encadenados."""
    trabajos_taller = trabajos_taller or []
    eventos: list[EventoAgenda] = []
    reloj = _hora_inicio(settings, dia)

    # Trabajos de taller primero: se hacen antes de salir
    for trabajo in trabajos_taller:
        minutos = redondear_a(estimar_minutos(settings, trabajo.detalle))
        fin = reloj + timedelta(minutes=minutos)
        eventos.append(EventoAgenda(
            titulo=f"[TALLER] {trabajo.cliente}",
            inicio=reloj, fin=fin,
            descripcion=_descripcion(trabajo),
            ubicacion="Taller",
            color=COLOR_TALLER,
            tipo="taller",
        ))
        reloj = fin

    for parada in ruta.paradas:
        viaje = int(round(parada.min_desde_anterior))
        if viaje > 0 and settings.calendar_eventos_viaje:
            fin_viaje = reloj + timedelta(minutes=viaje)
            eventos.append(EventoAgenda(
                titulo=f"Viaje a {parada.lugar} ({parada.km_desde_anterior:.0f} km)",
                inicio=reloj, fin=fin_viaje,
                ubicacion=parada.lugar,
                color=COLOR_VIAJE,
                tipo="viaje",
            ))
            reloj = fin_viaje
        elif viaje > 0:
            reloj += timedelta(minutes=viaje)

        minutos = redondear_a(estimar_minutos(settings, parada.detalle))
        fin = reloj + timedelta(minutes=minutos)
        eventos.append(EventoAgenda(
            titulo=f"{parada.orden}. {parada.cliente} - {parada.lugar}",
            inicio=reloj, fin=fin,
            descripcion=_descripcion(parada),
            ubicacion=_ubicacion(parada),
            color=COLOR_PARADA,
            tipo="parada",
        ))
        reloj = fin

    if ruta.paradas and ruta.min_regreso and settings.calendar_eventos_viaje:
        fin = reloj + timedelta(minutes=int(round(ruta.min_regreso)))
        eventos.append(EventoAgenda(
            titulo=f"Regreso al taller ({ruta.km_regreso:.0f} km)",
            inicio=reloj, fin=fin,
            color=COLOR_VIAJE,
            tipo="viaje",
        ))

    return eventos


def _descripcion(parada: Parada) -> str:
    lineas = []
    if parada.detalle:
        lineas.append(clean_text(parada.detalle))
    lineas.append("")
    if parada.referencia:
        lineas.append(f"Soporte: {parada.referencia}")
    if parada.equipo:
        lineas.append(f"Equipo: {parada.equipo}")
    if parada.contacto:
        lineas.append(f"Contacto: {parada.contacto}")
    if parada.extras:
        lineas.append(f"Extras: {parada.extras}")
    return "\n".join(lineas).strip()


def _ubicacion(parada: Parada) -> str:
    """Ubicacion navegable: coordenadas si las hay, si no el texto del lugar."""
    ubi = parada.ubicacion
    if ubi is not None:
        return f"{ubi.lat},{ubi.lon}"
    return clean_text(parada.lugar)


# ---------------------------------------------------------------- publicar


def _clave_lote(mecanico: str, dia: date) -> str:
    return f"{clean_text(mecanico).lower().replace(' ', '_')}|{dia:%Y-%m-%d}"


def _borrar_lote_previo(sesion, calendar_id: str, lote: str) -> int:
    """Elimina los eventos que este sistema ya habia creado para ese lote."""
    respuesta = sesion.get(
        f"{API_BASE}/calendars/{calendar_id}/events",
        params={
            "privateExtendedProperty": f"{PROP_LOTE}={lote}",
            "maxResults": 250,
            "showDeleted": "false",
        },
        timeout=30,
    )
    if respuesta.status_code != 200:
        return 0

    borrados = 0
    for evento in respuesta.json().get("items", []):
        eliminar = sesion.delete(
            f"{API_BASE}/calendars/{calendar_id}/events/{evento['id']}", timeout=30
        )
        if eliminar.status_code in (200, 204, 404, 410):
            borrados += 1
    return borrados


def publicar_agenda(
    settings: Settings,
    ruta: Ruta,
    mecanico: str,
    dia: date,
    trabajos_taller: list[Parada] | None = None,
    reemplazar: bool = True,
    calendar_id: str = "",
) -> ResultadoSync:
    """Sube la hoja de ruta al calendario. Devuelve el resultado del sync.

    Si se pasa calendar_id, se usa ese; si no, se resuelve por mecanico.
    Solo se tocan los eventos de ESE calendario y de ESE lote (mecanico+fecha).
    """
    eventos = construir_agenda(settings, ruta, dia, trabajos_taller)
    if not eventos:
        return ResultadoSync(calendario="", eventos=[])

    sesion, email_sa = _sesion(settings)
    calendar_id = clean_text(calendar_id) or calendario_de(settings, mecanico)
    lote = _clave_lote(mecanico, dia)
    zona = clean_text(settings.zona_horaria) or "America/Argentina/Buenos_Aires"

    borrados = _borrar_lote_previo(sesion, calendar_id, lote) if reemplazar else 0

    creados = 0
    primer_link = ""
    for evento in eventos:
        cuerpo = {
            "summary": evento.titulo,
            "description": evento.descripcion or None,
            "location": evento.ubicacion or None,
            "colorId": evento.color,
            "start": {"dateTime": evento.inicio.isoformat(), "timeZone": zona},
            "end": {"dateTime": evento.fin.isoformat(), "timeZone": zona},
            "extendedProperties": {
                "private": {
                    PROP_ORIGEN: "1",
                    PROP_LOTE: lote,
                    "tipo": evento.tipo,
                }
            },
            "reminders": {"useDefault": False, "overrides": []},
        }
        cuerpo = {k: v for k, v in cuerpo.items() if v is not None}

        respuesta = sesion.post(
            f"{API_BASE}/calendars/{calendar_id}/events", json=cuerpo, timeout=30
        )
        if respuesta.status_code in (200, 201):
            creados += 1
            if not primer_link:
                primer_link = respuesta.json().get("htmlLink", "")
        elif respuesta.status_code in (403, 404):
            raise CalendarNoConfigurado(
                f"Sin permiso para escribir en el calendario '{calendar_id}'.\n\n"
                f"Compartilo con:\n  {email_sa}\n"
                "con permiso 'Realizar cambios en los eventos'.\n\n"
                f"Respuesta: {respuesta.status_code} {respuesta.text[:200]}"
            )
        else:
            raise CalendarNoConfigurado(
                f"Google Calendar respondio {respuesta.status_code}: {respuesta.text[:250]}"
            )

    return ResultadoSync(
        creados=creados,
        borrados=borrados,
        calendario=calendar_id,
        link=primer_link,
        eventos=eventos,
    )


def minutos_jornada(eventos: list[EventoAgenda]) -> int:
    if not eventos:
        return 0
    return int((eventos[-1].fin - eventos[0].inicio).total_seconds() // 60)


def evaluar_jornada(settings: Settings, eventos: list[EventoAgenda]) -> str:
    """Devuelve una advertencia si el dia no entra en la jornada laboral."""
    if not eventos:
        return ""
    minutos = minutos_jornada(eventos)
    tope = settings.jornada_max_horas * 60
    if minutos <= tope:
        return ""
    exceso = minutos - tope
    return (
        f"La jornada dura {formato_duracion(minutos)} y supera en "
        f"{formato_duracion(exceso)} el maximo de {settings.jornada_max_horas} h.\n"
        "Sacale paradas, repartilas en otro dia o asignalas a otro mecanico."
    )


def resumen_texto(eventos: list[EventoAgenda], settings: Settings | None = None) -> str:
    """Vista previa en texto de la agenda, para mostrar antes de publicar."""
    lineas = []
    for evento in eventos:
        rango = f"{evento.inicio:%H:%M} - {evento.fin:%H:%M}"
        if evento.tipo == "viaje":
            lineas.append(f"{rango}   ({evento.titulo})")
        else:
            lineas.append(f"{rango}   {evento.titulo}")
            primera = (evento.descripcion or "").split("\n")[0]
            if primera:
                lineas.append(f"{'':17s}{primera[:80]}")
    if eventos:
        minutos = minutos_jornada(eventos)
        lineas.append("")
        lineas.append(f"Jornada: {eventos[0].inicio:%H:%M} a {eventos[-1].fin:%H:%M}"
                      f"  ({formato_duracion(minutos)})")
        if settings is not None:
            advertencia = evaluar_jornada(settings, eventos)
            if advertencia:
                lineas.append("")
                for linea in advertencia.split("\n"):
                    lineas.append(f"  !! {linea}")
    return "\n".join(lineas)
