"""Lectura y normalizacion de datos."""

from datetime import date, timedelta

import pandas as pd

from app.config import Settings
from app.conexion_tactica import load_from_tactica
from app.utils import clean_text, normalize_columns, to_date, to_number
import re


REQUIRED_COLUMNS = [
    "cliente",
    "equipo",
    "serial",
    "fecha_service",
    "numero_soporte",
    "horas",
    "tipo_service",
    "lugar",
    "mail_cliente",
    "telefono_cliente",
    "observaciones",
]


def load_source_data(settings: Settings) -> pd.DataFrame:
    if settings.data_source == "database":
        df = load_from_tactica(settings)
    elif settings.data_source == "excel":
        if not settings.excel_input_path.exists():
            raise FileNotFoundError(f"No existe el Excel de entrada: {settings.excel_input_path}")
        df = pd.read_excel(settings.excel_input_path)
    elif settings.data_source == "sample":
        df = build_sample_data()
    else:
        raise ValueError(f"DATA_SOURCE no soportado: {settings.data_source}")
    return normalize_service_data(df)


def normalize_service_data(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df).copy()
    aliases = {
        "fecha": "fecha_service",
        "nro soporte": "numero_soporte",
        "nº soporte": "numero_soporte",
        "soporte": "numero_soporte",
        "tipo de serv.": "tipo_service",
        "tipo de servicio": "tipo_service",
        "serializado": "serial",
        "mail": "mail_cliente",
        "email": "mail_cliente",
        "telefono": "telefono_cliente",
        "tel": "telefono_cliente",
        "celular": "telefono_cliente",
        "movil": "telefono_cliente",
        "whatsapp": "telefono_cliente",
        "telefono contacto": "telefono_cliente",
        "telefono cliente": "telefono_cliente",
    }
    df = df.rename(columns={col: aliases.get(col, col) for col in df.columns})
    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    normalized = df[REQUIRED_COLUMNS].copy()
    normalized["cliente"] = normalized["cliente"].map(clean_text)
    normalized["equipo"] = normalized["equipo"].map(clean_text)
    normalized["serial"] = normalized["serial"].map(clean_text)
    normalized["numero_soporte"] = normalized["numero_soporte"].map(clean_text)
    normalized["tipo_service"] = normalized["tipo_service"].map(clean_text)
    normalized["lugar"] = normalized["lugar"].map(clean_text)
    normalized["mail_cliente"] = normalized["mail_cliente"].map(clean_text)
    normalized["telefono_cliente"] = normalized["telefono_cliente"].map(clean_text)
    normalized["observaciones"] = normalized["observaciones"].map(clean_text)
    normalized["tipo_service"] = normalized.apply(_complete_tipo_service, axis=1)
    normalized["fecha_service"] = normalized["fecha_service"].map(to_date)
    normalized["horas"] = normalized["horas"].map(to_number)
    return normalized.dropna(subset=["fecha_service"])


def _complete_tipo_service(row: pd.Series) -> str:
    current = clean_text(row.get("tipo_service"))
    if current:
        return current
    text = clean_text(row.get("observaciones"))
    if re.search(r"servi(cio|ce)\s+preventivo\s+semestral", text, flags=re.IGNORECASE):
        return "semestral"
    match = re.search(r"servi(?:cio|ce)\s+([0-9][0-9.\s]*)\s*_?\s*km", text, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1).strip()} Km"
    match = re.search(r"servicio\s+([0-9]{2,5})\s*_?\s*h(?:s)?\b", text, flags=re.IGNORECASE)
    if not match:
        return ""
    return f"{match.group(1)} Hs"


def build_sample_data() -> pd.DataFrame:
    today = date.today()
    return pd.DataFrame(
        [
            {
                "cliente": "Cliente Proximo",
                "equipo": "Autoelevador 1",
                "serial": "SER-001",
                "fecha_service": today - timedelta(days=20),
                "numero_soporte": "SOP-1001",
                "horas": 1000,
                "tipo_service": "250 Hs",
                "lugar": "ZONA",
                "mail_cliente": "cliente.proximo@example.com",
                "telefono_cliente": "5491111111111",
                "observaciones": "",
            },
            {
                "cliente": "Cliente Proximo",
                "equipo": "Autoelevador 1",
                "serial": "SER-001",
                "fecha_service": today - timedelta(days=45),
                "numero_soporte": "SOP-0901",
                "horas": 750,
                "tipo_service": "1000 Hs",
                "lugar": "ZONA",
                "mail_cliente": "cliente.proximo@example.com",
                "telefono_cliente": "5491111111111",
                "observaciones": "",
            },
            {
                "cliente": "Cliente Sin Mail",
                "equipo": "Apilador 2",
                "serial": "SER-002",
                "fecha_service": today - timedelta(days=15),
                "numero_soporte": "SOP-1002",
                "horas": 520,
                "tipo_service": "500 Hs",
                "lugar": "TALLER",
                "mail_cliente": "",
                "telefono_cliente": "",
                "observaciones": "",
            },
            {
                "cliente": "Cliente Sin Mail",
                "equipo": "Apilador 2",
                "serial": "SER-002",
                "fecha_service": today - timedelta(days=40),
                "numero_soporte": "SOP-0902",
                "horas": 260,
                "tipo_service": "250 Hs",
                "lugar": "TALLER",
                "mail_cliente": "",
                "telefono_cliente": "",
                "observaciones": "",
            },
            {
                "cliente": "Cliente OK",
                "equipo": "Autoelevador 3",
                "serial": "SER-003",
                "fecha_service": today - timedelta(days=10),
                "numero_soporte": "SOP-1003",
                "horas": 2000,
                "tipo_service": "1000 Hs",
                "lugar": "ZONA",
                "mail_cliente": "cliente.ok@example.com",
                "telefono_cliente": "5491199999999",
                "observaciones": "",
            },
            {
                "cliente": "Cliente OK",
                "equipo": "Autoelevador 3",
                "serial": "SER-003",
                "fecha_service": today - timedelta(days=110),
                "numero_soporte": "SOP-0903",
                "horas": 1900,
                "tipo_service": "750 Hs",
                "lugar": "ZONA",
                "mail_cliente": "cliente.ok@example.com",
                "telefono_cliente": "5491199999999",
                "observaciones": "",
            },
        ]
    )
