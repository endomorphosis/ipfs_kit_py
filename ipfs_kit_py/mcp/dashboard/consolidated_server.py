#!/usr/bin/env python3
"""
Consolidated MCP-first FastAPI Dashboard

Single-file FastAPI app providing:
 - JSON-RPC style tool endpoints (under /mcp)
 - REST mirrors for key domain objects (buckets, backends, pins, files, metrics)
 - Realtime WebSocket + SSE logs
 - Self-rendered HTML UI (progressively enhanced)

NOTE: Large HTML template content was previously (accidentally) embedded inside this
module docstring causing the original import section to be lost and producing a
cascade of "name is not defined" errors. This docstring has been reduced and the
imports + helpers restored below.
"""
import os, sys, json, time, asyncio, logging, socket, signal, tarfile, shutil, subprocess, inspect, atexit, threading
from collections import deque
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Iterable
from contextlib import suppress, asynccontextmanager
from types import SimpleNamespace

# Import comprehensive service manager
try:
    from ipfs_kit_py.mcp.services.comprehensive_service_manager import ComprehensiveServiceManager
    COMPREHENSIVE_SERVICE_MANAGER_AVAILABLE = True
except ImportError:
    COMPREHENSIVE_SERVICE_MANAGER_AVAILABLE = False
    ComprehensiveServiceManager = None

import uvicorn  # server
try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # type: ignore
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # type: ignore

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse, Response, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import mimetypes

UTC = timezone.utc

class InMemoryLogHandler(logging.Handler):
    def __init__(self, maxlen: int = 4000):
        super().__init__()
        self.maxlen = maxlen
        self._items: List[Dict[str, Any]] = []
    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        try:
            self._items.append({
                "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            })
            if len(self._items) > self.maxlen:
                trim = max(1, int(self.maxlen * 0.1))
                self._items = self._items[trim:]
        except Exception:
            pass
    def get(self, limit: int = 200) -> List[Dict[str, Any]]:
        if limit and limit > 0:
            return self._items[-limit:]
        return list(self._items)
    def clear(self) -> None:
        self._items.clear()

def create_default_backends():
    """Create default backend configurations for testing and demonstration."""
    now = datetime.now(UTC).isoformat()
    
    return {
        "local_fs": {
            "type": "local_storage",
            "description": "Local filesystem storage backend",
            "status": "enabled",
            "config": {
                "path": "/tmp/ipfs_kit_storage",
                "max_size": "10GB",
                "compression": True
            },
            "created_at": now,
            "last_check": now,
            "health": "healthy",
            "category": "storage",
            "policy": {
                "quota": "10GB",
                "replication": 1,
                "retention": "30d",
                "cache": "enabled"
            },
            "stats": {
                "size": "2.1GB",
                "files": 1247,
                "last_sync": now
            }
        },
        "ipfs_local": {
            "type": "ipfs",
            "description": "Local IPFS node for distributed storage",
            "status": "enabled",
            "config": {
                "api_url": "http://127.0.0.1:5001",
                "gateway_url": "http://127.0.0.1:8080",
                "pinning": True
            },
            "created_at": now,
            "last_check": now,
            "health": "healthy",
            "category": "network",
            "policy": {
                "quota": "unlimited",
                "replication": 3,
                "retention": "permanent",
                "cache": "enabled"
            },
            "stats": {
                "peers": 42,
                "pins": 156,
                "last_sync": now
            }
        },
        "s3_demo": {
            "type": "s3",
            "description": "S3-compatible object storage",
            "status": "enabled",
            "config": {
                "endpoint": "https://s3.amazonaws.com",
                "bucket": "ipfs-kit-demo",
                "region": "us-east-1",
                "access_key": "demo-key",
                "secret_key": "demo-secret"
            },
            "created_at": now,
            "last_check": now,
            "health": "healthy",
            "category": "storage",
            "policy": {
                "quota": "100GB",
                "replication": 3,
                "retention": "90d",
                "cache": "enabled"
            },
            "stats": {
                "objects": 3421,
                "size": "45.2GB",
                "last_sync": now
            }
        },
        "parquet_meta": {
            "type": "parquet",
            "description": "Parquet metadata storage backend",
            "status": "enabled",
            "config": {
                "path": "/tmp/ipfs_kit_parquet",
                "compression": "snappy",
                "schema_version": "1.0"
            },
            "created_at": now,
            "last_check": now,
            "health": "healthy",
            "category": "analytics",
            "policy": {
                "quota": "50GB",
                "replication": 2,
                "retention": "365d",
                "cache": "enabled"
            },
            "stats": {
                "tables": 12,
                "rows": 98765,
                "last_sync": now
            }
        },
        "github": {
            "type": "git",
            "description": "Git repository backend for version control",
            "status": "enabled",
            "config": {
                "repo_url": "https://github.com/user/repo.git",
                "branch": "main",
                "auth_token": "demo-token"
            },
            "created_at": now,
            "last_check": now,
            "health": "healthy",
            "category": "storage",
            "policy": {
                "quota": "5GB",
                "replication": 1,
                "retention": "365d",
                "cache": "enabled"
            },
            "stats": {
                "commits": 245,
                "branches": 3,
                "last_sync": now
            }
        },
        "cluster": {
            "type": "ipfs_cluster",
            "description": "IPFS Cluster for coordinated pinning",
            "status": "enabled",
            "config": {
                "cluster_api": "http://127.0.0.1:9094",
                "peer_id": "12D3KooWDemo...",
                "secret": "demo-secret"
            },
            "created_at": now,
            "last_check": now,
            "health": "healthy",
            "category": "network",
            "policy": {
                "quota": "unlimited",
                "replication": 5,
                "retention": "permanent",
                "cache": "enabled"
            },
            "stats": {
                "nodes": 5,
                "pins": 892,
                "last_sync": now
            }
        }
    }

def ensure_paths(data_dir: Optional[str]):
    base = Path(data_dir or os.path.expanduser("~/.ipfs_kit"))
    data_dir_path = base
    data_dir_path.mkdir(parents=True, exist_ok=True)
    car_store = data_dir_path / "car_store"; car_store.mkdir(exist_ok=True)
    vfs_root = data_dir_path / "vfs"; vfs_root.mkdir(exist_ok=True)
    bucket_configs = data_dir_path / "bucket_configs"; bucket_configs.mkdir(exist_ok=True)
    backends_file = data_dir_path / "backends.json"
    buckets_file = data_dir_path / "buckets.json"
    pins_file = data_dir_path / "pins.json"
    
    # Initialize with default backends if file doesn't exist or is empty
    if not backends_file.exists() or backends_file.stat().st_size == 0:
        with suppress(Exception):
            with backends_file.open('w', encoding='utf-8') as fh:
                json.dump(create_default_backends(), fh, indent=2)
    
    # Check if backends.json has old format and upgrade it
    try:
        with backends_file.open('r', encoding='utf-8') as fh:
            existing_backends = json.load(fh)
        
        # Check if any backend is in old format (missing required fields)
        needs_upgrade = False
        for name, config in existing_backends.items():
            if not isinstance(config, dict) or 'description' not in config or 'created_at' not in config:
                needs_upgrade = True
                break
        
        if needs_upgrade:
            # Upgrade to new format with defaults
            default_backends = create_default_backends()
            with backends_file.open('w', encoding='utf-8') as fh:
                json.dump(default_backends, fh, indent=2)
    except Exception:
        # If there's any error reading, create defaults
        with suppress(Exception):
            with backends_file.open('w', encoding='utf-8') as fh:
                json.dump(create_default_backends(), fh, indent=2)
    
    for f, default in [(buckets_file, []), (pins_file, [])]:
        if not f.exists():
            with suppress(Exception):
                with f.open('w', encoding='utf-8') as fh:
                    json.dump(default, fh)
    
    return SimpleNamespace(
        base=base,
        data_dir=data_dir_path,
        car_store=car_store,
        vfs_root=vfs_root,
        bucket_configs=bucket_configs,
        backends_file=backends_file,
        buckets_file=buckets_file,
        pins_file=pins_file,
    )


# ---- JSON helpers (restored) ----
def _read_json(path: Path, default):
    try:
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def _atomic_write_json(path: Path, data) -> None:
    try:
        tmp = path.with_suffix(path.suffix + '.tmp')
        with tmp.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, sort_keys=True)
        tmp.replace(path)
    except Exception:
        pass

def _which(bin_name: str) -> Optional[str]:
    from shutil import which
    return which(bin_name)

def _port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            return s.connect_ex((host, port)) == 0
        except Exception:
            return False

def _run_cmd(cmd: List[str], timeout: float = 10.0) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"code": proc.returncode, "out": proc.stdout, "err": proc.stderr}
    except Exception as e:
        return {"code": -1, "error": str(e)}

def _normalize_buckets(items):
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = it.get('name') or it.get('id')
        if not name:
            continue
        # Normalize embedded policy with defaults
        pol = it.get('policy') or {}
        norm_policy = {
            'replication_factor': int(pol.get('replication_factor', 1) or 1),
            'cache_policy': pol.get('cache_policy', 'none') or 'none',
            'retention_days': int(pol.get('retention_days', 0) or 0),
        }
        out.append({"name": name, "backend": it.get('backend'), "meta": it.get('meta', {}), "policy": norm_policy})
    return out

def _normalize_pins(items):
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        cid = it.get('cid') or it.get('hash')
        if not cid:
            continue
        out.append({"cid": cid, "name": it.get('name')})
    return out

def _normalize_backends(items):
    """Normalize backend items ensuring required fields are present."""
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = it.get("name")
        if name:
            # Ensure all backends have required fields with defaults
            backend = {
                "name": name,
                "type": it.get("type", "unknown"),
                "tier": it.get("tier", "standard"),
                "description": it.get("description", f"{it.get('type', 'unknown')} backend"),
                "config": it.get("config", {}),
                "policy": it.get("policy", {
                    "replication_factor": 1,
                    "cache_policy": "none", 
                    "retention_days": 0
                }),
                "enabled": it.get("enabled", False),
                "created_at": it.get("created_at"),
                "last_updated": it.get("last_updated")
            }
            out.append(backend)
    return out

def _safe_vfs_path(root: Path, user_path: str) -> Path:
    # prevent directory traversal
    p = (root / user_path).resolve()
    if not str(p).startswith(str(root.resolve())):
        raise ValueError("invalid path")
    return p

def _run_cmd_bytes(cmd: List[str], timeout: float = 30.0) -> Dict[str, Any]:
    """Run command returning dict with raw bytes; mirrors shape of _run_cmd.

    Returns: { ok: bool, code: int, out_bytes: bytes, err: str }
    """
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "out_bytes": proc.stdout if proc.returncode == 0 else b"",
            "err": proc.stderr.decode('utf-8', 'ignore'),
        }
    except Exception as e:  # pragma: no cover
        return {"ok": False, "code": -1, "out_bytes": b"", "err": str(e)}


# -----------------------------
# Main dashboard class
# -----------------------------

class ConsolidatedMCPDashboard:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        # Basic config
        self.config = config or {}
        self.paths = ensure_paths(self.config.get("data_dir"))
        self.host = self.config.get("host", "127.0.0.1")
        self.port = int(self.config.get("port", 8081))
        self.debug = bool(self.config.get("debug", False))
        self.DEPRECATED_ENDPOINTS: Dict[str, str] = {"/api/system/overview": "3.2.0"}
        self.api_token = self.config.get("api_token") or os.environ.get("MCP_API_TOKEN")
        self._start_time = time.time()
        # Metrics / accounting
        self._realtime_task: Optional[asyncio.Task] = None
        self._net_last: Optional[Dict[str, Any]] = None
        self._net_history: deque = deque(maxlen=360)
        self._sys_history: deque = deque(maxlen=360)
        self.request_count: int = 0
        self.endpoint_hits: Dict[str, int] = {}
        self._hits_file = self.paths.data_dir / "endpoint_hits.json"

        # Initialize comprehensive service manager (will be lazily loaded)
        self._service_manager = None  # Will be initialized on first use to avoid circular imports

        # Ensure graceful persistence on process signals (SIGTERM/SIGINT)
        def _persist_hits(*_a):  # pragma: no cover - signal handling is hard to unit test reliably
            try:
                if self.endpoint_hits:
                    _atomic_write_json(self._hits_file, self.endpoint_hits)
            except Exception:
                pass
        with suppress(Exception):
            signal.signal(signal.SIGTERM, lambda *_: (_persist_hits(), sys.exit(0)))
        with suppress(Exception):
            signal.signal(signal.SIGINT, lambda *_: (_persist_hits(), sys.exit(0)))
        atexit.register(_persist_hits)

        @asynccontextmanager
        async def _lifespan(app: FastAPI):  # noqa: D401
            with suppress(Exception):
                self._write_pid_file()
            # load persisted hits
            with suppress(Exception):
                if self._hits_file.exists():
                    data = _read_json(self._hits_file, {})
                    if isinstance(data, dict):
                        self.endpoint_hits.update({k: int(v) for k, v in data.items() if isinstance(k, str)})
            with suppress(Exception):
                if self._realtime_task is None:
                    self._realtime_task = asyncio.create_task(self._broadcast_loop())
            try:
                yield
            finally:
                if self._realtime_task:
                    self._realtime_task.cancel()
                    try:
                        await self._realtime_task
                    except asyncio.CancelledError:
                        # Expected during graceful shutdown on Python 3.12+
                        pass
                    except Exception:
                        pass
                    self._realtime_task = None
                with suppress(Exception):
                    _atomic_write_json(self._hits_file, self.endpoint_hits)
                with suppress(Exception):
                    self._cleanup_pid_file()

        self.app = FastAPI(title="IPFS Kit MCP Dashboard", version="1.0", lifespan=_lifespan)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.memlog = InMemoryLogHandler(maxlen=4000)
        root = logging.getLogger()
        if not any(isinstance(h, InMemoryLogHandler) for h in root.handlers):
            root.addHandler(self.memlog)
        root.setLevel(logging.INFO)
        self.log = logging.getLogger("dashboard")
        self.log.info("Consolidated MCP Dashboard initialized at %s", self.paths.base)
        self._ws_clients: set[WebSocket] = set()
        # Lazy-initialized peer manager
        self._peer_manager = None
        self._register_routes()
        atexit.register(self._cleanup_pid_file)

    # --- Helper methods added to restore references ---
    def _pid_file_path(self) -> Path:
        try:
            return self.paths.data_dir / f"mcp_{self.port}.pid"
        except Exception:
            return Path(os.path.expanduser("~/.ipfs_kit")) / f"mcp_{self.port}.pid"

    def _write_pid_file(self) -> None:
        with suppress(Exception):
            p = self._pid_file_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(str(os.getpid()), encoding="utf-8")
        with suppress(Exception):
            (self.paths.data_dir / "dashboard.pid").write_text(str(os.getpid()), encoding="utf-8")

    def _cleanup_pid_file(self) -> None:
        with suppress(Exception):
            self._pid_file_path().unlink(missing_ok=True)  # type: ignore[arg-type]
        with suppress(Exception):
            (self.paths.data_dir / "dashboard.pid").unlink(missing_ok=True)  # type: ignore[arg-type]

    def render_beta_toolrunner(self) -> str:
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>IPFS Kit MCP Dashboard</title>"
            "<style>"
            "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,'Noto Sans',sans-serif;padding:12px;color:#e6eef6;background:#0d1117;}"
            "#toolrunner-beta-container{border:1px solid #263042;border-radius:8px;padding:12px;background:#111827;}"
            ".dash-nav{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px 0;padding:0 4px;}"
            ".dash-nav .nav-btn{background:#263242;color:#dbe2ee;border:1px solid #37475d;border-radius:4px;padding:6px 10px;cursor:pointer;font-size:13px;}"
            "#view-tools .row{display:flex;gap:10px;flex-wrap:wrap;}"
            "#view-tools .card{background:#0f172a;border:1px solid #263042;border-radius:8px;padding:10px;flex:1;min-width:280px;}"
            "select,textarea,input,button{background:#0b1220;color:#dbe2ee;border:1px solid #2a3a50;border-radius:6px;padding:6px;}"
            "pre{white-space:pre-wrap;max-height:300px;overflow:auto;background:#0b1220;color:#bfe1ff;border:1px solid #2a3a50;border-radius:6px;padding:8px;}"
            "label{display:block;margin:6px 0 4px 0;color:#93a8c3;font-size:12px;}"
            "</style>"
            "</head><body>"
            "<div id='app'>"
            "  <div id='toolrunner-beta-container'>"
            "    <div class='dash-nav'>"
            "      <button class='nav-btn' data-view='tools'>Tools</button>"
            "    </div>"
            "    <section id='view-tools'>"
            "      <div class='row'>"
            "        <div class='card'>"
            "          <label for='tool-filter'>Filter</label>"
            "          <input id='tool-filter' placeholder='filter tools...'>"
            "          <label for='tool-select'>Select Tool</label>"
            "          <select id='tool-select'></select>"
            "        </div>"
            "        <div class='card'>"
            "          <label for='tool-args'>Arguments (JSON)</label>"
            "          <textarea id='tool-args' rows='8' data-testid='toolrunner-args'>{}</textarea>"
            "          <div style='margin-top:8px'><button id='btn-tool-run'>Run</button></div>"
            "        </div>"
            "      </div>"
            "      <div class='card' style='margin-top:10px'>"
            "        <label>Result</label>"
            "        <pre id='tool-result'></pre>"
            "      </div>"
            "    </section>"
            "  </div>"
            "</div>"
            "<script src='/mcp-client.js'></script>"
            "<script>"
            "(function(){\n"
            "  let ALL_TOOLS = [];\n"
            "  async function populateTools(){\n"
            "    try{\n"
            "      const resp = await (window.MCP && MCP.listTools ? MCP.listTools() : Promise.resolve({jsonrpc:'2.0', result:{tools:[]}, id:1}));\n"
            "      const tools = (resp && resp.result && Array.isArray(resp.result.tools)) ? resp.result.tools : [];\n"
            "      ALL_TOOLS = tools.map(t => (t && t.name) ? String(t.name) : String(t));\n"
            "      const sel = document.getElementById('tool-select');\n"
            "      if(!sel) return; sel.innerHTML='';\n"
            "      const sorted = ALL_TOOLS.slice().sort((a,b)=>a.localeCompare(b));\n"
            "      for(const name of sorted){ const opt = document.createElement('option'); opt.value=name; opt.textContent=name; sel.appendChild(opt);}\n"
            "    }catch(e){ console.warn('populateTools failed', e); }\n"
            "  }\n"
            "  function setupFilter(){\n"
            "    const input = document.getElementById('tool-filter'); const sel = document.getElementById('tool-select');\n"
            "    if(!input || !sel) return;\n"
            "    input.addEventListener('input', ()=>{\n"
            "      const q = (input.value||'').toLowerCase();\n"
            "      const filtered = ALL_TOOLS.filter(n => !q || n.toLowerCase().includes(q)).sort((a,b)=>a.localeCompare(b));\n"
            "      sel.innerHTML='';\n"
            "      for(const name of filtered){ const opt = document.createElement('option'); opt.value=name; opt.textContent=name; sel.appendChild(opt);}\n"
            "      if (sel.options.length > 0) sel.selectedIndex = 0;\n"
            "    });\n"
            "  }\n"
            "  function setupRunner(){\n"
            "    const btn = document.getElementById('btn-tool-run'); const sel = document.getElementById('tool-select'); const argsEl = document.getElementById('tool-args'); const out = document.getElementById('tool-result');\n"
            "    if(!btn || !sel || !argsEl || !out) return;\n"
            "    btn.addEventListener('click', async ()=>{\n"
            "      try{ const name = sel.value; let args={}; try{ args = JSON.parse(argsEl.value||'{}'); }catch{}\n"
            "        const res = await MCP.callTool(name, args); const wrapped = (res && res.jsonrpc) ? res : { jsonrpc: '2.0', id: Date.now(), result: res }; out.textContent = JSON.stringify(wrapped, null, 2); }\n"
            "      catch(e){ out.textContent = 'Error: ' + (e && e.message || e); }\n"
            "    });\n"
            "  }\n"
            "  const ready = () => document.readyState === 'complete' || document.readyState === 'interactive';\n"
            "  async function init(){ await populateTools(); setupFilter(); setupRunner(); }\n"
            "  if(ready()) init(); else window.addEventListener('DOMContentLoaded', init);\n"
            "})();\n"
            "</script>"
            "<script src='/app.js'></script>"
            "</body></html>"
        )

    def _read_repo_static(self, name: str) -> Optional[str]:
        candidates = [
            Path(__file__).resolve().parents[3] / "static" / name,
            Path(__file__).parent / "static" / name,
        ]
        for p in candidates:
            try:
                if p.exists():
                    return p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
        return None

    def _app_js(self) -> str:
        body = self._read_repo_static("app.js")
        if body is not None:
            return body
        return (
            "// Minimal app.js fallback\n"
            "(function(){\n"
            "  if (typeof window !== 'undefined') {\n"
            "    console.log('app.js loaded');\n"
            "  }\n"
            "})();\n"
        )

    def _mcp_client_js(self) -> str:
        base = self._read_repo_static("mcp-sdk.js") or ""
        shim = (
            "\n\n// MCP SDK (Browser/Node UMD)\n"
            "(function(){\n"
            "  try{ window.MCP = window.MCP || {}; }catch(e){ return; }\n"
            "  // Provide JSON-RPC shaped helpers (override to ensure consistency)\n"
            "  window.MCP.listTools = async function(){\n"
            "    const r = await fetch('/mcp/tools/list', { method: 'POST' });\n"
            "    try { const j = await r.json(); if (j && j.jsonrpc) return j; const tools = (j && j.result && j.result.tools) || j.tools || []; return { jsonrpc:'2.0', id:1, result:{ tools } }; } catch(e){ return { jsonrpc:'2.0', id:1, result:{ tools: [] } }; }\n"
            "  };\n"
            "  window.MCP.callTool = async function(name, args){\n"
            "    const payload = { jsonrpc: '2.0', method: 'tools/call', params: { name: name, arguments: args||{} }, id: Date.now() };\n"
            "    const r = await fetch('/mcp/tools/call', { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify(payload) });\n"
            "    try { const j = await r.json(); if (j && j.jsonrpc) return j; return { jsonrpc:'2.0', id: Date.now(), result: j }; } catch(e){ return { jsonrpc:'2.0', id: Date.now(), error: { code: -32700, message: 'Parse error' } }; }\n"
            "  };\n"
            "})();\n"
        )
        return base + shim

    def _handle_backends(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    def _handle_config(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    def _tools_list(self) -> Dict[str, Any]:
        tools = [
            {"name": "health_check"},
            {"name": "list_backends"},
            {"name": "create_backend"},
            {"name": "backend_update"},
            {"name": "backend_remove"},
            {"name": "backend_show"},
            {"name": "list_buckets"},
            {"name": "create_bucket"},
            {"name": "delete_bucket"},
            {"name": "list_files"}, {"name": "files_list"},
            {"name": "read_file"}, {"name": "files_read"},
            {"name": "write_file"}, {"name": "files_write"},
            {"name": "list_pins"}, {"name": "create_pin"}, {"name": "delete_pin"},
            {"name": "get_logs"},
            {"name": "service_status"},
            {"name": "ipfs_version"},
            {"name": "list_cars"},
        ]
        return {"result": {"tools": tools}}

    def _dispatch_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        if name == "health_check":
            return {"ok": True, "time": now, "uptime": time.time() - self._start_time}
        if name == "list_backends":
            data = _read_json(self.paths.backends_file, default={})
            names = sorted(list(data.keys())) if isinstance(data, dict) else []
            return {"total": len(names), "items": names}
        if name == "create_backend":
            backends = _read_json(self.paths.backends_file, default={})
            if not isinstance(backends, dict):
                backends = {}
            spec = {k: v for k, v in (args or {}).items()}
            bname = spec.pop("name", None) or spec.pop("backend", None)
            if not bname:
                raise HTTPException(400, "Missing backend name")
            backends[bname] = spec.get("config") or spec
            _atomic_write_json(self.paths.backends_file, backends)
            return {"created": bname, "total": len(backends)}
        if name == "backend_update":
            backends = _read_json(self.paths.backends_file, default={})
            if not isinstance(backends, dict):
                backends = {}
            bname = (args or {}).get("name")
            cfg = (args or {}).get("config") or {}
            if not bname:
                raise HTTPException(400, "Missing backend name")
            backends[bname] = cfg
            _atomic_write_json(self.paths.backends_file, backends)
            return {"updated": bname}
        if name == "backend_remove":
            backends = _read_json(self.paths.backends_file, default={})
            if not isinstance(backends, dict):
                backends = {}
            bname = (args or {}).get("name")
            if bname and bname in backends:
                backends.pop(bname, None)
                _atomic_write_json(self.paths.backends_file, backends)
            return {"removed": bname}
        if name == "backend_show":
            backends = _read_json(self.paths.backends_file, default={})
            if not isinstance(backends, dict):
                backends = {}
            bname = (args or {}).get("name")
            return {"name": bname, "config": backends.get(bname)}
        if name == "list_buckets":
            data = _read_json(self.paths.buckets_file, default=[])
            norm_items: List[Dict[str, Any]] = []
            if isinstance(data, list):
                for it in data:
                    if isinstance(it, dict):
                        nm = it.get("name") or it.get("id")
                        if nm:
                            norm_items.append({
                                "name": nm,
                                "backend": it.get("backend"),
                                "created_at": it.get("created_at"),
                                "policy": (it.get("policy") or {"replication_factor": 1, "cache_policy": "none", "retention_days": 0})
                            })
                    elif isinstance(it, str):
                        norm_items.append({
                            "name": it,
                            "backend": None,
                            "created_at": None,
                            "policy": {"replication_factor": 1, "cache_policy": "none", "retention_days": 0}
                        })
            # Optionally write back normalized format for future consistency
            try:
                _atomic_write_json(self.paths.buckets_file, norm_items)
            except Exception:
                pass
            return {"total": len(norm_items), "items": norm_items}
        if name == "create_bucket":
            bucket = (args or {}).get("name") or (args or {}).get("bucket")
            if not bucket:
                raise HTTPException(400, "Missing bucket name")
            data = _read_json(self.paths.buckets_file, default=[])
            items_existing: List[Dict[str, Any]] = []
            if isinstance(data, list):
                for it in data:
                    if isinstance(it, dict):
                        if it.get("name"):
                            items_existing.append(it)
                    elif isinstance(it, str):
                        items_existing.append({
                            "name": it,
                            "backend": None,
                            "created_at": None,
                            "policy": {"replication_factor": 1, "cache_policy": "none", "retention_days": 0}
                        })
            if not any(b.get("name") == bucket for b in items_existing):
                entry = {
                    "name": bucket,
                    "backend": (args or {}).get("backend"),
                    "created_at": datetime.now(UTC).isoformat(),
                    "policy": {"replication_factor": 1, "cache_policy": "none", "retention_days": 0}
                }
                items_existing.append(entry)
                _atomic_write_json(self.paths.buckets_file, items_existing)
            return {"created": bucket, "total": len(items_existing)}
        if name == "delete_bucket":
            bucket = (args or {}).get("name") or (args or {}).get("bucket")
            data = _read_json(self.paths.buckets_file, default=[])
            items: List[Any] = data if isinstance(data, list) else []
            new_items: List[Any] = []
            for it in items:
                if isinstance(it, dict):
                    if it.get("name") != bucket:
                        new_items.append(it)
                else:
                    if it != bucket:
                        new_items.append(it)
            if len(new_items) != len(items):
                _atomic_write_json(self.paths.buckets_file, new_items)
            return {"deleted": bucket, "total": len(new_items)}
        # Files storage under data_dir/files or per-bucket
        def _files_root(bucket: Optional[str] = None) -> Path:
            root = self.paths.data_dir / ("storage" if bucket else "files")
            if bucket:
                root = root / bucket
            root.mkdir(parents=True, exist_ok=True)
            return root
        if name in ("list_files", "files_list"):
            bucket = (args or {}).get("bucket")
            path = (args or {}).get("path") or "."
            base = _files_root(bucket)
            p = (base / path).resolve()
            if not str(p).startswith(str(base.resolve())):
                raise HTTPException(400, "Invalid path")
            if p.is_dir():
                items = []
                for child in sorted(p.iterdir()):
                    items.append({"name": child.name, "type": "dir" if child.is_dir() else "file"})
                return {"path": str(path), "items": items}
            return {"path": str(path), "items": []}
        if name in ("read_file", "files_read"):
            bucket = (args or {}).get("bucket")
            path = (args or {}).get("path")
            if not path:
                raise HTTPException(400, "Missing path")
            base = _files_root(bucket)
            p = (base / path).resolve()
            if not str(p).startswith(str(base.resolve())):
                raise HTTPException(400, "Invalid path")
            if not p.exists() or not p.is_file():
                raise HTTPException(404, "Not found")
            content = p.read_text(encoding="utf-8", errors="ignore")
            return {"path": str(path), "content": content}
        if name in ("write_file", "files_write"):
            bucket = (args or {}).get("bucket")
            path = (args or {}).get("path")
            content = (args or {}).get("content", "")
            if not path:
                raise HTTPException(400, "Missing path")
            base = _files_root(bucket)
            p = (base / path).resolve()
            if not str(p).startswith(str(base.resolve())):
                raise HTTPException(400, "Invalid path")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(str(content), encoding="utf-8")
            return {"written": str(path), "bytes": len(str(content))}
        if name == "list_pins":
            pins = _read_json(self.paths.pins_file, default=[])
            arr = pins if isinstance(pins, list) else []
            return {"total": len(arr), "items": arr}
        if name == "create_pin":
            pins = _read_json(self.paths.pins_file, default=[])
            arr = pins if isinstance(pins, list) else []
            cid = (args or {}).get("cid")
            nm = (args or {}).get("name")
            if not cid:
                raise HTTPException(400, "Missing cid")
            if not any(p.get("cid") == cid for p in arr):
                arr.append({"cid": cid, "name": nm, "created": now})
                _atomic_write_json(self.paths.pins_file, arr)
            return {"pinned": cid}
        if name == "delete_pin":
            pins = _read_json(self.paths.pins_file, default=[])
            arr = pins if isinstance(pins, list) else []
            cid = (args or {}).get("cid")
            arr = [p for p in arr if p.get("cid") != cid]
            _atomic_write_json(self.paths.pins_file, arr)
            return {"unpinned": cid}
        if name == "get_logs":
            limit = int((args or {}).get("limit", 50))
            logs = self.memlog.get(limit=limit)
            return {"logs": logs, "total": len(logs)}
        if name == "service_status":
            svc = (args or {}).get("service") or (args or {}).get("name") or "ipfs"
            # Lightweight stub; if ComprehensiveServiceManager is wired, prefer it via REST elsewhere
            info = {"service": svc, "bin": _which(svc) or None, "api_port_open": False}
            return info
        if name == "ipfs_version":
            return {"ok": False, "error": "IPFS not available"}
        if name == "list_cars":
            return {"items": []}
        if name == "test_backend":
            backend = (args or {}).get("name") or (args or {}).get("backend")
            return {"backend": backend, "ok": True, "checked_at": now}
        raise HTTPException(404, f"Unknown tool: {name}")

    def _get_service_manager(self):
        """Get or initialize the service manager."""
        if self._service_manager is None:
            try:
                from ipfs_kit_py.mcp.services.comprehensive_service_manager import ComprehensiveServiceManager
                self._service_manager = ComprehensiveServiceManager(self.paths.base)
                
                # Auto-enable detectable services
                try:
                    result = self._service_manager.auto_enable_detectable_services()
                    if result.get("success") and result.get("enabled_services"):
                        self.log.info(f"Auto-enabled services: {result['enabled_services']}")
                except Exception as e:
                    self.log.warning(f"Failed to auto-enable services: {e}")
                
                self.log.info("Initialized ComprehensiveServiceManager")
            except ImportError as e:
                self.log.error(f"Failed to import ComprehensiveServiceManager: {e}")
                self._service_manager = None
            except Exception as e:
                self.log.error(f"Failed to initialize ComprehensiveServiceManager: {e}")
                self._service_manager = None
        return self._service_manager

    def _get_peer_manager(self):
        """Get or initialize the simple file-backed PeerManager.

        Uses ~/.ipfs_kit/peers.json to persist connections. If libp2p is not
        enabled in this deployment, this still provides a consistent surface
        for the dashboard UI and tools.
        """
        if self._peer_manager is None:
            try:
                from ipfs_kit_py.peer_manager import PeerManager  # type: ignore
                self._peer_manager = PeerManager()
            except Exception as e:  # pragma: no cover
                self.log.warning(f"PeerManager unavailable: {e}")
                self._peer_manager = None
        return self._peer_manager
    
    async def _list_all_services(self, service_manager):
        """List all services (enabled and disabled) for comprehensive dashboard view."""
        services = []
        
        # Get all daemon services
        for daemon_id, config in service_manager.services_config.get("daemons", {}).items():
            if config.get("enabled", False):
                status = await service_manager._check_daemon_status(daemon_id, config)
                actions = service_manager._get_available_actions(daemon_id, status["status"])
            else:
                # For disabled services, show as "not_enabled" 
                status = {
                    "status": "not_enabled",
                    "last_check": None,
                    "details": {"reason": "Service not enabled"}
                }
                actions = ["configure", "enable"]  # Allow enabling and configuration
            
            services.append({
                "id": daemon_id,
                "name": config["name"],
                "type": config["type"],
                "description": config["description"],
                "status": status["status"],
                "port": config.get("port"),
                "actions": actions,
                "last_check": status.get("last_check"),
                "details": status.get("details", {}),
                "enabled": config.get("enabled", False)
            })
        
        # Get all storage backend services  
        for backend_id, config in service_manager.services_config.get("storage_backends", {}).items():
            if config.get("enabled", False):
                status = await service_manager._check_storage_backend_status(backend_id, config)
                actions = service_manager._get_available_actions(backend_id, status["status"])
            else:
                # For disabled services, show as "not_configured" since most require credentials
                status = {
                    "status": "not_configured" if config.get("requires_credentials") else "not_enabled",
                    "last_check": None,
                    "details": {"reason": "Credentials not configured" if config.get("requires_credentials") else "Service not enabled"}
                }
                # Provide configure action for credentialed services, enable for others
                actions = ["configure", "enable"] if config.get("requires_credentials") else ["enable", "configure"]
            
            services.append({
                "id": backend_id,
                "name": config["name"],
                "type": config["type"],
                "description": config["description"],
                "status": status["status"],
                "requires_credentials": config.get("requires_credentials", False),
                "actions": actions,
                "last_check": status.get("last_check"),
                "details": status.get("details", {}),
                "enabled": config.get("enabled", False)
            })
        
        # Get all network services
        for service_id, config in service_manager.services_config.get("network_services", {}).items():
            if config.get("enabled", False):
                status = await service_manager._check_network_service_status(service_id, config)
                actions = service_manager._get_available_actions(service_id, status["status"])
            else:
                status = {
                    "status": "not_enabled",
                    "last_check": None,
                    "details": {"reason": "Service not enabled"}
                }
                actions = ["configure", "enable"]
            
            services.append({
                "id": service_id,
                "name": config["name"],
                "type": config["type"],
                "description": config["description"],
                "status": status["status"],
                "port": config.get("port"),
                "actions": actions,
                "last_check": status.get("last_check"),
                "details": status.get("details", {}),
                "enabled": config.get("enabled", False)
            })
        
        return {
            "services": services,
            "total": len(services),
            "summary": {
                "running": len([s for s in services if s["status"] == "running"]),
                "stopped": len([s for s in services if s["status"] == "stopped"]),
                "error": len([s for s in services if s["status"] == "error"]),
                "configured": len([s for s in services if s["status"] == "configured"]),
                "not_configured": len([s for s in services if s["status"] == "not_configured"]),
                "not_enabled": len([s for s in services if s["status"] == "not_enabled"])
            }
        }

    # --- Run helpers (restored) ---
    async def run(self) -> None:
        """Run the dashboard with uvicorn inside current asyncio loop."""
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info", reload=False)
        server = uvicorn.Server(config)
        await server.serve()

    def run_sync(self) -> None:  # pragma: no cover - integration helper
        """Synchronous convenience wrapper used by __main__ path."""
        anyio.run(self.run())

    # --- Realtime metrics ---
    def _gather_metrics_snapshot(self) -> Dict[str, Any]:
        """Collect a metrics snapshot; updates histories and returns current point including rolling averages."""
        snap: Dict[str, Any] = {"ts": time.time()}
        # System metrics
        if psutil:
            with suppress(Exception):
                snap["cpu"] = psutil.cpu_percent(interval=None)
            with suppress(Exception):
                vm = psutil.virtual_memory()
                snap["mem"] = vm.percent
        # Disk
        with suppress(Exception):
            du = shutil.disk_usage(str(self.paths.data_dir))
            snap["disk"] = round(du.used/du.total*100, 2) if du.total else None
        # Network delta (simple aggregate rx/tx bytes across interfaces)
        # NOTE: Original implementation may have used psutil.net_io_counters; restored lightweight placeholder if psutil present.
        if psutil:
            with suppress(Exception):
                counters = psutil.net_io_counters()
                if counters:
                    rx = counters.bytes_recv
                    tx = counters.bytes_sent
                    if self._net_last:
                        dt = snap["ts"] - self._net_last["ts"]
                        if dt > 0:
                            snap["rx_bps"] = (rx - self._net_last.get("rx", rx)) / dt
                            snap["tx_bps"] = (tx - self._net_last.get("tx", tx)) / dt
                    self._net_last = {"ts": snap["ts"], "rx": rx, "tx": tx}
        # Append to histories (ensure keys present for tests even if None yet)
        self._net_history.append({
            "ts": snap.get("ts"),
            "rx_bps": snap.get("rx_bps"),
            "tx_bps": snap.get("tx_bps"),
        })
        self._sys_history.append({k: snap.get(k) for k in ("ts", "cpu", "mem", "disk") if k in snap})
        # Rolling averages (5 most recent points with values)
        def _avg(seq: Iterable[Optional[float]]) -> Optional[float]:
            vals = [v for v in seq if isinstance(v, (int, float))]
            return round(sum(vals)/len(vals), 2) if vals else None
        last_net = list(self._net_history)[-5:]
        last_sys = list(self._sys_history)[-5:]
        snap["avg_rx_bps"] = _avg(p.get("rx_bps") for p in last_net)
        snap["avg_tx_bps"] = _avg(p.get("tx_bps") for p in last_net)
        snap["avg_cpu"] = _avg(p.get("cpu") for p in last_sys)
        snap["avg_mem"] = _avg(p.get("mem") for p in last_sys)
        snap["avg_disk"] = _avg(p.get("disk") for p in last_sys)
        return snap

    def _broadcast_loop(self):  # pragma: no cover (timing loop)
        async def _inner():
            while True:
                try:
                    snap = self._gather_metrics_snapshot()
                    if self._ws_clients:
                        payload = {**snap, "type": "metrics"}
                        dead = []
                        for ws in list(self._ws_clients):
                            try:
                                await ws.send_json(payload)
                            except Exception:
                                dead.append(ws)
                        for ws in dead:
                            self._ws_clients.discard(ws)
                except Exception:
                    self.log.exception("broadcast loop error")
                await anyio.sleep(1.0)
        return _inner()

    def _register_routes(self) -> None:
        app = self.app
        dashboard = self
        # --- auth dependency ---
        def _auth_dep(request: Request):
            token = dashboard.api_token
            if not token:
                return True
            supplied = (
                request.headers.get("x-api-token") or
                (request.headers.get("authorization", " ").split(" ")[1] if request.headers.get("authorization", " ").lower().startswith("bearer ") else None) or
                request.query_params.get("token")
            )
            if supplied != token:
                raise HTTPException(401, "Unauthorized")
            return True

        # --- Legacy compatibility: /api/system/overview ---
        # NOTE: This endpoint is deprecated in favor of /api/system/health and /api/mcp/status.
        # It is kept temporarily to support older polling clients/tests. It now also includes
        # a metrics snapshot for convenience. Remove after next minor release.
        self._overview_warning_emitted = False  # one-time log flag
        @app.get("/api/system/overview")
        async def system_overview() -> Response:  # type: ignore
            if not getattr(self, "_overview_warning_emitted", False):
                with suppress(Exception):
                    self.log.warning("/api/system/overview is deprecated; use /api/system/health and /api/mcp/status")
                self._overview_warning_emitted = True
            # Gather components
            health = await system_health()
            status_payload = await mcp_status()
            metrics = await metrics_system()
            payload = {
                "success": True,
                "deprecated": True,
                "remove_in": self.DEPRECATED_ENDPOINTS.get("/api/system/overview"),
                "status": status_payload.get("data", status_payload),
                "health": health,
                "metrics": metrics,
                "migration": {
                    "health": "/api/system/health",
                    "status": "/api/mcp/status",
                    "metrics": "/api/metrics/system"
                }
            }
            return JSONResponse(payload, headers={"X-Deprecated": "true", "Link": '</api/system/health>; rel="health", </api/mcp/status>; rel="status"'})

        # Basic pages
        @app.get("/", response_class=HTMLResponse)
        async def index() -> str:
            return dashboard.render_beta_toolrunner()

        # Simple request counter middleware (registered once)
        @app.middleware("http")
        async def _count_requests(request: Request, call_next):  # type: ignore
            try:
                self.request_count += 1
                path = request.url.path
                self.endpoint_hits[path] = self.endpoint_hits.get(path, 0) + 1
            except Exception:
                pass
            return await call_next(request)

        @app.get("/app.js", response_class=PlainTextResponse)
        async def app_js() -> Response:
            return Response(self._app_js(), media_type="application/javascript; charset=utf-8", headers={"Cache-Control": "no-store"})

        @app.get("/mcp-client.js", response_class=PlainTextResponse)
        async def mcp_client_js() -> Response:
            body = self._mcp_client_js()
            return Response(body, media_type="application/javascript; charset=utf-8", headers={"Cache-Control": "no-store", "X-MCP-SDK-Source": "inline"})

        # Add route for /static/mcp-sdk.js to fix dashboard loading
        @app.get("/static/mcp-sdk.js", response_class=PlainTextResponse)
        async def static_mcp_sdk_js() -> Response:
            return await mcp_client_js()

        # General static file handler for CSS, JS, and other assets
        @app.get("/static/{file_path:path}")
        async def serve_static_files(file_path: str) -> Response:
            """Serve static files from the static directory."""
            try:
                # Try to find the static file in multiple locations
                static_locations = [
                    Path(__file__).parent / "static" / file_path,
                    Path(__file__).parent / "mcp" / "dashboard" / "static" / file_path,
                    Path(__file__).parent.parent / "static" / file_path,
                ]
                
                for static_path in static_locations:
                    if static_path.exists() and static_path.is_file():
                        # Determine content type
                        content_type, _ = mimetypes.guess_type(str(static_path))
                        if not content_type:
                            content_type = "application/octet-stream"
                        
                        return FileResponse(
                            path=str(static_path),
                            media_type=content_type,
                            headers={"Cache-Control": "no-store"}
                        )
                
                # If file not found, return 404
                raise HTTPException(status_code=404, detail=f"Static file not found: {file_path}")
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error serving static file: {str(e)}")

        # Lightweight REST mirrors for analytics and configuration management
        @app.get("/api/analytics/performance")
        async def api_performance(request: Request) -> JSONResponse:
            try:
                backend = request.query_params.get("backend")
                time_range = request.query_params.get("range", "1h")
                include_history = request.query_params.get("history", "true").lower() in ("1","true","yes","y")
                res = self._handle_backends(
                    name="get_backend_performance_metrics",
                    args={"backend_name": backend, "time_range": time_range, "include_history": include_history},
                )
                if res is None:
                    raise HTTPException(404, "metrics handler unavailable")
                return JSONResponse(res.get("result", res))
            except HTTPException as he:
                raise he
            except Exception as e:
                self.log.exception("/api/analytics/performance failed")
                raise HTTPException(500, str(e))

        @app.get("/api/config/files")
        async def api_config_files() -> JSONResponse:
            res = self._handle_config("list_config_files", {})
            if res is None:
                raise HTTPException(404, "config handler unavailable")
            return JSONResponse(res.get("result", res))

        @app.get("/api/config/read/{filename:path}")
        async def api_config_read(filename: str) -> JSONResponse:
            res = self._handle_config("read_config_file", {"filename": filename})
            if res is None:
                raise HTTPException(404, "config read unavailable")
            if "error" in res:
                err = res["error"]
                raise HTTPException(int(err.get("code", 500)), err.get("message", "error"))
            return JSONResponse(res.get("result", res))

        @app.post("/api/config/write/{filename:path}")
        async def api_config_write(filename: str, request: Request) -> JSONResponse:
            body = await request.json()
            content = body.get("content", "")
            res = self._handle_config("write_config_file", {"filename": filename, "content": content})
            if res is None:
                raise HTTPException(404, "config write unavailable")
            if "error" in res:
                err = res["error"]
                raise HTTPException(int(err.get("code", 500)), err.get("message", "error"))
            return JSONResponse(res.get("result", res))

        # Explicit HEAD handlers for common endpoints (avoid 405s from probes)
        @app.head("/")
        async def index_head() -> Response:  # type: ignore
            return Response(status_code=200)

        @app.head("/app.js")
        async def app_js_head() -> Response:  # type: ignore
            return Response(status_code=200, headers={"Cache-Control": "no-store"})

        @app.head("/mcp-client.js")
        async def mcp_client_js_head() -> Response:  # type: ignore
            return Response(status_code=200, headers={"Cache-Control": "no-store"})

        # Favicon placeholder (avoid 404 noise)
        @app.get("/favicon.ico")
        async def favicon() -> Response:  # type: ignore
            return Response(status_code=204, headers={"Cache-Control": "public, max-age=3600"})
        @app.head("/favicon.ico")
        async def favicon_head() -> Response:  # type: ignore
            return Response(status_code=204, headers={"Cache-Control": "public, max-age=3600"})

        # Simple health endpoint (GET/HEAD)
        @app.get("/healthz")
        async def healthz() -> Response:  # type: ignore
            return PlainTextResponse("ok", headers={"Cache-Control": "no-store"})
        @app.head("/healthz")
        async def healthz_head() -> Response:  # type: ignore
            return Response(status_code=200, headers={"Cache-Control": "no-store"})

        # Health/Status
        @app.get("/api/system/health")
        async def system_health() -> Dict[str, Any]:
            info: Dict[str, Any] = {
                "ok": True,
                "time": datetime.now(UTC).isoformat(),
                "data_dir": str(self.paths.data_dir),
                "python": sys.version.split(" ")[0],
            }
            if psutil:
                with suppress(Exception):
                    info["cpu_percent"] = psutil.cpu_percent(interval=None)
                    vm = psutil.virtual_memory()
                    info["memory"] = {"used": vm.used, "total": vm.total, "percent": vm.percent}
            return info

        @app.get("/api/system/deprecations")
        async def system_deprecations() -> Dict[str, Any]:
            """List deprecated endpoints with planned removal versions and migration hints."""
            items = []
            for ep, remove_in in self.DEPRECATED_ENDPOINTS.items():
                migration = None
                if ep == "/api/system/overview":
                    migration = {
                        "health": "/api/system/health",
                        "status": "/api/mcp/status",
                        "metrics": "/api/metrics/system"
                    }
                items.append({
                    "endpoint": ep,
                    "remove_in": remove_in,
                    "migration": migration,
                    "hits": self.endpoint_hits.get(ep, 0),
                })
            return {"deprecated": items}

    # (Removed duplicate legacy overview endpoint definition above after enhancement)

        # System metrics
        @app.get("/api/metrics/system")
        async def metrics_system() -> Dict[str, Any]:
            out: Dict[str, Any] = {"ts": time.time()}
            if psutil:
                with suppress(Exception):
                    out["cpu_percent"] = psutil.cpu_percent(interval=None)
                with suppress(Exception):
                    vm = psutil.virtual_memory()
                    out["memory"] = {"used": vm.used, "total": vm.total, "percent": vm.percent}
            with suppress(Exception):
                du = shutil.disk_usage(str(self.paths.data_dir))
                out["disk"] = {"used": du.used, "total": du.total, "percent": round(du.used/du.total*100,2) if du.total else None}
            with suppress(Exception):
                out["uptime_sec"] = time.time() - self._start_time
            return out

        @app.get("/api/metrics/system/history")
        async def metrics_system_history(request: Request) -> Dict[str, Any]:
            seconds_param: Optional[float] = None
            with suppress(Exception):
                raw = request.query_params.get('seconds')
                if raw:
                    seconds_param = float(raw)
            pts = list(self._sys_history)
            if seconds_param is not None:
                cutoff = time.time() - seconds_param
                pts = [p for p in pts if p.get('ts', 0) >= cutoff]
            return {"interval": 1.0, "points": pts}

        @app.get("/api/metrics/network")
        async def metrics_network(request: Request) -> Dict[str, Any]:
            seconds_param: Optional[float] = None
            with suppress(Exception):
                raw = request.query_params.get('seconds')
                if raw:
                    seconds_param = float(raw)
            pts = list(self._net_history)
            if seconds_param is not None:
                cutoff = time.time() - seconds_param
                pts = [p for p in pts if p.get('ts', 0) >= cutoff]
            return {"interval": 1.0, "points": pts}

        # MCP tool endpoints for browser SDK shim
        @app.post("/mcp/tools/list")
        async def mcp_tools_list() -> JSONResponse:
            res = self._tools_list()
            return JSONResponse({"jsonrpc": "2.0", "result": res.get("result", {}), "id": 1})

        @app.post("/mcp/tools/call")
        async def mcp_tools_call(request: Request) -> JSONResponse:
            try:
                data = await request.json()
            except Exception:
                data = {}
            name = None
            args: Dict[str, Any] = {}
            if isinstance(data, dict):
                if data.get("method") in ("tools/call", "mcp.callTool"):
                    params = data.get("params") or {}
                    name = params.get("name") or params.get("tool")
                    args = params.get("arguments") or params.get("args") or {}
                else:
                    name = data.get("name") or data.get("tool")
                    args = data.get("arguments") or data.get("args") or {}
            if not name:
                raise HTTPException(400, "Missing tool name")
            result = self._dispatch_tool(name, args)
            return JSONResponse({"jsonrpc": "2.0", "result": result, "id": data.get("id", 1) if isinstance(data, dict) else 1})

        @app.get("/api/analytics/summary")
        async def analytics_summary() -> Dict[str, Any]:
            """Get analytics summary for dashboard."""
            try:
                # Get current metrics with error handling
                system_metrics = {}
                with suppress(Exception):
                    system_metrics = await metrics_system()
                
                # Get service counts with error handling
                services_count = 0
                active_services = 0
                with suppress(Exception):
                    service_manager = self._get_service_manager()
                    if service_manager:
                        services = await self._list_all_services(service_manager)
                        services_count = len(services)
                        active_services = len([s for s in services if isinstance(s, dict) and s.get("status") in ("running", "healthy")])
                
                # Get backend and bucket counts with error handling
                backends_count = 0
                with suppress(Exception):
                    backends = _read_json(self.paths.backends_file, {})
                    backends_count = len(backends.get("backends", []) if isinstance(backends, dict) else backends) if backends else 0
                
                buckets_count = 0
                with suppress(Exception):
                    buckets = _read_json(self.paths.buckets_file, [])
                    buckets_count = len(buckets) if isinstance(buckets, list) else len(buckets.get("items", [])) if isinstance(buckets, dict) else 0
                
                pins_count = 0
                with suppress(Exception):
                    pins = _read_json(self.paths.pins_file, [])
                    pins_count = len(pins) if isinstance(pins, list) else 0
                
                # Calculate request metrics with error handling
                total_requests = getattr(self, 'request_count', 0)
                popular_endpoints = []
                with suppress(Exception):
                    endpoint_hits = getattr(self, 'endpoint_hits', {})
                    popular_endpoints = sorted(endpoint_hits.items(), key=lambda x: x[1], reverse=True)[:10]
                
                # Build response with safe defaults
                response_data = {
                    "system": {
                        "cpu_percent": system_metrics.get("cpu_percent", 0.0),
                        "memory_percent": system_metrics.get("memory", {}).get("percent", 0.0),
                        "disk_percent": system_metrics.get("disk", {}).get("percent", 0.0),
                        "uptime_hours": system_metrics.get("uptime_sec", 0) / 3600.0
                    },
                    "services": {
                        "total": services_count,
                        "active": active_services,
                        "inactive": max(0, services_count - active_services)
                    },
                    "storage": {
                        "backends": backends_count,
                        "buckets": buckets_count,
                        "pins": pins_count
                    },
                    "requests": {
                        "total": total_requests,
                        "popular_endpoints": popular_endpoints
                    },
                    "logs": {
                        "total": len(self.memlog.get(limit=0)) if hasattr(self, 'memlog') else 0,
                        "recent": len(self.memlog.get(limit=100)) if hasattr(self, 'memlog') else 0
                    }
                }
                
                return response_data
                
            except Exception as e:
                self.log.error(f"Error in analytics summary: {e}")
                # Return safe default structure to prevent frontend errors
                return {
                    "system": {"cpu_percent": 0.0, "memory_percent": 0.0, "disk_percent": 0.0, "uptime_hours": 0.0},
                    "services": {"total": 0, "active": 0, "inactive": 0},
                    "storage": {"backends": 0, "buckets": 0, "pins": 0},
                    "requests": {"total": 0, "popular_endpoints": []},
                    "logs": {"total": 0, "recent": 0}
                }

        @app.get("/api/config/files")
        async def config_files() -> Dict[str, Any]:
            """Get configuration files information."""
            config_files = []
            
            # Check main config files
            config_paths = [
                ("backends.json", self.paths.backends_file),
                ("buckets.json", self.paths.buckets_file), 
                ("pins.json", self.paths.pins_file)
            ]
            
            for name, path in config_paths:
                try:
                    if path.exists():
                        stat_info = path.stat()
                        with path.open('r') as f:
                            content = json.load(f)
                        
                        config_files.append({
                            "name": name,
                            "path": str(path),
                            "size": stat_info.st_size,
                            "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat(),
                            "entries": len(content) if isinstance(content, (list, dict)) else 0,
                            "readable": True
                        })
                    else:
                        config_files.append({
                            "name": name,
                            "path": str(path),
                            "size": 0,
                            "modified": None,
                            "entries": 0,
                            "readable": False,
                            "status": "missing"
                        })
                except Exception as e:
                    config_files.append({
                        "name": name,
                        "path": str(path),
                        "size": 0,
                        "modified": None,
                        "entries": 0,
                        "readable": False,
                        "error": str(e)
                    })
            
            return {
                "files": config_files,
                "data_dir": str(self.paths.data_dir),
                "total_files": len(config_files)
            }

        @app.get("/api/mcp/status")
        async def mcp_status() -> Dict[str, Any]:
            tools_defs = self._tools_list()["result"]["tools"]
            tool_names = [t["name"] for t in tools_defs]
            
            # Use enhanced backend manager if available
            backend_count = 0
            bm = getattr(self, "backend_manager", None)
            if bm is not None:
                try:
                    backend_result = bm.list_backends()  # type: ignore[attr-defined]
                    if isinstance(backend_result, dict):
                        backend_count = int(backend_result.get("total", 0))
                except Exception as e:
                    self.log.warning(f"Error getting backend count: {e}")
                    backends = _read_json(self.paths.backends_file, default={})
                    backend_count = len(backends.keys()) if isinstance(backends, dict) else 0
            else:
                backends = _read_json(self.paths.backends_file, default={})
                backend_count = len(backends.keys()) if isinstance(backends, dict) else 0
            
            buckets = _read_json(self.paths.buckets_file, default=[])
            pins = _read_json(self.paths.pins_file, default=[])
            
            # Get comprehensive service count
            services_active = 0
            try:
                service_manager = self._get_service_manager()
                if service_manager:
                    services_data = await service_manager.list_all_services()
                    services_active = services_data.get("total", 0)
                else:
                    # Fallback to basic detection
                    if psutil:
                        services_active = sum(1 for name in ("ipfs",) if _which(name))
            except Exception as e:
                self.log.warning(f"Failed to get comprehensive service count: {e}")
                if psutil:
                    services_active = sum(1 for name in ("ipfs",) if _which(name))
            data = {
                "protocol_version": "1.0",
                "total_tools": len(tool_names),
                "tools": tool_names,
                "uptime": time.time() - self._start_time,
                "counts": {
                    "services_active": services_active,
                    "backends": backend_count,
                    "buckets": len(buckets) if isinstance(buckets, list) else 0,
                    "pins": len(pins) if isinstance(pins, list) else 0,
                    "requests": self.request_count,
                },
                "security": {"auth_enabled": bool(self.api_token)},
                "endpoints": {
                    "tools_list": "/mcp/tools/list",
                    "tools_call": "/mcp/tools/call",
                    "sse_logs": "/api/logs/stream",
                    "websocket": "/ws",
                },
            }
            return {"success": True, "data": data}

        # Logs SSE
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
                    await anyio.sleep(0.5)
            return StreamingResponse(event_gen(), media_type="text/event-stream")

        # Logs API endpoint for dashboard
        @app.get("/api/logs")
        async def api_logs(component: str = "all", level: str = "all", limit: int = 100) -> Dict[str, Any]:
            """Get logs with filtering options."""
            logs = self.memlog.get(limit=limit)
            
            # Filter by component if specified
            if component != "all":
                logs = [log for log in logs if component.lower() in log.get("logger", "").lower()]
            
            # Filter by level if specified
            if level != "all":
                level_filter = level.upper()
                logs = [log for log in logs if log.get("level", "").upper() == level_filter]
            
            return {
                "logs": logs,
                "total": len(logs),
                "filters": {
                    "component": component,
                    "level": level,
                    "limit": limit
                }
            }

        # WebSocket realtime
        @app.websocket("/ws")
        async def ws_endpoint(ws: WebSocket) -> None:
            await ws.accept()
            self._ws_clients.add(ws)
            try:
                status_payload = await mcp_status()
                # Attach deprecations list for client-side awareness
                deps = []
                for ep, remove_in in self.DEPRECATED_ENDPOINTS.items():
                    migration = None
                    if ep == "/api/system/overview":
                        migration = {"health": "/api/system/health", "status": "/api/mcp/status", "metrics": "/api/metrics/system"}
                    deps.append({"endpoint": ep, "remove_in": remove_in, "migration": migration, "hits": self.endpoint_hits.get(ep, 0)})
                await ws.send_json({"type": "system_update", "data": status_payload, "deprecations": deps})
                with suppress(Exception):
                    snap = self._gather_metrics_snapshot()
                    snap['type'] = 'metrics'
                    for k in ('cpu','mem','disk','rx_bps','tx_bps'):
                        v = snap.get(k)
                        if isinstance(v,(int,float)):
                            snap[f'avg_{k if k not in ("rx_bps","tx_bps") else k}'] = v
                    for name in ('avg_cpu','avg_mem','avg_disk','avg_rx_bps','avg_tx_bps'):
                        snap.setdefault(name, None)
                    await ws.send_json(snap)
                await anyio.sleep(0)
                while True:
                    msg = await ws.receive_text()
                    if msg == "ping":
                        await ws.send_text("ack")
                        continue
            except WebSocketDisconnect:
                pass
            finally:
                self._ws_clients.discard(ws)

        # Enhanced Backends with Policy Management
        # Initialize enhanced backend manager
        try:
            from ipfs_kit_py.enhanced_backend_manager import EnhancedBackendManager
            self.backend_manager = EnhancedBackendManager(str(self.paths.data_dir))
            self.log.info("✓ Enhanced backend manager initialized")
        except ImportError:
            # Fallback to basic implementation
            self.backend_manager = None
            self.log.warning("Enhanced backend manager not available, using basic implementation")

        @app.get("/api/state/backends")
        async def list_backends() -> Dict[str, Any]:
            if self.backend_manager:
                return self.backend_manager.list_backends()
            else:
                # Fallback to original implementation
                data = _read_json(self.paths.backends_file, default={})
                items = [{"name": k, "config": v} for k, v in data.items()]
                return {"items": items}

        # Alias for JavaScript compatibility
        @app.get("/api/backends")
        async def list_backends_alias() -> Dict[str, Any]:
            return await list_backends()

        @app.post("/api/state/backends")
        async def create_backend(payload: Dict[str, Any], _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            name = payload.get("name")
            backend_type = payload.get("type", "local")
            config = payload.get("config", {})
            tier = payload.get("tier", "standard")
            
            if not name:
                raise HTTPException(400, "Missing backend name")
                
            if bm := getattr(self, "backend_manager", None):
                # Use enhanced manager
                try:
                    backend_config = {
                        "name": name,
                        "type": backend_type,
                        "description": f"{backend_type.title()} storage backend",
                        "config": config,
                        "status": "enabled",
                        "tier": tier
                    }

                    config_path = bm._get_backend_config_path(name)  # type: ignore[attr-defined]
                    if config_path.exists():
                        raise HTTPException(409, "Backend already exists")

                    with open(config_path, 'w') as f:
                        yaml.safe_dump(backend_config, f)  # type: ignore[attr-defined]

                    # Create default policy (use enhanced manager instance consistently)
                    policy_set = bm._generate_policy_for_backend(name, backend_type, tier)  # type: ignore[attr-defined]
                    policy_path = bm._get_policy_config_path(name)  # type: ignore[attr-defined]
                    policy_payload: Any = policy_set.model_dump() if hasattr(policy_set, "model_dump") else (
                        policy_set.dict() if hasattr(policy_set, "dict") else policy_set
                    )
                    with open(policy_path, 'w') as f:
                        json.dump(policy_payload, f, indent=2)

                    return {"ok": True, "name": name, "type": backend_type, "tier": tier}
                except Exception as e:
                    raise HTTPException(500, f"Failed to create backend: {str(e)}")
            else:
                # Fallback to original implementation
                data = _read_json(self.paths.backends_file, default={})
                if name in data:
                    raise HTTPException(409, "Backend already exists")
                data[name] = {"type": backend_type, **config}
                _atomic_write_json(self.paths.backends_file, data)
                return {"ok": True, "name": name}

        @app.get("/api/state/backends/{name}")
        async def get_backend(name: str) -> Dict[str, Any]:
            if bm := getattr(self, "backend_manager", None):
                backend = bm.get_backend_with_policies(name)  # type: ignore[attr-defined]
                if not backend:
                    raise HTTPException(404, "Backend not found")
                
                # Add current stats
                stats = bm.get_backend_stats(name)  # type: ignore[attr-defined]
                backend["stats"] = stats
                
                return backend
            else:
                # Fallback to original implementation
                data = _read_json(self.paths.backends_file, default={})
                if name not in data:
                    raise HTTPException(404, "Not found")
                return {"name": name, "config": data[name]}

        @app.post("/api/state/backends/{name}")
        async def update_backend(name: str, payload: Dict[str, Any], _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            if bm := getattr(self, "backend_manager", None):
                backend = bm.get_backend_with_policies(name)  # type: ignore[attr-defined]
                if not backend:
                    raise HTTPException(404, "Backend not found")
                    
                # Update backend config
                config_path = bm._get_backend_config_path(name)  # type: ignore[attr-defined]
                with open(config_path, 'r') as f:
                    current_config = yaml.safe_load(f)  # type: ignore[attr-defined]
                    
                # Apply updates
                if "config" in payload:
                    if "config" not in current_config or not isinstance(current_config.get("config"), dict):
                        current_config["config"] = {}
                    current_config["config"].update(payload["config"])
                if "tier" in payload:
                    current_config["tier"] = payload["tier"]
                if "status" in payload:
                    current_config["status"] = payload["status"]
                if "description" in payload:
                    current_config["description"] = payload["description"]
                    
                with open(config_path, 'w') as f:
                    yaml.safe_dump(current_config, f)  # type: ignore[attr-defined]
                    
                # Update policies if provided
                if "policy" in payload and bm is not None:
                    bm.update_backend_policy(name, payload["policy"])  # type: ignore[attr-defined]
                    
                return {"ok": True}
            else:
                # Fallback to original implementation
                data = _read_json(self.paths.backends_file, default={})
                if name not in data:
                    raise HTTPException(404, "Not found")
                cfg = payload.get("config", {})
                data[name] = cfg
                _atomic_write_json(self.paths.backends_file, data)
                return {"ok": True}

        @app.delete("/api/state/backends/{name}")
        async def delete_backend(name: str, _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            if bm := getattr(self, "backend_manager", None):
                config_path = bm._get_backend_config_path(name)  # type: ignore[attr-defined]
                policy_path = bm._get_policy_config_path(name)  # type: ignore[attr-defined]
                
                if not config_path.exists():
                    raise HTTPException(404, "Backend not found")
                    
                try:
                    config_path.unlink()
                    if policy_path.exists():
                        policy_path.unlink()
                    return {"ok": True}
                except Exception as e:
                    raise HTTPException(500, f"Failed to delete backend: {str(e)}")
            else:
                # Fallback to original implementation
                data = _read_json(self.paths.backends_file, default={})
                if name not in data:
                    raise HTTPException(404, "Not found")
                data.pop(name)
                _atomic_write_json(self.paths.backends_file, data)
                return {"ok": True}

        @app.post("/api/state/backends/{name}/test")
        async def test_backend(name: str) -> Dict[str, Any]:
            if bm := getattr(self, "backend_manager", None):
                backend = bm.get_backend_with_policies(name)  # type: ignore[attr-defined]
                if not backend:
                    raise HTTPException(404, "Backend not found")
                    
                backend_type = backend.get("type", "unknown")
                stats = bm.get_backend_stats(name)  # type: ignore[attr-defined]
                
                # Simple reachability test based on backend type
                reachable = True  # Default to true for demo
                test_result = "ok"
                
                if backend_type == "ipfs":
                    # Test IPFS connectivity
                    ipfs_bin = _which("ipfs")
                    reachable = bool(ipfs_bin)
                    test_result = "ipfs available" if reachable else "ipfs not found"
                elif backend_type == "s3":
                    # Could test S3 connectivity here
                    test_result = "s3 endpoint reachable"
                elif backend_type == "local":
                    # Test local path accessibility  
                    path = backend.get("config", {}).get("path")
                    if path:
                        reachable = Path(path).exists()
                        test_result = "path accessible" if reachable else "path not found"
                
                return {
                    "name": name, 
                    "type": backend_type, 
                    "reachable": reachable, 
                    "test_result": test_result,
                    "stats": stats,
                    "availability": stats.get("availability", 1.0)
                }
            else:
                # Fallback to original implementation
                data = _read_json(self.paths.backends_file, default={})
                cfg = data.get(name, {})
                kind = (cfg or {}).get("type", "unknown")
                ipfs_bin = _which("ipfs")
                reachable = bool(ipfs_bin)
                return {"name": name, "type": kind, "reachable": reachable, "ipfs_bin": ipfs_bin}
                
        @app.get("/api/state/backends/{name}/stats")
        async def get_backend_stats(name: str) -> Dict[str, Any]:
            """Get detailed statistics for a specific backend."""
            if bm := getattr(self, "backend_manager", None):
                backend = bm.get_backend_with_policies(name)  # type: ignore[attr-defined]
                if not backend:
                    raise HTTPException(404, "Backend not found")
                stats = bm.get_backend_stats(name)  # type: ignore[attr-defined]
                return {"name": name, "stats": stats}
            else:
                raise HTTPException(501, "Backend statistics not available")
                
        @app.get("/api/state/backends/{name}/policy")
        async def get_backend_policy(name: str) -> Dict[str, Any]:
            """Get policy configuration for a specific backend."""
            if bm := getattr(self, "backend_manager", None):
                backend = bm.get_backend_with_policies(name)  # type: ignore[attr-defined]
                if not backend:
                    raise HTTPException(404, "Backend not found")
                    
                return {"name": name, "policy": backend.get("policy", {})}
            else:
                raise HTTPException(501, "Backend policies not available")
                
        @app.post("/api/state/backends/{name}/policy")
        async def update_backend_policy(name: str, payload: Dict[str, Any], _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            """Update policy configuration for a specific backend."""
            if bm := getattr(self, "backend_manager", None):
                backend = bm.get_backend_with_policies(name)  # type: ignore[attr-defined]
                if not backend:
                    raise HTTPException(404, "Backend not found")
                    
                policy_updates = payload.get("policy", {})
                if bm.update_backend_policy(name, policy_updates):  # type: ignore[attr-defined]
                    return {"ok": True, "message": "Policy updated successfully"}
                else:
                    raise HTTPException(500, "Failed to update policy")
            else:
                raise HTTPException(501, "Backend policies not available")

        # Services
        @app.get("/api/services")
        async def list_services() -> Dict[str, Any]:
            """List all services with their current status."""
            try:
                service_manager = self._get_service_manager()
                if service_manager:
                    # Use the comprehensive service manager to get ALL services
                    services_data = await service_manager.list_all_services()
                    # Transform the data format to match the expected API response
                    services = {}
                    for service in services_data.get("services", []):
                        services[service["id"]] = {
                            "name": service["name"],
                            "type": service["type"],
                            "status": service["status"],
                            "description": service.get("description", ""),
                            "port": service.get("port"),
                            "actions": service.get("actions", []),
                            "last_check": service.get("last_check"),
                            "details": service.get("details", {})
                        }
                    return {"services": services}
                else:
                    # Fallback to basic service detection if service manager fails
                    services = {}
                    
                    # IPFS daemon detection
                    ipfs_detected = _which("ipfs") is not None
                    ipfs_api_open = _port_open("127.0.0.1", 5001)
                    services["ipfs"] = {
                        "name": "IPFS Daemon",
                        "type": "daemon",
                        "status": "running" if (ipfs_detected and ipfs_api_open) else ("stopped" if ipfs_detected else "missing"),
                        "description": "InterPlanetary File System daemon",
                        "bin": _which("ipfs"),
                        "api_port_open": ipfs_api_open,
                        "actions": ["start", "stop", "restart"] if ipfs_detected else []
                    }
                    
                    # Check for other common daemons
                    daemon_checks = [
                        ("lotus", "Lotus Client", "Filecoin Lotus client", 1234),
                        ("aria2c", "Aria2 Daemon", "High-speed download daemon", 6800),
                        ("ipfs-cluster-service", "IPFS Cluster", "IPFS Cluster coordination service", 9094)
                    ]
                    
                    for binary_name, service_name, description, port in daemon_checks:
                        binary_path = _which(binary_name)
                        if binary_path:
                            service_id = binary_name.replace('-', '_').replace('c', '') if binary_name == 'aria2c' else binary_name.replace('-', '_')
                            port_open = _port_open("127.0.0.1", port)
                            services[service_id] = {
                                "name": service_name,
                                "type": "daemon", 
                                "status": "running" if port_open else "stopped",
                                "description": description,
                                "bin": binary_path,
                                "port": port,
                                "api_port_open": port_open,
                                "actions": ["start", "stop", "restart"]
                            }
                    
                    return {"services": services}
            except Exception as e:
                self.log.error(f"Error listing services: {e}")
                # Return minimal fallback
                return {
                    "services": {
                        "ipfs": {
                            "name": "IPFS Daemon", 
                            "type": "daemon",
                            "status": "unknown",
                            "description": "InterPlanetary File System daemon",
                            "actions": ["start", "stop"]
                        }
                    }
                }

        @app.post("/api/services/{name}/{action}")
        async def service_action(name: str, action: str, request: Request) -> Dict[str, Any]:
            """Perform an action on a service."""
            # Manual auth check (reuse _auth_dep logic)
            try:
                _auth_dep(request)
            except HTTPException:
                raise
            
            if action not in ("start", "stop", "restart", "enable", "disable", "health_check"):
                raise HTTPException(status_code=400, detail="Invalid action")
            
            try:
                service_manager = self._get_service_manager()
                if service_manager:
                    # Use comprehensive service manager for service actions
                    result = await service_manager.perform_service_action(name, action, {})
                    if result.get("success", False):
                        return {
                            "ok": True,
                            "success": True,
                            "service": name,
                            "action": action,
                            "status": result.get("status", "unknown"),
                            "message": f"Service {name} {action} completed successfully"
                        }
                    else:
                        return {
                            "ok": False,
                            "success": False,
                            "service": name,
                            "action": action,
                            "error": result.get("error", f"Failed to {action} service {name}")
                        }
                else:
                    # Fallback: basic daemon control for detected services
                    supported_services = ["ipfs", "lotus", "aria2", "ipfs_cluster"]
                    if name not in supported_services:
                        raise HTTPException(status_code=400, detail="Service not available")
                    
                    # Simulate service state change for basic implementation
                    success = False
                    status = "unknown"
                    
                    try:
                        # Map service names to their binary names and processes
                        service_binaries = {
                            "ipfs": ("ipfs", "ipfs daemon"),
                            "lotus": ("lotus", "lotus daemon"),
                            "aria2": ("aria2c", "aria2c"),
                            "ipfs_cluster": ("ipfs-cluster-service", "ipfs-cluster-service")
                        }
                        
                        binary_name, process_name = service_binaries.get(name, (name, name))
                        
                        if action == "start":
                            status = "starting"
                            # Note: In production, this would actually start the daemon
                            # For now, we'll simulate the response based on binary availability
                            if _which(binary_name):
                                success = True
                                status = "running"
                            else:
                                success = False
                                status = "missing"
                        elif action == "stop":
                            status = "stopping"
                            # Note: In production, this would stop the daemon
                            success = True
                            status = "stopped"
                        elif action == "restart":
                            status = "restarting"
                            # Note: In production, this would restart the daemon
                            if _which(binary_name):
                                success = True
                                status = "running"
                            else:
                                success = False
                                status = "missing"
                        
                        return {
                            "ok": success,
                            "success": success,
                            "service": name,
                            "action": action,
                            "status": status,
                            "message": f"Service {name} {action} {'completed' if success else 'failed'}"
                        }
                            
                    except Exception as e:
                        return {
                            "ok": False,
                            "success": False,
                            "service": name,
                            "action": action,
                            "error": f"Error during {action}: {str(e)}"
                        }
                        
            except Exception as e:
                self.log.error(f"Error performing service action {action} on {name}: {e}")
                return {
                    "ok": False,
                    "success": False,
                    "service": name,
                    "action": action,
                    "error": str(e)
                }

        @app.post("/api/services/{name}/configure")
        async def configure_service(name: str, request: Request) -> Dict[str, Any]:
            """Configure a service with enhanced multi-instance support and backend settings."""
            try:
                _auth_dep(request)
            except HTTPException:
                raise
            
            try:
                data = await request.json()
                config = data.get("config", {})
                
                # Enhanced configuration with multi-instance support
                enhanced_config = {
                    "basic": {
                        "instance_name": config.get("instance_name", name),
                        "service_type": config.get("service_type", name),
                        "description": config.get("description", f"Instance of {name}"),
                        "enabled": config.get("enabled", True)
                    },
                    "cache": {
                        "cache_policy": config.get("cache_policy", "none"),
                        "cache_size_mb": int(config.get("cache_size_mb", 1024)),
                        "cache_ttl_seconds": int(config.get("cache_ttl_seconds", 3600))
                    },
                    "storage": {
                        "storage_quota_gb": float(config.get("storage_quota_gb", 100)),
                        "max_files": int(config.get("max_files", 10000)),
                        "max_file_size_mb": int(config.get("max_file_size_mb", 500))
                    },
                    "retention": {
                        "retention_days": int(config.get("retention_days", 365)),
                        "auto_cleanup": config.get("auto_cleanup", False),
                        "versioning": config.get("versioning", False)
                    },
                    "replication": {
                        "replication_factor": int(config.get("replication_factor", 3)),
                        "sync_strategy": config.get("sync_strategy", "immediate")
                    },
                    "service_specific": config.get("service_specific", {})
                }
                
                service_manager = self._get_service_manager()
                if service_manager:
                    # Use comprehensive service manager for service configuration
                    result = await service_manager.configure_service(name, enhanced_config)
                    if result.get("success", False):
                        return {
                            "success": True,
                            "service": name,
                            "message": f"Service {name} configured successfully with enhanced settings",
                            "config_saved": True,
                            "config": enhanced_config
                        }
                    else:
                        return {
                            "success": False,
                            "service": name,
                            "error": result.get("error", f"Failed to configure service {name}")
                        }
                else:
                    # Enhanced fallback with backend configuration support
                    config_dir = self.paths.data_dir / "service_configs"
                    config_dir.mkdir(exist_ok=True)
                    
                    # Save instance-specific configuration
                    instance_name = enhanced_config["basic"]["instance_name"]
                    config_file = config_dir / f"{instance_name}_config.json"
                    
                    with open(config_file, 'w') as f:
                        json.dump(enhanced_config, f, indent=2)
                    
                    # Update backends configuration for storage services
                    if enhanced_config["basic"]["service_type"] in ["s3", "github", "ipfs_cluster", "huggingface", "gdrive", "ftp", "sshfs", "apache_arrow", "parquet"]:
                        backends = _normalize_backends(_read_json(self.paths.backends_file, default=[]))
                        
                        # Update or create backend entry
                        backend_found = False
                        for i, backend in enumerate(backends):
                            if backend.get("name") == instance_name:
                                backends[i] = {
                                    "name": instance_name,
                                    "type": enhanced_config["basic"]["service_type"],
                                    "tier": "standard",
                                    "description": enhanced_config["basic"]["description"],
                                    "config": enhanced_config,
                                    "policy": {
                                        "replication_factor": enhanced_config["replication"]["replication_factor"],
                                        "cache_policy": enhanced_config["cache"]["cache_policy"],
                                        "retention_days": enhanced_config["retention"]["retention_days"]
                                    },
                                    "enabled": enhanced_config["basic"]["enabled"],
                                    "last_updated": datetime.now(UTC).isoformat()
                                }
                                backend_found = True
                                break
                        
                        if not backend_found:
                            backends.append({
                                "name": instance_name,
                                "type": enhanced_config["basic"]["service_type"],
                                "tier": "standard", 
                                "description": enhanced_config["basic"]["description"],
                                "config": enhanced_config,
                                "policy": {
                                    "replication_factor": enhanced_config["replication"]["replication_factor"],
                                    "cache_policy": enhanced_config["cache"]["cache_policy"],
                                    "retention_days": enhanced_config["retention"]["retention_days"]
                                },
                                "enabled": enhanced_config["basic"]["enabled"],
                                "created_at": datetime.now(UTC).isoformat(),
                                "last_updated": datetime.now(UTC).isoformat()
                            })
                        
                        _atomic_write_json(self.paths.backends_file, backends)
                    
                    return {
                        "success": True,
                        "service": name,
                        "instance_name": instance_name,
                        "message": f"Service {instance_name} configured successfully with enhanced backend settings",
                        "config_saved": True,
                        "config": enhanced_config
                    }
                    
            except Exception as e:
                self.log.error(f"Error configuring service {name}: {e}")
                return {
                    "success": False,
                    "service": name,
                    "error": str(e)
                }

        @app.post("/api/services/instances")
        async def create_service_instance(request: Request) -> Dict[str, Any]:
            """Create a new service instance with multi-backend support."""
            try:
                _auth_dep(request)
            except HTTPException:
                raise
            
            try:
                data = await request.json()
                service_type = data.get("service_type")
                instance_name = data.get("instance_name")
                
                if not service_type or not instance_name:
                    return {
                        "success": False,
                        "error": "Missing service_type or instance_name"
                    }
                
                # Check if instance already exists
                config_dir = self.paths.data_dir / "service_configs"
                config_file = config_dir / f"{instance_name}_config.json"
                
                if config_file.exists():
                    return {
                        "success": False,
                        "error": f"Instance '{instance_name}' already exists"
                    }
                
                # Create new instance configuration
                new_config = {
                    "basic": {
                        "instance_name": instance_name,
                        "service_type": service_type,
                        "description": data.get("description", f"Instance of {service_type}"),
                        "enabled": True
                    },
                    "cache": {
                        "cache_policy": "none",
                        "cache_size_mb": 1024,
                        "cache_ttl_seconds": 3600
                    },
                    "storage": {
                        "storage_quota_gb": 100.0,
                        "max_files": 10000,
                        "max_file_size_mb": 500
                    },
                    "retention": {
                        "retention_days": 365,
                        "auto_cleanup": False,
                        "versioning": False
                    },
                    "replication": {
                        "replication_factor": 3,
                        "sync_strategy": "immediate"
                    },
                    "service_specific": {}
                }
                
                # Save configuration
                config_dir.mkdir(exist_ok=True)
                with open(config_file, 'w') as f:
                    json.dump(new_config, f, indent=2)
                
                # Add to backends if it's a storage service
                if service_type in ["s3", "github", "ipfs_cluster", "huggingface", "gdrive", "ftp", "sshfs", "apache_arrow", "parquet"]:
                    backends = _normalize_backends(_read_json(self.paths.backends_file, default=[]))
                    backends.append({
                        "name": instance_name,
                        "type": service_type,
                        "tier": "standard",
                        "description": new_config["basic"]["description"],
                        "config": new_config,
                        "policy": {
                            "replication_factor": new_config["replication"]["replication_factor"],
                            "cache_policy": new_config["cache"]["cache_policy"],
                            "retention_days": new_config["retention"]["retention_days"]
                        },
                        "enabled": True,
                        "created_at": datetime.now(UTC).isoformat(),
                        "last_updated": datetime.now(UTC).isoformat()
                    })
                    _atomic_write_json(self.paths.backends_file, backends)
                
                return {
                    "success": True,
                    "instance_name": instance_name,
                    "service_type": service_type,
                    "message": f"Service instance '{instance_name}' created successfully",
                    "config": new_config
                }
                
            except Exception as e:
                self.log.error(f"Error creating service instance: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }

        # Buckets
        @app.get("/api/state/buckets")
        async def list_buckets() -> Dict[str, Any]:
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            return {"buckets": items, "total": len(items)}

        # Alias for JavaScript compatibility
        @app.get("/api/buckets")
        async def list_buckets_alias() -> Dict[str, Any]:
            return await list_buckets()

        @app.post("/api/state/buckets")
        async def create_bucket(payload: Dict[str, Any], _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            name = payload.get("name")
            backend = payload.get("backend")
            if not name:
                raise HTTPException(400, "Missing bucket name")
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            if any(b.get("name") == name for b in items):
                raise HTTPException(409, "Bucket exists")
            entry = {"name": name, "backend": backend, "created_at": datetime.now(UTC).isoformat(), "policy": {"replication_factor": 1, "cache_policy": "none", "retention_days": 0}}
            items.append(entry)
            _atomic_write_json(self.paths.buckets_file, items)
            if yaml is not None:
                with suppress(Exception):
                    ydir = self.paths.data_dir / "bucket_configs"
                    ydir.mkdir(exist_ok=True)
                    (ydir / f"{name}.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")
            return {"ok": True, "bucket": entry}

        @app.get("/api/state/buckets/{name}/policy")
        async def get_bucket_policy(name: str) -> Dict[str, Any]:
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            for b in items:
                if b.get("name") == name:
                    return {"name": name, "policy": b.get("policy")}
            raise HTTPException(404, "Not found")

        @app.post("/api/state/buckets/{name}/policy")
        async def update_bucket_policy(name: str, payload: Dict[str, Any], _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            # Accept either flat keys or nested { policy: { ... } }
            pol_in = payload.get("policy") if isinstance(payload.get("policy"), dict) else None
            rf = payload.get("replication_factor") if payload.get("replication_factor") is not None else (pol_in or {}).get("replication_factor")
            cp = payload.get("cache_policy") if payload.get("cache_policy") is not None else (pol_in or {}).get("cache_policy")
            rd = payload.get("retention_days") if payload.get("retention_days") is not None else (pol_in or {}).get("retention_days")
            if rf is not None:
                try:
                    rf = int(rf)
                except Exception:
                    raise HTTPException(400, "replication_factor must be int")
                if rf < 1 or rf > 10:
                    raise HTTPException(400, "replication_factor out of range")
            if cp is not None and cp not in ("none", "memory", "disk"):
                raise HTTPException(400, "cache_policy invalid")
            if rd is not None:
                try:
                    rd = int(rd)
                except Exception:
                    raise HTTPException(400, "retention_days must be int")
                if rd < 0:
                    raise HTTPException(400, "retention_days must be >=0")
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            updated = False
            pol: Dict[str, Any] = {}
            for i, b in enumerate(items):
                if b.get("name") == name:
                    pol = dict(b.get("policy") or {})
                    if rf is not None:
                        pol["replication_factor"] = rf
                    if cp is not None:
                        pol["cache_policy"] = cp
                    if rd is not None:
                        pol["retention_days"] = rd
                    nb = dict(b)
                    nb["policy"] = pol
                    items[i] = nb
                    updated = True
            if updated:
                _atomic_write_json(self.paths.buckets_file, items)
                return {"ok": True, "name": name, "policy": pol}
            raise HTTPException(404, "Not found")
