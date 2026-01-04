# Cloud API Gateway — Práctica Cloud Computing (AWS)

Repositorio base para la práctica: desplegar una arquitectura serverless que ingiere CSV desde S3, lo guarda en DynamoDB y expone una web estática que consulta una API.

Estructura inicial:

- /infra/  -> scripts e instrucciones para crear recursos (CDK o boto3)
- /lambdas/load_inventory/ -> Lambda que procesa CSV y escribe en DynamoDB
- /lambdas/get_inventory_api/ -> Lambda que expone datos vía API Gateway
- /lambdas/notify_low_stock/ -> Lambda que recibe Streams y publica en SNS
- /web/ -> sitio estático (index.html) que consume la API
- .env.sample -> variables necesarias para despliegue

Requisitos mínimos (en tu máquina):
- Python 3.11
- Node.js + npm (para AWS CDK)
- AWS CLI configurado con un perfil con permisos para crear recursos (execute `aws configure`)
- AWS CDK (si vamos a usar CDK): `npm install -g aws-cdk`

Siguiente paso (instrucciones rápidas):

1. Clona el repo (ya estás en el workspace).
2. Copia `.env.sample` a `.env` y completa REGION, SUFFIX y EMAIL si quieres cambiarlos.
3. Para desplegar todo (infra + Lambdas + hosting web) ejecuta desde PowerShell en la raíz del repo:

```powershell
.\deploy.ps1
```

4. Para eliminar todos los recursos creados ejecuta:

```powershell
.\infra\teardown.ps1
```

Si prefieres desplegar manualmente desde la carpeta `infra`, sigue las instrucciones en `/infra/README.md`.

Notas:
- Actualmente este repo contiene solo el scaffold y handlers básicos. La parte de infra (CDK/python) se implementará después del scaffold y será idempotente.

Contacto: aimar.etxaniz@opendeusto.es
