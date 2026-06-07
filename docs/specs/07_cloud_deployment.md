# 07 Cloud Deployment

## Prerequisites
- Python 3.12 (Microsoft Store on Windows)
- Node.js 20+ (for CDK CLI)
- AWS credentials configured (aws configure)
- CDK CLI: npm install -g aws-cdk@latest

## First deploy
```bash
cdk bootstrap aws://<account>/<region>
cdk deploy -c alert_email=ops@example.com -c allowed_origins=https://your-app.example.com
```

## Outputs
- ApiEndpoint: live API URL
- AlertTopicArn: SNS topic (confirm email subscription)
- ScoringDLQUrl: watch for poison messages
- DashboardUrl: CloudWatch operations dashboard

## Tear down
```bash
cdk destroy -c alert_email=ops@example.com -c allowed_origins=https://your-app.example.com
```

Note: S3 bucket and KMS keys have RemovalPolicy.RETAIN, delete manually if needed.
