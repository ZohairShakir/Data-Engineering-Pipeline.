# Deployment status

AWS deployment is intentionally deferred until the local ETL and tests pass and
the owner explicitly approves infrastructure changes.

The future deployment will use S3 prefixes for `raw/`, `processed/`, and
`quarantine/`; an EC2 instance running the Docker image; an IAM instance role;
and Systems Manager Parameter Store for configuration. No AWS resources have
been created by Phase 1.
