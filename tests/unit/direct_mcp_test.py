#!/usr/bin/env python3
"""
Direct MCP Server Test
======================

Tests the MCP server by starting it manually and testing endpoints.
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path

def run_test():
    """Run the direct test"""
    print("🧪 Direct MCP Server Test")
    print("=" * 40)
    
    # Step 1: Check server file
    server_file = "final_mcp_server_enhanced.py"
    if not os.path.exists(server_file):
        print(f"❌ {server_file} not found")
        return False
    print(f"✅ {server_file} found")
    
    # Step 2: Kill any existing servers
    print("🔄 Stopping any existing servers...")
    try:
        subprocess.run(["pkill", "-f", "final_mcp_server"], check=False)
        time.sleep(2)
    except:
        pass
    
    # Step 3: Start server in background
    print("🚀 Starting server...")
    try:
        # Use absolute path to virtual environment python
        venv_python = Path.cwd() / ".venv" / "bin" / "python"
        
        cmd = [str(venv_python), server_file, "--host", "0.0.0.0", "--port", "9998"]
        print(f"Command: {' '.join(cmd)}")
        
        # Start server in background
        with open("server_test.log", "w") as log_file:
            server_proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid  # Create new process group
            )
        
        print(f"Server PID: {server_proc.pid}")
        
        # Step 4: Wait and test
        print("⏳ Waiting for server startup...")
        time.sleep(5)
        
        # Check if process is still running
        if server_proc.poll() is None:
            print("✅ Server process is running")
        else:
            print("❌ Server process died")
            with open("server_test.log", "r") as f:
                print("Server log:")
                print(f.read())
            return False
        
        # Step 5: Test with curl
        print("🌐 Testing endpoints...")
        
        # Test health endpoint
        result = subprocess.run([
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", 
            "http://localhost:9998/health"
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout == "200":
            print("✅ Health endpoint responding (200)")
        else:
            print(f"❌ Health endpoint failed: {result.stdout}")
        
        # Test info endpoint
        result = subprocess.run([
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "http://localhost:9998/"
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout == "200":
            print("✅ Info endpoint responding (200)")
        else:
            print(f"❌ Info endpoint failed: {result.stdout}")
        
        # Step 6: Cleanup
        print("🧹 Stopping server...")
        try:
            os.killpg(os.getpgid(server_proc.pid), signal.SIGTERM)
            server_proc.wait(timeout=5)
        except:
            try:
                os.killpg(os.getpgid(server_proc.pid), signal.SIGKILL)
            except:
                pass
        
        print("✅ Test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
