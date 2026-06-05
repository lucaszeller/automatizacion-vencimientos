"""Procesamiento de services y vencimientos."""

from datetime import date, timedelta
import math

import pandas as pd

from app.config import Settings
from app.utils import build_aviso_id, clean_text


ALERT_STATES = {"PROXIMO_A_VENCER", "VENCE_HOY"}


def process_services(df: pd.DataFrame, settings: Settings, today: date | None = None) -> pd.DataFrame:
    today = today or date.today()
    rows = []
    work = df.copy()
    work["grupo"] = work.apply(_group_key, axis=1)

    for _, group in work.groupby("grupo", dropna=False):
        ordered = group.sort_values("fecha_service", ascending=False)
        current = ordered.iloc[0]
        previous = ordered.iloc[1] if len(ordered) > 1 else None
        rows.append(_process_group(current, previous, settings, today))

    result = pd.DataFrame(rows)
    if not result.empty:
        result["id_interno_aviso"] = result.apply(build_aviso_id, axis=1)
    return result.sort_values(["estado", "cliente", "serial"], kind="stable")


def process_services_for_period(
    df: pd.DataFrame,
    settings: Settings,
    period_start: date,
    period_end: date,
    today: date | None = None,
) -> pd.DataFrame:
    today = today or date.today()
    rows = []
    work = df.copy()
    work["grupo"] = work.apply(_group_key, axis=1)
    work["_soporte_num"] = pd.to_numeric(work["numero_soporte"], errors="coerce")
    current_rows = work[
        (work["fecha_service"] >= period_start)
        & (work["fecha_service"] < period_end)
    ].sort_values(["fecha_service", "_soporte_num"], kind="stable")

    for index, current in current_rows.iterrows():
        group = work[(work["grupo"] == current["grupo"]) & (work.index != index)].copy()
        previous_candidates = group[
            (group["fecha_service"] < current["fecha_service"])
            | (
                (group["fecha_service"] == current["fecha_service"])
                & (group["_soporte_num"] < current["_soporte_num"])
            )
        ].sort_values(["fecha_service", "_soporte_num"], ascending=False, kind="stable")
        previous = previous_candidates.iloc[0] if not previous_candidates.empty else None
        rows.append(_process_group(current, previous, settings, today))

    result = pd.DataFrame(rows)
    if not result.empty:
        result["id_interno_aviso"] = result.apply(build_aviso_id, axis=1)
    return result


def _group_key(row: pd.Series) -> str:
    serial = clean_text(row.get("serial"))
    if serial:
        return f"serial:{serial.lower()}"
    return f"equipo:{clean_text(row.get('cliente')).lower()}|{clean_text(row.get('equipo')).lower()}"


def _base_output(current: pd.Series, previous: pd.Series | None) -> dict:
    return {
        "cliente": clean_text(current.get("cliente")),
        "equipo": clean_text(current.get("equipo")),
        "serial": clean_text(current.get("serial")),
        "lugar": clean_text(current.get("lugar")),
        "mail_cliente": clean_text(current.get("mail_cliente")),
        "telefono_cliente": clean_text(current.get("telefono_cliente")),
        "fecha_service_anterior": previous.get("fecha_service") if previous is not None else None,
        "soporte_anterior": clean_text(previous.get("numero_soporte")) if previous is not None else "",
        "horas_anteriores": previous.get("horas") if previous is not None else None,
        "tipo_service_anterior": clean_text(previous.get("tipo_service")) if previous is not None else "",
        "fecha_service_actual": current.get("fecha_service"),
        "soporte_actual": clean_text(current.get("numero_soporte")),
        "horas_actuales": current.get("horas"),
        "tipo_service_actual": clean_text(current.get("tipo_service")),
        "diferencia_horas": None,
        "diferencia_dias": None,
        "promedio_horas_dia": None,
        "horas_para_proximo_service": None,
        "fecha_estimada_proximo_service": None,
        "dias_restantes": None,
        "estado": "SIN_DATOS",
        "enviar_aviso": False,
        "mail_enviado": False,
        "fecha_envio_mail": None,
        "error_envio": "",
        "observaciones": clean_text(current.get("observaciones")),
    }


def _process_group(
    current: pd.Series,
    previous: pd.Series | None,
    settings: Settings,
    today: date,
) -> dict:
    row = _base_output(current, previous)
    if previous is None:
        return row

    current_date = current.get("fecha_service")
    previous_date = previous.get("fecha_service")
    current_hours = current.get("horas")
    previous_hours = previous.get("horas")
    if not _is_hour_service(row["tipo_service_actual"]) or not _is_hour_service(row["tipo_service_anterior"]):
        return row
    if (
        current_date is None
        or previous_date is None
        or _missing_number(current_hours)
        or _missing_number(previous_hours)
    ):
        return row

    diff_days = (current_date - previous_date).days
    diff_hours = current_hours - previous_hours
    row["diferencia_horas"] = diff_hours
    row["diferencia_dias"] = diff_days
    row["horas_para_proximo_service"] = settings.horas_para_proximo_service

    if diff_days <= 0 or diff_hours <= 0:
        row["estado"] = "ERROR_CALCULO"
        return row

    avg = diff_hours / diff_days
    row["promedio_horas_dia"] = avg
    if avg <= 0:
        row["estado"] = "ERROR_CALCULO"
        return row

    estimated_days = settings.horas_para_proximo_service / avg
    next_date = current_date + timedelta(days=estimated_days)
    row["fecha_estimada_proximo_service"] = next_date
    row["dias_restantes"] = (next_date - today).days

    if not row["telefono_cliente"]:
        row["estado"] = "SIN_CONTACTO"
    elif next_date < today:
        row["estado"] = "VENCIDO"
    elif next_date == today:
        row["estado"] = "VENCE_HOY"
    elif next_date <= today + timedelta(days=settings.dias_antes_aviso):
        row["estado"] = "PROXIMO_A_VENCER"
    else:
        row["estado"] = "OK"

    row["enviar_aviso"] = row["estado"] in ALERT_STATES and bool(row["telefono_cliente"])
    return row


def _missing_number(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def _is_hour_service(value: str) -> bool:
    return "hs" in clean_text(value).lower()
