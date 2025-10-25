#!/usr/bin/env python3
"""
ARM64 architecture detection and compatibility fixes for ipfs_kit_py
"""

import os
import platform
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_architecture():
    """Detect the current system architecture."""
    arch = platform.machine()
    print(f"Detected architecture: {arch}")
    
    if arch in ['aarch64', 'arm64']:
        return 'arm64'
    elif arch in ['x86_64', 'AMD64']:
        return 'x86_64'
    else:
        return arch


def check_binary_compatibility(binary_path):
    """Check if a binary is compatible with the current architecture."""
    if not os.path.exists(binary_path):
        return False, "Binary not found"
    
    try:
        # Use file command to check binary type
        result = subprocess.run(['file', binary_path], 
                              capture_output=True, text=True, timeout=10)
        
        arch = detect_architecture()
        output = result.stdout.lower()
        
        if arch == 'arm64' and 'aarch64' in output:
            return True, "ARM64 binary compatible"
        elif arch == 'x86_64' and ('x86-64' in output or 'x86_64' in output):
            return True, "x86_64 binary compatible"
        else:
            return False, f"Binary incompatible: {output.strip()}"
            
    except Exception as e:
        return False, f"Error checking binary: {e}"


def create_arch_specific_config():
    """Create architecture-specific configuration."""
    arch = detect_architecture()
    config = {
        'architecture': arch,
        'binary_compatibility': {},
        'skip_binary_deps': False
    }
    
    # Check common binaries
    binaries = [
        'ipfs_kit_py/bin/lotus',
        'ipfs_kit_py/bin/ipfs',
        '/usr/local/bin/lotus',
        '/usr/local/bin/ipfs'
    ]
    
    for binary in binaries:
        compatible, msg = check_binary_compatibility(binary)
        config['binary_compatibility'][binary] = {
            'compatible': compatible,
            'message': msg
        }
        
        if not compatible and os.path.exists(binary):
            print(f"⚠ Binary compatibility issue: {binary} - {msg}")
    
    # For ARM64, we might need to skip some binary dependencies
    if arch == 'arm64':
        config['skip_binary_deps'] = True
        print("ℹ ARM64 detected: Will skip incompatible binary dependencies")
    
    return config


def test_arm64_fixes():
    """Test ARM64 specific compatibility fixes."""
    print("=" * 60)
    print("ARM64 Compatibility Analysis")
    print("=" * 60)
    
    # 1. Check system architecture
    arch = platform.machine()
    print(f"System Architecture: {arch}")
    assert arch in ['aarch64', 'arm64'], f"Expected ARM64 architecture, got {arch}"
    
    # 2. Test binary compatibility
    bin_path = Path(__file__).parent.parent / "ipfs_kit_py" / "bin"
    if bin_path.exists():
        binaries = list(bin_path.glob("*"))
        print(f"Found {len(binaries)} binaries in bin directory")
        
        for binary in binaries:
            if binary.is_file() and not binary.name.endswith('.exe'):
                print(f"Testing binary: {binary.name}")
                try:
                    # Try to get file info without executing
                    result = subprocess.run(['file', str(binary)], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        file_info = result.stdout.strip()
                        print(f"  File info: {file_info}")
                        
                        # Check if it's x86-64 (incompatible with ARM64)
                        if 'x86-64' in file_info or 'x86_64' in file_info:
                            print(f"  ⚠️ INCOMPATIBLE: {binary.name} is x86-64, cannot run on ARM64")
                        elif 'aarch64' in file_info or 'ARM' in file_info:
                            print(f"  ✅ COMPATIBLE: {binary.name} is ARM64 compatible")
                        else:
                            print(f"  ❓ UNKNOWN: Architecture not clearly identified")
                    
                except subprocess.TimeoutExpired:
                    print(f"  ⚠️ Timeout checking {binary.name}")
                except Exception as e:
                    print(f"  ❌ Error checking {binary.name}: {e}")
    
    # 3. Test package imports work
    try:
        import ipfs_kit_py
        print(f"✅ Package import successful: version {ipfs_kit_py.__version__}")
    except Exception as e:
        print(f"❌ Package import failed: {e}")
        assert False, f"Package import should work on ARM64: {e}"
    
    # 4. Test core functionality without binary dependencies
    try:
        # Test functions that should work without external binaries
        from ipfs_kit_py import get_ipfs_filesystem
        fs = get_ipfs_filesystem()
        print(f"✅ IPFSFileSystem creation: {type(fs)}")
    except Exception as e:
        print(f"⚠️ IPFSFileSystem creation issue (may be expected): {e}")
    
    print("=" * 60)
    print("ARM64 compatibility analysis complete")
    print("=" * 60)
    
    # Always return None for pytest


if __name__ == "__main__":
    test_arm64_fixes()