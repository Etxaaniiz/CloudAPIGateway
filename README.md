# Cloud Computing Dashboard — Práctica Serverless AWS

Arquitectura serverless que ingiere archivos CSV desde Amazon S3, los procesa con Lambda, almacena datos en DynamoDB y expone una UI web simple que consulta una API.

##  Buenos aspectos de la solución

### 1. **Despliegue completamente automatizado**
- **Un solo comando** (`.\deploy.ps1`) despliega toda la infraestructura: 8 recursos AWS sin intervención manual
- **Idempotencia garantizada**: re-ejecutar el script no causa errores, actualiza recursos existentes
- **Outputs automáticos**: genera `outputs.json` con URLs y ARNs para verificación inmediata
- Eliminación del 100% de clics en consola AWS (solo para verificación opcional)

### 2. **Arquitectura event-driven robusta**
- **Procesamiento asíncrono**: S3 → Lambda → DynamoDB sin bloqueos ni polling
- **Notificaciones en tiempo real**: DynamoDB Streams detectan cambios y disparan alertas automáticamente
- **Escalabilidad automática**: Lambda y DynamoDB on-demand escalan sin configuración
- **Desacoplamiento total**: cada componente es independiente y reemplazable

### 3. **Gestión de errores y resiliencia**
- **Retry automático**: Lambda tiene retry incorporado con dead-letter queue opcional
- **Conflict handling**: manejo de `ResourceConflictException` en deploy_boto3.py
- **Validación de permisos**: verifica LabRole antes de crear recursos
- **Logging completo**: CloudWatch captura todos los eventos para troubleshooting
- **Serialización robusta**: DecimalEncoder maneja correctamente tipos de DynamoDB

### 4. **Seguridad de mínimo privilegio**
- **IAM granular**: cada Lambda tiene solo los permisos necesarios (GetObject, PutItem, Scan, Publish)
- **Sin credenciales hardcodeadas**: usa roles IAM nativos de AWS
- **CORS restrictivo**: configurable por dominio (actualmente `*` para desarrollo)
- **Compatibilidad AWS Academy**: funciona con cuentas limitadas sin permisos IAM de administración

### 5. **Developer Experience (DX)**
- **Configuración centralizada**: archivo `.env` para todos los parámetros
- **Teardown seguro**: confirmación manual antes de eliminar recursos
- **Logs legibles**: emojis UTF-8 y colores en terminal para seguimiento visual
- **Documentación completa**: README con troubleshooting y ejemplos reales
- **Testing facilitado**: estructura de datos simple (CSV de 3 columnas)

### 6. **Costos optimizados**
- **Serverless puro**: pago por uso, cero cuando no hay tráfico
- **DynamoDB on-demand**: sin capacidad provisionada innecesaria
- **S3 Lifecycle policies** (opcional): eliminación automática de CSVs antiguos
- **HTTP API v2**: más barato que REST API (70% menos costoso en API Gateway)
- **Sin NAT Gateway**: Lambda accede directamente a servicios AWS sin VPC

### 7. **Mantenibilidad**
- **Código Python limpio**: funciones pequeñas con responsabilidad única
- **Separación infra/app**: `/infra/` (boto3) vs `/lambdas/` (handlers)
- **Versionado con Git**: .gitignore excluye archivos temporales
- **Extensible**: añadir nuevas Lambdas solo requiere agregar función en deploy_boto3.py
- **Sin dependencias complejas**: solo boto3 (incluido en Lambda runtime)

### 8. **Producción ready**
- **API Gateway con rutas RESTful**: `/items` y `/items/{store}`
- **Payload Format v2.0**: mejor rendimiento y menor latencia
- **Batch operations**: `batch_writer` en DynamoDB para inserciones eficientes
- **CORS habilitado**: web puede consumir API desde cualquier origen
- **Static hosting**: S3 website con failover a CloudFront (opcional)

## Estructura del repositorio

```
.
├── infra/
│   ├── deploy_boto3.py          # Script principal de despliegue (boto3)
│   ├── cleanup_boto3.py         # Script de limpieza de recursos
│   ├── deploy.ps1              # Despliegue desde PowerShell
│   ├── teardown.ps1            # Limpieza desde PowerShell
│   └── requirements.txt         # Dependencias Python
├── lambdas/
│   ├── load_inventory/app.py   # Lambda A: procesa CSV → DynamoDB
│   ├── get_inventory_api/app.py # Lambda B: API HTTP para consultar datos
│   ├── notify_low_stock/app.py # Lambda C: DynamoDB Streams → SNS
│   └── requirements.txt         # Dependencias de Lambdas
├── web/
│   └── index.html              # Sitio estático que consulta la API
├── capturas_evidencias/        # Evidencias de ejecución
│   ├── EVIDENCIAS.md           # Documento con capturas y pruebas
│   ├── WebItemsCargados.png    # Captura del dashboard web
│   ├── respuestaAPI.png        # Respuesta JSON del API
│   └── MailsBajoStock.png      # Email de notificación SNS
├── .env.sample                 # Plantilla de configuración
└── README.md                   # Este archivo
```

## Requisitos previos

- **Python 3.11+** (para AWS Lambda runtime)
- **AWS CLI v2** configurado con credenciales válidas
- **PowerShell 5.1+** (Windows) o equivalente en Linux/Mac
- Acceso a **AWS Academy** o cuenta AWS con permisos para crear:
  - S3 buckets
  - DynamoDB tables
  - Lambda functions
  - API Gateway HTTP API
  - IAM roles/policies
  - SNS topics

## Despliegue (una sola instrucción)

### Paso 1: Configurar variables de entorno

```bash
cp .env.sample .env
# Edita .env con tus valores (región, email, suffix)
```

### Paso 2: Desplegar infraestructura y Lambdas

```powershell
.\deploy.ps1
```

Este script crea automáticamente:
- ✅ S3 buckets (ingesta + web)
- ✅ DynamoDB table con Streams
- ✅ 3 Lambda functions empaquetadas
- ✅ API Gateway HTTP API v2
- ✅ SNS topic para notificaciones
- ✅ Roles IAM de mínimo privilegio
- ✅ Sitio web estático alojado en S3
- ✅ Triggers entre servicios

El script genera `outputs.json` con URLs de acceso.

## Verificación

Una vez desplegado:

1. **API Gateway** - Consulta el inventario:
   ```bash
   curl https://<api-id>.execute-api.us-east-1.amazonaws.com/items
   curl https://<api-id>.execute-api.us-east-1.amazonaws.com/items/Berlin
   ```

2. **Web dashboard**:
   - Abre: `http://inventory-web-<suffix>.s3-website-us-east-1.amazonaws.com`
   - Sube un CSV a `s3://inventory-uploads-<suffix>/`
   - Los datos aparecerán en la tabla

3. **SNS notifications** - Confirma email y carga CSV con items con Count ≤ 5

## Limpieza (eliminar todos los recursos)

```powershell
.\infra\teardown.ps1
```

Confirma escribiendo `SI` cuando se pida. Esto elimina:
- S3 buckets y su contenido
- DynamoDB table
- Lambda functions
- API Gateway
- SNS topic
- IAM policies

## Estructura de datos

**DynamoDB Table: Inventory**
```
{
  "Store": "Berlin",           # Partition Key (S)
  "Item": "Laptop",            # Sort Key (S)
  "Count": 3                   # Attribute (N)
}
```

**CSV esperado:**
```csv
Store,Item,Count
Berlin,Laptop,3
Madrid,Mouse,15
```

## Detalles técnicos

- **Lambda runtime:** Python 3.11
- **API Gateway:** HTTP API v2 (no REST API)
- **DynamoDB:** On-demand pricing
- **Streams:** Habilitados para notificaciones automáticas
- **CORS:** Configurado en API Gateway para acceso desde web

## Troubleshooting

- **Permisos denegados:** Verifica que tus credenciales AWS tienen permisos para crear recursos
- **API Gateway error 500:** Ejecuta `.\deploy.ps1` de nuevo (es idempotente)
- **SNS sin emails:** Confirma suscripción en tu inbox

## Contacto

aimar.etxaniz@opendeusto.es
