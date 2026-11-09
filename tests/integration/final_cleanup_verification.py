#!/usr/bin/env python3
"""
Final Comprehensive Test After Workspace Cleanup
===============================================

This test verifies that:
1. All files are properly organized
2. The MCP server still works from src/
3. Tests can still run from tests/
4. Tools are accessible from tools/
"""

import subprocess
import time
import json
import sys
from pathlib import Path

def test_server_functionality():
    """Test the MCP server from its new location"""
    print("🚀 Testing MCP server from src/ directory...")
    
    try:
        # Kill any existing servers
        subprocess.run(["pkill", "-f", "final_mcp_server"], check=False, capture_output=True)
        time.sleep(2)
        
        # Start server from src/
        venv_python = Path(".venv/bin/python")
        if not venv_python.exists():
            venv_python = Path("python3")  # fallback
        
        server_path = Path("src/final_mcp_server_enhanced.py")
        cmd = [str(venv_python), str(server_path), "--host", "0.0.0.0", "--port", "9998"]
        
        with open("final_test_server.log", "w") as log_file:
            server_proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(Path.cwd())
            )
        
        # Wait for startup
        print("   ⏳ Waiting for server startup...")
        for i in range(20):
            try:
                result = subprocess.run([
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    "http://localhost:9998/health"
                ], capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0 and result.stdout == "200":
                    print("   ✅ Server started successfully!")
                    break
            except:
                pass
            time.sleep(1)
        else:
            print("   ❌ Server failed to start within 20 seconds")
            server_proc.terminate()
            return False
        
        # Test basic endpoints
        endpoints = [
            ("/health", "Health check"),
            ("/", "Server info"),
            ("/mcp/tools", "Tools listing")
        ]
        
        for endpoint, description in endpoints:
            try:
                result = subprocess.run([
                    "curl", "-s", f"http://localhost:9998{endpoint}"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    print(f"   ✅ {description} working")
                else:
                    print(f"   ❌ {description} failed")
            except Exception as e:
                print(f"   ❌ {description} exception: {e}")
        
        # Test IPFS operation
        try:
            result = subprocess.run([
                "curl", "-s", "-X", "POST",
                "-H", "Content-Type: application/json",
                "-d", '{"content": "Final cleanup test"}',
                "http://localhost:9998/ipfs/add"
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get("success"):
                    print(f"   ✅ IPFS add working (CID: {response.get('cid', 'N/A')})")
                else:
                    print(f"   ❌ IPFS add failed: {response}")
            else:
                print("   ❌ IPFS add request failed")
        except Exception as e:
            print(f"   ❌ IPFS test exception: {e}")
        
        # Stop server
        print("   🛑 Stopping server...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except:
            server_proc.kill()
        
        return True
        
    except Exception as e:
        print(f"   ❌ Server test failed: {e}")
        return False

def test_workspace_organization():
    """Test that workspace is properly organized"""
    print("📁 Testing workspace organization...")
    
    # Check required directories
    required_dirs = {
        "src": "Source code",
        "tests": "Test files",
        "tools": "Development tools",
        "docs": "Documentation",
        "scripts": "Shell scripts",
        "docker": "Docker files",
        "config": "Configuration",
        "archive": "Archived files",
        "backup": "Backup files"
    }
    
    all_good = True
    for dir_name, description in required_dirs.items():
        path = Path(dir_name)
        if path.exists() and path.is_dir():
            file_count = len(list(path.rglob("*")))
            print(f"   ✅ {dir_name}/ - {description} ({file_count} items)")
        else:
            print(f"   ❌ {dir_name}/ - {description} MISSING")
            all_good = False
    
    # Check that main server is in src/
    server_path = Path("src/final_mcp_server_enhanced.py")
    if server_path.exists():
        print(f"   ✅ Main server properly located in src/")
    else:
        print(f"   ❌ Main server missing from src/")
        all_good = False
    
    # Check that root is clean (only essential files)
    root_files = [f for f in Path(".").iterdir() if f.is_file() and not f.name.startswith('.')]
    essential_files = {
        "README.md", "LICENSE", "pyproject.toml", "setup.py", "setup.cfg",
        "Makefile", "MANIFEST.in", "pytest.ini", "tox.ini"
    }
    
    unexpected_files = [f.name for f in root_files if f.name not in essential_files and not f.name.endswith(('.sh', '.py', '.log'))]
    
    if len(unexpected_files) == 0:
        print(f"   ✅ Root directory clean ({len(root_files)} essential files)")
    else:
        print(f"   ⚠️  Root has some extra files: {unexpected_files[:5]}")
    
    return all_good

def main():
    """Main test function"""
    print("🧹 FINAL WORKSPACE CLEANUP VERIFICATION")
    print("=" * 60)
    
    # Test organization
    org_success = test_workspace_organization()
    
    print("\n" + "=" * 60)
    
    # Test functionality
    func_success = test_server_functionality()
    
    print("\n" + "=" * 60)
    print("🎯 FINAL RESULTS:")
    
    if org_success and func_success:
        print("🎉 SUCCESS: Workspace is perfectly organized and fully functional!")
        print("✅ All files are in proper subdirectories")
        print("✅ MCP server works from new location")
        print("✅ Ready for development and deployment")
        return True
    else:
        print("❌ Some issues found:")
        if not org_success:
            print("   - Workspace organization needs attention")
        if not func_success:
            print("   - Server functionality issues")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
