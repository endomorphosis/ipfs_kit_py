#!/usr/bin/env python3
"""
IPFS-Kit CLI for the unified MCP dashboard.

Usage:
  python -m ipfs_kit_py.cli mcp start [--port 8004] [--foreground] [--server-path FILE]
  python -m ipfs_kit_py.cli mcp stop  [--port 8004]
  python -m ipfs_kit_py.cli mcp status [--port 8004]
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
from typing import Optional


class FastCLI:
    def __init__(self) -> None:
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="IPFS-Kit CLI", formatter_class=argparse.RawTextHelpFormatter)
        sub = parser.add_subparsers(dest="command")

        # MCP server commands
        mcp = sub.add_parser("mcp", help="MCP server and dashboard")
        mcp_sub = mcp.add_subparsers(dest="mcp_action")

        p_start = mcp_sub.add_parser("start", help="Start MCP server and dashboard")
        p_start.add_argument("--port", type=int, default=8004)
        p_start.add_argument("--host", default="127.0.0.1")
        p_start.add_argument("--debug", action="store_true")
        p_start.add_argument("--foreground", action="store_true")
        p_start.add_argument("--data-dir", default=str(Path.home() / ".ipfs_kit"))
        p_start.add_argument("--server-path", default=None)

        p_stop = mcp_sub.add_parser("stop", help="Stop MCP server and dashboard")
        p_stop.add_argument("--port", type=int, default=8004)
        p_stop.add_argument("--data-dir", default=str(Path.home() / ".ipfs_kit"))

        p_status = mcp_sub.add_parser("status", help="Check MCP server status")
        p_status.add_argument("--port", type=int, default=8004)
        p_status.add_argument("--host", default="127.0.0.1")
        p_status.add_argument("--data-dir", default=str(Path.home() / ".ipfs_kit"))

        # Daemon management commands
        daemon = sub.add_parser("daemon", help="Daemon management (IPFS, Aria2, Lotus)")
        daemon_sub = daemon.add_subparsers(dest="daemon_action")

        # Start daemon
        d_start = daemon_sub.add_parser("start", help="Start daemon(s)")
        d_start.add_argument("--type", choices=["ipfs", "aria2", "lotus", "all"], default="ipfs",
                           help="Daemon type to start")
        d_start.add_argument("--config-dir", help="Directory for daemon configuration")
        d_start.add_argument("--work-dir", help="Working directory for the daemon")
        d_start.add_argument("--log-dir", help="Directory for daemon logs")
        d_start.add_argument("--debug", action="store_true", help="Enable debug mode")
        d_start.add_argument("--api-port", type=int, help="Port for API server")
        d_start.add_argument("--gateway-port", type=int, help="Port for IPFS gateway")
        d_start.add_argument("--swarm-port", type=int, help="Port for IPFS swarm connections")

        # Stop daemon
        d_stop = daemon_sub.add_parser("stop", help="Stop daemon(s)")
        d_stop.add_argument("--type", choices=["ipfs", "aria2", "lotus", "all"], default="ipfs",
                          help="Daemon type to stop")
        d_stop.add_argument("--config-dir", help="Directory for daemon configuration")

        # Restart daemon
        d_restart = daemon_sub.add_parser("restart", help="Restart daemon(s)")
        d_restart.add_argument("--type", choices=["ipfs", "aria2", "lotus", "all"], default="ipfs",
                             help="Daemon type to restart")
        d_restart.add_argument("--config-dir", help="Directory for daemon configuration")
        d_restart.add_argument("--work-dir", help="Working directory for the daemon")
        d_restart.add_argument("--log-dir", help="Directory for daemon logs")
        d_restart.add_argument("--debug", action="store_true", help="Enable debug mode")
        d_restart.add_argument("--api-port", type=int, help="Port for API server")
        d_restart.add_argument("--gateway-port", type=int, help="Port for IPFS gateway")
        d_restart.add_argument("--swarm-port", type=int, help="Port for IPFS swarm connections")

        # Status daemon
        d_status = daemon_sub.add_parser("status", help="Check daemon status")
        d_status.add_argument("--type", choices=["ipfs", "aria2", "lotus", "all"], default="all",
                            help="Daemon type to check")
        d_status.add_argument("--config-dir", help="Directory for daemon configuration")

        return parser

    async def run(self) -> None:
        args = self.parser.parse_args()
        if not args.command:
            self.parser.print_help(); sys.exit(2)
        
        # Handle MCP commands
        if args.command == "mcp":
            sub_action = getattr(args, "mcp_action", None)
            handler = getattr(self, f"handle_mcp_{sub_action}", None) if sub_action else None
        # Handle daemon commands  
        elif args.command == "daemon":
            sub_action = getattr(args, "daemon_action", None)
            handler = getattr(self, f"handle_daemon_{sub_action}", None) if sub_action else None
        else:
            handler = getattr(self, f"handle_{args.command}", None)
            
        if handler is None:
            print("Unknown command"); sys.exit(2)
        await handler(args)

    # ---- MCP ----
    async def handle_mcp_start(self, args) -> None:
        host = str(getattr(args, "host", "127.0.0.1"))
        port = int(getattr(args, "port", 8004))
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
            print("No server file found. Use --server-path or IPFS_KIT_SERVER_FILE.")
            sys.exit(2)

        pid_file = data_dir / f"mcp_{port}.pid"

        if bool(getattr(args, "foreground", False)):
            print(f"Starting MCP dashboard (foreground) using: {server_file}")
            spec = importlib.util.spec_from_file_location(server_file.stem, str(server_file))
            if spec is None or spec.loader is None:
                print("Failed to load server module spec"); sys.exit(2)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[attr-defined]
            DashboardClass = getattr(mod, "ConsolidatedMCPDashboard", None)
            if DashboardClass is None:
                for n, obj in vars(mod).items():
                    if n.endswith("Dashboard") and callable(getattr(obj, "__init__", None)):
                        DashboardClass = obj; break
            if DashboardClass is None:
                print("No Dashboard class found in server file"); sys.exit(2)
            app = DashboardClass({"host": host, "port": port, "data_dir": str(data_dir), "debug": debug})
            await app.run()
            return

        # background
        print(f"Starting MCP dashboard (background) using: {server_file}")
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
            print(f"Failed to launch: {e}"); sys.exit(1)
        # Immediately write our own pid file for management
        try:
            pid_file.write_text(str(proc.pid), encoding="utf-8")
        except Exception:
            pass
        print(f"MCP started: pid={proc.pid} http://{host}:{port} (log: {log_file})")
        return

    async def handle_mcp_stop(self, args) -> None:
        port = int(getattr(args, "port", 8004))
        data_dir = Path(getattr(args, "data_dir", str(Path.home() / ".ipfs_kit"))).expanduser()
        pid_file = data_dir / f"mcp_{port}.pid"
        if not pid_file.exists():
            # Fallback to generic dashboard.pid
            alt = data_dir / "dashboard.pid"
            if alt.exists():
                pid_file = alt
        if not pid_file.exists():
            print(f"No PID file found for port {port} at {data_dir}/mcp_{port}.pid")
            return
        pid = None
        with suppress(Exception):
            pid = int(pid_file.read_text().strip())
        if not pid:
            print("PID file unreadable")
            return
        with suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)
        # wait a bit
        deadline = time.time() + 5
        while time.time() < deadline and Path(f"/proc/{pid}").exists():
            time.sleep(0.1)
        with suppress(Exception):
            pid_file.unlink()
        print(f"MCP server on port {port} stopped (or already not running)")

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
    cli = FastCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())


def sync_main():  # pragma: no cover
    return asyncio.run(main())
