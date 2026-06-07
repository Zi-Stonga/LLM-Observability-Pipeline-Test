# 01 Architecture

See docs/architecture.md for the full data flow diagram.

## Key design decisions
- Six per-function IAM roles (least privilege)
- KMS CMKs for all storage (DynamoDB, S3, SQS, SNS, Kinesis)
- SQS DLQ with CloudWatch alarm for poison message detection
- Kinesis 7-day retention to survive weekend outages
- WAFv2 with OWASP managed rules on API Gateway
- CORS locked to explicit origin list, no wildcard
