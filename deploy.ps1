# Wrapper en repo root para desplegar la infra (llama infra\deploy.ps1)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $scriptDir

Write-Host "Lanzando infra\deploy.ps1"
& .\infra\deploy.ps1

Pop-Location
