#!/bin/bash

# First, fix the syntax errors in the particularly problematic files
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
black ipfs_kit_py/mcp/controllers/cli_controller.py

# Run Ruff with fixes on the same files
echo "Running Ruff on fixed files..."
ruff check --fix ipfs_kit_py/mcp/controllers/cli_controller.py

# Now, now that we've fixed the critical syntax errors, use the original script to fix the rest
echo "Running Black on all files in ipfs_kit_py/mcp..."
black ipfs_kit_py/mcp

echo "Running Ruff with fixes on all files in ipfs_kit_py/mcp..."
ruff check --fix ipfs_kit_py/mcp

echo "Completed code formatting and linting fixes!"