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
        
        return parser

    async def run(self) -> None:
        args = self.parser.parse_args()
        if not args.command:
            self.parser.print_help(); sys.exit(2)
        
        # Handle both mcp_action and daemon_action
        if args.command == "mcp":
            sub_action = getattr(args, "mcp_action", None)
            handler = getattr(self, f"handle_mcp_{sub_action}", None) if sub_action else None
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
            if asyncio.iscoroutinefunction(run_method):
                await run_method()
            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, run_method)
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
                from mcp.ipfs_kit.daemon.ipfs_kit_daemon import IPFSKitDaemon
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


async def main() -> None:
    cli = FastCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())


def sync_main():  # pragma: no cover
    return asyncio.run(main())
