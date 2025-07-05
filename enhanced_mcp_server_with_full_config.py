#!/usr/bin/env python3
"""
Enhanced MCP Server with comprehensive daemon configuration management.

This server extends the original MCP server with robust configuration management
for all supported services: IPFS, Lotus, Lassie, IPFS cluster services, S3, 
HuggingFace, and Storacha.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("enhanced_mcp_server")

# Try to import MCP and ipfs_kit_py
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP not available - running in standalone mode")

try:
    import ipfs_kit_py
    from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
    IPFS_KIT_AVAILABLE = True
except ImportError:
    IPFS_KIT_AVAILABLE = False
    logger.error("ipfs_kit_py not available")

class EnhancedMCPServerWithFullConfig:
    """Enhanced MCP Server with comprehensive daemon configuration management."""
    
    def __init__(self):
        """Initialize the enhanced MCP server."""
        self.config_manager = None
        self.ipfs_kit_instance = None
        
        # Initialize components
        self._initialize_components()
        
        if MCP_AVAILABLE:
            self.server = Server("enhanced-ipfs-kit-server")
            self._setup_mcp_tools()
    
    def _initialize_components(self):
        """Initialize ipfs_kit_py components and configuration manager."""
        if not IPFS_KIT_AVAILABLE:
            logger.error("❌ ipfs_kit_py not available")
            return
        
        try:
            # Initialize ipfs_kit instance
            self.ipfs_kit_instance = ipfs_kit_py.ipfs_kit()
            logger.info("✅ ipfs_kit_py initialized successfully")
            
            # Initialize enhanced configuration manager
            self.config_manager = DaemonConfigManager(self.ipfs_kit_instance)
            logger.info("✅ Enhanced configuration manager initialized")
            
            # Ensure all daemons are configured
            self._ensure_all_daemons_configured()
            
        except Exception as e:
            logger.error(f"❌ Error initializing components: {e}")
            raise
    
    def _ensure_all_daemons_configured(self):
        """Ensure all daemons have proper configuration."""
        if not self.config_manager:
            return
        
        try:
            logger.info("🔧 Ensuring all daemons are configured...")
            
            # Check and configure all daemons
            config_results = self.config_manager.check_and_configure_all_daemons()
            
            if config_results.get("overall_success", False):
                logger.info("✅ All daemons configured successfully")
            else:
                logger.warning("⚠️ Some daemon configurations failed, but continuing...")
                
            # Log summary
            if "summary" in config_results:
                logger.info(f"📋 Configuration summary: {config_results['summary']}")
                
        except Exception as e:
            logger.error(f"❌ Error ensuring daemon configuration: {e}")
            # Don't raise - continue with partially configured system
    
    def _setup_mcp_tools(self):
        """Setup MCP tools for daemon configuration management."""
        if not MCP_AVAILABLE or not self.server:
            return
        
        # Configuration management tools
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="configure_daemon",
                    description="Configure a specific daemon with default settings",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "daemon_name": {
                                "type": "string",
                                "enum": ["ipfs", "lotus", "lassie", "ipfs_cluster_service", 
                                        "ipfs_cluster_follow", "ipfs_cluster_ctl", "s3", 
                                        "huggingface", "storacha", "all"],
                                "description": "Name of the daemon to configure"
                            }
                        },
                        "required": ["daemon_name"]
                    }
                ),
                Tool(
                    name="update_daemon_config",
                    description="Update configuration for a specific daemon",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "daemon_name": {
                                "type": "string",
                                "enum": ["ipfs", "lotus", "lassie", "ipfs_cluster_service", 
                                        "ipfs_cluster_follow", "ipfs_cluster_ctl", "s3", 
                                        "huggingface", "storacha"],
                                "description": "Name of the daemon to update"
                            },
                            "config_updates": {
                                "type": "object",
                                "description": "Configuration updates to apply",
                                "additionalProperties": True
                            }
                        },
                        "required": ["daemon_name", "config_updates"]
                    }
                ),
                Tool(
                    name="validate_daemon_configs",
                    description="Validate all daemon configurations",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_daemon_config_status",
                    description="Get configuration status for all daemons",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="ipfs_add",
                    description="Add content to IPFS",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Content to add to IPFS"
                            }
                        },
                        "required": ["content"]
                    }
                ),
                Tool(
                    name="ipfs_get",
                    description="Get content from IPFS",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cid": {
                                "type": "string",
                                "description": "CID of content to retrieve"
                            }
                        },
                        "required": ["cid"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
            """Handle tool calls."""
            try:
                if name == "configure_daemon":
                    return await self._handle_configure_daemon(arguments)
                elif name == "update_daemon_config":
                    return await self._handle_update_daemon_config(arguments)
                elif name == "validate_daemon_configs":
                    return await self._handle_validate_daemon_configs(arguments)
                elif name == "get_daemon_config_status":
                    return await self._handle_get_daemon_config_status(arguments)
                elif name == "ipfs_add":
                    return await self._handle_ipfs_add(arguments)
                elif name == "ipfs_get":
                    return await self._handle_ipfs_get(arguments)
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
                    
            except Exception as e:
                logger.error(f"Error in tool call {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _handle_configure_daemon(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Handle daemon configuration requests."""
        if not self.config_manager:
            return [TextContent(type="text", text="Configuration manager not available")]
        
        daemon_name = arguments.get("daemon_name", "all")
        
        try:
            if daemon_name == "all":
                results = self.config_manager.check_and_configure_all_daemons()
            elif daemon_name == "ipfs":
                results = {"ipfs": self.config_manager.check_and_configure_ipfs()}
            elif daemon_name == "lotus":
                results = {"lotus": self.config_manager.check_and_configure_lotus()}
            elif daemon_name == "lassie":
                results = {"lassie": self.config_manager.check_and_configure_lassie()}
            elif daemon_name == "ipfs_cluster_service":
                results = {"ipfs_cluster_service": self.config_manager.check_and_configure_ipfs_cluster_service()}
            elif daemon_name == "ipfs_cluster_follow":
                results = {"ipfs_cluster_follow": self.config_manager.check_and_configure_ipfs_cluster_follow()}
            elif daemon_name == "ipfs_cluster_ctl":
                results = {"ipfs_cluster_ctl": self.config_manager.check_and_configure_ipfs_cluster_ctl()}
            elif daemon_name == "s3":
                results = {"s3": self.config_manager.check_and_configure_s3()}
            elif daemon_name == "huggingface":
                results = {"huggingface": self.config_manager.check_and_configure_huggingface()}
            elif daemon_name == "storacha":
                results = {"storacha": self.config_manager.check_and_configure_storacha()}
            else:
                return [TextContent(type="text", text=f"Unknown daemon: {daemon_name}")]
            
            response = f"Configuration results for {daemon_name}:\n"
            response += json.dumps(results, indent=2)
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error configuring {daemon_name}: {str(e)}")]
    
    async def _handle_update_daemon_config(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Handle daemon configuration update requests."""
        if not self.config_manager:
            return [TextContent(type="text", text="Configuration manager not available")]
        
        daemon_name = arguments.get("daemon_name")
        config_updates = arguments.get("config_updates", {})
        
        try:
            result = self.config_manager.update_daemon_config(daemon_name, config_updates)
            
            response = f"Configuration update results for {daemon_name}:\n"
            response += json.dumps(result, indent=2)
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error updating {daemon_name} config: {str(e)}")]
    
    async def _handle_validate_daemon_configs(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Handle daemon configuration validation requests."""
        if not self.config_manager:
            return [TextContent(type="text", text="Configuration manager not available")]
        
        try:
            results = self.config_manager.validate_daemon_configs()
            
            response = "Daemon configuration validation results:\n"
            response += json.dumps(results, indent=2)
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error validating configs: {str(e)}")]
    
    async def _handle_get_daemon_config_status(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Handle daemon configuration status requests."""
        if not self.config_manager:
            return [TextContent(type="text", text="Configuration manager not available")]
        
        try:
            # Get both configuration and validation status
            config_results = self.config_manager.check_and_configure_all_daemons()
            validation_results = self.config_manager.validate_daemon_configs()
            
            status = {
                "configuration_status": config_results,
                "validation_status": validation_results
            }
            
            response = "Daemon configuration status:\n"
            response += json.dumps(status, indent=2)
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting config status: {str(e)}")]
    
    async def _handle_ipfs_add(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Handle IPFS add requests."""
        if not self.ipfs_kit_instance:
            return [TextContent(type="text", text="IPFS kit not available")]
        
        content = arguments.get("content", "")
        
        try:
            result = self.ipfs_kit_instance.add_json({"content": content})
            
            response = f"IPFS add result:\n"
            response += json.dumps(result, indent=2)
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error adding to IPFS: {str(e)}")]
    
    async def _handle_ipfs_get(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Handle IPFS get requests."""
        if not self.ipfs_kit_instance:
            return [TextContent(type="text", text="IPFS kit not available")]
        
        cid = arguments.get("cid", "")
        
        try:
            result = self.ipfs_kit_instance.get_json(cid)
            
            response = f"IPFS get result:\n"
            response += json.dumps(result, indent=2)
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting from IPFS: {str(e)}")]
    
    async def run_server(self):
        """Run the MCP server."""
        if not MCP_AVAILABLE:
            logger.error("❌ MCP not available - cannot run server")
            return
        
        if not self.server:
            logger.error("❌ Server not initialized")
            return
        
        logger.info("🚀 Starting Enhanced MCP Server with comprehensive configuration management...")
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="enhanced-ipfs-kit-server",
                    server_version="1.0.0",
                    capabilities={}
                )
            )
    
    def run_standalone(self):
        """Run in standalone mode for testing."""
        logger.info("🔧 Running in standalone mode...")
        
        if not self.config_manager:
            logger.error("❌ Configuration manager not available")
            return
        
        # Test all configuration functionality
        logger.info("📋 Testing configuration management...")
        
        # Test configuration
        config_results = self.config_manager.check_and_configure_all_daemons()
        logger.info(f"✅ Configuration results: {json.dumps(config_results, indent=2)}")
        
        # Test validation
        validation_results = self.config_manager.validate_daemon_configs()
        logger.info(f"✅ Validation results: {json.dumps(validation_results, indent=2)}")
        
        # Test configuration updates
        if config_results.get("overall_success", False):
            logger.info("🔧 Testing configuration updates...")
            
            # Test S3 config update
            s3_update = self.config_manager.update_daemon_config("s3", {"host_base": "s3.example.com"})
            logger.info(f"✅ S3 update result: {json.dumps(s3_update, indent=2)}")
            
            # Test HuggingFace config update
            hf_update = self.config_manager.update_daemon_config("huggingface", {"offline": True})
            logger.info(f"✅ HuggingFace update result: {json.dumps(hf_update, indent=2)}")
        
        logger.info("🎉 Standalone testing completed successfully!")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced MCP Server with comprehensive configuration management")
    parser.add_argument("--standalone", action="store_true", help="Run in standalone mode for testing")
    args = parser.parse_args()
    
    try:
        server = EnhancedMCPServerWithFullConfig()
        
        if args.standalone:
            server.run_standalone()
        else:
            asyncio.run(server.run_server())
            
    except KeyboardInterrupt:
        logger.info("👋 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
