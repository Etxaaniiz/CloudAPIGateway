Infra (guía rápida)

Decisión recomendada: usar AWS CDK (Python) porque facilita:
- Definir infra como código (idempotente)
- Empaquetar y desplegar Lambdas automáticamente

Requisitos locales (Windows PowerShell):
- Node.js + npm: https://nodejs.org/
- AWS CDK: `npm install -g aws-cdk`
- Python 3.11
- Virtualenv (opcional): `python -m venv .venv`
- AWS CLI y credenciales: `aws configure` (introduce el Access Key/Secret y región)

Pasos básicos (CDK):
1. Ir a la carpeta `infra`.
2. Crear e activar virtualenv (opcional):
   pwsh> python -m venv .venv; .\\.venv\\Scripts\\Activate.ps1
3. Instalar dependencias: `pip install -r requirements.txt` (cuando exista)
4. Inicializar CDK bootstrap (si no está hecho): `cdk bootstrap aws://ACCOUNT_ID/REGION`
5. Desplegar: `cdk deploy` (o el comando que incluiremos en README/Makefile)

Si prefieres scripts Python puros con boto3, también podemos implementarlo; dime y lo cambio.
