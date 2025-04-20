#!/usr/bin/env python3
import re

filepath = 'ipfs_kit_py/mcp/persistence/migration_store.py'

with open(filepath, 'r') as file:
    content = file.read()

# Fix missing comma in migration.get()
fixed_content = re.sub(
    r'status = migration\.get\("status" "unknown"\)',
    r'status = migration.get("status", "unknown")',
    content
)

with open(filepath, 'w') as file:
    file.write(fixed_content)

print(f"Fixed migration.get() call in {filepath}")
