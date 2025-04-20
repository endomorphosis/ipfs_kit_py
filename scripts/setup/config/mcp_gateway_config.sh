#!/bin/bash
# MCP Filecoin Gateway Configuration

# Filecoin gateway configuration
export LOTUS_PATH="/home/barberb/.lotus-gateway"
export LOTUS_GATEWAY_MODE="true"
export PATH="/home/barberb/ipfs_kit_py/bin:/home/barberb/.nvm/versions/node/v22.5.1/bin:/home/barberb/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin:/opt/hp/aistudio/bin"

echo "Filecoin gateway configured with:"
echo "  API: https://api.node.glif.io/rpc/v0"
echo "  Lotus script: /home/barberb/ipfs_kit_py/bin/lotus"
