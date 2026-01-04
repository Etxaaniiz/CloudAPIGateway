# Teardown script: ejecuta el script de limpieza boto3
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
        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
} else {
    Write-Host "Aviso: no se encontró .env en el repo root. Usando variables de entorno actuales."
}

Write-Host "Ejecutando limpieza de recursos..."
python cleanup_boto3.py

Pop-Location
