#!/bin/bash
set -e

# IPFS Kit Docker Setup Script
# This script creates the necessary directory structure and configuration for Docker deployment

# Create data directories
echo "Creating data directories..."
mkdir -p data/master data/worker1 data/worker2 data/leecher

# Set proper permissions
echo "Setting directory permissions..."
chmod -R 777 data

# Generate cluster secret (optional, for secure cluster communication)
if [ "$1" == "--cluster-secret" ]; then
  echo "Generating cluster secret..."
  CLUSTER_SECRET=$(openssl rand -base64 32)
  echo "export CLUSTER_SECRET=$CLUSTER_SECRET" > .env
  echo "Cluster secret saved to .env file."
fi

echo "Setup complete! You can now run:"
echo "docker-compose up -d"
echo ""
echo "To view logs:"
echo "docker-compose logs -f"
echo ""
echo "To scale workers:"
echo "docker-compose up -d --scale ipfs-worker=3"