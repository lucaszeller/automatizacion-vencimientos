"""Configuracion de la aplicacion."""

from dataclasses import dataclass
from pathlib import Path
import os
import sys

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs):
        return False


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent.parent
    RESOURCE_DIR = APP_DIR

BASE_DIR = APP_DIR


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "y"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    modo_prueba: bool
    modo_prueba_explicito: bool  # True si MODO_PRUEBA estaba definido en .env
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
    dias_conservar_reportes_diarios: int
    whatsapp_provider: str      # "meta" o "local"
    whatsapp_local_url: str     # URL del servidor local (solo cuando provider=local)
    whatsapp_api_url: str
    whatsapp_token: str
    whatsapp_phone_number_id: str
    whatsapp_admin_number: str
    whatsapp_test_number: str   # Numero propio para pruebas reales
    enviar_resumen_admin: bool
    whatsapp_country_prefix: str
    whatsapp_delay_min: int
    whatsapp_delay_max: int
    output_dir: Path
    services_db_path: Path
    log_dir: Path
    enviados_dir: Path
    errores_dir: Path
    respaldos_dir: Path


def resolve_path(value: str, resource: bool = False) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    app_path = APP_DIR / path
    if resource:
        if app_path.exists():
            return app_path
        return RESOURCE_DIR / path
    return app_path


def load_settings(force_test: bool = False) -> Settings:
    load_dotenv(APP_DIR / ".env", override=True)
    modo_prueba_raw = os.getenv("MODO_PRUEBA")
    modo_prueba_explicito = modo_prueba_raw is not None
    modo_prueba = _bool_env("MODO_PRUEBA", False)
    data_source = os.getenv("DATA_SOURCE", "database").strip().lower()
    if force_test:
        modo_prueba = True
        modo_prueba_explicito = True
        data_source = "sample"

    delay_min = int(os.getenv("WHATSAPP_DELAY_MIN", "5"))
    delay_max = int(os.getenv("WHATSAPP_DELAY_MAX", "15"))
    if delay_min > delay_max:
        delay_min, delay_max = delay_max, delay_min

    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        modo_prueba=modo_prueba,
        modo_prueba_explicito=modo_prueba_explicito,
        data_source=data_source,
        excel_input_path=resolve_path(os.getenv("EXCEL_INPUT_PATH", "data/entrada/servicios_prueba.xlsx")),
        db_engine=os.getenv("DB_ENGINE", "mysql"),
        db_host=os.getenv("DB_HOST", ""),
        db_port=os.getenv("DB_PORT", "3307"),
        db_name=os.getenv("DB_NAME", ""),
        db_user=os.getenv("DB_USER", ""),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_driver=os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server"),
        db_query_path=resolve_path(os.getenv("DB_QUERY_PATH", "sql/tacticasoft_services.sql"), resource=True),
        dias_antes_aviso=int(os.getenv("DIAS_ANTES_AVISO", "7")),
        horas_para_proximo_service=float(os.getenv("HORAS_PARA_PROXIMO_SERVICE", "250")),
        reenviar_aviso=_bool_env("REENVIAR_AVISO", False),
        dias_conservar_reportes_diarios=int(os.getenv("DIAS_CONSERVAR_REPORTES_DIARIOS", "30")),
        whatsapp_provider=os.getenv("WHATSAPP_PROVIDER", "meta").strip().lower(),
        whatsapp_local_url=os.getenv("WHATSAPP_LOCAL_URL", "http://127.0.0.1:3000"),
        whatsapp_api_url=os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v20.0"),
        whatsapp_token=os.getenv("WHATSAPP_TOKEN", ""),
        whatsapp_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
        whatsapp_admin_number=os.getenv("WHATSAPP_ADMIN_NUMBER", ""),
        whatsapp_test_number=os.getenv("WHATSAPP_TEST_NUMBER", ""),
        enviar_resumen_admin=_bool_env("ENVIAR_RESUMEN_ADMIN", True),
        whatsapp_country_prefix=os.getenv("WHATSAPP_COUNTRY_PREFIX", "54"),
        whatsapp_delay_min=delay_min,
        whatsapp_delay_max=delay_max,
        output_dir=resolve_path(os.getenv("OUTPUT_DIR", "data/reportes")),
        services_db_path=resolve_path(os.getenv("SERVICES_DB_PATH", "data/services.db")),
        log_dir=resolve_path(os.getenv("LOG_DIR", "data/logs")),
        enviados_dir=resolve_path(os.getenv("ENVIADOS_DIR", "data/enviados")),
        errores_dir=resolve_path(os.getenv("ERRORES_DIR", "data/errores")),
        respaldos_dir=resolve_path(os.getenv("RESPALDOS_DIR", "data/respaldos")),
    )


def ensure_directories(settings: Settings) -> None:
    for path in (
        settings.excel_input_path.parent,
        settings.output_dir,
        settings.services_db_path.parent,
        settings.log_dir,
        settings.enviados_dir,
        settings.errores_dir,
        settings.respaldos_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
