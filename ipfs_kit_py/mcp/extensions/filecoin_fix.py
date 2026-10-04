#!/usr/bin/env python3
import re

filepath = 'ipfs_kit_py/mcp/extensions/filecoin.py'

with open(filepath, 'r') as file:
    content = file.read()

# Fix missing commas in import statements
fixed_content = re.sub(
    r'from fastapi import APIRouter HTTPException Form',
    r'from fastapi import APIRouter, HTTPException, Form',
    content
)

fixed_content = re.sub(
    r'from typing import Optional Dict Any',
    r'from typing import Optional, Dict, Any',
    fixed_content
)

with open(filepath, 'w') as file:
    file.write(fixed_content)

print(f"Fixed import statements in {filepath}")
