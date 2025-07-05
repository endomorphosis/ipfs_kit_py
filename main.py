#!/usr/bin/env python3
"""
IPFS Kit - Main Entry Point
============================

Quick access to common IPFS Kit functionality with daemon management.
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Main entry point with command menu"""
    print("\n🚀 IPFS Kit - Complete IPFS Integration with Daemon Management")
    print("=" * 60)
    print("1. Start MCP Server (with daemon initialization)")
    print("2. Start MCP Server (basic mode)")
    print("3. Initialize System (daemons + API keys)")
    print("4. Check System Status")
    print("5. Run Comprehensive Tests")
    print("6. Quick Verification")
    print("7. Exit")
    
    choice = input("\nSelect option (1-7): ").strip()
    
    if choice == "1":
        print("\n🔧 Starting MCP Server with full daemon initialization...")
        print("This will:")
        print("- Initialize all daemons (IPFS, Lotus, Lassie)")
        print("- Configure API keys for all services")
        print("- Start the MCP server with full functionality")
        
        # Run the enhanced MCP server with initialization
        subprocess.run([
            sys.executable, 
            "final_mcp_server_enhanced.py", 
            "--host", "0.0.0.0", 
            "--port", "9998",
            "--initialize"
        ])
        
    elif choice == "2":
        print("\n🔧 Starting MCP Server in basic mode...")
        print("This will start the server with mock implementations")
        
        # Run the enhanced MCP server without initialization
        subprocess.run([
            sys.executable, 
            "final_mcp_server_enhanced.py", 
            "--host", "0.0.0.0", 
            "--port", "9998"
        ])
        
    elif choice == "3":
        print("\n⚙️ Initializing System...")
        print("This will initialize all daemons and API keys")
        
        # Initialize system via API call
        import requests
        try:
            response = requests.post("http://localhost:9998/daemons/initialize")
            result = response.json()
            if result.get("success"):
                print("✅ System initialized successfully")
            else:
                print(f"❌ Initialization failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Failed to initialize system: {e}")
            print("Make sure the MCP server is running first")
            
    elif choice == "4":
        print("\n📊 Checking System Status...")
        
        # Check system status via API call
        import requests
        try:
            response = requests.get("http://localhost:9998/daemons/status")
            status = response.json()
            
            print(f"System initialized: {status.get('initialized', False)}")
            print(f"Uptime: {status.get('uptime', 'Unknown')}")
            
            print("\nDaemon Status:")
            for daemon, info in status.get('daemons', {}).items():
                running = info.get('running', False)
                pid = info.get('pid', 'Unknown')
                print(f"  {daemon}: {'✅ Running' if running else '❌ Stopped'} (PID: {pid})")
            
            print("\nAPI Key Status:")
            for service, info in status.get('api_keys', {}).items():
                status_text = info.get('status', 'unknown')
                print(f"  {service}: {status_text}")
                
        except Exception as e:
            print(f"❌ Failed to check status: {e}")
            print("Make sure the MCP server is running first")
            
    elif choice == "5":
        print("\n🧪 Running Comprehensive Tests...")
        subprocess.run([sys.executable, "final_comprehensive_test.py"])
        
    elif choice == "6":
        print("\n🔍 Running Quick Verification...")
        subprocess.run([sys.executable, "quick_verify.py"])
        
    elif choice == "7":
        print("\n👋 Goodbye!")
        return
        
    else:
        print("\n❌ Invalid choice. Please try again.")
        main()

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
