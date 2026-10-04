#!/usr/bin/env python3
"""
FastMCP-compatible IPFS tools registration.
This version uses the @app.tool decorator pattern instead of the register_tool method.
"""

import os
import sys
import logging
import json
import base64
import tempfile
from typing import Optional, Dict, Any, List

# Configure logging
logger = logging.getLogger("ipfs-fastmcp-tools")

# Try to import ipfshttpclient
try:
    import ipfshttpclient
    IPFS_CLIENT_AVAILABLE = True
    logger.info("ipfshttpclient is available")
except ImportError:
    logger.warning("ipfshttpclient not available, falling back to subprocess")
    IPFS_CLIENT_AVAILABLE = False
    import subprocess

def register_ipfs_tools_fastmcp(app):
    """
    Register IPFS tools with a FastMCP server using decorators.
    
    Args:
        app: The FastMCP application instance
        
    Returns:
        bool: True if registration was successful, False otherwise
    """
    logger.info("Registering IPFS tools with FastMCP using decorators...")
    
    try:
        tools_registered = 0
        
        # Add content to IPFS
        @app.tool(description="Add content to IPFS and get its CID")
        async def ipfs_add(
            content: Optional[str] = None,
            file_path: Optional[str] = None,
            file_name: Optional[str] = None,
            pin: bool = True
        ) -> Dict[str, Any]:
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
                    try:
                        if content is not None:
                            # Create a temporary file
                            with tempfile.NamedTemporaryFile(delete=False) as temp:
                                # Write content to the file
                                if isinstance(content, str):
                                    temp.write(content.encode('utf-8'))
                                elif isinstance(content, bytes):
                                    temp.write(content)
                                else:
                                    temp.write(str(content).encode('utf-8'))
                                
                                temp_path = temp.name
                            
                            try:
                                # Build the command
                                cmd = ["ipfs", "add"]
                                if pin:
                                    cmd.append("--pin")
                                cmd.append(temp_path)
                                
                                # Run the command
                                process = subprocess.run(cmd, capture_output=True, text=True, check=True)
                                
                                # Parse output (format: "added <cid> <filename>")
                                output_lines = process.stdout.strip().split("\n")
                                last_line = output_lines[-1]  # Get the last line which contains the root hash
                                parts = last_line.split()
                                
                                if len(parts) >= 2 and parts[0] == "added":
                                    cid = parts[1]
                                    
                                    # Get file size
                                    file_size = os.path.getsize(temp_path)
                                    
                                    # Cleanup the temporary file
                                    os.unlink(temp_path)
                                    
                                    return {
                                        "success": True,
                                        "cid": cid,
                                        "size": file_size,
                                        "name": file_name
                                    }
                                else:
                                    # Cleanup the temporary file
                                    os.unlink(temp_path)
                                    return {"success": False, "error": "Unexpected output format from IPFS add"}
                            
                            except Exception as e:
                                # Cleanup the temporary file in case of error
                                if os.path.exists(temp_path):
                                    os.unlink(temp_path)
                                raise e
                        
                        else:  # Use file_path
                            if not os.path.exists(file_path):
                                return {"success": False, "error": f"File does not exist: {file_path}"}
                            
                            # Build the command
                            cmd = ["ipfs", "add"]
                            if pin:
                                cmd.append("--pin")
                            cmd.append(file_path)
                            
                            # Run the command
                            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
                            
                            # Parse output
                            output_lines = process.stdout.strip().split("\n")
                            last_line = output_lines[-1]
                            parts = last_line.split()
                            
                            if len(parts) >= 2 and parts[0] == "added":
                                cid = parts[1]
                                file_size = os.path.getsize(file_path)
                                
                                return {
                                    "success": True,
                                    "cid": cid,
                                    "size": file_size,
                                    "name": file_name
                                }
                            else:
                                return {"success": False, "error": "Unexpected output format from IPFS add"}
                    
                    except subprocess.CalledProcessError as e:
                        return {
                            "success": False,
                            "error": f"IPFS add failed: {e.stderr}"
                        }
                    
                    except Exception as e:
                        return {
                            "success": False,
                            "error": f"IPFS add failed: {str(e)}"
                        }
            
            except Exception as e:
                logger.error(f"Error in ipfs_add: {e}")
                return {"success": False, "error": str(e)}
        
        tools_registered += 1
        
        # Cat (retrieve) content from IPFS
        @app.tool(description="Retrieve content from IPFS by CID")
        async def ipfs_cat(
            cid: str,
            offset: int = 0,
            length: Optional[int] = None,
            timeout: int = 30
        ) -> Dict[str, Any]:
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
                        
                        # Convert binary data to base64
                        content_base64 = base64.b64encode(content).decode('utf-8')
                        
                        return {
                            "success": True,
                            "content_base64": content_base64,
                            "size": len(content)
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
        
        tools_registered += 1
        
        # List directory contents in IPFS
        @app.tool(description="List directory contents in IPFS by CID")
        async def ipfs_ls(
            cid: str,
            recursive: bool = False,
            timeout: int = 30
        ) -> Dict[str, Any]:
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
        
        tools_registered += 1
        
        # Get IPFS node info
        @app.tool(description="Get IPFS node information and status")
        async def ipfs_id(timeout: int = 30) -> Dict[str, Any]:
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
        
        tools_registered += 1
        
        # List pinned items
        @app.tool(description="List pinned items in IPFS")
        async def ipfs_pin_ls(
            pin_type: str = "all",
            timeout: int = 30
        ) -> Dict[str, Any]:
            """List pinned items"""
            try:
                # Validate type
                valid_types = ["all", "direct", "indirect", "recursive"]
                if pin_type not in valid_types:
                    return {"success": False, "error": f"Invalid pin type. Must be one of: {', '.join(valid_types)}"}
                
                # Use ipfshttpclient if available
                if IPFS_CLIENT_AVAILABLE:
                    with ipfshttpclient.connect() as client:
                        try:
                            # List the pinned items
                            result = client.pin.ls(type=pin_type)
                            
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
                        if pin_type != "all":
                            cmd.extend(["--type", pin_type])
                        
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
                                pin_type_found = parts[1].strip()
                                
                                # Remove the trailing colon
                                if pin_type_found.endswith(":"):
                                    pin_type_found = pin_type_found[:-1]
                                
                                pins[cid] = {"type": pin_type_found}
                        
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
        
        tools_registered += 1
        
        logger.info(f"Successfully registered {tools_registered} IPFS tools with FastMCP")
        return True
        
    except Exception as e:
        logger.error(f"Error registering IPFS tools with FastMCP: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("FastMCP-compatible IPFS Tools Registration Module")
    print("This module provides IPFS tools for FastMCP servers using the @app.tool decorator pattern.")
    print("It should be imported and used with a FastMCP server, not run directly.")
