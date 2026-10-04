#!/bin/bash
# Script to fix remaining issues in ipfs_kit_py/mcp

echo "Fixing remaining issues in ipfs_kit_py/mcp"
echo "-----------------------------------------"

# Fix missing time imports
echo "Fixing missing time imports..."
for file in $(grep -l "time\.time()" ipfs_kit_py/mcp/controllers/storage/s3_controller_anyio.py ipfs_kit_py/mcp/controllers/storage/storacha_controller_anyio.py ipfs_kit_py/mcp/controllers/ipfs_controller.py); do
  if ! grep -q "^import time" "$file"; then
    sed -i '1,10 s/^import logging/import logging\nimport time/' "$file"
    echo "Added time import to $file"
  fi
done

# Fix missing imports in filecoin_controller_anyio.py
echo "Fixing filecoin_controller_anyio.py..."
if grep -q "logger =" ipfs_kit_py/mcp/controllers/storage/filecoin_controller_anyio.py; then
  if ! grep -q "^import logging" ipfs_kit_py/mcp/controllers/storage/filecoin_controller_anyio.py; then
    sed -i '1,10 s/from ipfs_kit_py.mcp.controllers.storage.filecoin_controller/import logging\nimport time\nimport sniffio\n\nfrom ipfs_kit_py.mcp.controllers.storage.filecoin_controller/' ipfs_kit_py/mcp/controllers/storage/filecoin_controller_anyio.py
    echo "Added imports to filecoin_controller_anyio.py"
  fi
fi

# Fix missing imports in ipfs_storage_controller.py and s3_storage_controller.py
echo "Fixing storage controller imports..."
for file in ipfs_kit_py/mcp/controllers/storage/ipfs_storage_controller.py ipfs_kit_py/mcp/controllers/storage/s3_storage_controller.py; do
  if ! grep -q "^import logging" "$file"; then
    sed -i '1i import logging\nfrom typing import Dict, Any' "$file"
    echo "Added imports to $file"
  fi
done

# Fix prometheus imports
echo "Fixing prometheus.py imports..."
if grep -q "Info(" ipfs_kit_py/mcp/monitoring/prometheus.py; then
  if ! grep -q "Info," ipfs_kit_py/mcp/monitoring/prometheus.py; then
    sed -i 's/from prometheus_client import (/from prometheus_client import (\n        Info,/' ipfs_kit_py/mcp/monitoring/prometheus.py
    echo "Added Info import to prometheus.py"
  fi
fi

# Fix missing CONTENT_TYPE_LATEST in metrics.py
echo "Fixing metrics.py imports..."
if grep -q "CONTENT_TYPE_LATEST" ipfs_kit_py/mcp/extensions/metrics.py; then
  if ! grep -q "CONTENT_TYPE_LATEST," ipfs_kit_py/mcp/extensions/metrics.py; then
    sed -i 's/from prometheus_client import generate_latest/from prometheus_client import generate_latest, CONTENT_TYPE_LATEST/' ipfs_kit_py/mcp/extensions/metrics.py
    echo "Added CONTENT_TYPE_LATEST import to metrics.py"
  fi
fi

# Fix extended_features.py content_generator issue
echo "Fixing extended_features.py..."
if grep -q "content_generator(" ipfs_kit_py/mcp/extensions/extended_features.py; then
  sed -i '/content_generator()/i \ \ \ \ \ \ \ \ \ \ \ \ # Define the content generator function\n                def content_generator():' ipfs_kit_py/mcp/extensions/extended_features.py
  echo "Added content_generator function definition to extended_features.py"
fi

# Run Black and Ruff again after fixes
echo "Re-applying Black and Ruff..."
black ipfs_kit_py/mcp --quiet || echo "Black formatting encountered some errors (continuing)"
ruff check --fix ipfs_kit_py/mcp || echo "Ruff fixes applied with some errors (continuing)"

echo "-----------------------------------------"
echo "Fixes completed. Remaining issues may require manual attention."
echo "Run the following to see remaining issues:"
echo "  ruff check ipfs_kit_py/mcp"