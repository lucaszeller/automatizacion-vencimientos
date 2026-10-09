"""Conexion read-only a TacticaSoft."""

from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd

from app.config import Settings


def _read_query(path: Path) -> str:
    query = path.read_text(encoding="utf-8").strip()
    normalized = query.lstrip().lower()
    if not (normalized.startswith("select") or normalized.startswith("with") or normalized.startswith("/*")):
        raise ValueError("La consulta de TacticaSoft debe ser read-only y comenzar con SELECT o WITH.")
    blocked = {" update ", " delete ", " insert ", " merge ", " drop ", " alter ", " truncate "}
    lowered = f" {normalized} "
    found = [word.strip() for word in blocked if word in lowered]
    if found:
        raise ValueError(f"La consulta contiene operaciones no permitidas: {', '.join(found)}")
    return query


def _verificar_configuracion(settings: Settings) -> None:
    """Avisa con un mensaje entendible si falta la configuracion de la base.

    El caso tipico es abrir el EXE desde una carpeta sin .env: ahi DB_HOST
    queda vacio, pymysql asume localhost y el error que ve el usuario es un
    'Can't connect to MySQL server on localhost' que no dice nada util.
    """
    from app.config import APP_DIR

    faltantes = [
        nombre
        for nombre, valor in (
            ("DB_HOST", settings.db_host),
            ("DB_NAME", settings.db_name),
            ("DB_USER", settings.db_user),
        )
        if not str(valor).strip()
    ]
    if not faltantes:
        return

    archivo_env = APP_DIR / ".env"
    detalle = (
        f"No se encontro el archivo de configuracion:\n  {archivo_env}\n\n"
        if not archivo_env.exists()
        else f"El archivo {archivo_env} existe pero le faltan datos.\n\n"
    )
    raise RuntimeError(
        "Falta la configuracion de conexion a TacticaSoft "
        f"({', '.join(faltantes)}).\n\n"
        + detalle
        + "Si abriste el programa desde la carpeta 'dist_build', cerralo y "
        "usa el de 'dist', que es el unico que tiene el .env al lado."
    )


def load_from_tactica(settings: Settings) -> pd.DataFrame:
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import URL
    except ModuleNotFoundError as exc:
        raise RuntimeError("Faltan dependencias de base de datos. Ejecutar: pip install -r requirements.txt") from exc

    _verificar_configuracion(settings)

    if not settings.db_query_path.exists():
        raise FileNotFoundError(f"No existe la consulta SQL: {settings.db_query_path}")

    query = _read_query(settings.db_query_path)
    engine_name = settings.db_engine.lower()
    if engine_name in {"mysql", "mariadb"}:
        url = URL.create(
            "mysql+pymysql",
            username=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=int(settings.db_port),
            database=settings.db_name,
            query={"charset": "utf8"},
        )
        engine = create_engine(url)
    elif engine_name == "sqlserver":
        odbc = (
            f"DRIVER={{{settings.db_driver}}};"
            f"SERVER={settings.db_host},{settings.db_port};"
            f"DATABASE={settings.db_name};"
            f"UID={settings.db_user};"
            f"PWD={settings.db_password};"
            "TrustServerCertificate=yes;"
        )
        engine = create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc)}")
    else:
        raise ValueError(f"DB_ENGINE no soportado: {settings.db_engine}")

    with engine.connect() as connection:
        return pd.read_sql(text(query), connection)
