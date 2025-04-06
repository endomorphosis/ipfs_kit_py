import os
import re
import sys


file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/tiered_cache.py'

with open(file_path, 'r') as f:
    content = f.read()

# Fix the syntax error by properly nesting the try/except blocks
pattern = r'(partition_path = os\.path\.join\(self\.directory, filename\)[\s\n]+)# Get metadata without loading full content[\s\n]+metadata = pq\.read_metadata\(partition_path\)[\s\n]+([\s\n]+partitions\[partition_id\] = \{[^}]+\}[\s\n]+)except Exception as e:'
replacement = r'\1try:\n    # Get metadata without loading full content\n    metadata = pq.read_metadata(partition_path)\n\2except Exception as e:'

fixed_content = re.sub(pattern, replacement, content)

with open(file_path, 'w') as f:
    f.write(fixed_content)

print("Fix applied successfully!")
