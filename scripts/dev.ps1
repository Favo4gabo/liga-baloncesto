[CmdletBinding()]
param(
  [ValidateSet('demo', 'help', 'up', 'status', 'logs', 'plantilla', 'import', 'seed', 'api', 'open', 'stop', 'restart', 'reset')]
  [string]$Tarea = 'demo',
  [ValidateSet('backend', 'frontend', 'db')]
  [string]$Servicio
)

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $PSScriptRoot
$Api = 'http://localhost:5000/api'
$Plantilla = Join-Path $Raiz 'backend/plantilla_liga.xlsx'

function Write-Ayuda {
  @'
ArbiLiga - arranque local

  .\scripts\dev.ps1                 Arranca, carga la demo si está vacía y abre la aplicación
  .\scripts\dev.ps1 up              Construye, levanta y espera los servicios
  .\scripts\dev.ps1 logs backend    Logs de backend (también frontend o db)
  .\scripts\dev.ps1 plantilla       Genera el Excel de muestra
  .\scripts\dev.ps1 import          Sube el Excel de muestra a la API
  .\scripts\dev.ps1 seed            Importa solo si no existen partidos
  .\scripts\dev.ps1 status          Estado de los contenedores
  .\scripts\dev.ps1 api             Comprueba API y lista partidos
  .\scripts\dev.ps1 stop            Detiene sin borrar datos
  .\scripts\dev.ps1 reset           Borra datos y recrea la demo
'@ | Write-Host
}

function Assert-Docker {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker no está disponible en PATH. Instala y abre Docker Desktop antes de continuar.'
  }
  docker info *> $null
  if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop no está listo. Ábrelo y espera a que el motor inicie.' }
}

function Invoke-Compose([string[]]$Argumentos) {
  & docker compose @Argumentos
  if ($LASTEXITCODE -ne 0) { throw "Falló: docker compose $($Argumentos -join ' ')" }
}

function Initialize-Environment {
  $envFile = Join-Path $Raiz '.env'
  if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $Raiz '.env.example') $envFile; Write-Host 'Se creó .env desde .env.example.' }
}

function Wait-Services {
  for ($i = 0; $i -lt 46; $i++) {
    $estado = (& docker compose ps db 2>$null | Out-String)
    if ($estado -match 'healthy') { break }
    Start-Sleep -Seconds 2
    if ($i -eq 45) { throw 'La base de datos no quedó saludable a tiempo.' }
  }
  for ($i = 0; $i -lt 46; $i++) {
    try { if ((Invoke-RestMethod "$Api/health" -TimeoutSec 3).status -eq 'ok') { Write-Host 'Servicios listos.'; return } } catch { }
    Start-Sleep -Seconds 2
  }
  throw 'La API no respondió a tiempo.'
}

function Invoke-Up { Assert-Docker; Initialize-Environment; Invoke-Compose @('up', '--build', '-d'); Wait-Services }
function Invoke-Plantilla { Invoke-Compose @('exec', '-T', 'backend', 'python', 'scripts/generar_plantilla.py', '/app/plantilla_liga.xlsx') }
function Invoke-Import { if (-not (Test-Path $Plantilla)) { Invoke-Plantilla }; & curl.exe -fsS -X POST -F "file=@$Plantilla" "$Api/upload-excel"; if ($LASTEXITCODE -ne 0) { throw 'No se pudo importar la plantilla.' }; Write-Host }
function Invoke-Seed { $partidos = @(Invoke-RestMethod "$Api/partidos"); if ($partidos.Count -eq 0) { Invoke-Import } else { Write-Host "Ya existen $($partidos.Count) partido(s); se omite la importación para evitar duplicados." } }

Push-Location $Raiz
try {
  switch ($Tarea) {
    'help' { Write-Ayuda }
    'up' { Invoke-Up }
    'status' { Assert-Docker; Invoke-Compose @('ps') }
    'logs' { Assert-Docker; if ($Servicio) { & docker compose logs -f $Servicio } else { & docker compose logs -f } }
    'plantilla' { Assert-Docker; Invoke-Plantilla }
    'import' { Assert-Docker; Invoke-Import }
    'seed' { Assert-Docker; Invoke-Seed }
    'api' { Invoke-RestMethod "$Api/health" | ConvertTo-Json; Invoke-RestMethod "$Api/partidos" | ConvertTo-Json -Depth 8 }
    'open' { Start-Process 'http://localhost:5173' }
    'stop' { Assert-Docker; Invoke-Compose @('down') }
    'restart' { Assert-Docker; Invoke-Compose @('down'); Invoke-Up }
    'reset' { Assert-Docker; if ((Read-Host 'Esto borrará la base de datos local. ¿Continuar? [s/N]') -notmatch '^[sS]$') { return }; Invoke-Compose @('down', '-v'); Invoke-Up; Invoke-Seed; Start-Process 'http://localhost:5173' }
    'demo' { Invoke-Up; Invoke-Seed; Start-Process 'http://localhost:5173' }
  }
} finally { Pop-Location }
