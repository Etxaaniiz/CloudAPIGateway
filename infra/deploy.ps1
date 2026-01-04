# Deploy script: lee .env en el repo root, crea/activa venv en infra y despliega CDK
$Root = Split-Path -Parent $MyInvocation.MyCommand.Definition
# Ajustar si se invoca desde otro directorio
Push-Location $Root

$RepoRoot = Join-Path $Root '..'
$EnvFile = Join-Path $RepoRoot '.env'

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*#') { return }
        if ($_ -match '^\s*$') { return }
        $parts = $_ -split '='
        $name = $parts[0].Trim()
        $value = ($parts[1..($parts.Length-1)] -join '=').Trim()
        Write-Host "Setting env $name=$value"
        $env:$name = $value
    }
} else {
    Write-Host "Aviso: no se encontró .env en el repo root. Usando variables de entorno actuales."
}

# Crear venv si no existe
if (-not (Test-Path '.venv')) {
    Write-Host "Creando virtualenv..."
    python -m venv .venv
}

Write-Host "Activando virtualenv..."
.\.venv\Scripts\Activate.ps1

Write-Host "Instalando dependencias de infra (puede tardar)..."
pip install -r requirements.txt

Write-Host "Ejecutando cdk deploy..."
cd ..\infra
cdk deploy --require-approval never

Pop-Location
