"""Mini base local para vencimientos y avisos."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import sqlite3
from typing import Any

import pandas as pd

from app.config import Settings
from app.utils import clean_text


_initialized_paths: set[str] = set()

SERVICE_COLUMNS = [
    "aviso_id",
    "contact_key",
    "cliente",
    "equipo",
    "serial",
    "lugar",
    "telefono_cliente",
    "fecha_service_actual",
    "soporte_actual",
    "horas_actuales",
    "tipo_service_actual",
    "fecha_estimada_proximo_service",
    "estado",
    "observaciones",
    "updated_at",
]


def sync_services(df: pd.DataFrame, settings: Settings) -> int:
    init_store(settings)
    overrides = _read_phone_overrides(settings)
    rows = []
    for _, row in df.iterrows():
        aviso_id = clean_text(row.get("id_interno_aviso"))
        next_date = _iso_date(row.get("fecha_estimada_proximo_service"))
        if not aviso_id or not next_date:
            continue
        contact_key = build_contact_key(row)
        phone = overrides.get(contact_key) or clean_text(row.get("telefono_cliente"))
        rows.append(
            {
                "aviso_id": aviso_id,
                "contact_key": contact_key,
                "cliente": clean_text(row.get("cliente")),
                "equipo": clean_text(row.get("equipo")),
                "serial": clean_text(row.get("serial")),
                "lugar": clean_text(row.get("lugar")),
                "telefono_cliente": phone,
                "fecha_service_actual": _iso_date(row.get("fecha_service_actual")),
                "soporte_actual": clean_text(row.get("soporte_actual")),
                "horas_actuales": _number_or_none(row.get("horas_actuales")),
                "tipo_service_actual": clean_text(row.get("tipo_service_actual")),
                "fecha_estimada_proximo_service": next_date,
                "estado": clean_text(row.get("estado")),
                "observaciones": clean_text(row.get("observaciones")),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
        )

    if not rows:
        return 0

    placeholders = ", ".join("?" for _ in SERVICE_COLUMNS)
    updates = ", ".join(f"{column}=excluded.{column}" for column in SERVICE_COLUMNS if column != "aviso_id")
    with sqlite3.connect(settings.services_db_path) as connection:
        connection.executemany(
            f"""
            INSERT INTO services ({", ".join(SERVICE_COLUMNS)})
            VALUES ({placeholders})
            ON CONFLICT(aviso_id) DO UPDATE SET {updates}
            """,
            [[row[column] for column in SERVICE_COLUMNS] for row in rows],
        )
    return len(rows)


def list_service_contacts(settings: Settings, search: str = "") -> pd.DataFrame:
    init_store(settings)
    term = f"%{clean_text(search)}%"
    with sqlite3.connect(settings.services_db_path) as connection:
        query = """
            SELECT
                aviso_id,
                cliente,
                equipo,
                serial,
                lugar,
                telefono_cliente,
                fecha_estimada_proximo_service,
                updated_at
            FROM services
            WHERE ? = '%%'
               OR cliente LIKE ?
               OR equipo LIKE ?
               OR serial LIKE ?
               OR telefono_cliente LIKE ?
            ORDER BY cliente, equipo, serial, fecha_estimada_proximo_service
        """
        return pd.read_sql_query(query, connection, params=[term, term, term, term, term])


def update_service_phone(settings: Settings, aviso_id: str, telefono_cliente: str) -> None:
    init_store(settings)
    phone = clean_text(telefono_cliente)
    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(settings.services_db_path) as connection:
        row = connection.execute(
            """
            SELECT aviso_id, contact_key, cliente, equipo, serial
            FROM services
            WHERE aviso_id = ?
            """,
            (clean_text(aviso_id),),
        ).fetchone()
        if row is None:
            raise ValueError("No se encontro el service seleccionado en la base local")

        contact_key = row[1] or build_contact_key({"cliente": row[2], "equipo": row[3], "serial": row[4]})
        connection.execute(
            """
            UPDATE services
            SET telefono_cliente = ?, contact_key = ?, updated_at = ?
            WHERE contact_key = ?
               OR aviso_id = ?
            """,
            (phone, contact_key, now, contact_key, clean_text(aviso_id)),
        )
        connection.execute(
            """
            INSERT INTO phone_overrides (contact_key, telefono_cliente, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(contact_key) DO UPDATE SET
                telefono_cliente = excluded.telefono_cliente,
                updated_at = excluded.updated_at
            """,
            (contact_key, phone, now),
        )


def get_sent_aviso_ids(settings: Settings) -> set[str]:
    """Retorna el conjunto de aviso_ids que ya fueron enviados o simulados (fuente: tabla avisos)."""
    init_store(settings)
    with sqlite3.connect(settings.services_db_path) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT aviso_id
            FROM avisos
            WHERE resultado IN ('ENVIADO', 'SIMULADO')
            """
        ).fetchall()
    return {row[0] for row in rows if row[0]}


def get_pending_alerts(settings: Settings, today: date | None = None) -> pd.DataFrame:
    init_store(settings)
    today = today or date.today()
    limit = today + timedelta(days=settings.dias_antes_aviso)
    with sqlite3.connect(settings.services_db_path) as connection:
        duplicate_filter = ""
        if not settings.reenviar_aviso:
            duplicate_filter = """
              AND NOT EXISTS (
                  SELECT 1
                  FROM avisos a
                  WHERE a.aviso_id = s.aviso_id
                    AND a.resultado IN ('ENVIADO', 'SIMULADO')
              )
            """
        query = """
            SELECT
                s.*,
                CAST(julianday(s.fecha_estimada_proximo_service) - julianday(?) AS INTEGER) AS dias_restantes
            FROM services s
            WHERE s.fecha_estimada_proximo_service >= ?
              AND s.fecha_estimada_proximo_service <= ?
              AND COALESCE(s.telefono_cliente, '') <> ''
              {duplicate_filter}
            ORDER BY s.fecha_estimada_proximo_service, s.cliente, s.serial
        """.format(duplicate_filter=duplicate_filter)
        result = pd.read_sql_query(query, connection, params=[today.isoformat(), today.isoformat(), limit.isoformat()])
    return result


def record_seguimiento(
    settings: Settings,
    aviso_id: str,
    cliente: str,
    serial: str,
    equipo: str,
    fecha_estimada: str,
    telefono: str,
) -> int:
    """Registra un envio manual para seguimiento. Retorna el id generado."""
    init_store(settings)
    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(settings.services_db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO seguimiento (aviso_id, cliente, serial, equipo, fecha_estimada, telefono, fecha_envio, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pendiente')
            """,
            (
                clean_text(aviso_id), clean_text(cliente), clean_text(serial),
                clean_text(equipo), clean_text(fecha_estimada), clean_text(telefono), now,
            ),
        )
        return cursor.lastrowid


def update_seguimiento_estado(settings: Settings, seguimiento_id: int, estado: str) -> None:
    """Actualiza el estado de un registro de seguimiento (coordinado / sin_respuesta)."""
    init_store(settings)
    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(settings.services_db_path) as connection:
        connection.execute(
            "UPDATE seguimiento SET estado = ?, fecha_respuesta = ? WHERE id = ?",
            (estado, now, seguimiento_id),
        )


def list_seguimiento(settings: Settings) -> pd.DataFrame:
    """Lista todos los registros de seguimiento, mas recientes primero."""
    init_store(settings)
    with sqlite3.connect(settings.services_db_path) as connection:
        return pd.read_sql_query(
            """
            SELECT id, aviso_id, cliente, serial, equipo, fecha_estimada,
                   telefono, fecha_envio, estado, fecha_respuesta
            FROM seguimiento
            ORDER BY fecha_envio DESC
            """,
            connection,
        )


def get_seguimiento_aviso_ids(settings: Settings) -> set[str]:
    """Retorna aviso_ids que ya tienen mensaje enviado manualmente (para filtrarlos de Proximos/Vencidos)."""
    init_store(settings)
    with sqlite3.connect(settings.services_db_path) as connection:
        rows = connection.execute(
            "SELECT DISTINCT aviso_id FROM seguimiento"
        ).fetchall()
    return {row[0] for row in rows if row[0]}


def record_notice(settings: Settings, row: pd.Series, resultado: str, error: str = "") -> None:
    init_store(settings)
    with sqlite3.connect(settings.services_db_path) as connection:
        connection.execute(
            """
            INSERT INTO avisos (
                aviso_id, fecha_aviso, canal, destino, resultado, error
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                clean_text(row.get("aviso_id") or row.get("id_interno_aviso")),
                datetime.now().isoformat(timespec="seconds"),
                "whatsapp",
                clean_text(row.get("telefono_cliente")),
                resultado,
                error,
            ),
        )


def init_store(settings: Settings) -> None:
    db_key = str(settings.services_db_path)
    if db_key in _initialized_paths:
        return
    settings.services_db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.services_db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS services (
                aviso_id TEXT PRIMARY KEY,
                contact_key TEXT,
                cliente TEXT,
                equipo TEXT,
                serial TEXT,
                lugar TEXT,
                telefono_cliente TEXT,
                fecha_service_actual TEXT,
                soporte_actual TEXT,
                horas_actuales REAL,
                tipo_service_actual TEXT,
                fecha_estimada_proximo_service TEXT,
                estado TEXT,
                observaciones TEXT,
                updated_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS avisos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aviso_id TEXT NOT NULL,
                fecha_aviso TEXT NOT NULL,
                canal TEXT NOT NULL,
                destino TEXT,
                resultado TEXT NOT NULL,
                error TEXT,
                FOREIGN KEY(aviso_id) REFERENCES services(aviso_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS phone_overrides (
                contact_key TEXT PRIMARY KEY,
                telefono_cliente TEXT,
                updated_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS seguimiento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aviso_id TEXT NOT NULL,
                cliente TEXT,
                serial TEXT,
                equipo TEXT,
                fecha_estimada TEXT,
                telefono TEXT,
                fecha_envio TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'pendiente',
                fecha_respuesta TEXT
            )
            """
        )
        _ensure_column(connection, "services", "contact_key", "TEXT")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_services_next_date ON services(fecha_estimada_proximo_service)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_services_contact_key ON services(contact_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_avisos_aviso_id ON avisos(aviso_id)")
    _initialized_paths.add(db_key)


def build_contact_key(row: Any) -> str:
    serial = clean_text(_get_value(row, "serial"))
    if serial:
        return f"serial:{serial.lower()}"
    cliente = clean_text(_get_value(row, "cliente")).lower()
    equipo = clean_text(_get_value(row, "equipo")).lower()
    return f"equipo:{cliente}|{equipo}"


def _read_phone_overrides(settings: Settings) -> dict[str, str]:
    with sqlite3.connect(settings.services_db_path) as connection:
        rows = connection.execute(
            """
            SELECT contact_key, telefono_cliente
            FROM phone_overrides
            WHERE COALESCE(contact_key, '') <> ''
            """
        ).fetchall()
    return {clean_text(key): clean_text(phone) for key, phone in rows}


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _get_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return row.get(key)


def _iso_date(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if hasattr(value, "date") and not isinstance(value, date):
        value = value.date()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.date().isoformat()


def _number_or_none(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
