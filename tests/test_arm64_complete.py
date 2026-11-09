#!/usr/bin/env python3
"""
Comprehensive ARM64 compatibility test for ipfs_kit_py
Tests platform detection, URL accessibility, and installation readiness.
"""

import sys
import platform
import traceback
import pytest
from ipfs_kit_py.install_ipfs import install_ipfs


def _skip_if_not_arm64():
    if platform.machine() != "aarch64":
        pytest.skip("ARM64 compatibility tests require aarch64 host")

def test_platform_detection():
    """Test platform detection accuracy"""
    _skip_if_not_arm64()
    print("=== Platform Detection Test ===")
    print(f"Python version: {sys.version}")
    print(f"Platform system: {platform.system()}")
    print(f"Platform machine: {platform.machine()}")
    print(f"Platform processor: {platform.processor()}")
    print(f"Platform architecture: {platform.architecture()}")
    
    installer = install_ipfs()
    hardware = installer.hardware_detect()
    dist = installer.dist_select()
    
    print(f"Hardware detection result: {hardware}")
    print(f"Distribution selection: {dist}")
    
    # Validate ARM64 detection
    expected_dist = "linux arm64"
    if dist == expected_dist:
        print("✅ Platform detection PASSED - correctly detected ARM64")
    else:
        pytest.fail(f"Platform detection FAILED - expected '{expected_dist}', got '{dist}'")

def test_ipfs_urls():
    """Test IPFS URL accessibility and version handling"""
    _skip_if_not_arm64()
    print("\n=== IPFS URL Test ===")
    try:
        installer = install_ipfs()
        
        # Test current default URLs
        dist = installer.dist_select()
        if dist in installer.ipfs_dists:
            url = installer.ipfs_dists[dist]
            print(f"Default URL for {dist}: {url}")
            
            # Test URL accessibility
            import requests
            response = requests.head(url, timeout=10)
            print(f"Default URL status: {response.status_code} - {response.reason}")
            
            # Test latest version
            latest_version = installer.get_latest_kubo_version()
            print(f"Latest Kubo version: {latest_version}")
            
            installer.update_ipfs_dists_with_version(latest_version)
            latest_url = installer.ipfs_dists[dist]
            print(f"Latest URL for {dist}: {latest_url}")
            
            # Test latest URL accessibility
            response = requests.head(latest_url, timeout=10)
            print(f"Latest URL status: {response.status_code} - {response.reason}")
            
            if response.status_code == 200:
                print("✅ IPFS URL test PASSED - URLs are accessible")
            else:
                pytest.fail("IPFS URL test FAILED - URLs not accessible")
        else:
            pytest.fail(f"IPFS URL test FAILED - No URL defined for {dist}")
            
    except Exception as e:
        print(f"❌ IPFS URL test FAILED - Exception: {e}")
        traceback.print_exc()
        pytest.fail(str(e))

def test_build_from_source_availability():
    """Test that build-from-source methods are available"""
    _skip_if_not_arm64()
    print("\n=== Build from Source Test ===")
    try:
        installer = install_ipfs()
        
        # Check if build_ipfs_from_source method exists
        if hasattr(installer, 'build_ipfs_from_source'):
            print("✅ build_ipfs_from_source method available")
        else:
            pytest.fail("Build from source test FAILED - build_ipfs_from_source method missing")

        # Check if _install_go method exists
        if hasattr(installer, '_install_go'):
            print("✅ _install_go method available")
        else:
            pytest.fail("Build from source test FAILED - _install_go method missing")

        print("✅ Build from source test PASSED")
            
    except Exception as e:
        print(f"❌ Build from source test FAILED - Exception: {e}")
        traceback.print_exc()
        pytest.fail(str(e))

def test_system_requirements():
    """Test system requirements for ARM64 builds"""
    _skip_if_not_arm64()
    print("\n=== System Requirements Test ===")
    import subprocess
    import shutil
    
    required_tools = {
        'wget': 'Required for downloading',
        'tar': 'Required for extracting archives',
        'gcc': 'Required for building from source',
        'make': 'Required for building from source',
        'git': 'Required for cloning repositories'
    }
    
    missing_tools = []
    for tool, description in required_tools.items():
        if shutil.which(tool):
            print(f"✅ {tool}: Available")
        else:
            print(f"❌ {tool}: Missing - {description}")
            missing_tools.append(tool)
    
    if not missing_tools:
        print("✅ System requirements test PASSED")
    else:
        pytest.fail(f"System requirements test FAILED - Missing tools: {missing_tools}")

def main():
    """Run all tests"""
    print("Running comprehensive ARM64 compatibility tests for ipfs_kit_py")
    print("=" * 60)
    
    tests = [
        test_platform_detection,
        test_ipfs_urls,
        test_build_from_source_availability,
        test_system_requirements
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_func.__name__} FAILED with exception: {e}")
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    test_names = [func.__name__ for func in tests]
    for name, result in zip(test_names, results):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {name}: {status}")
    
    passed = sum(results)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests PASSED! ARM64 compatibility is confirmed.")
        return True
    else:
        print("⚠️  Some tests FAILED. ARM64 compatibility may have issues.")
        return False

if __name__ == "__main__":
    sys.exit(0 if main() else 1)