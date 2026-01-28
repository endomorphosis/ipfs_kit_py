#!/bin/bash
# Unified MCP Configuration
# This file is generated automatically by the MCP Server Real Implementation Integrator

# Global settings
export MCP_USE_MOCK_MODE="false"

# HuggingFace configuration
if [ -f ~/.cache/huggingface/token ]; then
  export HUGGINGFACE_TOKEN=$(cat ~/.cache/huggingface/token)
  echo "Using real HuggingFace token"
else
  echo "No HuggingFace token found, using mock mode"
  export HUGGINGFACE_TOKEN="mock_token"
fi

# AWS S3 configuration
if [ -f ~/.aws/credentials ]; then
  echo "Using real AWS credentials"
else
  echo "Using local S3 implementation"
  # Default values will be overridden if setup_s3_implementation.py set different ones
  export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-mock_access_key}"
  export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-mock_secret_key}"
  export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
  export S3_BUCKET_NAME="${S3_BUCKET_NAME:-ipfs-storage-demo}"
  export S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-http://localhost:9000}"
fi

# Filecoin configuration
# Using Filecoin public gateway
export LOTUS_PATH="C:\Users\Admin/.lotus-gateway"
export LOTUS_GATEWAY_MODE="true"
export PATH="C:\Users\Admin\ipfs_kit_py\bin:$PATH"

# Add bin directory to PATH
if [ -d "$(pwd)/bin" ]; then
  export PATH="$(pwd)/bin:$PATH"
fi

# Storacha configuration
export STORACHA_API_KEY="${STORACHA_API_KEY:-mock_key}"
export STORACHA_API_URL="${STORACHA_API_URL:-http://localhost:5678}"

# Lassie configuration
export LASSIE_API_URL="${LASSIE_API_URL:-http://localhost:5432}"
export LASSIE_ENABLED="${LASSIE_ENABLED:-true}"

# Print configuration summary
echo "MCP Configuration Summary:"
echo "=========================="
echo "HuggingFace Token: ${HUGGINGFACE_TOKEN:0:5}...${HUGGINGFACE_TOKEN: -5}"
echo "AWS S3 Key ID: ${AWS_ACCESS_KEY_ID:0:5}..."
echo "S3 Bucket: ${S3_BUCKET_NAME}"
echo "S3 Endpoint: ${S3_ENDPOINT_URL}"
echo "Filecoin API Endpoint: ${LOTUS_API_ENDPOINT}"
echo "Storacha API URL: ${STORACHA_API_URL}"
echo "Lassie API URL: ${LASSIE_API_URL}"
echo "=========================="
