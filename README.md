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
`DB_PORT`, `DATABASE_URL`, `SECRET_KEY`, `VITE_API_URL`).

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

## Notas de desarrollo

La primera inicialización crea las tablas desde los modelos SQLAlchemy. Al hacer
cambios de esquema en un ambiente ya creado, usa migraciones de Flask-Migrate o,
en desarrollo sin datos que conservar, `docker compose down -v` antes de levantar
los contenedores nuevamente.
