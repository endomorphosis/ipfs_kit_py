#!/usr/bin/env python3
"""
Unified MCP server runner with advanced file watching.

This script provides a comprehensive solution for running the MCP server with:
- Automatic file watching and hot-reloading
- Syntax validation before restart
- Dependency analysis for smarter reloading
- Real-time dashboard for status monitoring
- Detailed error reporting with fix suggestions
"""

import os
import sys
import time
import threading
import logging
import argparse
import importlib
import traceback
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger("mcp_unified")

# Check dependencies
missing_deps = []
try:
    import watchdog
except ImportError:
    missing_deps.append("watchdog")

try:
    from fastapi import FastAPI
    import uvicorn
except ImportError:
    missing_deps.append("fastapi and uvicorn")

# Exit if missing required dependencies
if missing_deps:
    logger.error("Missing required dependencies: %s", ", ".join(missing_deps))
    logger.error("Install them with: pip install %s", " ".join(missing_deps))
    sys.exit(1)

# Import file watcher and dashboard
try:
    from ipfs_kit_py.mcp.utils.file_watcher import MCPFileWatcher
    try:
        from ipfs_kit_py.mcp.utils.dashboard import MCPDashboard
        HAS_DASHBOARD = True
    except ImportError:
        logger.warning("Dashboard module not found, running without visual dashboard")
        HAS_DASHBOARD = False
except ImportError:
    logger.error("Could not import the MCP file watcher. Make sure the codebase is set up correctly.")
    sys.exit(1)

def get_server_class(server_type: str):
    """
    Get the appropriate server class based on server type.
    
    Args:
        server_type: Type of server ('sync' or 'anyio')
        
    Returns:
        Server class
    """
    if server_type == 'sync':
        # Import synchronous server
        from ipfs_kit_py.mcp.server import MCPServer
        return MCPServer
    elif server_type == 'anyio':
        # Import AnyIO server
        from ipfs_kit_py.mcp.server_anyio import MCPServer
        return MCPServer
    else:
        raise ValueError(f"Invalid server type: {server_type}")

class MCPServerRunner:
    """Advanced runner for MCP server with file watching and dashboard."""
    
    def __init__(
        self,
        server_type: str = 'anyio',
        debug_mode: bool = False,
        log_level: str = "INFO",
        persistence_path: Optional[str] = None,
        isolation_mode: bool = False,
        skip_daemon: bool = False,
        config: Dict[str, Any] = None,
        host: str = "127.0.0.1",
        port: int = 8000,
        api_prefix: str = "/api/v0/mcp",
        backend: str = "asyncio",
        watch_dirs: Optional[List[str]] = None,
        ignore_dirs: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
        dashboard_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the server runner.
        
        Args:
            server_type: Type of server ('sync' or 'anyio')
            debug_mode: Enable debug mode
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            persistence_path: Path for persistence files
            isolation_mode: Run in isolated mode
            skip_daemon: Skip daemon initialization
            config: Server configuration
            host: Host to bind to
            port: Port to listen on
            api_prefix: API prefix
            backend: AnyIO backend ('asyncio' or 'trio')
            watch_dirs: Additional directories to watch
            ignore_dirs: Directories to ignore
            ignore_patterns: File patterns to ignore
            dashboard_config: Configuration for the dashboard
        """
        self.server_type = server_type
        self.debug_mode = debug_mode
        self.log_level = log_level
        self.persistence_path = persistence_path
        self.isolation_mode = isolation_mode
        self.skip_daemon = skip_daemon
        self.config = config or {}
        self.host = host
        self.port = port
        self.api_prefix = api_prefix
        self.backend = backend
        self.watch_dirs = watch_dirs or []
        self.ignore_dirs = ignore_dirs or []
        self.ignore_patterns = ignore_patterns or []
        self.dashboard_config = dashboard_config or {}
        
        # Set default dashboard config values
        self.use_dashboard = self.dashboard_config.get('use_dashboard', True) and HAS_DASHBOARD
        self.dashboard_interval = self.dashboard_config.get('update_interval', 1.0)
        
        # Server and file watcher
        self.server = None
        self.app = None
        self.file_watcher = None
        self.server_thread = None
        self.shutdown_event = threading.Event()
        
        # Get server class based on server type
        self.server_class = get_server_class(server_type)
        
        # Initialize server arguments
        self.server_args = {
            'debug_mode': debug_mode,
            'log_level': log_level,
            'persistence_path': persistence_path,
            'isolation_mode': isolation_mode,
            'skip_daemon': skip_daemon,
            'config': config,
        }
        
        # For AnyIO server, make sure skip_daemon is available
        if server_type == 'anyio' and 'skip_daemon' not in self.server_args:
            self.server_args['skip_daemon'] = skip_daemon
            
        logger.info(f"Initialized MCPServerRunner with {server_type} server")
        
        # Print dashboard status
        if self.use_dashboard:
            logger.info("Dashboard enabled for real-time monitoring")
        else:
            logger.info("Running without dashboard (use --enable-dashboard to enable)")
    
    def start(self):
        """Start the server and file watcher."""
        # Print banner
        self._print_banner()
        
        # Create FastAPI app
        self.app = FastAPI(
            title="IPFS MCP Server",
            description="Model-Controller-Persistence Server for IPFS Kit",
            version="0.1.0"
        )
        
        # Create server instance
        logger.info(f"Creating {self.server_type} server instance")
        self.server = self.server_class(**self.server_args)
        
        # Register server with app
        logger.info(f"Registering server with app at prefix: {self.api_prefix}")
        self.server.register_with_app(self.app, prefix=self.api_prefix)
        
        # Get project root directory (parent of current file)
        project_root = os.path.abspath(os.path.dirname(__file__))
        
        # Initialize file watcher
        logger.info(f"Creating file watcher with project root: {project_root}")
        self.file_watcher = MCPFileWatcher(
            project_root=project_root,
            additional_dirs=self.watch_dirs,
            ignore_dirs=self.ignore_dirs,
            ignore_patterns=self.ignore_patterns,
            server_class=self.server_class,
            server_instance=self.server,
            server_args=self.server_args,
            use_dashboard=self.use_dashboard
        )
        
        # Configure dashboard if enabled
        if self.use_dashboard and hasattr(self.file_watcher, 'dashboard') and self.file_watcher.dashboard:
            # Set custom update interval if specified
            if self.dashboard_interval != 1.0:
                self.file_watcher.dashboard.update_interval = self.dashboard_interval
        
        # Start file watcher
        logger.info("Starting file watcher")
        self.file_watcher.start()
        
        # Create Uvicorn config
        logger.info(f"Starting server at http://{self.host}:{self.port}")
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level=self.log_level.lower()
        )
        server = uvicorn.Server(config)
        
        # Start server in main thread (will block until server stops)
        logger.info("Starting Uvicorn server")
        os.environ["ANYIO_BACKEND"] = self.backend
        try:
            server.run()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down")
        finally:
            # Clean up
            self._cleanup()
    
    def _print_banner(self):
        """Print a fancy banner for the unified server."""
        banner = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                              MCP UNIFIED SERVER                           ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Server Type: {self.server_type.ljust(11)}    Host: {self.host.ljust(12)}    Port: {str(self.port).ljust(6)}  ║
║  Debug Mode: {str(self.debug_mode).ljust(11)}    API Prefix: {self.api_prefix.ljust(22)} ║
║  Dashboard:  {str(self.use_dashboard).ljust(11)}    Backend: {self.backend.ljust(26)} ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
        print(banner)
    
    def _cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources")
        
        # Stop file watcher
        if self.file_watcher:
            logger.info("Stopping file watcher")
            self.file_watcher.stop()
            self.file_watcher = None
        
        # Shut down server
        if self.server:
            logger.info("Shutting down server")
            
            # Determine correct shutdown method
            if hasattr(self.server, 'sync_shutdown'):
                # AnyIO server
                self.server.sync_shutdown()
            elif hasattr(self.server, 'shutdown'):
                # Sync server
                self.server.shutdown()
            else:
                logger.warning("No suitable shutdown method found for server")
                
            self.server = None
        
        logger.info("Cleanup complete")

def main():
    """Run the unified MCP server with advanced file watching."""
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Unified MCP Server with advanced file watching",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Server configuration
    server_group = parser.add_argument_group("Server Configuration")
    server_group.add_argument("--server-type", choices=["sync", "anyio"], default="anyio",
                        help="Server type (sync or anyio)")
    server_group.add_argument("--debug", action="store_true", help="Enable debug mode")
    server_group.add_argument("--isolation", action="store_true", help="Enable isolation mode")
    server_group.add_argument("--log-level", default="INFO", 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Logging level")
    server_group.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    server_group.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    server_group.add_argument("--persistence-path", help="Path for persistence files")
    server_group.add_argument("--api-prefix", default="/api/v0/mcp", help="Prefix for API endpoints")
    server_group.add_argument("--backend", default="asyncio", choices=["asyncio", "trio"], 
                        help="AnyIO backend to use")
    server_group.add_argument("--skip-daemon", action="store_true", 
                        help="Skip IPFS daemon initialization (run in daemon-less mode)")
    
    # File watcher configuration
    watcher_group = parser.add_argument_group("File Watcher Configuration")
    watcher_group.add_argument("--watch-dir", action="append", dest="watch_dirs", default=[],
                        help="Additional directories to watch (can be specified multiple times)")
    watcher_group.add_argument("--ignore-dir", action="append", dest="ignore_dirs", default=[],
                        help="Directories to ignore (can be specified multiple times)")
    watcher_group.add_argument("--ignore-pattern", action="append", dest="ignore_patterns", default=[],
                        help="File patterns to ignore (can be specified multiple times)")
    
    # Dashboard configuration
    dashboard_group = parser.add_argument_group("Dashboard Configuration")
    dashboard_group.add_argument("--no-dashboard", action="store_true", 
                        help="Disable the real-time dashboard")
    dashboard_group.add_argument("--dashboard-interval", type=float, default=1.0,
                        help="Dashboard update interval in seconds")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Initialize dashboard configuration
    dashboard_config = {
        'use_dashboard': not args.no_dashboard,
        'update_interval': args.dashboard_interval
    }
    
    # Create server runner
    runner = MCPServerRunner(
        server_type=args.server_type,
        debug_mode=args.debug,
        log_level=args.log_level,
        persistence_path=args.persistence_path,
        isolation_mode=args.isolation,
        skip_daemon=args.skip_daemon,
        host=args.host,
        port=args.port,
        api_prefix=args.api_prefix,
        backend=args.backend,
        watch_dirs=args.watch_dirs,
        ignore_dirs=args.ignore_dirs,
        ignore_patterns=args.ignore_patterns,
        dashboard_config=dashboard_config
    )
    
    # Start server
    try:
        runner.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down")
    except Exception as e:
        logger.error(f"Error running server: {e}")
        logger.error(traceback.format_exc())
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())