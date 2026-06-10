from datetime import date, timedelta
import unittest

import pandas as pd

from app.config import load_settings
from app.procesador_services import process_services, _is_hour_service


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
                    "telefono_cliente": "5491111111111",
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
                    "telefono_cliente": "5491111111111",
                    "observaciones": "",
                },
            ]
        )

        result = process_services(df, settings, today=today)

        self.assertEqual(result.iloc[0]["estado"], "PROXIMO_A_VENCER")
        self.assertTrue(bool(result.iloc[0]["enviar_aviso"]))

    def test_vencido_no_envia_aviso(self):
        today = date(2026, 6, 3)
        settings = load_settings(force_test=True)
        df = pd.DataFrame(
            [
                {
                    "cliente": "Cliente",
                    "equipo": "Equipo",
                    "serial": "SER1",
                    "fecha_service": date(2026, 5, 1),
                    "numero_soporte": "S2",
                    "horas": 1000,
                    "tipo_service": "250 Hs",
                    "lugar": "ZONA",
                    "mail_cliente": "cliente@example.com",
                    "telefono_cliente": "5491111111111",
                    "observaciones": "",
                },
                {
                    "cliente": "Cliente",
                    "equipo": "Equipo",
                    "serial": "SER1",
                    "fecha_service": date(2026, 4, 1),
                    "numero_soporte": "S1",
                    "horas": 750,
                    "tipo_service": "1000 Hs",
                    "lugar": "ZONA",
                    "mail_cliente": "cliente@example.com",
                    "telefono_cliente": "5491111111111",
                    "observaciones": "",
                },
            ]
        )

        result = process_services(df, settings, today=today)

        self.assertEqual(result.iloc[0]["estado"], "VENCIDO")
        self.assertFalse(bool(result.iloc[0]["enviar_aviso"]))


class IsHourServiceTest(unittest.TestCase):
    def test_reconoce_formatos_validos(self):
        self.assertTrue(_is_hour_service("250 Hs"))
        self.assertTrue(_is_hour_service("1000hs"))
        self.assertTrue(_is_hour_service("500 HS"))
        self.assertTrue(_is_hour_service("  250 Hs  "))

    def test_rechaza_falsos_positivos(self):
        self.assertFalse(_is_hour_service("chassis"))
        self.assertFalse(_is_hour_service("Reparacion"))
        self.assertFalse(_is_hour_service(""))
        self.assertFalse(_is_hour_service("hs sin numero"))


if __name__ == "__main__":
    unittest.main()
