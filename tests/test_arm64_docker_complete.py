#!/usr/bin/env python3
"""
Comprehensive ARM64 Docker Test for IPFS Kit Python
===================================================

This script validates that the IPFS Kit Docker containers work properly on ARM64.
"""

import subprocess
import time
import requests
import json
import sys
import platform
import pytest
from pathlib import Path


def _skip_if_not_arm64():
    if platform.machine() != "aarch64":
        pytest.skip("ARM64 Docker tests require aarch64 host")

def run_command(cmd, description="", return_output=True, timeout=60):
    """Run a shell command and return the result"""
    print(f"\n🔧 {description}")
    print(f"   Command: {cmd}")
    
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=return_output, 
            text=True, timeout=timeout
        )
        if return_output:
            if result.returncode == 0:
                print(f"   ✅ Success")
                return result.stdout.strip()
            else:
                print(f"   ❌ Failed (exit code: {result.returncode})")
                print(f"   Error: {result.stderr}")
                return None
        else:
            print(f"   ✅ Command executed")
            return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"   ⏰ Timeout after {timeout}s")
        return None
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return None

def test_docker_availability():
    """Test if Docker is available and running"""
    _skip_if_not_arm64()
    print("\n" + "="*60)
    print("🐳 TESTING DOCKER AVAILABILITY")
    print("="*60)
    
    # Check Docker version
    version = run_command("docker --version", "Checking Docker version")
    if not version:
        return False
    
    # Check Docker daemon
    status = run_command("docker info --format '{{.ServerVersion}}'", "Checking Docker daemon")
    if not status:
        return False
    
    print(f"   Docker version: {version}")
    print(f"   Docker daemon: {status}")
    return True

def test_system_architecture():
    """Test system architecture"""
    _skip_if_not_arm64()
    print("\n" + "="*60)
    print("🏗️  TESTING SYSTEM ARCHITECTURE")
    print("="*60)
    
    arch = run_command("uname -m", "Getting system architecture")
    if arch:
        print(f"   System architecture: {arch}")
        return arch == "aarch64"
    return False

def test_docker_build():
    """Test Docker image build for ARM64"""
    _skip_if_not_arm64()
    print("\n" + "="*60)
    print("🔨 TESTING DOCKER BUILD ON ARM64")
    print("="*60)
    
    # Build development image
    build_cmd = "docker build --platform linux/arm64 --target development -t ipfs-kit-py:test-arm64 ."
    success = run_command(build_cmd, "Building ARM64 development image", return_output=False, timeout=300)
    
    if success:
        # Check if image was created
        images = run_command("docker images ipfs-kit-py:test-arm64 --format '{{.Repository}}:{{.Tag}}'", 
                            "Verifying image creation")
        return images == "ipfs-kit-py:test-arm64"
    
    return False

def test_container_startup():
    """Test container startup and basic functionality"""
    _skip_if_not_arm64()
    print("\n" + "="*60)
    print("🚀 TESTING CONTAINER STARTUP")
    print("="*60)
    
    # Start container in background
    start_cmd = ("docker run --platform linux/arm64 -d --name ipfs-kit-test-arm64 "
                "--rm -p 8003:8000 "
                "ipfs-kit-py:test-arm64 "
                "python -m ipfs_kit_py.cli daemon start --host 0.0.0.0 --port 8000")
    
    container_id = run_command(start_cmd, "Starting ARM64 container")
    if not container_id:
        return False
    
    print(f"   Container ID: {container_id[:12]}...")
    
    # Wait for container to start
    print("   Waiting for container to start...")
    time.sleep(10)
    
    # Check if container is running
    status = run_command("docker ps -f name=ipfs-kit-test-arm64 --format '{{.Status}}'", 
                        "Checking container status")
    
    if status and "Up" in status:
        print(f"   Container status: {status}")
        return True
    
    # If failed, show logs
    logs = run_command("docker logs ipfs-kit-test-arm64", "Getting container logs")
    if logs:
        print(f"   Container logs:\n{logs}")
    
    return False

def test_api_endpoints():
    """Test API endpoints"""
    _skip_if_not_arm64()
    print("\n" + "="*60)
    print("🌐 TESTING API ENDPOINTS")
    print("="*60)
    
    base_url = "http://localhost:8003"
    endpoints_to_test = [
        ("/health", "Health check endpoint"),
        ("/api/v1/status", "Status endpoint"),
        ("/docs", "API documentation endpoint"),
    ]
    
    successful_tests = 0
    
    for endpoint, description in endpoints_to_test:
        print(f"\n   Testing {description}")
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            if response.status_code == 200:
                print(f"   ✅ {endpoint} - Status: {response.status_code}")
                
                # For health endpoint, show some details
                if endpoint == "/health":
                    try:
                        health_data = response.json()
                        healthy_backends = health_data.get("components", {}).get("backends", {})
                        healthy_count = sum(1 for backend_data in healthy_backends.values() 
                                          if backend_data.get("health") == "healthy")
                        print(f"      Healthy backends: {healthy_count}")
                        
                        # Show some working backends
                        for name, data in healthy_backends.items():
                            if data.get("health") == "healthy":
                                print(f"      ✅ {name}: {data.get('status', 'unknown')}")
                    except:
                        print(f"      Response length: {len(response.text)} chars")
                
                successful_tests += 1
            else:
                print(f"   ⚠️  {endpoint} - Status: {response.status_code}")
        except Exception as e:
            print(f"   ❌ {endpoint} - Error: {e}")
    
    return successful_tests > 0

def test_container_functionality():
    """Test specific container functionality"""
    _skip_if_not_arm64()
    print("\n" + "="*60)
    print("⚙️  TESTING CONTAINER FUNCTIONALITY")  
    print("="*60)
    
    # Test CLI help
    help_output = run_command("docker exec ipfs-kit-test-arm64 python -m ipfs_kit_py.cli --help", 
                             "Testing CLI help command")
    if help_output and "IPFS-Kit CLI" in help_output:
        print("   ✅ CLI is working")
    else:
        print("   ❌ CLI test failed")
        return False
    
    # Test Python import
    import_test = run_command("docker exec ipfs-kit-test-arm64 python -c 'import ipfs_kit_py; print(\"Import successful\")'", 
                             "Testing Python import")
    if import_test and "Import successful" in import_test:
        print("   ✅ Python import is working")
    else:
        print("   ❌ Python import test failed")
        return False
    
    return True

def cleanup_containers():
    """Clean up test containers"""
    print("\n" + "="*60)
    print("🧹 CLEANING UP")
    print("="*60)
    
    # Stop and remove test container
    run_command("docker stop ipfs-kit-test-arm64 2>/dev/null || true", "Stopping test container")
    run_command("docker rm ipfs-kit-test-arm64 2>/dev/null || true", "Removing test container")
    
    # Remove test image
    run_command("docker rmi ipfs-kit-test-arm64 2>/dev/null || true", "Removing test image")
    
    print("   ✅ Cleanup complete")

def main():
    """Main test function"""
    print("🔬 IPFS Kit Python ARM64 Docker Test Suite")
    print("=" * 60)
    print("This test validates ARM64 Docker functionality")
    
    test_results = {}
    
    try:
        # Run tests
        test_results["docker_available"] = test_docker_availability()
        test_results["arm64_architecture"] = test_system_architecture() 
        test_results["docker_build"] = test_docker_build()
        test_results["container_startup"] = test_container_startup()
        test_results["api_endpoints"] = test_api_endpoints() 
        test_results["container_functionality"] = test_container_functionality()
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        cleanup_containers()
    
    # Print results summary
    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY")
    print("="*60)
    
    passed_tests = 0
    total_tests = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:<25} : {status}")
        if result:
            passed_tests += 1
    
    print(f"\n   Tests passed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("   🎉 ALL TESTS PASSED! ARM64 Docker support is working!")
        return 0
    else:
        print("   ⚠️  Some tests failed. Check the details above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())