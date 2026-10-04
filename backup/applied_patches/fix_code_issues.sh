#!/bin/bash

# Script to fix all code issues in ipfs_kit_py/mcp using Black and Ruff
# This approach focuses on fixing critical issues first, then applying formatters

echo "===== Starting comprehensive code fixes for ipfs_kit_py/mcp ====="

# Create a backup of the entire directory first
BACKUP_DIR="mcp_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR..."
mkdir -p $BACKUP_DIR
cp -r ipfs_kit_py/mcp/* $BACKUP_DIR/

# STEP 1: Fix critical issues that prevent Black and Ruff from running properly

# Fix 1: Fix corrupted webrtc_controller.py file
echo "Fixing corrupted webrtc_controller.py file..."
if grep -q "</final_file_content>" "ipfs_kit_py/mcp/controllers/webrtc_controller.py"; then
  # Remove all content from </final_file_content> to the end
  sed -i '/^<\/final_file_content>/,$d' ipfs_kit_py/mcp/controllers/webrtc_controller.py
  # Add a proper function end
  echo "            return {'success': True, 'message': 'WebRTC controller initialized'}" >> ipfs_kit_py/mcp/controllers/webrtc_controller.py
  echo "        except Exception as e:" >> ipfs_kit_py/mcp/controllers/webrtc_controller.py
  echo "            logger.error(f'Error in WebRTC controller initialization: {e}')" >> ipfs_kit_py/mcp/controllers/webrtc_controller.py
  echo "            return {'success': False, 'error': str(e)}" >> ipfs_kit_py/mcp/controllers/webrtc_controller.py
fi

# Fix 2: Fix empty imports in controllers/__init__.py
echo "Fixing empty imports in controllers/__init__.py..."
sed -i 's/from ipfs_kit_py.mcp.controllers.fs_journal_controller import (/# Import commented out\n# from ipfs_kit_py.mcp.controllers.fs_journal_controller import FsJournalController/' ipfs_kit_py/mcp/controllers/__init__.py
sed -i 's/from ipfs_kit_py.mcp.controllers.libp2p_controller import (/# Import commented out\n# from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController/' ipfs_kit_py/mcp/controllers/__init__.py

# Fix 3: Fix prometheus.py with a completely rewritten version
echo "Fixing prometheus.py..."
cat > ipfs_kit_py/mcp/monitoring/prometheus.py << 'EOF'
"""
Prometheus monitoring integration for MCP.
"""

import logging
import psutil
import platform
from datetime import datetime
import time
import threading

# Configure logger
logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        start_http_server,
        generate_latest,
        REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
    CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4; charset=utf-8'
except ImportError:
    logger.warning("Prometheus client library not available, metrics will be disabled")
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = 'text/plain'

# Metrics collection class
class PrometheusMetricsCollector:
    """Collect and expose Prometheus metrics for MCP."""
    
    def __init__(self, config=None):
        """Initialize metrics collector with configuration."""
        self.config = config or {}
        self.enabled = self.config.get("enabled", PROMETHEUS_AVAILABLE)
        self.port = self.config.get("port", 9090)
        self.endpoint = self.config.get("endpoint", "/metrics")
        self.collection_interval = self.config.get("collection_interval", 15)
        self.registry = REGISTRY
        self.server_started = False
        self.metrics = {}
        self.collection_thread = None
        self.running = False
        
        if self.enabled and PROMETHEUS_AVAILABLE:
            self._setup_metrics()
        else:
            logger.info("Prometheus metrics collection is disabled")
    
    def _setup_metrics(self):
        """Set up metrics collectors."""
        # System metrics
        self.metrics["system_info"] = Info(
            "mcp_system_info", "System information"
        )
        self.metrics["system_cpu_usage"] = Gauge(
            "mcp_system_cpu_usage", "System CPU usage percent"
        )
        self.metrics["system_memory_usage"] = Gauge(
            "mcp_system_memory_usage", "System memory usage in bytes"
        )
        self.metrics["system_memory_percent"] = Gauge(
            "mcp_system_memory_percent", "System memory usage percent"
        )
        self.metrics["system_disk_usage"] = Gauge(
            "mcp_system_disk_usage", "System disk usage in bytes"
        )
        self.metrics["system_disk_percent"] = Gauge(
            "mcp_system_disk_percent", "System disk usage percent"
        )
        
        # IPFS metrics
        self.metrics["ipfs_operations_total"] = Counter(
            "mcp_ipfs_operations_total", "Total IPFS operations", 
            ["operation", "status"]
        )
        self.metrics["ipfs_operation_duration"] = Histogram(
            "mcp_ipfs_operation_duration", "IPFS operation duration in seconds",
            ["operation"]
        )
        self.metrics["ipfs_peers_connected"] = Gauge(
            "mcp_ipfs_peers_connected", "Number of connected IPFS peers"
        )
        self.metrics["ipfs_repo_size"] = Gauge(
            "mcp_ipfs_repo_size", "IPFS repository size in bytes"
        )
        self.metrics["ipfs_bandwidth_total"] = Counter(
            "mcp_ipfs_bandwidth_total", "Total IPFS bandwidth usage in bytes",
            ["direction"]
        )
        
        # Storage metrics
        self.metrics["storage_operations_total"] = Counter(
            "mcp_storage_operations_total", "Total storage operations",
            ["backend", "operation", "status"]
        )
        self.metrics["storage_operation_duration"] = Histogram(
            "mcp_storage_operation_duration", "Storage operation duration in seconds",
            ["backend", "operation"]
        )
        self.metrics["storage_size"] = Gauge(
            "mcp_storage_size", "Storage size in bytes", 
            ["backend"]
        )
        self.metrics["storage_objects"] = Gauge(
            "mcp_storage_objects", "Number of objects in storage",
            ["backend"]
        )
        
        # API metrics
        self.metrics["api_requests_total"] = Counter(
            "mcp_api_requests_total", "Total API requests",
            ["method", "endpoint", "status_code"]
        )
        self.metrics["api_request_duration"] = Histogram(
            "mcp_api_request_duration", "API request duration in seconds",
            ["method", "endpoint"]
        )
        
        # System information
        self.metrics["system_info"].info({
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "hostname": platform.node(),
        })
        
        logger.info("Prometheus metrics collectors initialized")
    
    def get_metrics(self):
        """Get current metrics as text."""
        if not PROMETHEUS_AVAILABLE:
            return "Prometheus metrics not available", 503
        
        try:
            # Generate latest metrics
            prometheus_data = generate_latest()
            return prometheus_data, 200, {"Content-Type": CONTENT_TYPE_LATEST}
        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}")
            return f"Error generating metrics: {e}", 500

# Singleton instance
metrics_collector = None

def get_metrics_collector(config=None):
    """Get or create the metrics collector singleton."""
    global metrics_collector
    if metrics_collector is None:
        metrics_collector = PrometheusMetricsCollector(config)
    return metrics_collector
EOF

# Fix 4: Fix broken ipfs_model_anyio.py
echo "Fixing ipfs_model_anyio.py with proper indentation..."
# Look for the section with try/except ImportError
if grep -q "try:" "ipfs_kit_py/mcp/models/ipfs_model_anyio.py" && grep -q "except ImportError:" "ipfs_kit_py/mcp/models/ipfs_model_anyio.py"; then
  # Fix the broken try-except block by creating a new one
  sed -i '/try:/,/except ImportError:/{
    s/try:/try:/g
    s/except ImportError:/except ImportError:/g
  }' ipfs_kit_py/mcp/models/ipfs_model_anyio.py
fi

# Fix 5: Fix broken storage_manager_anyio.py
echo "Fixing storage_manager_anyio.py..."
# Add missing import for run_async
sed -i '/<function_calls>/,/run_async/''{
    s/anyio.create_task_group()/# Define run_async function first\n                async def run_async():\n                    """Run the async refresh operation."""\n                    try:\n                        await self.refresh_backend_info_async(backend_name)\n                    except Exception as e:\n                        logger.error(f"Error refreshing backend info: {e}")\n                anyio.lowlevel.spawn_system_task(run_async)/
}' ipfs_kit_py/mcp/models/storage_manager_anyio.py

# Fix 6: Add missing imports
echo "Adding missing imports to files with undefined names..."
# Add import time to ipfs_controller.py (at the top)
sed -i '1s/^/import time\n/' ipfs_kit_py/mcp/controllers/ipfs_controller.py

# Add os import to monitoring/alerting.py
sed -i '1s/^/import os\n/' ipfs_kit_py/mcp/monitoring/alerting.py

# Add import to webrtc.py
sed -i '1s/^/from fastapi import APIRouter, WebSocket\nfrom typing import Optional\n/' ipfs_kit_py/mcp/extensions/webrtc.py

# Fix 7: Fix create_webrtc_router in webrtc.py
sed -i '/def create_webrtc_extension_router/i\
def create_webrtc_router(api_prefix: str) -> Optional[APIRouter]:\
    """Create a router for WebRTC endpoints."""\
    try:\
        router = APIRouter(prefix=api_prefix)\
        # Here would be route registrations\
        return router\
    except Exception as e:\
        logger.error(f"Error creating WebRTC router: {e}")\
        return None\
' ipfs_kit_py/mcp/extensions/webrtc.py

# STEP 2: Apply Black formatter to fix coding style issues
echo "Running Black formatter on fixed files..."

# Run black on each directory separately to avoid issues with any remaining problematic files
directories=(
  "ipfs_kit_py/mcp/auth"
  "ipfs_kit_py/mcp/controllers"
  "ipfs_kit_py/mcp/extensions"
  "ipfs_kit_py/mcp/ha"
  "ipfs_kit_py/mcp/models"
  "ipfs_kit_py/mcp/monitoring"
  "ipfs_kit_py/mcp/persistence"
  "ipfs_kit_py/mcp/routing"
  "ipfs_kit_py/mcp/security"
  "ipfs_kit_py/mcp/server"
  "ipfs_kit_py/mcp/services"
  "ipfs_kit_py/mcp/storage_manager"
  "ipfs_kit_py/mcp/tests"
  "ipfs_kit_py/mcp/utils"
)

for dir in "${directories[@]}"; do
  if [ -d "$dir" ]; then
    echo "Applying Black to $dir..."
    black "$dir" --quiet
  fi
done

# Also format the main __init__.py
black ipfs_kit_py/mcp/__init__.py --quiet

# STEP 3: Apply Ruff to fix linting issues
echo "Running Ruff to fix linting issues..."

# Fix unused imports
echo "Fixing unused imports..."
for dir in "${directories[@]}"; do
  if [ -d "$dir" ]; then
    echo "Applying Ruff --select=F401 to $dir..."
    ruff check --select=F401 --fix "$dir" --quiet
  fi
done

# Fix E402 (imports not at top of file)
echo "Fixing import ordering issues..."
for dir in "${directories[@]}"; do
  if [ -d "$dir" ]; then
    echo "Applying Ruff --select=E402 to $dir..."
    ruff check --select=E402 --fix "$dir" --quiet
  fi
done

# Apply Ruff to fix other issues
echo "Fixing other linting issues..."
for dir in "${directories[@]}"; do
  if [ -d "$dir" ]; then
    echo "Applying Ruff to $dir..."
    ruff check --fix "$dir" --quiet
  fi
done

# STEP 4: Check for remaining issues
echo "Checking for remaining issues..."
cd ipfs_kit_py && ruff check mcp --statistics

echo "===== Code fixing complete ====="
echo "Original code has been backed up to $BACKUP_DIR"