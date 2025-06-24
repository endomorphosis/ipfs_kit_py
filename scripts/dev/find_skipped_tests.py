#!/usr/bin/env python
"""Script to find remaining skipped tests."""

import os
import sys
import subprocess
import re

def main():
    """Find remaining skipped tests in the codebase."""
    # Set environment variables to force features to be available
    os.environ["IPFS_KIT_FORCE_WEBRTC"] = "1"
    os.environ["FORCE_WEBRTC_TESTS"] = "1"
    os.environ["IPFS_KIT_RUN_ALL_TESTS"] = "1"

    # Run pytest in collect-only mode to get all tests
    print("Collecting tests...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-v"],
        capture_output=True,
        text=True,
        env=os.environ
    )

    # Now run pytest with -v to see which tests are skipped
    print("\nRunning tests to find skipped ones...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v"],
        capture_output=True,
        text=True,
        env=os.environ
    )

    # Parse output to find skipped tests
    output = result.stdout

    # Extract skipped tests using regex
    skipped_tests = re.findall(r'(test/.*?\.py::.*?)\s+SKIPPED', output)

    # Print results
    if skipped_tests:
        print(f"\nFound {len(skipped_tests)} skipped tests:")
        for i, test in enumerate(skipped_tests, 1):
            print(f"{i}. {test}")

        # Group by file
        files = {}
        for test in skipped_tests:
            file_path = test.split("::")[0]
            if file_path not in files:
                files[file_path] = []
            files[file_path].append(test)

        print("\nSkipped tests by file:")
        for file_path, tests in files.items():
            print(f"\n{file_path}: {len(tests)} skipped tests")
            for test in tests:
                print(f"  - {test.split('::', 1)[1]}")
    else:
        print("\nNo skipped tests found!")

    return 0

if __name__ == "__main__":
    sys.exit(main())
