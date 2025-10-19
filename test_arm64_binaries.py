#!/usr/bin/env python3
"""
Test ARM64 binary availability and architecture detection
"""

import platform
import requests
import sys
import os

sys.path.append('/home/endomorphosis/ipfs_kit_py')

def test_architecture_detection():
    """Test that our architecture detection fixes work correctly."""
    print("🔍 Testing Architecture Detection")
    print("=" * 50)
    
    from ipfs_kit_py.install_ipfs import install_ipfs
    from ipfs_kit_py.install_lotus import install_lotus
    
    # Test system detection
    print(f"System: {platform.system()}")
    print(f"Machine: {platform.machine()}")
    print(f"Processor: {platform.processor()}")
    print(f"Architecture: {platform.architecture()}")
    print()
    
    # Test our fixes
    ipfs_installer = install_ipfs()
    ipfs_dist = ipfs_installer.dist_select()
    print(f"IPFS dist_select(): {ipfs_dist}")
    
    lotus_installer = install_lotus()
    lotus_dist = lotus_installer.dist_select()
    print(f"Lotus dist_select(): {lotus_dist}")
    
    expected = "linux arm64"
    ipfs_ok = ipfs_dist == expected
    lotus_ok = lotus_dist == expected
    
    print(f"Expected: {expected}")
    print(f"IPFS Detection: {'✅ PASS' if ipfs_ok else '❌ FAIL'}")
    print(f"Lotus Detection: {'✅ PASS' if lotus_ok else '❌ FAIL'}")
    
    return ipfs_ok and lotus_ok


def test_binary_availability():
    """Test if ARM64 binaries are actually available for download."""
    print("\n🔗 Testing Binary Availability")
    print("=" * 50)
    
    # Test IPFS ARM64 binary
    ipfs_url = "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_linux-arm64.tar.gz"
    print(f"Testing IPFS ARM64 binary...")
    try:
        response = requests.head(ipfs_url, timeout=10)
        ipfs_available = response.status_code == 200
        print(f"IPFS ARM64: {'✅ AVAILABLE' if ipfs_available else '❌ NOT AVAILABLE'} ({response.status_code})")
        if ipfs_available:
            print(f"  Size: {int(response.headers.get('content-length', 0)) // 1024 // 1024} MB")
    except Exception as e:
        ipfs_available = False
        print(f"IPFS ARM64: ❌ ERROR - {e}")
    
    # Test Lotus ARM64 binary
    lotus_url = "https://github.com/filecoin-project/lotus/releases/download/v1.24.0/lotus_1.24.0_linux-arm64.tar.gz"
    print(f"Testing Lotus ARM64 binary...")
    try:
        response = requests.head(lotus_url, timeout=10)
        lotus_available = response.status_code == 200
        print(f"Lotus ARM64: {'✅ AVAILABLE' if lotus_available else '❌ NOT AVAILABLE'} ({response.status_code})")
        if lotus_available:
            print(f"  Size: {int(response.headers.get('content-length', 0)) // 1024 // 1024} MB")
    except Exception as e:
        lotus_available = False
        print(f"Lotus ARM64: ❌ ERROR - {e}")
    
    # Test alternative Lotus URLs
    print(f"\nChecking latest Lotus release for ARM64 support...")
    try:
        response = requests.get("https://api.github.com/repos/filecoin-project/lotus/releases/latest", timeout=10)
        if response.status_code == 200:
            release_data = response.json()
            assets = [asset['browser_download_url'] for asset in release_data['assets'] 
                     if not asset['name'].endswith(('.cid', '.sha512'))]
            
            print(f"Available Lotus binaries (v{release_data['tag_name']}):")
            for asset in assets:
                name = asset.split('/')[-1]
                print(f"  - {name}")
                
            arm64_assets = [asset for asset in assets if 'arm64' in asset or 'aarch64' in asset]
            if arm64_assets:
                print(f"✅ Found {len(arm64_assets)} ARM64 assets")
                lotus_available = True
            else:
                print(f"❌ No ARM64 assets found")
                lotus_available = False
        else:
            print(f"❌ Failed to fetch release info: {response.status_code}")
            lotus_available = False
    except Exception as e:
        print(f"❌ Error checking latest release: {e}")
        lotus_available = False
    
    return ipfs_available, lotus_available


def test_current_binaries():
    """Test if the currently installed binaries work on ARM64."""
    print("\n🏃 Testing Current Binary Compatibility")
    print("=" * 50)
    
    bin_path = "/home/endomorphosis/ipfs_kit_py/ipfs_kit_py/bin"
    
    binaries = ['ipfs', 'lotus', 'ipfs-cluster-service', 'ipfs-cluster-ctl', 'ipfs-cluster-follow']
    
    for binary in binaries:
        binary_path = os.path.join(bin_path, binary)
        if os.path.exists(binary_path):
            print(f"Testing {binary}...")
            
            # Check file type
            try:
                import subprocess
                result = subprocess.run(['file', binary_path], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    file_info = result.stdout.strip()
                    print(f"  File info: {file_info}")
                    
                    if 'x86-64' in file_info or 'x86_64' in file_info:
                        print(f"  ❌ INCOMPATIBLE: x86-64 binary on ARM64 system")
                    elif 'aarch64' in file_info or 'ARM aarch64' in file_info:
                        print(f"  ✅ COMPATIBLE: ARM64 binary")
                        
                        # Try to run it
                        try:
                            version_result = subprocess.run([binary_path, '--version'], 
                                                          capture_output=True, text=True, timeout=5)
                            if version_result.returncode == 0:
                                version_line = version_result.stdout.split('\n')[0]
                                print(f"  ✅ EXECUTABLE: {version_line}")
                            else:
                                print(f"  ⚠️ Binary exists but version check failed")
                        except subprocess.TimeoutExpired:
                            print(f"  ⚠️ Binary exists but timed out")
                        except Exception as e:
                            print(f"  ❌ Execution error: {e}")
                    else:
                        print(f"  ❓ UNKNOWN: Could not determine architecture compatibility")
                        
            except Exception as e:
                print(f"  ❌ Error checking {binary}: {e}")
        else:
            print(f"❌ {binary}: Not found")


def main():
    """Main test function."""
    print("🚀 ARM64 Binary Compatibility Test Suite")
    print("=" * 60)
    print(f"Running on: {platform.system()} {platform.machine()}")
    print(f"Date: {__import__('datetime').datetime.now()}")
    print()
    
    # Test 1: Architecture Detection
    arch_ok = test_architecture_detection()
    
    # Test 2: Binary Availability  
    ipfs_available, lotus_available = test_binary_availability()
    
    # Test 3: Current Binary Compatibility
    test_current_binaries()
    
    # Summary
    print("\n📊 Summary")
    print("=" * 50)
    print(f"Architecture Detection: {'✅ PASS' if arch_ok else '❌ FAIL'}")
    print(f"IPFS ARM64 Binary: {'✅ AVAILABLE' if ipfs_available else '❌ NOT AVAILABLE'}")
    print(f"Lotus ARM64 Binary: {'✅ AVAILABLE' if lotus_available else '❌ NOT AVAILABLE'}")
    
    if arch_ok and ipfs_available:
        print("\n✅ IPFS can be installed natively on ARM64!")
    
    if not lotus_available:
        print("\n⚠️ Lotus doesn't provide ARM64 binaries")
        print("   Recommendation: Use remote Lotus node or x86_64 container")
    
    print(f"\n🎯 Overall Status: ARM64 support is {'GOOD' if arch_ok and ipfs_available else 'PARTIAL'}")


if __name__ == "__main__":
    main()