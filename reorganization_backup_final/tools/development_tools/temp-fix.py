#!/usr/bin/env python3
import re

filepath = 'ipfs_kit_py/mcp/storage_manager/manager.py'

with open(filepath, 'r') as file:
    content = file.read()

# Fix missing comma in import
fixed_content = re.sub(
    r'from ipfs_kit_py.mcp.controllers.migration_controller import MigrationController MigrationPolicy',
    r'from ipfs_kit_py.mcp.controllers.migration_controller import MigrationController, MigrationPolicy',
    content
)

with open(filepath, 'w') as file:
    file.write(fixed_content)

print(f"Fixed migration_controller import in {filepath}")
