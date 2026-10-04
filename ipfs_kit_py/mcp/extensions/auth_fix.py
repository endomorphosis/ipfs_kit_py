#!/usr/bin/env python3
import re

filepath = 'ipfs_kit_py/mcp/extensions/auth.py'

with open(filepath, 'r') as file:
    content = file.read()

# Fix missing commas in import statements
fixed_content = re.sub(
    r'from typing import Dict Any Optional',
    r'from typing import Dict, Any, Optional',
    content
)

# Fix OAuth2 imports
fixed_content = re.sub(
    r'from fastapi.security import OAuth2PasswordBearer OAuth2PasswordRequestForm',
    r'from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm',
    fixed_content
)

# Fix APIKey imports
fixed_content = re.sub(
    r'from fastapi.security.api_key import APIKeyHeader APIKeyQuery',
    r'from fastapi.security.api_key import APIKeyHeader, APIKeyQuery',
    fixed_content
)

# Fix malformed FastAPI imports
pattern = re.compile(r'from fastapi import \(\s+APIRouter\s+Depends\s+HTTPException', re.DOTALL)
replacement = 'from fastapi import (\n    APIRouter,\n    Depends,\n    HTTPException'
fixed_content = pattern.sub(replacement, fixed_content)

with open(filepath, 'w') as file:
    file.write(fixed_content)

print(f"Fixed import statements in {filepath}")
