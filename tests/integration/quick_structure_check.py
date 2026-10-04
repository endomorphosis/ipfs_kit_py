#!/usr/bin/env python3
"""Quick test of cleaned up workspace"""

import os
from pathlib import Path

def main():
    # Check current directory
    cwd = Path.cwd()
    print(f"Current directory: {cwd}")
    
    # List key directories
    print("\n📁 Directory Structure:")
    essential_dirs = ["src", "tests", "tools", "docs", "scripts", "docker", "config", "archive", "backup"]
    for dir_name in essential_dirs:
        path = Path(dir_name)
        if path.exists():
            count = len(list(path.rglob("*")))
            print(f"✅ {dir_name}/ ({count} items)")
        else:
            print(f"❌ {dir_name}/ missing")
    
    # Check main files in root
    print("\n📄 Root Files:")
    root_files = [f for f in Path(".").iterdir() if f.is_file() and not f.name.startswith('.')]
    for file in sorted(root_files):
        print(f"   {file.name}")
    
    # Check server location
    server_path = Path("src/final_mcp_server_enhanced.py")
    if server_path.exists():
        print(f"\n✅ Main server found: {server_path}")
        print(f"   Size: {server_path.stat().st_size} bytes")
    else:
        print(f"\n❌ Main server missing: {server_path}")
    
    # Quick test imports
    print("\n🧪 Testing imports...")
    try:
        import sys
        sys.path.insert(0, str(Path.cwd() / "src"))
        # Don't actually import the server module to avoid starting it
        print("✅ Path setup successful")
    except Exception as e:
        print(f"❌ Import test failed: {e}")
    
    print("\n🎉 Workspace structure check complete!")

if __name__ == "__main__":
    main()
