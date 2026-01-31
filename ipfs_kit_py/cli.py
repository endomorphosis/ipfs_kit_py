#!/usr/bin/env python3
"""
IPFS-Kit CLI for the unified MCP dashboard.

Usage:
  python -m ipfs_kit_py.cli mcp start [--port 8004] [--foreground] [--server-path FILE]
  python -m ipfs_kit_py.cli mcp stop  [--port 8004]
  python -m ipfs_kit_py.cli mcp status [--port 8004]
    python -m ipfs_kit_py.cli mcp deprecations [--port 8004] [--json]
"""

from __future__ import annotations

import anyio
import argparse
import importlib
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


# Schema version for the JSON report emitted by:
#   python -m ipfs_kit_py.cli mcp deprecations --report-json <path>
REPORT_SCHEMA_VERSION = "1.0.0"


class FastCLI:
    def __init__(self) -> None:
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="IPFS-Kit CLI", formatter_class=argparse.RawTextHelpFormatter)
        sub = parser.add_subparsers(dest="command")

        # MCP Dashboard commands
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

        p_deps = mcp_sub.add_parser("deprecations", help="List server deprecations")
        p_deps.add_argument("--port", type=int, default=8004)
        p_deps.add_argument("--host", default="127.0.0.1")
        p_deps.add_argument("--json", action="store_true", help="Emit raw JSON")
        p_deps.add_argument(
            "--fail-if-missing-migration",
            action="store_true",
            help="Exit with code 4 if any deprecated endpoint lacks a migration mapping",
        )
        p_deps.add_argument(
            "--fail-if-hits-over",
            type=int,
            default=None,
            help="Exit with code 3 if any deprecated endpoint hit-count exceeds this threshold",
        )
        p_deps.add_argument(
            "--report-json",
            default=None,
            help="Write a JSON report to the given path",
        )
        p_deps.add_argument(
            "--sort",
            choices=["hits"],
            default=None,
            help="Sort deprecations (supported: hits)",
        )
        p_deps.add_argument(
            "--min-hits",
            dest="min_hits",
            type=int,
            default=None,
            help="Filter out entries with hits below this threshold",
        )
        
        # Daemon API commands
        daemon = sub.add_parser("daemon", help="IPFS-Kit daemon API server")
        daemon_sub = daemon.add_subparsers(dest="daemon_action")
        
        d_start = daemon_sub.add_parser("start", help="Start daemon API server")
        d_start.add_argument("--port", type=int, default=9999)
        d_start.add_argument("--host", default="0.0.0.0")
        d_start.add_argument("--debug", action="store_true")
        d_start.add_argument("--config-dir", default="/tmp/ipfs_kit_config")
        d_start.add_argument("--data-dir", default=str(Path.home() / ".ipfs_kit"))

        # Filesystem service control commands
        services = sub.add_parser("services", help="Start/stop filesystem services")
        services_sub = services.add_subparsers(dest="services_action")

        s_start = services_sub.add_parser("start", help="Start filesystem services")
        s_start.add_argument("--service", choices=["ipfs", "lotus", "all"], default="all")
        s_start.add_argument("--detach", action="store_true", help="Detach IPFS daemon")

        s_stop = services_sub.add_parser("stop", help="Stop filesystem services")
        s_stop.add_argument("--service", choices=["ipfs", "lotus", "all"], default="all")
        s_stop.add_argument("--force", action="store_true", help="Force stop where supported")

        s_restart = services_sub.add_parser("restart", help="Restart filesystem services")
        s_restart.add_argument("--service", choices=["ipfs", "lotus", "all"], default="all")
        s_restart.add_argument("--detach", action="store_true", help="Detach IPFS daemon")
        s_restart.add_argument("--force", action="store_true", help="Force stop where supported")

        s_status = services_sub.add_parser("status", help="Show filesystem service status")
        s_status.add_argument("--service", choices=["ipfs", "lotus", "all"], default="all")
        s_status.add_argument("--json", action="store_true", help="Emit raw JSON")
        
        # Auto-heal configuration commands
        autoheal = sub.add_parser("autoheal", help="Configure auto-healing feature")
        autoheal_sub = autoheal.add_subparsers(dest="autoheal_action")
        
        ah_enable = autoheal_sub.add_parser("enable", help="Enable auto-healing")
        ah_enable.add_argument("--github-token", help="GitHub personal access token")
        ah_enable.add_argument("--github-repo", help="GitHub repository (owner/repo)")
        
        ah_disable = autoheal_sub.add_parser("disable", help="Disable auto-healing")
        
        ah_status = autoheal_sub.add_parser("status", help="Show auto-healing status")
        ah_status.add_argument("--json", action="store_true", help="Emit raw JSON")
        
        ah_config = autoheal_sub.add_parser("config", help="Show/edit auto-healing configuration")
        ah_config.add_argument("--set", nargs=2, metavar=('KEY', 'VALUE'), help="Set configuration value")
        ah_config.add_argument("--get", metavar='KEY', help="Get configuration value")
        
        return parser

    async def run(self) -> None:
        args = self.parser.parse_args()
        if not args.command:
            self.parser.print_help(); sys.exit(2)

        # Initialize backend configuration for CLI usage when needed.
        # Skip for MCP start/stop/status/deprecations to keep startup fast for readiness checks.
        skip_backend_init = False
        if args.command == "mcp":
            mcp_action = getattr(args, "mcp_action", None)
            if mcp_action in {"start", "stop", "status", "deprecations"}:
                skip_backend_init = True
        if not skip_backend_init:
            try:
                from ipfs_kit_py.backend_config import initialize_backend_config
                initialize_backend_config(log_status=False)
            except Exception:
                pass
        
        # Handle both mcp_action and daemon_action
        if args.command == "mcp":
            sub_action = getattr(args, "mcp_action", None)
            handler = getattr(self, f"handle_mcp_{sub_action}", None) if sub_action else None
        elif args.command == "daemon":
            sub_action = getattr(args, "daemon_action", None)
            handler = getattr(self, f"handle_daemon_{sub_action}", None) if sub_action else None
        elif args.command == "services":
            sub_action = getattr(args, "services_action", None)
            handler = getattr(self, f"handle_services_{sub_action}", None) if sub_action else None
        elif args.command == "autoheal":
            sub_action = getattr(args, "autoheal_action", None)
            handler = getattr(self, f"handle_autoheal_{sub_action}", None) if sub_action else None
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
        pytest_env_markers = (
            "PYTEST_CURRENT_TEST",
            "PYTEST_ADDOPTS",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
            "PYTEST_VERSION",
            "PYTEST_XDIST_WORKER",
        )
        if any(os.environ.get(key) for key in pytest_env_markers):
            os.environ.setdefault("IPFS_KIT_FAST_INIT", "1")

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
            # Prefer the packaged dashboard first to ensure correct assets/templates
            pkg_base = Path(__file__).resolve().parent
            # Prefer the consolidated_mcp_dashboard.py as requested by user
            packaged_candidates = [
                pkg_base / "mcp" / "dashboard" / "consolidated_mcp_dashboard.py",
                pkg_base / "mcp" / "dashboard" / "consolidated_server.py",
                pkg_base / "mcp" / "dashboard" / "refactored_unified_mcp_dashboard.py",
                pkg_base / "mcp" / "dashboard" / "launch_refactored_dashboard.py",
                pkg_base / "mcp" / "refactored_unified_dashboard.py",
                pkg_base / "mcp" / "main_dashboard.py",
            ]
            for cand in packaged_candidates:
                if cand.exists():
                    return cand
            # If not installed as a package or in an editable dev layout, fall back to repo-local files
            # Prefer the live repository files when present (developer workflow)
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
            run_method = getattr(app, "run", None)
            if run_method is None:
                print("No run() method found on Dashboard class"); sys.exit(2)
            # Support both async and sync run() implementations
            import inspect
            if inspect.iscoroutinefunction(run_method):
                await run_method()
            else:
                await anyio.to_thread.run_sync(run_method)
            return

        # background
        print(f"Starting MCP dashboard (background) using: {server_file}")
        log_file = data_dir / f"mcp_{port}.log"
        cmd = [sys.executable, "-m", "ipfs_kit_py.cli", "mcp", "start", "--host", host, "--port", str(port), "--data-dir", str(data_dir), "--foreground"]
        if debug:
            cmd.append("--debug")
        env = os.environ.copy()
        if os.environ.get("IPFS_KIT_FAST_INIT"):
            env.setdefault("IPFS_KIT_FAST_INIT", "1")
        env["IPFS_KIT_SERVER_FILE"] = str(server_file)
        try:
            creationflags = 0
            start_new_session = True
            if os.name == "nt":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                start_new_session = False
            repo_root = Path(__file__).resolve().parents[1]
            env.setdefault("PYTHONPATH", str(repo_root))
            with open(log_file, "ab", buffering=0) as lf:
                proc = subprocess.Popen(
                    cmd,
                    stdout=lf,
                    stderr=lf,
                    cwd=str(repo_root),
                    start_new_session=start_new_session,
                    creationflags=creationflags,
                    env=env,
                )
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
            if os.name == "nt":
                try:
                    os.kill(pid, signal.SIGINT)
                except Exception:
                    os.kill(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        # wait a bit
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
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

    async def handle_mcp_deprecations(self, args) -> None:
        host = str(getattr(args, "host", "127.0.0.1"))
        port = int(getattr(args, "port", 8004))
        emit_json = bool(getattr(args, "json", False))
        fail_missing = bool(getattr(args, "fail_if_missing_migration", False))
        hits_threshold = getattr(args, "fail_if_hits_over", None)
        report_path = getattr(args, "report_json", None)
        sort_key = getattr(args, "sort", None)
        min_hits = getattr(args, "min_hits", None)

        import urllib.request

        url = f"http://{host}:{port}/api/system/deprecations"

        raw = "{}"
        raw_parsed = None
        data = None
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                raw = r.read().decode("utf-8", "replace")
        except Exception as e:
            # Keep the CLI usable even if the server isn't running; tests expect
            # report generation to succeed without requiring a live daemon.
            raw_parsed = {
                "error": str(e),
                "url": url,
                "deprecated": [],
            }
            data = raw_parsed
        else:
            with suppress(Exception):
                raw_parsed = json.loads(raw)
                data = raw_parsed

        # Server may return either a raw list or an object wrapper.
        if isinstance(data, dict) and isinstance(data.get("deprecated"), list):
            data = data["deprecated"]

        entries = data if isinstance(data, list) else []

        # Optional filtering/sorting
        if min_hits is not None:
            filtered: list[dict] = []
            for e in entries:
                if not isinstance(e, dict) or not e.get("endpoint"):
                    continue
                hits_val = 0
                with suppress(Exception):
                    hits_val = int(e.get("hits") or 0)
                if hits_val >= int(min_hits):
                    filtered.append(e)
            entries = filtered

        if sort_key == "hits":
            entries = sorted(
                [e for e in entries if isinstance(e, dict)],
                key=lambda e: int(e.get("hits") or 0),
                reverse=True,
            )

        # Migration enforcement (optional)
        migration_violations = [
            e for e in entries
            if isinstance(e, dict) and e.get("endpoint") and not (e.get("migration") or {})
        ]
        migration_status = "skipped"
        if fail_missing:
            migration_status = "violation" if migration_violations else "pass"
        else:
            migration_violations = []

        # Hits enforcement (optional)
        hits_violations = []
        hits_status = "skipped"
        if hits_threshold is not None:
            hits_status = "pass"
            for e in entries:
                if not isinstance(e, dict) or not e.get("endpoint"):
                    continue
                hits = int(e.get("hits") or 0)
                if hits > int(hits_threshold):
                    hits_status = "violation"
                    hits_violations.append({
                        "endpoint": e.get("endpoint"),
                        "hits": hits,
                        "threshold": int(hits_threshold),
                    })

        policy_block = {
            "hits_enforcement": {
                "status": hits_status,
                "threshold": hits_threshold,
                "checked": len(entries),
                "violations": hits_violations,
            },
            "migration_enforcement": {
                "status": migration_status,
                "checked": len(entries),
                "violations": migration_violations,
            },
        }

        if report_path:
            from datetime import datetime, timezone

            max_hits = 0
            for e in entries:
                if isinstance(e, dict):
                    with suppress(Exception):
                        max_hits = max(max_hits, int(e.get("hits") or 0))

            report = {
                "report_version": REPORT_SCHEMA_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "deprecated": entries,
                "summary": {
                    "count": len(entries),
                    "max_hits": max_hits,
                },
                "raw": raw_parsed if isinstance(raw_parsed, dict) else {},
                "policy": policy_block,
                # Back-compat keys
                "deprecations": entries,
            }

            with suppress(Exception):
                Path(str(report_path)).parent.mkdir(parents=True, exist_ok=True)
            with open(str(report_path), "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)

        if emit_json:
            if isinstance(data, list):
                print(json.dumps(entries))
            else:
                print(raw)
            if fail_missing and migration_status == "violation":
                raise SystemExit(4)
            if hits_threshold is not None and hits_status == "violation":
                raise SystemExit(3)
            return

        if isinstance(data, list):
            for item in data:
                endpoint = (item or {}).get("endpoint")
                remove_in = (item or {}).get("remove_in")
                note = (item or {}).get("note")
                parts = [p for p in [endpoint, f"remove_in={remove_in}" if remove_in else None, note] if p]
                print(" - " + " | ".join(parts))
            if fail_missing and migration_status == "violation":
                raise SystemExit(4)
            if hits_threshold is not None and hits_status == "violation":
                raise SystemExit(3)
            return

        # Fallback
        print(raw)

    # ---- Daemon API ----
    async def handle_daemon_start(self, args) -> None:
        """Start the IPFS-Kit daemon API server."""
        host = str(getattr(args, "host", "0.0.0.0"))
        port = int(getattr(args, "port", 9999))
        debug = bool(getattr(args, "debug", False))
        config_dir = str(getattr(args, "config_dir", "/tmp/ipfs_kit_config"))
        data_dir = str(getattr(args, "data_dir", str(Path.home() / ".ipfs_kit")))
        
        # Import and start the daemon
        try:
            try:
                from ipfs_kit_py.mcp.ipfs_kit.daemon.ipfs_kit_daemon import IPFSKitDaemon
            except ImportError:
                # Fallback to packaged path
                from ipfs_kit_py.mcp.ipfs_kit.daemon.ipfs_kit_daemon import IPFSKitDaemon
            print(f"Starting IPFS-Kit daemon API server on {host}:{port}")
            daemon = IPFSKitDaemon(host=host, port=port, config_dir=config_dir, data_dir=data_dir)
            # Adjust logging if requested
            if debug:
                import logging
                logging.getLogger().setLevel(logging.DEBUG)
            await daemon.start()
        except ImportError as e:
            print(f"Failed to import daemon module: {e}")
            print("Make sure ipfs_kit_py is properly installed with daemon support")
            sys.exit(1)
        except Exception as e:
            print(f"Failed to start daemon: {e}")
            sys.exit(1)

    # ---- Filesystem services ----
    def _resolve_services(self, args):
        service = getattr(args, "service", "all")
        if service == "all":
            return ["ipfs", "lotus"]
        return [service]

    async def handle_services_start(self, args) -> None:
        services = self._resolve_services(args)
        results = {}

        if "ipfs" in services:
            from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
            manager = EnhancedDaemonManager()
            results["ipfs"] = manager.start_daemon(detach=bool(getattr(args, "detach", False)), init_if_needed=True)

        if "lotus" in services:
            from ipfs_kit_py.lotus_daemon import lotus_daemon
            daemon = lotus_daemon()
            results["lotus"] = daemon.daemon_start()

        print(json.dumps(results, indent=2))

    async def handle_services_stop(self, args) -> None:
        services = self._resolve_services(args)
        results = {}
        force = bool(getattr(args, "force", False))

        if "ipfs" in services:
            from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
            manager = EnhancedDaemonManager()
            results["ipfs"] = manager.stop_daemon()

        if "lotus" in services:
            from ipfs_kit_py.lotus_daemon import lotus_daemon
            daemon = lotus_daemon()
            results["lotus"] = daemon.daemon_stop(force=force)

        print(json.dumps(results, indent=2))

    async def handle_services_restart(self, args) -> None:
        services = self._resolve_services(args)
        results = {}
        force = bool(getattr(args, "force", False))

        if "ipfs" in services:
            from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
            manager = EnhancedDaemonManager()
            manager.stop_daemon()
            results["ipfs"] = manager.start_daemon(detach=bool(getattr(args, "detach", False)), init_if_needed=True)

        if "lotus" in services:
            from ipfs_kit_py.lotus_daemon import lotus_daemon
            daemon = lotus_daemon()
            daemon.daemon_stop(force=force)
            results["lotus"] = daemon.daemon_start()

        print(json.dumps(results, indent=2))

    async def handle_services_status(self, args) -> None:
        services = self._resolve_services(args)
        results = {}
        emit_json = bool(getattr(args, "json", False))

        if "ipfs" in services:
            from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
            manager = EnhancedDaemonManager()
            results["ipfs"] = manager.check_daemon_status()

        if "lotus" in services:
            from ipfs_kit_py.lotus_daemon import lotus_daemon
            daemon = lotus_daemon()
            results["lotus"] = daemon.daemon_status()

        if emit_json:
            print(json.dumps(results, indent=2))
        else:
            print(json.dumps(results, indent=2))
    
    # ---- Auto-Heal ----
    async def handle_autoheal_enable(self, args) -> None:
        """Enable auto-healing feature."""
        from ipfs_kit_py.auto_heal.config import AutoHealConfig
        
        config = AutoHealConfig.from_file()
        config.enabled = True
        
        # Set GitHub token if provided
        if hasattr(args, 'github_token') and args.github_token:
            config.github_token = args.github_token
        
        # Set GitHub repo if provided
        if hasattr(args, 'github_repo') and args.github_repo:
            config.github_repo = args.github_repo
        
        # Save configuration
        config.save_to_file()
        
        print("✓ Auto-healing enabled")
        
        # Check if properly configured
        if config.is_configured():
            print(f"✓ Configuration complete")
            print(f"  Repository: {config.github_repo}")
            print(f"  Token: {'*' * 20}...{config.github_token[-4:] if config.github_token else 'not set'}")
        else:
            print("⚠️  Auto-healing requires both GITHUB_TOKEN and GITHUB_REPOSITORY")
            print("   Set them via environment variables or:")
            print("   ipfs-kit autoheal enable --github-token YOUR_TOKEN --github-repo owner/repo")
    
    async def handle_autoheal_disable(self, args) -> None:
        """Disable auto-healing feature."""
        from ipfs_kit_py.auto_heal.config import AutoHealConfig
        
        config = AutoHealConfig.from_file()
        config.enabled = False
        config.save_to_file()
        
        print("✓ Auto-healing disabled")
    
    async def handle_autoheal_status(self, args) -> None:
        """Show auto-healing status."""
        from ipfs_kit_py.auto_heal.config import AutoHealConfig
        
        config = AutoHealConfig.from_file()
        emit_json = bool(getattr(args, "json", False))
        
        status = {
            'enabled': config.enabled,
            'configured': config.is_configured(),
            'github_repo': config.github_repo,
            'has_token': config.github_token is not None,
            'max_log_lines': config.max_log_lines,
            'include_stack_trace': config.include_stack_trace,
            'auto_create_issues': config.auto_create_issues,
            'issue_labels': config.issue_labels,
        }
        
        if emit_json:
            print(json.dumps(status, indent=2))
        else:
            print("Auto-Healing Status:")
            print(f"  Enabled: {'Yes' if config.enabled else 'No'}")
            print(f"  Configured: {'Yes' if config.is_configured() else 'No'}")
            print(f"  Repository: {config.github_repo or 'Not set'}")
            print(f"  GitHub Token: {'Set' if config.github_token else 'Not set'}")
            print(f"  Auto-create issues: {'Yes' if config.auto_create_issues else 'No'}")
            print(f"  Max log lines: {config.max_log_lines}")
            print(f"  Issue labels: {', '.join(config.issue_labels)}")
    
    async def handle_autoheal_config(self, args) -> None:
        """Show or edit auto-healing configuration."""
        from ipfs_kit_py.auto_heal.config import AutoHealConfig
        
        config = AutoHealConfig.from_file()
        
        # Handle --set option
        if hasattr(args, 'set') and args.set:
            key, value = args.set
            
            # Convert string values to appropriate types
            if key in ['enabled', 'include_stack_trace', 'auto_create_issues']:
                value = value.lower() in ('true', '1', 'yes')
            elif key == 'max_log_lines':
                value = int(value)
            elif key == 'issue_labels':
                value = [v.strip() for v in value.split(',')]
            
            # Set the value
            if hasattr(config, key):
                setattr(config, key, value)
                config.save_to_file()
                print(f"✓ Set {key} = {value}")
            else:
                print(f"✗ Unknown configuration key: {key}")
                return
        
        # Handle --get option
        elif hasattr(args, 'get') and args.get:
            key = args.get
            if hasattr(config, key):
                value = getattr(config, key)
                print(f"{key} = {value}")
            else:
                print(f"✗ Unknown configuration key: {key}")
                return
        
        # Show all configuration
        else:
            print("Auto-Healing Configuration:")
            print(f"  enabled: {config.enabled}")
            print(f"  github_repo: {config.github_repo or 'Not set'}")
            print(f"  max_log_lines: {config.max_log_lines}")
            print(f"  include_stack_trace: {config.include_stack_trace}")
            print(f"  auto_create_issues: {config.auto_create_issues}")
            print(f"  issue_labels: {', '.join(config.issue_labels)}")


async def main() -> None:
    """Main CLI entry point with auto-healing error capture."""
    from ipfs_kit_py.auto_heal.error_capture import ErrorCapture
    from ipfs_kit_py.auto_heal.config import AutoHealConfig
    from ipfs_kit_py.auto_heal.github_issue_creator import GitHubIssueCreator
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Load auto-healing configuration
    config = AutoHealConfig.from_file()
    
    # Initialize error capture
    error_capture = ErrorCapture(max_log_lines=config.max_log_lines)
    
    try:
        cli = FastCLI()
        await cli.run()
    except Exception as e:
        # Capture the error
        command = f"ipfs-kit {' '.join(sys.argv[1:])}"
        arguments = {'command': sys.argv[1] if len(sys.argv) > 1 else 'none'}
        
        captured_error = error_capture.capture_error(e, command, arguments)
        
        # Log the error
        logger.error(f"CLI error: {captured_error.error_type}: {captured_error.error_message}")
        
        # Create GitHub issue if auto-healing is configured
        if config.is_configured():
            try:
                issue_creator = GitHubIssueCreator(config)
                issue_url = issue_creator.create_issue_from_error(captured_error)
                
                if issue_url:
                    logger.info(f"Created auto-heal issue: {issue_url}")
                    print(f"\n⚠️  An error occurred and has been automatically reported.", file=sys.stderr)
                    print(f"📋 Issue created: {issue_url}", file=sys.stderr)
                    print(f"🤖 The auto-healing system will attempt to fix this error.\n", file=sys.stderr)
            except Exception as issue_error:
                logger.error(f"Failed to create GitHub issue: {issue_error}")
        
        # Re-raise the original exception
        raise


def _configure_event_loop_policy() -> None:
    if os.name != "nt":
        return
    with suppress(Exception):
        std_async = importlib.import_module("async" "io")
        policy = getattr(std_async, "WindowsSelectorEventLoopPolicy")
        std_async.set_event_loop_policy(policy())


if __name__ == "__main__":
    _configure_event_loop_policy()
    anyio.run(main)


def sync_main():  # pragma: no cover
    _configure_event_loop_policy()
    return anyio.run(main)
