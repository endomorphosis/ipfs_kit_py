#!/bin/bash
# Real AWS credentials for S3 integration

# AWS S3 credentials (using MinIO for local testing)
export AWS_ACCESS_KEY_ID="minioadmin"
export AWS_SECRET_ACCESS_KEY="minioadmin"
export AWS_S3_BUCKET_NAME="ipfs-storage-demo"
export AWS_REGION="us-east-1"
export AWS_ENDPOINT_URL="http://localhost:9000"  # MinIO endpoint

# Disable forced mock mode
export MCP_USE_MOCK_MODE="false"