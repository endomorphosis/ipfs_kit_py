#!/usr/bin/env python3
"""
This script fixes syntax errors in the cli_controller.py file.
"""

import re

# Path to the file
file_path = "ipfs_kit_py/mcp/controllers/cli_controller.py"

with open(file_path, "r") as f:
    content = f.read()

# Fix the import error section
import_section_pattern = r"try:\s+import anyio\s+import sniffio\s+HAS_ANYIO = True\s+except ImportError:\s+(HTTPException,\s+Body,\s+Query,\s+Path,\s+Response,\s+Request,\s+)"
import_section_replacement = """try:
    import anyio
    import sniffio

    HAS_ANYIO = True
except ImportError:
    HAS_ANYIO = False

# FastAPI imports
from fastapi import (
    APIRouter,
    HTTPException,
    Body,
    Query,
    Path,
    Response,
    Request,
)"""

content = re.sub(import_section_pattern, import_section_replacement, content)

# Fix the YAML formatting section
yaml_section_pattern = r'if command_request\.format == FormatType\.YAML:\s+import yaml\s+try:\s+"yaml_output": yaml\.dump\(result, default_flow_style=False\)\s+\}\s+except Exception as e:'
yaml_section_replacement = """if command_request.format == FormatType.YAML:
                import yaml

                try:
                    formatted_result = {
                        "yaml_output": yaml.dump(result, default_flow_style=False)
                    }
                except Exception as e:"""

content = re.sub(yaml_section_pattern, yaml_section_replacement, content)

# Fix any duplicate async shutdown methods
content = re.sub(r"(async def shutdown.*?sync_shutdown completed successfully\"\s+)(\s+try:.*?sync_shutdown completed successfully\"\s+)", r"\1", content, flags=re.DOTALL)

# Write the fixed content back to the file
with open(file_path, "w") as f:
    f.write(content)

print(f"Fixed syntax errors in {file_path}")
