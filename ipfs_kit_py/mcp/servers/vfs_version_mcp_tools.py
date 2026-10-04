"""
MCP tools for VFS version tracking system.

Provides Model Context Protocol (MCP) tools for managing filesystem versions
through the MCP server interface. These tools offer Git-like version control
for virtual filesystems using IPFS content addressing.
"""

import json
import logging
import threading
import tempfile
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Integration with ipfs_datasets_py for distributed storage
HAS_DATASETS = False
try:
    from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager
    HAS_DATASETS = True
    logger.info("ipfs_datasets_py integration available")
except ImportError:
    logger.info("ipfs_datasets_py not available - using local storage only")

# Integration with ipfs_accelerate_py for compute acceleration
HAS_ACCELERATE = False
try:
    import sys
    from pathlib import Path as PathLib
    accelerate_path = PathLib(__file__).parent.parent.parent / "external" / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))
    from ipfs_accelerate_py import AccelerateCompute
    HAS_ACCELERATE = True
    logger.info("ipfs_accelerate_py compute acceleration available")
except ImportError:
    logger.info("ipfs_accelerate_py not available - using standard compute")

# VFS version tracker imports
try:
    from ipfs_kit_py.vfs_version_tracker import (
        get_global_vfs_tracker,
        auto_version_filesystem,
        get_vfs_status,
        get_vfs_history
    )
    VFS_TRACKER_AVAILABLE = True
except ImportError:
    VFS_TRACKER_AVAILABLE = False
    logger.warning("VFS version tracker not available")

# MCP imports
try:
    from mcp.server.models import Tool, TextContent
    from mcp.types import INVALID_PARAMS, INTERNAL_ERROR
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP not available")
    
    # Fallback classes for when MCP is not available
    class Tool:
        def __init__(self, name, description, inputSchema):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema
    
    class TextContent:
        def __init__(self, type, text):
            self.type = type
            self.text = text

# IPFS Kit imports
try:
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    IPFS_API_AVAILABLE = True
except ImportError:
    IPFS_API_AVAILABLE = False
    IPFSSimpleAPI = None

# Global dataset storage tracking
_dataset_manager = None
_compute_layer = None
_operation_buffer = []
_buffer_lock = threading.Lock()
_dataset_batch_size = 100
_enable_dataset_storage = False
_enable_compute_layer = False

def init_dataset_storage(enable_dataset_storage: bool = False,
                        enable_compute_layer: bool = False,
                        ipfs_client = None,
                        dataset_batch_size: int = 100):
    """Initialize dataset storage and compute layer."""
    global _dataset_manager, _compute_layer, _dataset_batch_size
    global _enable_dataset_storage, _enable_compute_layer
    
    _enable_dataset_storage = enable_dataset_storage
    _enable_compute_layer = enable_compute_layer
    _dataset_batch_size = dataset_batch_size
    
    if HAS_DATASETS and enable_dataset_storage:
        try:
            _dataset_manager = get_ipfs_datasets_manager(
                enable=True,
                ipfs_client=ipfs_client
            )
            logger.info("Dataset storage enabled for VFS version operations")
        except Exception as e:
            logger.warning(f"Failed to initialize dataset storage: {e}")
    
    if HAS_ACCELERATE and enable_compute_layer:
        try:
            _compute_layer = AccelerateCompute()
            logger.info("Compute acceleration enabled for VFS version operations")
        except Exception as e:
            logger.warning(f"Failed to initialize compute layer: {e}")

def _store_operation_to_dataset(tool_name: str, parameters: dict, result: dict):
    """Store tool invocation to dataset if enabled."""
    global _dataset_manager, _operation_buffer, _buffer_lock, _dataset_batch_size
    
    if not HAS_DATASETS or not _enable_dataset_storage or not _dataset_manager:
        return
    
    operation_data = {
        "tool_name": tool_name,
        "timestamp": datetime.now().isoformat(),
        "parameters": parameters,
        "result": result
    }
    
    with _buffer_lock:
        _operation_buffer.append(operation_data)
        
        if len(_operation_buffer) >= _dataset_batch_size:
            _flush_operations_to_dataset()

def _flush_operations_to_dataset():
    """Flush buffered operations to dataset storage."""
    global _dataset_manager, _operation_buffer
    
    if not _operation_buffer or not _dataset_manager:
        return
    
    try:
        # Write operations to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for op in _operation_buffer:
                f.write(json.dumps(op) + '\n')
            temp_path = f.name
        
        try:
            # Store via dataset manager
            result = _dataset_manager.store(
                temp_path,
                metadata={
                    "type": "vfs_version_tool_invocations",
                    "operation_count": len(_operation_buffer),
                    "timestamp": datetime.now().isoformat(),
                    "component": "vfs_version_mcp_tools"
                }
            )
            
            if result.get("success"):
                logger.info(f"Stored {len(_operation_buffer)} VFS version operations to dataset: {result.get('cid', 'N/A')}")
            
            _operation_buffer.clear()
            
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Failed to flush operations to dataset: {e}")

def flush_to_dataset():
    """Manually flush pending operations to dataset storage."""
    global _buffer_lock
    
    if HAS_DATASETS and _enable_dataset_storage:
        with _buffer_lock:
            _flush_operations_to_dataset()


def create_result_dict(success: bool, **kwargs):
    """Create standardized result dictionary."""
    return {"success": success, **kwargs}


# MCP Tools for VFS Version Tracking

VFS_INIT_TOOL = Tool(
    name="vfs_init",
    description="Initialize VFS version tracking in specified directory (defaults to ~/.ipfs_kit)",
    inputSchema={
        "type": "object",
        "properties": {
            "directory": {
                "type": "string", 
                "description": "VFS root directory path (optional, defaults to ~/.ipfs_kit)"
            },
            "enable_auto_versioning": {
                "type": "boolean",
                "description": "Enable automatic versioning on changes (default: true)"
            }
        }
    }
)

VFS_STATUS_TOOL = Tool(
    name="vfs_status",
    description="Get current VFS status, including HEAD commit, changes, and recent version history",
    inputSchema={
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "VFS root directory path (optional)"
            }
        }
    }
)

VFS_COMMIT_TOOL = Tool(
    name="vfs_commit",
    description="Create a new version snapshot (commit) of the current filesystem state",
    inputSchema={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Commit message describing the changes"
            },
            "author": {
                "type": "string", 
                "description": "Author of the commit (default: MCP-Server)"
            },
            "force": {
                "type": "boolean",
                "description": "Force commit even if no changes detected (default: false)"
            },
            "directory": {
                "type": "string",
                "description": "VFS root directory path (optional)"
            }
        },
        "required": ["message"]
    }
)

VFS_LOG_TOOL = Tool(
    name="vfs_log", 
    description="Show VFS version history with commit details and CID chain",
    inputSchema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of versions to return (default: 10)",
                "minimum": 1,
                "maximum": 100
            },
            "directory": {
                "type": "string",
                "description": "VFS root directory path (optional)"
            }
        }
    }
)

VFS_CHECKOUT_TOOL = Tool(
    name="vfs_checkout",
    description="Checkout (switch to) a specific version by CID",
    inputSchema={
        "type": "object", 
        "properties": {
            "version_cid": {
                "type": "string",
                "description": "The CID of the version to checkout"
            },
            "directory": {
                "type": "string",
                "description": "VFS root directory path (optional)"
            }
        },
        "required": ["version_cid"]
    }
)

VFS_SCAN_TOOL = Tool(
    name="vfs_scan",
    description="Scan the filesystem and show what files would be included in next commit",
    inputSchema={
        "type": "object",
        "properties": {
            "include_buckets": {
                "type": "boolean",
                "description": "Include bucket VFS in scan (default: true)"
            },
            "include_metadata": {
                "type": "boolean", 
                "description": "Include detailed file metadata (default: true)"
            },
            "directory": {
                "type": "string",
                "description": "VFS root directory path (optional)"
            }
        }
    }
)

VFS_AUTO_COMMIT_TOOL = Tool(
    name="vfs_auto_commit",
    description="Automatically create commit if filesystem changes are detected",
    inputSchema={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Custom commit message (default: auto-generated)"
            },
            "force": {
                "type": "boolean",
                "description": "Force commit even if no changes detected (default: false)"
            }
        }
    }
)

VFS_DIFF_TOOL = Tool(
    name="vfs_diff",
    description="Show differences between two versions or between current state and a version",
    inputSchema={
        "type": "object",
        "properties": {
            "version_a": {
                "type": "string",
                "description": "First version CID (defaults to current HEAD)"
            },
            "version_b": {
                "type": "string", 
                "description": "Second version CID (defaults to current filesystem state)"
            },
            "directory": {
                "type": "string",
                "description": "VFS root directory path (optional)"
            }
        }
    }
)


# MCP Tool Handler Functions

async def handle_vfs_init(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle VFS initialization."""
    if not VFS_TRACKER_AVAILABLE:
        return [TextContent(
            type="text",
            text="ERROR: VFS version tracker not available. Please install required dependencies."
        )]
    
    try:
        directory = arguments.get("directory")
        enable_auto_versioning = arguments.get("enable_auto_versioning", True)
        
        # Initialize IPFS client
        ipfs_client = None
        if IPFS_API_AVAILABLE and IPFSSimpleAPI:
            try:
                ipfs_client = IPFSSimpleAPI()
            except Exception as e:
                logger.warning(f"Could not initialize IPFS client: {e}")
        
        # Initialize VFS tracker
        vfs_tracker = get_global_vfs_tracker(
            vfs_root=directory,
            ipfs_client=ipfs_client,
            enable_auto_versioning=enable_auto_versioning
        )
        
        # Get initial status
        status_result = await vfs_tracker.get_filesystem_status()
        
        if status_result["success"]:
            result_text = f"✓ VFS version tracking initialized\n"
            result_text += f"VFS Root: {status_result['vfs_root']}\n"
            result_text += f"Current HEAD: {status_result['current_head'][:12]}...\n"
            result_text += f"Auto-versioning: {'enabled' if status_result['auto_versioning'] else 'disabled'}\n"
            
            # Create initial commit if needed
            if status_result.get("has_uncommitted_changes", False):
                commit_result = await vfs_tracker.create_version_snapshot(
                    commit_message="Initial filesystem state",
                    author="MCP-Server"
                )
                
                if commit_result["success"]:
                    result_text += f"\n✓ Initial commit created: {commit_result['version_cid'][:12]}..."
                else:
                    result_text += f"\n✗ Failed to create initial commit: {commit_result.get('error', 'Unknown error')}"
            
            # Store operation to dataset
            _store_operation_to_dataset("vfs_init", arguments, {"success": True, "text": result_text})
            
            return [TextContent(type="text", text=result_text)]
        else:
            error_text = f"✗ Failed to initialize VFS tracking: {status_result.get('error', 'Unknown error')}"
            _store_operation_to_dataset("vfs_init", arguments, {"success": False, "text": error_text})
            return [TextContent(
                type="text",
                text=error_text
            )]
            
    except Exception as e:
        logger.error(f"Error in vfs_init: {e}")
        error_text = f"✗ Error initializing VFS tracking: {e}"
        _store_operation_to_dataset("vfs_init", arguments, {"success": False, "error": str(e)})
        return [TextContent(type="text", text=error_text)]


async def handle_vfs_status(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle VFS status request."""
    if not VFS_TRACKER_AVAILABLE:
        return [TextContent(
            type="text",
            text="ERROR: VFS version tracker not available"
        )]
    
    try:
        directory = arguments.get("directory")
        vfs_tracker = get_global_vfs_tracker(vfs_root=directory)
        
        status_result = await vfs_tracker.get_filesystem_status()
        
        if status_result["success"]:
            result_text = "VFS Status:\n"
            result_text += "=" * 50 + "\n"
            result_text += f"VFS Root: {status_result['vfs_root']}\n"
            result_text += f"Current HEAD: {status_result['current_head'][:12]}...\n"
            result_text += f"Current Hash: {status_result['current_filesystem_hash'][:12]}...\n"
            
            if status_result.get("has_uncommitted_changes", False):
                result_text += "📝 Changes detected (use vfs_commit to create snapshot)\n"
            else:
                result_text += "✓ No changes detected\n"
            
            result_text += f"Auto-versioning: {'🟢 enabled' if status_result['auto_versioning'] else '🔴 disabled'}\n"
            
            # Show recent versions
            recent_versions = status_result.get("recent_versions", [])
            if recent_versions:
                result_text += f"\nRecent Versions ({len(recent_versions)}):\n"
                for i, version in enumerate(recent_versions[:5]):
                    created_at = version.get("created_at", "Unknown")
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            pass
                    
                    result_text += f"  {version.get('version_cid', 'Unknown')[:12]}... - {created_at}\n"
                    result_text += f"    {version.get('commit_message', 'No message')} ({version.get('file_count', 0)} files)\n"
                    if i == 0:
                        result_text += "    ^HEAD\n"
            
            _store_operation_to_dataset("vfs_status", arguments, {"success": True, "text": result_text})
            return [TextContent(type="text", text=result_text)]
        else:
            error_text = f"✗ Failed to get VFS status: {status_result.get('error', 'Unknown error')}"
            _store_operation_to_dataset("vfs_status", arguments, {"success": False, "text": error_text})
            return [TextContent(
                type="text",
                text=error_text
            )]
            
    except Exception as e:
        logger.error(f"Error in vfs_status: {e}")
        error_text = f"✗ Error getting VFS status: {e}"
        _store_operation_to_dataset("vfs_status", arguments, {"success": False, "error": str(e)})
        return [TextContent(type="text", text=error_text)]


async def handle_vfs_commit(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle VFS commit creation."""
    if not VFS_TRACKER_AVAILABLE:
        return [TextContent(
            type="text",
            text="ERROR: VFS version tracker not available"
        )]
    
    try:
        directory = arguments.get("directory")
        message = arguments.get("message", "MCP Server commit")
        author = arguments.get("author", "MCP-Server")
        force = arguments.get("force", False)
        
        vfs_tracker = get_global_vfs_tracker(vfs_root=directory)
        
        commit_result = await vfs_tracker.create_version_snapshot(
            commit_message=message,
            author=author,
            force=force
        )
        
        if commit_result["success"]:
            result_text = f"✓ Version snapshot created\n"
            result_text += f"Version CID: {commit_result['version_cid']}\n"
            result_text += f"Parent CID: {commit_result['parent_cid']}\n" 
            result_text += f"Files: {commit_result['file_count']}\n"
            result_text += f"Total Size: {commit_result['total_size']:,} bytes\n"
            result_text += f"CAR File: {commit_result['car_file_cid']}"
            
            _store_operation_to_dataset("vfs_commit", arguments, {"success": True, "text": result_text, **commit_result})
            return [TextContent(type="text", text=result_text)]
        else:
            error_msg = commit_result.get('error', commit_result.get('message', 'Unknown error'))
            result_text = f"✗ Failed to create snapshot: {error_msg}"
            if "No changes detected" in error_msg:
                result_text += "\n(Use force=true to create snapshot anyway)"
            
            _store_operation_to_dataset("vfs_commit", arguments, {"success": False, "text": result_text})
            return [TextContent(type="text", text=result_text)]
            
    except Exception as e:
        logger.error(f"Error in vfs_commit: {e}")
        error_text = f"✗ Error creating version snapshot: {e}"
        _store_operation_to_dataset("vfs_commit", arguments, {"success": False, "error": str(e)})
        return [TextContent(type="text", text=error_text)]


async def handle_vfs_log(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle VFS version history request."""
    if not VFS_TRACKER_AVAILABLE:
        return [TextContent(
            type="text",
            text="ERROR: VFS version tracker not available"
        )]
    
    try:
        directory = arguments.get("directory")
        limit = arguments.get("limit", 10)
        
        vfs_tracker = get_global_vfs_tracker(vfs_root=directory)
        
        history_result = await vfs_tracker.get_version_history(limit=limit)
        
        if history_result["success"]:
            versions = history_result.get("versions", [])
            
            if not versions:
                return [TextContent(type="text", text="No versions found")]
            
            result_text = f"VFS Version History (showing {len(versions)} entries):\n"
            result_text += "=" * 60 + "\n"
            
            for i, version in enumerate(versions):
                # Format timestamp
                created_at = version.get("created_at", "Unknown")
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                    except:
                        pass
                
                result_text += f"Commit: {version.get('version_cid', 'Unknown')}\n"
                result_text += f"Parent: {version.get('parent_cid', 'None')}\n"
                result_text += f"Author: {version.get('author', 'Unknown')}\n"
                result_text += f"Date:   {created_at}\n"
                result_text += f"Files:  {version.get('file_count', 0)} ({version.get('total_size', 0):,} bytes)\n"
                result_text += f"CAR:    {version.get('car_file_cid', 'None')}\n"
                result_text += f"\n    {version.get('commit_message', 'No message')}\n"
                
                if i == 0:
                    result_text += "    ^HEAD\n"
                
                result_text += "\n"
            
            return [TextContent(type="text", text=result_text)]
        else:
            return [TextContent(
                type="text",
                text=f"✗ Failed to get version history: {history_result.get('error', 'Unknown error')}"
            )]
            
    except Exception as e:
        logger.error(f"Error in vfs_log: {e}")
        return [TextContent(type="text", text=f"✗ Error getting version history: {e}")]


async def handle_vfs_checkout(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle VFS version checkout."""
    if not VFS_TRACKER_AVAILABLE:
        return [TextContent(
            type="text",
            text="ERROR: VFS version tracker not available"
        )]
    
    try:
        directory = arguments.get("directory")
        version_cid = arguments.get("version_cid")
        
        if not version_cid:
            return [TextContent(type="text", text="✗ version_cid is required")]
        
        vfs_tracker = get_global_vfs_tracker(vfs_root=directory)
        
        checkout_result = await vfs_tracker.checkout_version(version_cid)
        
        if checkout_result["success"]:
            result_text = f"✓ Checked out version {version_cid}\n"
            result_text += f"HEAD now points to: {checkout_result['version_cid']}"
            
            return [TextContent(type="text", text=result_text)]
        else:
            return [TextContent(
                type="text",
                text=f"✗ Failed to checkout version: {checkout_result.get('error', 'Unknown error')}"
            )]
            
    except Exception as e:
        logger.error(f"Error in vfs_checkout: {e}")
        return [TextContent(type="text", text=f"✗ Error checking out version: {e}")]


async def handle_vfs_scan(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle VFS filesystem scan."""
    if not VFS_TRACKER_AVAILABLE:
        return [TextContent(
            type="text",
            text="ERROR: VFS version tracker not available"
        )]
    
    try:
        directory = arguments.get("directory")
        include_buckets = arguments.get("include_buckets", True)
        include_metadata = arguments.get("include_metadata", True)
        
        vfs_tracker = get_global_vfs_tracker(vfs_root=directory)
        
        filesystem_state = await vfs_tracker.scan_filesystem(
            include_buckets=include_buckets,
            include_metadata=include_metadata
        )
        
        result_text = f"✓ Filesystem scan complete\n"
        result_text += f"Files found: {len(filesystem_state['files'])}\n"
        result_text += f"Buckets found: {len(filesystem_state['buckets'])}\n"
        result_text += f"Total size: {filesystem_state['metadata']['total_size']:,} bytes\n"
        
        # Show files by bucket
        bucket_files = {}
        for file_info in filesystem_state['files']:
            bucket = file_info.get('bucket_name', 'unknown')
            if bucket not in bucket_files:
                bucket_files[bucket] = []
            bucket_files[bucket].append(file_info)
        
        result_text += "\nFiles by bucket:\n"
        for bucket, files in bucket_files.items():
            result_text += f"  {bucket}: {len(files)} files\n"
            # Show first few files as examples
            for file_info in files[:3]:
                result_text += f"    - {file_info['file_path']} ({file_info['file_size']} bytes)\n"
            if len(files) > 3:
                result_text += f"    ... and {len(files) - 3} more files\n"
        
        # Compute filesystem hash
        fs_hash = await vfs_tracker.compute_filesystem_hash(filesystem_state)
        result_text += f"\nFilesystem hash: {fs_hash}"
        
        return [TextContent(type="text", text=result_text)]
        
    except Exception as e:
        logger.error(f"Error in vfs_scan: {e}")
        return [TextContent(type="text", text=f"✗ Error scanning filesystem: {e}")]


async def handle_vfs_auto_commit(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle automatic VFS commit."""
    if not VFS_TRACKER_AVAILABLE:
        return [TextContent(
            type="text",
            text="ERROR: VFS version tracker not available"
        )]
    
    try:
        message = arguments.get("message") or f"Auto-commit {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        force = arguments.get("force", False)
        
        result = await auto_version_filesystem(
            commit_message=message,
            force=force
        )
        
        if result["success"]:
            result_text = f"✓ Auto-commit successful\n"
            result_text += f"Version CID: {result['version_cid']}\n"
            result_text += f"Files: {result['file_count']}"
            
            return [TextContent(type="text", text=result_text)]
        else:
            error_msg = result.get('error', result.get('message', 'Unknown error'))
            if "No changes detected" in error_msg:
                return [TextContent(type="text", text="✓ No changes detected - no commit needed")]
            else:
                return [TextContent(type="text", text=f"✗ Auto-commit failed: {error_msg}")]
                
    except Exception as e:
        logger.error(f"Error in vfs_auto_commit: {e}")
        return [TextContent(type="text", text=f"✗ Error during auto-commit: {e}")]


async def handle_vfs_diff(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle VFS diff between versions."""
    if not VFS_TRACKER_AVAILABLE:
        return [TextContent(
            type="text",
            text="ERROR: VFS version tracker not available"
        )]
    
    try:
        directory = arguments.get("directory")
        version_a = arguments.get("version_a")
        version_b = arguments.get("version_b")
        
        vfs_tracker = get_global_vfs_tracker(vfs_root=directory)
        
        # For now, return basic diff info (full implementation would compare version objects)
        current_head = await vfs_tracker.get_current_head()
        has_changed, current_hash, _ = await vfs_tracker.has_filesystem_changed()
        
        result_text = "VFS Diff Information:\n"
        result_text += "=" * 30 + "\n"
        result_text += f"Current HEAD: {current_head[:12]}...\n"
        result_text += f"Current Hash: {current_hash[:12]}...\n"
        result_text += f"Has Changes: {'Yes' if has_changed else 'No'}\n"
        
        if version_a:
            result_text += f"Version A: {version_a[:12]}...\n"
        if version_b:
            result_text += f"Version B: {version_b[:12]}...\n"
        
        result_text += "\nNote: Detailed diff implementation pending"
        
        return [TextContent(type="text", text=result_text)]
        
    except Exception as e:
        logger.error(f"Error in vfs_diff: {e}")
        return [TextContent(type="text", text=f"✗ Error computing diff: {e}")]


# MCP Tool Registry

VFS_VERSION_TOOLS = [
    VFS_INIT_TOOL,
    VFS_STATUS_TOOL,
    VFS_COMMIT_TOOL,
    VFS_LOG_TOOL,
    VFS_CHECKOUT_TOOL,
    VFS_SCAN_TOOL,
    VFS_AUTO_COMMIT_TOOL,
    VFS_DIFF_TOOL
]

VFS_VERSION_HANDLERS = {
    "vfs_init": handle_vfs_init,
    "vfs_status": handle_vfs_status, 
    "vfs_commit": handle_vfs_commit,
    "vfs_log": handle_vfs_log,
    "vfs_checkout": handle_vfs_checkout,
    "vfs_scan": handle_vfs_scan,
    "vfs_auto_commit": handle_vfs_auto_commit,
    "vfs_diff": handle_vfs_diff
}


def get_vfs_version_tools() -> List[Tool]:
    """Get all VFS version tracking MCP tools."""
    return VFS_VERSION_TOOLS


def get_vfs_version_handlers() -> Dict[str, Any]:
    """Get all VFS version tracking MCP handlers."""
    return VFS_VERSION_HANDLERS
