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
│           └── CargaExcel.jsx
└── database/
    └── init.sql
```

## Configuración

Copia `.env.example` a `.env` y ajusta las credenciales. Docker Compose lee
ese fichero para sustituir las variables (`DB_USER`, `DB_PASSWORD`, `DB_NAME`,
`DB_PORT`, `DATABASE_URL`, `SECRET_KEY`, `VITE_API_URL`, `VISION_PROVIDER`,
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `BOT_WEBHOOK_TOKEN`, `FRONTEND_ORIGINS`,
`COOKIE_SECURE` y `BCV_URL`).

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
`GET /api/health`, `GET /api/partidos`, `GET /api/arbitros/` y
`POST /api/upload-excel`.

## Libro Excel maestro

La carga masiva exige las hojas: `Estados`, `Ciudades`, `TarifasTraslado`,
`TarifasHospedaje`, `Parametros`, `EstadosCercanos`, `Arbitros` y `Partidos`.
El parámetro `viatico_por_dia` es obligatorio. Las tarifas y catálogos cargados
pueden editarse posteriormente desde la aplicación.

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
| `VISION_PROVIDER=openrouter` | Habilita visión multimodal real. |
| `OPENROUTER_API_KEY` | API key privada de OpenRouter; solo se usa en el backend. |
| `OPENROUTER_MODEL` | Modelo multimodal; por defecto `google/gemini-2.5-flash`. |

Para usar OpenRouter, configura el proveedor y la clave en `.env` y reinicia el
backend/servicio. El reconocimiento puede equivocarse: las sugerencias son
orientativas y la aprobación humana es obligatoria.

## Webhook del bot

Configura `BOT_WEBHOOK_TOKEN` como un secreto largo. La API espera la cabecera
`X-Bot-Token` y un JSON con el teléfono del árbitro y el evento. Puede enviarse
`asignacion_id` o `partido_id`; si se omiten, se aplica a la próxima asignación
pendiente del árbitro.

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

## Cuentas y permisos

La API y la interfaz requieren una sesión autenticada. Los perfiles son:

| Perfil | Capacidades |
| --- | --- |
| `super_admin` | Propietarios: acceso completo, administra usuarios, roles y bloqueo de cuentas. Se crean como máximo dos. |
| `admin` | Gestiona árbitros, canchas, importaciones, partidos y asignaciones. |
| `accountant` | Consulta finanzas, registra/anula gastos reales y descarga informes. No administra la liga. |
| `viewer` | Consulta la aplicación; no modifica datos ni descarga informes. |

En el primer arranque, crea de forma interactiva las dos cuentas propietarias:

```bash
docker compose exec backend flask create-superadmin
docker compose exec backend flask create-superadmin
```

El comando solicita correo, nombre y contraseña sin mostrarla mientras se escribe.
Las contraseñas se almacenan como hash y no son recuperables en texto plano. Un
superadministrador puede emitir una clave temporal de un solo uso para otra
cuenta; el usuario debe reemplazarla al iniciar sesión. El comando
`docker compose exec backend flask reset-user-password correo@ejemplo.com`
permite recuperar una cuenta desde una terminal operativa.

Las cookies de sesión son HttpOnly y las operaciones de escritura requieren CSRF.
En producción configura `SECRET_KEY`, `COOKIE_SECURE=true` y los orígenes HTTPS
permitidos en `FRONTEND_ORIGINS`.

## Finanzas, gastos reales e informes

Los importes de tarifas se interpretan como presupuesto en USD. La vista de
finanzas muestra presupuesto por asignación, gastos reales y variación por
categoría. El perfil contable, administración y superadministración pueden
registrar o anular gastos reales con categoría, fecha, moneda y referencia; las
anulaciones quedan auditadas. Los informes Excel/PDF se agrupan por árbitro,
partido, ciudad o temporada. Los perfiles viewer pueden consultar, pero no
descargar.

Para gastos reales en VES debe existir una tasa BCV guardada para la fecha del
gasto. Administración puede solicitar la tasa publicada hoy o registrar una
tasa histórica verificada. El portal público del BCV no garantiza un endpoint
API estable: si la consulta automática falla, la pantalla informa del error y
se registra manualmente la cotización oficial; no se estima ni inventa.

Por decisión del alcance actual, **no se marca un pago como realizado desde la
aplicación, no se cierra nómina y no se envían correos de pago/nómina**. Los
estados de pagos heredados se conservan para consulta, pero el endpoint rechaza
intentos de modificarlos. Las notificaciones SMTP existentes se limitan a los
eventos operativos ya soportados.

La conversión VES usa la tasa efectiva en la fecha del gasto real (y en la fecha
de pago registrada para los presupuestos ya pagados). Las filas sin tasa
histórica permanecen sin conversión hasta registrar la tasa oficial.

## Notas de desarrollo

La primera inicialización crea las tablas desde los modelos SQLAlchemy. Al hacer
cambios de esquema en un ambiente ya creado, usa migraciones de Flask-Migrate o,
en desarrollo sin datos que conservar, `docker compose down -v` antes de levantar
los contenedores nuevamente.
