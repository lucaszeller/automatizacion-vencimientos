"""Utilidades compartidas."""

from datetime import date, datetime
import re
from typing import Any

import pandas as pd


MONTH_NAMES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
}


def clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def to_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    text = clean_text(value).replace(",", ".")
    match = re.search(r"-?\d+(\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {column: clean_text(column).lower().strip() for column in df.columns}
    return df.rename(columns=mapping)


def build_aviso_id(row: pd.Series) -> str:
    cliente = clean_text(row.get("cliente"))
    serial = clean_text(row.get("serial")) or clean_text(row.get("equipo"))
    fecha = row.get("fecha_estimada_proximo_service")
    if hasattr(fecha, "isoformat"):
        fecha_text = fecha.isoformat()
    else:
        fecha_text = clean_text(fecha)
    tipo = clean_text(row.get("tipo_service_actual"))
    return f"{cliente}|{serial}|{fecha_text}|{tipo}"
