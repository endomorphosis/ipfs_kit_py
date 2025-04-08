"""
CLI Controller for the MCP server.

This controller provides an interface to the CLI functionality through the MCP API.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from fastapi import APIRouter, HTTPException, Depends, Body, Query, Path, Response
from pydantic import BaseModel, Field

from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.validation import validate_cid

# Check for WAL integration support
try:
    from ipfs_kit_py.wal_cli_integration import handle_wal_command
    WAL_CLI_AVAILABLE = True
except ImportError:
    WAL_CLI_AVAILABLE = False

# Configure logger
logger = logging.getLogger(__name__)

# Define Pydantic models for requests and responses
class FormatType(str, Enum):
    """Output format types."""
    JSON = "json"
    YAML = "yaml" 
    TEXT = "text"

class CliCommandRequest(BaseModel):
    """Request model for executing CLI commands."""
    command: str = Field(..., description="CLI command to execute")
    args: List[str] = Field(default=[], description="Command arguments")
    params: Dict[str, Any] = Field(default={}, description="Additional parameters")
    format: FormatType = Field(default=FormatType.JSON, description="Output format")

class CliCommandResponse(BaseModel):
    """Response model for CLI command execution."""
    success: bool = Field(..., description="Whether the command was successful")
    result: Any = Field(None, description="Command result")
    operation_id: Optional[str] = Field(None, description="Operation ID for async operations")
    format: Optional[str] = Field(None, description="Output format used")

class CliVersionResponse(BaseModel):
    """Response model for CLI version information."""
    ipfs_kit_py_version: str = Field(..., description="IPFS Kit Python package version")
    python_version: Optional[str] = Field(None, description="Python version")
    platform: Optional[str] = Field(None, description="Platform information")
    ipfs_daemon_version: Optional[str] = Field(None, description="IPFS daemon version")

class CliWalStatusResponse(BaseModel):
    """Response model for WAL status information."""
    success: bool = Field(..., description="Whether the operation was successful")
    total_operations: int = Field(..., description="Total WAL operations")
    pending: int = Field(..., description="Pending operations")
    processing: int = Field(..., description="Processing operations")
    completed: int = Field(..., description="Completed operations")
    failed: int = Field(..., description="Failed operations")

class CliController:
    """
    Controller for CLI operations.
    
    Provides HTTP endpoints for CLI functionality through the MCP API.
    """
    
    def __init__(self, ipfs_model):
        """
        Initialize the CLI controller.
        
        Args:
            ipfs_model: IPFS model to use for operations
        """
        self.ipfs_model = ipfs_model
        self.api = IPFSSimpleAPI()  # Create high-level API instance
        logger.info("CLI Controller initialized")
    
    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.
        
        Args:
            router: FastAPI router to register routes with
        """
        
        # Get CLI version
        router.add_api_route(
            "/cli/version",
            self.get_version,
            methods=["GET"],
            response_model=CliVersionResponse,
            summary="Get version information",
            description="Get version information for IPFS Kit and dependencies"
        )
        
        # Add content with CLI
        router.add_api_route(
            "/cli/add",
            self.add_content,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Add content via CLI",
            description="Add content to IPFS using the CLI interface"
        )
        
        # Get content with CLI
        router.add_api_route(
            "/cli/cat/{cid}",
            self.get_content,
            methods=["GET"],
            response_class=Response,
            summary="Get content via CLI",
            description="Get content from IPFS using the CLI interface"
        )
        
        # Pin content with CLI
        router.add_api_route(
            "/cli/pin/{cid}",
            self.pin_content,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Pin content via CLI",
            description="Pin content to local IPFS node using the CLI interface"
        )
        
        # Unpin content with CLI
        router.add_api_route(
            "/cli/unpin/{cid}",
            self.unpin_content,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Unpin content via CLI",
            description="Unpin content from local IPFS node using the CLI interface"
        )
        
        # List pins with CLI
        router.add_api_route(
            "/cli/pins",
            self.list_pins,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="List pins via CLI",
            description="List pinned content using the CLI interface"
        )
        
        # IPNS publish endpoint
        router.add_api_route(
            "/cli/publish/{cid}",
            self.publish_content,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Publish to IPNS via CLI",
            description="Publish content to IPNS using the CLI interface"
        )
        
        # IPNS resolve endpoint
        router.add_api_route(
            "/cli/resolve/{name}",
            self.resolve_name,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Resolve IPNS name via CLI",
            description="Resolve IPNS name to CID using the CLI interface"
        )
        
        # Connect to peer endpoint
        router.add_api_route(
            "/cli/connect/{peer}",
            self.connect_peer,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Connect to peer via CLI",
            description="Connect to a peer using the CLI interface"
        )
        
        # List peers endpoint
        router.add_api_route(
            "/cli/peers",
            self.list_peers,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="List peers via CLI",
            description="List connected peers using the CLI interface"
        )
        
        # Path existence endpoint
        router.add_api_route(
            "/cli/exists/{path}",
            self.check_existence,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Check existence via CLI",
            description="Check if path exists in IPFS using the CLI interface"
        )
        
        # Directory listing endpoint
        router.add_api_route(
            "/cli/ls/{path}",
            self.list_directory,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="List directory via CLI",
            description="List directory contents using the CLI interface"
        )
        
        # SDK generation endpoint
        router.add_api_route(
            "/cli/generate-sdk",
            self.generate_sdk,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Generate SDK via CLI",
            description="Generate SDK for a specific language using the CLI interface"
        )
        
        # WebRTC dependencies check
        router.add_api_route(
            "/cli/webrtc/check-deps",
            self.check_webrtc_dependencies,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Check WebRTC dependencies",
            description="Check if WebRTC dependencies are available"
        )
        
        # Start WebRTC streaming
        router.add_api_route(
            "/cli/webrtc/stream",
            self.start_webrtc_stream,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Start WebRTC streaming",
            description="Start WebRTC streaming for IPFS content"
        )
        
        # Run WebRTC benchmark
        router.add_api_route(
            "/cli/webrtc/benchmark",
            self.run_webrtc_benchmark,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Run WebRTC benchmark",
            description="Run WebRTC streaming benchmark"
        )
        
        # IPLD import
        router.add_api_route(
            "/cli/ipld/import",
            self.ipld_import,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Import IPLD object",
            description="Import data as an IPLD object"
        )
        
        # IPLD create link
        router.add_api_route(
            "/cli/ipld/link",
            self.ipld_link,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Create IPLD link",
            description="Create a link between IPLD objects"
        )
        
        # IPLD get object
        router.add_api_route(
            "/cli/ipld/get/{cid}",
            self.ipld_get,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Get IPLD object",
            description="Get an IPLD object and its data"
        )
        
        # MCP server start
        router.add_api_route(
            "/cli/mcp/start",
            self.start_mcp_server,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Start MCP server",
            description="Start the MCP server"
        )
        
        # MCP server stop
        router.add_api_route(
            "/cli/mcp/stop",
            self.stop_mcp_server,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Stop MCP server",
            description="Stop the MCP server"
        )
        
        # MCP server status
        router.add_api_route(
            "/cli/mcp/status",
            self.get_mcp_server_status,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Get MCP server status",
            description="Get the current status of the MCP server"
        )
        
        # Register WAL CLI routes if available
        if WAL_CLI_AVAILABLE:
            # WAL status
            router.add_api_route(
                "/cli/wal/status",
                self.get_wal_status,
                methods=["GET"],
                response_model=CliWalStatusResponse,
                summary="Get WAL status",
                description="Get WAL status and statistics"
            )
            
            # WAL list operations
            router.add_api_route(
                "/cli/wal/list/{operation_type}",
                self.list_wal_operations,
                methods=["GET"],
                response_model=CliCommandResponse,
                summary="List WAL operations",
                description="List WAL operations by type"
            )
            
            # WAL show operation
            router.add_api_route(
                "/cli/wal/show/{operation_id}",
                self.show_wal_operation,
                methods=["GET"],
                response_model=CliCommandResponse,
                summary="Show WAL operation",
                description="Show details for a specific WAL operation"
            )
            
            # WAL retry operation
            router.add_api_route(
                "/cli/wal/retry/{operation_id}",
                self.retry_wal_operation,
                methods=["POST"],
                response_model=CliCommandResponse,
                summary="Retry WAL operation",
                description="Retry a failed WAL operation"
            )
            
            # WAL cleanup
            router.add_api_route(
                "/cli/wal/cleanup",
                self.cleanup_wal,
                methods=["POST"],
                response_model=CliCommandResponse,
                summary="Clean up WAL",
                description="Clean up old WAL operations"
            )
            
            # WAL metrics
            router.add_api_route(
                "/cli/wal/metrics",
                self.get_wal_metrics,
                methods=["GET"],
                response_model=CliCommandResponse,
                summary="Get WAL metrics",
                description="Get WAL metrics and performance statistics"
            )
        
        logger.info("CLI Controller routes registered")
    
    async def execute_command(self, command_request: CliCommandRequest) -> Dict[str, Any]:
        """
        Execute a CLI command.
        
        Args:
            command_request: CLI command request
            
        Returns:
            Command execution result
        """
        try:
            logger.debug(f"Executing CLI command: {command_request.command} {command_request.args}")
            
            # Execute the command using the high-level API
            if command_request.command == "add":
                result = self.api.add(command_request.args[0], **command_request.params)
            elif command_request.command == "get":
                result = self.api.get(command_request.args[0], **command_request.params)
            elif command_request.command == "pin":
                result = self.api.pin(command_request.args[0], **command_request.params)
            elif command_request.command == "unpin":
                result = self.api.unpin(command_request.args[0], **command_request.params)
            elif command_request.command == "list-pins":
                result = self.api.list_pins(**command_request.params)
            elif command_request.command == "version":
                result = self._get_version_info()
            elif command_request.command == "publish":
                cid = command_request.args[0] if len(command_request.args) > 0 else command_request.params.get("cid")
                result = self.api.publish(cid, **command_request.params)
            elif command_request.command == "resolve":
                name = command_request.args[0] if len(command_request.args) > 0 else command_request.params.get("name")
                result = self.api.resolve(name, **command_request.params)
            elif command_request.command == "connect":
                peer = command_request.args[0] if len(command_request.args) > 0 else command_request.params.get("peer")
                result = self.api.connect(peer, **command_request.params)
            elif command_request.command == "peers":
                result = self.api.peers(**command_request.params)
            elif command_request.command == "exists":
                path = command_request.args[0] if len(command_request.args) > 0 else command_request.params.get("path")
                result = {"exists": self.api.exists(path, **command_request.params)}
            elif command_request.command == "ls":
                path = command_request.args[0] if len(command_request.args) > 0 else command_request.params.get("path")
                result = self.api.ls(path, **command_request.params)
            elif command_request.command == "generate-sdk":
                language = command_request.args[0] if len(command_request.args) > 0 else command_request.params.get("language")
                output_dir = command_request.args[1] if len(command_request.args) > 1 else command_request.params.get("output_dir")
                result = self.api.generate_sdk(language, output_dir)
            elif command_request.command == "webrtc":
                # Handle WebRTC commands
                webrtc_command = command_request.args[0] if len(command_request.args) > 0 else command_request.params.get("webrtc_command")
                
                if webrtc_command == "check-deps":
                    result = self.api.check_webrtc_dependencies()
                elif webrtc_command == "stream":
                    cid = command_request.args[1] if len(command_request.args) > 1 else command_request.params.get("cid")
                    result = self.api.start_webrtc_stream(cid=cid, **command_request.params)
                elif webrtc_command == "benchmark":
                    result = self.api.run_webrtc_benchmark(**command_request.params)
                else:
                    return {
                        "success": False,
                        "result": {"error": f"Unsupported WebRTC command: {webrtc_command}"}
                    }
            elif command_request.command == "ipld":
                # Handle IPLD commands
                ipld_command = command_request.args[0] if len(command_request.args) > 0 else command_request.params.get("ipld_command")
                
                if ipld_command == "import":
                    file = command_request.args[1] if len(command_request.args) > 1 else command_request.params.get("file")
                    result = self.api.ipld_import(file=file, **command_request.params)
                elif ipld_command == "link":
                    from_cid = command_request.args[1] if len(command_request.args) > 1 else command_request.params.get("from_cid")
                    to_cid = command_request.args[2] if len(command_request.args) > 2 else command_request.params.get("to_cid")
                    link_name = command_request.args[3] if len(command_request.args) > 3 else command_request.params.get("link_name")
                    result = self.api.ipld_link(from_cid=from_cid, to_cid=to_cid, link_name=link_name)
                elif ipld_command == "get":
                    cid = command_request.args[1] if len(command_request.args) > 1 else command_request.params.get("cid")
                    path = command_request.params.get("path")
                    result = self.api.ipld_get(cid=cid, path=path)
                else:
                    return {
                        "success": False,
                        "result": {"error": f"Unsupported IPLD command: {ipld_command}"}
                    }
            elif command_request.command == "mcp":
                # Handle MCP server commands
                mcp_command = command_request.args[0] if len(command_request.args) > 0 else command_request.params.get("mcp_command")
                
                if mcp_command == "start":
                    result = self.api.start_mcp_server(**command_request.params)
                elif mcp_command == "stop":
                    result = self.api.stop_mcp_server(**command_request.params)
                elif mcp_command == "status":
                    result = self.api.get_mcp_server_status(**command_request.params)
                else:
                    return {
                        "success": False,
                        "result": {"error": f"Unsupported MCP command: {mcp_command}"}
                    }
            elif command_request.command == "filesystem":
                # Handle filesystem commands
                fs_command = command_request.args[0] if len(command_request.args) > 0 else command_request.params.get("fs_command")
                
                if fs_command == "get":
                    result = self.api.get_filesystem(**command_request.params)
                    result = {"success": True, "message": "Filesystem interface created", "filesystem_info": {"ready": True}}
                elif fs_command == "enable-journal":
                    result = self.api.enable_filesystem_journal(**command_request.params)
                    result = {"success": True, "message": "Filesystem journaling enabled", "journal_info": result}
                elif fs_command == "disable-journal":
                    result = self.api.disable_filesystem_journal()
                    result = {"success": True, "message": "Filesystem journaling disabled", "journal_info": result}
                elif fs_command == "journal-status":
                    result = self.api.get_filesystem_journal_status()
                    result = {"success": True, "journal_status": result}
                else:
                    return {
                        "success": False,
                        "result": {"error": f"Unsupported filesystem command: {fs_command}"}
                    }
            elif command_request.command == "wal" and WAL_CLI_AVAILABLE:
                # Handle WAL command through the WAL CLI integration
                import argparse
                args = argparse.Namespace()
                args.wal_command = command_request.args[0] if len(command_request.args) > 0 else None
                
                # Add the remaining arguments as attributes
                for i, arg in enumerate(command_request.args[1:]):
                    setattr(args, f"arg{i}", arg)
                
                # Add params as attributes
                for key, value in command_request.params.items():
                    setattr(args, key, value)
                
                result = handle_wal_command(args, self.api)
            else:
                return {
                    "success": False,
                    "result": {"error": f"Unsupported command: {command_request.command}"}
                }
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            # Format the result according to the requested format
            formatted_result = result
            if command_request.format == FormatType.YAML:
                import yaml
                try:
                    # Convert result to YAML format (still returning as a string)
                    formatted_result = {"yaml_output": yaml.dump(result, default_flow_style=False)}
                except Exception as e:
                    logger.warning(f"Error formatting result as YAML: {e}")
            elif command_request.format == FormatType.TEXT:
                # Format as text (simple formatting for API)
                if isinstance(result, dict):
                    text_lines = []
                    for key, value in result.items():
                        if isinstance(value, dict):
                            text_lines.append(f"{key}:")
                            for k, v in value.items():
                                text_lines.append(f"  {k}: {v}")
                        elif isinstance(value, list):
                            text_lines.append(f"{key}:")
                            for item in value:
                                text_lines.append(f"  - {item}")
                        else:
                            text_lines.append(f"{key}: {value}")
                    formatted_text = "\n".join(text_lines)
                    formatted_result = {"text_output": formatted_text}
                elif isinstance(result, list):
                    formatted_result = {"text_output": "\n".join([str(item) for item in result])}
                else:
                    formatted_result = {"text_output": str(result)}
            
            return {
                "success": success,
                "result": formatted_result,
                "format": str(command_request.format)
            }
        except Exception as e:
            logger.error(f"Error executing CLI command: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def get_version(self) -> Dict[str, Any]:
        """
        Get version information.
        
        Returns:
            Version information
        """
        try:
            return self._get_version_info()
        except Exception as e:
            logger.error(f"Error getting version information: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_version_info(self) -> Dict[str, Any]:
        """
        Get version information.
        
        Returns:
            Version information dictionary
        """
        import platform
        import importlib.metadata
        
        # Get package version
        try:
            package_version = importlib.metadata.version("ipfs_kit_py")
        except:
            package_version = "unknown (development mode)"
        
        # Get platform information
        platform_info = f"{platform.system()} {platform.release()}"
        
        # Get Python version
        python_version = platform.python_version()
        
        # Try to get IPFS daemon version
        try:
            if hasattr(self.api, "ipfs") and hasattr(self.api.ipfs, "ipfs_version"):
                ipfs_version_result = self.api.ipfs.ipfs_version()
                if isinstance(ipfs_version_result, dict) and "Version" in ipfs_version_result:
                    ipfs_version = ipfs_version_result["Version"]
                else:
                    ipfs_version = str(ipfs_version_result)
            else:
                ipfs_version = "unknown"
        except Exception:
            ipfs_version = "unknown (daemon not running)"
        
        return {
            "ipfs_kit_py_version": package_version,
            "python_version": python_version,
            "platform": platform_info,
            "ipfs_daemon_version": ipfs_version
        }
    
    async def add_content(self, content: str = Body(..., description="Content to add"), 
                          filename: Optional[str] = Body(None, description="Optional filename"),
                          wrap_with_directory: bool = Body(False, description="Wrap content with a directory"),
                          chunker: str = Body("size-262144", description="Chunking algorithm (e.g., size-262144)"),
                          hash: str = Body("sha2-256", description="Hash algorithm (e.g., sha2-256)"),
                          pin: bool = Body(True, description="Pin content after adding")) -> Dict[str, Any]:
        """
        Add content via CLI.
        
        Args:
            content: Content to add
            filename: Optional filename
            wrap_with_directory: Wrap content with a directory
            chunker: Chunking algorithm (e.g., size-262144)
            hash: Hash algorithm (e.g., sha2-256)
            pin: Whether to pin content after adding
            
        Returns:
            Add operation result
        """
        try:
            # Add content using the high-level API
            params = {
                "wrap_with_directory": wrap_with_directory,
                "chunker": chunker,
                "hash": hash,
                "pin": pin
            }
            
            if filename:
                params["filename"] = filename
            
            result = self.api.add(content, **params)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error adding content: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def get_content(self, cid: str = Path(..., description="Content identifier")) -> Response:
        """
        Get content via CLI.
        
        Args:
            cid: Content identifier
            
        Returns:
            Raw content response
        """
        try:
            # Validate CID
            validate_cid(cid)
            
            # Get content using the high-level API
            content = self.api.get(cid)
            
            # Prepare response headers
            headers = {
                "X-IPFS-Path": f"/ipfs/{cid}"
            }
            
            # Return raw response
            return Response(
                content=content if isinstance(content, bytes) else content.encode("utf-8"),
                media_type="application/octet-stream",
                headers=headers
            )
        except Exception as e:
            logger.error(f"Error getting content: {e}")
            raise HTTPException(status_code=404, detail=f"Content not found: {str(e)}")
    
    async def pin_content(self, cid: str = Path(..., description="Content identifier"),
                          recursive: bool = Query(True, description="Pin recursively")) -> Dict[str, Any]:
        """
        Pin content via CLI.
        
        Args:
            cid: Content identifier
            recursive: Whether to pin recursively
            
        Returns:
            Pin operation result
        """
        try:
            # Validate CID
            validate_cid(cid)
            
            # Pin content using the high-level API
            result = self.api.pin(cid, recursive=recursive)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error pinning content: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def unpin_content(self, cid: str = Path(..., description="Content identifier"),
                            recursive: bool = Query(True, description="Unpin recursively")) -> Dict[str, Any]:
        """
        Unpin content via CLI.
        
        Args:
            cid: Content identifier
            recursive: Whether to unpin recursively
            
        Returns:
            Unpin operation result
        """
        try:
            # Validate CID
            validate_cid(cid)
            
            # Unpin content using the high-level API
            result = self.api.unpin(cid, recursive=recursive)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error unpinning content: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def list_pins(self, pin_type: str = Query("all", description="Pin type filter"),
                       quiet: bool = Query(False, description="Return only CIDs")) -> Dict[str, Any]:
        """
        List pins via CLI.
        
        Args:
            pin_type: Pin type filter
            quiet: Return only CIDs
            
        Returns:
            List pins operation result
        """
        try:
            # List pins using the high-level API
            result = self.api.list_pins(type=pin_type, quiet=quiet)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error listing pins: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    # WAL CLI routes - only available if WAL integration is enabled
    
    async def get_wal_status(self) -> Dict[str, Any]:
        """
        Get WAL status.
        
        Returns:
            WAL status information
        """
        if not WAL_CLI_AVAILABLE:
            return {
                "success": False,
                "error": "WAL integration not available"
            }
        
        try:
            # Get WAL status
            import argparse
            args = argparse.Namespace()
            args.wal_command = "status"
            
            result = handle_wal_command(args, self.api)
            
            # Format result for response
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
                
                if success:
                    # Return formatted result for Pydantic model
                    return {
                        "success": success,
                        "total_operations": result.get("Total operations", 0),
                        "pending": result.get("Pending", 0),
                        "processing": result.get("Processing", 0),
                        "completed": result.get("Completed", 0),
                        "failed": result.get("Failed", 0)
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    }
            else:
                return {
                    "success": False,
                    "error": "Invalid WAL status response"
                }
        except Exception as e:
            logger.error(f"Error getting WAL status: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_wal_operations(self, operation_type: str = Path(..., description="Operation type"),
                                 limit: int = Query(10, description="Maximum number of operations to show"),
                                 backend: str = Query("all", description="Backend filter")) -> Dict[str, Any]:
        """
        List WAL operations.
        
        Args:
            operation_type: Operation type
            limit: Maximum number of operations to show
            backend: Backend filter
            
        Returns:
            WAL operations list
        """
        if not WAL_CLI_AVAILABLE:
            return {
                "success": False,
                "result": {"error": "WAL integration not available"}
            }
        
        try:
            # Get WAL operations
            import argparse
            args = argparse.Namespace()
            args.wal_command = "list"
            args.operation_type = operation_type
            args.limit = limit
            args.backend = backend
            
            result = handle_wal_command(args, self.api)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error listing WAL operations: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def show_wal_operation(self, operation_id: str = Path(..., description="Operation ID")) -> Dict[str, Any]:
        """
        Show WAL operation details.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            WAL operation details
        """
        if not WAL_CLI_AVAILABLE:
            return {
                "success": False,
                "result": {"error": "WAL integration not available"}
            }
        
        try:
            # Get WAL operation details
            import argparse
            args = argparse.Namespace()
            args.wal_command = "show"
            args.operation_id = operation_id
            
            result = handle_wal_command(args, self.api)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error showing WAL operation: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def retry_wal_operation(self, operation_id: str = Path(..., description="Operation ID")) -> Dict[str, Any]:
        """
        Retry a failed WAL operation.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            Retry operation result
        """
        if not WAL_CLI_AVAILABLE:
            return {
                "success": False,
                "result": {"error": "WAL integration not available"}
            }
        
        try:
            # Retry WAL operation
            import argparse
            args = argparse.Namespace()
            args.wal_command = "retry"
            args.operation_id = operation_id
            
            result = handle_wal_command(args, self.api)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error retrying WAL operation: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def cleanup_wal(self) -> Dict[str, Any]:
        """
        Clean up old WAL operations.
        
        Returns:
            Cleanup operation result
        """
        if not WAL_CLI_AVAILABLE:
            return {
                "success": False,
                "result": {"error": "WAL integration not available"}
            }
        
        try:
            # Clean up WAL operations
            import argparse
            args = argparse.Namespace()
            args.wal_command = "cleanup"
            
            result = handle_wal_command(args, self.api)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error cleaning up WAL: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def get_wal_metrics(self, detailed: bool = Query(False, description="Show detailed metrics")) -> Dict[str, Any]:
        """
        Get WAL metrics.
        
        Args:
            detailed: Whether to show detailed metrics
            
        Returns:
            WAL metrics
        """
        if not WAL_CLI_AVAILABLE:
            return {
                "success": False,
                "result": {"error": "WAL integration not available"}
            }
        
        try:
            # Get WAL metrics
            import argparse
            args = argparse.Namespace()
            args.wal_command = "metrics"
            args.detailed = detailed
            
            result = handle_wal_command(args, self.api)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error getting WAL metrics: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
            
    # New handlers for the added CLI routes
    
    async def publish_content(self, 
                             cid: str = Path(..., description="Content identifier"),
                             key: str = Query("self", description="IPNS key to use"),
                             lifetime: str = Query("24h", description="IPNS record lifetime"),
                             ttl: str = Query("1h", description="IPNS record TTL")) -> Dict[str, Any]:
        """
        Publish content to IPNS.
        
        Args:
            cid: Content identifier to publish
            key: IPNS key to use
            lifetime: IPNS record lifetime
            ttl: IPNS record TTL
            
        Returns:
            Publish operation result
        """
        try:
            # Validate CID
            validate_cid(cid)
            
            # Publish to IPNS using the high-level API
            result = self.api.publish(cid, key=key, lifetime=lifetime, ttl=ttl)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error publishing to IPNS: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def resolve_name(self, 
                          name: str = Path(..., description="IPNS name to resolve"),
                          recursive: bool = Query(True, description="Resolve recursively"),
                          timeout: int = Query(30, description="Timeout in seconds")) -> Dict[str, Any]:
        """
        Resolve IPNS name to CID.
        
        Args:
            name: IPNS name to resolve
            recursive: Whether to resolve recursively
            timeout: Timeout in seconds
            
        Returns:
            Resolve operation result
        """
        try:
            # Resolve IPNS name using the high-level API
            result = self.api.resolve(name, recursive=recursive, timeout=timeout)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error resolving IPNS name: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def connect_peer(self, 
                          peer: str = Path(..., description="Peer multiaddress"),
                          timeout: int = Query(30, description="Timeout in seconds")) -> Dict[str, Any]:
        """
        Connect to a peer.
        
        Args:
            peer: Peer multiaddress
            timeout: Timeout in seconds
            
        Returns:
            Connection result
        """
        try:
            # Connect to peer using the high-level API
            result = self.api.connect(peer, timeout=timeout)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error connecting to peer: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def list_peers(self, 
                        verbose: bool = Query(False, description="Return verbose information"),
                        latency: bool = Query(False, description="Include latency information"),
                        direction: bool = Query(False, description="Include connection direction")) -> Dict[str, Any]:
        """
        List connected peers.
        
        Args:
            verbose: Return verbose information
            latency: Include latency information
            direction: Include connection direction
            
        Returns:
            List of connected peers
        """
        try:
            # List peers using the high-level API
            result = self.api.peers(verbose=verbose, latency=latency, direction=direction)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error listing peers: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def check_existence(self, path: str = Path(..., description="IPFS path or CID")) -> Dict[str, Any]:
        """
        Check if path exists in IPFS.
        
        Args:
            path: IPFS path or CID
            
        Returns:
            Existence check result
        """
        try:
            # Check existence using the high-level API
            exists = self.api.exists(path)
            
            return {
                "success": True,
                "result": {"exists": exists}
            }
        except Exception as e:
            logger.error(f"Error checking path existence: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def list_directory(self, 
                           path: str = Path(..., description="IPFS path or CID"),
                           detail: bool = Query(True, description="Return detailed information")) -> Dict[str, Any]:
        """
        List directory contents.
        
        Args:
            path: IPFS path or CID
            detail: Return detailed information
            
        Returns:
            Directory listing
        """
        try:
            # List directory using the high-level API
            result = self.api.ls(path, detail=detail)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error listing directory: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def generate_sdk(self, 
                         language: str = Body(..., description="Target language"),
                         output_dir: str = Body(..., description="Output directory")) -> Dict[str, Any]:
        """
        Generate SDK for a specific language.
        
        Args:
            language: Target language (python, javascript, rust)
            output_dir: Output directory
            
        Returns:
            SDK generation result
        """
        try:
            # Validate language
            if language not in ["python", "javascript", "rust"]:
                return {
                    "success": False,
                    "result": {"error": f"Unsupported language: {language}. Supported languages: python, javascript, rust"}
                }
            
            # Generate SDK using the high-level API
            result = self.api.generate_sdk(language, output_dir)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error generating SDK: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    # WebRTC Methods
    
    async def check_webrtc_dependencies(self) -> Dict[str, Any]:
        """
        Check if WebRTC dependencies are available.
        
        Returns:
            WebRTC dependencies status
        """
        try:
            # Check WebRTC dependencies
            result = self.api.check_webrtc_dependencies()
            
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error checking WebRTC dependencies: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def start_webrtc_stream(self, 
                                cid: str = Body(..., description="Content identifier"),
                                quality: str = Body("medium", description="Streaming quality preset"),
                                port: int = Body(8083, description="Port for WebRTC signaling server"),
                                ice_servers: str = Body(json.dumps([{"urls": ["stun:stun.l.google.com:19302"]}]), description="ICE servers as JSON")) -> Dict[str, Any]:
        """
        Start WebRTC streaming for IPFS content.
        
        Args:
            cid: Content identifier
            quality: Streaming quality preset (low, medium, high, auto)
            port: Port for WebRTC signaling server
            ice_servers: ICE servers as JSON
            
        Returns:
            WebRTC streaming result
        """
        try:
            # Parse ICE servers
            try:
                ice_servers_list = json.loads(ice_servers)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "result": {"error": "Invalid ICE servers JSON"}
                }
            
            # Validate quality
            if quality not in ["low", "medium", "high", "auto"]:
                return {
                    "success": False,
                    "result": {"error": f"Invalid quality preset: {quality}. Valid values: low, medium, high, auto"}
                }
            
            # Start WebRTC streaming
            result = self.api.start_webrtc_stream(cid=cid, quality=quality, port=port, ice_servers=ice_servers_list)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error starting WebRTC stream: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def run_webrtc_benchmark(self, 
                                duration: int = Body(30, description="Benchmark duration in seconds"),
                                bitrates: str = Body("500,1000,2000,5000", description="Comma-separated list of bitrates to test (in kbps)"),
                                output: str = Body("webrtc_benchmark_results.json", description="Output file for benchmark results")) -> Dict[str, Any]:
        """
        Run WebRTC streaming benchmark.
        
        Args:
            duration: Benchmark duration in seconds
            bitrates: Comma-separated list of bitrates to test (in kbps)
            output: Output file for benchmark results
            
        Returns:
            Benchmark results
        """
        try:
            # Parse bitrates
            bitrate_list = [int(b.strip()) for b in bitrates.split(",")]
            
            # Run benchmark
            result = self.api.run_webrtc_benchmark(duration=duration, bitrates=bitrate_list, output=output)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error running WebRTC benchmark: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    # IPLD Methods
    
    async def ipld_import(self, 
                        file: str = Body(..., description="File path to import"),
                        format: str = Body("json", description="IPLD format"),
                        pin: bool = Body(True, description="Pin the imported object")) -> Dict[str, Any]:
        """
        Import data as an IPLD object.
        
        Args:
            file: File path to import
            format: IPLD format (json, cbor, raw)
            pin: Whether to pin the imported object
            
        Returns:
            Import result
        """
        try:
            # Validate format
            if format not in ["json", "cbor", "raw"]:
                return {
                    "success": False,
                    "result": {"error": f"Invalid IPLD format: {format}. Valid formats: json, cbor, raw"}
                }
            
            # Import IPLD object
            result = self.api.ipld_import(file=file, format=format, pin=pin)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error importing IPLD object: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def ipld_link(self, 
                      from_cid: str = Body(..., description="Source CID"),
                      to_cid: str = Body(..., description="Target CID"),
                      link_name: str = Body(..., description="Link name")) -> Dict[str, Any]:
        """
        Create a link between IPLD objects.
        
        Args:
            from_cid: Source CID
            to_cid: Target CID
            link_name: Link name
            
        Returns:
            Link creation result
        """
        try:
            # Create link
            result = self.api.ipld_link(from_cid=from_cid, to_cid=to_cid, link_name=link_name)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error creating IPLD link: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def ipld_get(self, 
                     cid: str = Path(..., description="Content identifier"),
                     path: str = Query(None, description="Optional path within the object")) -> Dict[str, Any]:
        """
        Get an IPLD object and its data.
        
        Args:
            cid: Content identifier
            path: Optional path within the object
            
        Returns:
            IPLD object data
        """
        try:
            # Get IPLD object
            result = self.api.ipld_get(cid=cid, path=path)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error getting IPLD object: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    # MCP Server Methods
    
    async def start_mcp_server(self, 
                             host: str = Body("127.0.0.1", description="Host to bind server"),
                             port: int = Body(8000, description="Port to bind server"),
                             debug: bool = Body(False, description="Enable debug mode"),
                             log_level: str = Body("INFO", description="Logging level")) -> Dict[str, Any]:
        """
        Start the MCP server.
        
        Args:
            host: Host to bind server
            port: Port to bind server
            debug: Enable debug mode
            log_level: Logging level
            
        Returns:
            Server start result
        """
        try:
            # Start MCP server
            result = self.api.start_mcp_server(host=host, port=port, debug=debug, log_level=log_level)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error starting MCP server: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def stop_mcp_server(self, 
                            host: str = Body("127.0.0.1", description="Host of the server"),
                            port: int = Body(8000, description="Port of the server")) -> Dict[str, Any]:
        """
        Stop the MCP server.
        
        Args:
            host: Host of the server
            port: Port of the server
            
        Returns:
            Server stop result
        """
        try:
            # Stop MCP server
            result = self.api.stop_mcp_server(host=host, port=port)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }
    
    async def get_mcp_server_status(self, 
                                  host: str = Query("127.0.0.1", description="Host of the server"),
                                  port: int = Query(8000, description="Port of the server")) -> Dict[str, Any]:
        """
        Get the current status of the MCP server.
        
        Args:
            host: Host of the server
            port: Port of the server
            
        Returns:
            Server status
        """
        try:
            # Get MCP server status
            result = self.api.get_mcp_server_status(host=host, port=port)
            
            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)
            
            return {
                "success": success,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error getting MCP server status: {e}")
            return {
                "success": False,
                "result": {"error": str(e)}
            }