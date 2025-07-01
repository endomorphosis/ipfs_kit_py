#!/usr/bin/env python3
"""
Fix the patch_direct_mcp_server.py script by adding a proper shebang line
"""

import os

PATCH_SCRIPT = "./patch_direct_mcp_server.py"

def fix_patch_script():
    """Add shebang line to the patch script"""
    if not os.path.exists(PATCH_SCRIPT):
        print(f"❌ File not found: {PATCH_SCRIPT}")
        return False
    
    with open(PATCH_SCRIPT, 'r') as f:
        content = f.read()
    
    # Check if the file already has a shebang
    if content.startswith("#!/usr/bin/env python3"):
        print("✅ Patch script already has a shebang line")
        return True
    
    # Add the shebang line
    with open(PATCH_SCRIPT, 'w') as f:
        f.write("#!/usr/bin/env python3\n" + content)
    
    print("✅ Added shebang line to patch_direct_mcp_server.py")
    return True

if __name__ == "__main__":
    fix_patch_script()
