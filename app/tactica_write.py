"""Operaciones de escritura puntual hacia TacticaSoft (MySQL).

Solo expone funciones de proposito especifico para evitar escrituras accidentales.
"""
from __future__ import annotations

from app.config import Settings


def _make_engine(settings: Settings):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL

    url = URL.create(
        "mysql+pymysql",
        username=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=int(settings.db_port),
        database=settings.db_name,
        query={"charset": "utf8"},
    )
    return create_engine(url)


def upsert_service_contact_phone(settings: Settings, id_empresa: int, phone: str) -> str:
    """Busca o crea un contacto con Cargo='Servicio Tecnico' en la empresa dada
    y actualiza o inserta su celular (Tipo=0).

    Retorna una descripcion de la accion realizada.
    Lanza una excepcion si falla la conexion o la escritura.
    """
    from sqlalchemy import text

    engine = _make_engine(settings)

    with engine.begin() as conn:
        # 1. Buscar contacto existente con cargo 'Servicio Tecnico'
        contact_row = conn.execute(
            text(
                "SELECT IDContacto FROM contactos "
                "WHERE IDEmpresa = :id_empresa "
                "  AND LOWER(COALESCE(Cargo, '')) LIKE '%servicio tecnico%' "
                "LIMIT 1"
            ),
            {"id_empresa": id_empresa},
        ).fetchone()

        if contact_row is None:
            # 2. Crear nuevo contacto minimo
            result = conn.execute(
                text(
                    "INSERT INTO contactos (IDEmpresa, Nombre, Cargo) "
                    "VALUES (:id_empresa, 'Servicio Tecnico', 'Servicio Tecnico')"
                ),
                {"id_empresa": id_empresa},
            )
            id_contacto = result.lastrowid
            contact_action = "contacto nuevo creado"
        else:
            id_contacto = contact_row[0]
            contact_action = "contacto existente"

        # 3. Buscar celular (Tipo=0) existente para ese contacto
        tel_row = conn.execute(
            text(
                "SELECT IDRef2 FROM telefonos "
                "WHERE IDRef2 = :id_contacto AND Tipo = 0 "
                "LIMIT 1"
            ),
            {"id_contacto": id_contacto},
        ).fetchone()

        if tel_row is None:
            # 4a. Insertar nuevo celular
            conn.execute(
                text(
                    "INSERT INTO telefonos (IDRef2, Tipo, Numero, Defecto) "
                    "VALUES (:id_contacto, 0, :phone, 1)"
                ),
                {"id_contacto": id_contacto, "phone": phone},
            )
            return f"Teléfono guardado en TacticaSoft ({contact_action}, celular insertado)"
        else:
            # 4b. Actualizar celular existente
            conn.execute(
                text(
                    "UPDATE telefonos SET Numero = :phone "
                    "WHERE IDRef2 = :id_contacto AND Tipo = 0"
                ),
                {"phone": phone, "id_contacto": id_contacto},
            )
            return f"Teléfono guardado en TacticaSoft ({contact_action}, celular actualizado)"
