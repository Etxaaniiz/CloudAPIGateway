# Wrapper en repo root para desplegar la infra (llama infra\deploy_boto3.py)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $scriptDir

Write-Host "Lanzando despliegue con boto3..."

# Cargar variables de .env
$EnvFile = Join-Path $scriptDir '.env'
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*#') { return }
        if ($_ -match '^\s*$') { return }
        $parts = $_ -split '='
        $name = $parts[0].Trim()
        $value = ($parts[1..($parts.Length-1)] -join '=').Trim()
        Write-Host "Setting env $name=$value"
        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# Ejecutar script Python
python .\infra\deploy_boto3.py

Pop-Location
