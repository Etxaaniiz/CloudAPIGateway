# Teardown script: carga .env y ejecuta cdk destroy
$Root = Split-Path -Parent $MyInvocation.MyCommand.Definition
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
        $env:$name = $value
    }
} else {
    Write-Host "Aviso: no se encontró .env en el repo root. Usando variables de entorno actuales."
}

if (-not (Test-Path '.venv')) {
    Write-Host "Virtualenv no encontrado. Creando uno temporal..."
    python -m venv .venv
}

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

Write-Host "Ejecutando cdk destroy (confirmaciones automáticas)..."
cd ..\infra
cdk destroy --force

Pop-Location
