#!/bin/bash

# Use mock mode only as fallback if real credentials are not available
export MCP_USE_MOCK_MODE="false"

# HuggingFace configuration
if [ -f ~/.cache/huggingface/token ]; then
  export HUGGINGFACE_TOKEN=$(cat ~/.cache/huggingface/token)
  echo "Found HuggingFace token"
else
  echo "No HuggingFace token found, will use mock mode"
  export HF_MOCK_MODE="true"
fi

# AWS S3 configuration - check for credentials
if [ -f ~/.aws/credentials ] || [ -n "$AWS_ACCESS_KEY_ID" ]; then
  echo "AWS credentials found"
  # AWS credentials will be loaded from environment or ~/.aws/credentials
  export AWS_S3_BUCKET_NAME="ipfs-storage-demo"
else
  echo "No AWS credentials found, will use mock mode"
  export AWS_S3_BUCKET_NAME="ipfs-storage-demo"
  export AWS_ACCESS_KEY_ID="mock_key"
  export AWS_SECRET_ACCESS_KEY="mock_secret"
  export AWS_DEFAULT_REGION="us-east-1"
fi

# Filecoin configuration
if [ -n "$LOTUS_API_TOKEN" ] && [ -n "$LOTUS_API_ENDPOINT" ]; then
  echo "Lotus API credentials found"
else
  echo "No Lotus API credentials found, will use mock mode"
  export LOTUS_API_TOKEN="mock_token"
  export LOTUS_API_ENDPOINT="http://localhost:1234/rpc/v0"
fi

# Storacha configuration
if [ -n "$STORACHA_API_KEY" ]; then
  echo "Storacha API key found"
else
  echo "No Storacha API key found, will use mock mode"
  export STORACHA_API_KEY="mock_key"
fi

# Lassie configuration
if [ -n "$LASSIE_API_URL" ]; then
  echo "Lassie API URL found"
else
  echo "No Lassie API configuration found, will use mock mode"
  export LASSIE_API_URL="http://localhost:5000"
  export LASSIE_ENABLED="true"
fi

# Fix any permissions issues in the directories
chmod -R 755 ~/.ipfs_kit 2>/dev/null || true
