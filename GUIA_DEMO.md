# Guía de demostración — Gestor de árbitros de baloncesto (ArbiLiga)

Esta guía explica, paso a paso, cómo levantar el proyecto con Docker y
Docker Compose, cargar datos de ejemplo y verlo en el navegador.

---

## 1. Requisitos previos

- **Docker** instalado.
- **Docker Compose** (viene con Docker Desktop o el plugin `docker compose`).
- Tu usuario debe pertenecer al grupo **`docker`** (ver paso 2).

Comprueba que están instalados:

```bash
docker --version
docker compose version
```

---

## 2. Dar permiso a tu usuario para usar Docker (solo la primera vez)

```bash
sudo usermod -aG docker $USER
```

> Escribe tu contraseña de Linux. Este comando agrega tu usuario al grupo
> `docker`, para no tener que usar `sudo` en cada comando.

**Muy importante:** los grupos se asignan **al iniciar sesión**. Tu terminal
**abierta antes** de este comando seguirá dando:

```
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

Tienes tres formas de solucionarlo:

| Opción | Comando | Cuándo usarla |
| --- | --- | --- |
| **A. Cerrar sesión (recomendada)** | Cierra sesión y vuelve a entrar (o reinicia) | Arreglo definitivo |
| **B. Nueva subshell con el grupo** | `newgrp docker` | Arreglo rápido en la terminal actual (sal con `exit`) |
| **C. Un solo comando** | `sg docker -c "docker compose up --build -d"` | Solo para probar algo puntual |

Comprueba que ya tienes el grupo (debe aparecer `docker`):

```bash
id -nG
```

---

## 3. Levantar el proyecto

### Windows (método recomendado)

Abre Docker Desktop. Luego abre PowerShell en la raíz del proyecto y ejecuta:

```powershell
.\scripts\dev.ps1
```

El script prepara `.env`, levanta los servicios, espera a que estén disponibles,
carga la plantilla solo cuando no hay datos y abre la página automáticamente.
Para ayuda y diagnósticos:

```powershell
.\scripts\dev.ps1 help
.\scripts\dev.ps1 logs backend
.\scripts\dev.ps1 reset
```

### Linux, macOS, Git Bash o WSL

Entra a la carpeta del proyecto:

```bash
cd /home/gabo/proyecto_curso/Liga-baloncesto
```

Crea el archivo de configuración (solo si no existe):

```bash
cp .env.example .env
```

Levanta los tres servicios (base de datos, backend y frontend):

```bash
docker compose up --build -d
```

También puedes ejecutar `make demo` para realizar todos los pasos, incluida la
carga inicial, de forma automática.

- `--build`: construye las imágenes con el código actual (la primera vez tarda
  unos minutos).
- `-d`: deja los contenedores corriendo en segundo plano.

Verifica el estado:

```bash
docker compose ps
```

Debes ver los 3 contenedores en `Up`, y `arbitros_db` con `(healthy)`.

---

## 4. Generar y cargar datos de ejemplo

Genera la plantilla Excel de ejemplo:

```bash
docker compose exec -T backend python scripts/generar_plantilla.py /app/plantilla_liga.xlsx
```

El archivo quedará en tu carpeta como `backend/plantilla_liga.xlsx`.

La interfaz web permite cargar horarios desde **Importar archivos**. Selecciona
un archivo `.xlsx`, `.csv`, `.png` o `.jpg`, revisa la previsualización y
confirma únicamente los datos correctos.

---

## 5. Ver la página

Abre en el navegador:

```
http://localhost:5173
```

- **Resumen**: métricas y próximos partidos.
- **Calendario**: partidos por fecha, sede y árbitros asignados.
- **Importar Excel**: carga masiva de datos.

---

## 6. Comandos útiles durante la demo

```bash
docker compose ps                     # estado de los contenedores
docker compose logs -f backend        # logs del backend en vivo (Ctrl+C para salir)
docker compose logs -f frontend       # logs del frontend en vivo
curl -s http://localhost:5000/api/health   # probar la API
curl -s http://localhost:5000/api/partidos # ver partidos cargados
```

---

## 7. Detener y reiniciar

```bash
docker compose stop          # pausa (conserva los datos)
docker compose start         # reanuda
docker compose down          # baja los contenedores (CONSERVA la base de datos)
docker compose down -v       # baja y BORRA la base de datos (demo limpia)
docker compose up --build -d # volver a levantar
```

---

## 8. Solución de problemas

### `permission denied ... docker.sock`
Tu terminal no tiene el grupo `docker`. Cierra sesión y vuelve a entrar, usa
`newgrp docker`, o antepón `sg docker -c "..."`.

### `unauthorized: personal access token is expired`
Tu Docker tiene un login con token vencido. Solución:

```bash
docker logout     # las imágenes usadas son públicas
# o
docker login      # si prefieres volver a autenticarte
```

### `port is already allocated` (5000, 5173 o 3306)
Otro proceso usa el puerto. Detén lo que esté corriendo ahí o cambia los
puertos en `.env` y `docker-compose.yml`.

### La página sale en blanco
Confirma que los contenedores están arriba (`docker compose ps`) y revisa los
logs (`docker compose logs -f frontend`). Es una aplicación React (SPA), así que
"ver código fuente" muestra muy poco: es normal.

### Las imágenes no se descargan
Necesitas internet la primera vez. Tras la primera ejecución quedan en caché.

---

## 9. Puertos y credenciales

| Servicio | URL / Puerto | Notas |
| --- | --- | --- |
| Frontend | http://localhost:5173 | Panel de administración |
| Backend (API) | http://localhost:5000/api | API Flask |
| MariaDB | localhost:3306 | Usuario/clave definidos en `.env` |

Los datos se guardan en el volumen `liga-baloncesto_db_data` y sobreviven a
reinicios. Solo se borran con `docker compose down -v`.
