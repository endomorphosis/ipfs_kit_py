#!/bin/bash
# Unified MCP Server Configuration

# Global settings
export MCP_USE_MOCK_MODE="false"

# HuggingFace configuration
if [ -f ~/.cache/huggingface/token ]; then
  export HUGGINGFACE_TOKEN=$(cat ~/.cache/huggingface/token)
  echo "Using HuggingFace token"
else
  echo "No HuggingFace token found, using mock mode"
fi

# AWS S3 configuration
# Using local implementation for demonstration
export AWS_ACCESS_KEY_ID="mock_key_$(date +%s)"
export AWS_SECRET_ACCESS_KEY="mock_secret_$(date +%s)"
export AWS_DEFAULT_REGION="us-east-1"
export S3_BUCKET_NAME="ipfs-storage-demo"

# Filecoin configuration
# Using public gateway
export LOTUS_PATH="/home/barberb/.lotus-gateway"
export LOTUS_GATEWAY_MODE="true"
export PATH="/home/barberb/ipfs_kit_py/bin:$PATH"

# Storacha configuration
export STORACHA_API_KEY="mock_storacha_key"
export STORACHA_API_URL="http://localhost:5678"

# Lassie configuration
export LASSIE_API_URL="http://localhost:5432"
export LASSIE_ENABLED="true"

echo "MCP configuration loaded"
