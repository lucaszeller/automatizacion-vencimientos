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
    "serie_equipo",
    "marca_equipo",
    "modelo_equipo",
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
    normalized["serie_equipo"]  = normalized["serie_equipo"].map(clean_text)
    normalized["marca_equipo"]  = normalized["marca_equipo"].map(clean_text)
    normalized["modelo_equipo"] = normalized["modelo_equipo"].map(clean_text)
    normalized["numero_soporte"] = normalized["numero_soporte"].map(clean_text)
    normalized["tipo_service"] = normalized["tipo_service"].map(clean_text)
    normalized["lugar"] = normalized["lugar"].map(clean_text)
    normalized["mail_cliente"] = normalized["mail_cliente"].map(clean_text)
    normalized["telefono_cliente"] = normalized["telefono_cliente"].map(clean_text)
    normalized["observaciones"] = normalized["observaciones"].map(clean_text)
    normalized["tipo_service"] = normalized.apply(_complete_tipo_service, axis=1)
    normalized["fecha_service"] = normalized["fecha_service"].map(to_date)
    normalized["horas"] = normalized["horas"].map(to_number)
    normalized = normalized.dropna(subset=["fecha_service"])

    # Deduplicar por numero_soporte: si el mismo soporte tiene varias filas (por multiples
    # telefonos en TacticaSoft), quedarse con la que tenga telefono valido; si no, la primera.
    if "numero_soporte" in normalized.columns:
        has_phone = normalized["telefono_cliente"].str.strip().ne("").fillna(False)
        normalized["_has_phone"] = has_phone
        normalized = (
            normalized
            .sort_values("_has_phone", ascending=False)
            .drop_duplicates(subset=["numero_soporte"], keep="first")
            .drop(columns=["_has_phone"])
            .reset_index(drop=True)
        )

    return normalized


def _complete_tipo_service(row: pd.Series) -> str:
    current = clean_text(row.get("tipo_service"))
    if current:
        return current
    text = clean_text(row.get("observaciones"))
    # lecturas iniciales de horimetro (pre entrega, consulta de hs)
    if re.search(r"chequeo\s+pre\s+entrega", text, flags=re.IGNORECASE):
        return "entrega"
    if re.search(r"consulta\s+de\s+hs", text, flags=re.IGNORECASE):
        return "consulta"
    # semestral: "servicio semestral", "servicio de semestral", "servicio preventivo semestral", etc.
    if re.search(r"servi(?:cio|ce)\s+(?:de\s+)?(?:mantenimiento\s+)?(?:preventivo\s+)?semestral", text, flags=re.IGNORECASE):
        return "semestral"
    # trimestral: "servicio trimestral", "service trimestral", etc.
    if re.search(r"servi(?:cio|ce)\s+(?:de\s+)?(?:mantenimiento\s+)?(?:preventivo\s+)?trimestral", text, flags=re.IGNORECASE):
        return "trimestral"
    # anual: "servicio anual", "service anual", "mantenimiento anual", etc.
    if re.search(r"(?:servi(?:cio|ce)|mantenimiento)\s+(?:de\s+)?(?:preventivo\s+)?anual", text, flags=re.IGNORECASE):
        return "anual"
    if re.search(r"preventivo\s+anual", text, flags=re.IGNORECASE):
        return "anual"
    # km
    match = re.search(r"servi(?:cio|ce)\s+([0-9][0-9.\s]*)\s*_?\s*km", text, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1).strip()} Km"
    # patron general para extraer NNN Hs de cualquier contexto de service/preventivo
    # cubre: "servicio", "service", "servicios", "sevicio" (sin r), "servico" (sin i)
    _hs_pattern = r"([0-9]{2,5})\s*_?\s*h(?:s)?\b"
    # servi(ci?o|ce) cubre: "servicio", "servico" (sin 2da i), "service"
    # sevi(ci?o|ce)  cubre: "sevicio" (sin r), "sevice"
    _svc = r"(?:servi|sevi)(?:ci?o|ce)s?"
    match = (
        re.search(_svc + r"\s+(?:de\s+)?(?:mantenimiento\s+)?(?:preventivo\s+)?(?:de\s+)?" + _hs_pattern, text, flags=re.IGNORECASE)
        or re.search(r"preventivo\s+(?:de\s+)?" + _hs_pattern, text, flags=re.IGNORECASE)
        or re.search(r"mantenimiento\s+(?:de\s+)?preventivo\s+(?:de\s+)?" + _hs_pattern, text, flags=re.IGNORECASE)
    )
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
