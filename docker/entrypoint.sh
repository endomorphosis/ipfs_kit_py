#!/bin/bash
set -e

SUPERVISOR_CONF="/etc/supervisor/conf.d/supervisord.conf"
SUPERVISORD_BIN="/usr/bin/supervisord"
SUPERVISORCTL_BIN="/usr/bin/supervisorctl"
SUPERVISORD_PID=""

# Default mode is all services if not specified
MODE=${1:-"all"}

# Function to log with timestamp
log() {
  echo "[$(date --rfc-3339=seconds)] $1"
}

# Function to handle signals
handle_signal() {
  log "Caught signal, shutting down gracefully..."
  if ! "$SUPERVISORCTL_BIN" -c "$SUPERVISOR_CONF" stop all >/dev/null 2>&1; then
    log "Failed to stop services via supervisorctl"
  fi
  if [ -n "$SUPERVISORD_PID" ] && kill -0 "$SUPERVISORD_PID" >/dev/null 2>&1; then
    kill "$SUPERVISORD_PID" >/dev/null 2>&1 || true
  fi
  exit 0
}

# Register signal handlers
trap handle_signal SIGTERM SIGINT

# Ensure log directory exists
mkdir -p /tmp/ipfs_kit_logs /tmp/ipfs_kit_config

# Ensure project-managed binaries are on PATH for supervisord programs.
export PATH="/app/ipfs_kit_py/bin:${PATH}"

# Install required binaries using the repo's shared installers.
# This avoids duplicating pinned binary download logic across Docker/CI.
export IPFS_KIT_DOCKER_MODE="$MODE"
log "Ensuring IPFS binaries are installed (mode=$MODE)..."
ZERO_TOUCH_BINARIES="core"
if [ "${MODE:-}" = "full" ]; then
  ZERO_TOUCH_BINARIES="full"
fi
python -m ipfs_kit_py.zero_touch --binaries "$ZERO_TOUCH_BINARIES" || exit 1

# Initialize IPFS repo on first run (needed before running daemon).
if [ ! -f "/home/ipfs_user/.ipfs/config" ]; then
  log "Initializing IPFS repo..."
  ipfs init --profile server || true
  ipfs config Addresses.API /ip4/0.0.0.0/tcp/5001 || true
  ipfs config Addresses.Gateway /ip4/0.0.0.0/tcp/8080 || true
fi

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

# Start supervisord in the background
log "Starting supervisord..."
"$SUPERVISORD_BIN" -c "$SUPERVISOR_CONF" &
SUPERVISORD_PID=$!

# Wait for supervisord to be ready (up to ~20s)
for attempt in $(seq 1 40); do
  if "$SUPERVISORCTL_BIN" -c "$SUPERVISOR_CONF" status >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! "$SUPERVISORCTL_BIN" -c "$SUPERVISOR_CONF" status >/dev/null 2>&1; then
  log "supervisord did not become ready"
  if [ -f /tmp/supervisord.log ]; then
    log "supervisord.log (tail):"
    tail -n 100 /tmp/supervisord.log || true
  fi
  # Do not exit; attempt to continue starting services
fi

case "$MODE" in
  "daemon-only")
    log "Starting daemon-only mode (IPFS-Kit daemon API on port 9999)"
    # Start only the IPFS-Kit daemon
    # Ensure IPFS is running as a dependency for the daemon
    "$SUPERVISORCTL_BIN" -c "$SUPERVISOR_CONF" start ipfs || true
    "$SUPERVISORCTL_BIN" -c "$SUPERVISOR_CONF" start ipfs-kit-daemon
    ;;
    
  "ipfs-only")
    log "Starting IPFS-only mode (IPFS daemon on ports 4001, 5001, 8080)"
    # Start only IPFS daemon
    "$SUPERVISORCTL_BIN" -c "$SUPERVISOR_CONF" start ipfs
    ;;
    
  "all")
    log "Starting all services (IPFS + IPFS-Kit daemon)"
    # Start all default services
    "$SUPERVISORCTL_BIN" -c "$SUPERVISOR_CONF" start ipfs ipfs-kit-daemon
    ;;
    
  "full")
    log "Starting full stack (IPFS + Cluster + IPFS-Kit daemon + MCP)"
    # Start everything including optional services
    "$SUPERVISORCTL_BIN" -c "$SUPERVISOR_CONF" start ipfs ipfs-cluster ipfs-kit-daemon mcp-server
    ;;
    
  *)
    log "Unknown mode: $MODE"
    log "Valid modes: daemon-only, ipfs-only, all, full"
    exit 1
    ;;
esac

# Keep container running by tailing logs (robust if files don't exist yet)
log "Services started. Monitoring logs..."

# Ensure log files exist so tail doesn't exit if glob is empty
touch /tmp/ipfs_kit_logs/ipfs_out.log \
  /tmp/ipfs_kit_logs/ipfs_error.log \
  /tmp/ipfs_kit_logs/daemon_out.log \
  /tmp/ipfs_kit_logs/daemon_error.log \
  /tmp/ipfs_kit_logs/cluster_out.log \
  /tmp/ipfs_kit_logs/cluster_error.log \
  /tmp/ipfs_kit_logs/mcp_out.log \
  /tmp/ipfs_kit_logs/mcp_error.log

# Follow all logs and never exit; if tail fails for any reason, sleep to keep container alive
tail -F /tmp/ipfs_kit_logs/*.log || sleep infinity