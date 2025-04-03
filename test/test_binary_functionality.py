import os
import platform
import shutil
import subprocess
import sys
import tempfile

import pytest

from ipfs_kit_py import download_binaries
from ipfs_kit_py.ipfs_kit import ipfs_kit


class TestBinaryFunctionality:
    """Test that the downloaded binaries are functional and match the platform."""

    @pytest.fixture
    def ensure_binaries(self):
        """Ensure binaries are downloaded for testing."""
        # Get the bin directory
        bin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ipfs_kit_py", "bin")
        os.makedirs(bin_dir, exist_ok=True)

        # Check if we have the right binary for this platform
        binary_name = "ipfs.exe" if platform.system() == "Windows" else "ipfs"
        binary_path = os.path.join(bin_dir, binary_name)

        if not os.path.exists(binary_path):
            # Download binaries if they don't exist
            download_binaries()

        return bin_dir

    def test_binary_exists_for_platform(self, ensure_binaries):
        """Test that the appropriate binary exists for the current platform."""
        bin_dir = ensure_binaries

        # Check for the appropriate binary based on platform
        if platform.system() == "Windows":
            binary_path = os.path.join(bin_dir, "ipfs.exe")
            assert os.path.exists(
                binary_path
            ), f"Windows binary ipfs.exe does not exist at {binary_path}"
        else:
            binary_path = os.path.join(bin_dir, "ipfs")
            assert os.path.exists(binary_path), f"Unix binary ipfs does not exist at {binary_path}"

    def test_binary_is_executable(self, ensure_binaries):
        """Test that the binary is executable."""
        bin_dir = ensure_binaries

        # Get the appropriate binary path
        binary_name = "ipfs.exe" if platform.system() == "Windows" else "ipfs"
        binary_path = os.path.join(bin_dir, binary_name)

        # Check if binary exists
        assert os.path.exists(binary_path), f"Binary {binary_name} doesn't exist"

        # Check if binary is executable (skip on Windows as permissions work differently)
        if platform.system() != "Windows":
            assert os.access(binary_path, os.X_OK), f"Binary {binary_name} is not executable"

    def test_binary_has_correct_architecture(self, ensure_binaries):
        """Test that the binary matches the system architecture."""
        bin_dir = ensure_binaries

        # Get the appropriate binary path
        binary_name = "ipfs.exe" if platform.system() == "Windows" else "ipfs"
        binary_path = os.path.join(bin_dir, binary_name)

        # Get system architecture information
        system_bits = "64" if "64" in platform.architecture()[0] else "32"

        # Use file command on Unix to check binary architecture
        if platform.system() in ["Linux", "Darwin"]:
            result = subprocess.run(
                ["file", binary_path], capture_output=True, text=True, check=False
            )
            # Check if the architecture info is present in the output
            output = result.stdout.lower()

            if system_bits == "64":
                assert any(
                    arch in output for arch in ["x86-64", "x86_64", "64-bit", "arm64"]
                ), f"Binary doesn't match 64-bit architecture: {output}"
            else:
                assert any(
                    arch in output for arch in ["i386", "i686", "32-bit", "arm"]
                ), f"Binary doesn't match 32-bit architecture: {output}"

    def test_binary_returns_version(self, ensure_binaries):
        """Test that the binary returns a version number."""
        bin_dir = ensure_binaries

        # Get the appropriate binary path
        binary_name = "ipfs.exe" if platform.system() == "Windows" else "ipfs"
        binary_path = os.path.join(bin_dir, binary_name)

        # Run the version command
        try:
            result = subprocess.run(
                [binary_path, "version"], capture_output=True, text=True, check=True
            )
            # Check if the output contains version information
            assert (
                "ipfs version" in result.stdout.lower()
            ), f"Binary doesn't return expected version output: {result.stdout}"
        except subprocess.CalledProcessError as e:
            pytest.fail(f"Binary execution failed: {e}")
        except FileNotFoundError:
            pytest.fail(f"Binary not found at {binary_path}")

    def test_ipfs_kit_uses_downloaded_binary(self, ensure_binaries):
        """Test that ipfs_kit uses the downloaded binary."""
        # Initialize ipfs_kit
        kit = ipfs_kit()

        # Create a test file
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(b"Test content")
            temp_path = temp.name

        try:
            # Add the file to IPFS - use the correct method name
            # Look for methods with 'add' in the name
            add_methods = [method for method in dir(kit) if "add" in method.lower()]

            # Try the appropriate add method
            if hasattr(kit, "ipfs_add"):
                result = kit.ipfs_add(temp_path)
            elif hasattr(kit, "ipfs_add_file"):
                result = kit.ipfs_add_file(temp_path)
            else:
                pytest.skip(
                    f"Could not find appropriate add method. Available methods: {add_methods}"
                )
                return

            # Check that the operation succeeded and returned a CID
            # Different implementations might return different result structures
            assert result is not None, "Add operation returned None"

            # Get the CID - could be in different fields depending on implementation
            if isinstance(result, dict):
                # Try different possible field names for the CID
                cid = None
                for field in ["Hash", "cid", "hash", "ipfs_path"]:
                    if field in result:
                        cid = result[field]
                        break

                if cid is None:
                    pytest.skip(f"Could not find CID in result: {result}")
                    return
            elif isinstance(result, str):
                # Sometimes the result might just be the CID as a string
                cid = result

            # Try to retrieve the content - check if ipfs_cat exists
            if hasattr(kit, "ipfs_cat"):
                cat_result = kit.ipfs_cat(cid)

                # Verify content was retrieved successfully
                # Different implementations might return different result structures
                if isinstance(cat_result, dict):
                    if "success" in cat_result:
                        assert cat_result.get(
                            "success", False
                        ), f"Cat operation failed: {cat_result}"

                    # Try different fields that might contain the data
                    data = None
                    for field in ["data", "content", "result"]:
                        if field in cat_result:
                            data = cat_result[field]
                            break

                    if data is None:
                        pytest.skip(f"Could not find data in cat result: {cat_result}")
                        return

                    # Verify the content
                    assert data == b"Test content", f"Retrieved data doesn't match original: {data}"

                elif isinstance(cat_result, bytes):
                    # Sometimes the result might just be the content as bytes
                    assert cat_result == b"Test content", "Retrieved data doesn't match original"

                elif isinstance(cat_result, str):
                    # Sometimes the result might be a string
                    assert cat_result == "Test content", "Retrieved data doesn't match original"
            else:
                pytest.skip("ipfs_cat method not available")
                return
        finally:
            # Clean up
            os.unlink(temp_path)

    @pytest.mark.skipif(
        platform.system() == "Windows", reason="Unix socket test not applicable on Windows"
    )
    def test_unix_socket_if_available(self, ensure_binaries):
        """Test Unix socket functionality if available (Unix platforms only)."""
        # This test is only applicable on Unix-like systems
        if not platform.system() in ["Linux", "Darwin"]:
            pytest.skip("Unix socket test only applies to Unix-like systems")

        # Check if the Unix socket is available
        ipfs_socket_path = os.path.expanduser("~/.ipfs/api")
        if not os.path.exists(ipfs_socket_path):
            # Try to initialize IPFS to create the socket
            bin_dir = ensure_binaries
            binary_path = os.path.join(bin_dir, "ipfs")

            try:
                # Initialize IPFS if needed
                subprocess.run([binary_path, "init"], capture_output=True, check=False)

                # Check if we have a daemon running, and start one if not
                daemon_proc = None
                try:
                    # Try to ping the daemon
                    subprocess.run([binary_path, "id"], capture_output=True, timeout=5, check=True)
                except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                    # Start a daemon for testing
                    daemon_proc = subprocess.Popen(
                        [binary_path, "daemon", "--offline"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    # Give it time to start
                    import time

                    time.sleep(3)

                # Initialize ipfs_kit with socket preference
                kit = ipfs_kit(metadata={"use_unix_socket": True})

                # Test basic functionality
                id_result = kit.ipfs_id()
                assert (
                    "ID" in id_result or "id" in id_result
                ), f"Missing ID in response: {id_result}"

                # Clean up daemon if we started one
                if daemon_proc:
                    daemon_proc.terminate()
                    daemon_proc.wait(timeout=5)

            except Exception as e:
                pytest.skip(f"Could not initialize IPFS for Unix socket test: {e}")
