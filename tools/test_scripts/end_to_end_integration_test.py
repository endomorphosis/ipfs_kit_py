#!/usr/bin/env python3
"""
End-to-End Integration Test for Final MCP Server
Tests the complete deployment pipeline and functionality
"""

import subprocess
import requests
import time
import sys
import json
import os
from pathlib import Path

class MCPServerIntegrationTest:
    def __init__(self):
        self.base_url = "http://localhost:9998"
        self.server_process = None
        
    def run_command(self, cmd, timeout=30):
        """Run a shell command and return the result"""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, 
                text=True, timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
    
    def test_file_existence(self):
        """Test that all required files exist"""
        print("🔍 Testing file existence...")
        
        required_files = [
            "final_mcp_server_enhanced.py",
            "final_mcp_server.py",
            "Dockerfile",
            "Dockerfile.final",
            "docker-compose.final.yml",
            "run_final_mcp.sh",
            ".github/workflows/final-mcp-server.yml"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            print(f"❌ Missing files: {missing_files}")
            return False
        
        print("✅ All required files exist")
        return True
    
    def test_server_syntax(self):
        """Test Python syntax of the enhanced server"""
        print("🔍 Testing server syntax...")
        
        success, stdout, stderr = self.run_command(
            "python -m py_compile final_mcp_server_enhanced.py"
        )
        
        if not success:
            print(f"❌ Syntax error: {stderr}")
            return False
        
        print("✅ Server syntax is valid")
        return True
    
    def test_server_import(self):
        """Test that the server can be imported"""
        print("🔍 Testing server import...")
        
        success, stdout, stderr = self.run_command(
            "python -c 'import final_mcp_server_enhanced; print(final_mcp_server_enhanced.__version__)'"
        )
        
        if not success:
            print(f"❌ Import error: {stderr}")
            return False
        
        version = stdout.strip()
        print(f"✅ Server imports successfully (version: {version})")
        return True
    
    def test_server_help(self):
        """Test server help command"""
        print("🔍 Testing server help command...")
        
        success, stdout, stderr = self.run_command(
            "timeout 10s python final_mcp_server_enhanced.py --help"
        )
        
        if not success:
            print(f"❌ Help command failed: {stderr}")
            return False
        
        if "usage:" not in stdout.lower():
            print("❌ Help output doesn't contain usage information")
            return False
        
        print("✅ Server help command works")
        return True
    
    def start_server(self):
        """Start the server for testing"""
        print("🔍 Starting server for API testing...")
        
        # Kill any existing server on the port
        self.run_command("pkill -f 'final_mcp_server_enhanced.py'")
        time.sleep(2)
        
        # Start the server in background
        self.server_process = subprocess.Popen(
            ["python", "final_mcp_server_enhanced.py", "--host", "0.0.0.0", "--port", "9998"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server to start
        for _ in range(30):  # Wait up to 30 seconds
            try:
                response = requests.get(f"{self.base_url}/health", timeout=2)
                if response.status_code == 200:
                    print("✅ Server started successfully")
                    return True
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)
        
        print("❌ Server failed to start within 30 seconds")
        return False
    
    def stop_server(self):
        """Stop the test server"""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait(timeout=10)
            self.server_process = None
        
        # Also kill via process name as backup
        self.run_command("pkill -f 'final_mcp_server_enhanced.py'")
    
    def test_api_endpoints(self):
        """Test the main API endpoints"""
        print("🔍 Testing API endpoints...")
        
        # Test health endpoint
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code != 200:
                print(f"❌ Health endpoint failed: {response.status_code}")
                return False
            
            health_data = response.json()
            if health_data.get("status") != "healthy":
                print(f"❌ Health status not healthy: {health_data}")
                return False
            
            print("✅ Health endpoint working")
        except Exception as e:
            print(f"❌ Health endpoint error: {e}")
            return False
        
        # Test root endpoint
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code != 200:
                print(f"❌ Root endpoint failed: {response.status_code}")
                return False
            print("✅ Root endpoint working")
        except Exception as e:
            print(f"❌ Root endpoint error: {e}")
            return False
        
        # Test docs endpoint
        try:
            response = requests.get(f"{self.base_url}/docs", timeout=5)
            if response.status_code != 200:
                print(f"❌ Docs endpoint failed: {response.status_code}")
                return False
            print("✅ Docs endpoint working")
        except Exception as e:
            print(f"❌ Docs endpoint error: {e}")
            return False
        
        # Test IPFS add endpoint
        try:
            response = requests.post(
                f"{self.base_url}/ipfs/add",
                json={"content": "test content"},
                timeout=5
            )
            if response.status_code != 200:
                print(f"❌ IPFS add failed: {response.status_code}")
                return False
            
            add_data = response.json()
            if "hash" not in add_data:
                print(f"❌ IPFS add response missing hash: {add_data}")
                return False
            
            print("✅ IPFS add endpoint working")
            
            # Test IPFS get with the returned hash
            test_hash = add_data["hash"]
            response = requests.get(f"{self.base_url}/ipfs/get/{test_hash}", timeout=5)
            if response.status_code != 200:
                print(f"❌ IPFS get failed: {response.status_code}")
                return False
            
            get_data = response.json()
            if get_data.get("content") != "test content":
                print(f"❌ IPFS get returned wrong content: {get_data}")
                return False
            
            print("✅ IPFS get endpoint working")
            
        except Exception as e:
            print(f"❌ IPFS endpoints error: {e}")
            return False
        
        return True
    
    def test_docker_build(self):
        """Test Docker build process"""
        print("🔍 Testing Docker build...")
        
        success, stdout, stderr = self.run_command(
            "docker build -t final-mcp-test -f Dockerfile . 2>&1 | tail -10",
            timeout=300  # 5 minutes for Docker build
        )
        
        if not success:
            print(f"❌ Docker build failed: {stderr}")
            return False
        
        print("✅ Docker build successful")
        return True
    
    def test_docker_compose(self):
        """Test Docker Compose configuration"""
        print("🔍 Testing Docker Compose configuration...")
        
        # Test compose file validation
        success, stdout, stderr = self.run_command(
            "docker-compose -f docker-compose.final.yml config"
        )
        
        if not success:
            print(f"❌ Docker Compose config invalid: {stderr}")
            return False
        
        print("✅ Docker Compose configuration is valid")
        return True
    
    def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Starting End-to-End Integration Tests")
        print("=" * 60)
        
        tests = [
            ("File Existence", self.test_file_existence),
            ("Server Syntax", self.test_server_syntax),
            ("Server Import", self.test_server_import),
            ("Server Help", self.test_server_help),
            ("Docker Build", self.test_docker_build),
            ("Docker Compose", self.test_docker_compose),
        ]
        
        # Run basic tests first
        for test_name, test_func in tests:
            if not test_func():
                print(f"\n❌ Integration test failed at: {test_name}")
                return False
        
        # Run API tests with server
        if self.start_server():
            try:
                api_success = self.test_api_endpoints()
            finally:
                self.stop_server()
            
            if not api_success:
                print("\n❌ API tests failed")
                return False
        else:
            print("\n❌ Could not start server for API testing")
            return False
        
        print("\n🎉 All integration tests passed!")
        print("✅ Final MCP Server is production ready")
        return True

def main():
    tester = MCPServerIntegrationTest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
