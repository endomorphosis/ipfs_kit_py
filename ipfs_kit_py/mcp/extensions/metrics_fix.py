#!/usr/bin/env python3
import re

filepath = 'ipfs_kit_py/mcp/extensions/metrics.py'

with open(filepath, 'r') as file:
    content = file.read()

# Fix missing commas in dictionary
pattern = re.compile(r'success": True\s+(".*?": .*?)(?=\s+\"|\s+\})', re.DOTALL)
replacement = 'success": True,\n            \\1,'
fixed_content = pattern.sub(replacement, content)

# Fix the indentation and add missing commas
fixed_content = re.sub(
    r'success": True\s+"status": "available"\s+"system_info": system_info\s+"prometheus_enabled": PROMETHEUS_AVAILABLE',
    r'success": True,\n            "status": "available",\n            "system_info": system_info,\n            "prometheus_enabled": PROMETHEUS_AVAILABLE',
    fixed_content
)

with open(filepath, 'w') as file:
    file.write(fixed_content)

print(f"Fixed dictionary syntax in {filepath}")
