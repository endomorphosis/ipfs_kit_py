#!/usr/bin/env python3
"""
IPFS MCP Tools Integration Module

This module provides core IPFS operations for the MCP server,
including add, cat, ls, and pin management.
"""

import os
import sys
import json
import base64
import logging
import anyio
import tempfile
from typing import Dict, List, Any, Optional, Union, BinaryIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import ipfshttpclient, fall back to using subprocess if not available
try:
    import ipfshttpclient
    IPFS_CLIENT_AVAILABLE = True
except ImportError:
    logger.warning("ipfshttpclient not available, falling back to subprocess")
    IPFS_CLIENT_AVAILABLE = False
    import subprocess

def register_ipfs_tools(mcp_server) -> bool:
    """
    Register IPFS tools with the MCP server.

    Args:
        mcp_server: The MCP server instance

    Returns:
        bool: True if registration was successful, False otherwise
    """
    logger.info("Registering IPFS tools...")

    try:
        # Check if server has register_tool method
        if not hasattr(mcp_server, "register_tool"):
            logger.error("MCP server does not have register_tool method")
            return False

        # Register tools
        tools_registered = 0

        # Add content to IPFS
        async def ipfs_add(content=None, file_path=None, file_name=None, pin=True):
            """Add content to IPFS"""
            try:
                # Validate input
                if content is None and file_path is None:
                    return {"success": False, "error": "Either content or file_path must be provided"}

                # Determine file_name if not provided
                if file_name is None:
                    if file_path:
                        file_name = os.path.basename(file_path)
                    else:
                        file_name = "file"

                # Use ipfshttpclient if available
                if IPFS_CLIENT_AVAILABLE:
                    with ipfshttpclient.connect() as client:
                        # Add content or file
                        if content is not None:
                            # Create a temporary file
                            with tempfile.NamedTemporaryFile(delete=False) as temp:
                                # Write content to the file
                                if isinstance(content, str):
                                    temp.write(content.encode('utf-8'))
                                elif isinstance(content, bytes):
                                    temp.write(content)
                                else:
                                    # Try to convert to string
                                    temp.write(str(content).encode('utf-8'))

                                temp_path = temp.name

                            try:
                                # Add the file to IPFS
                                result = client.add(temp_path, pin=pin)

                                # Cleanup the temporary file
                                os.unlink(temp_path)

                                if isinstance(result, list):
                                    # If multiple entries (directory), use the last one (root)
                                    result = result[-1]

                                return {
                                    "success": True,
                                    "cid": result["Hash"],
                                    "size": result["Size"],
                                    "name": file_name
                                }
                            except Exception as e:
                                # Cleanup the temporary file in case of error
                                if os.path.exists(temp_path):
                                    os.unlink(temp_path)
                                raise e

                        else:  # Use file_path
                            if not os.path.exists(file_path):
                                return {"success": False, "error": f"File does not exist: {file_path}"}

                            # Add the file to IPFS
                            result = client.add(file_path, pin=pin)

                            if isinstance(result, list):
                                # If multiple entries (directory), use the last one (root)
                                result = result[-1]

                            return {
                                "success": True,
                                "cid": result["Hash"],
                                "size": result["Size"],
                                "name": file_name
                            }

                else:  # Use subprocess
                    # Create a temporary file if content is provided
                    if content is not None:
                        with tempfile.NamedTemporaryFile(delete=False) as temp:
                            # Write content to the file
                            if isinstance(content, str):
                                temp.write(content.encode('utf-8'))
                            elif isinstance(content, bytes):
                                temp.write(content)
                            else:
                                # Try to convert to string
                                temp.write(str(content).encode('utf-8'))

                            temp_path = temp.name

                        file_to_add = temp_path
                    else:
                        file_to_add = file_path

                        if not os.path.exists(file_to_add):
                            return {"success": False, "error": f"File does not exist: {file_to_add}"}

                    try:
                        # Add the file to IPFS
                        cmd = ["ipfs", "add", "--quiet", file_to_add]
                        if not pin:
                            cmd.append("--pin=false")

                        process = subprocess.run(cmd, capture_output=True, text=True, check=True)

                        # Get the CID from the output
                        cid = process.stdout.strip()

                        # Cleanup the temporary file if created
                        if content is not None and os.path.exists(temp_path):
                            os.unlink(temp_path)

                        # Get the file size
                        cmd_stat = ["ipfs", "files", "stat", f"/ipfs/{cid}"]
                        process_stat = subprocess.run(cmd_stat, capture_output=True, text=True, check=True)

                        # Parse the output to get the size
                        stat_output = process_stat.stdout.strip()
                        size = 0
                        for line in stat_output.split("\n"):
                            if line.startswith("Size:"):
                                size = int(line.split(":")[1].strip())
                                break

                        return {
                            "success": True,
                            "cid": cid,
                            "size": size,
                            "name": file_name
                        }

                    except subprocess.CalledProcessError as e:
                        # Cleanup the temporary file if created
                        if content is not None and os.path.exists(temp_path):
                            os.unlink(temp_path)

                        return {
                            "success": False,
                            "error": f"IPFS add failed: {e.stderr}"
                        }

                    except Exception as e:
                        # Cleanup the temporary file if created
                        if content is not None and os.path.exists(temp_path):
                            os.unlink(temp_path)

                        return {
                            "success": False,
                            "error": f"IPFS add failed: {str(e)}"
                        }

            except Exception as e:
                logger.error(f"Error in ipfs_add: {e}")
                return {"success": False, "error": str(e)}

        mcp_server.register_tool("ipfs_add", ipfs_add)
        tools_registered += 1

        # Cat (retrieve) content from IPFS
        async def ipfs_cat(cid, offset=0, length=None, timeout=30):
            """Retrieve content from IPFS"""
            try:
                # Validate CID
                if not cid or not isinstance(cid, str):
                    return {"success": False, "error": "Invalid CID"}

                # Use ipfshttpclient if available
                if IPFS_CLIENT_AVAILABLE:
                    with ipfshttpclient.connect() as client:
                        try:
                            # Get the content
                            content = client.cat(cid, offset=offset, length=length, timeout=timeout)

                            # Get the size
                            stats = client.files.stat(f"/ipfs/{cid}")

                            # Convert binary data to base64
                            content_base64 = base64.b64encode(content).decode('utf-8')

                            return {
                                "success": True,
                                "content_base64": content_base64,
                                "size": stats["Size"] if "Size" in stats else len(content)
                            }
                        except Exception as e:
                            return {"success": False, "error": f"IPFS cat failed: {str(e)}"}

                else:  # Use subprocess
                    try:
                        # Build the command
                        cmd = ["ipfs", "cat"]

                        # Add offset and length if provided
                        if offset > 0:
                            cmd.extend(["--offset", str(offset)])
                        if length is not None:
                            cmd.extend(["--length", str(length)])

                        cmd.append(cid)

                        # Run the command
                        process = subprocess.run(cmd, capture_output=True, check=True, timeout=timeout)

                        # Get the content from the output
                        content = process.stdout

                        # Get the size
                        cmd_stat = ["ipfs", "files", "stat", f"/ipfs/{cid}"]
                        process_stat = subprocess.run(cmd_stat, capture_output=True, text=True, check=True)

                        # Parse the output to get the size
                        stat_output = process_stat.stdout.strip()
                        size = 0
                        for line in stat_output.split("\n"):
                            if line.startswith("Size:"):
                                size = int(line.split(":")[1].strip())
                                break

                        # Convert binary data to base64
                        content_base64 = base64.b64encode(content).decode('utf-8')

                        return {
                            "success": True,
                            "content_base64": content_base64,
                            "size": size
                        }

                    except subprocess.CalledProcessError as e:
                        return {
                            "success": False,
                            "error": f"IPFS cat failed: {e.stderr.decode('utf-8')}"
                        }

                    except subprocess.TimeoutExpired:
                        return {
                            "success": False,
                            "error": f"IPFS cat timed out after {timeout} seconds"
                        }

                    except Exception as e:
                        return {
                            "success": False,
                            "error": f"IPFS cat failed: {str(e)}"
                        }

            except Exception as e:
                logger.error(f"Error in ipfs_cat: {e}")
                return {"success": False, "error": str(e)}

        mcp_server.register_tool("ipfs_cat", ipfs_cat)
        tools_registered += 1

        # List directory contents in IPFS
        async def ipfs_ls(cid, recursive=False, timeout=30):
            """List directory contents in IPFS"""
            try:
                # Validate CID
                if not cid or not isinstance(cid, str):
                    return {"success": False, "error": "Invalid CID"}

                # Use ipfshttpclient if available
                if IPFS_CLIENT_AVAILABLE:
                    with ipfshttpclient.connect() as client:
                        try:
                            # List the directory contents
                            result = client.ls(cid)

                            # Process the result
                            entries = []
                            for entry in result.get("Objects", []):
                                for link in entry.get("Links", []):
                                    entries.append({
                                        "name": link.get("Name", ""),
                                        "cid": link.get("Hash", ""),
                                        "size": link.get("Size", 0),
                                        "type": link.get("Type", 0)
                                    })

                            # If recursive, handle the entries
                            if recursive and entries:
                                try:
                                    # Process directories recursively
                                    all_entries = entries.copy()
                                    for entry in entries:
                                        if entry.get("type") == 1:  # Directory
                                            try:
                                                sub_result = await ipfs_ls(entry["cid"], recursive=True)
                                                if sub_result.get("success", False):
                                                    for sub_entry in sub_result.get("entries", []):
                                                        # Prefix the name with the parent directory
                                                        sub_entry["name"] = f"{entry['name']}/{sub_entry['name']}"
                                                        all_entries.append(sub_entry)
                                            except Exception as sub_e:
                                                logger.warning(f"Error in recursive ls for {entry['cid']}: {sub_e}")

                                    entries = all_entries
                                except Exception as rec_e:
                                    logger.warning(f"Error in recursive processing: {rec_e}")

                            return {
                                "success": True,
                                "entries": entries,
                                "count": len(entries)
                            }
                        except Exception as e:
                            return {"success": False, "error": f"IPFS ls failed: {str(e)}"}

                else:  # Use subprocess
                    try:
                        # Build the command
                        cmd = ["ipfs", "ls"]

                        # Add recursive flag if requested
                        if recursive:
                            cmd.append("-r")

                        cmd.append(cid)

                        # Run the command
                        process = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)

                        # Parse the output
                        entries = []
                        for line in process.stdout.strip().split("\n"):
                            if not line:
                                continue

                            # Parse the line
                            parts = line.split()
                            if len(parts) >= 3:
                                entry_cid = parts[0]
                                entry_size = parts[1]
                                entry_name = " ".join(parts[2:])

                                # Determine type
                                entry_type = 0  # File
                                if entry_size.endswith("/"):
                                    entry_type = 1  # Directory
                                    entry_size = entry_size[:-1]

                                # Convert size to bytes
                                try:
                                    size = int(entry_size)
                                except ValueError:
                                    # Handle human-readable sizes (e.g., 5.2 KiB)
                                    size_str = entry_size.lower()
                                    multiplier = 1
                                    if "kib" in size_str:
                                        multiplier = 1024
                                    elif "mib" in size_str:
                                        multiplier = 1024 * 1024
                                    elif "gib" in size_str:
                                        multiplier = 1024 * 1024 * 1024

                                    try:
                                        size_val = float(size_str.split()[0])
                                        size = int(size_val * multiplier)
                                    except:
                                        size = 0

                                entries.append({
                                    "name": entry_name,
                                    "cid": entry_cid,
                                    "size": size,
                                    "type": entry_type
                                })

                        return {
                            "success": True,
                            "entries": entries,
                            "count": len(entries)
                        }

                    except subprocess.CalledProcessError as e:
                        return {
                            "success": False,
                            "error": f"IPFS ls failed: {e.stderr}"
                        }

                    except subprocess.TimeoutExpired:
                        return {
                            "success": False,
                            "error": f"IPFS ls timed out after {timeout} seconds"
                        }

                    except Exception as e:
                        return {
                            "success": False,
                            "error": f"IPFS ls failed: {str(e)}"
                        }

            except Exception as e:
                logger.error(f"Error in ipfs_ls: {e}")
                return {"success": False, "error": str(e)}

        mcp_server.register_tool("ipfs_ls", ipfs_ls)
        tools_registered += 1

        # List pinned items
        async def ipfs_pin_ls(type="all", timeout=30):
            """List pinned items"""
            try:
                # Validate type
                valid_types = ["all", "direct", "indirect", "recursive"]
                if type not in valid_types:
                    return {"success": False, "error": f"Invalid pin type. Must be one of: {', '.join(valid_types)}"}

                # Use ipfshttpclient if available
                if IPFS_CLIENT_AVAILABLE:
                    with ipfshttpclient.connect() as client:
                        try:
                            # List the pinned items
                            result = client.pin.ls(type=type)

                            # Process the result
                            pins = result.get("Keys", {})

                            return {
                                "success": True,
                                "pins": pins,
                                "count": len(pins)
                            }
                        except Exception as e:
                            return {"success": False, "error": f"IPFS pin ls failed: {str(e)}"}

                else:  # Use subprocess
                    try:
                        # Build the command
                        cmd = ["ipfs", "pin", "ls"]

                        # Add type if not "all"
                        if type != "all":
                            cmd.extend(["--type", type])

                        # Run the command
                        process = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)

                        # Parse the output
                        pins = {}
                        for line in process.stdout.strip().split("\n"):
                            if not line:
                                continue

                            # Parse the line
                            parts = line.split()
                            if len(parts) >= 2:
                                cid = parts[0]
                                pin_type = parts[1].strip()

                                # Remove the trailing colon
                                if pin_type.endswith(":"):
                                    pin_type = pin_type[:-1]

                                pins[cid] = {"type": pin_type}

                        return {
                            "success": True,
                            "pins": pins,
                            "count": len(pins)
                        }

                    except subprocess.CalledProcessError as e:
                        return {
                            "success": False,
                            "error": f"IPFS pin ls failed: {e.stderr}"
                        }

                    except subprocess.TimeoutExpired:
                        return {
                            "success": False,
                            "error": f"IPFS pin ls timed out after {timeout} seconds"
                        }

                    except Exception as e:
                        return {
                            "success": False,
                            "error": f"IPFS pin ls failed: {str(e)}"
                        }

            except Exception as e:
                logger.error(f"Error in ipfs_pin_ls: {e}")
                return {"success": False, "error": str(e)}

        mcp_server.register_tool("ipfs_pin_ls", ipfs_pin_ls)
        tools_registered += 1

        # Get IPFS node info
        async def ipfs_id(timeout=30):
            """Get IPFS node information"""
            try:
                # Use ipfshttpclient if available
                if IPFS_CLIENT_AVAILABLE:
                    with ipfshttpclient.connect() as client:
                        try:
                            # Get the node ID
                            result = client.id()

                            return {
                                "success": True,
                                "id": result
                            }
                        except Exception as e:
                            return {"success": False, "error": f"IPFS id failed: {str(e)}"}

                else:  # Use subprocess
                    try:
                        # Run the command
                        process = subprocess.run(["ipfs", "id"], capture_output=True, text=True, check=True, timeout=timeout)

                        # Parse the output
                        try:
                            result = json.loads(process.stdout)

                            return {
                                "success": True,
                                "id": result
                            }
                        except json.JSONDecodeError:
                            return {
                                "success": False,
                                "error": "Failed to parse IPFS id output as JSON"
                            }

                    except subprocess.CalledProcessError as e:
                        return {
                            "success": False,
                            "error": f"IPFS id failed: {e.stderr}"
                        }

                    except subprocess.TimeoutExpired:
                        return {
                            "success": False,
                            "error": f"IPFS id timed out after {timeout} seconds"
                        }

                    except Exception as e:
                        return {
                            "success": False,
                            "error": f"IPFS id failed: {str(e)}"
                        }

            except Exception as e:
                logger.error(f"Error in ipfs_id: {e}")
                return {"success": False, "error": str(e)}

        mcp_server.register_tool("ipfs_id", ipfs_id)
        tools_registered += 1

        logger.info(f"Successfully registered {tools_registered} IPFS tools")
        return True
    except Exception as e:
        logger.error(f"Error registering IPFS tools: {e}")
        return False

if __name__ == "__main__":
    print("IPFS MCP Tools Integration Module")
    print("This module provides MCP tools for IPFS operations.")
    print("It should be imported and used with an MCP server, not run directly.")
