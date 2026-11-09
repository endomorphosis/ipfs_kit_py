#!/usr/bin/env python3
import re

filepath = 'ipfs_kit_py/mcp/extensions/routing.py'

with open(filepath, 'r') as file:
    content = file.read()

# Fix missing commas in import statements
fixed_content = re.sub(
    r'from typing import Dict List Any Optional',
    r'from typing import Dict, List, Any, Optional',
    content
)

# Fix pydantic imports
fixed_content = re.sub(
    r'from pydantic import BaseModel Field validator',
    r'from pydantic import BaseModel, Field, validator',
    fixed_content
)

# Fix malformed FastAPI imports
pattern = re.compile(r'APIRouter\s+HTTPException\s+Query\s+BackgroundTasks\s+Request', re.DOTALL)
replacement = 'APIRouter,\n    HTTPException,\n    Query,\n    BackgroundTasks,\n    Request'
fixed_content = pattern.sub(replacement, fixed_content)

with open(filepath, 'w') as file:
    file.write(fixed_content)

print(f"Fixed import statements in {filepath}")
