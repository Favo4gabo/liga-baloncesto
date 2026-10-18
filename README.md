# Sistema de gestión y logística de árbitros de baloncesto

Aplicación para la gestión de árbitros, calendario de partidos y asignación/logística
de colegiados a partir de la carga de calendarios en formato Excel.

## Stack

| Capa       | Tecnología                  |
| ---------- | --------------------------- |
| Backend    | Python 3.11 + Flask         |
| Frontend   | React + Vite (`.jsx`)       |
| Base datos | MariaDB 11 (compatible MySQL) |
| Infra      | Docker + docker-compose     |

## Estructura del proyecto

```
.
├── docker-compose.yml
├── .gitignore
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py          # Application factory de Flask
│       ├── database.py          # Configuración SQLAlchemy / sesión
│       ├── models.py            # Catálogos, logística, asignaciones, pagos y eventos
│       ├── services/
│       │   ├── __init__.py
│       │   ├── calculator.py    # Cálculo de traslados, estadía y viáticos
│       │   ├── excel_parser.py  # Importación atómica del libro maestro
│       │   └── notifications.py # Registro y envío SMTP al administrador
│       └── routes/
│           ├── __init__.py      # Registro de blueprints
│           ├── upload.py        # POST /api/upload
│           ├── partidos.py      # CRUD /api/partidos
│           └── arbitros.py      # CRUD /api/arbitros
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── public/
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── components/
│       └── views/
│           ├── Dashboard.jsx
│           ├── Calendario.jsx
│           └── ImportarArchivos.jsx
└── database/
    └── init.sql
```

## Configuración

Copia `.env.example` a `.env` y ajusta las credenciales. Docker Compose lee
ese fichero para sustituir las variables (`DB_USER`, `DB_PASSWORD`, `DB_NAME`,
`DB_PORT`, `DATABASE_URL`, `SECRET_KEY`, `VITE_API_URL`, `VISION_PROVIDER`,
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL` y
`BOT_WEBHOOK_TOKEN`).

```bash
cp .env.example .env
```

## Arranque rápido en Windows

Con Docker Desktop abierto, desde PowerShell y en la raíz del proyecto ejecuta:

```powershell
.\scripts\dev.ps1
```

El comando crea `.env` si hace falta, construye e inicia los contenedores,
espera a que MariaDB y la API estén listos, genera/importa la plantilla de demo
solo si la base está vacía y abre `http://localhost:5173`.

Comandos frecuentes:

```powershell
.\scripts\dev.ps1 logs backend  # logs del backend (también frontend o db)
.\scripts\dev.ps1 status        # estado de servicios
.\scripts\dev.ps1 reset         # borra datos locales y recrea la demo
.\scripts\dev.ps1 help          # lista completa
```

En Linux, macOS, Git Bash o WSL puede usarse el Makefile equivalente:

```bash
make demo
make help
```

### Probar el bot de Telegram

El bot funciona en modo **polling** y no necesita una URL pública ni
`BOT_WEBHOOK_TOKEN`. Configura en `.env` un token nuevo generado por
`@BotFather`, además de los IDs de Telegram que podrán aprobar gastos:

```env
TELEGRAM_BOT_TOKEN=pega_aqui_el_token_nuevo
TELEGRAM_ADMIN_IDS=123456789
```

Con Docker, inicia el perfil del bot desde la raíz:

```powershell
docker compose --profile telegram up -d --build
docker compose logs -f telegram-bot
```

Sin Docker, con las dependencias del backend instaladas y el entorno virtual
activado, puedes iniciarlo en otra consola:

```powershell
$env:PYTHONPATH = "backend"
python -m app.telegram_bot
```

El log debe mostrar `Bot de Telegram iniciado en modo polling.`. También
puedes comprobar la identidad del bot sin mostrar el token en pantalla:

```powershell
$token = (Get-Content .env | Where-Object { $_ -match '^TELEGRAM_BOT_TOKEN=' } |
  ForEach-Object { $_.Substring('TELEGRAM_BOT_TOKEN='.Length) })
Invoke-RestMethod "https://api.telegram.org/bot$token/getMe" |
  Select-Object -ExpandProperty ok
```

El resultado debe ser `True`. Para saber tu ID, escribe `/mi_id` al bot.

Prueba el flujo en este orden:

1. En el catálogo, verifica que el teléfono del árbitro esté registrado.
2. En Telegram, escribe `/start` y comparte **tu propio contacto**.
3. Pulsa **Mis asignaciones** y selecciona un partido próximo.
4. Prueba **En camino** y **Llegué a instalación**; revisa que cambie el
   estado de viaje en el calendario.
5. Prueba **Reportar retraso** enviando `20 | tráfico`.
6. Prueba **Reportar gasto** enviando `12,50 | taxi | traslado adicional`.
7. Desde una cuenta cuyo ID esté en `TELEGRAM_ADMIN_IDS`, escribe `/pendientes`
   y aprueba el gasto. El total de la asignación y su pago deben aumentar.

Si el bot no responde, revisa `docker compose logs telegram-bot`. Un error
`401 Unauthorized` indica un token inválido o revocado. Si no aparecen
asignaciones, comprueba que el árbitro esté vinculado al teléfono exacto del
catálogo y tenga un partido futuro asignado.

### Arranque local sin Docker

Si no tienes Docker, hay un script equivalente que levanta backend y frontend
directamente sobre tu máquina usando SQLite y el entorno virtual `.venv`:

```powershell
.\scripts\dev-local.ps1              # arranca todo, carga la demo si falta y abre la app
.\scripts\dev-local.ps1 status       # estado de los servicios locales
.\scripts\dev-local.ps1 logs frontend
.\scripts\dev-local.ps1 stop         # detiene sin borrar datos
.\scripts\dev-local.ps1 help         # lista completa
```

Cada servicio corre en segundo plano y escribe sus logs en `.run/`. La base de
datos local es `backend/dev.db`; si existe un `.env` con el `DATABASE_URL` de
Docker (host `db`) el script lo ignora y avisa por pantalla.

## Puesta en marcha

```bash
docker-compose up --build
```

> Para desarrollo se recomienda `docker compose` (con espacio), que es el
> comando que emplean el Makefile y `scripts/dev.ps1`.

- Frontend: http://localhost:5173
- Backend:  http://localhost:5000
- MariaDB:  localhost:3306

## Desarrollo local del backend sin React

Desde la raíz del proyecto, crea un entorno virtual e instala las dependencias:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

Si no defines `DATABASE_URL`, el backend usa SQLite y crea `backend/dev.db`.
Docker Compose usa MariaDB porque proporciona `DATABASE_URL` explícitamente.

Para comprobar la aplicación y crear las tablas:

```powershell
$env:PYTHONPATH = "backend"
python -c "from app import create_app; app = create_app(); print('Backend inicializado correctamente')"
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('Tablas creadas con éxito')"
```

Después, inicia Flask:

```powershell
$env:FLASK_APP = "app"
python -m flask run --port=5000
```

Abre http://localhost:5000 para ver la interfaz temporal de Flask. También
puedes consultar los endpoints desde Thunder Client o Postman:
`GET /api/health`, `GET /api/partidos` y `GET /api/arbitros/`.

De forma opcional, el libro puede incluir estas hojas para la planificación de
viajes y sedes:

| Hoja | Columnas | Uso |
| --- | --- | --- |
| `DistanciasCiudades` | `ciudad_origen`, `ciudad_destino`, `distancia_km` | Matriz de distancias bidireccional para estimar trayectos. |
| `UbicacionesCancha` | `estadio_cancha`, `ciudad`, `direccion`, `latitud`, `longitud` | Dirección y coordenadas de cada sede. |

La estimación mostrada al asignar un árbitro aplica `T = distancia / velocidad
+ margen logístico`: local (≤40 km) a 35 km/h + 15 min, terrestre a 75 km/h +
30 min y avión a 550 km/h + 2 h. La API entrega duración, llegada proyectada y
porcentaje de avance; el frontend actualiza el avance cada 30 segundos.

### Recomendaciones para importar horarios

Para que la lectura automática sea más precisa, usa una tabla simple con una
sola fila de encabezados y una fila por partido. Los encabezados reconocidos
son `fecha`, `hora`, `árbitro`, `cancha`/`estadio` y `ciudad`; también se
admite una columna combinada `fecha_hora`. Evita celdas combinadas, subtítulos
intercalados y fórmulas sin valor calculado. La pantalla de previsualización
resalta los campos con baja confianza para corregirlos antes de confirmar.

En el calendario, cada árbitro asignado tiene la opción **Cambiar árbitro**.
El cambio vuelve a calcular viáticos, traslados y hospedaje con la ciudad de
origen del nuevo árbitro. Al pasar el cursor sobre su nombre se muestra una
ayuda con el nombre completo.

## Estado

El backend contiene el modelo de logística, el cálculo de ida/vuelta, la
importación atómica del Excel y la API de partidos/asignaciones. El frontend
incluye resumen, carga de Excel y calendario operativo con detalle de viajes.

## Calendario operativo

La sección **Calendario** incorpora una vista mensual navegable y una agenda de
árbitros por los próximos 14 días. Al seleccionar un día se muestra el detalle
de partidos, árbitros, origen/destino, estado del viaje, hospedaje y una barra
de avance para los traslados entre ciudades. Los trayectos aparecen cuando los
árbitros están asignados a un partido.

## Lector de horarios (OCR/visión)

En **Importar archivos** se encuentran, en una sola opción del menú, el libro
maestro `.xlsx` y la lectura de horarios. En el modo **Leer horario** se pueden
previsualizar `.xlsx`, `.csv`, `.png`, `.jpg` y `.jpeg`. La ruta
`POST /api/horarios/escanear` solo procesa y devuelve
filas con sugerencias de árbitro, cancha y ciudad; no guarda información. La
tabla debe revisarse y editarse antes de llamar a `POST /api/horarios/confirmar`.
La confirmación crea el partido si aún no existe para la combinación de fecha y
cancha, y registra cada asignación usando el mismo cálculo logístico que el
calendario. Un partido admite como máximo dos árbitros. El lote se confirma como
una transacción: ante una fila inválida no se registra parcialmente.

Variables del lector en `.env`:

| Variable | Uso |
| --- | --- |
| `VISION_PROVIDER=simulado` | Modo local sin llamadas externas; útil para comprobar la interfaz. No interpreta realmente los píxeles de la imagen. |
| `VISION_PROVIDER=openrouter` | Visión multimodal real mediante OpenRouter. |
| `VISION_PROVIDER=gemini` | Visión multimodal real con la API de Google (Google AI Studio). |
| `OPENROUTER_API_KEY` | API key privada de OpenRouter (`sk-or-v1-...`); solo se usa en el backend. |
| `OPENROUTER_MODEL` | Modelo multimodal de OpenRouter; por defecto `google/gemini-2.5-flash`. |
| `GEMINI_API_KEY` | API key de Google AI Studio (`AIza...`); solo se usa en el backend. |
| `GEMINI_MODEL` | Modelo de Gemini; por defecto `gemini-2.5-flash`. |

Para usar visión real, elige un proveedor, coloca su clave en `.env` y reinicia
el backend/servicio (por ejemplo `.\scripts\dev-local.ps1 restart` en local o
`docker compose up -d --force-recreate backend` con Docker). El reconocimiento
puede equivocarse: las sugerencias son orientativas y la aprobación humana es
obligatoria.

## Webhook del bot

Configura `BOT_WEBHOOK_TOKEN` como un secreto largo. La API espera la cabecera
`X-Bot-Token` y un JSON con el teléfono del árbitro y el evento. Puede enviarse
`asignacion_id` o `partido_id`; si se omiten, se aplica a la próxima asignación
pendiente del árbitro.

## Bot de Telegram para árbitros

Para probar el bot localmente, configura en `.env` `TELEGRAM_BOT_TOKEN` (de
@BotFather) y opcionalmente `TELEGRAM_ADMIN_IDS` con los IDs numéricos de las
cuentas autorizadas a revisar gastos, separados por comas. Arranca el entorno
con `.\scripts\dev-local.ps1 restart`; el script inicia el bot en polling
solo cuando encuentra el token. No hace falta publicar un webhook ni exponer
localhost. En Docker se puede arrancar con
`docker compose --profile telegram up -d telegram-bot`.

El árbitro inicia con `/start` y vincula la cuenta compartiendo su propio
teléfono, que se valida contra el catálogo. Puede informar que va en camino,
reportar retraso, confirmar llegada o registrar un gasto con el formato
`monto | concepto | detalle`. Los gastos quedan pendientes y solo se agregan al
costo de la asignación cuando un administrador los aprueba desde Telegram. El
comando `/mi_id` permite consultar el ID numérico de Telegram para añadirlo a
`TELEGRAM_ADMIN_IDS`; `/pendientes` lista los gastos por revisar.
Antes de que el bot pueda enviarle avisos, cada administrador debe abrir el bot
y enviar `/start`. Los árbitros vinculan su cuenta compartiendo su propio
contacto de Telegram; su teléfono se compara con el guardado en el catálogo.

```json
{
  "telefono": "+58 414 1234567",
  "evento": "Retraso",
  "minutos_retraso": 15,
  "partido_id": 12
}
```

Eventos aceptados: `En camino`, `En cancha` y `Retraso`; `En cancha` se almacena
como `En estadio`. Cada cambio se registra en `GET /api/historial` con origen
`bot_whatsapp`, estado anterior/nuevo y minutos de retraso.

Prueba local en PowerShell (el backend debe estar levantado y el token debe
coincidir con `.env`):

```powershell
$token = "tu-secreto-configurado"
$payload = @{ telefono = "+58 414 1234567"; evento = "Retraso"; minutos_retraso = 15; partido_id = 12 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:5000/api/bot/webhook" `
  -Headers @{ "X-Bot-Token" = $token } -ContentType "application/json" -Body $payload
Invoke-RestMethod "http://localhost:5000/api/historial?entidad=asignacion&origen=bot_whatsapp"
```

Endpoints nuevos:

| Método | Ruta | Función |
| --- | --- | --- |
| `POST` | `/api/horarios/escanear` | Previsualización solo lectura del horario. Multipart: campo `file`. |
| `POST` | `/api/horarios/confirmar` | Inserta las filas revisadas por una persona. JSON: `{ "filas": [...] }`. |
| `POST` | `/api/bot/webhook` | Actualiza el estado arbitral; requiere `X-Bot-Token`. |
| `GET` | `/api/historial` | Consulta bitácora con filtros y paginación. |

## Notas de desarrollo

La primera inicialización crea las tablas desde los modelos SQLAlchemy. Al hacer
cambios de esquema en un ambiente ya creado, usa migraciones de Flask-Migrate o,
en desarrollo sin datos que conservar, `docker compose down -v` antes de levantar
los contenedores nuevamente.
