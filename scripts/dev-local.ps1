<#
.SYNOPSIS
    Arranque local de ArbiLiga sin Docker (backend Flask + frontend Vite).

.DESCRIPTION
    Levanta el backend con SQLite (backend/dev.db) y el frontend con Vite, cada
    uno en segundo plano y con sus logs en la carpeta .run/.
    Está pensado para equipos Windows donde no hay Docker disponible; para el
    flujo con contenedores usa scripts/dev.ps1 o make demo.

.EXAMPLE
    .\scripts\dev-local.ps1            Arranca backend y frontend y abre la app
    .\scripts\dev-local.ps1 status     Estado de los servicios locales
    .\scripts\dev-local.ps1 logs frontend
    .\scripts\dev-local.ps1 stop       Detiene los servicios
#>
[CmdletBinding()]
param(
  [ValidateSet('start', 'help', 'backend', 'frontend', 'status', 'logs', 'api', 'plantilla', 'import', 'seed', 'stop', 'restart', 'reset')]
  [string]$Tarea = 'start',

  [ValidateSet('backend', 'frontend')]
  [string]$Servicio
)

$ErrorActionPreference = 'Stop'

$Raiz        = Split-Path -Parent $PSScriptRoot
$DirBack     = Join-Path $Raiz 'backend'
$DirFront    = Join-Path $Raiz 'frontend'
$DirRun      = Join-Path $Raiz '.run'
# Las comprobaciones usan 127.0.0.1: en Windows "localhost" se resuelve primero
# como IPv6 (::1) y los servidores de desarrollo solo escuchan en IPv4, por lo
# que la petición quedaría esperando hasta agotar el tiempo de espera.
$Api         = 'http://127.0.0.1:5000/api'
$UrlFront    = 'http://127.0.0.1:5173'
$UrlNavegador = 'http://localhost:5173'
$Plantilla   = Join-Path $DirBack 'plantilla_liga.xlsx'
$PuertoBack  = 5000
$PuertoFront = 5173

function Write-Ayuda {
  @'
ArbiLiga - arranque local sin Docker (backend Flask + frontend Vite)

  .\scripts\dev-local.ps1                 Arranca todo, carga la demo si está vacía y abre la app
  .\scripts\dev-local.ps1 backend         Arranca solo el backend en http://localhost:5000
  .\scripts\dev-local.ps1 frontend        Arranca solo el frontend en http://localhost:5173
  .\scripts\dev-local.ps1 status          Estado de los servicios locales
  .\scripts\dev-local.ps1 logs            Sigue los logs de ambos servicios
  .\scripts\dev-local.ps1 logs frontend   Logs de un servicio (backend o frontend)
  .\scripts\dev-local.ps1 api             Comprueba la API y lista los partidos
  .\scripts\dev-local.ps1 plantilla       Genera backend/plantilla_liga.xlsx
  .\scripts\dev-local.ps1 import          Sube la plantilla a la API
  .\scripts\dev-local.ps1 seed            Importa la plantilla solo si no hay partidos
  .\scripts\dev-local.ps1 stop            Detiene los servicios sin borrar datos
  .\scripts\dev-local.ps1 restart         Reinicia sin borrar datos
  .\scripts\dev-local.ps1 reset           Borra backend/dev.db y recrea la demo

La base de datos local es SQLite en backend/dev.db. Si existe un .env con el
DATABASE_URL de Docker (host "db") se ignora y se avisa por pantalla.
'@ | Write-Host
}

function Get-PidFile([string]$Nombre) { Join-Path $DirRun "$Nombre.pid" }

function Get-PythonExe {
  foreach ($ruta in @((Join-Path $Raiz '.venv\Scripts\python.exe'), (Join-Path $Raiz 'venv\Scripts\python.exe'))) {
    if (Test-Path $ruta) { return $ruta }
  }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if (-not $cmd) { throw 'No se encontró Python. Instálalo o crea el entorno virtual con: python -m venv .venv' }
  return $cmd.Source
}

function Assert-DependenciasPython([string]$Python) {
  & $Python -c "import flask, flask_sqlalchemy, flask_migrate, flask_cors, openpyxl, pandas" 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Faltan dependencias de Python en $Python.`nInstálalas con:  & '$Python' -m pip install -r backend\requirements.txt"
  }
}

function Get-DatabaseUrl {
  $sqlite = 'sqlite:///' + ((Join-Path $DirBack 'dev.db') -replace '\\', '/')
  $envFile = Join-Path $Raiz '.env'
  if (-not (Test-Path $envFile)) { return $sqlite }
  foreach ($linea in (Get-Content $envFile)) {
    if ($linea -match '^\s*DATABASE_URL\s*=\s*(.+?)\s*$') {
      $valor = $Matches[1]
      if ($valor -match '@db[:/]') {
        Write-Host 'Aviso: .env apunta a la base de datos de Docker (host "db"); se usará SQLite local.' -ForegroundColor Yellow
        return $sqlite
      }
      return $valor
    }
  }
  return $sqlite
}

function Get-PortOwner([int]$Puerto) {
  try {
    $c = Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { return [int]$c.OwningProcess }
  } catch { }
  return $null
}

function Test-ServicioActivo([string]$Nombre) {
  $f = Get-PidFile $Nombre
  if (-not (Test-Path $f)) { return $false }
  $procId = 0
  [void][int]::TryParse(((Get-Content $f -ErrorAction SilentlyContinue) | Select-Object -First 1), [ref]$procId)
  if ($procId -le 0) { return $false }
  return [bool](Get-Process -Id $procId -ErrorAction SilentlyContinue)
}

function Start-Backend {
  if (Test-ServicioActivo 'backend') { Write-Host 'El backend ya está en ejecución.'; return }
  $ocupado = Get-PortOwner $PuertoBack
  if ($ocupado) { throw "El puerto $PuertoBack ya está ocupado por el proceso $ocupado. Deténlo antes de continuar." }

  $py = Get-PythonExe
  Assert-DependenciasPython $py
  New-Item -ItemType Directory -Force -Path $DirRun | Out-Null

  $env:PYTHONPATH   = $DirBack
  $env:FLASK_APP    = 'app'
  $env:DATABASE_URL = Get-DatabaseUrl

  $proc = Start-Process -FilePath $py `
    -ArgumentList @('-m', 'flask', 'run', "--port=$PuertoBack") `
    -WorkingDirectory $DirBack `
    -RedirectStandardOutput (Join-Path $DirRun 'backend.out.log') `
    -RedirectStandardError (Join-Path $DirRun 'backend.err.log') `
    -WindowStyle Hidden -PassThru
  $proc.Id | Set-Content (Get-PidFile 'backend')
  Write-Host "Backend iniciado (PID $($proc.Id)) en http://localhost:$PuertoBack"
}

function Wait-Backend {
  for ($i = 0; $i -lt 40; $i++) {
    try { if ((Invoke-RestMethod "$Api/health" -TimeoutSec 2).status -eq 'ok') { return } } catch { }
    if (-not (Test-ServicioActivo 'backend')) {
      throw "El backend terminó durante el arranque. Revisa los logs con: .\scripts\dev-local.ps1 logs backend"
    }
    Start-Sleep -Milliseconds 750
  }
  throw 'La API no respondió a tiempo.'
}

function Start-Frontend {
  if (Test-ServicioActivo 'frontend') { Write-Host 'El frontend ya está en ejecución.'; return }
  $ocupado = Get-PortOwner $PuertoFront
  if ($ocupado) { throw "El puerto $PuertoFront ya está ocupado por el proceso $ocupado. Deténlo antes de continuar." }

  if (-not (Test-Path (Join-Path $DirFront 'node_modules'))) {
    Write-Host 'Instalando dependencias del frontend (npm install)...'
    Push-Location $DirFront
    try { & cmd.exe /c 'npm install' } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Falló npm install en frontend.' }
  }

  New-Item -ItemType Directory -Force -Path $DirRun | Out-Null
  $proc = Start-Process -FilePath 'cmd.exe' `
    -ArgumentList @('/c', 'npm run dev') `
    -WorkingDirectory $DirFront `
    -RedirectStandardOutput (Join-Path $DirRun 'frontend.out.log') `
    -RedirectStandardError (Join-Path $DirRun 'frontend.err.log') `
    -WindowStyle Hidden -PassThru
  $proc.Id | Set-Content (Get-PidFile 'frontend')
  Write-Host "Frontend iniciado (PID $($proc.Id)) en $UrlNavegador"
}

function Wait-Frontend {
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $r = Invoke-WebRequest $UrlFront -TimeoutSec 3 -UseBasicParsing
      if ($r.StatusCode -eq 200) { return }
    } catch { }
    if (-not (Test-ServicioActivo 'frontend')) {
      throw "El frontend terminó durante el arranque. Revisa los logs con: .\scripts\dev-local.ps1 logs frontend"
    }
    Start-Sleep -Milliseconds 750
  }
  throw 'El frontend no respondió a tiempo.'
}

function Stop-Servicios {
  foreach ($nombre in @('backend', 'frontend')) {
    $f = Get-PidFile $nombre
    if (-not (Test-Path $f)) { continue }
    $procId = 0
    [void][int]::TryParse(((Get-Content $f | Select-Object -First 1)), [ref]$procId)
    if ($procId -gt 0 -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
      & taskkill.exe /PID $procId /T /F *> $null
      Write-Host "$nombre detenido (PID $procId)."
    }
    Remove-Item $f -Force -ErrorAction SilentlyContinue
  }
  foreach ($par in @(@('backend', $PuertoBack), @('frontend', $PuertoFront))) {
    $owner = Get-PortOwner $par[1]
    if ($owner) { Write-Host "Aviso: el puerto $($par[1]) sigue ocupado por el proceso $owner." -ForegroundColor Yellow }
  }
}

function Invoke-Plantilla {
  $py = Get-PythonExe
  & $py (Join-Path $DirBack 'scripts\generar_plantilla.py') $Plantilla
  if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar la plantilla Excel.' }
  Write-Host "Plantilla generada en $Plantilla"
}

function Invoke-Import {
  Wait-Backend
  if (-not (Test-Path $Plantilla)) { Invoke-Plantilla }
  & curl.exe -fsS -X POST -F "file=@$Plantilla" "$Api/upload-excel"
  if ($LASTEXITCODE -ne 0) { throw 'No se pudo importar la plantilla.' }
  Write-Host
}

function Invoke-Seed {
  Wait-Backend
  $respuestaPartidos = Invoke-RestMethod "$Api/partidos" -TimeoutSec 10
  $partidos = @($respuestaPartidos)
  if ($partidos.Count -eq 0) { Invoke-Import } else { Write-Host "Ya existen $($partidos.Count) partido(s); se omite la importación." }
}

function Get-Estatus {
  foreach ($par in @(@('backend', $PuertoBack), @('frontend', $PuertoFront))) {
    $nombre = $par[0]
    $activo = Test-ServicioActivo $nombre
    $owner = Get-PortOwner $par[1]
    $detalle = if ($activo) { "activo (PID $(Get-Content (Get-PidFile $nombre) | Select-Object -First 1))" }
      elseif ($owner) { "ocupado por otro proceso (PID $owner)" }
      else { 'detenido' }
    Write-Host ("{0,-9} puerto {1,-5} {2}" -f $nombre, $par[1], $detalle)
  }
  $db = Join-Path $DirBack 'dev.db'
  if (Test-Path $db) {
    Write-Host ("base datos  {0}  ({1:N0} KB)" -f $db, ((Get-Item $db).Length / 1KB))
  } else {
    Write-Host 'base datos  sin crear (se genera al arrancar el backend)'
  }
}

function Show-Logs([string]$Nombre) {
  $archivos = @((Join-Path $DirRun "$Nombre.out.log"), (Join-Path $DirRun "$Nombre.err.log")) | Where-Object { Test-Path $_ }
  if (-not $archivos) { throw "No hay logs de $Nombre. Arranca primero con: .\scripts\dev-local.ps1 start" }
  Get-Content -Path $archivos -Wait -Tail 40
}

function Show-LogsTodos {
  $archivos = @(Get-ChildItem (Join-Path $DirRun '*.log') -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
  if (-not $archivos) { throw 'No hay logs todavía. Arranca primero con: .\scripts\dev-local.ps1 start' }
  Get-Content -Path $archivos -Wait -Tail 30
}

function Invoke-Start([bool]$AbrirNavegador) {
  Start-Backend
  Wait-Backend
  Start-Frontend
  Wait-Frontend
  Invoke-Seed
  if ($AbrirNavegador) { Start-Process $UrlNavegador }
}

Push-Location $Raiz
try {
  switch ($Tarea) {
    'help' { Write-Ayuda }
    'start' { Invoke-Start $true }
    'backend' { Start-Backend; Wait-Backend }
    'frontend' { Start-Frontend; Wait-Frontend }
    'status' { Get-Estatus }
    'logs' { if ($Servicio) { Show-Logs $Servicio } else { Show-LogsTodos } }
    'api' {
      Wait-Backend
      Invoke-RestMethod "$Api/health" -TimeoutSec 10 | ConvertTo-Json -Compress
      $respuestaPartidos = Invoke-RestMethod "$Api/partidos" -TimeoutSec 10
      $partidos = @($respuestaPartidos)
      Write-Host "Partidos registrados: $($partidos.Count)"
    }
    'plantilla' { Invoke-Plantilla }
    'import' { Invoke-Import }
    'seed' { Invoke-Seed }
    'stop' { Stop-Servicios }
    'restart' { Stop-Servicios; Invoke-Start $false }
    'reset' {
      Stop-Servicios
      $db = Join-Path $DirBack 'dev.db'
      if (Test-Path $db) { Remove-Item $db -Force; Write-Host 'Base de datos local eliminada.' }
      Invoke-Start $true
    }
  }
} finally { Pop-Location }
