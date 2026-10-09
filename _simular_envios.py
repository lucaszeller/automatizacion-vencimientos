"""
Simulacion de envios WhatsApp: muestra cuantos mensajes se enviarian hoy
y el detalle de cada uno, sin enviar nada.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.config import load_settings, ensure_directories
from app.lector_datos import load_source_data
from app.procesador_services import process_services
from app.notifier_whatsapp import build_service_message, normalize_phone

settings = load_settings()
ensure_directories(settings)

print("Cargando datos de TacticaSoft...")
raw = load_source_data(settings)
print(f"  {len(raw)} registros leidos.")

print("\nProcesando equipos...")
df = process_services(raw, settings)
print(f"  {len(df)} equipos procesados.\n")

# Resumen por estado
print("=" * 60)
print("RESUMEN POR ESTADO")
print("=" * 60)
for estado in ["PROXIMO_A_VENCER", "VENCE_HOY", "VENCIDO", "OK", "SIN_CONTACTO", "SIN_DATOS", "ERROR_CALCULO"]:
    count = int((df["estado"] == estado).sum()) if "estado" in df.columns else 0
    if count > 0:
        print(f"  {estado:<25} {count}")

# Equipos que recibirian mensaje
a_enviar = df[df.get("enviar_aviso", False) == True] if "enviar_aviso" in df.columns else df.iloc[0:0]

print(f"\n{'=' * 60}")
print(f"MENSAJES A ENVIAR: {len(a_enviar)}")
print("=" * 60)

if a_enviar.empty:
    print("  Ninguno por el momento.")
else:
    def tel_es_valido(telefono_cliente):
        tel = normalize_phone(telefono_cliente, settings.whatsapp_country_prefix)
        return tel, 12 <= len(tel) <= 13

    for i, (_, row) in enumerate(a_enviar.iterrows(), 1):
        tel, tel_valido = tel_es_valido(row.get("telefono_cliente"))
        dias = row.get("dias_restantes", "?")
        prox = row.get("fecha_estimada_proximo_service", "?")
        if hasattr(prox, "strftime"):
            prox = prox.strftime("%d/%m/%Y")
        print(f"\n[{i}] {row['cliente']} | {row['serial']} | Estado: {row['estado']}")
        if tel_valido:
            print(f"    Telefono:        +{tel}")
        else:
            print(f"    Telefono:        +{tel}  *** INVALIDO - revisar en TacticaSoft ***")
        dias_str = int(dias) if dias != "?" and str(dias) not in ("", "nan") else dias
        print(f"    Proximo service: {prox} (en {dias_str} dias)")
        print(f"    Tipo actual:     {row.get('tipo_service_actual', '')}")
        if tel_valido:
            print(f"    --- MENSAJE ---")
            msg = build_service_message(row, operario_whatsapp=settings.operario_whatsapp)
            for line in msg.split("\n"):
                print(f"    {line}")
        else:
            print(f"    (mensaje no se enviaria por telefono invalido)")

print(f"\n{'=' * 60}")
print(f"Simulacion completada. No se envio ningun mensaje.")
print("=" * 60)

# --- RESUMEN ADMIN (como llegaria al WhatsApp) ---
a_vencer = len(a_enviar)

# De los que vencen hoy/proximos: cuales tienen telefono invalido o ausente
sin_contacto_nombres = []
enviados_reales = 0
for _, r in a_enviar.iterrows():
    tel, valido = tel_es_valido(r.get("telefono_cliente"))
    if valido:
        enviados_reales += 1
    else:
        nombre = r.get("cliente", "")
        if not tel:
            label = f"{nombre}: sin numero cargado"
        else:
            label = f"{nombre}: numero invalido (+{tel})"
        sin_contacto_nombres.append(label)
sin_contacto_nombres = sorted(set(sin_contacto_nombres))

error_calculo_rows = df[df["estado"] == "ERROR_CALCULO"]
error_calculo_nombres = []
if not error_calculo_rows.empty:
    for _, r in error_calculo_rows.iterrows():
        motivo = r.get("error_calculo_motivo", "")
        label = r.get("cliente", "")
        if motivo:
            label = f"{label}: {motivo}"
        error_calculo_nombres.append(label)
    error_calculo_nombres = sorted(set(error_calculo_nombres))

lines = [
    "",
    "=" * 60,
    "MENSAJE QUE RECIBE EL ADMIN:",
    "=" * 60,
    "",
    "Resumen de services del dia:",
    "",
    f"Services a vencer: {a_vencer}",
    "",
    f"Mensajes enviados: {enviados_reales}",
]
if sin_contacto_nombres:
    lines.append("")
    lines.append(f"Sin contacto o mal cargado ({len(sin_contacto_nombres)}):")
    for nombre in sin_contacto_nombres:
        lines.append(f"  - {nombre}")
if error_calculo_nombres:
    lines.append("")
    lines.append(f"Error de calculo - revisar en TacticaSoft ({len(error_calculo_nombres)}):")
    for nombre in error_calculo_nombres:
        lines.append(f"  - {nombre}")

print("\n".join(lines))
