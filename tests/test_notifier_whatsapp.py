import unittest

import pandas as pd

from app.notifier_whatsapp import build_service_message, normalize_phone


class WhatsAppMessageTest(unittest.TestCase):
    def test_message_includes_model_hours_and_due_date(self):
        row = pd.Series(
            {
                "cliente": "Cliente",
                "equipo": "Toyota 8FG25",
                "serial": "SER-123",
                "horas_actuales": 1250,
                "fecha_estimada_proximo_service": "2026-06-10",
            }
        )

        message = build_service_message(row)

        self.assertIn("Toyota 8FG25", message)
        self.assertIn("1250", message)
        self.assertIn("2026-06-10", message)
        self.assertIn("proximo a vencer", message)


class NormalizePhoneTest(unittest.TestCase):
    def test_agrega_prefijo_cuando_falta(self):
        result = normalize_phone("1134567890", country_prefix="54")
        self.assertEqual(result, "541134567890")

    def test_no_duplica_prefijo_existente(self):
        result = normalize_phone("541134567890", country_prefix="54")
        self.assertEqual(result, "541134567890")

    def test_elimina_caracteres_no_numericos(self):
        result = normalize_phone("+54 11 3456-7890", country_prefix="54")
        self.assertEqual(result, "541134567890")

    def test_retorna_vacio_para_valor_nulo(self):
        self.assertEqual(normalize_phone(None, country_prefix="54"), "")
        self.assertEqual(normalize_phone("", country_prefix="54"), "")

    def test_prefijo_con_signo_mas(self):
        # WHATSAPP_COUNTRY_PREFIX podria venir como "+54"
        result = normalize_phone("1134567890", country_prefix="+54")
        self.assertEqual(result, "541134567890")


if __name__ == "__main__":
    unittest.main()
