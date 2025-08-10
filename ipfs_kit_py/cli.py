#!/usr/bin/env python3
"""
IPFS-Kit CLI - Optimized for Just-in-Time Imports

This CLI is designed to be fast and responsive by deferring the loading of heavy
libraries until they are actually needed.

Docs:
- CONSOLIDATED_MCP_DASHBOARD.md (server/dashboard details)
- JIT_CLI_README.md (CLI usage for MCP dashboard)
"""

import argparse
import sys
import asyncio
from pathlib import Path
import importlib.util
import inspect

class FastCLI:
    """
    A Just-in-Time (JIT) CLI for ipfs-kit.
    """

    def __init__(self):
        self.parser = self._create_parser()

    def _create_parser(self):
        """Create the argument parser for the CLI (minimal JIT version)."""
        parser = argparse.ArgumentParser(
            description="IPFS-Kit Enhanced CLI Tool",
            formatter_class=argparse.RawTextHelpFormatter,
        )
        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        # === MCP Commands (unified dashboard) ===
        mcp_parser = subparsers.add_parser('mcp', help='MCP server and dashboard')
        mcp_subparsers = mcp_parser.add_subparsers(dest='mcp_action', help='MCP actions')

        mcp_start = mcp_subparsers.add_parser('start', help='Start MCP server and dashboard')
        mcp_start.add_argument('--port', type=int, default=8004, help='Port for unified MCP server + dashboard (default: 8004)')
        mcp_start.add_argument('--host', default='127.0.0.1', help='Host for MCP server (default: 127.0.0.1)')
        mcp_start.add_argument('--debug', action='store_true', help='Enable debug mode')
        mcp_start.add_argument('--foreground', action='store_true', help='Run in foreground (do not daemonize)')
        mcp_start.add_argument('--data-dir', default=str(Path.home() / '.ipfs_kit'), help='Data directory (default: ~/.ipfs_kit)')

        # Stop & Status (with optional port override)
        stop_parser = mcp_subparsers.add_parser('stop', help='Stop MCP server and dashboard')
        stop_parser.add_argument('--port', type=int, default=8004, help='Port to stop (default: 8004)')
        stop_parser.add_argument('--data-dir', default=str(Path.home() / '.ipfs_kit'), help='Data directory (default: ~/.ipfs_kit)')

        status_parser = mcp_subparsers.add_parser('status', help='Check MCP server status')
        status_parser.add_argument('--port', type=int, default=8004, help='Port to check (default: 8004)')
        status_parser.add_argument('--host', default='127.0.0.1', help='Host to check (default: 127.0.0.1)')
        status_parser.add_argument('--data-dir', default=str(Path.home() / '.ipfs_kit'), help='Data directory (default: ~/.ipfs_kit)')

        return parser

    async def run(self):
        """
        Parses arguments and executes the corresponding command.
        """
        args = self.parser.parse_args()
        if not args.command:
            self.parser.print_help()
            sys.exit(1)

        # Determine sub-action attribute name dynamically per command group
        action_attr = f"{args.command}_action"
        sub_action = getattr(args, action_attr, None)
        handler_name = f"handle_{args.command}_{sub_action}" if sub_action else f"handle_{args.command}"

        handler = getattr(self, handler_name, None)
        if handler is None:
            print(f"Error: Command '{args.command} {sub_action or ''}'. Not implemented.")
            self.parser.print_help()
            sys.exit(1)

        await handler(args)

    async def handle_daemon_start(self, args):
        print("Daemon start is not implemented in this minimal CLI.")

    async def handle_daemon_stop(self, args):
        print("Daemon stop is not implemented in this minimal CLI.")

    async def handle_daemon_status(self, args):
        print("Daemon status is not implemented in this minimal CLI.")

    async def handle_pin_add(self, args):
        print("Pin add is not implemented in this minimal CLI.")

    async def handle_pin_remove(self, args):
        print("Pin remove is not implemented in this minimal CLI.")

    async def handle_pin_list(self, args):
        print("Pin list is not implemented in this minimal CLI.")

    async def handle_bucket_list(self, args):
        print("Bucket list is not implemented in this minimal CLI.")

    async def handle_bucket_create(self, args):
        print("Bucket create is not implemented in this minimal CLI.")

    async def handle_mcp_start(self, args):
        import subprocess, os, time
        port = getattr(args, 'port', 8004)
        host = getattr(args, 'host', '127.0.0.1')
        debug = bool(getattr(args, 'debug', False))
        data_dir = Path(getattr(args, 'data_dir', str(Path.home() / '.ipfs_kit'))).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)

        # Foreground mode: run server in current process (blocks until Ctrl-C)
        if getattr(args, 'foreground', False):
            print("Starting unified MCP dashboard (foreground)...")
            try:
                repo_root = Path(__file__).resolve().parents[1]
                unified = repo_root / 'consolidated_mcp_dashboard.py'
                legacy = repo_root / 'modernized_comprehensive_dashboard.py'

                module_path = None
                module_name = None
                class_name = None

                if unified.exists():
                    module_path = unified
                    module_name = 'consolidated_mcp_dashboard'
                    class_name = 'ConsolidatedMCPDashboard'
                elif legacy.exists():
                    module_path = legacy
                    module_name = 'modernized_comprehensive_dashboard'
                    class_name = 'ModernizedComprehensiveDashboard'
                else:
                    print('No dashboard file found in repository root (expected consolidated or legacy).')
                    sys.exit(2)

                spec = importlib.util.spec_from_file_location(module_name, str(module_path))
                if spec is None or spec.loader is None:
                    raise ImportError(f"Failed to load module spec for {module_name}")
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                DashboardClass = getattr(mod, class_name)
                config = {
                    'host': host,
                    'port': port,
                    'debug': debug,
                    'data_dir': str(data_dir),
                }
                instance = DashboardClass(config)
                run_method = getattr(instance, 'run', None)
                if run_method is None:
                    raise AttributeError('Dashboard class has no run() method')
                if inspect.iscoroutinefunction(run_method):
                    await run_method()
                else:
                    run_method()
            except Exception as e:
                print(f"Failed to start dashboard (foreground): {e}")
                sys.exit(1)
            return

        # Background mode: spawn a detached child that runs foreground server
        print("Starting unified MCP dashboard (background)...")
        log_file = data_dir / f"mcp_{port}.log"
        cmd = [
            sys.executable,
            '-m', 'ipfs_kit_py.cli', 'mcp', 'start',
            '--host', host,
            '--port', str(port),
            '--data-dir', str(data_dir),
            '--foreground'
        ]
        if debug:
            cmd.append('--debug')
        try:
            with open(log_file, 'ab', buffering=0) as lf:
                proc = subprocess.Popen(
                    cmd,
                    stdout=lf,
                    stderr=lf,
                    cwd=Path(__file__).resolve().parents[1],
                    start_new_session=True,
                    env=os.environ.copy(),
                )
        except Exception as e:
            print(f"Failed to launch background process: {e}")
            sys.exit(1)

        # Wait briefly for PID file written by app startup hook
        pid_file = data_dir / f"mcp_{port}.pid"
        deadline = time.time() + 10
        while time.time() < deadline and not pid_file.exists():
            time.sleep(0.2)

        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                print(f"MCP started on http://{host}:{port} (pid {pid}). Logs: {log_file}")
                return
            except Exception:
                pass

        # Fallback: no PID file yet—report child PID and log path
        print(f"MCP launch initiated (child pid {proc.pid}) on http://{host}:{port}. Logs: {log_file}")
        # Do not block—return success
        return

    async def handle_mcp_stop(self, args):
        port = getattr(args, 'port', 8004)
        data_dir = Path(getattr(args, 'data_dir', str(Path.home() / '.ipfs_kit'))).expanduser()
        pid_file = data_dir / f'mcp_{port}.pid'
        if not pid_file.exists():
            print(f"No PID file found for port {port} ({pid_file}). Is MCP running?")
            return
        try:
            pid = int(pid_file.read_text().strip())
        except Exception as e:
            print(f"Failed to read PID file: {e}")
            return
        import os, signal
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to MCP process {pid} (port {port}).")
        except ProcessLookupError:
            print(f"Process {pid} not found. Cleaning stale PID file.")
        except Exception as e:
            print(f"Error sending SIGTERM: {e}")
        try:
            pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    async def handle_mcp_status(self, args):
        port = getattr(args, 'port', 8004)
        host = getattr(args, 'host', '127.0.0.1')
        data_dir = Path(getattr(args, 'data_dir', str(Path.home() / '.ipfs_kit'))).expanduser()
        pid_file = data_dir / f'mcp_{port}.pid'
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                # Check if process alive
                alive = Path(f'/proc/{pid}').exists()
                print(f"MCP (port {port}) PID file present: pid={pid} alive={alive}")
            except Exception as e:
                print(f"MCP (port {port}) PID file unreadable: {e}")
        else:
            print(f"MCP (port {port}) not running (no PID file).")

        # Attempt HTTP status probe (best-effort)
        try:
            import urllib.request, json as _json
            with urllib.request.urlopen(f'http://{host}:{port}/api/mcp/status', timeout=1.5) as r:
                raw = r.read().decode('utf-8', 'ignore')
                j = _json.loads(raw)
                data = j.get('data') or j
                tools = (data or {}).get('total_tools')
                initialized = (data or {}).get('initialized')
                print(f"HTTP status: ok initialized={initialized} tools={tools}")
        except Exception as e:  # pragma: no cover
            print(f"HTTP status: unavailable ({e.__class__.__name__})")

async def main():
    """
    Main entry point for the JIT CLI.
    """
    cli = FastCLI()
    await cli.run()

if __name__ == "__main__":
    asyncio.run(main())

# Synchronous entrypoint for packaging scripts (pyproject points here)
def sync_main():  # pragma: no cover
    import asyncio as _asyncio
    return _asyncio.run(main())
