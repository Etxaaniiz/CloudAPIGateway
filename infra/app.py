#!/usr/bin/env python3
import os
from aws_cdk import App, Environment
from cloud_api_stack import CloudApiStack

app = App()

env = None
# Allow using REGION and AWS_ACCOUNT env vars or fall back to default
region = os.environ.get('REGION')
account = os.environ.get('CDK_DEFAULT_ACCOUNT')
if region or account:
    env = Environment(account=account, region=region)

CloudApiStack(app, "CloudApiStack", env=env)

app.synth()
