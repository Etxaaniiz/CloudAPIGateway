import os
import json
import boto3
from decimal import Decimal

DDB_TABLE = os.environ.get('DDB_TABLE', 'Inventory')

ddb = boto3.resource('dynamodb')
TABLE = ddb.Table(DDB_TABLE)


# Helper para convertir Decimal a tipos JSON serializables
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)


def response(status, body):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }


def lambda_handler(event, context):
    """Handler para HTTP API Gateway v2."""
    print(f"Event: {json.dumps(event)}")  # Debug
    
    try:
        # Soportamos: GET /items  y GET /items/{store}
        # Para HTTP API v2, los parámetros están en rawPath
        path = event.get('rawPath', '/')
        path_params = event.get('pathParameters')
        store = None
        
        if path_params and 'store' in path_params:
            store = path_params.get('store')
        
        print(f"Path: {path}, Store param: {store}")
        
        if store:
            # Query por PK Store
            resp = TABLE.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('Store').eq(store)
            )
            items = resp.get('Items', [])
        else:
            # Scan para obtener todo
            resp = TABLE.scan()
            items = resp.get('Items', [])
        
        return response(200, {'items': items})
    except Exception as e:
        print(f'Error al acceder a DynamoDB: {str(e)}')
        import traceback
        traceback.print_exc()
        return response(500, {'error': str(e)})
