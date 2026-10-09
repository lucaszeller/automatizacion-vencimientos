"""Estimacion de cuanto dura cada tipo de service.

Se usa para armar los horarios de la agenda del mecanico.

Orden de prioridad:
  1. Regla explicita configurada en el .env (DURACIONES_SERVICE)
  2. Mediana historica real, calculada desde la planilla de registro
     (columna "Tiempo (hrs)" de Planilla_Servicio_Tecnico)
  3. Reglas por defecto del sistema
  4. DURACION_SERVICE_DEFECTO
"""

from __future__ import annotations

import re
import sqlite3
from statistics import median

from app.config import Settings
from app.utils import clean_text


# Reglas por defecto: patron -> minutos.
# Se evaluan en orden; gana el primero que coincida.
# Solo se usan si no hay dato historico para ese tipo.
REGLAS_DEFECTO: list[tuple[str, int]] = [
    (r"\b1000\s*hs?\b", 180),
    (r"\b750\s*hs?\b", 150),
    (r"\b500\s*hs?\b", 120),
    (r"\b250\s*hs?\b", 90),
    (r"\b100\s*hs?\b", 60),
    (r"\banual\b", 240),
    (r"\bsemestral\b", 120),
    (r"\btrimestral\b", 90),
    (r"chequeo\s+pre\s*entrega", 120),
    (r"\bconsulta\b", 30),
    (r"cambiar\s+rueda", 60),
    (r"\bdiagnosticar\b", 90),
    (r"\binstalar\b", 180),
    (r"\bpintar\b", 240),
]

# Minimo de registros historicos para confiar en la mediana
MINIMO_MUESTRAS = 3


# ------------------------------------------------------------- normalizacion


def clave_tipo(texto: str) -> str:
    """Reduce una descripcion de tarea a una clave canonica comparable.

    'Servicio 250 Hs electrico (chequeo incluido)'  -> '250 hs'
    'Servicio semestral CDD15J'                     -> 'semestral'
    'Cambiar bomba de frenos'                       -> 'cambiar bomba de frenos'
    """
    texto = clean_text(texto).lower()
    if not texto:
        return ""

    # Pre entrega primero: suele venir como "chequeo pre entrega 0Km"
    # y el 0Km haria que caiga en la regla de kilometraje.
    if re.search(r"pre\s*_?\s*entrega", texto):
        return "pre entrega"

    # Tipos con horas: se agrupan por el numero
    match = re.search(r"\b([0-9]{2,5})\s*_?\s*hs?\b", texto)
    if match:
        return f"{match.group(1)} hs"

    # Tipos por periodo
    for periodo in ("semestral", "trimestral", "anual", "mensual"):
        if re.search(rf"\b{periodo}\b", texto):
            return periodo

    # Kilometraje (service por km recorridos), ignorando el "0 km" de entrega
    match = re.search(r"\b([1-9][0-9.\s]*)\s*km\b", texto)
    if match:
        return f"{match.group(1).strip()} km"

    # Tarea suelta: primera oracion, sin parentesis ni detalles
    texto = re.sub(r"\([^)]*\)", " ", texto)
    texto = re.split(r"[.;\n]", texto)[0]
    texto = re.sub(r"[^a-z0-9áéíóúñ ]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto[:60]


# ------------------------------------------------------------------- cache


def _conectar(settings: Settings) -> sqlite3.Connection:
    conn = sqlite3.connect(settings.services_db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS duraciones_historicas (
            clave     TEXT PRIMARY KEY,
            minutos   INTEGER NOT NULL,
            muestras  INTEGER NOT NULL,
            minimo    INTEGER DEFAULT 0,
            maximo    INTEGER DEFAULT 0,
            fecha     TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    return conn


def leer_historico(settings: Settings, clave: str) -> tuple[int, int] | None:
    """Devuelve (minutos, muestras) para una clave, o None."""
    if not clave:
        return None
    try:
        with _conectar(settings) as conn:
            fila = conn.execute(
                "SELECT minutos, muestras FROM duraciones_historicas WHERE clave = ?",
                (clave,),
            ).fetchone()
    except sqlite3.Error:
        return None
    if fila is None or fila[1] < MINIMO_MUESTRAS:
        return None
    return (fila[0], fila[1])


def listar_historico(settings: Settings) -> list[tuple]:
    with _conectar(settings) as conn:
        return conn.execute(
            "SELECT clave, minutos, muestras, minimo, maximo FROM duraciones_historicas "
            "ORDER BY muestras DESC, clave"
        ).fetchall()


# ----------------------------------------------------- calculo desde el Sheet


def _numero(valor: str) -> float | None:
    texto = clean_text(valor).replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def recalcular_desde_historial(settings: Settings) -> dict:
    """Lee la planilla de registro y recalcula las duraciones reales.

    Espera una hoja con encabezados que incluyan 'Descripcion de la tarea'
    (o similar) y 'Tiempo (hrs)'.

    Retorna un resumen: {"filas": n, "claves": n, "descartadas": n}
    """
    from app.lector_pedidos import SheetNoConfigurado, _abrir_hoja_por_id

    if not settings.sheet_registro_id:
        raise SheetNoConfigurado(
            "Falta SHEET_REGISTRO_ID en el .env (planilla de registro de tareas)"
        )

    hoja = _abrir_hoja_por_id(
        settings, settings.sheet_registro_id, settings.sheet_registro_hoja
    )
    valores = hoja.get_all_values()
    if not valores:
        return {"filas": 0, "claves": 0, "descartadas": 0}

    # Buscar la fila de encabezados en las primeras 5 filas
    col_desc = col_tiempo = None
    fila_enc = 0
    for indice, fila in enumerate(valores[:5]):
        for pos, celda in enumerate(fila):
            texto = clean_text(celda).lower()
            if "descrip" in texto and "tarea" in texto:
                col_desc = pos
            elif texto.startswith("tiempo"):
                col_tiempo = pos
        if col_desc is not None and col_tiempo is not None:
            fila_enc = indice
            break
        col_desc = col_tiempo = None

    if col_desc is None or col_tiempo is None:
        raise SheetNoConfigurado(
            "No se encontraron las columnas 'Descripción de la tarea' y "
            "'Tiempo (hrs)' en la planilla de registro."
        )

    acumulado: dict[str, list[float]] = {}
    filas = descartadas = 0
    for fila in valores[fila_enc + 1:]:
        if len(fila) <= max(col_desc, col_tiempo):
            continue
        descripcion = clean_text(fila[col_desc])
        horas = _numero(fila[col_tiempo])
        if not descripcion or horas is None:
            continue
        filas += 1
        # Descartar valores absurdos (tipeos: 0 hs o mas de 16 hs seguidas)
        if horas <= 0 or horas > 16:
            descartadas += 1
            continue
        clave = clave_tipo(descripcion)
        if clave:
            acumulado.setdefault(clave, []).append(horas)

    with _conectar(settings) as conn:
        conn.execute("DELETE FROM duraciones_historicas")
        for clave, horas_lista in acumulado.items():
            minutos = int(round(median(horas_lista) * 60))
            conn.execute(
                "INSERT INTO duraciones_historicas "
                "(clave, minutos, muestras, minimo, maximo) VALUES (?, ?, ?, ?, ?)",
                (
                    clave,
                    minutos,
                    len(horas_lista),
                    int(round(min(horas_lista) * 60)),
                    int(round(max(horas_lista) * 60)),
                ),
            )
        conn.commit()

    utiles = sum(1 for v in acumulado.values() if len(v) >= MINIMO_MUESTRAS)
    return {
        "filas": filas,
        "claves": len(acumulado),
        "confiables": utiles,
        "descartadas": descartadas,
    }


# --------------------------------------------------------------- estimacion


def _parsear_reglas_env(texto: str) -> list[tuple[str, int]]:
    """Interpreta 'DURACIONES_SERVICE=250 hs=60;semestral=120;anual=240'."""
    reglas: list[tuple[str, int]] = []
    for parte in (texto or "").split(";"):
        parte = parte.strip()
        if not parte or "=" not in parte:
            continue
        patron, _, minutos = parte.rpartition("=")
        patron = patron.strip()
        try:
            valor = int(float(minutos.strip()))
        except ValueError:
            continue
        if patron and valor > 0:
            reglas.append((re.escape(patron.lower()), valor))
    return reglas


def estimar(settings: Settings, tipo_servicio: str) -> tuple[int, str]:
    """Devuelve (minutos, origen) para un texto de tipo de servicio.

    origen: "env" | "historico" | "regla" | "defecto"
    """
    texto = clean_text(tipo_servicio).lower()
    if not texto:
        return settings.duracion_service_defecto, "defecto"

    for patron, minutos in _parsear_reglas_env(settings.duraciones_service):
        if re.search(patron, texto):
            return minutos, "env"

    if settings.usar_duraciones_historicas:
        historico = leer_historico(settings, clave_tipo(texto))
        if historico is not None:
            return historico[0], "historico"

    for patron, minutos in REGLAS_DEFECTO:
        if re.search(patron, texto):
            return minutos, "regla"

    return settings.duracion_service_defecto, "defecto"


def estimar_minutos(settings: Settings, tipo_servicio: str) -> int:
    return estimar(settings, tipo_servicio)[0]


def redondear_a(minutos: int, paso: int = 15) -> int:
    """Redondea hacia arriba al multiplo de `paso` mas cercano."""
    if paso <= 0:
        return minutos
    resto = minutos % paso
    return minutos if resto == 0 else minutos + (paso - resto)
