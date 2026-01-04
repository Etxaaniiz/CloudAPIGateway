#!/usr/bin/env python3
"""
Script de limpieza para eliminar todos los recursos creados.
"""
import boto3
import json
import os
import time

# Configuración
REGION = os.environ.get('REGION', 'us-east-1')
SUFFIX = os.environ.get('SUFFIX', 'aimar')
TABLE_NAME = os.environ.get('DDB_TABLE', 'Inventory')

# Nombres de recursos
UPLOADS_BUCKET = f'inventory-uploads-{SUFFIX}'
WEB_BUCKET = f'inventory-web-{SUFFIX}'
SNS_TOPIC_NAME = f'NoStockTopic-{SUFFIX}'
API_NAME = f'InventoryHttpApi-{SUFFIX}'

# Clientes AWS
s3 = boto3.client('s3', region_name=REGION)
s3_resource = boto3.resource('s3', region_name=REGION)
dynamodb = boto3.client('dynamodb', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)
apigateway = boto3.client('apigatewayv2', region_name=REGION)
sns_client = boto3.client('sns', region_name=REGION)


def delete_s3_buckets():
    """Elimina los buckets S3 y su contenido."""
    print("\n🗑️  Eliminando buckets S3...")
    
    for bucket_name in [UPLOADS_BUCKET, WEB_BUCKET]:
        try:
            bucket = s3_resource.Bucket(bucket_name)
            # Eliminar todos los objetos
            bucket.objects.all().delete()
            # Eliminar el bucket
            bucket.delete()
            print(f"✅ Bucket eliminado: {bucket_name}")
        except Exception as e:
            print(f"⚠️  Error eliminando bucket {bucket_name}: {e}")


def delete_dynamodb_table():
    """Elimina la tabla DynamoDB."""
    print("\n🗑️  Eliminando tabla DynamoDB...")
    
    try:
        dynamodb.delete_table(TableName=TABLE_NAME)
        print(f"✅ Tabla eliminada: {TABLE_NAME}")
        
        # Esperar a que se elimine
        print("⏳ Esperando a que la tabla se elimine...")
        waiter = dynamodb.get_waiter('table_not_exists')
        waiter.wait(TableName=TABLE_NAME)
    except dynamodb.exceptions.ResourceNotFoundException:
        print(f"ℹ️  Tabla no encontrada: {TABLE_NAME}")
    except Exception as e:
        print(f"⚠️  Error eliminando tabla: {e}")


def delete_lambda_functions():
    """Elimina las funciones Lambda."""
    print("\n🗑️  Eliminando funciones Lambda...")
    
    lambda_names = [
        f'load-inventory-{SUFFIX}',
        f'get-inventory-api-{SUFFIX}',
        f'notify-low-stock-{SUFFIX}'
    ]
    
    for lambda_name in lambda_names:
        try:
            # Primero, eliminar event source mappings (DynamoDB Stream)
            mappings = lambda_client.list_event_source_mappings(FunctionName=lambda_name)
            for mapping in mappings.get('EventSourceMappings', []):
                lambda_client.delete_event_source_mapping(UUID=mapping['UUID'])
            
            # Eliminar la función
            lambda_client.delete_function(FunctionName=lambda_name)
            print(f"✅ Lambda eliminada: {lambda_name}")
        except lambda_client.exceptions.ResourceNotFoundException:
            print(f"ℹ️  Lambda no encontrada: {lambda_name}")
        except Exception as e:
            print(f"⚠️  Error eliminando Lambda {lambda_name}: {e}")


def delete_api_gateway():
    """Elimina el API Gateway."""
    print("\n🗑️  Eliminando API Gateway...")
    
    try:
        apis = apigateway.get_apis()
        for api in apis['Items']:
            if api['Name'] == API_NAME:
                apigateway.delete_api(ApiId=api['ApiId'])
                print(f"✅ API eliminada: {API_NAME}")
                return
        print(f"ℹ️  API no encontrada: {API_NAME}")
    except Exception as e:
        print(f"⚠️  Error eliminando API Gateway: {e}")


def delete_sns_topic():
    """Elimina el topic SNS."""
    print("\n🗑️  Eliminando topic SNS...")
    
    try:
        topics = sns_client.list_topics()
        for topic in topics['Topics']:
            if SNS_TOPIC_NAME in topic['TopicArn']:
                # Eliminar suscripciones primero
                subscriptions = sns_client.list_subscriptions_by_topic(TopicArn=topic['TopicArn'])
                for sub in subscriptions.get('Subscriptions', []):
                    sns_client.unsubscribe(SubscriptionArn=sub['SubscriptionArn'])
                
                # Eliminar el topic
                sns_client.delete_topic(TopicArn=topic['TopicArn'])
                print(f"✅ Topic SNS eliminado: {SNS_TOPIC_NAME}")
                return
        print(f"ℹ️  Topic SNS no encontrado: {SNS_TOPIC_NAME}")
    except Exception as e:
        print(f"⚠️  Error eliminando topic SNS: {e}")


def main():
    """Función principal de limpieza."""
    print("=" * 60)
    print("🗑️  LIMPIEZA DE RECURSOS AWS")
    print("=" * 60)
    print(f"Región: {REGION}")
    print(f"Sufijo: {SUFFIX}")
    print("=" * 60)
    
    confirm = input("\n⚠️  ¿Estás seguro de eliminar TODOS los recursos? (escribe 'SI' para confirmar): ")
    if confirm != 'SI':
        print("❌ Operación cancelada.")
        return 1
    
    try:
        delete_api_gateway()
        delete_lambda_functions()
        delete_sns_topic()
        delete_dynamodb_table()
        delete_s3_buckets()
        
        # Eliminar archivo de outputs
        if os.path.exists('outputs.json'):
            os.remove('outputs.json')
        
        print("\n" + "=" * 60)
        print("✅ LIMPIEZA COMPLETADA")
        print("=" * 60)
        print("Todos los recursos han sido eliminados.")
        
    except Exception as e:
        print(f"\n❌ Error durante la limpieza: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
