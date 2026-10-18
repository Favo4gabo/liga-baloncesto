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

## Puesta en marcha

```bash
docker-compose up --build
```

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

## Estado

El backend ya contiene el modelo de logística, el cálculo de ida/vuelta y la
importación atómica del Excel. El frontend existente es un esqueleto y se
implementará en la siguiente fase.

## Notas de desarrollo

La primera inicialización crea las tablas desde los modelos SQLAlchemy. Al hacer
cambios de esquema en un ambiente ya creado, usa migraciones de Flask-Migrate o,
en desarrollo sin datos que conservar, `docker compose down -v` antes de levantar
los contenedores nuevamente.
