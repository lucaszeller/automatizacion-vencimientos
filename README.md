# Alertas de services

Aplicacion mensual para leer services desde TacticaSoft en modo read-only, generar un Excel de control similar a `Servicios Terceros 2025.xlsx` y enviar recordatorios por Gmail a clientes con services proximos a vencer.

## Uso

1. Crear el entorno e instalar dependencias:

```bash
pip install -r requirements.txt
```

2. Copiar `.env.example` a `.env` y completar credenciales.

3. Para prueba local sin mails reales:

```bash
python main.py --test
```

4. Para ejecucion mensual real:

```bash
python main.py --run
```

## TacticaSoft

La app espera que `sql/tacticasoft_services.sql` devuelva estas columnas con alias:

```text
cliente, equipo, serial, fecha_service, numero_soporte, horas,
tipo_service, lugar, mail_cliente, observaciones
```

No se hacen escrituras sobre TacticaSoft. La consulta debe ser `SELECT` o `WITH`.
