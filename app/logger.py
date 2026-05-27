"""Logger diario de proceso."""

from datetime import date
import logging
from pathlib import Path


def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("alertas_services")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    log_path = log_dir / f"log_{date.today().isoformat()}.txt"
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger
