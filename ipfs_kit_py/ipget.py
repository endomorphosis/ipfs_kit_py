import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
import httpx

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
        self.resources = resources if resources is not None else {}
        self.metadata = metadata if metadata is not None else {}
        self.correlation_id = self.metadata.get("correlation_id", str(uuid.uuid4()))

        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ.get("PATH", "")
        self.path = f"{self.path}:{os.path.join(self.this_dir, 'bin')}"

        try:
            self.config = self.metadata.get("config")
            self.role = self.metadata.get("role", "leecher")
            if self.role not in ["master", "worker", "leecher"]:
                raise IPFSValidationError(
                    f"Invalid role: {self.role}. Must be one of: master, worker, leecher"
                )
            self.cluster_name = self.metadata.get("cluster_name")
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

        self.http_client = httpx.Client(
            transport=httpx.HTTPTransport(retries=3),
            event_hooks={'request': [self._log_request], 'response': [self._log_response]}
        )
        self.ipfs_api_addr = None
        if self.config and 'Addresses' in self.config and 'API' in self.config['Addresses']:
            self.ipfs_api_addr = self.config['Addresses']['API']

    def _log_request(self, request):
        logger.debug(f"Request: {request.method} {request.url}")

    def _log_response(self, response):
        response.read()
        logger.debug(f"Response: {response.status_code} {response.text}")

    def _get_api_addr(self):
        if self.ipfs_api_addr:
            return self.ipfs_api_addr
        
        try:
            result = self._run_cli_command(["ipfs", "config", "Addresses.API"])
            if result['success']:
                self.ipfs_api_addr = result['stdout'].strip()
                return self.ipfs_api_addr
        except Exception as e:
            logger.warning(f"Could not get API address from config: {e}")

        return None

    def _http_request(self, method, path, params=None, data=None, files=None, timeout=30):
        api_addr = self._get_api_addr()
        if not api_addr:
            raise IPFSConnectionError("IPFS API address not configured.")

        base_url = f"http://{api_addr.split('/')[-1]}"
        url = f"{base_url}{path}"

        try:
            response = self.http_client.request(
                method, url, params=params, data=data, files=files, timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            raise IPFSTimeoutError(f"HTTP request timed out: {e}")
        except httpx.RequestError as e:
            raise IPFSConnectionError(f"HTTP request failed: {e}")
        except httpx.HTTPStatusError as e:
            raise IPFSError(f"HTTP request failed with status {e.response.status_code}: {e.response.text}")

    def run_ipget_command(self, cmd_args, check=True, timeout=30, correlation_id=None, shell=False):
        # First, try to execute the command via HTTP API if possible
        try:
            if cmd_args[0] == "ipfs":
                api_path = f"/api/v0/{cmd_args[1]}"
                params = {}
                if len(cmd_args) > 2:
                    for i in range(2, len(cmd_args)):
                        if cmd_args[i].startswith('--'):
                            key, value = cmd_args[i][2:].split('=', 1) if '=' in cmd_args[i] else (cmd_args[i][2:], 'true')
                            params[key] = value
                        else:
                            params['arg'] = cmd_args[i]
                
                response = self._http_request("POST", api_path, params=params, timeout=timeout)
                return {
                    "success": True,
                    "stdout_json": response,
                    "stdout": json.dumps(response),
                    "returncode": 0
                }
        except (IPFSConnectionError, IPFSTimeoutError, IPFSError) as e:
            logger.warning(f"IPFS API request failed, falling back to CLI: {e}")
        except Exception as e:
            logger.warning(f"An unexpected error occurred with IPFS API, falling back to CLI: {e}")

        # Fallback to CLI if API fails or is not applicable
        return self._run_cli_command(cmd_args, check, timeout, correlation_id, shell)

    def _run_cli_command(self, cmd_args, check=True, timeout=30, correlation_id=None, shell=False):
        command_str = cmd_args if isinstance(cmd_args, str) else " ".join(cmd_args)
        operation = command_str.split()[0] if isinstance(command_str, str) else cmd_args[0]

        result = create_result_dict(
            f"run_command_{operation}", correlation_id or self.correlation_id
        )
        result["command"] = command_str

        try:
            env = os.environ.copy()
            env["PATH"] = self.path
            if hasattr(self, "ipfs_path"):
                env["IPFS_PATH"] = self.ipfs_path

            process = subprocess.run(
                cmd_args, capture_output=True, check=check, timeout=timeout, shell=shell, env=env
            )

            result["success"] = True
            result["returncode"] = process.returncode

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
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("ipget_download_object", correlation_id)

        try:
            cid = kwargs.get("cid")
            if not cid:
                return handle_error(result, IPFSValidationError("Missing required parameter: cid"))

            path = kwargs.get("path")
            if not path:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))

            timeout = kwargs.get("timeout", 60)

            if not isinstance(cid, str):
                return handle_error(
                    result, IPFSValidationError(f"CID must be a string, got {type(cid).__name__}")
                )

            if re.search(r'[;&|"`\'$<>]', cid):
                return handle_error(
                    result, IPFSValidationError(f"CID contains invalid characters: {cid}")
                )

            if not isinstance(path, str):
                return handle_error(
                    result, IPFSValidationError(f"Path must be a string, got {type(path).__name__}")
                )

            try:
                parent_dir = os.path.dirname(path)
                if parent_dir and not os.path.exists(parent_dir):
                    logger.debug(f"Creating parent directory: {parent_dir}")
                    os.makedirs(parent_dir, exist_ok=True)
            except Exception as e:
                return handle_error(
                    result, IOError(f"Failed to create directory for download: {str(e)}")
                )

            cmd_args = ["ipfs", "get", cid, "-o", path]

            logger.debug(f"Downloading IPFS object {cid} to {path}")

            cmd_result = self.run_ipget_command(
                cmd_args,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id,
            )

            result["command_result"] = cmd_result

            if not cmd_result.get("success", False) or cmd_result.get("returncode", 1) != 0:
                error_msg = f"Failed to download IPFS object: {cmd_result.get('stderr', '')}"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result

            if not os.path.exists(path):
                error_msg = "Download completed, but output file was not created"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result

            try:
                stat_info = os.stat(path)
                result["metadata"] = {
                    "cid": cid,
                    "path": path,
                    "mtime": stat_info.st_mtime,
                    "filesize": stat_info.st_size,
                    "is_directory": os.path.isdir(path),
                }

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
                result["success"] = True

            return result

        except Exception as e:
            logger.exception(f"Unexpected error in ipget_download_object: {str(e)}")
            return handle_error(result, e)

    def test_ipget(self, **kwargs):
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("test_ipget", correlation_id)

        try:
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

            if "test_cid" in kwargs and kwargs["test_cid"]:
                test_cid = kwargs["test_cid"]

                if "test_path" in kwargs and kwargs["test_path"]:
                    test_path = kwargs["test_path"]
                else:
                    tmp_fd, test_path = tempfile.mkstemp(prefix="ipfs_test_")
                    os.close(tmp_fd)

                logger.debug(f"Testing download with CID {test_cid} to {test_path}")

                download_result = self.ipget_download_object(
                    cid=test_cid, path=test_path, timeout=30, correlation_id=correlation_id
                )

                result["download_test"] = download_result
                result["download_success"] = download_result.get("success", False)

                if "test_path" not in kwargs and os.path.exists(test_path):
                    try:
                        os.remove(test_path)
                        result["temp_file_cleaned"] = True
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp file {test_path}: {str(e)}")
                        result["temp_file_cleaned"] = False

            result["success"] = result["ipfs_available"]
            if "download_success" in result:
                result["success"] = result["success"] and result["download_success"]

            return result

        except Exception as e:
            logger.exception(f"Error testing ipget functionality: {str(e)}")
            return handle_error(result, e)