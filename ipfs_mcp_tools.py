#!/usr/bin/env python3
"""
IPFS MCP Tools

This module provides MCP tools for interacting with the InterPlanetary File System (IPFS)
network. It includes functionality for adding, retrieving, and managing content on IPFS,
as well as advanced features like pinning, IPNS, and MFS (Mutable File System) operations.
"""

import os
import sys
import json
import time
import base64
import logging
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple, Set, BinaryIO

# Import filesystem journal and multi-backend tools if available
try:
    import fs_journal_tools
    import multi_backend_fs_integration
    HAS_EXTENSIONS = True
except ImportError:
    HAS_EXTENSIONS = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# IPFS API configuration
DEFAULT_API_URL = "/ip4/127.0.0.1/tcp/5001"

def _get_ipfs_client():
    """Get an IPFS client instance"""
    try:
        import ipfshttpclient
        return ipfshttpclient.connect()
    except ImportError:
        logger.error("ipfshttpclient not installed. Install with: pip install ipfshttpclient")
        raise
    except Exception as e:
        logger.error(f"Error connecting to IPFS daemon: {e}")
        raise

def _run_ipfs_command(command: List[str]) -> Tuple[bool, str, str]:
    """Run an IPFS command via subprocess and return result"""
    try:
        cmd = ["ipfs"] + command
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True, result.stdout.strip(), ""
        else:
            return False, "", result.stderr.strip()
    except Exception as e:
        logger.error(f"Error executing IPFS command: {e}")
        return False, "", str(e)

def register_tools(server) -> bool:
    """Register IPFS MCP tools with the MCP server"""
    logger.info("Registering IPFS MCP tools...")
    
    # Tool: Add content to IPFS
    async def ipfs_add(content: Union[str, bytes], filename: Optional[str] = None, 
                     wrap_with_directory: bool = False, pin: bool = True,
                     only_hash: bool = False):
        """Add content to IPFS and return its content identifier (CID)"""
        try:
            # Handle string or bytes input
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
            else:
                content_bytes = content
            
            # Determine a filename if not provided
            if not filename:
                filename = f"file-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(prefix="ipfs-", suffix=f"-{filename}", delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(content_bytes)
            
            try:
                # Build ipfs add command
                cmd = ["add", "--progress=false", "--quieter"]
                if wrap_with_directory:
                    cmd.append("--wrap-with-directory")
                if not pin:
                    cmd.append("--pin=false")
                if only_hash:
                    cmd.append("--only-hash")
                
                cmd.append(temp_path)
                
                # Run ipfs add command
                success, stdout, stderr = _run_ipfs_command(cmd)
                
                if not success:
                    return {"success": False, "error": stderr}
                
                # Extract CID
                cid = stdout.strip()
                
                # If wrapped in directory, the output has multiple lines
                if wrap_with_directory:
                    lines = cid.split("\n")
                    if len(lines) > 1:
                        # Last line should be the directory CID
                        dir_cid = lines[-1]
                        file_cid = lines[0]
                        return {
                            "success": True, 
                            "cid": dir_cid,
                            "file_cid": file_cid,
                            "size": len(content_bytes),
                            "wrapped": True
                        }
                
                return {
                    "success": True,
                    "cid": cid,
                    "size": len(content_bytes),
                    "wrapped": wrap_with_directory
                }
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Error adding content to IPFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: Cat (retrieve) content from IPFS by CID
    async def ipfs_cat(cid: str, offset: Optional[int] = None, length: Optional[int] = None):
        """Retrieve content from IPFS by its content identifier (CID)"""
        try:
            # Build ipfs cat command
            cmd = ["cat"]
            
            # Add offset and length parameters if specified
            if offset is not None:
                cmd.extend([f"--offset={offset}"])
            if length is not None:
                cmd.extend([f"--length={length}"])
            
            cmd.append(cid)
            
            # Run ipfs cat command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            # Encode content as base64 to handle binary data
            content_bytes = stdout.encode('utf-8') if isinstance(stdout, str) else stdout
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')
            
            return {
                "success": True,
                "cid": cid,
                "content_base64": content_base64,
                "size": len(content_bytes)
            }
            
        except Exception as e:
            logger.error(f"Error retrieving content from IPFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: Pin content to local IPFS node
    async def ipfs_pin_add(cid: str, recursive: bool = True):
        """Pin content to the local IPFS node to prevent garbage collection"""
        try:
            # Build ipfs pin add command
            cmd = ["pin", "add"]
            if recursive:
                cmd.append("--recursive")
            cmd.append(cid)
            
            # Run ipfs pin add command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            return {
                "success": True,
                "cid": cid,
                "pinned": True,
                "recursive": recursive
            }
            
        except Exception as e:
            logger.error(f"Error pinning content to IPFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: Unpin content from local IPFS node
    async def ipfs_pin_rm(cid: str, recursive: bool = True):
        """Unpin content from the local IPFS node to allow garbage collection"""
        try:
            # Build ipfs pin rm command
            cmd = ["pin", "rm"]
            if recursive:
                cmd.append("--recursive")
            cmd.append(cid)
            
            # Run ipfs pin rm command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            return {
                "success": True,
                "cid": cid,
                "unpinned": True,
                "recursive": recursive
            }
            
        except Exception as e:
            logger.error(f"Error unpinning content from IPFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: List pinned content
    async def ipfs_pin_ls(cid: Optional[str] = None, pin_type: Optional[str] = None):
        """List content pinned to the local IPFS node"""
        try:
            # Build ipfs pin ls command
            cmd = ["pin", "ls"]
            
            if pin_type:
                valid_types = ["direct", "recursive", "indirect", "all"]
                if pin_type not in valid_types:
                    return {"success": False, "error": f"Invalid pin type. Must be one of: {', '.join(valid_types)}"}
                cmd.extend([f"--type={pin_type}"])
            
            if cid:
                cmd.append(cid)
            
            # Add --quiet to get only the CIDs
            cmd.append("--quiet")
            
            # Run ipfs pin ls command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            # Parse the output to get list of CIDs
            pins = [pin.strip() for pin in stdout.strip().split("\n") if pin.strip()]
            
            return {
                "success": True,
                "pins": pins,
                "count": len(pins),
                "filter": {
                    "cid": cid,
                    "type": pin_type
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing IPFS pins: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: Get information about an IPFS object
    async def ipfs_object_stat(cid: str):
        """Get statistics about an IPFS object"""
        try:
            # Run ipfs object stat command
            success, stdout, stderr = _run_ipfs_command(["object", "stat", cid])
            
            if not success:
                return {"success": False, "error": stderr}
            
            # Parse the output to extract statistics
            lines = stdout.strip().split("\n")
            stats = {}
            
            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    stats[key.strip()] = value.strip()
            
            return {
                "success": True,
                "cid": cid,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Error getting IPFS object stats: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: Get information about a file or directory (ls)
    async def ipfs_ls(cid: str, resolve_type: bool = True):
        """List directory contents or file information from IPFS"""
        try:
            # Run ipfs ls command
            success, stdout, stderr = _run_ipfs_command(["ls", cid])
            
            if not success:
                # If the CID is a file, ls will fail, so try file stat instead
                if resolve_type:
                    stat_success, stat_stdout, stat_stderr = _run_ipfs_command(["object", "stat", cid])
                    if stat_success:
                        return {
                            "success": True,
                            "cid": cid,
                            "type": "file",
                            "entries": []
                        }
                
                return {"success": False, "error": stderr}
            
            # Parse the output to extract entries
            lines = stdout.strip().split("\n")
            entries = []
            
            for line in lines:
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) >= 3:
                    entry = {
                        "cid": parts[0],
                        "size": parts[1],
                        "name": " ".join(parts[2:])
                    }
                    entries.append(entry)
            
            return {
                "success": True,
                "cid": cid,
                "type": "directory",
                "entries": entries,
                "count": len(entries)
            }
            
        except Exception as e:
            logger.error(f"Error listing IPFS content: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS Name Publish (IPNS)
    async def ipfs_name_publish(cid: str, key: Optional[str] = None, 
                               lifetime: str = "24h", ttl: Optional[str] = None):
        """Publish an IPFS content identifier to IPNS"""
        try:
            # Build ipfs name publish command
            cmd = ["name", "publish", f"--lifetime={lifetime}"]
            
            if key:
                cmd.append(f"--key={key}")
            
            if ttl:
                cmd.append(f"--ttl={ttl}")
            
            cmd.append(f"/ipfs/{cid}")
            
            # Run ipfs name publish command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            # Parse the output to extract the IPNS name
            # Output format: Published to <name>: <path>
            if "Published to " in stdout:
                published_to = stdout.split("Published to ")[1].split(":")[0].strip()
                return {
                    "success": True,
                    "cid": cid,
                    "name": published_to,
                    "lifetime": lifetime,
                    "ttl": ttl,
                    "key": key or "self"
                }
            else:
                return {"success": False, "error": "Failed to parse name publish output"}
            
        except Exception as e:
            logger.error(f"Error publishing to IPNS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS Name Resolve (IPNS)
    async def ipfs_name_resolve(name: str, recursive: bool = True, nocache: bool = False):
        """Resolve an IPNS name to an IPFS content identifier"""
        try:
            # Build ipfs name resolve command
            cmd = ["name", "resolve"]
            
            if recursive:
                cmd.append("--recursive")
            
            if nocache:
                cmd.append("--nocache")
            
            cmd.append(name)
            
            # Run ipfs name resolve command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            # Extract the resolved path
            path = stdout.strip()
            
            # Extract CID from path
            cid = path.replace("/ipfs/", "")
            
            return {
                "success": True,
                "name": name,
                "path": path,
                "cid": cid
            }
            
        except Exception as e:
            logger.error(f"Error resolving IPNS name: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS MFS (Mutable File System) operations - mkdir
    async def ipfs_files_mkdir(path: str, parents: bool = True):
        """Create a directory in the IPFS Mutable File System (MFS)"""
        try:
            # Build ipfs files mkdir command
            cmd = ["files", "mkdir"]
            
            if parents:
                cmd.append("--parents")
            
            cmd.append(path)
            
            # Run ipfs files mkdir command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            return {
                "success": True,
                "path": path,
                "parents": parents
            }
            
        except Exception as e:
            logger.error(f"Error creating directory in MFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS MFS (Mutable File System) operations - write
    async def ipfs_files_write(path: str, content: Union[str, bytes], 
                              create: bool = True, truncate: bool = True,
                              offset: Optional[int] = None):
        """Write content to a file in the IPFS Mutable File System (MFS)"""
        try:
            # Handle string or bytes input
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
            else:
                content_bytes = content
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(prefix="ipfs-mfs-", delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(content_bytes)
            
            try:
                # Build ipfs files write command
                cmd = ["files", "write"]
                
                if create:
                    cmd.append("--create")
                
                if truncate:
                    cmd.append("--truncate")
                
                if offset is not None:
                    cmd.append(f"--offset={offset}")
                
                cmd.extend([path, temp_path])
                
                # Run ipfs files write command
                success, stdout, stderr = _run_ipfs_command(cmd)
                
                if not success:
                    return {"success": False, "error": stderr}
                
                return {
                    "success": True,
                    "path": path,
                    "size": len(content_bytes),
                    "create": create,
                    "truncate": truncate,
                    "offset": offset
                }
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Error writing to MFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS MFS (Mutable File System) operations - read
    async def ipfs_files_read(path: str, offset: Optional[int] = None, count: Optional[int] = None):
        """Read content from a file in the IPFS Mutable File System (MFS)"""
        try:
            # Build ipfs files read command
            cmd = ["files", "read"]
            
            if offset is not None:
                cmd.append(f"--offset={offset}")
            
            if count is not None:
                cmd.append(f"--count={count}")
            
            cmd.append(path)
            
            # Run ipfs files read command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            # Encode content as base64 to handle binary data
            content_bytes = stdout.encode('utf-8') if isinstance(stdout, str) else stdout
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')
            
            return {
                "success": True,
                "path": path,
                "content_base64": content_base64,
                "size": len(content_bytes)
            }
            
        except Exception as e:
            logger.error(f"Error reading from MFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS MFS (Mutable File System) operations - ls
    async def ipfs_files_ls(path: str = "/", long: bool = False):
        """List directory contents in the IPFS Mutable File System (MFS)"""
        try:
            # Build ipfs files ls command
            cmd = ["files", "ls"]
            
            if long:
                cmd.append("--long")
            
            cmd.append(path)
            
            # Run ipfs files ls command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            # Parse the output to extract entries
            lines = stdout.strip().split("\n")
            entries = []
            
            for line in lines:
                if not line.strip():
                    continue
                
                if long:
                    # Format with --long: <mode> <size> <cid> <name>
                    parts = line.split()
                    if len(parts) >= 4:
                        mode, size, cid = parts[0:3]
                        name = " ".join(parts[3:])
                        
                        entry = {
                            "name": name,
                            "type": "directory" if mode.startswith("d") else "file",
                            "size": size,
                            "cid": cid,
                            "mode": mode
                        }
                        entries.append(entry)
                else:
                    # Format without --long: just the name
                    entries.append({"name": line.strip()})
            
            return {
                "success": True,
                "path": path,
                "entries": entries,
                "count": len(entries)
            }
            
        except Exception as e:
            logger.error(f"Error listing MFS directory: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS MFS (Mutable File System) operations - rm
    async def ipfs_files_rm(path: str, recursive: bool = False):
        """Remove a file or directory from the IPFS Mutable File System (MFS)"""
        try:
            # Build ipfs files rm command
            cmd = ["files", "rm"]
            
            if recursive:
                cmd.append("--recursive")
            
            cmd.append(path)
            
            # Run ipfs files rm command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            return {
                "success": True,
                "path": path,
                "recursive": recursive
            }
            
        except Exception as e:
            logger.error(f"Error removing from MFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS MFS (Mutable File System) operations - stat
    async def ipfs_files_stat(path: str):
        """Get file or directory status in the IPFS Mutable File System (MFS)"""
        try:
            # Run ipfs files stat command
            success, stdout, stderr = _run_ipfs_command(["files", "stat", path])
            
            if not success:
                return {"success": False, "error": stderr}
            
            # Parse the output to extract statistics
            lines = stdout.strip().split("\n")
            stats = {}
            
            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    stats[key.strip()] = value.strip()
            
            # Extract some common fields for easier access
            cid = stats.get("CumulativeSize", "")
            size = stats.get("Size", "0")
            blocks = stats.get("Blocks", "0")
            
            return {
                "success": True,
                "path": path,
                "cid": cid,
                "size": size,
                "blocks": blocks,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Error getting MFS stats: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS MFS (Mutable File System) operations - cp
    async def ipfs_files_cp(source: str, dest: str):
        """Copy files in the IPFS Mutable File System (MFS)"""
        try:
            # Run ipfs files cp command
            success, stdout, stderr = _run_ipfs_command(["files", "cp", source, dest])
            
            if not success:
                return {"success": False, "error": stderr}
            
            return {
                "success": True,
                "source": source,
                "destination": dest
            }
            
        except Exception as e:
            logger.error(f"Error copying in MFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS MFS (Mutable File System) operations - mv
    async def ipfs_files_mv(source: str, dest: str):
        """Move files in the IPFS Mutable File System (MFS)"""
        try:
            # Run ipfs files mv command
            success, stdout, stderr = _run_ipfs_command(["files", "mv", source, dest])
            
            if not success:
                return {"success": False, "error": stderr}
            
            return {
                "success": True,
                "source": source,
                "destination": dest
            }
            
        except Exception as e:
            logger.error(f"Error moving in MFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: IPFS Daemon Status
    async def ipfs_status():
        """Get the status of the IPFS daemon"""
        try:
            # Run ipfs id command
            success, stdout, stderr = _run_ipfs_command(["id"])
            
            if not success:
                return {"success": False, "error": stderr, "daemon_running": False}
            
            # Parse the output to extract identity information
            try:
                id_info = json.loads(stdout)
            except:
                id_info = {"ID": "unknown", "Error": "Failed to parse JSON output"}
            
            # Get bandwidth stats
            bw_success, bw_stdout, bw_stderr = _run_ipfs_command(["stats", "bw"])
            
            if bw_success:
                try:
                    bw_info = json.loads(bw_stdout)
                except:
                    bw_info = {"Error": "Failed to parse JSON output"}
            else:
                bw_info = {"Error": bw_stderr}
            
            # Get repo stats
            repo_success, repo_stdout, repo_stderr = _run_ipfs_command(["repo", "stat"])
            
            if repo_success:
                try:
                    repo_info = json.loads(repo_stdout)
                except:
                    repo_info = {"Error": "Failed to parse JSON output"}
            else:
                repo_info = {"Error": repo_stderr}
            
            return {
                "success": True,
                "daemon_running": True,
                "id": id_info,
                "bandwidth": bw_info,
                "repo": repo_info
            }
            
        except Exception as e:
            logger.error(f"Error getting IPFS status: {e}")
            return {"success": False, "error": str(e), "daemon_running": False}
    
    # Tool: Add local file to IPFS
    async def ipfs_add_file(file_path: str, wrap_with_directory: bool = False, 
                           pin: bool = True, only_hash: bool = False):
        """Add a local file to IPFS and return its content identifier (CID)"""
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return {"success": False, "error": f"File not found: {file_path}"}
            
            # Build ipfs add command
            cmd = ["add", "--progress=false", "--quieter"]
            if wrap_with_directory:
                cmd.append("--wrap-with-directory")
            if not pin:
                cmd.append("--pin=false")
            if only_hash:
                cmd.append("--only-hash")
            
            cmd.append(file_path)
            
            # Run ipfs add command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            # Extract CID
            cid = stdout.strip()
            
            # If wrapped in directory, the output has multiple lines
            if wrap_with_directory:
                lines = cid.split("\n")
                if len(lines) > 1:
                    # Last line should be the directory CID
                    dir_cid = lines[-1]
                    file_cid = lines[0]
                    return {
                        "success": True, 
                        "cid": dir_cid,
                        "file_cid": file_cid,
                        "file_path": file_path,
                        "wrapped": True
                    }
            
            return {
                "success": True,
                "cid": cid,
                "file_path": file_path,
                "wrapped": wrap_with_directory
            }
            
        except Exception as e:
            logger.error(f"Error adding file to IPFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Tool: Get content from IPFS and save to local file
    async def ipfs_get(cid: str, output_dir: Optional[str] = None, 
                     archive: bool = False, compression_level: int = 6):
        """Get content from IPFS and save to a local file"""
        try:
            # Determine output directory
            if not output_dir:
                output_dir = os.getcwd()
            
            # Ensure the output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Build ipfs get command
            cmd = ["get"]
            
            if archive:
                cmd.append("--archive")
                cmd.append(f"--compression-level={compression_level}")
            
            cmd.extend([cid, "--output", output_dir])
            
            # Run ipfs get command
            success, stdout, stderr = _run_ipfs_command(cmd)
            
            if not success:
                return {"success": False, "error": stderr}
            
            # Determine the path of the output file/directory
            output_path = os.path.join(output_dir, cid)
            
            # If the CID is a directory, get will create a directory with that name
            # If the CID is a file, get will create a file with that name
            file_type = "unknown"
            if os.path.exists(output_path):
                file_type = "directory" if os.path.isdir(output_path) else "file"
                
                # Get file size
                size = 0
                if file_type == "file":
                    size = os.path.getsize(output_path)
                elif file_type == "directory":
                    size = sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, dirnames, filenames in os.walk(output_path)
                        for filename in filenames
                    )
                
                return {
                    "success": True,
                    "cid": cid,
                    "output_path": output_path,
                    "type": file_type,
                    "size": size,
                    "archive": archive
                }
            else:
                return {"success": False, "error": f"Output path not found: {output_path}"}
                
        except Exception as e:
            logger.error(f"Error getting content from IPFS: {e}")
            return {"success": False, "error": str(e)}
    
    # Register all tools with the MCP server
    try:
        # Core IPFS tools
        server.register_tool("ipfs_add", ipfs_add)
        server.register_tool("ipfs_cat", ipfs_cat)
        server.register_tool("ipfs_pin_add", ipfs_pin_add)
        server.register_tool("ipfs_pin_rm", ipfs_pin_rm)
        server.register_tool("ipfs_pin_ls", ipfs_pin_ls)
        server.register_tool("ipfs_object_stat", ipfs_object_stat)
        server.register_tool("ipfs_ls", ipfs_ls)
        server.register_tool("ipfs_status", ipfs_status)
        
        # IPNS tools
        server.register_tool("ipfs_name_publish", ipfs_name_publish)
        server.register_tool("ipfs_name_resolve", ipfs_name_resolve)
        
        # MFS tools
        server.register_tool("ipfs_files_mkdir", ipfs_files_mkdir)
        server.register_tool("ipfs_files_write", ipfs_files_write)
        server.register_tool("ipfs_files_read", ipfs_files_read)
        server.register_tool("ipfs_files_ls", ipfs_files_ls)
        server.register_tool("ipfs_files_rm", ipfs_files_rm)
        server.register_tool("ipfs_files_stat", ipfs_files_stat)
        server.register_tool("ipfs_files_cp", ipfs_files_cp)
        server.register_tool("ipfs_files_mv", ipfs_files_mv)
        
        # File management tools
        server.register_tool("ipfs_add_file", ipfs_add_file)
        server.register_tool("ipfs_get", ipfs_get)
        
        # Register filesystem journal tools if available
        if HAS_EXTENSIONS:
            logger.info("Registering filesystem extensions...")
            fs_journal_tools.register_tools(server)
            multi_backend_fs_integration.register_tools(server)
            logger.info("✅ Filesystem extensions registered")
        
        logger.info("✅ IPFS MCP tools registered successfully")
        return True
    except Exception as e:
        logger.error(f"Error registering IPFS MCP tools: {e}")
        return False

if __name__ == "__main__":
    logger.info("This module should be imported, not run directly.")
    logger.info("To use these tools, import and register them with an MCP server.")
