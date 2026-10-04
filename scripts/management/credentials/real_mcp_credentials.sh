#!/bin/bash
# MCP Server Credentials for Local Services

# AWS S3 credentials (MinIO)
export AWS_ENDPOINT_URL="http://localhost:9000"
export AWS_ACCESS_KEY_ID="minioadmin"
export AWS_SECRET_ACCESS_KEY="minioadmin"
export AWS_S3_BUCKET_NAME="ipfs-storage-demo"
export AWS_REGION="us-east-1"

# Set this to true to use local implementations
export USE_LOCAL_IMPLEMENTATIONS="true"