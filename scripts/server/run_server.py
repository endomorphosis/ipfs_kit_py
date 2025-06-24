#!/usr/bin/env python3
"""
Consolidated MCP Server Runner for IPFS Kit

This script consolidates functionality from all previous MCP server runners:
- run_mcp_server.py
- run_mcp_server_anyio.py
- run_mcp_server_fixed.py
- run_mcp_server_real.py
- run_mcp_server_with_storage.py
- run_mcp_server_all_backends_fixed.py
- run_enhanced_mcp_server.py
- run_custom_mcp_server.py
- start_mcp_server.py
- start_mcp_anyio_server.sh
- start_mcp_server.sh
- start_mcp_real_apis.sh
- start_mcp_server_with_webrtc.sh

It provides a comprehensive solution for running any type of MCP server.
"""

import os
import sys
import json
import signal
import logging
import argparse
import threading
import traceback
from typing import Dict, Any, Optional, List, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("mcp_server_runner")

# Check dependencies
missing_deps = []
try:
    import fastapi
    from fastapi import FastAPI
except ImportError:
    missing_deps.append("fastapi")

try:
    import uvicorn
except ImportError:
    missing_deps.append("uvicorn")

try:
    import watchdog
except ImportError:
    missing_deps.append("watchdog")

# Exit if missing required dependencies
if missing_deps:
    logger.error("Missing required dependencies: %s", ", ".join(missing_deps))
    logger.error("Install them with: pip install %s", " ".join(missing_deps))
    sys.exit(1)

# Try to import file watcher and dashboard if available
try:
    from ipfs_kit_py.mcp.utils.file_watcher import MCPFileWatcher
    HAS_FILE_WATCHER = True

    try:
        from ipfs_kit_py.mcp.utils.dashboard import MCPDashboard
        HAS_DASHBOARD = True
    except ImportError:
        logger.warning("Dashboard module not found, running without visual dashboard")
        HAS_DASHBOARD = False
except ImportError:
    logger.warning("File watcher module not found, hot reloading will be disabled")
    HAS_FILE_WATCHER = False
    HAS_DASHBOARD = False

class ServerTypes:
    """Constants for supported server types."""
    SYNC = "sync"
    ANYIO = "anyio"
    REAL = "real"
    STORAGE = "storage"
    ENHANCED = "enhanced"
    FIXED = "fixed"
    WEBRTC = "webrtc"

    @classmethod
    def get_all(cls):
        """Get all supported server types."""
        return [
            cls.SYNC, cls.ANYIO, cls.REAL, cls.STORAGE,
            cls.ENHANCED, cls.FIXED, cls.WEBRTC
        ]

def get_server_class(server_type: str):
    """
    Get the appropriate server class based on server type.

    Args:
        server_type: Type of server (sync, anyio, real, storage, etc.)

    Returns:
        Server class or None if not found
    """
    try:
        if server_type == ServerTypes.SYNC:
            # Import synchronous server
            from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
            return MCPServer
        elif server_type == ServerTypes.ANYIO:
            # Import AnyIO server
            from ipfs_kit_py.mcp.server_anyio import MCPServer
            return MCPServer
        elif server_type == ServerTypes.REAL:
            # Import real server
            from ipfs_kit_py.mcp.server_real import MCPServer
            return MCPServer
        elif server_type == ServerTypes.STORAGE:
            # Import server with storage
            from ipfs_kit_py.mcp.server_storage import MCPServer
            return MCPServer
        elif server_type == ServerTypes.ENHANCED:
            # Import enhanced server
            from ipfs_kit_py.mcp.server_enhanced import MCPServer
            return MCPServer
        elif server_type == ServerTypes.FIXED:
            # Import fixed server
            from ipfs_kit_py.mcp.server_fixed import MCPServer
            return MCPServer
        elif server_type == ServerTypes.WEBRTC:
            # Import WebRTC server
            from ipfs_kit_py.mcp.server_webrtc import MCPServer
            return MCPServer
        else:
            raise ValueError(f"Invalid server type: {server_type}")
    except ImportError as e:
        logger.error(f"Failed to import server type '{server_type}': {e}")
        return None

class MCPServerRunner:
    """Consolidated runner for all MCP server types."""

    def __init__(
        self,
        server_type: str = ServerTypes.ANYIO,
        debug_mode: bool = False,
        log_level: str = "INFO",
        persistence_path: Optional[str] = None,
        isolation_mode: bool = False,
        skip_daemon: bool = False,
        config: Dict[str, Any] = None,
        host: str = "127.0.0.1",
        port: int = 8000,
        api_prefix: str = "/api/v0",
        backend: str = "asyncio",
        watch_mode: bool = False,
        watch_dirs: Optional[List[str]] = None,
        ignore_dirs: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
        dashboard: bool = False,
        dashboard_config: Optional[Dict[str, Any]] = None,
        storage_config: Optional[Dict[str, Any]] = None,
        auto_start_daemons: bool = False,
        daemon_health_monitor: bool = False,
        webrtc_enabled: bool = False,
        webrtc_config: Optional[Dict[str, Any]] = None,
        metrics_enabled: bool = False,
        metrics_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the server runner with comprehensive options.

        Args:
            server_type: Type of server (sync, anyio, real, storage, etc.)
            debug_mode: Enable debug mode
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            persistence_path: Path for persistence files
            isolation_mode: Run in isolated mode
            skip_daemon: Skip daemon initialization
            config: Server configuration
            host: Host to bind to
            port: Port to listen on
            api_prefix: API prefix
            backend: AnyIO backend (asyncio or trio)
            watch_mode: Enable file watching and hot reload
            watch_dirs: Additional directories to watch
            ignore_dirs: Directories to ignore
            ignore_patterns: File patterns to ignore
            dashboard: Enable visual dashboard
            dashboard_config: Configuration for the dashboard
            storage_config: Configuration for storage backend
            auto_start_daemons: Automatically start required daemons
            daemon_health_monitor: Enable daemon health monitoring
            webrtc_enabled: Enable WebRTC functionality
            webrtc_config: Configuration for WebRTC
            metrics_enabled: Enable metrics collection
            metrics_config: Configuration for metrics
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
        self.watch_mode = watch_mode and HAS_FILE_WATCHER
        self.watch_dirs = watch_dirs or []
        self.ignore_dirs = ignore_dirs or []
        self.ignore_patterns = ignore_patterns or []
        self.dashboard_enabled = dashboard and HAS_DASHBOARD
        self.dashboard_config = dashboard_config or {}
        self.storage_config = storage_config or {}
        self.auto_start_daemons = auto_start_daemons
        self.daemon_health_monitor = daemon_health_monitor
        self.webrtc_enabled = webrtc_enabled
        self.webrtc_config = webrtc_config or {}
        self.metrics_enabled = metrics_enabled
        self.metrics_config = metrics_config or {}

        # Server and app
        self.server = None
        self.app = None
        self.file_watcher = None
        self.shutdown_event = threading.Event()

        # Get server class based on server type
        self.server_class = get_server_class(server_type)
        if not self.server_class:
            raise ValueError(f"Server type '{server_type}' is not available")

        # Initialize server arguments
        self.server_args = {
            'debug_mode': debug_mode,
            'log_level': log_level,
            'isolation_mode': isolation_mode,
            'skip_daemon': skip_daemon,
            'config': config
        }

        # Add persistence path if provided
        if persistence_path:
            self.server_args['persistence_path'] = persistence_path

        # Add storage configuration if required
        if server_type == ServerTypes.STORAGE and self.storage_config:
            self.server_args['storage_config'] = self.storage_config

        # Add daemon configuration
        if auto_start_daemons:
            self.server_args['auto_start_daemons'] = True

        if daemon_health_monitor:
            self.server_args['daemon_health_monitor'] = True

        # Add WebRTC configuration if enabled
        if webrtc_enabled and self.webrtc_config:
            self.server_args['webrtc_enabled'] = True
            self.server_args['webrtc_config'] = self.webrtc_config

        # Add metrics configuration if enabled
        if metrics_enabled and self.metrics_config:
            self.server_args['metrics_enabled'] = True
            self.server_args['metrics_config'] = self.metrics_config

        logger.info(f"Initialized MCPServerRunner with {server_type} server")

        # Print dashboard status if relevant
        if self.dashboard_enabled:
            logger.info("Dashboard enabled for real-time monitoring")

    def start(self):
        """Start the server with all configured options."""
        # Print banner
        self._print_banner()

        # Create FastAPI app
        self.app = FastAPI(
            title="IPFS MCP Server",
            description="Model-Controller-Persistence Server for IPFS Kit",
            version="1.0.0"
        )

        # Create server instance
        logger.info(f"Creating {self.server_type} server instance")
        try:
            self.server = self.server_class(**self.server_args)
        except Exception as e:
            logger.error(f"Failed to create server: {e}")
            logger.error(traceback.format_exc())
            return False

        # Register server with app
        logger.info(f"Registering server with app at prefix: {self.api_prefix}")
        try:
            if hasattr(self.server, 'register_with_app'):
                self.server.register_with_app(self.app, prefix=self.api_prefix)
            else:
                logger.error("Server instance does not have register_with_app method")
                return False
        except Exception as e:
            logger.error(f"Failed to register server with app: {e}")
            logger.error(traceback.format_exc())
            return False

        # Add root endpoint if it doesn't exist
        if '/' not in [route.path for route in self.app.routes]:
            @self.app.get("/")
            async def root():
                """Root endpoint with server information."""
                # Get daemon status information if available
                daemon_info = {}
                if hasattr(self.server, 'ipfs_kit') and hasattr(self.server.ipfs_kit, 'check_daemon_status'):
                    try:
                        daemon_info["ipfs_daemon_running"] = self.server.ipfs_kit.check_daemon_status('ipfs').get("running", False)
                    except Exception:
                        daemon_info["ipfs_daemon_running"] = False

                if hasattr(self.server, 'ipfs_kit') and hasattr(self.server.ipfs_kit, 'auto_start_daemons'):
                    daemon_info["auto_start_daemons"] = self.server.ipfs_kit.auto_start_daemons

                if self.daemon_health_monitor and hasattr(self.server, 'ipfs_kit') and hasattr(self.server.ipfs_kit, 'is_daemon_health_monitor_running'):
                    daemon_info["daemon_monitor_running"] = self.server.ipfs_kit.is_daemon_health_monitor_running()

                # List available controllers if any
                controllers = []
                if hasattr(self.server, 'controllers'):
                    controllers = list(self.server.controllers.keys())

                return {
                    "message": "MCP Server is running",
                    "server_type": self.server_type,
                    "debug_mode": self.debug_mode,
                    "isolation_mode": self.isolation_mode,
                    "controllers": controllers,
                    "daemon_status": daemon_info,
                    "documentation": "/docs"
                }

        # Set up file watcher if enabled
        if self.watch_mode:
            self._setup_file_watcher()

        # Add shutdown event handler
        @self.app.on_event("shutdown")
        async def shutdown_event():
            """Handle FastAPI shutdown event."""
            if self.server:
                logger.info("FastAPI shutdown event received, cleaning up server")
                self._cleanup_server()

        # Register signal handlers for graceful shutdown
        self._setup_signal_handlers()

        # Start the server using uvicorn
        logger.info(f"Starting server at http://{self.host}:{self.port}")
        os.environ["ANYIO_BACKEND"] = self.backend

        # Create uvicorn config
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level=self.log_level.lower()
        )
        server = uvicorn.Server(config)

        # Start server (will block until server stops)
        try:
            server.run()
            return True
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down")
            self._cleanup()
            return True
        except Exception as e:
            logger.error(f"Error running server: {e}")
            logger.error(traceback.format_exc())
            self._cleanup()
            return False

    def _setup_file_watcher(self):
        """Set up file watcher for hot reloading."""
        if not HAS_FILE_WATCHER:
            logger.warning("File watcher not available, running without hot reloading")
            return

        logger.info("Setting up file watcher for hot reloading")

        # Get project root directory
        project_root = os.path.abspath(os.path.dirname(__file__))

        # Initialize file watcher
        try:
            self.file_watcher = MCPFileWatcher(
                project_root=project_root,
                additional_dirs=self.watch_dirs,
                ignore_dirs=self.ignore_dirs,
                ignore_patterns=self.ignore_patterns,
                server_class=self.server_class,
                server_instance=self.server,
                server_args=self.server_args,
                use_dashboard=self.dashboard_enabled
            )

            # Configure dashboard if enabled
            if self.dashboard_enabled and hasattr(self.file_watcher, 'dashboard') and self.file_watcher.dashboard:
                dashboard_interval = self.dashboard_config.get('update_interval', 1.0)
                if dashboard_interval != 1.0:
                    self.file_watcher.dashboard.update_interval = dashboard_interval

            # Start file watcher
            self.file_watcher.start()
            logger.info("File watcher started successfully")
        except Exception as e:
            logger.error(f"Failed to set up file watcher: {e}")
            logger.error(traceback.format_exc())

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            """Handle termination signals."""
            logger.info(f"Received signal {sig}, shutting down...")
            self._cleanup()
            # Let the process terminate naturally after cleanup
            sys.exit(0)

        # Register handlers for SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _cleanup_server(self):
        """Clean up server resources."""
        if self.server:
            logger.info("Shutting down server")

            # Determine correct shutdown method
            try:
                if hasattr(self.server, 'sync_shutdown'):
                    # AnyIO server
                    self.server.sync_shutdown()
                elif hasattr(self.server, 'shutdown'):
                    # Sync server
                    self.server.shutdown()
                else:
                    logger.warning("No suitable shutdown method found for server")
            except Exception as e:
                logger.error(f"Error during server shutdown: {e}")

            self.server = None

    def _cleanup(self):
        """Clean up all resources."""
        logger.info("Cleaning up resources")

        # Stop file watcher
        if self.file_watcher:
            logger.info("Stopping file watcher")
            try:
                self.file_watcher.stop()
            except Exception as e:
                logger.error(f"Error stopping file watcher: {e}")

            self.file_watcher = None

        # Shut down server
        self._cleanup_server()

        logger.info("Cleanup complete")

    def _print_banner(self):
        """Print a banner for the server."""
        banner = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                       IPFS KIT MCP SERVER RUNNER                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Server Type: {self.server_type.ljust(11)}    Host: {self.host.ljust(12)}    Port: {str(self.port).ljust(6)}  ║
║  Debug Mode: {str(self.debug_mode).ljust(11)}    API Prefix: {self.api_prefix.ljust(22)} ║
║  Dashboard:  {str(self.dashboard_enabled).ljust(11)}    Watch Mode: {str(self.watch_mode).ljust(22)} ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
        print(banner)


def main():
    """Run the consolidated MCP server with command-line arguments."""
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Consolidated MCP Server Runner for IPFS Kit",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Server configuration
    server_group = parser.add_argument_group("Server Configuration")
    server_group.add_argument("--server-type", choices=ServerTypes.get_all(), default=ServerTypes.ANYIO,
                        help="Server type")
    server_group.add_argument("--debug", action="store_true", help="Enable debug mode")
    server_group.add_argument("--isolation", action="store_true", help="Enable isolation mode")
    server_group.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Logging level")
    server_group.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    server_group.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    server_group.add_argument("--persistence-path", help="Path for persistence files")
    server_group.add_argument("--api-prefix", default="/api/v0", help="Prefix for API endpoints")
    server_group.add_argument("--backend", default="asyncio", choices=["asyncio", "trio"],
                        help="AnyIO backend to use")
    server_group.add_argument("--skip-daemon", action="store_true",
                        help="Skip IPFS daemon initialization")
    server_group.add_argument("--config", help="Path to JSON configuration file")

    # Daemon configuration
    daemon_group = parser.add_argument_group("Daemon Configuration")
    daemon_group.add_argument("--auto-start-daemons", action="store_true",
                        help="Automatically start required daemons")
    daemon_group.add_argument("--daemon-health-monitor", action="store_true",
                        help="Enable daemon health monitoring")

    # File watcher configuration
    watcher_group = parser.add_argument_group("File Watcher Configuration")
    watcher_group.add_argument("--watch-mode", action="store_true",
                        help="Enable file watching and hot reload")
    watcher_group.add_argument("--watch-dir", action="append", dest="watch_dirs", default=[],
                        help="Additional directories to watch (can be specified multiple times)")
    watcher_group.add_argument("--ignore-dir", action="append", dest="ignore_dirs", default=[],
                        help="Directories to ignore (can be specified multiple times)")
    watcher_group.add_argument("--ignore-pattern", action="append", dest="ignore_patterns", default=[],
                        help="File patterns to ignore (can be specified multiple times)")

    # Dashboard configuration
    dashboard_group = parser.add_argument_group("Dashboard Configuration")
    dashboard_group.add_argument("--dashboard", action="store_true",
                        help="Enable the real-time dashboard")
    dashboard_group.add_argument("--dashboard-interval", type=float, default=1.0,
                        help="Dashboard update interval in seconds")

    # Storage configuration
    storage_group = parser.add_argument_group("Storage Configuration")
    storage_group.add_argument("--storage-backend", choices=["local", "s3", "ipfs", "filecoin"],
                        help="Storage backend to use")
    storage_group.add_argument("--storage-path", help="Path for local storage")
    storage_group.add_argument("--storage-config", help="Path to storage configuration JSON file")

    # WebRTC configuration
    webrtc_group = parser.add_argument_group("WebRTC Configuration")
    webrtc_group.add_argument("--webrtc-enabled", action="store_true",
                        help="Enable WebRTC functionality")
    webrtc_group.add_argument("--webrtc-config", help="Path to WebRTC configuration JSON file")

    # Metrics configuration
    metrics_group = parser.add_argument_group("Metrics Configuration")
    metrics_group.add_argument("--metrics-enabled", action="store_true",
                        help="Enable metrics collection")
    metrics_group.add_argument("--metrics-config", help="Path to metrics configuration JSON file")

    # Parse arguments
    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Load configuration from file if specified
    config = {}
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {args.config}")
        except Exception as e:
            logger.error(f"Failed to load configuration from {args.config}: {e}")
            return 1

    # Load storage configuration if specified
    storage_config = {}
    if args.storage_backend:
        storage_config["backend"] = args.storage_backend

    if args.storage_path:
        storage_config["path"] = args.storage_path

    if args.storage_config and os.path.exists(args.storage_config):
        try:
            with open(args.storage_config, 'r') as f:
                storage_config.update(json.load(f))
                logger.info(f"Loaded storage configuration from {args.storage_config}")
        except Exception as e:
            logger.error(f"Failed to load storage configuration from {args.storage_config}: {e}")
            return 1

    # Load WebRTC configuration if specified
    webrtc_config = {}
    if args.webrtc_config and os.path.exists(args.webrtc_config):
        try:
            with open(args.webrtc_config, 'r') as f:
                webrtc_config = json.load(f)
                logger.info(f"Loaded WebRTC configuration from {args.webrtc_config}")
        except Exception as e:
            logger.error(f"Failed to load WebRTC configuration from {args.webrtc_config}: {e}")
            return 1

    # Load metrics configuration if specified
    metrics_config = {}
    if args.metrics_config and os.path.exists(args.metrics_config):
        try:
            with open(args.metrics_config, 'r') as f:
                metrics_config = json.load(f)
                logger.info(f"Loaded metrics configuration from {args.metrics_config}")
        except Exception as e:
            logger.error(f"Failed to load metrics configuration from {args.metrics_config}: {e}")
            return 1

    # Initialize dashboard configuration
    dashboard_config = {
        'update_interval': args.dashboard_interval
    }

    # Create server runner
    try:
        runner = MCPServerRunner(
            server_type=args.server_type,
            debug_mode=args.debug,
            log_level=args.log_level,
            persistence_path=args.persistence_path,
            isolation_mode=args.isolation,
            skip_daemon=args.skip_daemon,
            config=config,
            host=args.host,
            port=args.port,
            api_prefix=args.api_prefix,
            backend=args.backend,
            watch_mode=args.watch_mode,
            watch_dirs=args.watch_dirs,
            ignore_dirs=args.ignore_dirs,
            ignore_patterns=args.ignore_patterns,
            dashboard=args.dashboard,
            dashboard_config=dashboard_config,
            storage_config=storage_config,
            auto_start_daemons=args.auto_start_daemons,
            daemon_health_monitor=args.daemon_health_monitor,
            webrtc_enabled=args.webrtc_enabled,
            webrtc_config=webrtc_config,
            metrics_enabled=args.metrics_enabled,
            metrics_config=metrics_config
        )
    except ValueError as e:
        logger.error(f"Error creating server runner: {e}")
        return 1

    # Start server
    try:
        success = runner.start()
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down")
        return 0
    except Exception as e:
        logger.error(f"Error running server: {e}")
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
