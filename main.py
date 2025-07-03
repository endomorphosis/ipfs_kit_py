#!/usr/bin/env python3
"""
IPFS Kit - Main Entry Point
============================

Quick access to common IPFS Kit functionality.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Main entry point with command menu"""
    print("\n🚀 IPFS Kit - Complete IPFS Integration")
    print("=" * 40)
    print("1. Start MCP Server")
    print("2. Run Tests")
    print("3. Check IPFS Status")
    print("4. Initialize Environment")
    print("5. Exit")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == "1":
        print("\n🔧 Starting MCP Server...")
        from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import main as mcp_main
        mcp_main()
    elif choice == "2":
        print("\n🧪 Running Tests...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pytest", "tests/"], cwd=Path(__file__).parent)
    elif choice == "3":
        print("\n📊 Checking IPFS Status...")
        from mcp.ipfs_kit.core.service_manager import service_manager
        status = service_manager.get_service_status("ipfs")
        print(f"IPFS Status: {status}")
    elif choice == "4":
        print("\n⚙️ Initializing Environment...")
        import subprocess
        subprocess.run([sys.executable, "scripts/initialize_phase2.py"], cwd=Path(__file__).parent)
    elif choice == "5":
        print("\n👋 Goodbye!")
        return
    else:
        print("\n❌ Invalid choice. Please try again.")
        main()

if __name__ == "__main__":
    main()
