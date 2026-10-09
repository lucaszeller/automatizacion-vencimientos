"""Tabla de equivalencias: equipo de TacticaSoft -> numero de serie real.

TacticaSoft guarda dos cosas distintas:
  - productosstocknroserie.Numero  ->  "HELI Nº 1 (3246)"   (identificador interno)
  - info.Campo5 de la solapa Info  ->  "010259U0280"        (serie real del equipo)

No pudimos determinar la relacion entre ambas tablas desde la base, asi que
la equivalencia se carga desde un export de Tactica y queda cacheada en
data/services.db.

Uso tipico:
    python _cargar_series.py "C:\\ruta\\export_nroserie.xlsx"
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path

from app.config import Settings
from app.utils import clean_text


# Nombres aceptados para cada columna del export (en minusculas, sin acentos)
COLUMNAS_EQUIPO = {
    "nro de serie", "n de serie", "numero de serie", "nro serie",
    "equipo", "numero", "nro", "descripcion",
}
COLUMNAS_SERIE = {
    "serie", "nro serie real", "serial", "numero de serie real", "campo5",
}


def _normalizar(texto: str) -> str:
    """Clave de comparacion: sin acentos, sin espacios, en minusculas."""
    texto = unicodedata.normalize("NFKD", clean_text(texto))
    texto = texto.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", "", texto)


def clave_equipo(valor: str) -> str:
    """Clave a partir del identificador de Tactica.

    'HELI Nº 1 (3246)' -> '3246'   (el numero entre parentesis es lo estable)
    Si no hay parentesis, se usa el nombre normalizado.
    """
    texto = clean_text(valor)
    match = re.search(r"\((\d+)\)\s*$", texto)
    if match:
        return match.group(1)
    return _normalizar(texto)


# ------------------------------------------------------------------ cache


def _conectar(settings: Settings) -> sqlite3.Connection:
    conn = sqlite3.connect(settings.services_db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS series_equipos (
            clave       TEXT PRIMARY KEY,
            equipo      TEXT NOT NULL,
            serie       TEXT NOT NULL,
            fecha_carga TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    return conn


def buscar_serie(settings: Settings, equipo: str) -> str:
    """Serie real del equipo, o cadena vacia si no esta cargada."""
    clave = clave_equipo(equipo)
    if not clave:
        return ""
    try:
        with _conectar(settings) as conn:
            fila = conn.execute(
                "SELECT serie FROM series_equipos WHERE clave = ?", (clave,)
            ).fetchone()
    except sqlite3.Error:
        return ""
    return fila[0] if fila else ""


def listar(settings: Settings) -> list[tuple[str, str, str]]:
    with _conectar(settings) as conn:
        return conn.execute(
            "SELECT clave, equipo, serie FROM series_equipos ORDER BY clave"
        ).fetchall()


def contar(settings: Settings) -> int:
    try:
        with _conectar(settings) as conn:
            return conn.execute("SELECT COUNT(*) FROM series_equipos").fetchone()[0]
    except sqlite3.Error:
        return 0


# ------------------------------------------------------------ importacion


def _detectar_columnas(columnas: list[str]) -> tuple[str | None, str | None]:
    """Ubica cual columna es el equipo y cual la serie."""
    col_equipo = col_serie = None
    for nombre in columnas:
        clave = _normalizar(nombre).replace("_", "")
        for candidata in COLUMNAS_SERIE:
            if clave == _normalizar(candidata):
                col_serie = col_serie or nombre
        for candidata in COLUMNAS_EQUIPO:
            if clave == _normalizar(candidata):
                col_equipo = col_equipo or nombre
    return col_equipo, col_serie


def importar(settings: Settings, ruta: Path, reemplazar: bool = True) -> dict:
    """Carga el export de Tactica (xlsx o csv) en la tabla local.

    Retorna {"filas", "cargadas", "sin_serie", "duplicadas", "columnas"}.
    """
    import pandas as pd

    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")

    if ruta.suffix.lower() in {".csv", ".txt"}:
        df = pd.read_csv(ruta, dtype=str, sep=None, engine="python")
    else:
        df = pd.read_excel(ruta, dtype=str)

    df.columns = [str(c).strip() for c in df.columns]
    col_equipo, col_serie = _detectar_columnas(list(df.columns))

    if col_equipo is None or col_serie is None:
        raise ValueError(
            "No se reconocieron las columnas del export.\n"
            f"Columnas encontradas: {', '.join(df.columns)}\n\n"
            "Se esperaba una columna con el identificador del equipo "
            "(ej. 'Nº de Serie') y otra con la serie real (ej. 'SERIE')."
        )

    registros: dict[str, tuple[str, str]] = {}
    sin_serie = 0
    duplicadas = 0

    for _, fila in df.iterrows():
        equipo = clean_text(fila.get(col_equipo))
        serie = clean_text(fila.get(col_serie))
        if not equipo:
            continue
        if not serie:
            sin_serie += 1
            continue
        clave = clave_equipo(equipo)
        if not clave:
            continue
        if clave in registros and registros[clave][1] != serie:
            duplicadas += 1
            continue
        registros[clave] = (equipo, serie)

    with _conectar(settings) as conn:
        if reemplazar:
            conn.execute("DELETE FROM series_equipos")
        conn.executemany(
            "INSERT OR REPLACE INTO series_equipos (clave, equipo, serie) VALUES (?, ?, ?)",
            [(c, e, s) for c, (e, s) in registros.items()],
        )
        conn.commit()

    return {
        "filas": len(df),
        "cargadas": len(registros),
        "sin_serie": sin_serie,
        "duplicadas": duplicadas,
        "columnas": (col_equipo, col_serie),
    }
