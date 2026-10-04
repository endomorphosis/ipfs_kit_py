#!/usr/bin/env python3
"""
Enhanced MCP Server with Proper Daemon Configuration Management

This version ensures all daemons are properly configured before startup.
"""

import os
import sys
import json
import logging
import anyio
import signal
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("enhanced_mcp_server_with_config.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhanced-mcp-with-config")

class EnhancedMCPServerWithConfig:
    """Enhanced MCP Server with proper daemon configuration management."""
    
    def __init__(self):
        """Initialize the enhanced MCP server with configuration management."""
        self.initialized = False
        self.ipfs_kit = None
        self.daemon_config_manager = None
        self.config_status = {}
        self.startup_errors = []
        
    async def initialize_with_config(self):
        """Initialize the server with proper daemon configuration."""
        logger.info("🚀 Starting enhanced MCP server with configuration management...")
        
        try:
            # Step 1: Initialize configuration manager
            logger.info("📋 Initializing daemon configuration manager...")
            from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
            self.daemon_config_manager = DaemonConfigManager()
            
            # Step 2: Check and configure all daemons
            logger.info("⚙️ Checking and configuring all daemons...")
            config_results = self.daemon_config_manager.check_and_configure_all_daemons()
            self.config_status = config_results
            
            # Log configuration results
            if config_results.get("overall_success", False):
                logger.info("✅ All daemons configured successfully")
                logger.info(f"📊 Configuration summary:\n{config_results.get('summary', 'No summary available')}")
            else:
                logger.warning("⚠️ Some daemon configurations failed")
                logger.warning(f"📊 Configuration summary:\n{config_results.get('summary', 'No summary available')}")
            
            # Step 3: Import and initialize ipfs_kit
            logger.info("📦 Importing ipfs_kit...")
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            
            # Create ipfs_kit instance with master role
            logger.info("🔧 Creating ipfs_kit instance...")
            metadata = {
                "role": "master",
                "auto_start_daemons": True,
                "ipfs_path": self.daemon_config_manager.ipfs_path,
                "lotus_path": self.daemon_config_manager.lotus_path
            }
            
            self.ipfs_kit = ipfs_kit(metadata=metadata)
            logger.info(f"✅ ipfs_kit instance created with role: {self.ipfs_kit.role}")
            
            # Step 4: Validate daemon configurations
            logger.info("🔍 Validating daemon configurations...")
            validation_results = self.daemon_config_manager.validate_daemon_configs()
            
            if validation_results.get("overall_valid", False):
                logger.info("✅ All daemon configurations are valid")
            else:
                logger.warning("⚠️ Some daemon configurations are invalid")
                for daemon, result in validation_results.items():
                    if daemon != "overall_valid" and not result.get("valid", False):
                        logger.error(f"❌ {daemon.upper()} validation failed: {result.get('error', 'Unknown error')}")
            
            # Step 5: Check daemon status
            logger.info("📊 Checking daemon status...")
            daemon_status = self.check_daemon_status()
            
            self.initialized = True
            logger.info("🎉 Enhanced MCP server initialized successfully!")
            
            return {
                "success": True,
                "config_results": config_results,
                "validation_results": validation_results,
                "daemon_status": daemon_status
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize server: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            self.startup_errors.append(str(e))
            return {"success": False, "error": str(e)}
    
    def check_daemon_status(self) -> Dict[str, Any]:
        """Check the status of all daemons."""
        logger.info("🔍 Checking daemon status...")
        
        status = {}
        
        # Check IPFS daemon
        if hasattr(self.ipfs_kit, 'ipfs') and self.ipfs_kit.ipfs:
            try:
                # Try to get IPFS version as a health check
                ipfs_info = self.ipfs_kit.ipfs.version()
                status["ipfs"] = {
                    "running": True,
                    "version": ipfs_info.get("Version", "unknown"),
                    "api_available": True
                }
                logger.info("✅ IPFS daemon is running")
            except Exception as e:
                status["ipfs"] = {
                    "running": False,
                    "error": str(e),
                    "api_available": False
                }
                logger.warning(f"⚠️ IPFS daemon check failed: {e}")
        else:
            status["ipfs"] = {"running": False, "error": "IPFS not initialized"}
        
        # Check Lotus daemon
        if hasattr(self.ipfs_kit, 'lotus_kit') and self.ipfs_kit.lotus_kit:
            try:
                lotus_status = self.ipfs_kit.lotus_kit.daemon_status()
                status["lotus"] = {
                    "running": lotus_status.get("process_running", False),
                    "pid": lotus_status.get("pid"),
                    "api_available": lotus_status.get("api_available", False)
                }
                if status["lotus"]["running"]:
                    logger.info(f"✅ Lotus daemon is running (PID: {status['lotus']['pid']})")
                else:
                    logger.warning("⚠️ Lotus daemon is not running")
            except Exception as e:
                status["lotus"] = {
                    "running": False,
                    "error": str(e),
                    "api_available": False
                }
                logger.warning(f"⚠️ Lotus daemon check failed: {e}")
        else:
            status["lotus"] = {"running": False, "error": "Lotus not initialized"}
        
        # Check Lassie (if available)
        if hasattr(self.ipfs_kit, 'lassie_kit') and self.ipfs_kit.lassie_kit:
            try:
                # Lassie is typically used on-demand, so just check if it's available
                status["lassie"] = {
                    "available": True,
                    "path": getattr(self.ipfs_kit.lassie_kit, 'lassie_path', None)
                }
                logger.info("✅ Lassie is available")
            except Exception as e:
                status["lassie"] = {
                    "available": False,
                    "error": str(e)
                }
                logger.warning(f"⚠️ Lassie check failed: {e}")
        else:
            status["lassie"] = {"available": False, "error": "Lassie not initialized"}
        
        return status
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the server."""
        return {
            "server_initialized": self.initialized,
            "startup_errors": self.startup_errors,
            "config_status": self.config_status,
            "daemon_status": self.check_daemon_status() if self.initialized else {},
            "timestamp": datetime.now().isoformat()
        }
    
    def get_mcp_tools_status(self) -> Dict[str, Any]:
        """Get status of MCP tools."""
        if not self.initialized or not self.ipfs_kit:
            return {"error": "Server not initialized"}
        
        tools_status = {}
        
        # Check IPFS tools
        if hasattr(self.ipfs_kit, 'ipfs') and self.ipfs_kit.ipfs:
            tools_status["ipfs_add"] = {"available": True}
            tools_status["ipfs_cat"] = {"available": True}
            tools_status["ipfs_pin"] = {"available": True}
            tools_status["ipfs_get"] = {"available": True}
        else:
            tools_status["ipfs_tools"] = {"available": False}
        
        # Check Lotus tools
        if hasattr(self.ipfs_kit, 'lotus_kit') and self.ipfs_kit.lotus_kit:
            tools_status["lotus_wallet"] = {"available": True}
            tools_status["lotus_chain"] = {"available": True}
        else:
            tools_status["lotus_tools"] = {"available": False}
        
        # Check Lassie tools
        if hasattr(self.ipfs_kit, 'lassie_kit') and self.ipfs_kit.lassie_kit:
            tools_status["lassie_retrieve"] = {"available": True}
        else:
            tools_status["lassie_tools"] = {"available": False}
        
        return tools_status


def main():
    """Main entry point for the enhanced MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enhanced MCP Server with Daemon Configuration Management"
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Check daemon configurations only"
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate existing daemon configurations"
    )
    parser.add_argument(
        "--daemon",
        choices=["ipfs", "lotus", "lassie", "all"],
        default="all",
        help="Specific daemon to configure"
    )
    
    args = parser.parse_args()
    
    # Handle config-only operations
    if args.check_config or args.validate_config:
        from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
        
        manager = DaemonConfigManager()
        
        if args.validate_config:
            logger.info("🔍 Validating daemon configurations...")
            results = manager.validate_daemon_configs()
        else:
            logger.info("⚙️ Checking and configuring daemons...")
            results = manager.check_and_configure_all_daemons()
        
        print(json.dumps(results, indent=2))
        return 0 if results.get("overall_valid" if args.validate_config else "overall_success", False) else 1
    
    # Initialize and start the server
    async def run_server():
        server = EnhancedMCPServerWithConfig()
        
        # Handle graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}, shutting down...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Initialize the server
        init_result = await server.initialize_with_config()
        
        if not init_result.get("success", False):
            logger.error("❌ Failed to initialize server")
            return 1
        
        logger.info("🚀 Enhanced MCP server is running!")
        logger.info("💡 Press Ctrl+C to stop the server")
        
        # Print status report
        health_status = server.get_health_status()
        tools_status = server.get_mcp_tools_status()
        
        print("\n" + "="*60)
        print("🎯 SERVER STATUS REPORT")
        print("="*60)
        print(f"Server Initialized: {health_status['server_initialized']}")
        print(f"Startup Errors: {len(health_status['startup_errors'])}")
        print(f"Config Status: {health_status['config_status'].get('overall_success', 'Unknown')}")
        print(f"Daemon Status: {len([d for d in health_status['daemon_status'].values() if d.get('running', False) or d.get('available', False)])} daemons active")
        print(f"Available Tools: {len([t for t in tools_status.values() if t.get('available', False)])}")
        print("="*60)
        
        # Keep the server running
        try:
            while True:
                await anyio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Server stopped by user")
            return 0
    
    # Run the server
    try:
        return anyio.run(run_server)
    except Exception as e:
        logger.error(f"❌ Server failed to start: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
