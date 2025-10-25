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

DAEMON_OK=0
API_OK=0

# Probe daemon HTTP API directly (most reliable)
echo "Checking daemon HTTP API (http://localhost:9999/api/v1/status)..."
if curl -f -s "http://localhost:9999/api/v1/status" > /dev/null 2>&1; then
    echo "✅ Daemon HTTP API: Responding"
    DAEMON_OK=1
    API_OK=1
else
    echo "❌ Daemon HTTP API: Not responding yet"
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
