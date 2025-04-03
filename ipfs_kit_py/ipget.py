import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid

from .error import (
    IPFSConfigurationError,
    IPFSConnectionError,
    IPFSContentNotFoundError,
    IPFSError,
    IPFSPinningError,
    IPFSTimeoutError,
    IPFSValidationError,
    create_result_dict,
    handle_error,
    perform_with_retry,
)

# Configure logger
logger = logging.getLogger(__name__)


class ipget:
    def __init__(self, resources=None, metadata=None):
        """Initialize IPFS ipget functionality.

        Args:
            resources: Dictionary containing system resources
            metadata: Dictionary containing configuration metadata
                - config: Configuration settings
                - role: Node role (master, worker, leecher)
                - ipfs_path: Path to IPFS configuration
                - cluster_name: Name of the IPFS cluster to follow
        """
        # Initialize basic attributes
        self.resources = resources if resources is not None else {}
        self.metadata = metadata if metadata is not None else {}
        self.correlation_id = self.metadata.get("correlation_id", str(uuid.uuid4()))

        # Set up path configuration for binaries
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ.get("PATH", "")
        self.path = f"{self.path}:{os.path.join(self.this_dir, 'bin')}"

        # Extract and validate metadata
        try:
            # Extract configuration settings
            self.config = self.metadata.get("config")

            # Extract and validate role
            self.role = self.metadata.get("role", "leecher")
            if self.role not in ["master", "worker", "leecher"]:
                raise IPFSValidationError(
                    f"Invalid role: {self.role}. Must be one of: master, worker, leecher"
                )

            # Extract cluster name if provided
            self.cluster_name = self.metadata.get("cluster_name")

            # Extract IPFS path
            self.ipfs_path = self.metadata.get("ipfs_path", os.path.expanduser("~/.ipfs"))

            logger.debug(
                f"Initialized IPFS ipget with role={self.role}, "
                f"correlation_id={self.correlation_id}"
            )

        except Exception as e:
            logger.error(f"Error initializing IPFS ipget: {str(e)}")
            if isinstance(e, IPFSValidationError):
                raise
            else:
                raise IPFSConfigurationError(f"Failed to initialize IPFS ipget: {str(e)}")

    def run_ipget_command(self, cmd_args, check=True, timeout=30, correlation_id=None, shell=False):
        """Run IPFS ipget command with proper error handling.

        Args:
            cmd_args: Command and arguments as a list or string
            check: Whether to raise exception on non-zero exit code
            timeout: Command timeout in seconds
            correlation_id: ID for tracking related operations
            shell: Whether to use shell execution (avoid if possible)

        Returns:
            Dictionary with command result information
        """
        # Create standardized result dictionary
        command_str = cmd_args if isinstance(cmd_args, str) else " ".join(cmd_args)
        operation = command_str.split()[0] if isinstance(command_str, str) else cmd_args[0]

        result = create_result_dict(
            f"run_command_{operation}", correlation_id or self.correlation_id
        )
        result["command"] = command_str

        try:
            # Add environment variables if needed
            env = os.environ.copy()
            env["PATH"] = self.path
            if hasattr(self, "ipfs_path"):
                env["IPFS_PATH"] = self.ipfs_path

            # Never use shell=True unless absolutely necessary for security
            process = subprocess.run(
                cmd_args, capture_output=True, check=check, timeout=timeout, shell=shell, env=env
            )

            # Process completed successfully
            result["success"] = True
            result["returncode"] = process.returncode

            # Decode stdout and stderr if they exist
            if process.stdout:
                try:
                    result["stdout"] = process.stdout.decode("utf-8")
                except UnicodeDecodeError:
                    result["stdout"] = process.stdout

            if process.stderr:
                try:
                    result["stderr"] = process.stderr.decode("utf-8")
                except UnicodeDecodeError:
                    result["stderr"] = process.stderr

            return result

        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {timeout} seconds: {command_str}"
            logger.error(error_msg)
            return handle_error(result, IPFSTimeoutError(error_msg))

        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed with return code {e.returncode}: {command_str}"
            result["returncode"] = e.returncode

            # Try to decode stdout and stderr
            if e.stdout:
                try:
                    result["stdout"] = e.stdout.decode("utf-8")
                except UnicodeDecodeError:
                    result["stdout"] = e.stdout

            if e.stderr:
                try:
                    result["stderr"] = e.stderr.decode("utf-8")
                except UnicodeDecodeError:
                    result["stderr"] = e.stderr

            logger.error(f"{error_msg}\nStderr: {result.get('stderr', '')}")
            return handle_error(result, IPFSError(error_msg))

        except FileNotFoundError as e:
            error_msg = f"Command binary not found: {command_str}"
            logger.error(error_msg)
            return handle_error(result, IPFSConfigurationError(error_msg))

        except Exception as e:
            error_msg = f"Failed to execute command: {str(e)}"
            logger.exception(f"Exception running command: {command_str}")
            return handle_error(result, e)

    def ipget_download_object(self, **kwargs):
        """Download an IPFS object (file or directory) to a local path.

        Args:
            **kwargs: Arguments for the download operation
                - cid: The IPFS Content Identifier to download
                - path: The local path to save the downloaded content
                - timeout: Optional timeout in seconds (default: 60)
                - correlation_id: Optional ID for tracking related operations

        Returns:
            Dictionary with the operation result and metadata
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("ipget_download_object", correlation_id)

        try:
            # Validate required parameters
            cid = kwargs.get("cid")
            if not cid:
                return handle_error(result, IPFSValidationError("Missing required parameter: cid"))

            path = kwargs.get("path")
            if not path:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))

            # Set timeout for the operation
            timeout = kwargs.get("timeout", 60)

            # Validate CID format (basic check)
            if not isinstance(cid, str):
                return handle_error(
                    result, IPFSValidationError(f"CID must be a string, got {type(cid).__name__}")
                )

            # Remove any potentially unsafe characters from CID
            if re.search(r'[;&|"`\'$<>]', cid):
                return handle_error(
                    result, IPFSValidationError(f"CID contains invalid characters: {cid}")
                )

            # Validate path and create parent directory if needed
            if not isinstance(path, str):
                return handle_error(
                    result, IPFSValidationError(f"Path must be a string, got {type(path).__name__}")
                )

            # Create directory structure if it doesn't exist
            try:
                parent_dir = os.path.dirname(path)
                if parent_dir and not os.path.exists(parent_dir):
                    logger.debug(f"Creating parent directory: {parent_dir}")
                    os.makedirs(parent_dir, exist_ok=True)
            except Exception as e:
                return handle_error(
                    result, IOError(f"Failed to create directory for download: {str(e)}")
                )

            # Build command arguments (using ipfs get, which is more reliable than ipget for some uses)
            cmd_args = ["ipfs", "get", cid, "-o", path]

            logger.debug(f"Downloading IPFS object {cid} to {path}")

            # Execute the command with environment variables
            cmd_result = self.run_ipget_command(
                cmd_args,
                check=False,  # Don't raise exception, we'll handle errors
                timeout=timeout,
                correlation_id=correlation_id,
            )

            result["command_result"] = cmd_result

            # Check if the download was successful
            if not cmd_result.get("success", False) or cmd_result.get("returncode", 1) != 0:
                error_msg = f"Failed to download IPFS object: {cmd_result.get('stderr', '')}"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result

            # Check if the file was actually created
            if not os.path.exists(path):
                error_msg = "Download completed, but output file was not created"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result

            # Collect metadata about the downloaded file/directory
            try:
                stat_info = os.stat(path)
                result["metadata"] = {
                    "cid": cid,
                    "path": path,
                    "mtime": stat_info.st_mtime,
                    "filesize": stat_info.st_size,
                    "is_directory": os.path.isdir(path),
                }

                # Additional content info for files
                if os.path.isfile(path):
                    result["metadata"]["file_type"] = "regular"
                elif os.path.islink(path):
                    result["metadata"]["file_type"] = "symlink"
                    result["metadata"]["link_target"] = os.readlink(path)

                logger.info(f"Successfully downloaded {cid} to {path} ({stat_info.st_size} bytes)")
                result["success"] = True

            except Exception as e:
                logger.warning(f"Download succeeded but metadata collection failed: {str(e)}")
                result["metadata"] = {"cid": cid, "path": path}
                result["metadata_error"] = str(e)
                result["success"] = True  # Still consider download successful

            return result

        except Exception as e:
            logger.exception(f"Unexpected error in ipget_download_object: {str(e)}")
            return handle_error(result, e)

    # NOTE: Create test that feeds ipget_download_object with a CID and the path to local_path

    def test_ipget(self, **kwargs):
        """Test if ipget/ipfs get functionality is available.

        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - test_cid: Optional test CID to verify download (default: uses a small test CID)
                - test_path: Optional path to save test download (default: uses a temp file)

        Returns:
            Dictionary with test results
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("test_ipget", correlation_id)

        try:
            # First test if ipfs command is available
            cmd_result = self.run_ipget_command(
                ["which", "ipfs"], check=False, correlation_id=correlation_id
            )

            if not cmd_result.get("success", False) or cmd_result.get("returncode", 1) != 0:
                logger.warning("ipfs command not found in PATH")
                result["success"] = False
                result["ipfs_available"] = False
                return result

            result["ipfs_command"] = cmd_result.get("stdout", "").strip()
            result["ipfs_available"] = True

            # Optionally test actual download if test_cid is provided
            if "test_cid" in kwargs and kwargs["test_cid"]:
                test_cid = kwargs["test_cid"]

                # Use provided test path or create a temporary file
                if "test_path" in kwargs and kwargs["test_path"]:
                    test_path = kwargs["test_path"]
                else:
                    # Create a temporary file for testing
                    tmp_fd, test_path = tempfile.mkstemp(prefix="ipfs_test_")
                    os.close(tmp_fd)  # Close the file descriptor

                logger.debug(f"Testing download with CID {test_cid} to {test_path}")

                # Try to download a small test object
                download_result = self.ipget_download_object(
                    cid=test_cid, path=test_path, timeout=30, correlation_id=correlation_id
                )

                result["download_test"] = download_result
                result["download_success"] = download_result.get("success", False)

                # Clean up temp file if we created one
                if "test_path" not in kwargs and os.path.exists(test_path):
                    try:
                        os.remove(test_path)
                        result["temp_file_cleaned"] = True
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp file {test_path}: {str(e)}")
                        result["temp_file_cleaned"] = False

            # Set overall success
            result["success"] = result["ipfs_available"]
            if "download_success" in result:
                result["success"] = result["success"] and result["download_success"]

            return result

        except Exception as e:
            logger.exception(f"Error testing ipget functionality: {str(e)}")
            return handle_error(result, e)


# if __name__ == "__main__":
#     this_ipget = ipget(None, metadata={"role":"leecher","ipfs_path":"/tmp/test/"})
#     results = this_ipget.test_ipget()
#     print(results)
#     pass

# TODO:
# TEST THIS COMMAND FOR OTHER PATHS
# export IPFS_PATH=/mnt/ipfs/ipfs && ipfs get QmccfbkWLYs9K3yucc6b3eSt8s8fKcyRRt24e3CDaeRhM1 -o /tmp/test
