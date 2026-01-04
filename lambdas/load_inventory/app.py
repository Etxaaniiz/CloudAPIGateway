import os
import csv
import boto3
import io
from typing import Iterable, Tuple

DDB_TABLE = os.environ.get('DDB_TABLE', 'Inventory')

s3 = boto3.client('s3')
ddb = boto3.resource('dynamodb')

TABLE = ddb.Table(DDB_TABLE)


def parse_csv_rows(csv_text: str) -> Iterable[Tuple[str, str, int]]:
    """Parsea el CSV y yield (store, item, count).

    Acepta encabezados en mayúsculas o minúsculas: Store, Item, Count.
    Si Count no es numérico se devuelve 0.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        store = row.get('Store') or row.get('store')
        item = row.get('Item') or row.get('item')
        cnt = row.get('Count') or row.get('count') or '0'
        try:
            cnt_n = int(float(cnt))
        except Exception:
            cnt_n = 0
        if not store or not item:
            # Omitir filas inválidas
            continue
        yield (str(store), str(item), cnt_n)


def lambda_handler(event, context):
    # Evento S3 PutObject
    total = 0
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        print(f"Procesando archivo s3://{bucket}/{key}")
        obj = s3.get_object(Bucket=bucket, Key=key)
        body = obj['Body'].read().decode('utf-8')
        with TABLE.batch_writer() as batch:
            for store, item, count in parse_csv_rows(body):
                batch.put_item(Item={'Store': store, 'Item': item, 'Count': count})
                total += 1
        print(f"Insertadas {total} entradas en DynamoDB tabla {DDB_TABLE}")
    return {'status': 'ok', 'processed': total}


if __name__ == '__main__':
    # Modo local de prueba: lee sample.csv si existe y parsea
    sample = 'sample.csv'
    if os.path.exists(sample):
        with open(sample, 'r', encoding='utf-8') as f:
            txt = f.read()
        for s, i, c in parse_csv_rows(txt):
            print(s, i, c)
    else:
        print('Ponte un sample.csv en la carpeta para probar parse_csv_rows localmente')
