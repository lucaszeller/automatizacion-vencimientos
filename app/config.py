"""Configuracion de la aplicacion."""

from dataclasses import dataclass
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs):
        return False


BASE_DIR = Path(__file__).resolve().parent.parent


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "y"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    modo_prueba: bool
    data_source: str
    excel_input_path: Path
    db_engine: str
    db_host: str
    db_port: str
    db_name: str
    db_user: str
    db_password: str
    db_driver: str
    db_query_path: Path
    dias_antes_aviso: int
    horas_para_proximo_service: float
    reenviar_aviso: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from_name: str
    smtp_use_tls: bool
    mail_admin: str
    enviar_resumen_admin: bool
    output_dir: Path
    log_dir: Path
    enviados_dir: Path
    errores_dir: Path
    respaldos_dir: Path


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def load_settings(force_test: bool = False) -> Settings:
    load_dotenv(BASE_DIR / ".env")
    modo_prueba = _bool_env("MODO_PRUEBA", True)
    data_source = os.getenv("DATA_SOURCE", "database").strip().lower()
    if force_test:
        modo_prueba = True
        data_source = "sample"

    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        modo_prueba=modo_prueba,
        data_source=data_source,
        excel_input_path=resolve_path(os.getenv("EXCEL_INPUT_PATH", "data/entrada/servicios_prueba.xlsx")),
        db_engine=os.getenv("DB_ENGINE", "sqlserver"),
        db_host=os.getenv("DB_HOST", ""),
        db_port=os.getenv("DB_PORT", "1433"),
        db_name=os.getenv("DB_NAME", ""),
        db_user=os.getenv("DB_USER", ""),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_driver=os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server"),
        db_query_path=resolve_path(os.getenv("DB_QUERY_PATH", "sql/tacticasoft_services.sql")),
        dias_antes_aviso=int(os.getenv("DIAS_ANTES_AVISO", "7")),
        horas_para_proximo_service=float(os.getenv("HORAS_PARA_PROXIMO_SERVICE", "250")),
        reenviar_aviso=_bool_env("REENVIAR_AVISO", False),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from_name=os.getenv("SMTP_FROM_NAME", "Servicio Tecnico"),
        smtp_use_tls=_bool_env("SMTP_USE_TLS", True),
        mail_admin=os.getenv("MAIL_ADMIN", ""),
        enviar_resumen_admin=_bool_env("ENVIAR_RESUMEN_ADMIN", True),
        output_dir=resolve_path(os.getenv("OUTPUT_DIR", "data/reportes")),
        log_dir=resolve_path(os.getenv("LOG_DIR", "data/logs")),
        enviados_dir=resolve_path(os.getenv("ENVIADOS_DIR", "data/enviados")),
        errores_dir=resolve_path(os.getenv("ERRORES_DIR", "data/errores")),
        respaldos_dir=resolve_path(os.getenv("RESPALDOS_DIR", "data/respaldos")),
    )


def ensure_directories(settings: Settings) -> None:
    for path in (
        settings.excel_input_path.parent,
        settings.output_dir,
        settings.log_dir,
        settings.enviados_dir,
        settings.errores_dir,
        settings.respaldos_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
