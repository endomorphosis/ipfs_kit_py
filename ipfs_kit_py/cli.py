#!/usr/bin/env python3
"""IPFS-Kit CLI for the unified MCP dashboard and utilities.

Examples:
    python -m ipfs_kit_py.cli mcp start --port 8004
    python -m ipfs_kit_py.cli mcp status
    python -m ipfs_kit_py.cli mcp deprecations --json
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
from datetime import datetime, timezone
from contextlib import suppress
from pathlib import Path
from typing import Optional, Callable, Awaitable


class FastCLI:
    """Small async-friendly CLI wrapper.

    We keep logic self‑contained to avoid accidental indentation corruption.
    """

    def __init__(self) -> None:
        self.parser = self._create_parser()

    # ------------------------------------------------------------------
    # Parser
    # ------------------------------------------------------------------
    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description="IPFS-Kit CLI",
            formatter_class=argparse.RawTextHelpFormatter,
        )
        sub = parser.add_subparsers(dest="command")

        # mcp group
        mcp = sub.add_parser("mcp", help="MCP server and dashboard commands")
        mcp_sub = mcp.add_subparsers(dest="mcp_action")

        # start
        p_start = mcp_sub.add_parser("start", help="Start MCP dashboard/server")
        p_start.add_argument("--port", type=int, default=8004)
        p_start.add_argument("--host", default="127.0.0.1")
        p_start.add_argument("--debug", action="store_true")
        p_start.add_argument("--foreground", action="store_true", help="Run in foreground (no subprocess)")
        p_start.add_argument("--data-dir", default=str(Path.home() / ".ipfs_kit"))
        p_start.add_argument("--server-path", default=None, help="Explicit path to dashboard server file")

        # stop
        p_stop = mcp_sub.add_parser("stop", help="Stop MCP dashboard/server")
        p_stop.add_argument("--port", type=int, default=8004)
        p_stop.add_argument("--data-dir", default=str(Path.home() / ".ipfs_kit"))

        # status
        p_status = mcp_sub.add_parser("status", help="Show MCP server status")
        p_status.add_argument("--port", type=int, default=8004)
        p_status.add_argument("--host", default="127.0.0.1")
        p_status.add_argument("--data-dir", default=str(Path.home() / ".ipfs_kit"))

        # deprecations
        p_deps = mcp_sub.add_parser("deprecations", help="List deprecated HTTP endpoints (with hit counts)")
        p_deps.add_argument("--port", type=int, default=8004)
        p_deps.add_argument("--host", default="127.0.0.1")
        p_deps.add_argument("--json", action="store_true", help="Output raw JSON instead of table")
        p_deps.add_argument("--sort", choices=["endpoint", "remove_in", "hits"], help="Sort column (default: original order)")
        p_deps.add_argument("--reverse", action="store_true", help="Reverse sort order (use with --sort)")
        p_deps.add_argument("--min-hits", type=int, default=0, help="Filter: only show endpoints with at least this many hits")
        p_deps.add_argument("--fail-if-hits-over", type=int, default=None, dest="fail_hits",
                            help="Exit with code 3 if any deprecated endpoint has hits greater than this threshold (policy enforcement / CI)")
        p_deps.add_argument("--report-json", metavar="PATH", default=None,
                            help="Write a machine-readable JSON report to PATH (includes list, raw response, timestamp, summary). Does not affect stdout format unless --json specified.")
        p_deps.add_argument("--fail-if-missing-migration", action="store_true", dest="fail_missing_migration",
                            help="Exit with code 4 if any deprecated endpoint lacks a migration hint (policy enforcement / CI)")

        return parser

    # ------------------------------------------------------------------
    async def run(self, argv: Optional[list[str]] = None) -> None:
        args = self.parser.parse_args(argv)
        if not getattr(args, "command", None):
            self.parser.print_help(); return
        if args.command == "mcp" and not getattr(args, "mcp_action", None):
            self.parser.print_help(); return
        # Resolve handler name
        mcp_action = getattr(args, "mcp_action", None)
        handler_name = f"handle_{args.command}_{mcp_action}" if mcp_action else f"handle_{args.command}"
        handler: Optional[Callable[[object], Awaitable[None]]] = getattr(self, handler_name, None)
        if handler is None:
            print(f"Unknown command: {handler_name}")
            self.parser.print_help(); return
        await handler(args)

    # ------------------------------------------------------------------
    # MCP handlers
    # ------------------------------------------------------------------
    async def handle_mcp_start(self, args) -> None:
        host = str(args.host)
        port = int(args.port)
        debug = bool(args.debug)
        data_dir = Path(args.data_dir).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)

        def detect_server_file() -> Optional[Path]:
            explicit = getattr(args, "server_path", None)
            if explicit:
                p = Path(explicit).expanduser().resolve()
                if p.exists():
                    return p
            envp = os.environ.get("IPFS_KIT_SERVER_FILE")
            if envp:
                p = Path(envp).expanduser().resolve()
                if p.exists():
                    return p
            # search common names
            search_roots = [Path(__file__).resolve().parents[1], Path.cwd()]
            candidates = [
                "consolidated_mcp_dashboard.py",
                "unified_mcp_dashboard.py",
                "modernized_comprehensive_dashboard.py",
            ]
            for root in search_roots:
                for name in candidates:
                    cand = root / name
                    if cand.exists():
                        return cand
            return None

        server_file = detect_server_file()
        if not server_file:
            print("No server file found. Use --server-path or set IPFS_KIT_SERVER_FILE.")
            sys.exit(2)

        pid_file_main = data_dir / f"mcp_{port}.pid"
        pid_file_alt = data_dir / "dashboard.pid"

        if args.foreground:
            print(f"Starting MCP dashboard (foreground) using: {server_file}")
            spec = importlib.util.spec_from_file_location(server_file.stem, str(server_file))
            if not spec or not spec.loader:  # pragma: no cover - defensive
                print("Failed to load server module spec")
                sys.exit(2)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[attr-defined]
            DashboardClass = getattr(mod, "ConsolidatedMCPDashboard", None)
            if DashboardClass is None:
                for n, obj in vars(mod).items():
                    if n.endswith("Dashboard") and callable(getattr(obj, "__init__", None)):
                        DashboardClass = obj
                        break
            if DashboardClass is None:
                print("No Dashboard class found in server file")
                sys.exit(2)
            app = DashboardClass({"host": host, "port": port, "data_dir": str(data_dir), "debug": debug})
            await app.run()
            return

        # background spawn
        print(f"Starting MCP dashboard (background) using: {server_file}")
        log_file = data_dir / f"mcp_{port}.log"
        cmd = [
            sys.executable,
            "-m",
            "ipfs_kit_py.cli",
            "mcp",
            "start",
            "--host", host,
            "--port", str(port),
            "--data-dir", str(data_dir),
            "--foreground",
        ]
        if debug:
            cmd.append("--debug")
        env = os.environ.copy()
        env["IPFS_KIT_SERVER_FILE"] = str(server_file)
        try:
            with open(log_file, "ab", buffering=0) as lf:
                proc = subprocess.Popen(
                    cmd,
                    stdout=lf,
                    stderr=lf,
                    cwd=server_file.parent,
                    start_new_session=True,
                    env=env,
                )
        except Exception as e:  # pragma: no cover - launch failure path
            print(f"Failed to launch: {e}")
            sys.exit(1)
        # wait for readiness (pid file or health probe)
        deadline = time.time() + 15
        ready = False
        pid = None
        while time.time() < deadline and not ready:
            if pid_file_main.exists() or pid_file_alt.exists():
                with suppress(Exception):
                    pf = pid_file_main if pid_file_main.exists() else pid_file_alt
                    pid = int(pf.read_text().strip())
                ready = True
                break
            with suppress(Exception):
                import urllib.request  # local import to avoid upfront dependency for pure CLI ops
                with urllib.request.urlopen(f"http://{host}:{port}/healthz", timeout=1.5) as r:
                    if r.status == 200:
                        ready = True
                        break
            time.sleep(0.3)
        if ready:
            print(f"MCP started: pid={pid or proc.pid} http://{host}:{port} (log: {log_file})")
        else:
            print(f"MCP launch initiated (child pid {proc.pid}) on http://{host}:{port}. Logs: {log_file}")

    async def handle_mcp_stop(self, args) -> None:
        port = int(args.port)
        data_dir = Path(args.data_dir).expanduser()
        pid_file_main = data_dir / f"mcp_{port}.pid"
        pf = pid_file_main if pid_file_main.exists() else None
        if not pf:
            print(f"No PID file found for port {port} at {pid_file_main}")
            return
        pid = None
        with suppress(Exception):
            pid = int(Path(pf).read_text().strip())
        if not pid:
            print("PID file unreadable")
            return
        with suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)
        deadline = time.time() + 5
        while time.time() < deadline and Path(f"/proc/{pid}").exists():
            time.sleep(0.1)
        with suppress(Exception):
            Path(pf).unlink()
        print(f"MCP server on port {port} stopped (or already not running)")

    async def handle_mcp_status(self, args) -> None:
        host = str(args.host)
        port = int(args.port)
        data_dir = Path(args.data_dir).expanduser()
        pid_file_main = data_dir / f"mcp_{port}.pid"
        pf = pid_file_main if pid_file_main.exists() else None
        info = {"pidFile": str(pid_file_main), "pid": None, "http": None}
        if pf and Path(pf).exists():
            with suppress(Exception):
                info["pid"] = int(Path(pf).read_text().strip())
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/api/mcp/status", timeout=2.5) as r:
                raw = r.read().decode("utf-8", "ignore")
                with suppress(Exception):
                    info["http"] = json.loads(raw)
        except Exception:
            with suppress(Exception):
                with urllib.request.urlopen(f"http://{host}:{port}/healthz", timeout=1.5) as r:
                    info["http"] = {"ok": (r.status == 200)}
        print(json.dumps(info, indent=2))

    async def handle_mcp_deprecations(self, args) -> None:
        host = str(args.host)
        port = int(args.port)
        url = f"http://{host}:{port}/api/system/deprecations"
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=3.0) as r:
                raw = r.read().decode("utf-8", "ignore")
        except Exception as e:
            print(json.dumps({"error": f"Failed to connect: {e}"}, indent=2))
            return
        try:
            js = json.loads(raw)
        except Exception as e:
            print(json.dumps({"error": f"Invalid JSON: {e}", "raw": raw[:400]}, indent=2))
            return
        items = js.get("deprecated") if isinstance(js, dict) else None
        # Apply filtering / sorting before any output
        if items:
            # Filter on min-hits
            if getattr(args, "min_hits", 0) > 0:
                min_hits = int(args.min_hits)
                items = [it for it in items if (it.get("hits") or 0) >= min_hits]

            # Sorting logic
            sort_key = getattr(args, "sort", None)
            if sort_key:
                def parse_version(v: str):
                    if not isinstance(v, str):
                        return (str(v),)
                    parts = []
                    for p in v.split('.'):
                        if p.isdigit():
                            parts.append(int(p))
                        else:
                            # split numeric prefix if any
                            num = ''
                            suf = p
                            for ch in p:
                                if ch.isdigit():
                                    num += ch
                                else:
                                    break
                            if num:
                                try:
                                    parts.append(int(num))
                                    suf = p[len(num):]
                                except ValueError:
                                    parts.append(p)
                            if suf:
                                parts.append(suf)
                    return tuple(parts) if parts else (v,)

                def key_func(it):
                    if sort_key == 'hits':
                        return it.get('hits') or 0
                    if sort_key == 'endpoint':
                        return str(it.get('endpoint'))
                    if sort_key == 'remove_in':
                        return parse_version(it.get('remove_in'))
                    return 0

                items = sorted(items, key=key_func, reverse=bool(getattr(args, 'reverse', False)))

        # Prepare report output (before printing) if requested
        report_path = getattr(args, 'report_json', None)
        report_written = False
        # Schema/report version (increment on backward-incompatible structure changes)
        REPORT_SCHEMA_VERSION = "1.0.0"
        if report_path:
            try:
                deps_list = items or []
                max_hits = max((d.get('hits') or 0) for d in deps_list) if deps_list else 0
                # Pre-build policy evaluation (without triggering exit yet)
                threshold = getattr(args, 'fail_hits', None)
                violations = []
                policy_status = 'skipped'
                threshold_val = None
                if threshold is not None:
                    try:
                        threshold_val = int(threshold)
                    except Exception:
                        threshold_val = None
                    if threshold_val is not None:
                        for d in deps_list:
                            h = d.get('hits') or 0
                            if h > threshold_val:
                                violations.append({
                                    'endpoint': d.get('endpoint'),
                                    'hits': h,
                                    'remove_in': d.get('remove_in'),
                                    'threshold': threshold_val,
                                })
                        policy_status = 'violation' if violations else 'pass'
                # Migration enforcement evaluation
                missing_migration = []
                mig_status = 'skipped'
                if getattr(args, 'fail_missing_migration', False):
                    if deps_list:
                        for d in deps_list:
                            if not d.get('migration'):
                                missing_migration.append({
                                    'endpoint': d.get('endpoint'),
                                    'remove_in': d.get('remove_in'),
                                    'hits': d.get('hits'),
                                })
                        mig_status = 'violation' if missing_migration else 'pass'
                report_obj = {
                    'generated_at': datetime.now(timezone.utc).isoformat(),
                    'report_version': REPORT_SCHEMA_VERSION,
                    'deprecated': deps_list,
                    'summary': {
                        'count': len(deps_list),
                        'max_hits': max_hits,
                    },
                    'policy': {
                        'hits_enforcement': {
                            'status': policy_status,
                            'threshold': threshold_val,
                            'violations': violations,
                        },
                        'migration_enforcement': {
                            'status': mig_status,
                            'violations': missing_migration,
                        }
                    },
                    'raw': js,
                }
                rp = Path(report_path).expanduser()
                rp.parent.mkdir(parents=True, exist_ok=True)
                rp.write_text(json.dumps(report_obj, indent=2), encoding='utf-8')
                report_written = True
            except Exception as e:  # pragma: no cover - I/O failure path
                print(f"Warning: failed to write report JSON: {e}", file=sys.stderr)

        if args.json:
            print(json.dumps(items, indent=2))
            return
        if not items:
            print("No deprecated endpoints.")
            # still exit code logic may apply, but with no items only violation if threshold < 0 (not possible). Write report already handled.
            return
        rows = [(it.get("endpoint"), it.get("remove_in"), it.get("hits"), it.get("migration")) for it in items]
        w_ep = max(len("Endpoint"), *(len(str(r[0])) for r in rows))
        w_rm = max(len("Remove In"), *(len(str(r[1])) for r in rows))
        w_hits = max(len("Hits"), *(len(str(r[2])) for r in rows))

        def fmt_mig(m):
            if not m:
                return "-"
            if isinstance(m, dict):
                return ",".join(f"{k}:{v}" for k, v in m.items())
            return str(m)

        print(f"{'Endpoint'.ljust(w_ep)}  {'Remove In'.ljust(w_rm)}  {'Hits'.rjust(w_hits)}  Migration")
        print(f"{'-'*w_ep}  {'-'*w_rm}  {'-'*w_hits}  {'-'*9}")
        for ep, rm, hits, mig in rows:
            print(f"{str(ep).ljust(w_ep)}  {str(rm).ljust(w_rm)}  {str(hits).rjust(w_hits)}  {fmt_mig(mig)}")

        # Policy enforcement exit code logic
        threshold = getattr(args, 'fail_hits', None)
        if threshold is not None:
            try:
                threshold_val = int(threshold)
            except Exception:
                threshold_val = None
            if threshold_val is not None and any((r[2] or 0) > threshold_val for r in rows):
                # Non-zero exit to signal policy violation
                sys.exit(3)
        # Missing migration enforcement exit code logic
        if getattr(args, 'fail_missing_migration', False):
            # if any deprecated endpoint lacks migration mapping
            if any(it.get('migration') in (None, {}) for it in items or []):
                sys.exit(4)


async def main() -> None:  # pragma: no cover
    cli = FastCLI()
    await cli.run()


def sync_main():  # pragma: no cover
    return asyncio.run(main())


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
