#!/usr/bin/env python3
"""
Script de despliegue usando boto3 para entornos con restricciones IAM.
Usa el LabRole existente en lugar de crear roles nuevos.
"""
import boto3
import json
import os
import zipfile
import io
import time
from pathlib import Path

# Configuración
REGION = os.environ.get('REGION', 'us-east-1')
SUFFIX = os.environ.get('SUFFIX', 'aimar')
EMAIL = os.environ.get('EMAIL', 'aimar.etxaniz@opendeusto.es')
TABLE_NAME = os.environ.get('DDB_TABLE', 'Inventory')

# Nombres de recursos
UPLOADS_BUCKET = f'inventory-uploads-{SUFFIX}'
WEB_BUCKET = f'inventory-web-{SUFFIX}'
SNS_TOPIC_NAME = f'NoStockTopic-{SUFFIX}'
API_NAME = f'InventoryHttpApi-{SUFFIX}'

# Clientes AWS
s3 = boto3.client('s3', region_name=REGION)
dynamodb = boto3.client('dynamodb', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)
apigateway = boto3.client('apigatewayv2', region_name=REGION)
sns_client = boto3.client('sns', region_name=REGION)
iam = boto3.client('iam', region_name=REGION)
sts = boto3.client('sts', region_name=REGION)


def get_lab_role_arn():
    """Obtiene el ARN del LabRole existente."""
    try:
        response = iam.get_role(RoleName='LabRole')
        role_arn = response['Role']['Arn']
        print(f"✅ Usando LabRole existente: {role_arn}")
        return role_arn
    except Exception as e:
        print(f"❌ Error: {e}")
        raise Exception("No se encontró LabRole. Asegúrate de estar en una cuenta AWS con LabRole disponible")


def create_s3_buckets():
    """Crea los buckets S3 necesarios."""
    print("\n📦 Creando buckets S3...")
    
    # Bucket de uploads
    try:
        if REGION == 'us-east-1':
            s3.create_bucket(Bucket=UPLOADS_BUCKET)
        else:
            s3.create_bucket(
                Bucket=UPLOADS_BUCKET,
                CreateBucketConfiguration={'LocationConstraint': REGION}
            )
        print(f"✅ Bucket creado: {UPLOADS_BUCKET}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"ℹ️  Bucket ya existe: {UPLOADS_BUCKET}")
    
    # Bucket web con configuración estática
    try:
        if REGION == 'us-east-1':
            s3.create_bucket(Bucket=WEB_BUCKET)
        else:
            s3.create_bucket(
                Bucket=WEB_BUCKET,
                CreateBucketConfiguration={'LocationConstraint': REGION}
            )
        
        # Configurar para hosting web estático
        s3.put_bucket_website(
            Bucket=WEB_BUCKET,
            WebsiteConfiguration={
                'IndexDocument': {'Suffix': 'index.html'}
            }
        )
        
        # Permitir acceso público
        s3.delete_public_access_block(Bucket=WEB_BUCKET)
        
        # Política de acceso público
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{WEB_BUCKET}/*"
            }]
        }
        s3.put_bucket_policy(Bucket=WEB_BUCKET, Policy=json.dumps(bucket_policy))
        
        print(f"✅ Bucket web creado: {WEB_BUCKET}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"ℹ️  Bucket web ya existe: {WEB_BUCKET}")


def create_dynamodb_table():
    """Crea la tabla DynamoDB."""
    print("\n🗄️  Creando tabla DynamoDB...")
    
    try:
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'Store', 'KeyType': 'HASH'},
                {'AttributeName': 'Item', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'Store', 'AttributeType': 'S'},
                {'AttributeName': 'Item', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST',
            StreamSpecification={
                'StreamEnabled': True,
                'StreamViewType': 'NEW_IMAGE'
            }
        )
        
        # Esperar a que la tabla esté activa
        print("⏳ Esperando a que la tabla esté activa...")
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=TABLE_NAME)
        
        print(f"✅ Tabla creada: {TABLE_NAME}")
    except dynamodb.exceptions.ResourceInUseException:
        print(f"ℹ️  Tabla ya existe: {TABLE_NAME}")


def create_lambda_zip(lambda_name):
    """Crea un ZIP con el código de la Lambda y dependencias."""
    project_root = Path(__file__).parent.parent
    lambda_dir = project_root / 'lambdas' / lambda_name
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Agregar app.py
        app_file = lambda_dir / 'app.py'
        if app_file.exists():
            zip_file.write(app_file, 'app.py')
        
        # Nota: boto3 ya viene en Lambda runtime, pero para local necesitaría incluirlo
        # Por ahora confiamos en que está disponible en el runtime
    
    zip_buffer.seek(0)
    return zip_buffer.read()


def create_lambda_functions(role_arn):
    """Crea las funciones Lambda."""
    print("\n⚡ Creando funciones Lambda...")
    
    # Obtener ARN del stream de DynamoDB
    table_info = dynamodb.describe_table(TableName=TABLE_NAME)
    stream_arn = table_info['Table'].get('LatestStreamArn')
    
    # SNS Topic ARN
    sns_topic_arn = create_sns_topic()
    
    lambdas = [
        {
            'name': f'load-inventory-{SUFFIX}',
            'handler': 'app.lambda_handler',
            'code': create_lambda_zip('load_inventory'),
            'env': {'DDB_TABLE': TABLE_NAME}
        },
        {
            'name': f'get-inventory-api-{SUFFIX}',
            'handler': 'app.lambda_handler',
            'code': create_lambda_zip('get_inventory_api'),
            'env': {'DDB_TABLE': TABLE_NAME}
        },
        {
            'name': f'notify-low-stock-{SUFFIX}',
            'handler': 'app.lambda_handler',
            'code': create_lambda_zip('notify_low_stock'),
            'env': {'SNS_TOPIC_ARN': sns_topic_arn, 'LOW_STOCK_THRESHOLD': '5'}
        }
    ]
    
    lambda_arns = {}
    
    for lambda_config in lambdas:
        try:
            response = lambda_client.create_function(
                FunctionName=lambda_config['name'],
                Runtime='python3.11',
                Role=role_arn,
                Handler=lambda_config['handler'],
                Code={'ZipFile': lambda_config['code']},
                Environment={'Variables': lambda_config['env']},
                Timeout=30
            )
            lambda_arns[lambda_config['name']] = response['FunctionArn']
            print(f"✅ Lambda creada: {lambda_config['name']}")
        except lambda_client.exceptions.ResourceConflictException:
            # Actualizar si ya existe - esperar si hay update en progreso
            print(f"ℹ️  Lambda ya existe, esperando y actualizando: {lambda_config['name']}")
            
            # Esperar a que termine cualquier update en progreso
            max_retries = 10
            for i in range(max_retries):
                try:
                    lambda_client.update_function_code(
                        FunctionName=lambda_config['name'],
                        ZipFile=lambda_config['code']
                    )
                    break
                except lambda_client.exceptions.ResourceConflictException:
                    if i < max_retries - 1:
                        print(f"   Esperando... ({i+1}/{max_retries})")
                        time.sleep(3)
                    else:
                        print(f"⚠️  No se pudo actualizar {lambda_config['name']}, usand la versión existente")
            
            # Esperar un poco más y actualizar la configuración
            time.sleep(2)
            for i in range(max_retries):
                try:
                    lambda_client.update_function_configuration(
                        FunctionName=lambda_config['name'],
                        Environment={'Variables': lambda_config['env']}
                    )
                    break
                except lambda_client.exceptions.ResourceConflictException:
                    if i < max_retries - 1:
                        time.sleep(3)
            
            response = lambda_client.get_function(FunctionName=lambda_config['name'])
            lambda_arns[lambda_config['name']] = response['Configuration']['FunctionArn']
            print(f"✅ Lambda actualizada: {lambda_config['name']}")
    
    # Configurar trigger S3 -> Lambda
    setup_s3_trigger(lambda_arns[f'load-inventory-{SUFFIX}'])
    
    # Configurar trigger DynamoDB Stream -> Lambda
    if stream_arn:
        setup_dynamodb_stream_trigger(lambda_arns[f'notify-low-stock-{SUFFIX}'], stream_arn)
    
    return lambda_arns


def setup_s3_trigger(lambda_arn):
    """Configura el trigger de S3 para la Lambda."""
    print("\n🔗 Configurando trigger S3 -> Lambda...")
    
    # Dar permiso a S3 para invocar la Lambda
    try:
        lambda_client.add_permission(
            FunctionName=lambda_arn,
            StatementId='s3-trigger-permission',
            Action='lambda:InvokeFunction',
            Principal='s3.amazonaws.com',
            SourceArn=f'arn:aws:s3:::{UPLOADS_BUCKET}'
        )
        # Esperar un momento para que el permiso se propague
        time.sleep(2)
    except lambda_client.exceptions.ResourceConflictException:
        pass  # El permiso ya existe
    
    # Configurar notificación S3
    try:
        s3.put_bucket_notification_configuration(
            Bucket=UPLOADS_BUCKET,
            NotificationConfiguration={
                'LambdaFunctionConfigurations': [{
                    'LambdaFunctionArn': lambda_arn,
                    'Events': ['s3:ObjectCreated:*']
                }]
            }
        )
        print("✅ Trigger S3 configurado")
    except Exception as e:
        print(f"⚠️  Error configurando trigger S3: {e}")
        print("ℹ️  Puedes configurarlo manualmente en la consola de AWS")


def setup_dynamodb_stream_trigger(lambda_arn, stream_arn):
    """Configura el trigger DynamoDB Stream -> Lambda."""
    print("\n🔗 Configurando trigger DynamoDB Stream -> Lambda...")
    
    try:
        lambda_client.create_event_source_mapping(
            EventSourceArn=stream_arn,
            FunctionName=lambda_arn,
            StartingPosition='LATEST',
            BatchSize=100
        )
        print("✅ Trigger DynamoDB Stream configurado")
    except lambda_client.exceptions.ResourceConflictException:
        print("ℹ️  Trigger DynamoDB Stream ya existe")


def create_sns_topic():
    """Crea el topic SNS y suscribe el email."""
    print("\n📧 Creando topic SNS...")
    
    try:
        response = sns_client.create_topic(Name=SNS_TOPIC_NAME)
        topic_arn = response['TopicArn']
        print(f"✅ Topic SNS creado: {SNS_TOPIC_NAME}")
        
        # Suscribir email
        if EMAIL:
            sns_client.subscribe(
                TopicArn=topic_arn,
                Protocol='email',
                Endpoint=EMAIL
            )
            print(f"📬 Suscripción de email enviada a: {EMAIL}")
            print("⚠️  IMPORTANTE: Revisa tu email y confirma la suscripción!")
        
        return topic_arn
    except Exception as e:
        # Puede que ya exista
        topics = sns_client.list_topics()
        for topic in topics['Topics']:
            if SNS_TOPIC_NAME in topic['TopicArn']:
                print(f"ℹ️  Topic SNS ya existe: {SNS_TOPIC_NAME}")
                return topic['TopicArn']
        raise e


def create_api_gateway(lambda_arn):
    """Crea el API Gateway HTTP."""
    print("\n🌐 Creando API Gateway...")
    
    lambda_name = lambda_arn.split(':')[-1]
    account_id = lambda_arn.split(':')[4]
    
    try:
        # Crear API
        api_response = apigateway.create_api(
            Name=API_NAME,
            ProtocolType='HTTP',
            CorsConfiguration={
                'AllowOrigins': ['*'],
                'AllowMethods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
                'AllowHeaders': ['*'],
                'ExposeHeaders': ['*'],
                'MaxAge': 300
            }
        )
        api_id = api_response['ApiId']
        api_endpoint = api_response['ApiEndpoint']
        print(f"✅ API creada: {API_NAME} ({api_id})")
        
    except Exception as e:
        # Buscar si ya existe
        apis = apigateway.get_apis()
        for api in apis['Items']:
            if api['Name'] == API_NAME:
                api_id = api['ApiId']
                api_endpoint = api['ApiEndpoint']
                print(f"ℹ️  API ya existe: {API_NAME}")
                break
        else:
            raise e
    
    # Crear integración Lambda
    try:
        integration_response = apigateway.create_integration(
            ApiId=api_id,
            IntegrationType='AWS_PROXY',
            IntegrationUri=lambda_arn,
            PayloadFormatVersion='2.0'
        )
        integration_id = integration_response['IntegrationId']
        print(f"✅ Integración Lambda creada")
    except Exception as e:
        integrations = apigateway.get_integrations(ApiId=api_id)
        if integrations['Items']:
            integration_id = integrations['Items'][0]['IntegrationId']
            print(f"ℹ️  Integración ya existe")
        else:
            raise e
    
    # Crear rutas
    routes = ['/items', '/items/{store}']
    for route in routes:
        try:
            apigateway.create_route(
                ApiId=api_id,
                RouteKey=f'GET {route}',
                Target=f'integrations/{integration_id}'
            )
            print(f"✅ Ruta creada: GET {route}")
        except apigateway.exceptions.ConflictException:
            print(f"ℹ️  Ruta ya existe: GET {route}")
        except Exception as e:
            print(f"⚠️  Error creando ruta {route}: {e}")
    
    # Crear stage $default
    try:
        apigateway.create_stage(
            ApiId=api_id,
            StageName='$default',
            AutoDeploy=True
        )
        print(f"✅ Stage $default creado")
    except apigateway.exceptions.ConflictException:
        print(f"ℹ️  Stage $default ya existe")
    
    # Dar permiso a API Gateway para invocar Lambda (importante!)
    lambda_source_arn = f'arn:aws:execute-api:{REGION}:{account_id}:{api_id}/*'
    try:
        lambda_client.add_permission(
            FunctionName=lambda_name,
            StatementId=f'apigateway-{api_id}',
            Action='lambda:InvokeFunction',
            Principal='apigateway.amazonaws.com',
            SourceArn=lambda_source_arn
        )
        print(f"✅ Permiso de invocación agregado a Lambda")
    except lambda_client.exceptions.ResourceConflictException:
        print(f"ℹ️  Permiso ya existe")
    except Exception as e:
        print(f"⚠️  Error agregando permiso: {e}")
    
    print(f"📍 API URL: {api_endpoint}")
    return api_endpoint


def upload_website(api_url):
    """Sube el sitio web a S3 y actualiza la URL del API."""
    print("\n🌍 Subiendo sitio web...")
    
    project_root = Path(__file__).parent.parent
    index_file = project_root / 'web' / 'index.html'
    
    # Leer y modificar index.html con la URL real del API
    with open(index_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Reemplazar la URL del API
    content = content.replace(
        "const API_BASE = window.API_URL || 'https://{API_ID}.execute-api.REGION.amazonaws.com';",
        f"const API_BASE = '{api_url}';"
    )
    
    # Subir a S3
    s3.put_object(
        Bucket=WEB_BUCKET,
        Key='index.html',
        Body=content.encode('utf-8'),
        ContentType='text/html'
    )
    
    website_url = f'http://{WEB_BUCKET}.s3-website-{REGION}.amazonaws.com'
    print(f"✅ Sitio web desplegado")
    print(f"🌐 Website URL: {website_url}")
    
    return website_url


def main():
    """Función principal de despliegue."""
    print("=" * 60)
    print("🚀 DESPLIEGUE DE ARQUITECTURA SERVERLESS")
    print("=" * 60)
    print(f"Región: {REGION}")
    print(f"Sufijo: {SUFFIX}")
    print(f"Email: {EMAIL}")
    print("=" * 60)
    
    try:
        # Obtener rol IAM
        role_arn = get_lab_role_arn()
        print(f"✅ Rol IAM: {role_arn}")
        
        # Crear recursos
        create_s3_buckets()
        create_dynamodb_table()
        lambda_arns = create_lambda_functions(role_arn)
        
        # API Gateway
        api_lambda_arn = lambda_arns[f'get-inventory-api-{SUFFIX}']
        api_url = create_api_gateway(api_lambda_arn)
        
        # Subir web
        website_url = upload_website(api_url)
        
        print("\n" + "=" * 60)
        print("✅ DESPLIEGUE COMPLETADO")
        print("=" * 60)
        print(f"📍 API URL: {api_url}")
        print(f"🌐 Website URL: {website_url}")
        print(f"📦 Uploads Bucket: s3://{UPLOADS_BUCKET}")
        print(f"🗄️  DynamoDB Table: {TABLE_NAME}")
        print("=" * 60)
        print("\n⚠️  RECUERDA: Confirma la suscripción de email en tu bandeja de entrada!")
        
        # Guardar outputs
        outputs = {
            'api_url': api_url,
            'website_url': website_url,
            'uploads_bucket': UPLOADS_BUCKET,
            'table_name': TABLE_NAME,
            'region': REGION,
            'deployment_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'project': 'Cloud API Gateway - Serverless Inventory'
        }
        
        with open('outputs.json', 'w') as f:
            json.dump(outputs, f, indent=2)
        print("📄 Outputs guardados en: outputs.json")
        
    except Exception as e:
        print(f"\n❌ Error durante el despliegue: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
