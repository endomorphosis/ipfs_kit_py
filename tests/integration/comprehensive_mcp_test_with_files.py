#!/usr/bin/env python3
"""
Comprehensive MCP Tools Test with File Output
==============================================

This test writes all results to files for debugging.
"""

import os
import sys
import json
import time
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

def write_log(message):
    """Write message to log file"""
    with open("test_output.log", "a") as f:
        f.write(f"{datetime.now().isoformat()}: {message}\n")
    print(message)  # Also try to print

def test_mcp_functionality():
    """Test MCP server functionality"""
    results = {
        "start_time": datetime.now().isoformat(),
        "tests": {},
        "summary": {"passed": 0, "failed": 0}
    }
    
    write_log("🧪 Starting Comprehensive MCP Test Suite")
    
    # Test 1: Check if server file exists
    server_file = "final_mcp_server_enhanced.py"
    if os.path.exists(server_file):
        results["tests"]["server_file_exists"] = {"status": "PASS", "message": f"{server_file} found"}
        results["summary"]["passed"] += 1
        write_log(f"✅ {server_file} exists")
    else:
        results["tests"]["server_file_exists"] = {"status": "FAIL", "message": f"{server_file} not found"}
        results["summary"]["failed"] += 1
        write_log(f"❌ {server_file} not found")
        
    # Test 2: Check Python syntax
    try:
        result = subprocess.run([
            sys.executable, "-m", "py_compile", server_file
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            results["tests"]["syntax_check"] = {"status": "PASS", "message": "Python syntax valid"}
            results["summary"]["passed"] += 1
            write_log("✅ Python syntax check passed")
        else:
            results["tests"]["syntax_check"] = {"status": "FAIL", "message": f"Syntax error: {result.stderr}"}
            results["summary"]["failed"] += 1
            write_log(f"❌ Python syntax error: {result.stderr}")
    except Exception as e:
        results["tests"]["syntax_check"] = {"status": "FAIL", "message": f"Syntax check failed: {e}"}
        results["summary"]["failed"] += 1
        write_log(f"❌ Syntax check exception: {e}")
    
    # Test 3: Test module imports
    test_imports = """
import sys
print(f"Python version: {sys.version}")

try:
    import fastapi
    print(f"FastAPI: {fastapi.__version__}")
except Exception as e:
    print(f"FastAPI error: {e}")

try:
    import uvicorn
    print("Uvicorn: OK")
except Exception as e:
    print(f"Uvicorn error: {e}")

try:
    import requests
    print(f"Requests: {requests.__version__}")
except Exception as e:
    print(f"Requests error: {e}")
"""
    
    try:
        venv_python = Path.cwd() / ".venv" / "bin" / "python"
        result = subprocess.run([
            str(venv_python), "-c", test_imports
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            results["tests"]["module_imports"] = {"status": "PASS", "message": "All modules imported", "output": result.stdout}
            results["summary"]["passed"] += 1
            write_log("✅ Module imports successful")
            write_log(f"Import output: {result.stdout}")
        else:
            results["tests"]["module_imports"] = {"status": "FAIL", "message": f"Import failed: {result.stderr}", "output": result.stdout}
            results["summary"]["failed"] += 1
            write_log(f"❌ Module import failed: {result.stderr}")
    except Exception as e:
        results["tests"]["module_imports"] = {"status": "FAIL", "message": f"Import test failed: {e}"}
        results["summary"]["failed"] += 1
        write_log(f"❌ Module import test exception: {e}")
    
    # Test 4: Try to start server
    try:
        write_log("🚀 Attempting to start server...")
        
        # Kill any existing servers
        subprocess.run(["pkill", "-f", "final_mcp_server"], check=False)
        time.sleep(2)
        
        venv_python = Path.cwd() / ".venv" / "bin" / "python"
        cmd = [str(venv_python), server_file, "--host", "0.0.0.0", "--port", "9999"]
        
        with open("server_startup.log", "w") as log_file:
            server_proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT
            )
        
        write_log(f"Server started with PID: {server_proc.pid}")
        
        # Wait for startup
        time.sleep(5)
        
        # Check if still running
        if server_proc.poll() is None:
            results["tests"]["server_startup"] = {"status": "PASS", "message": f"Server running (PID: {server_proc.pid})"}
            results["summary"]["passed"] += 1
            write_log("✅ Server started successfully")
            
            # Test 5: Test endpoints with curl
            endpoints_to_test = [
                ("health", "http://localhost:9999/health"),
                ("info", "http://localhost:9999/"),
                ("tools", "http://localhost:9999/mcp/tools")
            ]
            
            for name, url in endpoints_to_test:
                try:
                    result = subprocess.run([
                        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", 
                        "--max-time", "5", url
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0 and result.stdout == "200":
                        results["tests"][f"endpoint_{name}"] = {"status": "PASS", "message": f"{name} endpoint responding"}
                        results["summary"]["passed"] += 1
                        write_log(f"✅ {name} endpoint OK (200)")
                    else:
                        results["tests"][f"endpoint_{name}"] = {"status": "FAIL", "message": f"{name} endpoint failed: {result.stdout}"}
                        results["summary"]["failed"] += 1
                        write_log(f"❌ {name} endpoint failed: {result.stdout}")
                        
                except Exception as e:
                    results["tests"][f"endpoint_{name}"] = {"status": "FAIL", "message": f"{name} endpoint test failed: {e}"}
                    results["summary"]["failed"] += 1
                    write_log(f"❌ {name} endpoint test exception: {e}")
            
            # Test 6: Test IPFS operations
            try:
                # Test add operation
                add_data = '{"content": "Hello, IPFS test!"}'
                result = subprocess.run([
                    "curl", "-s", "-X", "POST", 
                    "-H", "Content-Type: application/json",
                    "-d", add_data,
                    "--max-time", "10",
                    "http://localhost:9999/ipfs/add"
                ], capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0 and "cid" in result.stdout:
                    results["tests"]["ipfs_add"] = {"status": "PASS", "message": "IPFS add operation successful", "response": result.stdout}
                    results["summary"]["passed"] += 1
                    write_log("✅ IPFS add operation successful")
                    
                    # Extract CID for cat test
                    try:
                        import json
                        response_data = json.loads(result.stdout)
                        cid = response_data.get("cid")
                        
                        if cid:
                            # Test cat operation
                            cat_result = subprocess.run([
                                "curl", "-s", "--max-time", "10",
                                f"http://localhost:9999/ipfs/cat/{cid}"
                            ], capture_output=True, text=True, timeout=15)
                            
                            if cat_result.returncode == 0 and "content" in cat_result.stdout:
                                results["tests"]["ipfs_cat"] = {"status": "PASS", "message": "IPFS cat operation successful"}
                                results["summary"]["passed"] += 1
                                write_log("✅ IPFS cat operation successful")
                            else:
                                results["tests"]["ipfs_cat"] = {"status": "FAIL", "message": f"IPFS cat failed: {cat_result.stdout}"}
                                results["summary"]["failed"] += 1
                                write_log(f"❌ IPFS cat failed: {cat_result.stdout}")
                    except:
                        write_log("⚠️ Could not extract CID for cat test")
                        
                else:
                    results["tests"]["ipfs_add"] = {"status": "FAIL", "message": f"IPFS add failed: {result.stdout}"}
                    results["summary"]["failed"] += 1
                    write_log(f"❌ IPFS add failed: {result.stdout}")
                    
            except Exception as e:
                results["tests"]["ipfs_operations"] = {"status": "FAIL", "message": f"IPFS operations test failed: {e}"}
                results["summary"]["failed"] += 1
                write_log(f"❌ IPFS operations test exception: {e}")
            
            # Cleanup: Stop server
            try:
                server_proc.terminate()
                server_proc.wait(timeout=5)
                write_log("🛑 Server stopped")
            except:
                server_proc.kill()
                write_log("🛑 Server killed")
                
        else:
            # Server didn't start
            results["tests"]["server_startup"] = {"status": "FAIL", "message": f"Server failed to start (exit code: {server_proc.returncode})"}
            results["summary"]["failed"] += 1
            write_log(f"❌ Server failed to start (exit code: {server_proc.returncode})")
            
            # Read startup log
            try:
                with open("server_startup.log", "r") as f:
                    startup_log = f.read()
                write_log(f"Server startup log: {startup_log}")
                results["tests"]["server_startup"]["startup_log"] = startup_log
            except:
                pass
                
    except Exception as e:
        results["tests"]["server_startup"] = {"status": "FAIL", "message": f"Server startup test failed: {e}"}
        results["summary"]["failed"] += 1
        write_log(f"❌ Server startup test exception: {e}")
        write_log(f"Traceback: {traceback.format_exc()}")
    
    # Cleanup any remaining processes
    try:
        subprocess.run(["pkill", "-f", "final_mcp_server"], check=False)
    except:
        pass
    
    # Save results
    results["end_time"] = datetime.now().isoformat()
    
    with open("mcp_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Summary
    write_log("="*50)
    write_log("🧪 MCP TEST SUMMARY")
    write_log("="*50)
    write_log(f"✅ Tests Passed: {results['summary']['passed']}")
    write_log(f"❌ Tests Failed: {results['summary']['failed']}")
    write_log(f"📄 Results saved to: mcp_test_results.json")
    write_log(f"📄 Logs saved to: test_output.log")
    
    if results["summary"]["failed"] > 0:
        write_log("🚨 Some tests failed - check logs for details")
        return False
    else:
        write_log("🎉 All tests passed!")
        return True

if __name__ == "__main__":
    # Clear previous logs
    for log_file in ["test_output.log", "server_startup.log", "mcp_test_results.json"]:
        if os.path.exists(log_file):
            os.remove(log_file)
    
    success = test_mcp_functionality()
    sys.exit(0 if success else 1)
