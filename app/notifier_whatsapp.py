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
        if not destination or not (12 <= len(destination) <= 13):
            stats["errores_envio"] += 1
            updated.at[index, "error_envio"] = f"Telefono invalido: {destination}"
            logger.warning("Telefono invalido para %s (%s), se omite el envio.", row.get("cliente"), destination)
            continue
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
                _send_with_retry(row, destination, settings, logger)
                logger.info("WhatsApp enviado: %s - %s", destination, row["serial"])
                stats["enviados"] += 1
            updated.at[index, "mail_enviado"] = True
            updated.at[index, "fecha_envio_mail"] = datetime.now()
        except Exception as exc:
            result = "ERROR"
            error = str(exc)
            stats["errores_envio"] += 1
            updated.at[index, "error_envio"] = error
            logger.error("ERROR WHATSAPP (sin mas reintentos): %s - %s", destination, error)

        record_notice(settings, row, result, error)
        records.append(_history_record(row, destination, result, error, aviso_id))

    sent_path = settings.enviados_dir / f"whatsapp_enviados_{date.today().year}.xlsx"
    history = _read_history(sent_path)
    _write_history(sent_path, history, records)
    return updated, stats


def send_admin_summary(settings: Settings, summary: dict, logger) -> None:
    if not settings.enviar_resumen_admin or not settings.whatsapp_admin_number:
        return

    a_vencer = summary.get("a_vencer", 0)
    enviados = summary.get("avisos_enviados", 0)
    sin_contacto = summary.get("sin_contacto_nombres", [])
    error_calculo = summary.get("error_calculo_nombres", [])

    lines = [
        "Resumen de services del dia:",
        "",
        f"Services a vencer: {a_vencer}",
        "",
        f"Mensajes enviados: {enviados}",
    ]
    if sin_contacto:
        lines.append("")
        lines.append(f"Sin contacto o mal cargado ({len(sin_contacto)}):")
        for nombre in sin_contacto:
            lines.append(f"  - {nombre}")
    if error_calculo:
        lines.append("")
        lines.append(f"Error de calculo - revisar en TacticaSoft ({len(error_calculo)}):")
        for nombre in error_calculo:
            lines.append(f"  - {nombre}")

    body = "\n".join(lines)

    if settings.modo_prueba:
        logger.info("Resumen admin simulado para %s:\n%s", settings.whatsapp_admin_number, body)
        return
    _send_whatsapp_message(
        normalize_phone(settings.whatsapp_admin_number, settings.whatsapp_country_prefix, logger),
        body,
        settings,
    )
    logger.info("Resumen admin enviado a %s", settings.whatsapp_admin_number)


def _parse_model_serial(equipo: str) -> tuple[str, str]:
    """Separa 'HELI CPCD25-Q22K2 (3725)' en modelo='HELI CPCD25-Q22K2' y serie='3725'."""
    import re
    m = re.match(r"^(.*?)\s*\((\d+)\)\s*$", str(equipo).strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return str(equipo).strip(), ""


def build_service_message(row: pd.Series, operario_whatsapp: str = "") -> str:
    equipo = row.get("equipo", "")
    modelo, nro_serie = _parse_model_serial(equipo)
    due_date = row.get("fecha_estimada_proximo_service", "")
    if hasattr(due_date, "strftime"):
        due_date_str = due_date.strftime("%d/%m/%Y")
    else:
        due_date_str = str(due_date)

    lines = [
        "Hola! Nos comunicamos de Porta Autoelevadores para informarle que el proximo service del autoelevador se acerca a su fecha estimada de vencimiento.",
        "",
    ]
    if modelo:
        lines.append(f"Modelo: {modelo}")
    if nro_serie:
        lines.append(f"N de serie: {nro_serie}")
    lines.append(f"Proximo service: {due_date_str}")
    lines.append("")
    lines.append("Para coordinar un turno comuniquese al numero: 3564221129 - Luis")
    lines.append("")
    lines.append("Saludos")
    lines.append("Servicio Tecnico Porta")
    return "\n".join(lines)

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
    if len(digits) < 12 or len(digits) > 13:
        if logger:
            logger.warning("Telefono invalido (se esperan 12-13 digitos, tiene %d): %s", len(digits), digits)
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


def _send_with_retry(row: pd.Series, destination: str, settings: Settings, logger=None) -> None:
    """Envia un mensaje con reintentos automaticos en caso de fallo.

    Intenta hasta (max_retries + 1) veces en total.
    Entre reintentos espera 15 segundos (fijo, independiente del delay anti-ban entre clientes).
    Si todos los intentos fallan, relanza la ultima excepcion.
    """
    _RETRY_WAIT = 15  # segundos entre reintentos
    max_retries = getattr(settings, "whatsapp_max_retries", 2)
    last_exc = None
    for attempt in range(1, max_retries + 2):  # intento 1, 2, ..., max_retries+1
        try:
            _send_client_whatsapp(row, destination, settings, logger)
            if attempt > 1 and logger:
                logger.info("Reintento %d exitoso para %s", attempt - 1, destination)
            return
        except Exception as exc:
            last_exc = exc
            if attempt <= max_retries:
                if logger:
                    logger.warning(
                        "Error en intento %d/%d para %s: %s — reintentando en %ds...",
                        attempt, max_retries + 1, destination, exc, _RETRY_WAIT,
                    )
                time.sleep(_RETRY_WAIT)
            else:
                if logger:
                    logger.warning(
                        "Error en intento %d/%d para %s: %s — sin mas reintentos.",
                        attempt, max_retries + 1, destination, exc,
                    )
    raise last_exc


def _send_client_whatsapp(row: pd.Series, destination: str, settings: Settings, logger=None) -> None:
    body = build_service_message(row, operario_whatsapp=settings.operario_whatsapp)
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
