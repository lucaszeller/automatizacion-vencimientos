"""Envio de avisos por WhatsApp y registro de avisos."""

from datetime import date, datetime
import json
from pathlib import Path
import random
import time
import urllib.error
import urllib.request

import pandas as pd

from app.config import Settings
from app.service_store import get_sent_aviso_ids, record_notice


def dynamic_delay(min_sec: int, max_sec: int, logger=None) -> float:
    """Genera una pausa dinamica e impredecible para simular comportamiento humano.

    Estrategia:
    - 70% del tiempo: pausa dentro del rango configurado
    - 20% del tiempo: pausa larga (hasta 2x el maximo) — simula distraccion
    - 10% del tiempo: pausa corta (mitad del minimo) — simula rapidez ocasional
    """
    r = random.random()
    if r < 0.10:
        delay = random.uniform(max(5, min_sec // 2), min_sec)
    elif r < 0.30:
        delay = random.uniform(max_sec, max_sec * 2)
    else:
        delay = random.uniform(min_sec, max_sec)

    # Micro-jitter de +/- 3 segundos para evitar patrones exactos
    delay += random.uniform(-3, 3)
    delay = max(3, delay)

    if logger:
        logger.debug("Pausa dinamica: %.1f segundos", delay)
    time.sleep(delay)
    return delay


SENT_COLUMNS = [
    "Fecha ejecucion",
    "Cliente",
    "Equipo",
    "Serial",
    "WhatsApp destino",
    "Fecha proximo service",
    "Estado",
    "Resultado",
    "Error",
    "ID interno del aviso",
]


def check_whatsapp_config(settings: Settings, logger) -> bool:
    """Valida que las credenciales de WhatsApp esten configuradas antes de intentar enviar.
    Retorna True si la configuracion es valida, False si falta algo.
    """
    if settings.whatsapp_provider == "local":
        try:
            req = urllib.request.Request(
                url=f"{settings.whatsapp_local_url}/status",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read().decode())
                if not body.get("ready"):
                    logger.warning(
                        "Servidor WhatsApp local en %s no esta listo (WhatsApp no conectado). "
                        "Escanee el QR en la ventana del servidor.",
                        settings.whatsapp_local_url,
                    )
                    return False
                logger.info("Servidor WhatsApp local conectado y listo.")
                return True
        except Exception as exc:
            logger.error(
                "No se pudo conectar al servidor WhatsApp local en %s: %s. "
                "Ejecute 'Iniciar WhatsApp Server.bat' antes de enviar avisos.",
                settings.whatsapp_local_url,
                exc,
            )
            return False

    # Provider: meta
    ok = True
    if not settings.whatsapp_token:
        logger.error("WHATSAPP_TOKEN no esta configurado en .env — no se podran enviar mensajes")
        ok = False
    if not settings.whatsapp_phone_number_id:
        logger.error("WHATSAPP_PHONE_NUMBER_ID no esta configurado en .env — no se podran enviar mensajes")
        ok = False
    return ok


def process_whatsapp_alerts(df: pd.DataFrame, settings: Settings, logger) -> tuple[pd.DataFrame, dict]:
    sent_ids = get_sent_aviso_ids(settings) if not settings.reenviar_aviso else set()

    updated = df.copy()
    records = []
    stats = {"avisos_a_enviar": 0, "enviados": 0, "simulados": 0, "duplicados": 0, "errores_envio": 0}
    if "enviar_aviso" not in updated.columns or updated.empty:
        _write_history(settings.enviados_dir / f"whatsapp_enviados_{date.today().year}.xlsx", pd.DataFrame(columns=SENT_COLUMNS), records)
        return updated, stats

    rows_to_send = updated[updated["enviar_aviso"] == True]
    for i, (index, row) in enumerate(rows_to_send.iterrows()):
        aviso_id = str(row["id_interno_aviso"])
        destination = normalize_phone(row.get("telefono_cliente"), settings.whatsapp_country_prefix, logger)
        if aviso_id in sent_ids:
            stats["duplicados"] += 1
            updated.at[index, "mail_enviado"] = True
            updated.at[index, "error_envio"] = "Aviso ya enviado anteriormente"
            continue

        stats["avisos_a_enviar"] += 1
        result = "SIMULADO" if settings.modo_prueba else "ENVIADO"
        error = ""
        try:
            if settings.modo_prueba:
                logger.info("WhatsApp simulado: %s - %s", destination, row["serial"])
                stats["simulados"] += 1
            else:
                # Pausa aleatoria antes de cada envio (excepto el primero) para evitar ban
                if i > 0:
                    dynamic_delay(settings.whatsapp_delay_min, settings.whatsapp_delay_max, logger)
                _send_client_whatsapp(row, destination, settings, logger)
                logger.info("WhatsApp enviado: %s - %s", destination, row["serial"])
                stats["enviados"] += 1
            updated.at[index, "mail_enviado"] = True
            updated.at[index, "fecha_envio_mail"] = datetime.now()
        except Exception as exc:
            result = "ERROR"
            error = str(exc)
            stats["errores_envio"] += 1
            updated.at[index, "error_envio"] = error
            logger.exception("ERROR WHATSAPP: %s - %s", destination, error)

        record_notice(settings, row, result, error)
        records.append(_history_record(row, destination, result, error, aviso_id))

    sent_path = settings.enviados_dir / f"whatsapp_enviados_{date.today().year}.xlsx"
    history = _read_history(sent_path)
    _write_history(sent_path, history, records)
    return updated, stats


def send_admin_summary(settings: Settings, summary: dict, logger) -> None:
    if not settings.enviar_resumen_admin or not settings.whatsapp_admin_number:
        return
    body = (
        "Resultado de ejecucion diaria\n\n"
        f"Registros leidos: {summary.get('registros_leidos', 0)}\n"
        f"Equipos procesados: {summary.get('equipos_procesados', 0)}\n"
        f"Avisos enviados/simulados: {summary.get('avisos_enviados', 0)}\n"
        f"Errores: {summary.get('errores', 0)}\n"
        f"Clientes sin contacto: {summary.get('clientes_sin_mail', 0)}\n"
        f"Archivo generado: {summary.get('archivo_generado', '')}\n"
    )
    if settings.modo_prueba:
        logger.info("Resumen admin simulado para %s", settings.whatsapp_admin_number)
        return
    _send_whatsapp_message(
        normalize_phone(settings.whatsapp_admin_number, settings.whatsapp_country_prefix, logger),
        body,
        settings,
    )
    logger.info("Resumen admin enviado a %s", settings.whatsapp_admin_number)


def build_service_message(row: pd.Series) -> str:
    model = row.get("equipo", "")
    serial = row.get("serial", "")
    hours = row.get("horas_actuales", "")
    due_date = row.get("fecha_estimada_proximo_service", "")
    return (
        "Hola.\n\n"
        "Le avisamos que el service del autoelevador esta proximo a vencer.\n\n"
        f"Modelo/equipo: {model}\n"
        f"Serial: {serial}\n"
        f"Horas actuales: {hours}\n"
        f"Fecha estimada de vencimiento: {due_date}\n\n"
        "Por favor coordinar disponibilidad para realizar el mantenimiento.\n"
        "Servicio Tecnico."
    )

def send_whatsapp_text(destination: str, body: str, settings: Settings, logger=None) -> None:
    _send_whatsapp_message(normalize_phone(destination, settings.whatsapp_country_prefix, logger), body, settings)


def normalize_phone(value, country_prefix: str = "54", logger=None) -> str:
    """Extrae digitos y agrega codigo de pais si falta."""
    raw = str(value or "").strip()
    digits = "".join(char for char in raw if char.isdigit())
    if not digits:
        return digits
    prefix = country_prefix.lstrip("+")
    if not digits.startswith(prefix):
        digits = prefix + digits
        if logger:
            logger.warning("Telefono sin codigo de pais, se agrego prefijo %s: %s -> %s", prefix, raw, digits)
    if len(digits) < 10:
        if logger:
            logger.warning("Telefono posiblemente invalido (muy corto): %s", digits)
    return digits


def _read_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=SENT_COLUMNS)
    return pd.read_excel(path)


def _write_history(path: Path, history: pd.DataFrame, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_rows = pd.DataFrame(records, columns=SENT_COLUMNS)
    result = pd.concat([history, new_rows], ignore_index=True)
    result.to_excel(path, index=False)


def _history_record(row: pd.Series, destination: str, result: str, error: str, aviso_id: str) -> dict:
    return {
        "Fecha ejecucion": datetime.now(),
        "Cliente": row["cliente"],
        "Equipo": row["equipo"],
        "Serial": row["serial"],
        "WhatsApp destino": destination,
        "Fecha proximo service": row["fecha_estimada_proximo_service"],
        "Estado": row["estado"],
        "Resultado": result,
        "Error": error,
        "ID interno del aviso": aviso_id,
    }


def _send_client_whatsapp(row: pd.Series, destination: str, settings: Settings, logger=None) -> None:
    body = build_service_message(row)
    _send_whatsapp_message(normalize_phone(destination, settings.whatsapp_country_prefix, logger), body, settings)


def _send_whatsapp_message(destination: str, body: str, settings: Settings) -> None:
    """Envia un mensaje de WhatsApp usando el proveedor configurado (meta o local)."""
    if not destination:
        raise RuntimeError("Telefono de destino vacio")

    if settings.whatsapp_provider == "local":
        _send_whatsapp_local(destination, body, settings.whatsapp_local_url)
    else:
        _send_whatsapp_meta(destination, body, settings)


def _send_whatsapp_local(destination: str, body: str, local_url: str) -> None:
    """Envia un mensaje via el servidor local whatsapp-web.js."""
    payload = {"to": destination, "message": body}
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=f"{local_url}/send",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise RuntimeError(f"Servidor local: respuesta inesperada {status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Servidor local error ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"No se pudo conectar al servidor WhatsApp local ({local_url}). "
            f"Verifique que 'Iniciar WhatsApp Server.bat' este corriendo. Detalle: {exc.reason}"
        ) from exc


def _send_whatsapp_meta(destination: str, body: str, settings: Settings) -> None:
    """Envia un mensaje via la Cloud API de Meta."""
    if not settings.whatsapp_token:
        raise RuntimeError("Falta WHATSAPP_TOKEN en .env")
    if not settings.whatsapp_phone_number_id:
        raise RuntimeError("Falta WHATSAPP_PHONE_NUMBER_ID en .env")

    url = f"{settings.whatsapp_api_url}/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": destination,
        "type": "text",
        "text": {"body": body, "preview_url": False},
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise RuntimeError(f"Respuesta WhatsApp inesperada: {status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Error WhatsApp API ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo conectar a WhatsApp API: {exc.reason}") from exc
