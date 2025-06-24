#!/usr/bin/env python
"""Script to fix all skipped tests in the codebase."""

import os
import sys
import subprocess
import re
import glob
from pathlib import Path

def main():
    """Find and fix remaining skipped tests in the codebase."""
    print("Fixing all skipped tests in the codebase...")

    # 1. Force WebRTC and other optional dependencies to be available
    print("\n1. Patching modules to force feature availability...")

    # Apply patches to relevant modules
    modules_to_patch = [
        "ipfs_kit_py/webrtc_streaming.py"
    ]

    # Environment variables to set for tests
    os.environ["IPFS_KIT_FORCE_WEBRTC"] = "1"
    os.environ["FORCE_WEBRTC_TESTS"] = "1"
    os.environ["IPFS_KIT_RUN_ALL_TESTS"] = "1"

    # 2. Remove explicit skipif markers from test files
    print("\n2. Removing explicit pytest.mark.skip markers from test files...")
    # Updated to use correct paths for WebRTC tests
    test_files = glob.glob("test/**/*.py", recursive=True)
    modified_files = []
    skip_pattern = re.compile(r'^\s*@pytest\.mark\.skip.*?$', re.MULTILINE)
    skipif_pattern = re.compile(r'^\s*@pytest\.mark\.skipif.*?$', re.MULTILINE)

    for file_path in test_files:
        with open(file_path, 'r') as f:
            content = f.read()

        # Skip comments and intentionally skipped tests (like tests that document they should be skipped)
        original_content = content

        # Replace skipif markers (except for intentionally skipped tests)
        content = re.sub(r'^(\s*)@pytest\.mark\.skipif\(.*\)(\s*)$', r'\1# @pytest.mark.skipif(...) - removed by fix_all_tests.py\2', content, flags=re.MULTILINE)

        # Don't modify skip markers with explicit reasons that indicate they should be skipped
        excluded_reasons = [
            "complex WebSocket mocking",
            "intentionally skipped",
            "requires manual testing",
            "test is a template"
        ]

        # Find all skip markers with their reasons
        skip_markers = re.findall(r'@pytest\.mark\.skip\(reason=["\']([^"\']*)["\']', content)

        # Only replace skip markers that don't contain excluded reasons
        for marker in skip_markers:
            should_exclude = any(excl in marker.lower() for excl in excluded_reasons)
            if not should_exclude:
                content = content.replace(f'@pytest.mark.skip(reason="{marker}")', f'# @pytest.mark.skip(reason="{marker}") - removed by fix_all_tests.py')
                content = content.replace(f"@pytest.mark.skip(reason='{marker}')", f"# @pytest.mark.skip(reason='{marker}') - removed by fix_all_tests.py")

        # Write back modified content
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            modified_files.append(file_path)

    print(f"Modified {len(modified_files)} test files:")
    for file_path in modified_files:
        print(f"  - {file_path}")

    # 3. Run a sample WebRTC test to verify our fixes
    print("\n3. Running WebRTC tests to test our fixes...")
    webrtc_test_path = "test/integration/webrtc/test_webrtc_streaming.py"
    if os.path.exists(webrtc_test_path):
        subprocess.run(
            [sys.executable, "-m", "pytest", webrtc_test_path, "-v"],
            env=os.environ
        )
    else:
        print(f"Warning: WebRTC test file {webrtc_test_path} not found!")
        # Try to find any webrtc test file
        webrtc_files = glob.glob("test/**/test_webrtc*.py", recursive=True)
        if webrtc_files:
            print(f"Found alternative WebRTC test: {webrtc_files[0]}")
            subprocess.run(
                [sys.executable, "-m", "pytest", webrtc_files[0], "-v"],
                env=os.environ
            )
        else:
            print("No WebRTC test files found to run!")

    print("\nCompleted fixing skipped tests.")
    print("\nTo run all tests with WebRTC enabled:")
    print("IPFS_KIT_FORCE_WEBRTC=1 FORCE_WEBRTC_TESTS=1 IPFS_KIT_RUN_ALL_TESTS=1 python -m pytest")

    return 0

if __name__ == "__main__":
    sys.exit(main())
