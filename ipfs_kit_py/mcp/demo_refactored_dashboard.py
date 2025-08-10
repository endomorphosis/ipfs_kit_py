#!/usr/bin/env python3
"""
Demo script to showcase the refactored MCP dashboard

This demonstrates the benefits of the new modular structure:
- Separated HTML, CSS, and JavaScript
- Template-based rendering
- Static file serving
- Better maintainability
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    print("🎉 IPFS Kit MCP Dashboard - Refactored Demo")
    print("=" * 50)
    
    # Check if refactored files exist
    mcp_dir = Path(__file__).parent  # Current directory (mcp)
    template_path = mcp_dir / "dashboard_templates" / "unified_dashboard.html"
    css_path = mcp_dir / "dashboard_static" / "css" / "dashboard.css"
    js_path = mcp_dir / "dashboard_static" / "js" / "dashboard.js"
    server_path = mcp_dir / "refactored_unified_dashboard.py"
    
    print("📁 Checking refactored file structure...")
    files_exist = {
        "HTML Template": template_path.exists(),
        "CSS Styles": css_path.exists(),
        "JavaScript": js_path.exists(),
        "Python Server": server_path.exists()
    }
    
    for name, exists in files_exist.items():
        status = "✅" if exists else "❌"
        print(f"  {status} {name}: {exists}")
    
    if all(files_exist.values()):
        print("\n🚀 All refactored components are ready!")
        print("\nRefactoring Benefits:")
        print("  ✅ Separated concerns (HTML, CSS, JS)")
        print("  ✅ Template-based rendering with Jinja2")
        print("  ✅ Static file serving")
        print("  ✅ Better maintainability")
        print("  ✅ Easier to modify and extend")
        print("  ✅ Clean code organization")
        
        print(f"\n📋 File Locations:")
        print(f"  HTML: {template_path}")
        print(f"  CSS:  {css_path}")
        print(f"  JS:   {js_path}")
        print(f"  Server: {server_path}")
        
        print(f"\n🔧 To run the refactored dashboard:")
        print(f"  python -m ipfs_kit_py.mcp.refactored_unified_dashboard")
        print(f"  # OR")
        print(f"  cd {mcp_dir}")
        print(f"  python refactored_unified_dashboard.py")
        
        response = input("\n❓ Would you like to start the refactored dashboard now? (y/N): ")
        if response.lower().startswith('y'):
            print("\n🚀 Starting refactored dashboard...")
            try:
                subprocess.run([
                    sys.executable, "-m", "ipfs_kit_py.mcp.refactored_unified_dashboard"
                ], cwd=Path(__file__).parent.parent)
            except KeyboardInterrupt:
                print("\n🛑 Dashboard stopped.")
            except Exception as e:
                print(f"\n❌ Error starting dashboard: {e}")
                print("💡 Try running manually:")
                print(f"   cd {Path(__file__).parent}")
                print(f"   python -m ipfs_kit_py.mcp.refactored_unified_dashboard")
    else:
        print("\n❌ Some refactored components are missing!")
        print("💡 Please ensure all files were created properly.")

if __name__ == "__main__":
    main()
