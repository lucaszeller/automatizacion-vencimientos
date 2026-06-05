# Alertas de services

Aplicacion mensual para leer services desde TacticaSoft en modo read-only, generar un Excel anual de control similar a `Servicios Terceros 2025.xlsx` y enviar recordatorios por WhatsApp a clientes con services proximos a vencer.

## Uso

1. Crear el entorno e instalar dependencias:

```bash
pip install -r requirements.txt
```

2. Copiar `.env.example` a `.env` y completar credenciales.

3. Para prueba local sin WhatsApp reales:

```bash
python main.py --test
```

4. Para ejecucion mensual real:

```bash
python main.py --run
```

Para abrir la interfaz:

```bash
python main.py --ui
```

O con doble click en `Abrir Alertas Services.bat`.

## Reportes

La app genera un archivo por año:

```text
data/reportes/services_control_YYYY.xlsx
```

Cada periodo mensual se guarda como una hoja dentro de ese archivo (`ENERO`, `FEBRERO`, etc.). Si se vuelve a generar el mismo mes, la hoja se reemplaza.

Al generar un reporte mensual, la app tambien sincroniza los vencimientos en una mini base local:

```text
data/services.db
```

## Tarea diaria

Para ejecutar el control todos los dias sin abrir la interfaz, usar:

```text
Ejecutar Tarea Diaria.bat
```

Ese archivo ejecuta:

```text
dist/Alertas Services Tarea/Alertas Services Tarea.exe
```

En el Programador de tareas de Windows se puede crear una tarea diaria apuntando a `Ejecutar Tarea Diaria.bat`.

La ejecucion diaria revisa la mini base local que se actualiza cuando se genera el reporte desde la UI:

```text
data/services.db
```

Detecta services con fecha estimada entre hoy y `DIAS_ANTES_AVISO`, ignora los que ya tienen fecha pasada y evita duplicar avisos ya enviados. El resultado diario queda en:

```text
data/reportes/services_proximos_YYYY-MM-DD.xlsx
```

## Generar EXE

En la PC de desarrollo, ejecutar:

```bash
Crear EXE.bat
```

El ejecutable queda en:

```text
dist/Alertas Services UI/Alertas Services UI.exe
```

Para usarlo en otra PC, copiar junto al EXE el archivo `.env` configurado. El usuario final no necesita instalar Python ni dependencias.

## TacticaSoft

La app espera que `sql/tacticasoft_services.sql` devuelva estas columnas con alias:

```text
cliente, equipo, serial, fecha_service, numero_soporte, horas,
tipo_service, lugar, mail_cliente, telefono_cliente, observaciones
```

No se hacen escrituras sobre TacticaSoft. La consulta debe ser `SELECT` o `WITH`.
