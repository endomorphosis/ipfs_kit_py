#!/usr/bin/env python3
"""
Simple test to verify the final MCP server functionality
"""

import os
import sys
import subprocess
import time
import requests
import signal

def test_server():
    """Test the final MCP server"""
    print("🧪 Testing Final MCP Server")
    print("=" * 50)
    
    # Check if server file exists
    if not os.path.exists("final_mcp_server.py"):
        print("❌ final_mcp_server.py not found")
        return False
    
    print("✅ Server file found")
    
    # Test Python syntax
    try:
        result = subprocess.run([
            sys.executable, "-m", "py_compile", "final_mcp_server.py"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Python syntax is valid")
        else:
            print(f"❌ Syntax error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Syntax check timed out")
        return False
    except Exception as e:
        print(f"❌ Syntax check failed: {e}")
        return False
    
    # Try to import the module
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("final_mcp_server", "final_mcp_server.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print("✅ Module imports successfully")
        print(f"   Version: {getattr(module, '__version__', 'Unknown')}")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test starting the server
    print("\n🚀 Starting server...")
    
    try:
        # Start server in background
        process = subprocess.Popen([
            sys.executable, "final_mcp_server.py", 
            "--host", "127.0.0.1", 
            "--port", "9999"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        time.sleep(3)
        
        # Test health endpoint
        try:
            response = requests.get("http://127.0.0.1:9999/health", timeout=5)
            if response.status_code == 200:
                print("✅ Server is responding")
                data = response.json()
                print(f"   Status: {data.get('status', 'Unknown')}")
                print(f"   Version: {data.get('version', 'Unknown')}")
            else:
                print(f"❌ Server responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to server: {e}")
        
        # Test API endpoints
        try:
            # Test add endpoint
            add_response = requests.post(
                "http://127.0.0.1:9999/ipfs/add",
                json={"content": "Hello, IPFS!"},
                timeout=5
            )
            if add_response.status_code == 200:
                print("✅ IPFS add endpoint works")
                cid = add_response.json().get("cid")
                
                # Test cat endpoint
                cat_response = requests.get(f"http://127.0.0.1:9999/ipfs/cat/{cid}", timeout=5)
                if cat_response.status_code == 200:
                    print("✅ IPFS cat endpoint works")
                else:
                    print(f"❌ IPFS cat failed: {cat_response.status_code}")
            else:
                print(f"❌ IPFS add failed: {add_response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ API test failed: {e}")
        
    except Exception as e:
        print(f"❌ Server start failed: {e}")
        return False
    
    finally:
        # Clean up
        try:
            process.terminate()
            process.wait(timeout=5)
            print("✅ Server stopped cleanly")
        except:
            try:
                process.kill()
                print("⚠️ Server force-stopped")
            except:
                pass
    
    print("\n" + "=" * 50)
    print("🎉 Test completed!")
    return True

if __name__ == "__main__":
    # Change to project directory
    os.chdir("/home/barberb/ipfs_kit_py")
    
    # Run test
    test_server()
