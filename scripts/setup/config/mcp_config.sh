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

# AWS S3 configuration
# Using real S3 credentials configured by setup script
export AWS_ACCESS_KEY_ID="None"
export AWS_SECRET_ACCESS_KEY="None"
export AWS_DEFAULT_REGION="us-east-1"
export S3_BUCKET_NAME="ipfs-storage-demo"
export AWS_ACCESS_KEY_ID="None"
export AWS_SECRET_ACCESS_KEY="None"
export AWS_DEFAULT_REGION="us-east-1"
export S3_BUCKET_NAME="ipfs-storage-demo"
export AWS_ACCESS_KEY_ID="None"
export AWS_SECRET_ACCESS_KEY="None"
export AWS_DEFAULT_REGION="us-east-1"
export S3_BUCKET_NAME="ipfs-storage-demo"
export AWS_ACCESS_KEY_ID="None"
export AWS_SECRET_ACCESS_KEY="None"
export AWS_DEFAULT_REGION="us-east-1"
export S3_BUCKET_NAME="ipfs-storage-demo"

# Filecoin configuration
# Using Filecoin development environment
export LOTUS_PATH="C:\Users\Admin/.lotus-dev"
export LOTUS_API_TOKEN="mock-token-for-development"
export LOTUS_API_ENDPOINT="http://127.0.0.1:1234/rpc/v0"
export PATH="C:\Users\Admin\ipfs_kit_py\bin:$PATH"
# Using Lassie local development API
export LASSIE_API_URL="http://localhost:5432"
export LASSIE_ENABLED="true"

# Fix any permissions issues in the directories
chmod -R 755 ~/.ipfs_kit 2>/dev/null || true
