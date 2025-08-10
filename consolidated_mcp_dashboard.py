#!/usr/bin/env python3
"""
Consolidated MCP-first FastAPI Dashboard

- Single-file, lightweight FastAPI app
- JSON-RPC tools first; REST mirrors for parity
- UI: / and /app.js
- SDK alias: /mcp-client.js
- Health/Status: /api/system/health, /api/mcp/status
- Realtime: /api/logs/stream (SSE), /ws (WebSocket)
- State: ~/.ipfs_kit storing JSON files for buckets, pins, backends; YAML optional
- VFS: list/read/write under ~/.ipfs_kit/vfs

This module is the entry point for `ipfs_kit mcp start`.
It exposes class ConsolidatedMCPDashboard with .app ASGI app and .run() to start uvicorn.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import socket
import subprocess
from collections import deque
import atexit
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    import uvicorn  # type: ignore
except Exception:  # pragma: no cover
    uvicorn = None  # type: ignore

# Optional deps, kept lazy/guarded
try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # type: ignore

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # type: ignore

# -----------------------------
# Utilities and storage helpers
# -----------------------------

class Paths:
    def __init__(self, data_dir: Path, logs_dir: Path, backends_file: Path, buckets_file: Path, pins_file: Path, vfs_root: Path) -> None:
        self.data_dir = data_dir
        self.logs_dir = logs_dir
        self.backends_file = backends_file
        self.buckets_file = buckets_file
        self.pins_file = pins_file
        self.vfs_root = vfs_root


def ensure_paths(base: Optional[str | Path] = None) -> Paths:
    root = Path(base).expanduser() if base else Path.home() / ".ipfs_kit"
    root.mkdir(parents=True, exist_ok=True)
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    vfs_root = root / "vfs"
    vfs_root.mkdir(exist_ok=True)
    return Paths(
        data_dir=root,
        logs_dir=logs,
        backends_file=root / "backends.json",
        buckets_file=root / "buckets.json",
        pins_file=root / "pins.json",
        vfs_root=vfs_root,
    )


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _atomic_write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _which(cmd: str) -> Optional[str]:
    with suppress(Exception):
        return shutil.which(cmd)
    return None


def _port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    with suppress(Exception):
        with socket.create_connection((host, port), timeout=timeout):
            return True
    return False


def _safe_vfs_path(root: Path, rel: str) -> Path:
    p = (root / rel.lstrip("/"))
    p = p.resolve()
    if not str(p).startswith(str(root.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path outside VFS root")
    return p


class _MemoryLogHandler(logging.Handler):
    def __init__(self, maxlen: int = 2000) -> None:
        super().__init__()
        self.logs = deque(maxlen=maxlen)
        self.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.logs.append({
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            })
        except Exception:
            pass

    def get(self, limit: int = 200) -> List[Dict[str, Any]]:
        if limit <= 0:
            return list(self.logs)
        return list(self.logs)[-limit:]

    def clear(self) -> None:
        self.logs.clear()


# -----------------------------
# Main dashboard class
# -----------------------------

class ConsolidatedMCPDashboard:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.paths = ensure_paths(self.config.get("data_dir"))
        self.host = self.config.get("host", "127.0.0.1")
        self.port = int(self.config.get("port", 8081))
        self.debug = bool(self.config.get("debug", False))

        # App
        self.app = FastAPI(title="IPFS Kit MCP Dashboard", version="1.0")
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Logging
        self.memlog = _MemoryLogHandler(maxlen=4000)
        root = logging.getLogger()
        if not any(isinstance(h, _MemoryLogHandler) for h in root.handlers):
            root.addHandler(self.memlog)
        root.setLevel(logging.INFO)
        self.log = logging.getLogger("dashboard")
        self.log.info("Consolidated MCP Dashboard initialized at %s", self.paths.data_dir)

        # WebSocket clients
        self._ws_clients: set[WebSocket] = set()

        # Register routes
        self._register_routes()

        # Ensure PID file cleanup on exit if created
        atexit.register(self._cleanup_pid_file)

    def _pid_file_path(self) -> Path:
        return self.paths.data_dir / f"mcp_{self.port}.pid"

    def _write_pid_file(self) -> None:
        try:
            p = self._pid_file_path()
            p.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass

    def _cleanup_pid_file(self) -> None:
        try:
            self._pid_file_path().unlink(missing_ok=True)
        except Exception:
            pass

    # ---- public API ----
    async def run(self) -> None:
        """Start the server asynchronously (used by CLI which awaits this)."""
        if uvicorn is None:
            raise RuntimeError("uvicorn not installed")
        # Write PID file early for background launcher
        self._write_pid_file()
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if self.debug else "info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    def run_sync(self) -> None:
        """Start the server synchronously (used when executing this file directly)."""
        if uvicorn is None:
            raise RuntimeError("uvicorn not installed")
        # Write PID file early for direct invocation
        self._write_pid_file()
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if self.debug else "info",
        )

    # ---- route registration ----
    def _register_routes(self) -> None:
        app = self.app

        @app.get("/", response_class=HTMLResponse)
        async def index() -> str:
            return self._html()

        @app.get("/app.js", response_class=PlainTextResponse)
        async def app_js() -> str:
            return self._app_js()

        @app.get("/mcp-client.js", response_class=PlainTextResponse)
        async def mcp_client_js() -> str:
            return self._mcp_client_js()

        # Health/Status
        @app.get("/api/system/health")
        async def system_health() -> Dict[str, Any]:
            info: Dict[str, Any] = {
                "ok": True,
                "time": datetime.utcnow().isoformat() + "Z",
                "data_dir": str(self.paths.data_dir),
                "python": os.sys.version.split(" ")[0],
            }
            if psutil:
                with suppress(Exception):
                    info["cpu_percent"] = psutil.cpu_percent(interval=None)
                    vm = psutil.virtual_memory()
                    info["memory"] = {"used": vm.used, "total": vm.total, "percent": vm.percent}
            return info

        @app.get("/api/mcp/status")
        async def mcp_status() -> Dict[str, Any]:
            return {
                "jsonrpc": "2.0",
                "tools": [t["name"] for t in self._tools_list()["result"]["tools"]],
                "endpoints": {
                    "tools_list": "/mcp/tools/list",
                    "tools_call": "/mcp/tools/call",
                    "sse_logs": "/api/logs/stream",
                    "websocket": "/ws",
                },
            }

        # Realtime
        @app.get("/api/logs/stream")
        async def logs_stream(request: Request) -> StreamingResponse:
            async def event_gen():
                last = 0
                while True:
                    if await request.is_disconnected():
                        break
                    logs = self.memlog.get(limit=0)
                    if len(logs) > last:
                        for entry in logs[last:]:
                            data = json.dumps(entry)
                            yield f"data: {data}\n\n"
                        last = len(logs)
                    await asyncio.sleep(0.5)
            return StreamingResponse(event_gen(), media_type="text/event-stream")

        @app.websocket("/ws")
        async def ws_endpoint(ws: WebSocket) -> None:
            await ws.accept()
            self._ws_clients.add(ws)
            try:
                await ws.send_json({"type": "hello", "message": "connected"})
                while True:
                    msg = await ws.receive_text()
                    with suppress(Exception):
                        data = json.loads(msg)
                    if isinstance(data, dict) and data.get("type") == "ping":
                        await ws.send_json({"type": "pong", "time": datetime.utcnow().isoformat() + "Z"})
                    else:
                        await ws.send_json({"type": "ack", "received": data})
            except WebSocketDisconnect:
                pass
            finally:
                self._ws_clients.discard(ws)

        # REST mirrors: backends
        @app.get("/api/state/backends")
        async def list_backends() -> Dict[str, Any]:
            data = _read_json(self.paths.backends_file, default={})
            items = [{"name": k, "config": v} for k, v in data.items()]
            return {"items": items}

        @app.post("/api/state/backends")
        async def create_backend(payload: Dict[str, Any]) -> Dict[str, Any]:
            name = payload.get("name")
            cfg = payload.get("config", {})
            if not name:
                raise HTTPException(400, "Missing backend name")
            data = _read_json(self.paths.backends_file, default={})
            if name in data:
                raise HTTPException(409, "Backend already exists")
            data[name] = cfg
            _atomic_write_json(self.paths.backends_file, data)
            return {"ok": True, "name": name}

        @app.get("/api/state/backends/{name}")
        async def get_backend(name: str) -> Dict[str, Any]:
            data = _read_json(self.paths.backends_file, default={})
            if name not in data:
                raise HTTPException(404, "Not found")
            return {"name": name, "config": data[name]}

        @app.post("/api/state/backends/{name}")
        async def update_backend(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            data = _read_json(self.paths.backends_file, default={})
            if name not in data:
                raise HTTPException(404, "Not found")
            cfg = payload.get("config", {})
            data[name] = cfg
            _atomic_write_json(self.paths.backends_file, data)
            return {"ok": True}

        @app.delete("/api/state/backends/{name}")
        async def delete_backend(name: str) -> Dict[str, Any]:
            data = _read_json(self.paths.backends_file, default={})
            if name not in data:
                raise HTTPException(404, "Not found")
            data.pop(name)
            _atomic_write_json(self.paths.backends_file, data)
            return {"ok": True}

        @app.post("/api/state/backends/{name}/test")
        async def test_backend(name: str) -> Dict[str, Any]:
            data = _read_json(self.paths.backends_file, default={})
            cfg = data.get(name, {})
            kind = (cfg or {}).get("type", "unknown")
            ipfs_bin = _which("ipfs")
            reachable = bool(ipfs_bin)
            return {"name": name, "type": kind, "reachable": reachable, "ipfs_bin": ipfs_bin}

        # REST: services
        @app.get("/api/services")
        async def list_services() -> Dict[str, Any]:
            services = {
                "ipfs": {"bin": _which("ipfs")},
                "docker": {"bin": _which("docker")},
                "kubectl": {"bin": _which("kubectl")},
            }
            # Simple ipfs daemon probe
            services["ipfs"]["api_port_open"] = _port_open("127.0.0.1", 5001)
            return {"services": services}

        # REST: buckets
        @app.get("/api/state/buckets")
        async def list_buckets() -> Dict[str, Any]:
            items = _read_json(self.paths.buckets_file, default=[])
            return {"items": items}

        @app.post("/api/state/buckets")
        async def create_bucket(payload: Dict[str, Any]) -> Dict[str, Any]:
            name = payload.get("name")
            backend = payload.get("backend")
            if not name:
                raise HTTPException(400, "Missing bucket name")
            items = _read_json(self.paths.buckets_file, default=[])
            if any(b.get("name") == name for b in items):
                raise HTTPException(409, "Bucket exists")
            entry = {"name": name, "backend": backend, "created_at": datetime.utcnow().isoformat() + "Z"}
            items.append(entry)
            _atomic_write_json(self.paths.buckets_file, items)
            # Optional mirrored YAML
            if yaml is not None:
                with suppress(Exception):
                    ydir = self.paths.data_dir / "bucket_configs"
                    ydir.mkdir(exist_ok=True)
                    (ydir / f"{name}.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")
            return {"ok": True, "bucket": entry}

        @app.delete("/api/state/buckets/{name}")
        async def delete_bucket(name: str) -> Dict[str, Any]:
            items = _read_json(self.paths.buckets_file, default=[])
            new_items = [b for b in items if b.get("name") != name]
            if len(new_items) == len(items):
                raise HTTPException(404, "Not found")
            _atomic_write_json(self.paths.buckets_file, new_items)
            return {"ok": True}

        # REST: pins
        @app.get("/api/pins")
        async def list_pins() -> Dict[str, Any]:
            items = _read_json(self.paths.pins_file, default=[])
            return {"items": items}

        @app.post("/api/pins")
        async def create_pin(payload: Dict[str, Any]) -> Dict[str, Any]:
            cid = payload.get("cid")
            name = payload.get("name")
            if not cid:
                raise HTTPException(400, "Missing cid")
            pins = _read_json(self.paths.pins_file, default=[])
            if any(p.get("cid") == cid for p in pins):
                raise HTTPException(409, "Pin exists")
            entry = {"cid": cid, "name": name, "created_at": datetime.utcnow().isoformat() + "Z"}
            pins.append(entry)
            _atomic_write_json(self.paths.pins_file, pins)
            return {"ok": True, "pin": entry}

        @app.delete("/api/pins/{cid}")
        async def delete_pin(cid: str) -> Dict[str, Any]:
            pins = _read_json(self.paths.pins_file, default=[])
            new_pins = [p for p in pins if p.get("cid") != cid]
            if len(new_pins) == len(pins):
                raise HTTPException(404, "Not found")
            _atomic_write_json(self.paths.pins_file, new_pins)
            return {"ok": True}

        # REST: files VFS
        @app.get("/api/files/list")
        async def files_list(path: str = ".") -> Dict[str, Any]:
            base = self.paths.vfs_root
            p = _safe_vfs_path(base, path)
            if not p.exists():
                return {"path": str(path), "items": []}
            if p.is_file():
                raise HTTPException(400, "Path is a file")
            items = []
            for child in sorted(p.iterdir()):
                items.append({
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "size": child.stat().st_size if child.exists() and child.is_file() else None,
                })
            return {"path": str(path), "items": items}

        @app.get("/api/files/read")
        async def files_read(path: str) -> Dict[str, Any]:
            p = _safe_vfs_path(self.paths.vfs_root, path)
            if not p.exists() or not p.is_file():
                raise HTTPException(404, "File not found")
            try:
                content = p.read_text(encoding="utf-8")
                mode = "text"
            except UnicodeDecodeError:
                content = p.read_bytes().hex()
                mode = "hex"
            return {"path": path, "mode": mode, "content": content}

        @app.post("/api/files/write")
        async def files_write(payload: Dict[str, Any]) -> Dict[str, Any]:
            path = payload.get("path")
            content = payload.get("content", "")
            mode = payload.get("mode", "text")
            if not path:
                raise HTTPException(400, "Missing path")
            p = _safe_vfs_path(self.paths.vfs_root, path)
            p.parent.mkdir(parents=True, exist_ok=True)
            if mode == "hex":
                p.write_bytes(bytes.fromhex(content))
            else:
                p.write_text(str(content), encoding="utf-8")
            return {"ok": True}

        # JSON-RPC tools
        @app.post("/mcp/tools/list")
        async def mcp_tools_list() -> Dict[str, Any]:
            return self._tools_list()

        @app.post("/mcp/tools/call")
        async def mcp_tools_call(payload: Dict[str, Any]) -> Dict[str, Any]:
            name = payload.get("name") or payload.get("tool")
            args = payload.get("args") or payload.get("params") or {}
            return await self._tools_call(name, args)

    # ---- tools ----
    def _tools_list(self) -> Dict[str, Any]:
        tools = [
            {"name": "get_system_status", "description": "System health and versions", "inputSchema": {}},
            {"name": "list_services", "description": "List local services and probes", "inputSchema": {}},
            {"name": "list_backends", "description": "List configured backends", "inputSchema": {}},
            {"name": "create_backend", "description": "Create backend", "inputSchema": {"name": "string", "config": "object"}},
            {"name": "delete_backend", "description": "Delete backend", "inputSchema": {"name": "string"}},
            {"name": "list_buckets", "description": "List buckets", "inputSchema": {}},
            {"name": "create_bucket", "description": "Create bucket", "inputSchema": {"name": "string", "backend": "string"}},
            {"name": "delete_bucket", "description": "Delete bucket", "inputSchema": {"name": "string"}},
            {"name": "list_pins", "description": "List pins", "inputSchema": {}},
            {"name": "create_pin", "description": "Create pin", "inputSchema": {"cid": "string", "name": "string"}},
            {"name": "delete_pin", "description": "Delete pin", "inputSchema": {"cid": "string"}},
            {"name": "files_list", "description": "List VFS", "inputSchema": {"path": "string"}},
            {"name": "files_read", "description": "Read VFS file", "inputSchema": {"path": "string"}},
            {"name": "files_write", "description": "Write VFS file", "inputSchema": {"path": "string", "content": "string", "mode": "string"}},
            {"name": "get_logs", "description": "Get recent logs", "inputSchema": {"limit": "number"}},
            {"name": "clear_logs", "description": "Clear logs", "inputSchema": {}},
        ]
        return {"jsonrpc": "2.0", "result": {"tools": tools}, "id": None}

    async def _tools_call(self, name: Optional[str], args: Dict[str, Any]) -> Dict[str, Any]:
        if not name:
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Missing tool name"}, "id": None}

        try:
            if name == "get_system_status":
                result: Dict[str, Any] = {
                    "time": datetime.utcnow().isoformat() + "Z",
                    "data_dir": str(self.paths.data_dir),
                }
                if psutil:
                    with suppress(Exception):
                        result["cpu_percent"] = psutil.cpu_percent(interval=None)
                return {"jsonrpc": "2.0", "result": result, "id": None}

            if name == "list_services":
                services = {
                    "services": {
                        "ipfs": {"bin": _which("ipfs"), "api_port_open": _port_open("127.0.0.1", 5001)},
                        "docker": {"bin": _which("docker")},
                        "kubectl": {"bin": _which("kubectl")},
                    }
                }
                return {"jsonrpc": "2.0", "result": services, "id": None}

            if name == "list_backends":
                data = _read_json(self.paths.backends_file, default={})
                items = [{"name": k, "config": v} for k, v in data.items()]
                return {"jsonrpc": "2.0", "result": {"items": items}, "id": None}

            if name == "create_backend":
                bname = args.get("name")
                cfg = args.get("config", {})
                if not bname:
                    raise HTTPException(400, "Missing name")
                data = _read_json(self.paths.backends_file, default={})
                if bname in data:
                    raise HTTPException(409, "Exists")
                data[bname] = cfg
                _atomic_write_json(self.paths.backends_file, data)
                return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}

            if name == "delete_backend":
                bname = args.get("name")
                data = _read_json(self.paths.backends_file, default={})
                if bname not in data:
                    raise HTTPException(404, "Not found")
                data.pop(bname)
                _atomic_write_json(self.paths.backends_file, data)
                return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}

            if name == "list_buckets":
                items = _read_json(self.paths.buckets_file, default=[])
                return {"jsonrpc": "2.0", "result": {"items": items}, "id": None}

            if name == "create_bucket":
                bname = args.get("name")
                backend = args.get("backend")
                if not bname:
                    raise HTTPException(400, "Missing name")
                items = _read_json(self.paths.buckets_file, default=[])
                if any(b.get("name") == bname for b in items):
                    raise HTTPException(409, "Exists")
                entry = {"name": bname, "backend": backend, "created_at": datetime.utcnow().isoformat() + "Z"}
                items.append(entry)
                _atomic_write_json(self.paths.buckets_file, items)
                return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}

            if name == "delete_bucket":
                bname = args.get("name")
                items = _read_json(self.paths.buckets_file, default=[])
                new_items = [b for b in items if b.get("name") != bname]
                if len(new_items) == len(items):
                    raise HTTPException(404, "Not found")
                _atomic_write_json(self.paths.buckets_file, new_items)
                return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}

            if name == "list_pins":
                items = _read_json(self.paths.pins_file, default=[])
                return {"jsonrpc": "2.0", "result": {"items": items}, "id": None}

            if name == "create_pin":
                cid = args.get("cid")
                label = args.get("name")
                if not cid:
                    raise HTTPException(400, "Missing cid")
                pins = _read_json(self.paths.pins_file, default=[])
                if any(p.get("cid") == cid for p in pins):
                    raise HTTPException(409, "Exists")
                entry = {"cid": cid, "name": label, "created_at": datetime.utcnow().isoformat() + "Z"}
                pins.append(entry)
                _atomic_write_json(self.paths.pins_file, pins)
                return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}

            if name == "delete_pin":
                cid = args.get("cid")
                pins = _read_json(self.paths.pins_file, default=[])
                new_pins = [p for p in pins if p.get("cid") != cid]
                if len(new_pins) == len(pins):
                    raise HTTPException(404, "Not found")
                _atomic_write_json(self.paths.pins_file, new_pins)
                return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}

            if name == "files_list":
                path = args.get("path", ".")
                res = await self._call_files_list(path)
                return {"jsonrpc": "2.0", "result": res, "id": None}

            if name == "files_read":
                res = await self._call_files_read(args.get("path"))
                return {"jsonrpc": "2.0", "result": res, "id": None}

            if name == "files_write":
                await self._call_files_write(args.get("path"), args.get("content", ""), args.get("mode", "text"))
                return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}

            if name == "get_logs":
                limit = int(args.get("limit", 200))
                return {"jsonrpc": "2.0", "result": {"items": self.memlog.get(limit)}, "id": None}

            if name == "clear_logs":
                self.memlog.clear()
                return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}

            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Unknown tool: {name}"}, "id": None}
        except HTTPException as e:
            return {"jsonrpc": "2.0", "error": {"code": e.status_code, "message": e.detail}, "id": None}
        except Exception as e:  # pragma: no cover
            return {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(e)}, "id": None}

    # helpers used by tools
    async def _call_files_list(self, path: str) -> Dict[str, Any]:
        base = self.paths.vfs_root
        p = _safe_vfs_path(base, path)
        if not p.exists():
            return {"path": str(path), "items": []}
        if p.is_file():
            raise HTTPException(400, "Path is a file")
        items = []
        for child in sorted(p.iterdir()):
            items.append({
                "name": child.name,
                "is_dir": child.is_dir(),
                "size": child.stat().st_size if child.exists() and child.is_file() else None,
            })
        return {"path": str(path), "items": items}

    async def _call_files_read(self, path: Optional[str]) -> Dict[str, Any]:
        if not path:
            raise HTTPException(400, "Missing path")
        p = _safe_vfs_path(self.paths.vfs_root, path)
        if not p.exists() or not p.is_file():
            raise HTTPException(404, "File not found")
        try:
            content = p.read_text(encoding="utf-8")
            mode = "text"
        except UnicodeDecodeError:
            content = p.read_bytes().hex()
            mode = "hex"
        return {"path": path, "mode": mode, "content": content}

    async def _call_files_write(self, path: Optional[str], content: str, mode: str) -> None:
        if not path:
            raise HTTPException(400, "Missing path")
        p = _safe_vfs_path(self.paths.vfs_root, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if mode == "hex":
            p.write_bytes(bytes.fromhex(content))
        else:
            p.write_text(str(content), encoding="utf-8")

    # ---- assets ----
    def _html(self) -> str:
        return f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>IPFS Kit MCP Dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; padding: 0; }}
    header {{ background:#111; color:#fff; padding:10px 16px; }}
    main {{ padding: 16px; }}
    pre {{ background:#f5f5f5; padding:12px; border-radius:6px; overflow:auto; }}
    .row {{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; }}
    .card {{ border:1px solid #ddd; border-radius:8px; padding:12px; margin:8px 0; }}
    button {{ padding:6px 10px; }}
  </style>
</head>
<body>
  <header>
    <h3>IPFS Kit MCP Dashboard</h3>
  </header>
  <main>
    <div id="app">Loading…</div>
  </main>
  <script src="/mcp-client.js"></script>
  <script src="/app.js"></script>
</body>
</html>
"""

    def _app_js(self) -> str:
        return """
(async function(){
  const el = document.getElementById('app');
  const log = (m)=>{ console.log(m); };

  function h(tag, attrs={}, ...children){
    const n = document.createElement(tag);
    for(const [k,v] of Object.entries(attrs||{})){
      if(k.startsWith('on') && typeof v==='function') n.addEventListener(k.substring(2).toLowerCase(), v);
      else if(v!=null) n.setAttribute(k, v);
    }
    for(const c of children){ n.append(c); }
    return n;
  }

  // Tiny UI
  async function load(){
    const tools = await (await fetch('/mcp/tools/list', {method: 'POST'})).json();
    const toolNames = tools.result.tools.map(t=>t.name);

    const status = await (await fetch('/api/mcp/status')).json();

    const cont = h('div', {},
      h('div', {class: 'card'}, h('h4', {}, 'Status'), h('pre', {}, JSON.stringify(status,null,2))),
      h('div', {class: 'card'}, h('h4', {}, 'Tools ('+toolNames.length+')'),
        h('div', {}, ...toolNames.map(n=> h('button', {style:'margin:4px', onclick:()=>runTool(n)}, n)))
      ),
      h('div', {class: 'card'}, h('h4', {}, 'Logs'), h('pre', {id:'logs'}, '…'))
    );

    el.innerHTML='';
    el.append(cont);

    const es = new EventSource('/api/logs/stream');
    es.onmessage = (ev)=>{
      const data = JSON.parse(ev.data);
      const pre = document.getElementById('logs');
      pre.textContent += `\n${data.timestamp} ${data.level} ${data.logger}: ${data.message}`;
    };
  }

  async function runTool(name){
    const res = await fetch('/mcp/tools/call', { method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({name, args:{}})});
    const j = await res.json();
    alert(name+" =>\n"+JSON.stringify(j.result||j.error,null,2));
  }

  await load();
})();
"""

    def _mcp_client_js(self) -> str:
        return """
// Minimal JSON-RPC client for the dashboard
export async function listTools(){
  const r = await fetch('/mcp/tools/list', {method:'POST'});
  return await r.json();
}
export async function callTool(name, args={}){
  const r = await fetch('/mcp/tools/call', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({name, args})});
  return await r.json();
}
"""


if __name__ == "__main__":  # pragma: no cover
    cfg = {
        "host": os.environ.get("MCP_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MCP_PORT", "8081")),
        "data_dir": os.environ.get("MCP_DATA_DIR"),
        "debug": os.environ.get("MCP_DEBUG", "0") in ("1", "true", "True"),
    }
    app = ConsolidatedMCPDashboard(cfg)
    app.run_sync()
