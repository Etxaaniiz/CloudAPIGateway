import os
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_dynamodb as ddb,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_lambda_event_sources as event_sources,
    RemovalPolicy,
    CfnOutput,
)


class CloudApiStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Config via env (or .env antes de invocar cdk deploy)
        suffix = os.environ.get('SUFFIX', 'aimar')
        email = os.environ.get('EMAIL', '')
        table_name = os.environ.get('DDB_TABLE', 'Inventory')

        # Buckets
        uploads_bucket = s3.Bucket(self, 'UploadsBucket',
            bucket_name=f'inventory-uploads-{suffix}',
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        website_bucket = s3.Bucket(self, 'WebsiteBucket',
            bucket_name=f'inventory-web-{suffix}',
            website_index_document='index.html',
            public_read_access=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # DynamoDB
        table = ddb.Table(self, 'InventoryTable',
            table_name=table_name,
            partition_key=ddb.Attribute(name='Store', type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name='Item', type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            stream=ddb.StreamViewType.NEW_IMAGE,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Lambdas
        load_lambda = _lambda.Function(self, 'LoadInventoryFn',
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler='app.lambda_handler',
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'load_inventory')),
            environment={'DDB_TABLE': table.table_name}
        )

        # Grant permissions
        uploads_bucket.grant_read(load_lambda)
        table.grant_write_data(load_lambda)

        # S3 -> Lambda notification
        from aws_cdk.aws_s3_notifications import LambdaDestination
        uploads_bucket.add_event_notification(s3.EventType.OBJECT_CREATED, LambdaDestination(load_lambda))

        # API Lambda
        api_lambda = _lambda.Function(self, 'GetInventoryApiFn',
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler='app.lambda_handler',
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'get_inventory_api')),
            environment={'DDB_TABLE': table.table_name}
        )
        table.grant_read_data(api_lambda)

        # HTTP API + integrations
        http_api = apigwv2.HttpApi(self, 'InventoryHttpApi',
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=['*'],
                allow_methods=[apigwv2.HttpMethod.GET],
                allow_headers=['*']
            )
        )

        integration = integrations.LambdaProxyIntegration('GetItemsIntegration', handler=api_lambda)
        http_api.add_routes(path='/items', methods=[apigwv2.HttpMethod.GET], integration=integration)
        http_api.add_routes(path='/items/{store}', methods=[apigwv2.HttpMethod.GET], integration=integration)

        # SNS topic and notify lambda (DynamoDB Streams)
        topic = sns.Topic(self, 'NoStockTopic', display_name='NoStock')
        if email:
            topic.add_subscription(subs.EmailSubscription(email))

        notify_lambda = _lambda.Function(self, 'NotifyLowStockFn',
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler='app.lambda_handler',
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'notify_low_stock')),
            environment={'SNS_TOPIC_ARN': topic.topic_arn, 'LOW_STOCK_THRESHOLD': '5'}
        )

        # Grant stream read and publish
        table.grant_stream_read(notify_lambda)
        topic.grant_publish(notify_lambda)

        # Event source mapping (DynamoDB Streams -> Lambda)
        notify_lambda.add_event_source(event_sources.DynamoEventSource(table, starting_position=_lambda.StartingPosition.LATEST, batch_size=100))

        # Deploy website contents to website bucket
        s3_deploy.BucketDeployment(self, 'DeployWebsite',
            sources=[s3_deploy.Source.asset(os.path.join(os.path.dirname(__file__), '..', 'web'))],
            destination_bucket=website_bucket
        )

        # Outputs
        CfnOutput(self, 'ApiUrl', value=http_api.api_endpoint)
        CfnOutput(self, 'WebsiteUrl', value=website_bucket.bucket_website_url)
        CfnOutput(self, 'UploadsBucketName', value=uploads_bucket.bucket_name)
        CfnOutput(self, 'DynamoTableName', value=table.table_name)
        CfnOutput(self, 'SnsTopicArn', value=topic.topic_arn)
