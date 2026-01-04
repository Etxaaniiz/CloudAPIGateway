import os
import json
import boto3

SNS_ARN = os.environ.get('SNS_TOPIC_ARN')
THRESHOLD = int(os.environ.get('LOW_STOCK_THRESHOLD', '5'))

sns = boto3.client('sns')


def lambda_handler(event, context):
    # Evento desde DynamoDB Streams
    for record in event.get('Records', []):
        if record.get('eventName') not in ('INSERT', 'MODIFY'):
            continue
        new_img = record['dynamodb'].get('NewImage', {})
        try:
            store = new_img['Store']['S']
            item = new_img['Item']['S']
            count = int(new_img['Count']['N'])
        except Exception as e:
            print('Formato inesperado en stream:', e)
            continue
        if count <= THRESHOLD:
            msg = f"Low stock: store={store}, item={item}, count={count}"
            print('Enviando notificación:', msg)
            if SNS_ARN:
                sns.publish(TopicArn=SNS_ARN, Subject='Low stock alert', Message=msg)
            else:
                print('SNS_TOPIC_ARN no configurado; omitiendo publish')
    return {'status': 'ok'}
