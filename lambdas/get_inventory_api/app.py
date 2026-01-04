import os
import json
import boto3

DDB_TABLE = os.environ.get('DDB_TABLE', 'Inventory')

ddb = boto3.resource('dynamodb')
TABLE = ddb.Table(DDB_TABLE)


def response(status, body):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body)
    }


def lambda_handler(event, context):
    # Soportamos: GET /items  y GET /items/{store}
    path_params = event.get('pathParameters') or {}
    store = path_params.get('store') if path_params else None
    try:
        if store:
            # Query por PK Store (se asume que PK es Store)
            resp = TABLE.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('Store').eq(store)
            )
            items = resp.get('Items', [])
        else:
            # Scan (para demo; en producción usar paginación/query)
            resp = TABLE.scan()
            items = resp.get('Items', [])
        return response(200, {'items': items})
    except Exception as e:
        print('Error al acceder a DynamoDB', e)
        return response(500, {'error': str(e)})
