#!/usr/bin/env python3
"""
IPFS-Kit CLI - A comprehensive command-line interface for distributed storage backends.

Supports multiple backends with flexible command syntax:
  ipfs-kit <backend> <action>  # e.g., ipfs-kit storacha start
  ipfs-kit <action> <backend>  # e.g., ipfs-kit start storacha

Available backends: ipfs, storacha, s3, parquet, mcp
Available actions: start, stop, restart, status, init, info

Examples:
  ipfs-kit storacha start      # Start Storacha backend
  ipfs-kit start ipfs          # Start IPFS backend  
  ipfs-kit status all          # Check status of all backends
  ipfs-kit info                # Show available backends and usage
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Optional, List, Dict, Any


class BackendCLI:
    """Enhanced CLI with flexible backend-action command structure."""
    
    # Define available backends and their descriptions
    BACKENDS = {
        'ipfs': 'IPFS distributed storage daemon',
        'storacha': 'Storacha decentralized storage service',
        's3': 'Amazon S3 compatible storage backend',
        'parquet': 'Parquet data processing backend', 
        'mcp': 'MCP (Model Context Protocol) server',
        'daemon': 'Legacy daemon management (deprecated)',
        'all': 'All available backends'
    }
    
    # Define available actions and their descriptions
    ACTIONS = {
        'start': 'Start the specified backend service',
        'stop': 'Stop the specified backend service',
        'restart': 'Restart the specified backend service',
        'status': 'Check status of the specified backend',
        'init': 'Initialize the backend configuration',
        'info': 'Show information about backends and usage',
        'help': 'Show detailed help information'
    }

    def __init__(self) -> None:
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description="IPFS-Kit: Multi-backend distributed storage CLI",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self._get_usage_examples()
        )
        
        # Add top-level info command
        parser.add_argument('--version', action='version', version='ipfs-kit 0.3.0')
        
        subparsers = parser.add_subparsers(dest="command", help="Available commands")
        
        # Add info command
        info_parser = subparsers.add_parser("info", help="Show backend information and usage examples")
        info_parser.add_argument("--backends", action="store_true", help="List available backends")
        info_parser.add_argument("--actions", action="store_true", help="List available actions")
        
        # Add backend-specific parsers (backend first syntax: ipfs-kit storacha start)
        for backend, description in self.BACKENDS.items():
            if backend == 'all':  # Skip 'all' as it's handled differently
                continue
                
            backend_parser = subparsers.add_parser(backend, help=f"{description}")
            backend_subparsers = backend_parser.add_subparsers(dest=f"{backend}_action", help=f"{backend.title()} actions")
            
            # Add actions for each backend
            for action, action_desc in self.ACTIONS.items():
                if action in ['info', 'help']:  # Skip meta commands
                    continue
                    
                action_parser = backend_subparsers.add_parser(action, help=f"{action_desc}")
                self._add_common_arguments(action_parser, backend, action)
        
        # Add action-first parsers (action first syntax: ipfs-kit start storacha)
        for action, action_desc in self.ACTIONS.items():
            if action in ['info', 'help']:  # Skip meta commands
                continue
                
            action_parser = subparsers.add_parser(action, help=f"{action_desc}")
            
            # Add positional backend argument
            action_parser.add_argument(
                "backend", 
                choices=list(self.BACKENDS.keys()),
                help="Backend to perform action on"
            )
            
            self._add_common_arguments(action_parser, None, action)
        
        return parser

    def _add_common_arguments(self, parser: argparse.ArgumentParser, backend: Optional[str], action: str) -> None:
        """Add common arguments based on backend and action."""
        
        # Configuration arguments
        parser.add_argument("--config-dir", help="Directory for backend configuration")
        parser.add_argument("--work-dir", help="Working directory for the backend")
        parser.add_argument("--log-dir", help="Directory for backend logs")
        parser.add_argument("--debug", action="store_true", help="Enable debug mode")
        
        # Port arguments (for services that need them)
        if backend in ['ipfs', 'mcp', 'storacha'] or action in ['start', 'restart']:
            parser.add_argument("--port", type=int, help="Port for the service")
            parser.add_argument("--host", default="127.0.0.1", help="Host to bind service")
        
        # IPFS-specific arguments
        if backend == 'ipfs' or (backend is None and action in ['start', 'restart']):
            parser.add_argument("--gateway-port", type=int, help="Port for IPFS gateway")
            parser.add_argument("--swarm-port", type=int, help="Port for IPFS swarm connections")
            parser.add_argument("--api-port", type=int, help="Port for IPFS API")
        
        # MCP-specific arguments
        if backend == 'mcp' or (backend is None and action in ['start', 'restart']):
            parser.add_argument("--foreground", action="store_true", help="Run in foreground")
            parser.add_argument("--server-path", help="Path to MCP server file")
            parser.add_argument("--data-dir", default=str(Path.home() / ".ipfs_kit"), 
                              help="Data directory for MCP server")
        
        # S3-specific arguments
        if backend == 's3' or (backend is None and action in ['start', 'restart']):
            parser.add_argument("--endpoint", help="S3 endpoint URL")
            parser.add_argument("--region", help="S3 region")
            parser.add_argument("--bucket", help="S3 bucket name")
        
        # Storacha-specific arguments  
        if backend == 'storacha' or (backend is None and action in ['start', 'restart']):
            parser.add_argument("--space", help="Storacha space identifier")
            parser.add_argument("--agent", help="Storacha agent configuration")

    def _get_usage_examples(self) -> str:
        """Generate usage examples for the help text."""
        return """
Usage Examples:
  
  Backend-first syntax:
    ipfs-kit storacha start --port 8080     # Start Storacha service
    ipfs-kit ipfs status                    # Check IPFS status
    ipfs-kit s3 init --bucket my-bucket     # Initialize S3 backend
  
  Action-first syntax:
    ipfs-kit start storacha --port 8080     # Start Storacha service
    ipfs-kit status ipfs                    # Check IPFS status  
    ipfs-kit init s3 --bucket my-bucket     # Initialize S3 backend
  
  Information commands:
    ipfs-kit info                           # Show all available backends
    ipfs-kit info --backends               # List backends only
    ipfs-kit status all                     # Check status of all backends

Available Backends:
  ipfs      - IPFS distributed storage daemon
  storacha  - Storacha decentralized storage service
  s3        - Amazon S3 compatible storage backend
  parquet   - Parquet data processing backend
  mcp       - MCP (Model Context Protocol) server
  
Available Actions:
  start, stop, restart, status, init, info
        """

    async def run(self) -> None:
        args = self.parser.parse_args()
        if not args.command:
            self.parser.print_help()
            sys.exit(2)
        
        # Handle info command
        if args.command == "info":
            await self.handle_info(args)
            return
        
        # Determine if this is backend-first or action-first syntax
        if args.command in self.BACKENDS:
            # Backend-first syntax: ipfs-kit storacha start
            backend = args.command
            action = getattr(args, f"{backend}_action", None)
            if not action:
                print(f"No action specified for {backend} backend")
                self.parser.parse_args([backend, "--help"])
                return
        elif args.command in self.ACTIONS:
            # Action-first syntax: ipfs-kit start storacha  
            action = args.command
            backend = getattr(args, "backend", None)
            if not backend:
                print(f"No backend specified for {action} action")
                self.parser.parse_args([action, "--help"])
                return
        else:
            print(f"Unknown command: {args.command}")
            self.parser.print_help()
            sys.exit(2)
        
        # Route to appropriate handler
        # First try specific backend_action handler, then fall back to general action handler
        specific_handler = getattr(self, f"handle_{action}_{backend}", None)
        general_handler = getattr(self, f"handle_{action}", None)
        
        handler = specific_handler or general_handler
        
        if handler is None:
            print(f"No handler found for {action} {backend}")
            sys.exit(2)
        
        await handler(args, backend, action)

    async def handle_info(self, args) -> None:
        """Handle info command to show backend and usage information."""
        if args.backends:
            print("Available Backends:")
            for backend, desc in self.BACKENDS.items():
                if backend != 'all':
                    print(f"  {backend:<12} - {desc}")
        elif args.actions:
            print("Available Actions:")
            for action, desc in self.ACTIONS.items():
                if action not in ['info', 'help']:
                    print(f"  {action:<12} - {desc}")
        else:
            print("IPFS-Kit: Multi-backend distributed storage CLI")
            print("=" * 50)
            print("\nAvailable Backends:")
            for backend, desc in self.BACKENDS.items():
                if backend != 'all':
                    print(f"  {backend:<12} - {desc}")
            
            print("\nAvailable Actions:")
            for action, desc in self.ACTIONS.items():
                if action not in ['info', 'help']:
                    print(f"  {action:<12} - {desc}")
            
            print("\nCommand Syntax:")
            print("  ipfs-kit <backend> <action> [options]  # Backend-first")
            print("  ipfs-kit <action> <backend> [options]  # Action-first")
            
            print("\nExamples:")
            print("  ipfs-kit storacha start --port 8080")
            print("  ipfs-kit start ipfs --debug")
            print("  ipfs-kit status all")
            print("  ipfs-kit info --backends")

    # ---- Generic action handlers ----
    async def handle_start(self, args, backend: str, action: str) -> None:
        """Handle start action for any backend."""
        if backend == 'all':
            await self._handle_all_backends(args, 'start')
            return
        
        print(f"Starting {backend} backend...")
        
        if backend == 'mcp':
            await self._handle_mcp_start(args)
        elif backend == 'ipfs':
            await self._handle_daemon_start(args, 'ipfs')
        elif backend == 'storacha':
            await self._handle_storacha_start(args)
        elif backend == 's3':
            await self._handle_s3_start(args)
        elif backend == 'parquet':
            await self._handle_parquet_start(args)
        elif backend == 'daemon':
            # Legacy support
            await self._handle_daemon_start(args, args.type if hasattr(args, 'type') else 'ipfs')
        else:
            print(f"❌ Unknown backend: {backend}")

    async def handle_stop(self, args, backend: str, action: str) -> None:
        """Handle stop action for any backend."""
        if backend == 'all':
            await self._handle_all_backends(args, 'stop')
            return
        
        print(f"Stopping {backend} backend...")
        
        if backend == 'mcp':
            await self._handle_mcp_stop(args)
        elif backend == 'ipfs':
            await self._handle_daemon_stop(args, 'ipfs')
        elif backend == 'storacha':
            await self._handle_storacha_stop(args)
        elif backend == 's3':
            await self._handle_s3_stop(args)
        elif backend == 'parquet':
            await self._handle_parquet_stop(args)
        elif backend == 'daemon':
            # Legacy support
            await self._handle_daemon_stop(args, args.type if hasattr(args, 'type') else 'ipfs')
        else:
            print(f"❌ Unknown backend: {backend}")

    async def handle_restart(self, args, backend: str, action: str) -> None:
        """Handle restart action for any backend."""
        if backend == 'all':
            await self._handle_all_backends(args, 'restart')
            return
        
        print(f"Restarting {backend} backend...")
        await self.handle_stop(args, backend, 'stop')
        await asyncio.sleep(2)  # Give it a moment
        await self.handle_start(args, backend, 'start')

    async def handle_status(self, args, backend: str, action: str) -> None:
        """Handle status action for any backend."""
        if backend == 'all':
            await self._handle_all_backends(args, 'status')
            return
        
        print(f"\n{backend.upper()} Backend Status:")
        print("-" * (len(backend) + 16))
        
        if backend == 'mcp':
            await self._handle_mcp_status(args)
        elif backend == 'ipfs':
            await self._handle_daemon_status(args, 'ipfs')
        elif backend == 'storacha':
            await self._handle_storacha_status(args)
        elif backend == 's3':
            await self._handle_s3_status(args)
        elif backend == 'parquet':
            await self._handle_parquet_status(args)
        elif backend == 'daemon':
            # Legacy support
            await self._handle_daemon_status(args, args.type if hasattr(args, 'type') else 'all')
        else:
            print(f"❌ Unknown backend: {backend}")

    async def handle_init(self, args, backend: str, action: str) -> None:
        """Handle init action for any backend."""
        print(f"Initializing {backend} backend...")
        
        if backend == 'ipfs':
            await self._handle_ipfs_init(args)
        elif backend == 'storacha':
            await self._handle_storacha_init(args)
        elif backend == 's3':
            await self._handle_s3_init(args)
        elif backend == 'parquet':
            await self._handle_parquet_init(args)
        elif backend == 'mcp':
            print("✅ MCP backend requires no initialization")
        else:
            print(f"❌ Backend {backend} does not support initialization")

    # ---- Helper methods for all backends ----
    async def _handle_all_backends(self, args, action: str) -> None:
        """Handle actions for all backends."""
        backends_to_handle = ['ipfs', 'storacha', 's3', 'parquet', 'mcp']
        
        for backend in backends_to_handle:
            try:
                if action == 'start':
                    await self.handle_start(args, backend, action)
                elif action == 'stop':
                    await self.handle_stop(args, backend, action)
                elif action == 'restart':
                    await self.handle_restart(args, backend, action)
                elif action == 'status':
                    await self.handle_status(args, backend, action)
                await asyncio.sleep(0.5)  # Small delay between backends
            except Exception as e:
                print(f"❌ Error with {backend}: {e}")

    # ---- Backend-specific implementation methods ----
    async def _handle_mcp_start(self, args) -> None:
        """Start MCP server (preserving original functionality)."""
        host = str(getattr(args, "host", "127.0.0.1"))
        port = int(getattr(args, "port", None) or 8004)
        debug = bool(getattr(args, "debug", False))
        data_dir = Path(getattr(args, "data_dir", str(Path.home() / ".ipfs_kit"))).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)

        def detect_server_file() -> Optional[Path]:
            # explicit
            sp = getattr(args, "server_path", None)
            if sp:
                p = Path(sp).expanduser().resolve()
                if p.exists():
                    return p
            # env
            envp = os.environ.get("IPFS_KIT_SERVER_FILE")
            if envp:
                p = Path(envp).expanduser().resolve()
                if p.exists():
                    return p
            # repo root or cwd (handle missing/invalid cwd gracefully)
            bases: list[Path] = [Path(__file__).resolve().parents[1]]
            try:
                cwd = Path.cwd()
                bases.append(cwd)
            except FileNotFoundError:
                # Working directory no longer exists; ignore
                pass
            # common fallback if running from home or elsewhere
            home_repo = Path.home() / "ipfs_kit_py"
            if home_repo.exists():
                bases.append(home_repo)
            for base in bases:
                for name in (
                    "consolidated_mcp_dashboard.py",
                    "unified_mcp_dashboard.py",
                    "modernized_comprehensive_dashboard.py",
                ):
                    p = base / name
                    if p.exists():
                        return p
            return None

        server_file = detect_server_file()
        if not server_file:
            print("❌ No server file found. Use --server-path or IPFS_KIT_SERVER_FILE.")
            return

        pid_file = data_dir / f"mcp_{port}.pid"

        if bool(getattr(args, "foreground", False)):
            print(f"✅ Starting MCP dashboard (foreground) using: {server_file}")
            spec = importlib.util.spec_from_file_location(server_file.stem, str(server_file))
            if spec is None or spec.loader is None:
                print("❌ Failed to load server module spec")
                return
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[attr-defined]
            DashboardClass = getattr(mod, "ConsolidatedMCPDashboard", None)
            if DashboardClass is None:
                for n, obj in vars(mod).items():
                    if n.endswith("Dashboard") and callable(getattr(obj, "__init__", None)):
                        DashboardClass = obj; break
            if DashboardClass is None:
                print("❌ No Dashboard class found in server file")
                return
            app = DashboardClass({"host": host, "port": port, "data_dir": str(data_dir), "debug": debug})
            await app.run()
            return

        # background
        print(f"✅ Starting MCP dashboard (background) using: {server_file}")
        log_file = data_dir / f"mcp_{port}.log"
        cmd = [sys.executable, "-m", "ipfs_kit_py.cli", "mcp", "start", "--host", host, "--port", str(port), "--data-dir", str(data_dir), "--foreground"]
        if debug:
            cmd.append("--debug")
        env = os.environ.copy()
        env["IPFS_KIT_SERVER_FILE"] = str(server_file)
        try:
            with open(log_file, "ab", buffering=0) as lf:
                proc = subprocess.Popen(cmd, stdout=lf, stderr=lf, cwd=server_file.parent, start_new_session=True, env=env)
        except Exception as e:
            print(f"❌ Failed to launch: {e}")
            return
        # Immediately write our own pid file for management
        try:
            pid_file.write_text(str(proc.pid), encoding="utf-8")
        except Exception:
            pass
        print(f"✅ MCP started: pid={proc.pid} http://{host}:{port} (log: {log_file})")

    async def _handle_mcp_stop(self, args) -> None:
        """Stop MCP server (preserving original functionality)."""
        port = int(getattr(args, "port", None) or 8004)
        data_dir = Path(getattr(args, "data_dir", str(Path.home() / ".ipfs_kit"))).expanduser()
        pid_file = data_dir / f"mcp_{port}.pid"
        if not pid_file.exists():
            # Fallback to generic dashboard.pid
            alt = data_dir / "dashboard.pid"
            if alt.exists():
                pid_file = alt
        if not pid_file.exists():
            print(f"❌ No PID file found for port {port} at {data_dir}/mcp_{port}.pid")
            return
        pid = None
        with suppress(Exception):
            pid = int(pid_file.read_text().strip())
        if not pid:
            print("❌ PID file unreadable")
            return
        with suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)
        # wait a bit
        deadline = time.time() + 5
        while time.time() < deadline and Path(f"/proc/{pid}").exists():
            time.sleep(0.1)
        with suppress(Exception):
            pid_file.unlink()
        print(f"✅ MCP server on port {port} stopped (or already not running)")

    async def _handle_mcp_status(self, args) -> None:
        """Check MCP server status (preserving original functionality)."""
        host = str(getattr(args, "host", "127.0.0.1"))
        port = int(getattr(args, "port", None) or 8004)
        data_dir = Path(getattr(args, "data_dir", str(Path.home() / ".ipfs_kit"))).expanduser()
        pid_file = data_dir / f"mcp_{port}.pid"
        info = {"pidFile": str(pid_file), "pid": None, "http": None}
        if not pid_file.exists():
            # Fallback for older servers writing dashboard.pid
            alt = data_dir / "dashboard.pid"
            if alt.exists():
                info["pidFile"] = str(alt)
                pid_file = alt
        if pid_file.exists():
            with suppress(Exception):
                info["pid"] = int(pid_file.read_text().strip())
        # HTTP probe
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/api/mcp/status", timeout=2.5) as r:
                raw = r.read().decode("utf-8", "ignore")
                with suppress(Exception):
                    info["http"] = json.loads(raw)
        except Exception:
            pass
        print(json.dumps(info, indent=2))

    # ---- IPFS daemon handlers (legacy integration) ----
    def _get_daemon_manager_path(self) -> Path:
        """Get path to daemon manager script."""
        script_path = Path(__file__).parent.parent / "scripts" / "daemon" / "daemon_manager.py"
        if script_path.exists():
            return script_path
        # Fallback: look in the same directory structure
        alt_path = Path(__file__).parent / "scripts" / "daemon" / "daemon_manager.py"
        if alt_path.exists():
            return alt_path
        raise FileNotFoundError("daemon_manager.py not found")

    async def _handle_daemon_start(self, args, daemon_type: str) -> None:
        """Start daemon using existing daemon manager."""
        try:
            daemon_manager_path = self._get_daemon_manager_path()
            cmd = [sys.executable, str(daemon_manager_path), "--daemon", daemon_type, "--action", "start"]
            
            # Add optional arguments
            if hasattr(args, 'config_dir') and args.config_dir:
                cmd.extend(["--config-dir", args.config_dir])
            if hasattr(args, 'work_dir') and args.work_dir:
                cmd.extend(["--work-dir", args.work_dir])
            if hasattr(args, 'log_dir') and args.log_dir:
                cmd.extend(["--log-dir", args.log_dir])
            if hasattr(args, 'debug') and args.debug:
                cmd.append("--debug")
            if hasattr(args, 'api_port') and args.api_port:
                cmd.extend(["--api-port", str(args.api_port)])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"✅ {daemon_type} daemon started successfully")
            else:
                print(f"❌ Failed to start {daemon_type} daemon: {result.stderr}")
        except Exception as e:
            print(f"❌ Error starting {daemon_type} daemon: {e}")

    async def _handle_daemon_stop(self, args, daemon_type: str) -> None:
        """Stop daemon using existing daemon manager."""
        try:
            daemon_manager_path = self._get_daemon_manager_path()
            cmd = [sys.executable, str(daemon_manager_path), "--daemon", daemon_type, "--action", "stop"]
            
            if hasattr(args, 'config_dir') and args.config_dir:
                cmd.extend(["--config-dir", args.config_dir])
                
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                print(f"✅ {daemon_type} daemon stopped successfully")
            else:
                print(f"❌ Failed to stop {daemon_type} daemon: {result.stderr}")
        except Exception as e:
            print(f"❌ Error stopping {daemon_type} daemon: {e}")

    async def _handle_daemon_status(self, args, daemon_type: str) -> None:
        """Check daemon status using existing daemon manager."""
        if daemon_type == 'all':
            daemon_types = ['ipfs', 'aria2', 'lotus']
        else:
            daemon_types = [daemon_type]
            
        try:
            daemon_manager_path = self._get_daemon_manager_path()
            
            for dtype in daemon_types:
                cmd = [sys.executable, str(daemon_manager_path), "--daemon", dtype, "--action", "status"]
                
                if hasattr(args, 'config_dir') and args.config_dir:
                    cmd.extend(["--config-dir", args.config_dir])
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    try:
                        status = json.loads(result.stdout)
                        print(json.dumps(status, indent=2))
                    except json.JSONDecodeError:
                        print(result.stdout)
                else:
                    print(f"❌ Error getting {dtype} status: {result.stderr}")
        except Exception as e:
            print(f"❌ Error getting daemon status: {e}")

    # ---- Storacha backend handlers ----
    async def _handle_storacha_start(self, args) -> None:
        """Start Storacha backend."""
        print("🚀 Starting Storacha backend...")
        # Implementation would integrate with Storacha service
        # For now, show what would be done
        space = getattr(args, 'space', None)
        agent = getattr(args, 'agent', None)
        port = getattr(args, 'port', 8081)
        
        print(f"   Space: {space or 'default'}")
        print(f"   Agent: {agent or 'auto-detect'}")
        print(f"   Port: {port}")
        print("✅ Storacha backend would be started (implementation needed)")

    async def _handle_storacha_stop(self, args) -> None:
        """Stop Storacha backend."""
        print("🛑 Stopping Storacha backend...")
        print("✅ Storacha backend would be stopped (implementation needed)")

    async def _handle_storacha_status(self, args) -> None:
        """Check Storacha backend status."""
        status = {
            "backend": "storacha",
            "status": "not_implemented",
            "message": "Storacha status checking not yet implemented"
        }
        print(json.dumps(status, indent=2))

    async def _handle_storacha_init(self, args) -> None:
        """Initialize Storacha backend."""
        print("🔧 Initializing Storacha backend...")
        print("✅ Storacha backend would be initialized (implementation needed)")

    # ---- S3 backend handlers ----
    async def _handle_s3_start(self, args) -> None:
        """Start S3 backend service."""
        print("🚀 Starting S3 backend...")
        endpoint = getattr(args, 'endpoint', None)
        region = getattr(args, 'region', 'us-east-1')
        bucket = getattr(args, 'bucket', None)
        
        print(f"   Endpoint: {endpoint or 'AWS default'}")
        print(f"   Region: {region}")  
        print(f"   Bucket: {bucket or 'not specified'}")
        print("✅ S3 backend would be started (implementation needed)")

    async def _handle_s3_stop(self, args) -> None:
        """Stop S3 backend service."""
        print("🛑 Stopping S3 backend...")
        print("✅ S3 backend would be stopped (implementation needed)")

    async def _handle_s3_status(self, args) -> None:
        """Check S3 backend status."""
        status = {
            "backend": "s3",
            "status": "not_implemented", 
            "message": "S3 status checking not yet implemented"
        }
        print(json.dumps(status, indent=2))

    async def _handle_s3_init(self, args) -> None:
        """Initialize S3 backend."""
        print("🔧 Initializing S3 backend...")
        bucket = getattr(args, 'bucket', None)
        if bucket:
            print(f"   Creating/configuring bucket: {bucket}")
        print("✅ S3 backend would be initialized (implementation needed)")


async def main() -> None:
    """Main CLI entry point."""
    cli = BackendCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())


def sync_main():  # pragma: no cover
    """Synchronous main entry point for package scripts."""
    return asyncio.run(main())

    # ---- Parquet backend handlers ----
    async def _handle_parquet_start(self, args) -> None:
        """Start Parquet backend service."""
        print("🚀 Starting Parquet backend...")
        print("✅ Parquet backend would be started (implementation needed)")

    async def _handle_parquet_stop(self, args) -> None:
        """Stop Parquet backend service."""
        print("🛑 Stopping Parquet backend...")
        print("✅ Parquet backend would be stopped (implementation needed)")

    async def _handle_parquet_status(self, args) -> None:
        """Check Parquet backend status."""
        status = {
            "backend": "parquet",
            "status": "not_implemented",
            "message": "Parquet status checking not yet implemented"
        }
        print(json.dumps(status, indent=2))

    async def _handle_parquet_status(self, args) -> None:
        """Check Parquet backend status."""
        status = {
            "backend": "parquet",
            "status": "not_implemented",
            "message": "Parquet status checking not yet implemented"
        }
        print(json.dumps(status, indent=2))

    async def _handle_parquet_init(self, args) -> None:
        """Initialize Parquet backend."""
        print("🔧 Initializing Parquet backend...")
        print("✅ Parquet backend would be initialized (implementation needed)")

    async def _handle_ipfs_init(self, args) -> None:
        """Initialize IPFS backend."""
        print("🔧 Initializing IPFS backend...")
        try:
            daemon_manager_path = self._get_daemon_manager_path()
            # Use daemon manager to initialize IPFS
            cmd = [sys.executable, str(daemon_manager_path), "--daemon", "ipfs", "--action", "status"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("✅ IPFS backend already initialized")
            else:
                print("✅ IPFS backend would be initialized (implementation needed)")
        except Exception as e:
            print(f"❌ Error checking IPFS initialization: {e}")

    async def handle_mcp_status(self, args) -> None:
        host = str(getattr(args, "host", "127.0.0.1"))
        port = int(getattr(args, "port", 8004))
        data_dir = Path(getattr(args, "data_dir", str(Path.home() / ".ipfs_kit"))).expanduser()
        pid_file = data_dir / f"mcp_{port}.pid"
        info = {"pidFile": str(pid_file), "pid": None, "http": None}
        if not pid_file.exists():
            # Fallback for older servers writing dashboard.pid
            alt = data_dir / "dashboard.pid"
            if alt.exists():
                info["pidFile"] = str(alt)
                pid_file = alt
        if pid_file.exists():
            with suppress(Exception):
                info["pid"] = int(pid_file.read_text().strip())
        # HTTP probe
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/api/mcp/status", timeout=2.5) as r:
                raw = r.read().decode("utf-8", "ignore")
                with suppress(Exception):
                    info["http"] = json.loads(raw)
        except Exception:
            pass
        print(json.dumps(info, indent=2))

    # ---- Daemon management ----
    def _get_daemon_manager_path(self) -> Path:
        """Get path to daemon manager script."""
        script_path = Path(__file__).parent.parent / "scripts" / "daemon" / "daemon_manager.py"
        if script_path.exists():
            return script_path
        # Fallback: look in the same directory structure
        alt_path = Path(__file__).parent / "scripts" / "daemon" / "daemon_manager.py"
        if alt_path.exists():
            return alt_path
        raise FileNotFoundError("daemon_manager.py not found")

    def _get_daemon_types(self, daemon_type: str) -> list[str]:
        """Convert daemon type argument to list of daemon types."""
        if daemon_type == "all":
            return ["ipfs", "aria2", "lotus"]
        return [daemon_type]

    async def handle_daemon_start(self, args) -> None:
        """Start daemon(s)."""
        daemon_types = self._get_daemon_types(args.type)
        daemon_manager_path = self._get_daemon_manager_path()
        
        for daemon_type in daemon_types:
            print(f"Starting {daemon_type} daemon...")
            cmd = [sys.executable, str(daemon_manager_path), "--daemon", daemon_type, "--action", "start"]
            
            # Add optional arguments
            if args.config_dir:
                cmd.extend(["--config-dir", args.config_dir])
            if args.work_dir:
                cmd.extend(["--work-dir", args.work_dir])
            if args.log_dir:
                cmd.extend(["--log-dir", args.log_dir])
            if args.debug:
                cmd.append("--debug")
            if args.api_port:
                cmd.extend(["--api-port", str(args.api_port)])
            if args.gateway_port:
                cmd.extend(["--gateway-port", str(args.gateway_port)])
            if args.swarm_port:
                cmd.extend(["--swarm-port", str(args.swarm_port)])
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"✓ {daemon_type} daemon started successfully")
                else:
                    print(f"✗ Failed to start {daemon_type} daemon: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"✗ Timeout starting {daemon_type} daemon")
            except Exception as e:
                print(f"✗ Error starting {daemon_type} daemon: {e}")

    async def handle_daemon_stop(self, args) -> None:
        """Stop daemon(s)."""
        daemon_types = self._get_daemon_types(args.type)
        daemon_manager_path = self._get_daemon_manager_path()
        
        for daemon_type in daemon_types:
            print(f"Stopping {daemon_type} daemon...")
            cmd = [sys.executable, str(daemon_manager_path), "--daemon", daemon_type, "--action", "stop"]
            
            if args.config_dir:
                cmd.extend(["--config-dir", args.config_dir])
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    print(f"✓ {daemon_type} daemon stopped successfully")
                else:
                    print(f"✗ Failed to stop {daemon_type} daemon: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"✗ Timeout stopping {daemon_type} daemon")
            except Exception as e:
                print(f"✗ Error stopping {daemon_type} daemon: {e}")

    async def handle_daemon_restart(self, args) -> None:
        """Restart daemon(s)."""
        daemon_types = self._get_daemon_types(args.type)
        daemon_manager_path = self._get_daemon_manager_path()
        
        for daemon_type in daemon_types:
            print(f"Restarting {daemon_type} daemon...")
            cmd = [sys.executable, str(daemon_manager_path), "--daemon", daemon_type, "--action", "restart"]
            
            # Add optional arguments
            if args.config_dir:
                cmd.extend(["--config-dir", args.config_dir])
            if args.work_dir:
                cmd.extend(["--work-dir", args.work_dir])
            if args.log_dir:
                cmd.extend(["--log-dir", args.log_dir])
            if args.debug:
                cmd.append("--debug")
            if args.api_port:
                cmd.extend(["--api-port", str(args.api_port)])
            if args.gateway_port:
                cmd.extend(["--gateway-port", str(args.gateway_port)])
            if args.swarm_port:
                cmd.extend(["--swarm-port", str(args.swarm_port)])
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                if result.returncode == 0:
                    print(f"✓ {daemon_type} daemon restarted successfully")
                else:
                    print(f"✗ Failed to restart {daemon_type} daemon: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"✗ Timeout restarting {daemon_type} daemon")
            except Exception as e:
                print(f"✗ Error restarting {daemon_type} daemon: {e}")

    async def handle_daemon_status(self, args) -> None:
        """Check daemon status."""
        daemon_types = self._get_daemon_types(args.type)
        daemon_manager_path = self._get_daemon_manager_path()
        
        for daemon_type in daemon_types:
            print(f"\n{daemon_type.upper()} Daemon Status:")
            print("-" * (len(daemon_type) + 15))
            
            cmd = [sys.executable, str(daemon_manager_path), "--daemon", daemon_type, "--action", "status"]
            
            if args.config_dir:
                cmd.extend(["--config-dir", args.config_dir])
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    # Parse and format the JSON status output
                    try:
                        status = json.loads(result.stdout)
                        print(json.dumps(status, indent=2))
                    except json.JSONDecodeError:
                        print(result.stdout)
                else:
                    print(f"Error getting status: {result.stderr}")
            except subprocess.TimeoutExpired:
                print("Timeout getting daemon status")
            except Exception as e:
                print(f"Error getting daemon status: {e}")


async def main() -> None:
    cli = BackendCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())


def sync_main():  # pragma: no cover
    return asyncio.run(main())
