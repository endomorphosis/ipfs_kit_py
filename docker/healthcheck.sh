#!/bin/bash
# Health check script for IPFS-Kit container

set -e

echo "🏥 IPFS-Kit Health Check"
echo "========================"

# Check if IPFS daemon is running
echo "Checking IPFS daemon..."
if ipfs id > /dev/null 2>&1; then
    echo "✅ IPFS daemon: Running"
    IPFS_OK=1
else
    echo "❌ IPFS daemon: Not running"
    IPFS_OK=0
fi

# Check if IPFS-Kit daemon is running
echo "Checking IPFS-Kit daemon..."
if [ -f "/tmp/ipfs_kit_daemon.pid" ]; then
    PID=$(cat /tmp/ipfs_kit_daemon.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "✅ IPFS-Kit daemon: Running (PID: $PID)"
        DAEMON_OK=1
    else
        echo "❌ IPFS-Kit daemon: PID file exists but process not running"
        DAEMON_OK=0
    fi
else
    echo "❌ IPFS-Kit daemon: PID file not found"
    DAEMON_OK=0
fi

# Check HTTP API if daemon is running
if [ $DAEMON_OK -eq 1 ]; then
    echo "Checking daemon HTTP API..."
    if curl -f -s "http://localhost:9999/api/v1/status" > /dev/null 2>&1; then
        echo "✅ Daemon HTTP API: Responding"
        API_OK=1
    else
        echo "❌ Daemon HTTP API: Not responding"
        API_OK=0
    fi
else
    API_OK=0
fi

# Overall health assessment
if [ $IPFS_OK -eq 1 ] && [ $DAEMON_OK -eq 1 ] && [ $API_OK -eq 1 ]; then
    echo "✅ Overall health: HEALTHY"
    exit 0
elif [ $IPFS_OK -eq 1 ] && [ $DAEMON_OK -eq 1 ]; then
    echo "⚠️  Overall health: DEGRADED (API issues)"
    exit 0  # Still considered healthy for container orchestration
else
    echo "❌ Overall health: UNHEALTHY"
    exit 1
fi
