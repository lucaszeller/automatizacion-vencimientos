"""Lectura del Google Sheet 'Pedido de servicios' via Service Account.

Requiere:
    pip install gspread google-auth

Configuracion en .env:
    GOOGLE_CREDENTIALS_PATH=credenciales/hojas-de-ruta.json
    SHEET_PEDIDOS_ID=1IQyZ3ZlzVw7DKgc2_iiwUjAVu17pFHPWe_twbVtatIU
    SHEET_PEDIDOS_HOJA=Hoja 1
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.config import Settings
from app.utils import clean_text


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# Fila del Sheet donde estan los encabezados (fila 1 es el titulo "Pedido de servicios")
HEADER_ROW = 2

# Mapeo de encabezados del Sheet -> nombre interno
COLUMN_ALIASES = {
    "fecha de pedido": "fecha_pedido",
    "n° de soporte": "numero_soporte",
    "nº de soporte": "numero_soporte",
    "no de soporte": "numero_soporte",
    "cliente": "cliente",
    "telefono de contacto": "contacto",
    "teléfono de contacto": "contacto",
    "marca y modelo": "equipo",
    "tipo de servicio": "tipo_servicio",
    "lugar": "lugar",
    "extras": "extras",
    "mecanico": "mecanico",
    "mecánico": "mecanico",
    "fecha programada": "fecha_programada",
    "aprobado": "aprobado",
    "coordenadas": "coordenadas",
    "estado hr": "estado_hr",
}

CAMPOS = [
    "fila",
    "fecha_pedido",
    "numero_soporte",
    "cliente",
    "contacto",
    "equipo",
    "tipo_servicio",
    "lugar",
    "extras",
    "mecanico",
    "fecha_programada",
    "aprobado",
    "coordenadas",
    "estado_hr",
]

VALORES_APROBADO = {"si", "sí", "s", "ok", "x", "true", "1", "aprobado"}


class SheetNoConfigurado(RuntimeError):
    """Falta configurar credenciales o el ID del Sheet."""


def _abrir_hoja_por_id(settings: Settings, sheet_id: str, nombre_hoja: str = ""):
    """Abre cualquier Google Sheet con el service account configurado."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise SheetNoConfigurado(
            "Falta instalar dependencias: pip install gspread google-auth"
        ) from exc

    cred_path = settings.google_credentials_path
    if not cred_path or not cred_path.exists():
        raise SheetNoConfigurado(
            f"No se encontro el JSON de credenciales en: {cred_path}"
        )
    if not sheet_id:
        raise SheetNoConfigurado("Falta el ID del Sheet en el .env")

    creds = Credentials.from_service_account_file(str(cred_path), scopes=SCOPES)
    cliente = gspread.authorize(creds)
    libro = cliente.open_by_key(sheet_id)

    nombre_hoja = clean_text(nombre_hoja)
    if nombre_hoja:
        return libro.worksheet(nombre_hoja)
    return libro.get_worksheet(0)


def _abrir_hoja(settings: Settings):
    """Devuelve el worksheet de pedidos. Lanza SheetNoConfigurado si falta config."""
    if not settings.sheet_pedidos_id:
        raise SheetNoConfigurado("Falta SHEET_PEDIDOS_ID en el .env")
    return _abrir_hoja_por_id(
        settings, settings.sheet_pedidos_id, settings.sheet_pedidos_hoja
    )


def _normalizar_encabezado(valor: Any) -> str:
    texto = clean_text(valor).lower().strip()
    return COLUMN_ALIASES.get(texto, "")


def leer_pedidos(settings: Settings) -> pd.DataFrame:
    """Lee todos los pedidos del Sheet.

    Retorna un DataFrame con las columnas de CAMPOS.
    'fila' es el numero de fila real en el Sheet (para poder escribir de vuelta).
    """
    hoja = _abrir_hoja(settings)
    valores = hoja.get_all_values()
    return parsear_valores(valores)


def parsear_valores(valores: list[list[str]]) -> pd.DataFrame:
    """Convierte la matriz cruda del Sheet en un DataFrame normalizado.

    Separado de leer_pedidos para poder testear sin conexion.
    """
    if len(valores) < HEADER_ROW:
        return pd.DataFrame(columns=CAMPOS)

    encabezados = valores[HEADER_ROW - 1]
    indice_por_campo: dict[str, int] = {}
    for pos, celda in enumerate(encabezados):
        campo = _normalizar_encabezado(celda)
        if campo and campo not in indice_por_campo:
            indice_por_campo[campo] = pos

    filas = []
    for offset, fila_cruda in enumerate(valores[HEADER_ROW:], start=HEADER_ROW + 1):
        registro: dict[str, Any] = {"fila": offset}
        for campo in CAMPOS:
            if campo == "fila":
                continue
            pos = indice_por_campo.get(campo)
            valor = fila_cruda[pos] if pos is not None and pos < len(fila_cruda) else ""
            registro[campo] = clean_text(valor)
        # Descartar filas totalmente vacias
        if any(registro[c] for c in CAMPOS if c != "fila"):
            filas.append(registro)

    df = pd.DataFrame(filas, columns=CAMPOS)
    if df.empty:
        return df

    df["esta_aprobado"] = df["aprobado"].str.lower().str.strip().isin(VALORES_APROBADO)
    df["es_taller"] = df["lugar"].str.upper().str.strip().eq("TALLER")
    df["tiene_hr"] = df["estado_hr"].str.strip().ne("")
    return df


def pedidos_pendientes(df: pd.DataFrame) -> pd.DataFrame:
    """Pedidos aprobados, en campo, sin hoja de ruta generada todavia."""
    if df.empty:
        return df
    return df[df["esta_aprobado"] & ~df["es_taller"] & ~df["tiene_hr"]].copy()


def marcar_hoja_generada(settings: Settings, filas: list[int], marca: str) -> None:
    """Escribe la marca de 'Estado HR' en las filas indicadas del Sheet."""
    if not filas:
        return
    hoja = _abrir_hoja(settings)
    encabezados = hoja.row_values(HEADER_ROW)
    columna = None
    for pos, celda in enumerate(encabezados, start=1):
        if _normalizar_encabezado(celda) == "estado_hr":
            columna = pos
            break
    if columna is None:
        raise SheetNoConfigurado(
            "No existe la columna 'Estado HR' en el Sheet. Agregala y reintenta."
        )

    actualizaciones = [
        {"range": _celda_a1(fila, columna), "values": [[marca]]} for fila in filas
    ]
    hoja.batch_update(actualizaciones)


def _celda_a1(fila: int, columna: int) -> str:
    letras = ""
    n = columna
    while n > 0:
        n, resto = divmod(n - 1, 26)
        letras = chr(65 + resto) + letras
    return f"{letras}{fila}"
