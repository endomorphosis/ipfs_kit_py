#!/usr/bin/env python3
"""
A comprehensive script to enable all skipped tests in the ipfs_kit_py project.
This script:
1. Sets environment variables to enable WebRTC, notifications, and other tests
2. Modifies the test files to remove skip annotations
3. Patches modules to force features to be available
"""

import sys
import os
import importlib
import re
import glob

# Set environment variables to enable all tests
os.environ["FORCE_WEBRTC_TESTS"] = "1"
os.environ["IPFS_KIT_RUN_ALL_TESTS"] = "1"
os.environ["IPFS_KIT_FORCE_WEBRTC"] = "1"

print("Set environment variables to enable all tests")

# Patch WebRTC streaming module
try:
    # Import the module first to see initial state
    from ipfs_kit_py.webrtc_streaming import HAVE_WEBRTC as original_webrtc_flag
    print(f"Original webrtc_streaming.HAVE_WEBRTC: {original_webrtc_flag}")
    
    # Patch the module
    import ipfs_kit_py.webrtc_streaming
    ipfs_kit_py.webrtc_streaming.HAVE_WEBRTC = True
    ipfs_kit_py.webrtc_streaming.HAVE_NUMPY = True
    ipfs_kit_py.webrtc_streaming.HAVE_CV2 = True
    ipfs_kit_py.webrtc_streaming.HAVE_AV = True
    ipfs_kit_py.webrtc_streaming.HAVE_AIORTC = True
    ipfs_kit_py.webrtc_streaming.HAVE_NOTIFICATIONS = True
    
    # Reload the module
    importlib.reload(ipfs_kit_py.webrtc_streaming)
    print(f"Patched webrtc_streaming.HAVE_WEBRTC: {ipfs_kit_py.webrtc_streaming.HAVE_WEBRTC}")
except Exception as e:
    print(f"Error patching webrtc_streaming: {e}")

# Patch WebRTC benchmark module
try:
    # Import the module to see initial state
    from ipfs_kit_py.webrtc_benchmark import HAVE_WEBRTC as original_benchmark_flag
    print(f"Original webrtc_benchmark.HAVE_WEBRTC: {original_benchmark_flag}")
    
    # Patch the module
    import ipfs_kit_py.webrtc_benchmark
    ipfs_kit_py.webrtc_benchmark.HAVE_WEBRTC = True
    if hasattr(ipfs_kit_py.webrtc_benchmark, "_can_test_webrtc"):
        print(f"Original webrtc_benchmark._can_test_webrtc: {ipfs_kit_py.webrtc_benchmark._can_test_webrtc}")
        ipfs_kit_py.webrtc_benchmark._can_test_webrtc = True
        print(f"Patched webrtc_benchmark._can_test_webrtc: {ipfs_kit_py.webrtc_benchmark._can_test_webrtc}")
    
    # Reload the module
    importlib.reload(ipfs_kit_py.webrtc_benchmark)
except Exception as e:
    print(f"Error patching webrtc_benchmark: {e}")

# Patch other modules with skip flags
try:
    # Patch high_level_api
    import ipfs_kit_py.high_level_api
    if hasattr(ipfs_kit_py.high_level_api, "HAVE_WEBRTC"):
        print(f"Original high_level_api.HAVE_WEBRTC: {ipfs_kit_py.high_level_api.HAVE_WEBRTC}")
        ipfs_kit_py.high_level_api.HAVE_WEBRTC = True
        print(f"Patched high_level_api.HAVE_WEBRTC: {ipfs_kit_py.high_level_api.HAVE_WEBRTC}")
except Exception as e:
    print(f"Error patching high_level_api: {e}")

# Function to remove skip markers from test files
def remove_skip_from_file(file_path):
    """Remove skip markers from a test file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Comment out pytestmark skip lines
        content = re.sub(
            r'^(\s*pytestmark\s*=\s*pytest\.mark\.skip.*)', 
            r'# \1', 
            content, 
            flags=re.MULTILINE
        )
        
        # Comment out @pytest.mark.skip lines
        content = re.sub(
            r'^(\s*@pytest\.mark\.skip.*)', 
            r'# \1', 
            content, 
            flags=re.MULTILINE
        )
        
        # Comment out @pytest.mark.skipif lines for WebRTC
        content = re.sub(
            r'^(\s*@pytest\.mark\.skipif\s*\(\s*not\s+_can_test_webrtc.*)', 
            r'# \1', 
            content, 
            flags=re.MULTILINE
        )
        
        # Write the modified content back
        with open(file_path, 'w') as f:
            f.write(content)
            
        print(f"Removed skip markers from {file_path}")
        return True
    except Exception as e:
        print(f"Error removing skip markers from {file_path}: {e}")
        return False

# Process test files
test_files = glob.glob("/home/barberb/ipfs_kit_py/test/test_*.py")
for file_path in test_files:
    remove_skip_from_file(file_path)

print("All tests should now be enabled for running!")