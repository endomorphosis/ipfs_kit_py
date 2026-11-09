#!/usr/bin/env python3
import re

filepath = 'ipfs_kit_py/mcp/persistence/cache_manager.py'

with open(filepath, 'r') as file:
    content = file.read()

# Fix __init__ method definition
pattern = re.compile(r'def __init__\(self\s+self\s+base_path: str = None\s+memory_limit: int = 100 \* 1024 \* 1024\s+# 100 MB\s+disk_limit: int = 1024 \* 1024 \* 1024\s+# 1 GB\s+debug_mode: bool = False\s+config: Dict\[str Any\] = None\s+\):', re.DOTALL)
replacement = 'def __init__(self,\n        base_path: str = None,\n        memory_limit: int = 100 * 1024 * 1024,  # 100 MB\n        disk_limit: int = 1024 * 1024 * 1024,  # 1 GB\n        debug_mode: bool = False,\n        config: Dict[str, Any] = None\n    ):'
fixed_content = pattern.sub(replacement, content)

with open(filepath, 'w') as file:
    file.write(fixed_content)

print(f"Fixed __init__ method in {filepath}")
