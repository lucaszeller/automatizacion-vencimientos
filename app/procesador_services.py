"""Procesamiento de services y vencimientos."""

from datetime import date, timedelta
import math
import re

import pandas as pd

from app.config import Settings
from app.utils import build_aviso_id, clean_text


ALERT_STATES = {"PROXIMO_A_VENCER", "VENCE_HOY"}
# Tipos que se usan solo como punto de partida del calculo (anterior), nunca como service actual
_BASELINE_TYPES = {"entrega", "consulta"}


def process_services(df: pd.DataFrame, settings: Settings, today: date | None = None) -> pd.DataFrame:
    today = today or date.today()
    rows = []
    work = df.copy()
    work["grupo"] = work.apply(_group_key, axis=1)

    for _, group in work.groupby("grupo", dropna=False):
        ordered = group.sort_values("fecha_service", ascending=False)
        # Para el calculo usar solo registros con tipo de service;
        # los sin tipo son excepciones y se ignoran en el calculo.
        # Los tipos baseline (entrega, consulta) no aparecen como service actual
        # pero si pueden ser el service anterior.
        with_type = ordered[ordered["tipo_service"].str.strip().ne("")]
        serviceable = with_type[~with_type["tipo_service"].str.lower().isin(_BASELINE_TYPES)]
        if not serviceable.empty:
            current = serviceable.iloc[0]
            prev_candidates = with_type[with_type["fecha_service"] < current["fecha_service"]]
            if not prev_candidates.empty:
                # Preferir el anterior mas reciente que tenga horas cargadas
                prev_with_hours = prev_candidates[prev_candidates["horas"].notna()]
                previous = prev_with_hours.iloc[0] if not prev_with_hours.empty else prev_candidates.iloc[0]
            else:
                previous = None
        elif not with_type.empty:
            current = with_type.iloc[0]
            previous = None
        else:
            # Sin ningun tipo de service: mostrar igual con SIN_DATOS
            current = ordered.iloc[0]
            previous = None
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
        & ~work["tipo_service"].str.lower().isin(_BASELINE_TYPES)
    ].sort_values(["fecha_service", "_soporte_num"], kind="stable")

    for index, current in current_rows.iterrows():
        group = work[(work["grupo"] == current["grupo"]) & (work.index != index)].copy()
        previous_candidates = group[
            (
                (group["fecha_service"] < current["fecha_service"])
                | (
                    (group["fecha_service"] == current["fecha_service"])
                    & (group["_soporte_num"] < current["_soporte_num"])
                )
            )
            # Ignorar registros sin tipo de service como anterior para el calculo
            & group["tipo_service"].str.strip().ne("")
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
        "error_calculo_motivo": "",
        "observaciones": clean_text(current.get("observaciones")),
    }


_TIME_BASED_INTERVALS = {
    "semestral": "dias_service_semestral",
    "trimestral": "dias_service_trimestral",
}


def _is_time_based_service(tipo: str) -> bool:
    return clean_text(tipo).lower() in _TIME_BASED_INTERVALS


def _calc_time_based(row: dict, tipo: str, current_date: date, settings: Settings, today: date) -> dict:
    """Calcula proximo service para tipos con intervalo fijo en dias (semestral, trimestral)."""
    setting_key = _TIME_BASED_INTERVALS[tipo.lower()]
    interval_days = getattr(settings, setting_key)
    next_date = current_date + timedelta(days=interval_days)
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


def _process_group(
    current: pd.Series,
    previous: pd.Series | None,
    settings: Settings,
    today: date,
) -> dict:
    row = _base_output(current, previous)
    tipo_actual = clean_text(row["tipo_service_actual"]).lower()

    # Servicios con intervalo fijo en dias (semestral, trimestral)
    if _is_time_based_service(tipo_actual):
        current_date = current.get("fecha_service")
        if current_date is not None:
            return _calc_time_based(row, tipo_actual, current_date, settings, today)
        return row

    if previous is None:
        # Intento de calculo con un solo service: tasa = horas_actuales / dias_desde_service
        current_date = current.get("fecha_service")
        current_hours = current.get("horas")
        if (
            _is_hour_service(row["tipo_service_actual"])
            and current_date is not None
            and not _missing_number(current_hours)
            and current_hours > 0
        ):
            days_elapsed = (today - current_date).days
            if days_elapsed > 0:
                avg = current_hours / days_elapsed
                row["promedio_horas_dia"] = avg
                row["horas_para_proximo_service"] = settings.horas_para_proximo_service
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

    current_date = current.get("fecha_service")
    previous_date = previous.get("fecha_service")
    current_hours = current.get("horas")
    previous_hours = previous.get("horas")
    # El anterior debe tener tipo de service reconocido (horas) o ser una lectura inicial
    _BASELINE_TYPES = {"entrega", "consulta"}
    tipo_ant = row["tipo_service_anterior"].lower().strip()
    if not _is_hour_service(row["tipo_service_anterior"]) and tipo_ant not in _BASELINE_TYPES:
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
        if diff_days <= 0:
            row["error_calculo_motivo"] = f"Fechas iguales o invertidas ({int(diff_days)} dias entre services)"
        elif diff_hours < 0:
            row["error_calculo_motivo"] = f"Horas bajaron ({int(current_hours)} actual < {int(previous_hours)} anterior)"
        else:
            row["error_calculo_motivo"] = f"Horas sin cambio ({int(current_hours)} Hs en ambos services)"
        row["estado"] = "ERROR_CALCULO"
        return row

    avg = diff_hours / diff_days
    row["promedio_horas_dia"] = avg
    if avg <= 0:
        row["error_calculo_motivo"] = "Promedio de horas negativo o cero"
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
    """Retorna True si el tipo de service indica horas (ej: '250 Hs', '1000hs').
    Usa regex para evitar falsos positivos con palabras que contengan 'hs' (ej: 'chassis').
    """
    return bool(re.search(r"\d+\s*hs", clean_text(value), re.IGNORECASE))
