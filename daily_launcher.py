"""Launcher silencioso para revision diaria de services proximos."""

from app.config import ensure_directories, load_settings
from app.daily_alerts import run_daily_alert_check
from app.logger import setup_logger


if __name__ == "__main__":
    settings = load_settings()
    ensure_directories(settings)
    logger = setup_logger(settings.log_dir)
    run_daily_alert_check(settings, logger)
    raise SystemExit(0)
