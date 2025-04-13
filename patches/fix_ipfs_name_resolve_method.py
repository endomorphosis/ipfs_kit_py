#!/usr/bin/env python3
"""
Utility script to fix the ipfs_name_resolve method in the IPFS model.

This script:
1. Finds the ipfs_name_resolve method in the IPFS model.
2. Extracts the current implementation.
3. Replaces it with a properly indented implementation that handles bytes responses.
4. Validates the file syntax after the change.

Usage:
    python3 fix_ipfs_name_resolve_method.py
"""

import os
import sys
import tempfile
import shutil
import re
import py_compile

# Define path to IPFS model file
MODEL_FILE = 'ipfs_kit_py/mcp/models/ipfs_model.py'

def find_method(content):
    """Find the ipfs_name_resolve method in the content."""
    # Find the method definition
    method_pattern = re.compile(r'(\s*)def\s+ipfs_name_resolve\s*\([^)]*\)\s*-?>?\s*[^:]*:')
    match = method_pattern.search(content)
    
    if not match:
        print(f"ERROR: Could not find ipfs_name_resolve method in {MODEL_FILE}")
        return None, None
    
    # Determine indentation level (needed for proper replacemnet)
    indentation = match.group(1)
    method_start_pos = match.start()
    
    # Find the next method (or end of file)
    next_method_pattern = re.compile(r'\n\s*def\s+', re.MULTILINE)
    next_match = next_method_pattern.search(content, match.end())
    
    if next_match:
        method_end_pos = next_match.start()
    else:
        method_end_pos = len(content)
    
    return method_start_pos, method_end_pos, indentation

def create_fixed_method(indentation):
    """Create a fixed implementation of the method with the right indentation."""
    # Base indentation (class level)
    base_indent = indentation
    # Method body indentation (one level deeper)
    body_indent = base_indent + "    "
    
    # The fixed method implementation
    return f"""{base_indent}def ipfs_name_resolve(self, name: str, recursive: bool = True, nocache: bool = False, timeout: int = None) -> Dict[str, Any]:
{body_indent}\"\"\"
{body_indent}Resolve an IPNS name to a CID.

{body_indent}Args:
{body_indent}    name: IPNS name to resolve
{body_indent}    recursive: Recursively resolve until the result is not an IPNS name
{body_indent}    nocache: Do not use cached entries
{body_indent}    timeout: Maximum time duration for the resolution

{body_indent}Returns:
{body_indent}    Dictionary with IPNS resolution results
{body_indent}\"\"\"
{body_indent}operation_id = f"name_resolve_{{int(time.time() * 1000)}}"
{body_indent}start_time = time.time()

{body_indent}# Initialize result dictionary
{body_indent}result = {{
{body_indent}    "success": False,
{body_indent}    "operation_id": operation_id,
{body_indent}    "operation": "ipfs_name_resolve",
{body_indent}    "name": name,
{body_indent}    "start_time": start_time
{body_indent}}}

{body_indent}try:
{body_indent}    # Validate required parameters
{body_indent}    if not name:
{body_indent}        raise ValueError("Missing required parameter: name")

{body_indent}    # Check if IPFS client is available
{body_indent}    if not self.ipfs_kit:
{body_indent}        result["error"] = "IPFS client not available"
{body_indent}        result["error_type"] = "configuration_error"
{body_indent}        logger.error("IPFS name resolve failed: IPFS client not available")
{body_indent}        return result

{body_indent}    # Build command with proper arguments
{body_indent}    cmd = ["ipfs", "name", "resolve"]

{body_indent}    # Add optional flags
{body_indent}    if not recursive:
{body_indent}        cmd.append("--recursive=false")
{body_indent}    if nocache:
{body_indent}        cmd.append("--nocache")
{body_indent}    if timeout:
{body_indent}        cmd.extend(["--timeout", f"{{timeout}}s"])

{body_indent}    # Add the name as the last argument
{body_indent}    # Make sure the name has /ipns/ prefix if not already present
{body_indent}    if not name.startswith("/ipns/") and not name.startswith("ipns/"):
{body_indent}        name = f"/ipns/{{name}}"
{body_indent}    cmd.append(name)

{body_indent}    # Execute the command
{body_indent}    try:
{body_indent}        cmd_result = self.ipfs_kit.run_ipfs_command(cmd)
{body_indent}        
{body_indent}        # Handle the case where cmd_result is raw bytes instead of a dictionary
{body_indent}        if isinstance(cmd_result, bytes):
{body_indent}            # Log the raw response for debugging
{body_indent}            logger.debug(f"Raw bytes response from ipfs name resolve: {{cmd_result}}")
{body_indent}            result["raw_output"] = cmd_result
{body_indent}            
{body_indent}            # Try to decode the bytes as UTF-8 text
{body_indent}            try:
{body_indent}                decoded = cmd_result.decode("utf-8", errors="replace").strip()
{body_indent}                result["success"] = True
{body_indent}                result["path"] = decoded
{body_indent}                result["duration_ms"] = (time.time() - start_time) * 1000
{body_indent}                
{body_indent}                # Update operation stats
{body_indent}                if "name_resolve" not in self.operation_stats:
{body_indent}                    self.operation_stats["name_resolve"] = {{"count": 0, "errors": 0}}
{body_indent}                self.operation_stats["name_resolve"]["count"] = self.operation_stats["name_resolve"].get("count", 0) + 1
{body_indent}                self.operation_stats["total_operations"] += 1
{body_indent}                self.operation_stats["success_count"] += 1
{body_indent}                
{body_indent}                logger.info(f"Successfully resolved IPNS name {{name}} to {{result.get('path', 'unknown path')}}")
{body_indent}                return result
{body_indent}            except Exception as decode_error:
{body_indent}                result["error"] = f"Failed to decode bytes response: {{str(decode_error)}}"
{body_indent}                result["error_type"] = "decode_error"
{body_indent}                logger.error(f"Error decoding IPFS name resolve response: {{decode_error}}")
{body_indent}                return result
{body_indent}        elif not isinstance(cmd_result, dict):
{body_indent}            # Unexpected response type
{body_indent}            result["error"] = f"Unexpected response type: {{type(cmd_result)}}"
{body_indent}            result["error_type"] = "unexpected_response_type"
{body_indent}            logger.error(f"Unexpected response type from IPFS name resolve: {{type(cmd_result)}}")
{body_indent}            return result
{body_indent}            
{body_indent}    except AttributeError:
{body_indent}        # If run_ipfs_command doesn't exist, use subprocess directly
{body_indent}        import subprocess
{body_indent}        process = subprocess.run(
{body_indent}            cmd,
{body_indent}            capture_output=True,
{body_indent}            check=False
{body_indent}        )
{body_indent}        cmd_result = {{
{body_indent}            "success": process.returncode == 0,
{body_indent}            "returncode": process.returncode,
{body_indent}            "stdout": process.stdout,
{body_indent}            "stderr": process.stderr
{body_indent}        }}

{body_indent}    if not cmd_result.get("success", False):
{body_indent}        stderr = cmd_result.get("stderr", b"")
{body_indent}        # Handle bytes stderr
{body_indent}        if isinstance(stderr, bytes):
{body_indent}            error_msg = stderr.decode("utf-8", errors="replace")
{body_indent}        else:
{body_indent}            error_msg = str(stderr)
{body_indent}        
{body_indent}        result["error"] = error_msg
{body_indent}        result["error_type"] = "command_error"
{body_indent}        logger.error(f"IPFS name resolve command failed: {{result['error']}}")
{body_indent}        return result

{body_indent}    # Parse the response
{body_indent}    stdout_raw = cmd_result.get("stdout", b"")

{body_indent}    # Store raw output for debugging
{body_indent}    result["raw_output"] = stdout_raw

{body_indent}    # Handle bytes stdout
{body_indent}    if isinstance(stdout_raw, bytes):
{body_indent}        stdout = stdout_raw.decode("utf-8", errors="replace")
{body_indent}    else:
{body_indent}        stdout = str(stdout_raw)

{body_indent}    # Clean the output (remove whitespace/newlines)
{body_indent}    path = stdout.strip()

{body_indent}    # Update result
{body_indent}    result["success"] = True
{body_indent}    result["path"] = path
{body_indent}    result["duration_ms"] = (time.time() - start_time) * 1000

{body_indent}    # Update operation stats
{body_indent}    if "name_resolve" not in self.operation_stats:
{body_indent}        self.operation_stats["name_resolve"] = {{"count": 0, "errors": 0}}
{body_indent}    self.operation_stats["name_resolve"]["count"] = self.operation_stats["name_resolve"].get("count", 0) + 1
{body_indent}    self.operation_stats["total_operations"] += 1
{body_indent}    self.operation_stats["success_count"] += 1

{body_indent}    logger.info(f"Successfully resolved IPNS name {{name}} to {{result.get('path', 'unknown path')}}")

{body_indent}except Exception as e:
{body_indent}    result["error"] = str(e)
{body_indent}    result["error_type"] = type(e).__name__
{body_indent}    result["duration_ms"] = (time.time() - start_time) * 1000

{body_indent}    # Update error stats
{body_indent}    if "name_resolve" not in self.operation_stats:
{body_indent}        self.operation_stats["name_resolve"] = {{"count": 0, "errors": 0}}
{body_indent}    self.operation_stats["name_resolve"]["errors"] = self.operation_stats["name_resolve"].get("errors", 0) + 1
{body_indent}    self.operation_stats["failure_count"] += 1

{body_indent}    logger.error(f"Error resolving IPNS name: {{e}}")

{body_indent}return result"""

def fix_file():
    """Find and fix the ipfs_name_resolve method in the IPFS model file."""
    # Check if file exists
    if not os.path.exists(MODEL_FILE):
        print(f"ERROR: File not found: {MODEL_FILE}")
        return False
        
    # Read the file content
    with open(MODEL_FILE, 'r') as f:
        content = f.read()
        
    # Find the method
    method_start_pos, method_end_pos, indentation = find_method(content)
    
    if method_start_pos is None:
        return False
        
    # Create a fixed version of the method
    fixed_method = create_fixed_method(indentation)
    
    # Create new content with the fixed method
    new_content = content[:method_start_pos] + fixed_method + content[method_end_pos:]
    
    # Create a backup of the original file
    backup_file = MODEL_FILE + '.orig_fix'
    shutil.copy2(MODEL_FILE, backup_file)
    print(f"Created backup: {backup_file}")
    
    # Write the new content
    with open(MODEL_FILE, 'w') as f:
        f.write(new_content)
        
    print(f"Updated {MODEL_FILE} with fixed ipfs_name_resolve method")
    
    # Validate the file
    try:
        py_compile.compile(MODEL_FILE, doraise=True)
        print("Syntax validation passed!")
        return True
    except Exception as e:
        print(f"ERROR: Syntax validation failed: {e}")
        # Restore from backup
        shutil.copy2(backup_file, MODEL_FILE)
        print(f"Restored original file from backup")
        return False

if __name__ == "__main__":
    if fix_file():
        print("Successfully fixed ipfs_name_resolve method")
        print("This method now properly handles bytes responses, enhancing the robustness of the MCP server")
    else:
        print("Failed to fix ipfs_name_resolve method")
        print("Manual intervention may be required")