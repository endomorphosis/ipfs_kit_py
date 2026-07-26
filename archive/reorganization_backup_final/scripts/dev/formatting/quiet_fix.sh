#!/bin/bash

# Redirect all output to a log file
LOG_FILE="code_fixes.log"
exec > "$LOG_FILE" 2>&1

echo "===== Starting Code Fixes $(date) ====="

# First, fix the syntax errors in the problematic files
echo "Fixing specific syntax errors in problematic files..."

# Fix the cli_controller.py file - first create a backup
cp ipfs_kit_py/mcp/controllers/cli_controller.py ipfs_kit_py/mcp/controllers/cli_controller.py.bak

# Edit the file to fix the specific syntax errors
# Import section seems incomplete - fix it
sed -i '17,27c\
try:\
    import anyio\
    import sniffio\
    HAS_ANYIO = True\
except ImportError:\
    HAS_ANYIO = False\
\
# Import FastAPI components\
from fastapi import APIRouter, HTTPException, Body, Query, Path, Response, Request\
from fastapi.responses import StreamingResponse\
from pydantic import BaseModel, Field\
from enum import Enum\
from typing import Any, Dict, List, Optional' ipfs_kit_py/mcp/controllers/cli_controller.py

# Fix duplicated shutdown method
sed -i '/def sync_shutdown/,/sync_shutdown completed successfully/d' ipfs_kit_py/mcp/controllers/cli_controller.py

# Fix the yaml formatting section that's missing a proper dictionary structure
sed -i '/try:/,/except Exception as e:/c\
                try:\
                    formatted_result = {\
                        "yaml_output": yaml.dump(result, default_flow_style=False)\
                    }\
                except Exception as e:' ipfs_kit_py/mcp/controllers/cli_controller.py

# Now run Black on the fixed files
echo "Running Black on fixed files..."
black ipfs_kit_py/mcp/controllers/cli_controller.py --quiet

# Run Ruff with fixes on the same files
echo "Running Ruff on fixed files..."
ruff check --fix --quiet ipfs_kit_py/mcp/controllers/cli_controller.py

# Process specific directories with Black and Ruff
for dir in auth controllers extensions ha models monitoring persistence routing security server services storage_manager tests utils; do
    echo "Processing ipfs_kit_py/mcp/$dir with Black and Ruff..."
    black ipfs_kit_py/mcp/$dir --quiet
    ruff check --fix --quiet ipfs_kit_py/mcp/$dir
done

# Process the main init file
echo "Processing ipfs_kit_py/mcp/__init__.py with Black and Ruff..."
black ipfs_kit_py/mcp/__init__.py --quiet
ruff check --fix --quiet ipfs_kit_py/mcp/__init__.py

echo "===== Completed code formatting and linting fixes $(date) ====="

# Create a summary report
echo "===== Code Fix Summary =====" | tee /dev/tty
echo "Fix process completed at $(date)" | tee -a /dev/tty
echo "Log file: $LOG_FILE" | tee -a /dev/tty
echo "Checking remaining issues:" | tee -a /dev/tty
cd ipfs_kit_py && ruff check mcp --statistics | tee -a /dev/tty