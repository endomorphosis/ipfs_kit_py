#!/bin/bash
set -e

# Default mode is all services if not specified
MODE=${1:-"all"}

# Function to log with timestamp
log() {
  echo "[$(date --rfc-3339=seconds)] $1"
}

# Function to handle signals
handle_signal() {
  log "Caught signal, shutting down gracefully..."
  supervisorctl stop all || true
  exit 0
}

# Register signal handlers
trap handle_signal SIGTERM SIGINT

# Ensure log directory exists
mkdir -p /tmp/ipfs_kit_logs /tmp/ipfs_kit_config

# Create default daemon config if it doesn't exist
if [ ! -f "/tmp/ipfs_kit_config/daemon.json" ]; then
  log "Creating default daemon configuration..."
  cat > /tmp/ipfs_kit_config/daemon.json << EOF
{
  "host": "0.0.0.0",
  "port": 9999,
  "ipfs_path": "/home/ipfs_user/.ipfs",
  "log_level": "INFO"
}
EOF
fi

log "Starting IPFS-Kit in '$MODE' mode..."

case "$MODE" in
  "daemon-only")
    log "Starting daemon-only mode (IPFS-Kit daemon API on port 9999)"
    # Start only the IPFS-Kit daemon
    supervisorctl start ipfs-kit-daemon
    ;;
    
  "ipfs-only")
    log "Starting IPFS-only mode (IPFS daemon on ports 4001, 5001, 8080)"
    # Start only IPFS daemon
    supervisorctl start ipfs
    ;;
    
  "all")
    log "Starting all services (IPFS + IPFS-Kit daemon)"
    # Start all default services
    supervisorctl start ipfs ipfs-kit-daemon
    ;;
    
  "full")
    log "Starting full stack (IPFS + Cluster + IPFS-Kit daemon + MCP)"
    # Start everything including optional services
    supervisorctl start ipfs ipfs-cluster ipfs-kit-daemon mcp-server
    ;;
    
  *)
    log "Unknown mode: $MODE"
    log "Valid modes: daemon-only, ipfs-only, all, full"
    exit 1
    ;;
esac

# Keep container running by tailing logs
log "Services started. Monitoring logs..."
tail -f /tmp/ipfs_kit_logs/*.log