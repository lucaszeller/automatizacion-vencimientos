"""Script de prueba: envia un mensaje a multiples numeros con delay dinamico."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import load_settings
from app.notifier_whatsapp import dynamic_delay, send_whatsapp_text

NUMEROS = [
    "5493406415139",
    "5493562451325",
    "5493406645538",
    "5493564617556",
]

MENSAJE = (
    "Hola, este es un mensaje de prueba del sistema de alertas.\n\n"
    "Si recibiste este mensaje, el envio automatico esta funcionando correctamente.\n"
    "Servicio Tecnico."
)


def main():
    settings = load_settings()

    print(f"Proveedor WhatsApp: {settings.whatsapp_provider}")
    print(f"Delay configurado: {settings.whatsapp_delay_min}-{settings.whatsapp_delay_max} segundos")
    print(f"Enviando a {len(NUMEROS)} numeros...\n")

    for i, numero in enumerate(NUMEROS):
        if i > 0:
            print(f"  Esperando delay dinamico...")
            delay = dynamic_delay(settings.whatsapp_delay_min, settings.whatsapp_delay_max)
            print(f"  Delay: {delay:.1f} segundos\n")

        print(f"[{i+1}/{len(NUMEROS)}] Enviando a {numero}...")
        try:
            send_whatsapp_text(numero, MENSAJE, settings)
            print(f"  [OK] Enviado a {numero}")
        except Exception as e:
            print(f"  [ERROR] {numero}: {e}")

    print("\nListo.")


if __name__ == "__main__":
    main()
