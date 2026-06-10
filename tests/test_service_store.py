from dataclasses import replace
from datetime import date
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from app.config import load_settings
from app.service_store import list_service_contacts, sync_services, update_service_phone, get_sent_aviso_ids, record_notice


class ServiceStoreTest(unittest.TestCase):
    def test_phone_override_survives_next_sync(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            settings = replace(load_settings(force_test=True), services_db_path=Path(temp_dir) / "services.db")
            df = pd.DataFrame(
                [
                    {
                        "id_interno_aviso": "aviso-1",
                        "cliente": "Cliente",
                        "equipo": "Toyota 8FG25",
                        "serial": "SER-1",
                        "lugar": "ZONA",
                        "telefono_cliente": "111",
                        "fecha_service_actual": date(2026, 5, 1),
                        "soporte_actual": "S1",
                        "horas_actuales": 100,
                        "tipo_service_actual": "250 Hs",
                        "fecha_estimada_proximo_service": date(2026, 6, 10),
                        "estado": "PROXIMO_A_VENCER",
                    }
                ]
            )
            sync_services(df, settings)
            update_service_phone(settings, "aviso-1", "5493406000000")
            df.loc[0, "telefono_cliente"] = "222"
            sync_services(df, settings)

            contacts = list_service_contacts(settings)

        self.assertEqual(contacts.iloc[0]["telefono_cliente"], "5493406000000")


class GetSentAvisoIdsTest(unittest.TestCase):
    def _make_settings(self, temp_dir):
        return replace(load_settings(force_test=True), services_db_path=Path(temp_dir) / "services.db")

    def _seed_service(self, settings, aviso_id, serial):
        df = pd.DataFrame([{
            "id_interno_aviso": aviso_id,
            "cliente": "C", "equipo": "E", "serial": serial, "lugar": "Z",
            "telefono_cliente": "111",
            "fecha_service_actual": date(2026, 5, 1),
            "soporte_actual": "S1", "horas_actuales": 100,
            "tipo_service_actual": "250 Hs",
            "fecha_estimada_proximo_service": date(2026, 7, 1),
            "estado": "OK",
        }])
        sync_services(df, settings)

    def test_retorna_ids_enviados_y_simulados(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            settings = self._make_settings(temp_dir)
            self._seed_service(settings, "aviso-enviado", "S1")
            row = pd.Series({"aviso_id": "aviso-enviado", "telefono_cliente": "111"})
            record_notice(settings, row, "ENVIADO")

            ids = get_sent_aviso_ids(settings)

        self.assertIn("aviso-enviado", ids)

    def test_no_incluye_errores(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            settings = self._make_settings(temp_dir)
            self._seed_service(settings, "aviso-error", "S2")
            row = pd.Series({"aviso_id": "aviso-error", "telefono_cliente": "222"})
            record_notice(settings, row, "ERROR", "timeout")

            ids = get_sent_aviso_ids(settings)

        self.assertNotIn("aviso-error", ids)


if __name__ == "__main__":
    unittest.main()
