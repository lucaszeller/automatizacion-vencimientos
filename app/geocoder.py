"""Geocodificacion de direcciones con cache local en SQLite.

Convierte texto ("San Francisco, Cordoba") en coordenadas (lat, lon).
Cada direccion se resuelve una sola vez: el resultado queda cacheado en
la tabla `geocache` de data/services.db.

Proveedor: Nominatim (OpenStreetMap) - gratis, sin API key.
Politica de uso: maximo 1 request por segundo y User-Agent identificable.
https://operations.osmfoundation.org/policies/nominatim/
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass

from app.config import Settings
from app.utils import clean_text


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "PortaHojasDeRuta/1.0 (automatizacion interna)"

# Contexto que se agrega a las busquedas para desambiguar localidades
# ("San Francisco" existe en 40 paises).
CONTEXTO_DEFECTO = "Argentina"

_ultimo_request = 0.0
_ESPERA_MINIMA = 1.1  # segundos entre requests a Nominatim

# Abreviaturas comunes en los nombres de lugares.
# Nominatim no las entiende: "Est. Clucellas" no matchea con
# "Estacion Clucellas", asi que las expandimos antes de consultar.
ABREVIATURAS = [
    (r"\best\.?\s+", "estacion "),
    (r"\bpque\.?\s+", "parque "),
    (r"\bpje\.?\s+", "paraje "),
    (r"\bcol\.?\s+", "colonia "),
    (r"\bsta\.?\s+", "santa "),
    (r"\bsto\.?\s+", "santo "),
    (r"\bsn\.?\s+", "san "),
    (r"\bgral\.?\s+", "general "),
    (r"\bcnel\.?\s+", "coronel "),
    (r"\bpte\.?\s+", "presidente "),
    (r"\bdr\.?\s+", "doctor "),
    (r"\bing\.?\s+", "ingeniero "),
    (r"\bcap\.?\s+", "capitan "),
    (r"\bvda\.?\s+", "villa "),
    (r"\bav\.?\s+", "avenida "),
]


def expandir_abreviaturas(texto: str) -> str:
    """'Est. Clucellas' -> 'estacion Clucellas'"""
    resultado = clean_text(texto)
    for patron, reemplazo in ABREVIATURAS:
        resultado = re.sub(patron, reemplazo, resultado, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", resultado).strip()


@dataclass(frozen=True)
class Ubicacion:
    lat: float
    lon: float
    etiqueta: str
    origen: str  # "manual" | "cache" | "nominatim"
    km_referencia: float = 0.0   # distancia al taller, para detectar disparates

    @property
    def par(self) -> tuple[float, float]:
        return (self.lat, self.lon)

    def sospechosa(self, km_max: float) -> bool:
        """True si quedo mucho mas lejos de lo esperable para un cliente."""
        return self.origen != "manual" and km_max > 0 and self.km_referencia > km_max


class GeocodeError(RuntimeError):
    """No se pudo resolver la direccion."""


# ---------------------------------------------------------------- cache


def _conectar(settings: Settings) -> sqlite3.Connection:
    conn = sqlite3.connect(settings.services_db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS geocache (
            consulta   TEXT PRIMARY KEY,
            lat        REAL NOT NULL,
            lon        REAL NOT NULL,
            etiqueta   TEXT DEFAULT '',
            fecha      TEXT DEFAULT (datetime('now'))
        )
        """
    )
    # Distancia al taller, agregada despues de la version inicial
    columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(geocache)")}
    if "km_referencia" not in columnas:
        conn.execute("ALTER TABLE geocache ADD COLUMN km_referencia REAL DEFAULT 0")
    conn.commit()
    return conn


def _clave(texto: str) -> str:
    return re.sub(r"\s+", " ", clean_text(texto)).strip().lower()


def leer_cache(settings: Settings, texto: str) -> Ubicacion | None:
    with _conectar(settings) as conn:
        fila = conn.execute(
            "SELECT lat, lon, etiqueta, COALESCE(km_referencia, 0) "
            "FROM geocache WHERE consulta = ?",
            (_clave(texto),),
        ).fetchone()
    if fila is None:
        return None
    return Ubicacion(
        lat=fila[0], lon=fila[1], etiqueta=fila[2] or texto,
        origen="cache", km_referencia=fila[3],
    )


def guardar_cache(settings: Settings, texto: str, ubicacion: Ubicacion) -> None:
    with _conectar(settings) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO geocache "
            "(consulta, lat, lon, etiqueta, km_referencia) VALUES (?, ?, ?, ?, ?)",
            (
                _clave(texto), ubicacion.lat, ubicacion.lon,
                ubicacion.etiqueta, ubicacion.km_referencia,
            ),
        )
        conn.commit()


def borrar_cache(settings: Settings, texto: str | None = None) -> int:
    """Borra una entrada del cache, o todo el cache si texto es None."""
    with _conectar(settings) as conn:
        if texto is None:
            cur = conn.execute("DELETE FROM geocache")
        else:
            cur = conn.execute("DELETE FROM geocache WHERE consulta = ?", (_clave(texto),))
        conn.commit()
        return cur.rowcount


def listar_cache(settings: Settings) -> list[tuple[str, float, float, str]]:
    with _conectar(settings) as conn:
        return conn.execute(
            "SELECT consulta, lat, lon, etiqueta FROM geocache ORDER BY consulta"
        ).fetchall()


# ------------------------------------------------------- coords manuales


_COORD_RE = re.compile(
    r"^\s*(-?\d{1,3}(?:[.,]\d+)?)\s*[,;/ ]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$"
)


def parsear_coordenadas(texto: str) -> Ubicacion | None:
    """Interpreta un texto tipo '-31.4201, -64.1888' como coordenadas.

    Acepta coma o punto decimal, separadas por coma, punto y coma o espacio.
    Devuelve None si el texto no tiene forma de par de coordenadas.
    """
    texto = clean_text(texto)
    if not texto:
        return None
    match = _COORD_RE.match(texto)
    if not match:
        return None
    try:
        lat = float(match.group(1).replace(",", "."))
        lon = float(match.group(2).replace(",", "."))
    except ValueError:
        return None
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None
    return Ubicacion(lat=lat, lon=lon, etiqueta=texto, origen="manual")


# ------------------------------------------------------------ nominatim


def _distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en linea recta entre dos puntos, en km."""
    from math import asin, cos, radians, sin, sqrt

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    h = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * 6371.0 * asin(sqrt(h))


# Preferencia por tipo de lugar: una localidad es mejor candidato que
# un comercio, una calle o el centroide de una provincia entera.
_BONUS_TIPO = {
    "city": 120.0,
    "town": 120.0,
    "village": 100.0,
    "hamlet": 80.0,
    "municipality": 60.0,
    "administrative": 20.0,
}


def _puntaje(candidato: dict, referencia: Ubicacion | None) -> float:
    """Puntaje de un candidato de Nominatim. Mas alto es mejor.

    Combina tres senales:
      - que sea una localidad y no otra cosa
      - la 'importance' que da Nominatim
      - la cercania al punto de referencia (el taller)
    """
    puntos = _BONUS_TIPO.get(candidato.get("type", ""), 0.0)
    puntos += float(candidato.get("importance", 0) or 0) * 100

    if referencia is not None:
        km = _distancia_km(
            referencia.lat, referencia.lon,
            float(candidato["lat"]), float(candidato["lon"]),
        )
        # Penalizacion suave: 1 punto cada 5 km. A 500 km ya pierde 100 puntos,
        # suficiente para que una localidad lejana pierda contra una cercana.
        puntos -= km / 5.0

    return puntos


def _consultar_nominatim(consulta: str, referencia: Ubicacion | None = None) -> Ubicacion:
    """Busca la consulta y devuelve el mejor candidato.

    Pide varios resultados y los puntua en vez de quedarse con el primero:
    con nombres ambiguos ('Lopez', 'Santa Fe') el primero suele ser el
    equivocado.
    """
    global _ultimo_request

    import requests

    espera = _ESPERA_MINIMA - (time.monotonic() - _ultimo_request)
    if espera > 0:
        time.sleep(espera)

    respuesta = requests.get(
        NOMINATIM_URL,
        params={
            "q": consulta,
            "format": "json",
            "limit": 10,
            "countrycodes": "ar",
            "addressdetails": 0,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    _ultimo_request = time.monotonic()

    if respuesta.status_code != 200:
        raise GeocodeError(f"Nominatim respondio {respuesta.status_code} para '{consulta}'")

    datos = respuesta.json()
    if not datos:
        raise GeocodeError(f"No se encontro ubicacion para '{consulta}'")

    mejor = max(datos, key=lambda c: _puntaje(c, referencia))
    lat, lon = float(mejor["lat"]), float(mejor["lon"])
    km = (
        _distancia_km(referencia.lat, referencia.lon, lat, lon)
        if referencia is not None else 0.0
    )
    return Ubicacion(
        lat=lat, lon=lon,
        etiqueta=mejor.get("display_name", consulta),
        origen="nominatim",
        km_referencia=round(km, 1),
    )


# ------------------------------------------------------------- publico


def geocodificar(
    settings: Settings,
    lugar: str,
    coordenadas_manuales: str = "",
    contexto: str = CONTEXTO_DEFECTO,
    referencia: Ubicacion | None = None,
) -> Ubicacion:
    """Resuelve un lugar a coordenadas.

    Orden de prioridad:
      1. coordenadas_manuales (columna 'Coordenadas' del Sheet)
      2. cache local
      3. Nominatim (y se guarda en cache)

    `referencia` (normalmente el taller) se usa para desempatar entre
    candidatos con el mismo nombre: gana el mas cercano.

    Lanza GeocodeError si no se pudo resolver.
    """
    manual = parsear_coordenadas(coordenadas_manuales)
    if manual is not None:
        return manual

    lugar = clean_text(lugar)
    if not lugar:
        raise GeocodeError("Lugar vacio")

    # El lugar tambien puede venir como coordenadas directamente
    directo = parsear_coordenadas(lugar)
    if directo is not None:
        return directo

    cacheado = leer_cache(settings, lugar)
    if cacheado is not None:
        return cacheado

    # Se prueban varias formas del mismo nombre, de la mas fiel a la mas laxa
    intentos: list[str] = [lugar]
    expandido = expandir_abreviaturas(lugar)
    if expandido.lower() != lugar.lower():
        intentos.append(expandido)
    # Ultimo recurso: sacar el prefijo generico.
    # OJO: no se incluyen "villa" ni "puerto" porque en Argentina suelen ser
    # parte del nombre real ("Villa Maria" no es "Maria").
    sin_prefijo = re.sub(
        r"^(estacion|paraje|colonia)\s+", "", expandido, flags=re.IGNORECASE
    ).strip()
    if len(sin_prefijo) > 3 and sin_prefijo.lower() != expandido.lower():
        intentos.append(sin_prefijo)

    ultimo_error: Exception | None = None
    for intento in intentos:
        consulta = intento
        if contexto and contexto.lower() not in intento.lower():
            consulta = f"{intento}, {contexto}"
        try:
            ubicacion = _consultar_nominatim(consulta, referencia)
        except GeocodeError as exc:
            ultimo_error = exc
            continue
        guardar_cache(settings, lugar, ubicacion)
        return ubicacion

    raise GeocodeError(
        f"No se encontro ubicacion para '{lugar}'"
        + (f" (se probo tambien: {', '.join(intentos[1:])})" if len(intentos) > 1 else "")
    ) from ultimo_error


def geocodificar_lote(
    settings: Settings,
    lugares: list[tuple[str, str]],
    contexto: str = CONTEXTO_DEFECTO,
    referencia: Ubicacion | None = None,
) -> tuple[dict[str, Ubicacion], dict[str, str]]:
    """Geocodifica una lista de (lugar, coordenadas_manuales).

    Retorna (resueltos, fallidos):
      resueltos: {lugar: Ubicacion}
      fallidos:  {lugar: motivo}
    """
    resueltos: dict[str, Ubicacion] = {}
    fallidos: dict[str, str] = {}

    vistos: set[str] = set()
    for lugar, coords in lugares:
        clave = _clave(lugar)
        if not clave or clave in vistos:
            continue
        vistos.add(clave)
        try:
            resueltos[lugar] = geocodificar(settings, lugar, coords, contexto, referencia)
        except GeocodeError as exc:
            fallidos[lugar] = str(exc)
        except Exception as exc:  # noqa: BLE001
            fallidos[lugar] = f"{type(exc).__name__}: {exc}"

    return resueltos, fallidos


def ubicacion_taller(settings: Settings) -> Ubicacion:
    """Punto de partida y regreso de las rutas."""
    manual = parsear_coordenadas(settings.taller_coords)
    if manual is not None:
        return manual
    direccion = clean_text(settings.taller_direccion)
    if not direccion:
        raise GeocodeError(
            "Falta configurar TALLER_DIRECCION o TALLER_COORDS en el .env"
        )
    return geocodificar(settings, direccion)


def link_maps(ubicacion: Ubicacion) -> str:
    return f"https://www.google.com/maps?q={ubicacion.lat},{ubicacion.lon}"
