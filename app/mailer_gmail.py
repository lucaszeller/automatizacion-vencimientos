"""Envio de mails y registro de avisos."""

from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path
import smtplib

import pandas as pd

from app.config import Settings


SENT_COLUMNS = [
    "Fecha ejecucion",
    "Cliente",
    "Equipo",
    "Serial",
    "Mail destino",
    "Fecha proximo service",
    "Estado",
    "Resultado",
    "Error",
    "ID interno del aviso",
]


def process_email_alerts(df: pd.DataFrame, settings: Settings, logger) -> tuple[pd.DataFrame, dict]:
    sent_path = settings.enviados_dir / f"mails_enviados_{date.today().year}.xlsx"
    history = _read_history(sent_path)
    sent_ids = set(history["ID interno del aviso"].dropna().astype(str)) if not history.empty else set()

    updated = df.copy()
    records = []
    stats = {"avisos_a_enviar": 0, "enviados": 0, "simulados": 0, "duplicados": 0, "errores_smtp": 0}

    for index, row in updated[updated["enviar_aviso"] == True].iterrows():
        aviso_id = str(row["id_interno_aviso"])
        if aviso_id in sent_ids and not settings.reenviar_aviso:
            stats["duplicados"] += 1
            updated.at[index, "mail_enviado"] = True
            updated.at[index, "error_envio"] = "Aviso ya enviado anteriormente"
            continue

        stats["avisos_a_enviar"] += 1
        result = "SIMULADO" if settings.modo_prueba else "ENVIADO"
        error = ""
        try:
            if settings.modo_prueba:
                logger.info("Mail simulado: %s - %s", row["mail_cliente"], row["serial"])
                stats["simulados"] += 1
            else:
                _send_client_email(row, settings)
                logger.info("Mail enviado: %s - %s", row["mail_cliente"], row["serial"])
                stats["enviados"] += 1
            updated.at[index, "mail_enviado"] = True
            updated.at[index, "fecha_envio_mail"] = datetime.now()
        except Exception as exc:
            result = "ERROR"
            error = str(exc)
            stats["errores_smtp"] += 1
            updated.at[index, "error_envio"] = error
            logger.exception("ERROR SMTP: %s - %s", row["mail_cliente"], error)

        records.append(_history_record(row, result, error, aviso_id))

    _write_history(sent_path, history, records)
    return updated, stats


def send_admin_summary(settings: Settings, summary: dict, logger) -> None:
    if not settings.enviar_resumen_admin or not settings.mail_admin:
        return
    subject = "Resultado de ejecucion diaria"
    body = (
        "Resultado de ejecucion diaria\n\n"
        f"Registros leidos: {summary.get('registros_leidos', 0)}\n"
        f"Equipos procesados: {summary.get('equipos_procesados', 0)}\n"
        f"Avisos enviados/simulados: {summary.get('avisos_enviados', 0)}\n"
        f"Errores: {summary.get('errores', 0)}\n"
        f"Clientes sin mail: {summary.get('clientes_sin_mail', 0)}\n"
        f"Archivo generado: {summary.get('archivo_generado', '')}\n"
    )
    if settings.modo_prueba:
        logger.info("Resumen admin simulado para %s", settings.mail_admin)
        return
    _send_email(settings, settings.mail_admin, subject, body)
    logger.info("Resumen admin enviado a %s", settings.mail_admin)


def _read_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=SENT_COLUMNS)
    return pd.read_excel(path)


def _write_history(path: Path, history: pd.DataFrame, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_rows = pd.DataFrame(records, columns=SENT_COLUMNS)
    result = pd.concat([history, new_rows], ignore_index=True)
    result.to_excel(path, index=False)


def _history_record(row: pd.Series, result: str, error: str, aviso_id: str) -> dict:
    return {
        "Fecha ejecucion": datetime.now(),
        "Cliente": row["cliente"],
        "Equipo": row["equipo"],
        "Serial": row["serial"],
        "Mail destino": row["mail_cliente"],
        "Fecha proximo service": row["fecha_estimada_proximo_service"],
        "Estado": row["estado"],
        "Resultado": result,
        "Error": error,
        "ID interno del aviso": aviso_id,
    }


def _send_client_email(row: pd.Series, settings: Settings) -> None:
    subject = "Recordatorio de proximo service a vencer"
    body = (
        "Hola,\n\n"
        f"Le recordamos que el equipo {row['equipo']} / {row['serial']} correspondiente al cliente {row['cliente']}\n"
        f"tiene un proximo service estimado para el dia {row['fecha_estimada_proximo_service']}.\n\n"
        "Datos del ultimo service:\n"
        f"- Fecha: {row['fecha_service_actual']}\n"
        f"- Soporte: {row['soporte_actual']}\n"
        f"- Horas actuales: {row['horas_actuales']}\n"
        f"- Tipo de service: {row['tipo_service_actual']}\n\n"
        "Por favor, coordinar disponibilidad para realizar el mantenimiento correspondiente.\n\n"
        "Saludos.\n"
        "Servicio Tecnico\n"
    )
    _send_email(settings, row["mail_cliente"], subject, body)


def _send_email(settings: Settings, recipient: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_user}>"
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
