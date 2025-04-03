#!/bin/bash
set -e

# Default role is leecher if not specified
ROLE=${1:-"leecher"}

# Function to log with timestamp
log() {
  echo "[$(date --rfc-3339=seconds)] $1"
}

# Function to handle signals
handle_signal() {
  log "Caught signal, shutting down gracefully..."
  if [ -n "$PID" ]; then
    kill -TERM "$PID" 2>/dev/null
    wait "$PID"
  fi
  exit 0
}

# Register signal handlers
trap handle_signal SIGTERM SIGINT

# Validate environment
if [ "$ROLE" = "worker" ] && [ -z "$MASTER_ADDR" ]; then
  log "Error: MASTER_ADDR environment variable must be set for worker role"
  exit 1
fi

# Setup configuration from environment variables
CONFIG_ARGS=""
if [ -n "$CONFIG_PATH" ]; then
  CONFIG_ARGS="--config $CONFIG_PATH"
fi

# Set resource limits from environment
if [ -n "$MAX_MEMORY" ]; then
  export IPFS_KIT_MAX_MEMORY="$MAX_MEMORY"
fi

if [ -n "$MAX_STORAGE" ]; then
  export IPFS_KIT_MAX_STORAGE="$MAX_STORAGE"
fi

# Optional swarm key for private networks
if [ -n "$SWARM_KEY" ]; then
  echo "$SWARM_KEY" > "$IPFS_PATH/swarm.key"
  log "Created swarm key for private network"
fi

# Initialize IPFS and IPFS Cluster based on role
log "Initializing as $ROLE node..."

if [ "$ROLE" = "master" ]; then
  # Master-specific initialization
  CLUSTER_ARGS=""
  if [ -n "$CLUSTER_SECRET" ]; then
    CLUSTER_ARGS="--cluster-secret $CLUSTER_SECRET"
  fi
  
  if [ -n "$BOOTSTRAP_PEERS" ]; then
    CLUSTER_ARGS="$CLUSTER_ARGS --bootstrap $BOOTSTRAP_PEERS"
  fi
  
  # Start as a server process
  log "Starting IPFS Kit master node $CLUSTER_ARGS $CONFIG_ARGS"
  python -m ipfs_kit_py.cli serve --role master $CLUSTER_ARGS $CONFIG_ARGS &
  PID=$!

elif [ "$ROLE" = "worker" ]; then
  # Worker-specific initialization
  log "Starting IPFS Kit worker node connecting to $MASTER_ADDR"
  python -m ipfs_kit_py.cli serve --role worker --master-addr "$MASTER_ADDR" $CONFIG_ARGS &
  PID=$!

else
  # Leecher-specific initialization
  log "Starting IPFS Kit leecher node"
  python -m ipfs_kit_py.cli serve --role leecher $CONFIG_ARGS &
  PID=$!
fi

# Wait for the process to finish
wait $PID