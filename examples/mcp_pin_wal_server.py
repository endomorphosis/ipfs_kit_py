#!/usr/bin/env python3
"""
MCP Server WAL Integration

This module provides MCP server integration with the Pin WAL system,
allowing non-blocking pin operations through the MCP interface.
"""

import anyio
import logging
from typing import Dict, Any, Optional, List
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
import mcp.types as types

logger = logging.getLogger(__name__)

# Try to import WAL components
try:
    from ipfs_kit_py.pin_wal import add_pin_to_wal, remove_pin_from_wal, get_global_pin_wal
    WAL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"WAL components not available: {e}")
    WAL_AVAILABLE = False

class PinWALMCPServer:
    """MCP Server with Pin WAL integration."""
    
    def __init__(self):
        self.server = Server("ipfs-kit-pin-wal")
        self.pin_wal = None
        
        if WAL_AVAILABLE:
            self.pin_wal = get_global_pin_wal()
        
        # Register MCP handlers
        self._register_tools()
        self._register_resources()
    
    def _register_tools(self):
        """Register MCP tools for pin operations."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """List available tools."""
            tools = []
            
            if WAL_AVAILABLE:
                tools.extend([
                    types.Tool(
                        name="pin_add_wal",
                        description="Add a pin operation to the write-ahead log",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "cid": {
                                    "type": "string",
                                    "description": "The content identifier to pin"
                                },
                                "name": {
                                    "type": "string",
                                    "description": "Optional name for the pin"
                                },
                                "recursive": {
                                    "type": "boolean",
                                    "description": "Whether to pin recursively",
                                    "default": True
                                },
                                "priority": {
                                    "type": "integer",
                                    "description": "Operation priority (0-10)",
                                    "default": 1
                                }
                            },
                            "required": ["cid"]
                        }
                    ),
                    types.Tool(
                        name="pin_remove_wal",
                        description="Add a pin removal operation to the write-ahead log",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "cid": {
                                    "type": "string",
                                    "description": "The content identifier to unpin"
                                },
                                "priority": {
                                    "type": "integer",
                                    "description": "Operation priority (0-10)",
                                    "default": 1
                                }
                            },
                            "required": ["cid"]
                        }
                    ),
                    types.Tool(
                        name="pin_status_wal",
                        description="Check the status of a pin operation",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "operation_id": {
                                    "type": "string",
                                    "description": "The operation ID to check"
                                }
                            },
                            "required": ["operation_id"]
                        }
                    ),
                    types.Tool(
                        name="wal_stats",
                        description="Get WAL statistics and status",
                        inputSchema={
                            "type": "object",
                            "properties": {}
                        }
                    )
                ])
            else:
                tools.append(
                    types.Tool(
                        name="wal_unavailable",
                        description="WAL system is not available",
                        inputSchema={
                            "type": "object",
                            "properties": {}
                        }
                    )
                )
            
            return tools
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            """Handle tool calls."""
            
            if not WAL_AVAILABLE:
                return [types.TextContent(
                    type="text",
                    text="❌ WAL system is not available. Pin operations cannot be processed."
                )]
            
            try:
                if name == "pin_add_wal":
                    return await self._handle_pin_add_wal(arguments)
                elif name == "pin_remove_wal":
                    return await self._handle_pin_remove_wal(arguments)
                elif name == "pin_status_wal":
                    return await self._handle_pin_status_wal(arguments)
                elif name == "wal_stats":
                    return await self._handle_wal_stats(arguments)
                else:
                    return [types.TextContent(
                        type="text",
                        text=f"❌ Unknown tool: {name}"
                    )]
            except Exception as e:
                logger.error(f"Error handling tool {name}: {e}")
                return [types.TextContent(
                    type="text",
                    text=f"❌ Error: {str(e)}"
                )]
    
    async def _handle_pin_add_wal(self, arguments: dict) -> list[types.TextContent]:
        """Handle pin add WAL operation."""
        cid = arguments.get("cid")
        name = arguments.get("name")
        recursive = arguments.get("recursive", True)
        priority = arguments.get("priority", 1)
        
        if not cid:
            return [types.TextContent(
                type="text",
                text="❌ CID is required for pin add operation"
            )]
        
        try:
            metadata = {
                "added_via": "mcp_server",
                "mcp_timestamp": anyio.current_time()
            }
            
            operation_id = await add_pin_to_wal(
                cid=cid,
                name=name,
                recursive=recursive,
                metadata=metadata,
                priority=priority
            )
            
            response = f"✅ Pin operation queued successfully\n"
            response += f"   CID: {cid}\n"
            if name:
                response += f"   Name: {name}\n"
            response += f"   Recursive: {recursive}\n"
            response += f"   Priority: {priority}\n"
            response += f"   Operation ID: {operation_id}\n\n"
            response += "📝 The pin operation has been added to the write-ahead log.\n"
            response += "   The daemon will process it and update the metadata index.\n"
            response += f"   Use 'pin_status_wal' with operation_id '{operation_id}' to check progress."
            
            return [types.TextContent(type="text", text=response)]
            
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Failed to add pin to WAL: {str(e)}"
            )]
    
    async def _handle_pin_remove_wal(self, arguments: dict) -> list[types.TextContent]:
        """Handle pin remove WAL operation."""
        cid = arguments.get("cid")
        priority = arguments.get("priority", 1)
        
        if not cid:
            return [types.TextContent(
                type="text",
                text="❌ CID is required for pin remove operation"
            )]
        
        try:
            metadata = {
                "removed_via": "mcp_server",
                "mcp_timestamp": anyio.current_time()
            }
            
            operation_id = await remove_pin_from_wal(
                cid=cid,
                metadata=metadata,
                priority=priority
            )
            
            response = f"✅ Pin removal operation queued successfully\n"
            response += f"   CID: {cid}\n"
            response += f"   Priority: {priority}\n"
            response += f"   Operation ID: {operation_id}\n\n"
            response += "📝 The pin removal has been added to the write-ahead log.\n"
            response += "   The daemon will process it and update the metadata index.\n"
            response += f"   Use 'pin_status_wal' with operation_id '{operation_id}' to check progress."
            
            return [types.TextContent(type="text", text=response)]
            
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Failed to add pin removal to WAL: {str(e)}"
            )]
    
    async def _handle_pin_status_wal(self, arguments: dict) -> list[types.TextContent]:
        """Handle pin status check."""
        operation_id = arguments.get("operation_id")
        
        if not operation_id:
            return [types.TextContent(
                type="text",
                text="❌ Operation ID is required for status check"
            )]
        
        try:
            if not self.pin_wal:
                return [types.TextContent(
                    type="text",
                    text="❌ WAL system not available"
                )]
            
            operation = await self.pin_wal.get_operation_status(operation_id)
            
            if not operation:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Operation {operation_id} not found"
                )]
            
            response = "📋 OPERATION STATUS\n"
            response += "-" * 30 + "\n"
            response += f"Operation ID: {operation.get('operation_id', 'unknown')}\n"
            response += f"Type: {operation.get('operation_type', 'unknown')}\n"
            response += f"CID: {operation.get('cid', 'unknown')}\n"
            response += f"Status: {operation.get('status', 'unknown')}\n"
            response += f"Created: {operation.get('created_at', 'unknown')}\n"
            
            if operation.get('name'):
                response += f"Name: {operation['name']}\n"
            
            if operation.get('recursive') is not None:
                response += f"Recursive: {operation['recursive']}\n"
            
            if operation.get('retry_count', 0) > 0:
                response += f"Retry count: {operation['retry_count']}\n"
            
            if operation.get('last_error'):
                response += f"Last error: {operation['last_error']}\n"
            
            if operation.get('completed_at'):
                response += f"Completed: {operation['completed_at']}\n"
            
            return [types.TextContent(type="text", text=response)]
            
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Failed to get operation status: {str(e)}"
            )]
    
    async def _handle_wal_stats(self, arguments: dict) -> list[types.TextContent]:
        """Handle WAL statistics request."""
        try:
            if not self.pin_wal:
                return [types.TextContent(
                    type="text",
                    text="❌ WAL system not available"
                )]
            
            stats = await self.pin_wal.get_stats()
            
            response = "📊 WAL STATISTICS\n"
            response += "=" * 30 + "\n"
            response += f"Pending operations: {stats.get('pending', 0)}\n"
            response += f"Processing operations: {stats.get('processing', 0)}\n"
            response += f"Completed operations: {stats.get('completed', 0)}\n"
            response += f"Failed operations: {stats.get('failed', 0)}\n"
            response += f"Total operations: {stats.get('total_operations', 0)}\n"
            response += f"Cache size: {stats.get('cache_size', 0)}\n"
            
            return [types.TextContent(type="text", text=response)]
            
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Failed to get WAL statistics: {str(e)}"
            )]
    
    def _register_resources(self):
        """Register MCP resources."""
        
        @self.server.list_resources()
        async def handle_list_resources() -> list[types.Resource]:
            """List available resources."""
            resources = []
            
            if WAL_AVAILABLE:
                resources.append(
                    types.Resource(
                        uri="wal://pin-operations/status",
                        name="Pin Operations WAL Status",
                        description="Current status of the pin operations write-ahead log",
                        mimeType="application/json"
                    )
                )
            
            return resources
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read resource content."""
            if uri == "wal://pin-operations/status":
                if not self.pin_wal:
                    return '{"error": "WAL system not available"}'
                
                try:
                    stats = await self.pin_wal.get_stats()
                    return f'{{"wal_stats": {stats}}}'
                except Exception as e:
                    return f'{{"error": "Failed to get WAL stats: {str(e)}"}}'
            
            raise ValueError(f"Unknown resource: {uri}")
    
    async def run(self, transport_type: str = "stdio"):
        """Run the MCP server."""
        if transport_type == "stdio":
            from mcp.server.stdio import stdio_server
            
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="ipfs-kit-pin-wal",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")


async def main():
    """Main entry point for the MCP server."""
    server = PinWALMCPServer()
    await server.run()


if __name__ == "__main__":
    anyio.run(main)
