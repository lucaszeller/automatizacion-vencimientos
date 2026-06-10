# Alertas de services

Aplicacion para leer services desde TacticaSoft en modo read-only, generar un Excel anual de control y enviar recordatorios por WhatsApp a clientes con services proximos a vencer.

El proceso tiene dos modos de ejecucion:

- **Mensual** (desde la UI o linea de comandos): genera el reporte Excel completo del periodo, sincroniza la base local y envia avisos a los clientes correspondientes.
- **Diario** (tarea automatica): revisa la base local, detecta vencimientos proximos y envia avisos sin necesidad de regenerar el reporte completo.

---

## Instalacion

1. Instalar dependencias:

```bash
pip install -r requirements.txt
```

2. Copiar `.env.example` a `.env` y completar todas las credenciales (ver seccion **Configuracion** mas abajo).

---

## Uso

### Interfaz grafica

```bash
python main.py --ui
```

O con doble click en `Abrir Alertas Services.bat`.

### Linea de comandos

| Comando | Descripcion |
|---|---|
| `python main.py --test` | Prueba local con datos simulados, sin enviar WhatsApp reales |
| `python main.py --run` | Ejecucion completa real |
| `python main.py --generate-excel` | Solo genera el Excel, sin enviar avisos |
| `python main.py --send-mails` | Solo procesa avisos, sin regenerar Excel |
| `python main.py --period 2026-01` | Genera el reporte para un periodo especifico (YYYY-MM) |

### Tarea diaria automatica

```text
Ejecutar Tarea Diaria.bat
```

Ejecuta `dist/Alertas Services Tarea/Alertas Services Tarea.exe`. En el Programador de tareas de Windows se puede apuntar a este `.bat` para que corra automaticamente cada dia.

La tarea diaria revisa `data/services.db` (que se actualiza al generar el reporte mensual desde la UI), detecta services con fecha estimada entre hoy y `DIAS_ANTES_AVISO` dias, y evita reenviar avisos ya enviados.

El resultado queda en:

```text
data/reportes/services_proximos_YYYY-MM-DD.xlsx
```

Los reportes diarios mas viejos que `DIAS_CONSERVAR_REPORTES_DIARIOS` dias se eliminan automaticamente al finalizar cada ejecucion.

---

## Reportes

La app genera un archivo Excel por año:

```text
data/reportes/services_control_YYYY.xlsx
```

Cada periodo mensual se guarda como una hoja dentro del archivo (`ENERO`, `FEBRERO`, etc.). Si se vuelve a generar el mismo mes, la hoja se reemplaza.

Al generar el reporte mensual, la app sincroniza los vencimientos en la base local SQLite:

```text
data/services.db
```

---

## Historial de avisos enviados

Los avisos enviados se registran en dos lugares:

- **`data/services.db` (tabla `avisos`)**: fuente de verdad para deduplicacion. Tanto el flujo mensual como el diario leen de aqui para evitar reenvios.
- **`data/enviados/whatsapp_enviados_YYYY.xlsx`**: log legible para revision manual.

Si `REENVIAR_AVISO=false` (default), un aviso con el mismo ID no se vuelve a enviar aunque se vuelva a ejecutar el proceso.

---

## Configuracion (.env)

Copiar `.env.example` a `.env` y completar los valores marcados con `CAMBIAR_`.

### Modo de ejecucion

| Variable | Default | Descripcion |
|---|---|---|
| `APP_ENV` | `development` | Entorno de ejecucion (informativo) |
| `MODO_PRUEBA` | `false` | `true` para simular envios sin usar WhatsApp real. **Si no se define, el proceso corre en modo real y lo advierte en el log.** |

> **Importante:** `MODO_PRUEBA` debe estar explicitamente en el `.env`. Si no esta definida, la app asume modo real y emite una advertencia en el log. Usar `--test` desde linea de comandos siempre fuerza modo prueba independientemente de esta variable.

### Fuente de datos

| Variable | Default | Descripcion |
|---|---|---|
| `DATA_SOURCE` | `database` | Origen de datos: `database` (TacticaSoft via SQL), `excel` (archivo local) o `sample` (datos de prueba internos) |
| `EXCEL_INPUT_PATH` | `data/entrada/servicios_prueba.xlsx` | Ruta al Excel de entrada cuando `DATA_SOURCE=excel` |

### Conexion a TacticaSoft (cuando `DATA_SOURCE=database`)

| Variable | Default | Descripcion |
|---|---|---|
| `DB_ENGINE` | `mysql` | Motor de base de datos: `mysql` o `sqlserver` |
| `DB_HOST` | — | Host del servidor de base de datos |
| `DB_PORT` | `3307` | Puerto |
| `DB_NAME` | — | Nombre de la base de datos |
| `DB_USER` | — | Usuario |
| `DB_PASSWORD` | — | Contrasena |
| `DB_DRIVER` | `ODBC Driver 17 for SQL Server` | Driver ODBC (solo para `sqlserver`) |
| `DB_QUERY_PATH` | `sql/tacticasoft_services.sql` | Ruta al archivo SQL de consulta |

### Reglas de aviso

| Variable | Default | Descripcion |
|---|---|---|
| `DIAS_ANTES_AVISO` | `7` | Dias de anticipacion para considerar un service como "proximo a vencer" |
| `HORAS_PARA_PROXIMO_SERVICE` | `250` | Horas de uso entre services (umbral para calcular fecha estimada) |
| `REENVIAR_AVISO` | `false` | `true` para permitir reenviar avisos ya enviados en ejecuciones anteriores |
| `DIAS_CONSERVAR_REPORTES_DIARIOS` | `30` | Cantidad de dias que se conservan los archivos `services_proximos_*.xlsx`. Los mas viejos se eliminan automaticamente. |

### WhatsApp (Cloud API de Meta)

| Variable | Default | Descripcion |
|---|---|---|
| `WHATSAPP_API_URL` | `https://graph.facebook.com/v20.0` | URL base de la API de WhatsApp |
| `WHATSAPP_TOKEN` | — | Token de acceso de la Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | — | ID del numero de telefono en Meta |
| `WHATSAPP_ADMIN_NUMBER` | — | Numero interno que recibe el resumen de cada ejecucion (formato internacional, ej. `5491112345678`) |
| `ENVIAR_RESUMEN_ADMIN` | `true` | `true` para enviar el resumen de ejecucion al numero admin |
| `WHATSAPP_COUNTRY_PREFIX` | `54` | Prefijo de pais que se agrega automaticamente a numeros que no lo incluyan (Argentina = 54). Se puede escribir con o sin `+`. |

> **Health-check:** al arrancar en modo real, la app verifica que `WHATSAPP_TOKEN` y `WHATSAPP_PHONE_NUMBER_ID` esten configurados. Si alguno falta, lo reporta en el log antes de intentar enviar cualquier mensaje.

> **Normalizacion de telefonos:** todos los numeros pasan por `normalize_phone()`, que extrae solo digitos y agrega `WHATSAPP_COUNTRY_PREFIX` si el numero no lo tiene. Si el numero resultante tiene menos de 10 digitos, se emite una advertencia en el log.

### Carpetas de datos

| Variable | Default | Descripcion |
|---|---|---|
| `OUTPUT_DIR` | `data/reportes` | Reportes Excel generados |
| `SERVICES_DB_PATH` | `data/services.db` | Base local SQLite |
| `LOG_DIR` | `data/logs` | Archivos de log diarios |
| `ENVIADOS_DIR` | `data/enviados` | Log Excel de avisos enviados |
| `ERRORES_DIR` | `data/errores` | Reservado para errores |
| `RESPALDOS_DIR` | `data/respaldos` | Reservado para respaldos |

---

## TacticaSoft

La app espera que `sql/tacticasoft_services.sql` devuelva estas columnas con alias:

```text
cliente, equipo, serial, fecha_service, numero_soporte, horas,
tipo_service, lugar, mail_cliente, telefono_cliente, observaciones
```

No se hacen escrituras sobre TacticaSoft. La consulta debe ser `SELECT` o `WITH`.

---

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

---

## Tests

La suite de tests corre con:

```bash
python -m unittest discover -s tests -v
```

No requiere conexion a TacticaSoft ni credenciales de WhatsApp. Todos los tests usan bases SQLite temporales y datos en memoria.

| Archivo | Que cubre |
|---|---|
| `test_procesador_services.py` | Calculo de estados (PROXIMO_A_VENCER, VENCIDO), deteccion de tipos de service por horas, falsos positivos en `_is_hour_service` |
| `test_daily_alerts.py` | Filtrado de proximos vs vencidos vs lejanos, limpieza automatica de reportes diarios viejos |
| `test_service_store.py` | Persistencia de overrides de telefono entre sincronizaciones, `get_sent_aviso_ids` (incluye enviados/simulados, excluye errores) |
| `test_notifier_whatsapp.py` | Formato del mensaje WhatsApp, normalizacion de telefonos (prefijo de pais, caracteres no numericos, valores nulos) |

---

## Arquitectura interna

```
main.py                  Punto de entrada y orquestacion
app/
  config.py              Carga de .env y dataclass Settings
  lector_datos.py        Lectura desde TacticaSoft o Excel
  procesador_services.py Calculo de fechas estimadas y estados
  generador_excel.py     Generacion del reporte Excel mensual
  service_store.py       Base local SQLite (services, avisos, phone_overrides)
  notifier_whatsapp.py   Envio de mensajes y normalizacion de telefonos
  daily_alerts.py        Revision diaria y limpieza de reportes viejos
  ui.py                  Interfaz grafica simple
  logger.py              Configuracion de logging
  utils.py               Funciones compartidas
sql/
  tacticasoft_services.sql  Consulta read-only a TacticaSoft
data/
  services.db            Base local SQLite
  reportes/              Reportes Excel mensuales y diarios
  enviados/              Log de avisos enviados
  logs/                  Logs de ejecucion
```
