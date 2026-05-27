"""Punto de entrada de la aplicacion."""

import argparse
from datetime import date, timedelta
import calendar
import sys

from app.config import ensure_directories, load_settings
from app.generador_excel import generate_report
from app.lector_datos import load_source_data
from app.logger import setup_logger
from app.mailer_gmail import process_email_alerts, send_admin_summary
from app.procesador_services import process_services, process_services_for_period


def run(force_test: bool = False, only_excel: bool = False, only_mails: bool = False, period: str | None = None) -> int:
    settings = load_settings(force_test=force_test)
    ensure_directories(settings)
    logger = setup_logger(settings.log_dir)
    period_start, period_end = parse_period(period) if period else (None, None)

    logger.info("Inicio del proceso")
    logger.info("Fuente de datos: %s", settings.data_source)
    logger.info("Modo prueba: %s", settings.modo_prueba)
    if period_start and period_end:
        logger.info("Periodo del reporte: %s", period)

    raw = load_source_data(settings)
    logger.info("Registros leidos: %s", len(raw))

    if period_start and period_end:
        reference_date = period_end - timedelta(days=1)
        logger.info("Fecha de referencia para estado: %s", reference_date.isoformat())
        processed = process_services_for_period(raw, settings, period_start, period_end, today=reference_date)
    else:
        processed = process_services(raw, settings)
    logger.info("Equipos procesados: %s", len(processed))
    logger.info("Clientes sin mail: %s", int((processed["estado"] == "SIN_MAIL").sum()))
    logger.info("Errores de calculo: %s", int((processed["estado"] == "ERROR_CALCULO").sum()))

    if not only_excel:
        processed, mail_stats = process_email_alerts(processed, settings, logger)
    else:
        mail_stats = {"avisos_a_enviar": int(processed["enviar_aviso"].sum()), "enviados": 0, "simulados": 0, "errores_smtp": 0}

    report_date = period_start or date.today()
    report_path = generate_report(processed, settings.output_dir, run_date=report_date, period_label=period)
    logger.info("Archivo generado: %s", report_path)
    logger.info("Avisos a enviar: %s", mail_stats.get("avisos_a_enviar", 0))
    logger.info("Mails enviados correctamente: %s", mail_stats.get("enviados", 0))
    logger.info("Mails simulados: %s", mail_stats.get("simulados", 0))
    logger.info("Errores SMTP: %s", mail_stats.get("errores_smtp", 0))

    summary = {
        "registros_leidos": len(raw),
        "equipos_procesados": len(processed),
        "avisos_enviados": mail_stats.get("enviados", 0) + mail_stats.get("simulados", 0),
        "errores": mail_stats.get("errores_smtp", 0) + int((processed["estado"] == "ERROR_CALCULO").sum()),
        "clientes_sin_mail": int((processed["estado"] == "SIN_MAIL").sum()),
        "archivo_generado": report_path.name,
    }
    if not only_mails:
        send_admin_summary(settings, summary, logger)

    logger.info("Fin del proceso")
    print(f"Proceso finalizado. Reporte: {report_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alertas mensuales de services")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--run", action="store_true", help="Ejecuta el proceso completo con la configuracion actual")
    group.add_argument("--test", action="store_true", help="Ejecuta una prueba con datos simulados y sin mails reales")
    group.add_argument("--generate-excel", action="store_true", help="Genera Excel sin enviar mails")
    group.add_argument("--send-mails", action="store_true", help="Procesa avisos y mails segun configuracion")
    group.add_argument("--ui", action="store_true", help="Abre la interfaz grafica simple")
    parser.add_argument("--period", help="Periodo mensual a generar en formato YYYY-MM, por ejemplo 2026-01")
    return parser.parse_args()


def parse_period(value: str) -> tuple[date, date]:
    try:
        year_text, month_text = value.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)
    except Exception as exc:
        raise ValueError("El periodo debe tener formato YYYY-MM, por ejemplo 2026-01") from exc
    return start, end


def main() -> int:
    if len(sys.argv) == 1:
        from app.ui import launch_ui

        launch_ui()
        return 0

    args = parse_args()
    try:
        if args.ui:
            from app.ui import launch_ui

            launch_ui()
            return 0
        if args.test:
            return run(force_test=True, period=args.period)
        if args.generate_excel:
            return run(only_excel=True, period=args.period)
        if args.send_mails:
            return run(only_mails=True, period=args.period)
        return run(period=args.period)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
