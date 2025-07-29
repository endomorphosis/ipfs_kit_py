#!/usr/bin/env python3
"""
Clean up duplicate await self._ensure_peer_manager() calls.
"""

def clean_duplicates():
    file_path = "/home/devel/ipfs_kit_py/mcp/ipfs_kit/api/peer_endpoints.py"
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    cleaned_lines = []
    prev_line = ""
    
    for line in lines:
        # Skip duplicate await self._ensure_peer_manager() calls
        if "await self._ensure_peer_manager()" in line and "await self._ensure_peer_manager()" in prev_line:
            continue
        cleaned_lines.append(line)
        prev_line = line
    
    with open(file_path, 'w') as f:
        f.writelines(cleaned_lines)
    
    print("Cleaned up duplicate await calls")

if __name__ == "__main__":
    clean_duplicates()
