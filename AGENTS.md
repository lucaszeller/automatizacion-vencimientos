# AGENTS.md — App de Alertas de Services

## 1. Objetivo del proyecto

Desarrollar una aplicación simple en Python para automatizar el control de services próximos a vencer.

La app debe:

- Leer datos desde TácticaSoft o desde una fuente configurable.
- Detectar el service anterior y el service actual/nuevo de cada equipo.
- Calcular la fecha estimada del próximo service.
- Generar un Excel automático de seguimiento para la empresa.
- Enviar recordatorios por Gmail cuando un service esté próximo a vencer.
- Guardar logs, errores y registro de mails enviados.
- Evitar envíos duplicados.
- Ser simple de usar y lo más automática posible.

En esta primera versión NO se hará:

- WhatsApp.
- Panel web.
- Login de usuarios.
- Dashboard avanzado.
- Modificación de datos en TácticaSoft.

La app debe operar en modo lectura sobre TácticaSoft.

---

## 2. Alcance inicial del MVP

### Funcionalidades principales

1. Conexión a la fuente de datos
   - Inicialmente debe soportar modo de prueba leyendo desde Excel/CSV.
   - Luego debe permitir conexión read-only a la base de datos de TácticaSoft.
   - Los datos de conexión deben estar en `.env`.

2. Detección de services
   - Agrupar registros por cliente/equipo/serial.
   - Detectar service actual o último service realizado.
   - Detectar service anterior.
   - Comparar fechas y horas.
   - Calcular promedio de uso diario.
   - Calcular próxima fecha estimada de service.

3. Generación de Excel
   - Crear un Excel automático similar al usado actualmente por la empresa.
   - Debe incluir:
     - Servicio anterior.
     - Servicio actual/nuevo.
     - Próximo service calculado.
     - Estado del aviso.
     - Mail enviado.
     - Observaciones.
   - Guardar el Excel en una carpeta local.

4. Envío de mails
   - Usar Gmail vía SMTP.
   - Usar contraseña de aplicación, no contraseña normal.
   - Enviar recordatorio cuando falten X días para el próximo service.
   - El valor X debe ser configurable.
   - Registrar cada envío.
   - No reenviar el mismo aviso si ya fue enviado.

5. Logs y errores
   - Generar log diario.
   - Guardar errores de conexión.
   - Guardar errores SMTP.
   - Guardar clientes/equipos sin mail.
   - Enviar mail resumen interno al finalizar el proceso.

6. Ejecución automática
   - La app debe poder ejecutarse manualmente.
   - También debe poder correr desde el Programador de tareas de Windows.
   - Debe poder ejecutarse en modo silencioso.

---

## 3. Arquitectura propuesta

```text
TácticaSoft / Excel / CSV
        ↓
lector_datos.py
        ↓
procesador_services.py
        ↓
generador_excel.py
        ↓
mailer_gmail.py
        ↓
logs + registros + reportes
```

---

## 4. Estructura de carpetas

```text
alertas-services/
├─ AGENTS.md
├─ README.md
├─ requirements.txt
├─ .env.example
├─ main.py
├─ app/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ lector_datos.py
│  ├─ conexion_tactica.py
│  ├─ procesador_services.py
│  ├─ generador_excel.py
│  ├─ mailer_gmail.py
│  ├─ logger.py
│  ├─ utils.py
│  └─ modelos.py
├─ templates/
│  └─ recordatorio_service.html
├─ data/
│  ├─ entrada/
│  ├─ registros/
│  ├─ reportes/
│  ├─ enviados/
│  ├─ errores/
│  ├─ logs/
│  └─ respaldos/
└─ tests/
   ├─ test_procesador_services.py
   ├─ test_generador_excel.py
   └─ test_mailer.py
```

---

## 5. Variables de entorno

Crear archivo `.env` basado en `.env.example`.

```env
# Modo de ejecución
APP_ENV=development
MODO_PRUEBA=true

# Fuente de datos
DATA_SOURCE=excel
EXCEL_INPUT_PATH=data/entrada/servicios_prueba.xlsx

# Base de datos TácticaSoft
DB_ENGINE=sqlserver
DB_HOST=CAMBIAR_HOST
DB_PORT=1433
DB_NAME=CAMBIAR_NOMBRE_BD
DB_USER=CAMBIAR_USUARIO
DB_PASSWORD=CAMBIAR_CLAVE
DB_DRIVER=ODBC Driver 17 for SQL Server

# Reglas de aviso
DIAS_ANTES_AVISO=7
REENVIAR_AVISO=false

# Gmail SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=correo_empresa@gmail.com
SMTP_PASSWORD=CAMBIAR_PASSWORD_DE_APLICACION
SMTP_FROM_NAME=Servicio Técnico
SMTP_USE_TLS=true

# Mail interno de control
MAIL_ADMIN=admin@empresa.com
ENVIAR_RESUMEN_ADMIN=true

# Carpetas
OUTPUT_DIR=data/reportes
LOG_DIR=data/logs
ENVIADOS_DIR=data/enviados
ERRORES_DIR=data/errores
RESPALDOS_DIR=data/respaldos
```

---

## 6. Modelo de datos esperado

El sistema debe poder trabajar con estos campos, aunque los nombres reales de TácticaSoft se mapearán después.

```text
cliente
equipo
serial
fecha_service
numero_soporte
horas
tipo_service
lugar
mail_cliente
observaciones
```

Ejemplo:

```csv
cliente,equipo,serial,fecha_service,numero_soporte,horas,tipo_service,lugar,mail_cliente,observaciones
YPF,Equipo 1,SER123,2026-05-10,SOP1234,1500,500 HS,San Francisco,cliente@empresa.com,
YPF,Equipo 1,SER123,2026-04-01,SOP1111,1000,500 HS,San Francisco,cliente@empresa.com,
```

---

## 7. Excel de salida

El Excel generado debe llamarse:

```text
services_control_YYYY-MM-DD.xlsx
```

Debe contener las siguientes columnas:

### Identificación

- Cliente
- Equipo
- Serial
- Lugar
- Mail cliente

### Servicio anterior

- Fecha service anterior
- Soporte anterior
- Horas anteriores
- Tipo service anterior

### Servicio actual / nuevo

- Fecha service actual
- Soporte actual
- Horas actuales
- Tipo service actual

### Cálculos

- Diferencia de horas
- Diferencia de días
- Promedio horas por día
- Horas para próximo service
- Fecha estimada próximo service
- Días restantes
- Estado

### Avisos

- Enviar aviso
- Mail enviado
- Fecha envío mail
- Error envío
- Observaciones

---

## 8. Estados posibles

El campo `Estado` debe tener uno de estos valores:

```text
OK
PROXIMO_A_VENCER
VENCE_HOY
VENCIDO
SIN_DATOS
SIN_MAIL
ERROR_CALCULO
```

Reglas sugeridas:

```text
Si no hay service anterior: SIN_DATOS
Si no hay mail: SIN_MAIL
Si fecha próximo service < hoy: VENCIDO
Si fecha próximo service = hoy: VENCE_HOY
Si fecha próximo service <= hoy + DIAS_ANTES_AVISO: PROXIMO_A_VENCER
Caso contrario: OK
```

---

## 9. Cálculo del próximo service

Calcular:

```text
diferencia_horas = horas_actuales - horas_anteriores
diferencia_dias = fecha_actual - fecha_anterior
promedio_horas_dia = diferencia_horas / diferencia_dias
```

Luego:

```text
horas_objetivo = detectar según tipo de service
horas_restantes = horas_objetivo - horas_actuales
dias_estimados = horas_restantes / promedio_horas_dia
fecha_proximo_service = fecha_actual + dias_estimados
```

Importante:

- Si `diferencia_dias <= 0`, marcar `ERROR_CALCULO`.
- Si `promedio_horas_dia <= 0`, marcar `ERROR_CALCULO`.
- Si faltan datos, marcar `SIN_DATOS`.
- No detener todo el proceso por un registro con error.

---

## 10. Detección de service anterior y actual

Para cada equipo/serial:

1. Agrupar por `serial`.
2. Ordenar por `fecha_service` descendente.
3. El primer registro es el service actual/nuevo.
4. El segundo registro es el service anterior.
5. Si solo existe un registro, marcar `SIN_DATOS`.

Si no existe `serial`, usar combinación:

```text
cliente + equipo
```

---

## 11. Envío de mails

Enviar mail cuando:

```text
Estado sea PROXIMO_A_VENCER, VENCE_HOY o VENCIDO
```

No enviar si:

- No hay mail del cliente.
- Ya se envió un aviso para ese equipo y esa fecha de próximo service.
- `MODO_PRUEBA=true`, salvo que se configure lo contrario.

### Asunto sugerido

```text
Recordatorio de próximo service a vencer
```

### Cuerpo sugerido

```text
Hola,

Le recordamos que el equipo {equipo} / {serial} correspondiente al cliente {cliente}
tiene un próximo service estimado para el día {fecha_proximo_service}.

Datos del último service:
- Fecha: {fecha_service_actual}
- Soporte: {soporte_actual}
- Horas actuales: {horas_actuales}
- Tipo de service: {tipo_service_actual}

Por favor, coordinar disponibilidad para realizar el mantenimiento correspondiente.

Saludos.
Servicio Técnico
```

---

## 12. Registro de mails enviados

Guardar un Excel:

```text
data/enviados/mails_enviados_YYYY.xlsx
```

Columnas:

- Fecha ejecución
- Cliente
- Equipo
- Serial
- Mail destino
- Fecha próximo service
- Estado
- Resultado
- Error
- ID interno del aviso

El `ID interno del aviso` debe construirse así:

```text
cliente|serial|fecha_proximo_service|tipo_service
```

Esto evita duplicados.

---

## 13. Logs

Crear un archivo diario:

```text
data/logs/log_YYYY-MM-DD.txt
```

Debe registrar:

- Inicio del proceso.
- Fuente de datos usada.
- Cantidad de registros leídos.
- Cantidad de equipos procesados.
- Cantidad de avisos a enviar.
- Mails enviados correctamente.
- Errores SMTP.
- Clientes sin mail.
- Errores de cálculo.
- Fin del proceso.

Ejemplo:

```text
08:00 Inicio del proceso
08:01 Fuente de datos: Excel
08:01 Registros leídos: 250
08:02 Equipos procesados: 80
08:03 Avisos a enviar: 12
08:04 Mail enviado: cliente@empresa.com - SER123
08:05 ERROR SMTP: cliente2@empresa.com - Invalid recipient
08:06 Fin del proceso
```

---

## 14. Mail resumen interno

Al finalizar la ejecución, enviar un mail a `MAIL_ADMIN`.

Debe incluir:

```text
Resultado de ejecución diaria

Registros leídos: X
Equipos procesados: X
Avisos enviados: X
Errores: X
Clientes sin mail: X
Archivo generado: services_control_YYYY-MM-DD.xlsx
```

Si hubo errores, indicar:

```text
ATENCIÓN: El proceso finalizó con errores.
Revisar carpeta data/errores y logs.
```

---

## 15. Modo prueba

Cuando `MODO_PRUEBA=true`:

- No enviar mails reales a clientes.
- Generar Excel normalmente.
- Generar logs normalmente.
- Simular envío de mail.
- Opcionalmente enviar todo a `MAIL_ADMIN`.

Esto permite probar la app sin riesgo.

---

## 16. Interfaz simple

Primera versión puede ser por consola.

Comandos sugeridos:

```bash
python main.py --run
python main.py --test
python main.py --generate-excel
python main.py --send-mails
```

Luego se puede agregar una interfaz simple con Tkinter:

Botones:

- Ejecutar control ahora.
- Abrir carpeta de reportes.
- Abrir carpeta de logs.
- Ver último resultado.
- Configuración básica.

---

## 17. Automatización diaria

La app debe poder correr con Programador de tareas de Windows.

Comando esperado:

```bash
python C:\AlertasService\main.py --run
```

Debe finalizar sola al terminar.

---

## 18. Dependencias sugeridas

`requirements.txt`:

```text
pandas
openpyxl
python-dotenv
pyodbc
SQLAlchemy
Jinja2
```

Opcional:

```text
customtkinter
```

---

## 19. Seguridad

- No subir `.env` a Git.
- No hardcodear contraseñas.
- Usar cuenta Gmail dedicada.
- Usar contraseña de aplicación.
- El acceso a TácticaSoft debe ser read-only.
- No hacer UPDATE, DELETE ni INSERT sobre la base de TácticaSoft.
- Guardar logs sin exponer claves.

---

## 20. Criterios de aceptación

La app se considera funcional si:

- Lee datos desde Excel de prueba.
- Procesa service anterior y service actual.
- Calcula próximo service.
- Genera Excel automático.
- Detecta services próximos a vencer.
- Envía mails por Gmail en modo real.
- En modo prueba no envía mails reales.
- Guarda log diario.
- Guarda registro de mails enviados.
- No duplica avisos.
- Continúa ejecutándose aunque falle un mail.
- Envía resumen interno al finalizar.

---

## 21. Prioridades de desarrollo

### Prioridad 1

- Estructura del proyecto.
- Lectura desde Excel.
- Procesamiento de services.
- Generación de Excel.
- Logs.

### Prioridad 2

- Gmail SMTP.
- Registro de enviados.
- Modo prueba.
- Mail resumen interno.

### Prioridad 3

- Conexión read-only a TácticaSoft.
- Mapeo real de tablas/campos.
- Programador de tareas.

### Prioridad 4

- Interfaz simple.
- Mejoras visuales.
- Exportaciones adicionales.

### Prioridad futura

- WhatsApp oficial.
- Panel web.
- Dashboard.
- Base SQLite/PostgreSQL.
- Alertas avanzadas.

---

## 22. Indicaciones para Codex

Cuando modifiques este proyecto:

- Mantener código simple y legible.
- Priorizar estabilidad sobre complejidad.
- No asumir nombres reales de tablas de TácticaSoft.
- Crear funciones pequeñas y testeables.
- Agregar manejo de errores.
- No detener todo el proceso por un único registro inválido.
- Documentar cada módulo.
- Crear ejemplos de `.env.example`.
- Crear datos de prueba si no hay BD.
- Mantener compatibilidad con Windows.
- Evitar dependencias innecesarias.
- No implementar WhatsApp todavía.
- No implementar panel web todavía.

---

## 23. Entregable inicial esperado

Crear una primera versión que permita ejecutar:

```bash
python main.py --test
```

Y genere:

```text
data/reportes/services_control_YYYY-MM-DD.xlsx
data/logs/log_YYYY-MM-DD.txt
data/enviados/mails_enviados_YYYY.xlsx
```

Sin enviar mails reales.

Luego permitir:

```bash
python main.py --run
```

Para ejecutar el proceso completo en modo real.
