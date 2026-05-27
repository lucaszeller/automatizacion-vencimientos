"""Herramientas simples para inspeccionar la base de datos en modo lectura."""

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from app.config import Settings


def create_database_engine(settings: Settings):
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
        return create_engine(url)
    raise ValueError("El inspector inicial solo soporta mysql/mariadb.")


def list_tables(settings: Settings) -> pd.DataFrame:
    query = """
    SELECT table_name, table_rows
    FROM information_schema.tables
    WHERE table_schema = :schema
    ORDER BY table_name
    """
    with create_database_engine(settings).connect() as connection:
        return pd.read_sql(text(query), connection, params={"schema": settings.db_name})


def list_columns(settings: Settings, table_name: str) -> pd.DataFrame:
    query = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = :schema AND table_name = :table_name
    ORDER BY ordinal_position
    """
    with create_database_engine(settings).connect() as connection:
        return pd.read_sql(text(query), connection, params={"schema": settings.db_name, "table_name": table_name})
