#\!/usr/bin/env python3
"""
Completely rewrite the ipfs_name_resolve method to fix indentation issues.
"""

import re

file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/models/ipfs_model.py'

# Read the file
with open(file_path, 'r') as f:
    content = f.read()

# Find and remove the problematic method
pattern = r'def ipfs_name_resolve\([^)]*\).*?(?=def|\Z)'
match = re.search(pattern, content, re.DOTALL)

if not match:
    print("Could not find ipfs_name_resolve method")
    exit(1)

# Replacement method with correct indentation
replacement = """def ipfs_name_resolve(self, name: str, recursive: bool = True, nocache: bool = False, timeout: int = None) -> Dict[str, Any]:
    \"\"\"
    Resolve an IPNS name to a CID.

    Args:
        name: IPNS name to resolve
        recursive: Recursively resolve until the result is not an IPNS name
        nocache: Do not use cached entries
        timeout: Maximum time duration for the resolution

    Returns:
        Dictionary with IPNS resolution results
    \"\"\"
    operation_id = f"name_resolve_{int(time.time() * 1000)}"
    start_time = time.time()

    # Initialize result dictionary
    result = {
        "success": False,
        "operation_id": operation_id,
        "operation": "ipfs_name_resolve",
        "name": name,
        "start_time": start_time
    }

    try:
        # Validate required parameters
        if not name:
            raise ValueError("Missing required parameter: name")

        # Check if IPFS client is available
        if not self.ipfs_kit:
            result["error"] = "IPFS client not available"
            result["error_type"] = "configuration_error"
            logger.error("IPFS name resolve failed: IPFS client not available")
            return result

        # Build command with proper arguments
        cmd = ["ipfs", "name", "resolve"]

        # Add optional flags
        if not recursive:
            cmd.append("--recursive=false")
        if nocache:
            cmd.append("--nocache")
        if timeout:
            cmd.extend(["--timeout", f"{timeout}s"])

        # Add the name as the last argument
        # Make sure the name has /ipns/ prefix if not already present
        if not name.startswith("/ipns/") and not name.startswith("ipns/"):
            name = f"/ipns/{name}"
        cmd.append(name)

        # Execute the command
        try:
            cmd_result = self.ipfs_kit.run_ipfs_command(cmd)

            # Handle the case where cmd_result is raw bytes instead of a dictionary
            if isinstance(cmd_result, bytes):
                # Log the raw response for debugging
                logger.debug(f"Raw bytes response from ipfs name resolve: {cmd_result}")
                result["raw_output"] = cmd_result

                # Try to decode the bytes as UTF-8 text
                try:
                    decoded = cmd_result.decode("utf-8", errors="replace").strip()
                    result["success"] = True
                    result["path"] = decoded
                    result["duration_ms"] = (time.time() - start_time) * 1000

                    # Update operation stats
                    if "name_resolve" not in self.operation_stats:
                        self.operation_stats["name_resolve"] = {"count": 0, "errors": 0}
                    self.operation_stats["name_resolve"]["count"] = self.operation_stats["name_resolve"].get("count", 0) + 1
                    self.operation_stats["total_operations"] += 1
                    self.operation_stats["success_count"] += 1

                    logger.info(f"Successfully resolved IPNS name {name} to {result.get('path', 'unknown path')}")
                    return result
                except Exception as decode_error:
                    result["error"] = f"Failed to decode bytes response: {str(decode_error)}"
                    result["error_type"] = "decode_error"
                    logger.error(f"Error decoding IPFS name resolve response: {decode_error}")
                    return result
            elif not isinstance(cmd_result, dict):
                # Unexpected response type
                result["error"] = f"Unexpected response type: {type(cmd_result)}"
                result["error_type"] = "unexpected_response_type"
                logger.error(f"Unexpected response type from IPFS name resolve: {type(cmd_result)}")
                return result

        except AttributeError:
            # If run_ipfs_command doesn't exist, use subprocess directly
            import subprocess
            process = subprocess.run(
                cmd,
                capture_output=True,
                check=False
            )
            cmd_result = {
                "success": process.returncode == 0,
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr
            }

        if not cmd_result.get("success", False):
            stderr = cmd_result.get("stderr", b"")
            # Handle bytes stderr
            if isinstance(stderr, bytes):
                error_msg = stderr.decode("utf-8", errors="replace")
            else:
                error_msg = str(stderr)

            result["error"] = error_msg
            result["error_type"] = "command_error"
            logger.error(f"IPFS name resolve command failed: {result['error']}")
            return result

        # Parse the response
        stdout_raw = cmd_result.get("stdout", b"")

        # Store raw output for debugging
        result["raw_output"] = stdout_raw

        # Handle bytes stdout
        if isinstance(stdout_raw, bytes):
            stdout = stdout_raw.decode("utf-8", errors="replace")
        else:
            stdout = str(stdout_raw)

        # Clean the output (remove whitespace/newlines)
        path = stdout.strip()

        # Update result
        result["success"] = True
        result["path"] = path
        result["duration_ms"] = (time.time() - start_time) * 1000

        # Update operation stats
        if "name_resolve" not in self.operation_stats:
            self.operation_stats["name_resolve"] = {"count": 0, "errors": 0}
        self.operation_stats["name_resolve"]["count"] = self.operation_stats["name_resolve"].get("count", 0) + 1
        self.operation_stats["total_operations"] += 1
        self.operation_stats["success_count"] += 1

        logger.info(f"Successfully resolved IPNS name {name} to {result.get('path', 'unknown path')}")

    except Exception as e:
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["duration_ms"] = (time.time() - start_time) * 1000

        # Update error stats
        if "name_resolve" not in self.operation_stats:
            self.operation_stats["name_resolve"] = {"count": 0, "errors": 0}
        self.operation_stats["name_resolve"]["errors"] = self.operation_stats["name_resolve"].get("errors", 0) + 1
        self.operation_stats["failure_count"] += 1

        logger.error(f"Error resolving IPNS name: {e}")

    return result

"""

# Replace the method in the content
new_content = content.replace(match.group(0), replacement)

# Write the updated content back to the file
with open(file_path, 'w') as f:
    f.write(new_content)

print("Completely replaced ipfs_name_resolve method with correct indentation")
