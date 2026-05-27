from datetime import date, timedelta
import unittest

import pandas as pd

from app.config import load_settings
from app.procesador_services import process_services


class ProcesadorServicesTest(unittest.TestCase):
    def test_detecta_proximo_a_vencer(self):
        today = date(2026, 5, 27)
        settings = load_settings(force_test=True)
        df = pd.DataFrame(
            [
                {
                    "cliente": "Cliente",
                    "equipo": "Equipo",
                    "serial": "SER1",
                    "fecha_service": today - timedelta(days=20),
                    "numero_soporte": "S2",
                    "horas": 1000,
                    "tipo_service": "250 Hs",
                    "lugar": "ZONA",
                    "mail_cliente": "cliente@example.com",
                    "observaciones": "",
                },
                {
                    "cliente": "Cliente",
                    "equipo": "Equipo",
                    "serial": "SER1",
                    "fecha_service": today - timedelta(days=45),
                    "numero_soporte": "S1",
                    "horas": 750,
                    "tipo_service": "1000 Hs",
                    "lugar": "ZONA",
                    "mail_cliente": "cliente@example.com",
                    "observaciones": "",
                },
            ]
        )

        result = process_services(df, settings, today=today)

        self.assertEqual(result.iloc[0]["estado"], "PROXIMO_A_VENCER")
        self.assertTrue(bool(result.iloc[0]["enviar_aviso"]))


if __name__ == "__main__":
    unittest.main()
