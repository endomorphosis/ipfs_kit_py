#!/usr/bin/env python3
"""
Run problematic tests in isolation to verify they pass.
"""

import os
import subprocess
import sys

# List of tests that failed in the main test run
problematic_tests = [
    "test/test_simple_api.py::test_api_config",
    "test/test_simple_api.py::test_api_methods",
    "test/test_simple_api.py::test_file_download",
    "test/test_storage_wal.py::TestStorageWriteAheadLog::test_add_operation",
    "test/test_storage_wal.py::TestStorageWriteAheadLog::test_archiving",
    "test/test_storage_wal.py::TestStorageWriteAheadLog::test_cleanup",
    "test/test_storage_wal.py::TestStorageWriteAheadLog::test_get_all_operations",
    "test/test_storage_wal.py::TestStorageWriteAheadLog::test_get_operations_by_status",
    "test/test_storage_wal.py::TestStorageWriteAheadLog::test_partitioning",
    "test/test_storage_wal.py::TestStorageWriteAheadLog::test_statistics",
    "test/test_storage_wal.py::TestStorageWriteAheadLog::test_update_operation_status",
    "test/test_storage_wal.py::TestStorageWriteAheadLog::test_wait_for_operation",
    "test/test_webrtc_streaming.py::TestWebRTCStreaming::test_ipfs_media_stream_track",
]

# Run each test in a separate process
passed = 0
failed = 0

for test in problematic_tests:
    print(f"\n\nRunning test: {test}")
    print("=" * 80)

    # Run the test in isolation
    cmd = [sys.executable, "-m", "pytest", test, "-v"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Print test output
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    # Track test result
    if result.returncode == 0:
        print(f"✅ PASSED: {test}")
        passed += 1
    else:
        print(f"❌ FAILED: {test}")
        failed += 1

# Print summary
print("\n\n" + "=" * 80)
print(f"SUMMARY: {passed} passed, {failed} failed out of {len(problematic_tests)} tests")
print("=" * 80)

if failed > 0:
    sys.exit(1)
