#!/usr/bin/env python3
"""
Comprehensive ARM64 binary installation test for IPFS Kit Python

This script tests:
1. Platform detection fixes
2. URL validation for ARM64 binaries
3. Actual binary installation attempts
4. Build-from-source fallbacks
"""

import sys
import os
import platform
import subprocess
import tempfile
import shutil
from pathlib import Path
import pytest

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))


def _skip_if_not_arm64():
    if platform.machine() != "aarch64":
        pytest.skip("ARM64 installation tests require aarch64 host")

def test_platform_detection():
    """Test that our platform detection fixes work correctly."""
    _skip_if_not_arm64()
    print("🔍 Testing Platform Detection")
    print("=" * 50)
    
    print(f"System: {platform.system()}")
    print(f"Machine: {platform.machine()}")
    print(f"Architecture: {platform.architecture()}")
    
    try:
        from ipfs_kit_py.install_ipfs import install_ipfs
        from ipfs_kit_py.install_lotus import install_lotus
        
        # Test IPFS platform detection
        ipfs_installer = install_ipfs()
        ipfs_dist = ipfs_installer.dist_select()
        print(f"IPFS dist_select(): {ipfs_dist}")
        
        # Test Lotus platform detection
        lotus_installer = install_lotus()
        lotus_dist = lotus_installer.dist_select()
        print(f"Lotus dist_select(): {lotus_dist}")
        
        expected = "linux arm64"
        if ipfs_dist == expected and lotus_dist == expected:
            print("✅ Platform detection working correctly")
            return True
        else:
            print(f"❌ Platform detection failed. Expected: {expected}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing platform detection: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ipfs_urls():
    """Test IPFS download URLs for ARM64."""
    _skip_if_not_arm64()
    print("\n🔗 Testing IPFS ARM64 URLs")
    print("=" * 50)
    
    try:
        from ipfs_kit_py.install_ipfs import install_ipfs
        
        installer = install_ipfs()
        dist = installer.dist_select()
        
        if dist in installer.ipfs_dists:
            url = installer.ipfs_dists[dist]
            print(f"IPFS URL for {dist}: {url}")
            
            # Test URL validation if method exists
            if hasattr(installer, 'verify_release_url'):
                is_valid = installer.verify_release_url(url)
                print(f"URL validation: {'✅ Valid' if is_valid else '❌ Invalid'}")
                return is_valid
            else:
                # Fallback: test with curl
                result = subprocess.run(['curl', '-I', url], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and '200' in result.stdout:
                    print("✅ URL is accessible (curl test)")
                    return True
                else:
                    print("❌ URL not accessible (curl test)")
                    return False
        else:
            print(f"❌ No URL found for {dist}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing IPFS URLs: {e}")
        return False

def test_lotus_urls():
    """Test Lotus download URLs for ARM64."""
    _skip_if_not_arm64()
    print("\n🔗 Testing Lotus ARM64 URLs")
    print("=" * 50)
    
    try:
        from ipfs_kit_py.install_lotus import install_lotus
        
        installer = install_lotus()
        dist = installer.dist_select()
        
        if dist in installer.lotus_dists:
            url = installer.lotus_dists[dist]
            print(f"Lotus URL for {dist}: {url}")
            
            # Test with curl
            result = subprocess.run(['curl', '-I', url], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and '200' in result.stdout:
                print("✅ URL is accessible")
                return True
            else:
                print("❌ URL not accessible")
                print("This is expected - Lotus doesn't provide ARM64 binaries")
                return False
        else:
            print(f"❌ No URL found for {dist}")
            print("This is expected - Lotus doesn't provide ARM64 binaries")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Lotus URLs: {e}")
        return False

def test_build_from_source_methods():
    """Test that build-from-source methods exist and are callable."""
    _skip_if_not_arm64()
    print("\n🔧 Testing Build-from-Source Methods")
    print("=" * 50)
    
    results = {}
    
    # Test IPFS build methods
    try:
        from ipfs_kit_py.install_ipfs import install_ipfs
        installer = install_ipfs()
        
        methods = ['build_ipfs_from_source', '_install_go', '_add_to_user_path']
        for method in methods:
            if hasattr(installer, method):
                print(f"✅ IPFS {method} method exists")
                results[f'ipfs_{method}'] = True
            else:
                print(f"❌ IPFS {method} method missing")
                results[f'ipfs_{method}'] = False
                
    except Exception as e:
        print(f"❌ Error loading IPFS installer: {e}")
        results['ipfs_methods'] = False
    
    # Test Lotus build methods
    try:
        from ipfs_kit_py.install_lotus import install_lotus
        installer = install_lotus()
        
        methods = ['build_lotus_from_source', '_install_go_for_build']
        for method in methods:
            if hasattr(installer, method):
                print(f"✅ Lotus {method} method exists")
                results[f'lotus_{method}'] = True
            else:
                print(f"❌ Lotus {method} method missing")
                results[f'lotus_{method}'] = False
                
    except Exception as e:
        print(f"❌ Error loading Lotus installer: {e}")
        results['lotus_methods'] = False
    
    return all(results.values())

def test_actual_installation():
    """Test actual installation process (with safety measures)."""
    _skip_if_not_arm64()
    print("\n⚙️ Testing Actual Installation Process")
    print("=" * 50)
    
    # Create temporary directory for test installation
    temp_dir = tempfile.mkdtemp(prefix="ipfs_kit_test_")
    print(f"Using temporary directory: {temp_dir}")
    
    try:
        # Test IPFS installation in controlled environment
        print("\nTesting IPFS installation...")
        from ipfs_kit_py.install_ipfs import install_ipfs
        
        # Monkey patch to use temporary directory
        installer = install_ipfs()
        original_bin_path = installer.bin_path
        installer.bin_path = os.path.join(temp_dir, "bin")
        os.makedirs(installer.bin_path, exist_ok=True)
        
        # Get the expected distribution and URL
        dist = installer.dist_select()
        if dist in installer.ipfs_dists:
            url = installer.ipfs_dists[dist]
            print(f"Would download from: {url}")
            
            # Test URL validation
            if hasattr(installer, 'verify_release_url'):
                url_valid = installer.verify_release_url(url)
                if url_valid:
                    print("✅ URL is valid, installation would proceed")
                    return True
                else:
                    print("❌ URL validation failed, would fall back to build-from-source")
                    # Test that build method exists
                    if hasattr(installer, 'build_ipfs_from_source'):
                        print("✅ Build-from-source method available as fallback")
                        return True
                    else:
                        print("❌ No build-from-source fallback")
                        return False
            else:
                print("⚠️ No URL verification method")
                return False
        else:
            print("❌ No distribution available for this platform")
            return False
            
    except Exception as e:
        print(f"❌ Error during installation test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            shutil.rmtree(temp_dir)
            print(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            print(f"Warning: Could not clean up {temp_dir}: {e}")

def test_build_tools():
    """Test availability of build tools."""
    _skip_if_not_arm64()
    print("\n🔨 Testing Build Tools")
    print("=" * 50)
    
    tools = {
        'git': ['git', '--version'],
        'make': ['make', '--version'], 
        'gcc': ['gcc', '--version'],
        'g++': ['g++', '--version'],
        'go': ['go', 'version'],
    }
    
    available_tools = {}
    for tool, cmd in tools.items():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                print(f"✅ {tool}: {version}")
                available_tools[tool] = True
            else:
                print(f"❌ {tool}: Command failed")
                available_tools[tool] = False
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            print(f"❌ {tool}: Not found")
            available_tools[tool] = False
    
    required_tools = ['git', 'make', 'gcc']
    missing_required = [tool for tool in required_tools if not available_tools.get(tool, False)]
    
    if missing_required:
        print(f"\n⚠️ Missing required build tools: {', '.join(missing_required)}")
        print("Install with: sudo apt-get install -y build-essential git make gcc g++")
        return False
    else:
        print(f"\n✅ All required build tools available")
        if not available_tools.get('go', False):
            print("⚠️ Go not installed, but will be auto-installed if needed")
        return True

def main():
    """Main test function."""
    print("🚀 ARM64 Binary Installation Test Suite")
    print("=" * 60)
    print(f"Running on: {platform.system()} {platform.machine()}")
    print()
    
    tests = [
        ("Platform Detection", test_platform_detection),
        ("IPFS URLs", test_ipfs_urls),
        ("Lotus URLs", test_lotus_urls),
        ("Build Methods", test_build_from_source_methods),
        ("Build Tools", test_build_tools),
        ("Installation Process", test_actual_installation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! ARM64 installation should work correctly.")
        return 0
    else:
        print(f"\n⚠️ {total - passed} tests failed. Some issues need to be addressed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
