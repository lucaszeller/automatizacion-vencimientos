from dataclasses import replace
from datetime import date
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from app.config import load_settings
from app.daily_alerts import find_upcoming_services, cleanup_old_daily_reports
from app.service_store import sync_services


class DailyAlertsTest(unittest.TestCase):
    def test_filtra_proximos_e_ignora_vencidos(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            settings = replace(
                load_settings(force_test=True),
                services_db_path=Path(temp_dir) / "services.db",
                dias_antes_aviso=7,
            )
            df = pd.DataFrame(
                [
                    {
                        "id_interno_aviso": "vencido",
                        "cliente": "Vencido",
                        "equipo": "Equipo",
                        "serial": "SER-1",
                        "lugar": "ZONA",
                        "telefono_cliente": "5491111111111",
                        "fecha_service_actual": date(2026, 5, 1),
                        "soporte_actual": "S1",
                        "horas_actuales": 100,
                        "tipo_service_actual": "250 Hs",
                        "fecha_estimada_proximo_service": date(2026, 6, 1),
                        "estado": "VENCIDO",
                    },
                    {
                        "id_interno_aviso": "proximo",
                        "cliente": "Proximo",
                        "equipo": "Equipo",
                        "serial": "SER-2",
                        "lugar": "ZONA",
                        "telefono_cliente": "5491111111111",
                        "fecha_service_actual": date(2026, 5, 20),
                        "soporte_actual": "S2",
                        "horas_actuales": 200,
                        "tipo_service_actual": "250 Hs",
                        "fecha_estimada_proximo_service": date(2026, 6, 5),
                        "estado": "PROXIMO_A_VENCER",
                    },
                    {
                        "id_interno_aviso": "lejano",
                        "cliente": "Lejano",
                        "equipo": "Equipo",
                        "serial": "SER-3",
                        "lugar": "ZONA",
                        "telefono_cliente": "5491111111111",
                        "fecha_service_actual": date(2026, 5, 25),
                        "soporte_actual": "S3",
                        "horas_actuales": 300,
                        "tipo_service_actual": "250 Hs",
                        "fecha_estimada_proximo_service": date(2026, 7, 1),
                        "estado": "OK",
                    },
                ]
            )
            sync_services(df, settings)

            result = find_upcoming_services(settings, today=date(2026, 6, 3))

        self.assertEqual(list(result["cliente"]), ["Proximo"])
        self.assertEqual(int(result.iloc[0]["dias_restantes"]), 2)


class CleanupOldReportsTest(unittest.TestCase):
    def test_elimina_archivos_viejos_y_conserva_recientes(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            output_dir = Path(temp_dir)
            settings = replace(
                load_settings(force_test=True),
                services_db_path=Path(temp_dir) / "services.db",
                output_dir=output_dir,
                dias_conservar_reportes_diarios=7,
            )
            today = date(2026, 6, 8)
            old_file = output_dir / "services_proximos_2026-04-29.xlsx"
            old_file.touch()
            recent_file = output_dir / "services_proximos_2026-06-05.xlsx"
            recent_file.touch()

            removed = cleanup_old_daily_reports(settings, today)

            self.assertEqual(removed, 1)
            self.assertFalse(old_file.exists())
            self.assertTrue(recent_file.exists())


if __name__ == "__main__":
    unittest.main()
