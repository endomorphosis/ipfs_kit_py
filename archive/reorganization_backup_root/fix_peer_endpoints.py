#!/usr/bin/env python3
"""
Fix peer endpoints to use proper async initialization pattern.
"""

import re

def fix_peer_endpoints():
    file_path = "/home/devel/ipfs_kit_py/mcp/ipfs_kit/api/peer_endpoints.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern to find methods that check peer_manager
    pattern = r'(async def [^:]+:\s*"""[^"]*"""\s*try:\s*)if not self\.peer_manager:\s*return \{"success": False, "error": "Peer manager not initialized"\}'
    
    # Replace with proper initialization
    replacement = r'\1await self._ensure_peer_manager()\n            if not self.peer_manager:\n                return {"success": False, "error": "Peer manager not initialized"}'
    
    content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    # Also handle simpler cases
    simple_pattern = r'(\s+)if not self\.peer_manager:\s*return \{"success": False, "error": "Peer manager not initialized"\}'
    simple_replacement = r'\1await self._ensure_peer_manager()\n\1if not self.peer_manager:\n\1    return {"success": False, "error": "Peer manager not initialized"}'
    
    content = re.sub(simple_pattern, simple_replacement, content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("Fixed peer endpoints async initialization")

if __name__ == "__main__":
    fix_peer_endpoints()
