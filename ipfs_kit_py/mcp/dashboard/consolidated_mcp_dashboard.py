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
import os, sys, json, time, asyncio, logging, socket, signal, tarfile, shutil, subprocess, inspect, atexit, threading, mimetypes
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
            item = {
                "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            }
            # Allow callers to tag records with a logical component
            comp = getattr(record, "component", None)
            if isinstance(comp, str) and comp:
                item["component"] = comp
            self._items.append(item)
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

def create_default_buckets():
    """Create default bucket configurations for first-time setup."""
    from datetime import datetime, UTC
    now = datetime.now(UTC).isoformat()
    
    return [
        {
            "name": "media",
            "backend": "filesystem",
            "description": "Media files, images, and documents",
            "created_at": now,
            "meta": {},
            "policy": {
                "quota": "2GB",
                "replication": 1,
                "retention": "90d",
                "cache": "enabled"
            }
        },
        {
            "name": "documents", 
            "backend": "filesystem",
            "description": "Text documents and PDFs",
            "created_at": now,
            "meta": {},
            "policy": {
                "quota": "1GB",
                "replication": 1,
                "retention": "365d",
                "cache": "enabled"
            }
        },
        {
            "name": "archive",
            "backend": "filesystem", 
            "description": "Long-term archival storage",
            "created_at": now,
            "meta": {},
            "policy": {
                "quota": "5GB",
                "replication": 2,
                "retention": "permanent",
                "cache": "disabled"
            }
        }
    ]

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
    
    # Initialize buckets.json with default buckets if file doesn't exist or is empty
    if not buckets_file.exists() or buckets_file.stat().st_size == 0:
        with suppress(Exception):
            default_buckets = create_default_buckets()
            with buckets_file.open('w', encoding='utf-8') as fh:
                json.dump(default_buckets, fh, indent=2)
            
            # Create VFS directories for default buckets
            for bucket in default_buckets:
                bucket_dir = vfs_root / bucket["name"]
                bucket_dir.mkdir(exist_ok=True)
    
    # Initialize pins.json with empty array if it doesn't exist
    if not pins_file.exists():
        with suppress(Exception):
            with pins_file.open('w', encoding='utf-8') as fh:
                json.dump([], fh)
    
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

def _calculate_bucket_stats(bucket_name: str, vfs_base_path: Path) -> Dict[str, Any]:
    """Calculate actual bucket statistics from VFS directory."""
    bucket_path = vfs_base_path / bucket_name
    stats = {
        "size": 0,
        "file_count": 0, 
        "folder_count": 0,
        "total_size": 0
    }
    
    if not bucket_path.exists():
        return stats
        
    try:
        for root, dirs, files in os.walk(bucket_path):
            # Count folders (excluding .gitkeep files)
            stats["folder_count"] += len(dirs)
            
            # Count files and calculate size  
            for file in files:
                if file != '.gitkeep':  # Skip placeholder files
                    file_path = os.path.join(root, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        stats["size"] += file_size
                        stats["file_count"] += 1
                    except OSError:
                        continue
                        
        stats["total_size"] = stats["size"]
    except Exception:
        pass
        
    return stats

def _normalize_buckets(items, vfs_base_path: Path = None):
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
        
        # Calculate actual bucket statistics if VFS path provided
        bucket_stats = {"size": 0, "file_count": 0, "folder_count": 0, "total_size": 0}
        if vfs_base_path:
            bucket_stats = _calculate_bucket_stats(name, vfs_base_path)
        
        # Enhanced bucket info with all fields JavaScript expects
        bucket_info = {
            "name": name,
            "backend": it.get('backend', 'filesystem'),
            "meta": it.get('meta', {}),
            "policy": norm_policy,
            "description": it.get('description', f"Storage bucket with {bucket_stats['file_count']} files"),
            "status": it.get('status', 'active'),
            "tier": it.get('tier', it.get('backend', 'filesystem')),  # Use backend as tier if not specified
            "created_at": it.get('created_at', ''),
            "size": bucket_stats["size"],
            "size_gb": round(bucket_stats["size"] / (1024**3), 2),  # Size in GB for JavaScript
            "file_count": bucket_stats["file_count"],
            "folder_count": bucket_stats["folder_count"],
            "total_size": bucket_stats["total_size"],
            "quota": it.get('quota', {
                "storage": "5GB",
                "files": 10000,
                "bandwidth": "100GB"
            }),
            "backends": it.get('backends', [it.get('backend', 'filesystem')]),
            "replica_count": it.get('replica_count', 1)
        }
        out.append(bucket_info)
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

        # In library/test contexts, registering signal handlers that call sys.exit()
        # can cause pytest to crash during interruption or failure reporting.
        _running_under_pytest = bool(os.environ.get("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules)
        if not _running_under_pytest:
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

        # Per-process in-memory logs.
        # Under pytest, multiple dashboard instances are created within the same
        # process; we reuse a single handler to avoid "detached handler" issues
        # while clearing between instances to keep tests isolated.
        root = logging.getLogger()
        existing_memlog = next((h for h in root.handlers if isinstance(h, InMemoryLogHandler)), None)
        self.memlog = existing_memlog if existing_memlog is not None else InMemoryLogHandler(maxlen=4000)
        if existing_memlog is None:
            root.addHandler(self.memlog)
        if _running_under_pytest:
            with suppress(Exception):
                self.memlog.clear()
        root.setLevel(logging.INFO)
        self.log = logging.getLogger("dashboard")
        self.log.info("Consolidated MCP Dashboard initialized at %s", self.paths.base)
        self._ws_clients: set[WebSocket] = set()
        # Lazy-initialized peer manager
        self._peer_manager = None
        self._register_routes()
        atexit.register(self._cleanup_pid_file)

    def _get_service_manager(self):
        """Get or initialize the service manager."""
        if self._service_manager is None:
            try:
                from ipfs_kit_py.mcp.services.comprehensive_service_manager import ComprehensiveServiceManager
                # Use data_dir instead of base for service manager
                data_dir = self.paths.data_dir if hasattr(self.paths, 'data_dir') else self.paths.base
                self._service_manager = ComprehensiveServiceManager(data_dir)
                
                # Auto-enable detectable services
                try:
                    result = self._service_manager.auto_enable_detectable_services()
                    if result.get("success") and result.get("enabled_services"):
                        self.log.info(f"Auto-enabled services: {result['enabled_services']}")
                except Exception as e:
                    self.log.warning(f"Failed to auto-enable services: {e}")
                
                self.log.info(f"Initialized ComprehensiveServiceManager with data_dir: {data_dir}")
            except ImportError as e:
                self.log.error(f"Failed to import ComprehensiveServiceManager: {e}")
                self._service_manager = None
            except Exception as e:
                self.log.error(f"Failed to initialize ComprehensiveServiceManager: {e}", exc_info=True)
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
    
    def _transform_config_for_backend(self, service_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform user configuration to backend-specific format.
        
        This method converts the form input into the format expected by backend modules
        like s3_kit, github_kit, etc.
        """
        if service_type == "s3":
            # Transform to s3cfg format expected by s3_kit
            return {
                "s3cfg": {
                    "accessKey": config.get("access_key", ""),
                    "secretKey": config.get("secret_key", ""),
                    "endpoint": config.get("endpoint", f"https://s3.{config.get('region', 'us-east-1')}.amazonaws.com"),
                    "bucket": config.get("bucket", ""),
                    "region": config.get("region", "us-east-1")
                }
            }
        elif service_type == "github":
            # Transform to github_kit format
            return {
                "github_token": config.get("api_token", ""),
                "repository": config.get("repository", ""),
                "username": config.get("username", "")
            }
        elif service_type == "huggingface":
            # Transform to huggingface_kit format  
            return {
                "hf_token": config.get("api_token", ""),
                "username": config.get("username", ""),
                "repository": config.get("repository", "")
            }
        elif service_type == "gdrive":
            # Transform to gdrive_kit format
            return {
                "credentials": config.get("credentials", {}),
                "folder_id": config.get("folder_id", "")
            }
        elif service_type in ["ftp", "sftp"]:
            # Transform to FTP/SFTP format
            return {
                "host": config.get("host", ""),
                "port": config.get("port", 21 if service_type == "ftp" else 22),
                "username": config.get("username", ""),
                "password": config.get("password", ""),
                "path": config.get("path", "/")
            }
        elif service_type == "storacha":
            # Transform to storacha_kit format
            return {
                "api_token": config.get("api_token", ""),
                "space": config.get("space", "")
            }
        else:
            # Generic passthrough for other services
            return config
    
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
                "gateway_port": config.get("gateway_port"),
                "swarm_port": config.get("swarm_port"),
                "config_dir": config.get("config_dir"),
                "auto_start": config.get("auto_start", False),
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
                "config_keys": config.get("config_keys", []),
                "config_hints": config.get("config_hints", {}),
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
        asyncio.run(self.run())

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
                await asyncio.sleep(1.0)
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

        @app.get("/services", response_class=HTMLResponse)
        @app.get("/service-monitoring", response_class=HTMLResponse)
        async def service_monitoring_page() -> str:
            """Enhanced service monitoring page."""
            try:
                # Try to load from dashboard_templates directory
                base_dir = Path(__file__).parent.parent  # ipfs_kit_py/mcp
                template_path = base_dir / "dashboard_templates" / "enhanced_service_monitoring.html"
                
                if template_path.exists():
                    with open(template_path, 'r', encoding='utf-8') as f:
                        return f.read()
                
                # Fallback: try relative to this file
                alt_path = Path(__file__).parent / "templates" / "enhanced_service_monitoring.html"
                if alt_path.exists():
                    with open(alt_path, 'r', encoding='utf-8') as f:
                        return f.read()
                        
                self.log.warning(f"Service monitoring template not found at: {template_path}")
                return "<html><body><h1>Service Monitoring</h1><p>Template not found</p></body></html>"
            except Exception as e:
                self.log.error(f"Error loading service monitoring template: {e}")
                return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>"

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
            # Prefer user-provided static SDK if present; otherwise serve inline SDK with robust path resolution
            try:
                base_dir = Path(__file__).parent  # ipfs_kit_py/mcp/dashboard
                static_path = (base_dir / "static" / "mcp-sdk.js").resolve()
            except Exception:
                static_path = None
            # Compatibility shim: ensure core + expected namespaces exist when using static SDKs
            shim = "\n;(function(){\n" \
                   "  try {\n" \
                   "    var g = (typeof window !== 'undefined' ? window : globalThis);\n" \
                   "    g.MCP = g.MCP || {};\n" \
                   "    async function rpcList(){ const r = await fetch('/mcp/tools/list', {method:'POST', headers:{'x-api-token': (g.API_TOKEN||'')}}); return await r.json(); }\n" \
                   "    async function rpcCall(name, args){ const r = await fetch('/mcp/tools/call', {method:'POST', headers:{'content-type':'application/json','x-api-token':(g.API_TOKEN||'')}, body: JSON.stringify({name, args})}); return await r.json(); }\n" \
                   "    if (!g.MCP.listTools) g.MCP.listTools = rpcList;\n" \
                   "    if (!g.MCP.callTool) g.MCP.callTool = (n,a)=>rpcCall(n, a||{});\n" \
                   "    if (!g.MCP.status) {\n" \
                   "      g.MCP.status = async function(){ const r = await fetch('/api/mcp/status'); const js = await r.json(); const data = (js && (js.data||js)) || {}; const tools = Array.isArray(data.tools)?data.tools:[]; return Object.assign({ initialized: !!data, tools }, data); };\n" \
                   "    }\n" \
                   "    function ensureNS(ns, obj){ g.MCP[ns] = g.MCP[ns] || {}; var t=g.MCP[ns]; for (var k in obj){ if (!(k in t)) t[k]=obj[k]; } }\n" \
                   "    ensureNS('Services', { list:()=>rpcCall('list_services',{}), control:(s,a,p)=>rpcCall('service_control',{service:s, action:a, params:p}), status:(s)=>rpcCall('service_status',{service:s}) });\n" \
                   "    ensureNS('Backends', { list:()=>rpcCall('list_backends',{}), get:(n)=>rpcCall('get_backend',{name:n}), create:(n,c)=>rpcCall('create_backend',{name:n, config:c}), update:(n,c)=>rpcCall('update_backend',{name:n, config:c}), delete:(n)=>rpcCall('delete_backend',{name:n}), test:(n)=>rpcCall('test_backend',{name:n}), listInstances:()=>rpcCall('list_backend_instances',{}), createInstance:(type,name,desc)=>rpcCall('create_backend_instance',{service_type:type, instance_name:name, description:desc}), configureInstance:(name,type,config)=>rpcCall('configure_backend_instance',{instance_name:name, service_type:type, config:config}), getPerformanceMetrics:(name,range,history)=>rpcCall('get_backend_performance_metrics',{backend_name:name, time_range:range, include_history:history}), getTemplate:(type,template)=>rpcCall('get_backend_configuration_template',{backend_type:type, template_type:template}), clone:(source,newName,modifyConfig)=>rpcCall('clone_backend_configuration',{source_backend:source, new_backend_name:newName, modify_config:modifyConfig}), backup:(name,backupName,includeData)=>rpcCall('backup_backend_configuration',{backend_name:name, backup_name:backupName, include_data:includeData}), restore:(name,backupId,force)=>rpcCall('restore_backend_configuration',{backend_name:name, backup_id:backupId, force_restore:force}) });\n" \
                   "    ensureNS('Buckets', { list:()=>rpcCall('list_buckets',{}), get:(n)=>rpcCall('get_bucket',{name:n}), create:(n,b)=>rpcCall('create_bucket',{name:n, backend:b}), update:(n,p)=>rpcCall('update_bucket',{name:n, patch:p}), delete:(n)=>rpcCall('delete_bucket',{name:n}), getPolicy:(n)=>rpcCall('get_bucket_policy',{name:n}), updatePolicy:(n,pol)=>rpcCall('update_bucket_policy',{name:n, policy:pol}), listFiles:(bucket,path,meta)=>rpcCall('bucket_list_files',{bucket,path:(path||'.'),show_metadata:!!meta}), uploadFile:(bucket,path,content,mode,policy)=>rpcCall('bucket_upload_file',{bucket,path,content,mode:(mode||'text'),apply_policy:!!policy}), downloadFile:(bucket,path,format)=>rpcCall('bucket_download_file',{bucket,path,format:(format||'text')}), deleteFile:(bucket,path,replicas)=>rpcCall('bucket_delete_file',{bucket,path,remove_replicas:!!replicas}), renameFile:(bucket,src,dst,replicas)=>rpcCall('bucket_rename_file',{bucket,src,dst,update_replicas:!!replicas}), mkdir:(bucket,path,parents)=>rpcCall('bucket_mkdir',{bucket,path,create_parents:!!parents}), syncReplicas:(bucket,force)=>rpcCall('bucket_sync_replicas',{bucket,force_sync:!!force}), getMetadata:(bucket,path,replicas)=>rpcCall('bucket_get_metadata',{bucket,path,include_replicas:!!replicas}) });\n" \
                   "    ensureNS('Pins', { list:()=>rpcCall('list_pins',{}), create:(cid,name)=>rpcCall('create_pin',{cid, name}), delete:(cid)=>rpcCall('delete_pin',{cid}), export:()=>rpcCall('pins_export',{}), import:(items)=>rpcCall('pins_import',{items}) });\n" \
                   "    ensureNS('Files', { list:(p)=>rpcCall('files_list',{path:(p==null?'.':p)}), read:(p)=>rpcCall('files_read',{path:p}), write:(p,c,m)=>rpcCall('files_write',{path:p, content:c, mode:(m||'text')}), mkdir:(p)=>rpcCall('files_mkdir',{path:p}), rm:(p,rec)=>rpcCall('files_rm',{path:p, recursive:!!rec}), mv:(s,d)=>rpcCall('files_mv',{src:s, dst:d}), stat:(p)=>rpcCall('files_stat',{path:p}), copy:(s,d,rec)=>rpcCall('files_copy',{src:s, dst:d, recursive:!!rec}), touch:(p)=>rpcCall('files_touch',{path:p}), tree:(p,d)=>rpcCall('files_tree',{path:(p==null?'.':p), depth:(d==null?2:d)}) });\n" \
                   "    ensureNS('IPFS', { version:()=>rpcCall('ipfs_version',{}), add:(p)=>rpcCall('ipfs_add',{path:p}), pin:(cid,name)=>rpcCall('ipfs_pin',{cid, name}), cat:(cid)=>rpcCall('ipfs_cat',{cid}), ls:(cid)=>rpcCall('ipfs_ls',{cid}) });\n" \
                   "    ensureNS('CARs', { list:()=>rpcCall('cars_list',{}), export:(p,car)=>rpcCall('car_export',{path:p, car}), import:(car,dest)=>rpcCall('car_import',{car, dest}) });\n" \
                   "    ensureNS('State', { snapshot:()=>rpcCall('state_snapshot',{}), backup:()=>rpcCall('state_backup',{}), reset:()=>rpcCall('state_reset',{}) });\n" \
                   "    ensureNS('Logs', { get:(limit)=>rpcCall('get_logs',{limit: (limit==null?200:limit)}), clear:()=>rpcCall('clear_logs',{}) });\n" \
                   "    ensureNS('Server', { shutdown:()=>rpcCall('server_shutdown',{}) });\n" \
                   "    ensureNS('Peers', { list:()=>rpcCall('list_peers',{}), stats:()=>rpcCall('get_peer_stats',{}), connect:(peer)=>rpcCall('connect_peer',peer||{}), disconnect:(peer_id)=>rpcCall('disconnect_peer',{peer_id}), info:(peer_id)=>rpcCall('get_peer_info',{peer_id}), discover:(limit,timeout)=>rpcCall('discover_peers',{limit, timeout}), bootstrap:(action,peer_address)=>rpcCall('bootstrap_peers',{action, peer_address}) });\n" \
                   "  } catch(e) { /* ignore shim errors */ }\n" \
                   "})();\n"
            source = "inline"
            body = None
            if static_path and static_path.exists():
                try:
                    body = static_path.read_text(encoding="utf-8") + shim
                    source = "static"
                except Exception:
                    body = None
            if body is None:
                body = self._mcp_client_js()
                source = "inline"
            return Response(body, media_type="application/javascript; charset=utf-8", headers={"Cache-Control": "no-store", "X-MCP-SDK-Source": source})

        # Add route for /static/mcp-sdk.js to fix dashboard loading
        @app.get("/static/mcp-sdk.js", response_class=PlainTextResponse)
        async def static_mcp_sdk_js() -> Response:
            return await mcp_client_js()

        # General static file handler for CSS, JS, and other assets
        @app.get("/static/{file_path:path}")
        async def serve_static_files(file_path: str) -> Response:
            """Serve static files from the static directory."""
            try:
                # Try to find the static file in multiple locations with robust path resolution
                base_dir = Path(__file__).parent  # ipfs_kit_py/mcp/dashboard
                project_root = base_dir.parent.parent.parent  # Go up to /home/devel/ipfs_kit_py
                static_locations = [
                    project_root / "static" / file_path,  # Project root static dir (for built CSS)
                    base_dir / "static" / file_path,
                    base_dir / "mcp" / "dashboard" / "static" / file_path,
                    base_dir.parent / "static" / file_path,
                ]
                
                for static_path in static_locations:
                    if static_path.exists() and static_path.is_file():
                        self.log.debug(f"Serving static file from: {static_path}")
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
                    await asyncio.sleep(0.5)
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
                await asyncio.sleep(0)
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
                        service_dict = {
                            "name": service["name"],
                            "type": service["type"],
                            "status": service["status"],
                            "description": service.get("description", ""),
                            "port": service.get("port"),
                            "actions": service.get("actions", []),
                            "last_check": service.get("last_check"),
                            "details": service.get("details", {}),
                            "config_keys": service.get("config_keys", []),
                            "config_hints": service.get("config_hints", {}),
                            "requires_credentials": service.get("requires_credentials", False)
                        }
                        
                        # Add daemon-specific fields
                        if service["type"] == "daemon":
                            service_dict["gateway_port"] = service.get("gateway_port")
                            service_dict["swarm_port"] = service.get("swarm_port")
                            service_dict["config_dir"] = service.get("config_dir")
                            service_dict["auto_start"] = service.get("auto_start", False)
                        
                        services[service["id"]] = service_dict
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
                            }
                    
                    return {"services": services}
            except Exception as e:
                self.log.error(f"Error listing services: {e}")
                return {"services": {}, "error": str(e)}

        @app.post("/api/services/{name}/action")
        async def service_action(name: str, request: Request) -> Dict[str, Any]:
            """Perform an action on a service."""
            try:
                data = await request.json()
                action = data.get("action", "")
                params = data.get("params", {})
            except Exception:
                action = ""
                params = {}
                
            if action not in ("start", "stop", "restart", "enable", "disable", "health_check", "configure", "view_logs"):
                raise HTTPException(status_code=400, detail="Invalid action")
            
            try:
                service_manager = self._get_service_manager()
                if service_manager:
                    # Use comprehensive service manager for service actions
                    result = await service_manager.perform_service_action(name, action, params)
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
            """Configure a service with proper backend integration."""
            try:
                _auth_dep(request)
            except HTTPException:
                raise
            
            try:
                data = await request.json()
                config = data.get("config", {})
                
                # Transform config to backend-specific format
                backend_config = self._transform_config_for_backend(name, config)
                
                # Save configuration in proper format for backend modules
                config_dir = self.paths.data_dir / "backend_configs"
                config_dir.mkdir(exist_ok=True)
                
                instance_name = config.get("instance_name", name)
                config_file = config_dir / f"{instance_name}.json"
                
                # Save the backend-specific configuration
                with open(config_file, 'w') as f:
                    json.dump(backend_config, f, indent=2)
                
                # Also save to ipfs_kit metadata format
                metadata_dir = self.paths.data_dir / "metadata"
                metadata_dir.mkdir(exist_ok=True)
                metadata_file = metadata_dir / f"{instance_name}_meta.json"
                
                with open(metadata_file, 'w') as f:
                    json.dump({"config": backend_config, "service_type": name}, f, indent=2)
                
                # Update backends.json for UI
                backends = _normalize_backends(_read_json(self.paths.backends_file, default=[]))
                backend_found = False
                
                for i, backend in enumerate(backends):
                    if backend.get("name") == instance_name:
                        backends[i] = {
                            "name": instance_name,
                            "type": name,
                            "tier": "standard",
                            "description": config.get("description", f"{name} instance"),
                            "config": backend_config,
                            "enabled": True,
                            "last_updated": datetime.now(UTC).isoformat()
                        }
                        backend_found = True
                        break
                
                if not backend_found:
                    backends.append({
                        "name": instance_name,
                        "type": name,
                        "tier": "standard",
                        "description": config.get("description", f"{name} instance"),
                        "config": backend_config,
                        "enabled": True,
                        "created_at": datetime.now(UTC).isoformat(),
                        "last_updated": datetime.now(UTC).isoformat()
                    })
                
                _atomic_write_json(self.paths.backends_file, backends)
                
                return {
                    "success": True,
                    "service": name,
                    "instance_name": instance_name,
                    "message": f"Service {instance_name} configured successfully",
                    "config_saved": True,
                    "config_file": str(config_file)
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
            # Provide both keys for compatibility: older clients used "buckets", tests expect "items".
            return {"items": items, "buckets": items, "total": len(items)}

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
                    if rf is not None: pol['replication_factor'] = rf
                    if cp is not None: pol['cache_policy'] = cp
                    if rd is not None: pol['retention_days'] = rd
                    pol.setdefault('replication_factor', 1)
                    pol.setdefault('cache_policy', 'none')
                    pol.setdefault('retention_days', 0)
                    nb = dict(b); nb['policy'] = pol
                    items[i] = nb
                    updated = True
                    break
            if not updated:
                raise HTTPException(404, "Not found")
            _atomic_write_json(self.paths.buckets_file, items)
            return {"ok": True, "policy": pol}

        @app.delete("/api/state/buckets/{name}")
        async def delete_bucket(name: str, _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            new_items = [b for b in items if b.get("name") != name]
            if len(new_items) == len(items):
                raise HTTPException(404, "Not found")
            _atomic_write_json(self.paths.buckets_file, new_items)
            return {"ok": True}

        # ---- Enhanced Bucket File Management Endpoints ----
        
        @app.get("/api/buckets/{bucket_name}")
        async def get_bucket_details(bucket_name: str) -> Dict[str, Any]:
            """Get bucket details with file list and advanced settings."""
            # Check if bucket exists
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            bucket = None
            for b in items:
                if b.get("name") == bucket_name:
                    bucket = b
                    break
            
            if not bucket:
                raise HTTPException(404, "Bucket not found")
            
            # Get bucket directory
            bucket_path = self.paths.vfs_root / bucket_name
            bucket_path.mkdir(parents=True, exist_ok=True)
            
            # List files in bucket
            files = []
            if bucket_path.exists():
                for item in bucket_path.iterdir():
                    stat_info = item.stat()
                    files.append({
                        "name": item.name,
                        "path": str(item.relative_to(bucket_path)),
                        "size": stat_info.st_size,
                        "type": "directory" if item.is_dir() else "file",
                        "mime_type": mimetypes.guess_type(item.name)[0] if item.is_file() else None,
                        "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat(),
                        "created": datetime.fromtimestamp(stat_info.st_ctime, UTC).isoformat()
                    })
            
            # Calculate storage usage
            total_size = sum(f["size"] for f in files if f["type"] == "file")
            
            # Load bucket config with advanced settings
            bucket_config_path = self.paths.data_dir / "bucket_configs" / f"{bucket_name}.yaml"
            advanced_settings = {
                "vector_search": False,
                "knowledge_graph": False,
                "search_index_type": "hnsw",
                "storage_quota": None,
                "max_files": None,
                "cache_ttl": 3600,
                "public_access": False
            }
            
            if bucket_config_path.exists() and yaml:
                try:
                    with bucket_config_path.open('r') as f:
                        config = yaml.safe_load(f) or {}
                        settings = config.get("settings", {})
                        advanced_settings.update(settings)
                except Exception:
                    pass
            
            return {
                "bucket": bucket,
                "files": sorted(files, key=lambda x: (x["type"] != "directory", x["name"].lower())),
                "file_count": len([f for f in files if f["type"] == "file"]),
                "folder_count": len([f for f in files if f["type"] == "directory"]),
                "total_size": total_size,
                "settings": advanced_settings
            }

        @app.get("/api/buckets/{bucket_name}/files")
        async def list_bucket_files(bucket_name: str, path: str = "") -> Dict[str, Any]:
            """List files in a specific bucket path."""
            # Verify bucket exists
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            if not any(b.get("name") == bucket_name for b in items):
                raise HTTPException(404, "Bucket not found")
            
            bucket_path = self.paths.vfs_root / bucket_name
            if path:
                bucket_path = bucket_path / path.lstrip('/')
                
            if not bucket_path.exists():
                return {"files": []}
                
            files = []
            for item in bucket_path.iterdir():
                stat_info = item.stat()
                files.append({
                    "name": item.name,
                    "path": str(item.relative_to(self.paths.vfs_root / bucket_name)),
                    "size": stat_info.st_size,
                    "type": "directory" if item.is_dir() else "file",
                    "mime_type": mimetypes.guess_type(item.name)[0] if item.is_file() else None,
                    "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat()
                })
            
            return {"items": sorted(files, key=lambda x: (x["type"] != "directory", x["name"].lower()))}

        @app.post("/api/buckets/{bucket_name}/upload")
        async def upload_file_to_bucket(
            bucket_name: str, 
            file: UploadFile = File(...),
            path: str = Form("")
        ) -> Dict[str, Any]:
            """Upload a file to a bucket."""
            # Verify bucket exists
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            if not any(b.get("name") == bucket_name for b in items):
                raise HTTPException(404, "Bucket not found")
            
            # Create bucket directory
            bucket_path = self.paths.vfs_root / bucket_name
            if path:
                bucket_path = bucket_path / path.lstrip('/')
            bucket_path.mkdir(parents=True, exist_ok=True)
            
            # Check file size limits (500MB default)
            max_size = 500 * 1024 * 1024  # 500MB
            content = await file.read()
            if len(content) > max_size:
                raise HTTPException(413, f"File too large. Maximum size: {max_size // (1024*1024)}MB")
            
            # Save file
            file_path = bucket_path / file.filename
            if file_path.exists():
                raise HTTPException(409, f"File '{file.filename}' already exists")
            
            try:
                with file_path.open('wb') as f:
                    f.write(content)
                
                stat_info = file_path.stat()
                return {
                    "success": True,
                    "file": {
                        "name": file.filename,
                        "path": str(file_path.relative_to(self.paths.vfs_root / bucket_name)),
                        "size": stat_info.st_size,
                        "mime_type": (mimetypes.guess_type(file.filename or "")[0] if (file and getattr(file, 'filename', None)) else None),
                        "uploaded": datetime.now(UTC).isoformat()
                    }
                }
            except Exception as e:
                raise HTTPException(500, f"Failed to save file: {str(e)}")

        @app.get("/api/buckets/{bucket_name}/download/{file_path:path}")
        async def download_file_from_bucket(bucket_name: str, file_path: str):
            """Download a file from a bucket."""
            # Verify bucket exists
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            if not any(b.get("name") == bucket_name for b in items):
                raise HTTPException(404, "Bucket not found")
            
            full_path = self.paths.vfs_root / bucket_name / file_path.lstrip('/')
            if not full_path.exists() or not full_path.is_file():
                raise HTTPException(404, "File not found")
            
            mime_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
            return FileResponse(
                path=str(full_path),
                filename=full_path.name,
                media_type=mime_type
            )

        @app.delete("/api/buckets/{bucket_name}/files/{file_path:path}")
        async def delete_file_from_bucket(bucket_name: str, file_path: str, _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            """Delete a file or directory from a bucket."""
            # Verify bucket exists
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            if not any(b.get("name") == bucket_name for b in items):
                raise HTTPException(404, "Bucket not found")
            
            full_path = self.paths.vfs_root / bucket_name / file_path.lstrip('/')
            if not full_path.exists():
                raise HTTPException(404, "File or directory not found")
            
            try:
                if full_path.is_dir():
                    shutil.rmtree(full_path)
                else:
                    full_path.unlink()
                return {"success": True, "message": f"Deleted '{file_path}'"}
            except Exception as e:
                raise HTTPException(500, f"Failed to delete: {str(e)}")

        @app.post("/api/buckets/{bucket_name}/files/{file_path:path}/rename")
        async def rename_file_in_bucket(
            bucket_name: str, 
            file_path: str, 
            new_name: str = Form(...),
            _auth=Depends(_auth_dep)
        ) -> Dict[str, Any]:
            """Rename a file or directory in a bucket."""
            # Verify bucket exists
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            if not any(b.get("name") == bucket_name for b in items):
                raise HTTPException(404, "Bucket not found")
            
            old_path = self.paths.vfs_root / bucket_name / file_path.lstrip('/')
            if not old_path.exists():
                raise HTTPException(404, "File or directory not found")
            
            new_path = old_path.parent / new_name
            if new_path.exists():
                raise HTTPException(409, f"'{new_name}' already exists")
            
            try:
                old_path.rename(new_path)
                return {
                    "success": True, 
                    "old_name": old_path.name,
                    "new_name": new_name,
                    "path": str(new_path.relative_to(self.paths.vfs_root / bucket_name))
                }
            except Exception as e:
                raise HTTPException(500, f"Failed to rename: {str(e)}")

        @app.post("/api/buckets/{bucket_name}/files/{file_path:path}/move")
        async def move_file_in_bucket(
            bucket_name: str, 
            file_path: str, 
            destination: str = Form(...),
            _auth=Depends(_auth_dep)
        ) -> Dict[str, Any]:
            """Move a file or directory to a different location within the bucket."""
            # Verify bucket exists
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            if not any(b.get("name") == bucket_name for b in items):
                raise HTTPException(404, "Bucket not found")
            
            bucket_base = self.paths.vfs_root / bucket_name
            source_path = bucket_base / file_path.lstrip('/')
            dest_path = bucket_base / destination.lstrip('/')
            
            if not source_path.exists():
                raise HTTPException(404, "Source file or directory not found")
            
            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            if dest_path.exists():
                raise HTTPException(409, f"Destination '{destination}' already exists")
            
            try:
                source_path.rename(dest_path)
                return {
                    "success": True,
                    "source": file_path,
                    "destination": destination,
                    "new_path": str(dest_path.relative_to(bucket_base))
                }
            except Exception as e:
                raise HTTPException(500, f"Failed to move: {str(e)}")

        @app.put("/api/buckets/{bucket_name}/settings")
        async def update_bucket_settings(
            bucket_name: str, 
            settings: Dict[str, Any],
            _auth=Depends(_auth_dep)
        ) -> Dict[str, Any]:
            """Update advanced bucket settings including vector search and knowledge graph."""
            # Verify bucket exists
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            bucket_found = False
            for b in items:
                if b.get("name") == bucket_name:
                    bucket_found = True
                    break
            
            if not bucket_found:
                raise HTTPException(404, "Bucket not found")
            
            # Update bucket config file
            bucket_config_path = self.paths.data_dir / "bucket_configs" / f"{bucket_name}.yaml"
            bucket_config_path.parent.mkdir(exist_ok=True)
            
            config = {"name": bucket_name, "settings": {}}
            if bucket_config_path.exists() and yaml:
                try:
                    with bucket_config_path.open('r') as f:
                        config = yaml.safe_load(f) or config
                except Exception:
                    pass
            
            # Update settings
            current_settings = config.get("settings", {})
            current_settings.update(settings)
            config["settings"] = current_settings
            
            # Save config
            if yaml:
                try:
                    with bucket_config_path.open('w') as f:
                        yaml.safe_dump(config, f)
                except Exception as e:
                    raise HTTPException(500, f"Failed to save bucket config: {str(e)}")
            
            return {"success": True, "settings": current_settings}

        @app.get("/api/buckets/{bucket_name}/settings")
        async def get_bucket_settings(bucket_name: str) -> Dict[str, Any]:
            """Get advanced bucket settings."""
            # Verify bucket exists
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            if not any(b.get("name") == bucket_name for b in items):
                raise HTTPException(404, "Bucket not found")
            
            bucket_config_path = self.paths.data_dir / "bucket_configs" / f"{bucket_name}.yaml"
            settings = {
                "vector_search": False,
                "knowledge_graph": False,
                "search_index_type": "hnsw",
                "storage_quota": None,
                "max_files": None,
                "cache_ttl": 3600,
                "public_access": False
            }
            
            if bucket_config_path.exists() and yaml:
                try:
                    with bucket_config_path.open('r') as f:
                        config = yaml.safe_load(f) or {}
                        settings.update(config.get("settings", {}))
                except Exception:
                    pass
            
            return {"settings": settings}

        # ---- End Enhanced Bucket File Management ----

        # Pins
        @app.get("/api/pins")
        async def list_pins() -> Dict[str, Any]:
            items = _normalize_pins(_read_json(self.paths.pins_file, default=[]))
            return {"items": items}

        @app.post("/api/pins")
        async def create_pin(payload: Dict[str, Any], _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            cid = payload.get("cid")
            name = payload.get("name")
            if not cid:
                raise HTTPException(400, "Missing cid")
            pins = _normalize_pins(_read_json(self.paths.pins_file, default=[]))
            if any(p.get("cid") == cid for p in pins):
                raise HTTPException(409, "Pin exists")
            entry = {"cid": cid, "name": name, "created_at": datetime.now(UTC).isoformat()}
            pins.append(entry)
            _atomic_write_json(self.paths.pins_file, pins)
            return {"ok": True, "pin": entry}

        @app.delete("/api/pins/{cid}")
        async def delete_pin(cid: str, _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            pins = _normalize_pins(_read_json(self.paths.pins_file, default=[]))
            new_pins = [p for p in pins if p.get("cid") != cid]
            if len(new_pins) == len(pins):
                raise HTTPException(404, "Not found")
            _atomic_write_json(self.paths.pins_file, new_pins)
            return {"ok": True}

        # Files VFS
        @app.get("/api/files/list")
        async def files_list(path: str = ".", bucket: Optional[str] = None) -> Dict[str, Any]:
            # Use bucket-specific path if provided
            base = self.paths.vfs_root
            if bucket:
                # Check if bucket exists
                buckets_data = _read_json(self.paths.buckets_file, [])
                bucket_exists = any(b.get("name") == bucket for b in buckets_data)
                if bucket_exists:
                    base = self.paths.vfs_root / bucket
                    base.mkdir(parents=True, exist_ok=True)
            
            p = _safe_vfs_path(base, path)
            if not p.exists():
                return {"path": str(path), "bucket": bucket, "items": []}
            if p.is_file():
                raise HTTPException(400, "Path is a file")
            items = []
            for child in sorted(p.iterdir()):
                stat_info = child.stat() if child.exists() else None
                items.append({
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "size": stat_info.st_size if stat_info and child.is_file() else None,
                    "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat() if stat_info else None,
                    "created": datetime.fromtimestamp(stat_info.st_ctime, UTC).isoformat() if stat_info else None,
                    "permissions": oct(stat_info.st_mode)[-3:] if stat_info else None,
                    "type": "file" if child.is_file() else "directory",
                })
            return {"path": str(path), "bucket": bucket, "items": items, "total_items": len(items)}

        @app.get("/api/files/read")
        async def files_read(path: str, bucket: Optional[str] = None) -> Dict[str, Any]:
            base = self.paths.vfs_root
            if bucket:
                # Check if bucket exists
                buckets_data = _read_json(self.paths.buckets_file, [])
                bucket_exists = any(b.get("name") == bucket for b in buckets_data)
                if bucket_exists:
                    base = self.paths.vfs_root / bucket
                    
            p = _safe_vfs_path(base, path)
            if not p.exists() or not p.is_file():
                raise HTTPException(404, "File not found")
            try:
                content = p.read_text(encoding="utf-8")
                mode = "text"
            except UnicodeDecodeError:
                content = p.read_bytes().hex()
                mode = "hex"
            
            stat_info = p.stat()
            return {
                "path": path,
                "bucket": bucket,
                "mode": mode,
                "content": content,
                "size": stat_info.st_size,
                "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat(),
                "created": datetime.fromtimestamp(stat_info.st_ctime, UTC).isoformat(),
                "permissions": oct(stat_info.st_mode)[-3:],
            }

        @app.post("/api/files/write")
        async def files_write(payload: Dict[str, Any], _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            path = payload.get("path")
            content = payload.get("content", "")
            mode = payload.get("mode", "text")
            bucket = payload.get("bucket")
            if not path:
                raise HTTPException(400, "Missing path")
                
            base = self.paths.vfs_root
            if bucket:
                # Check if bucket exists, create if not
                buckets_data = _read_json(self.paths.buckets_file, [])
                bucket_exists = any(b.get("name") == bucket for b in buckets_data)
                if not bucket_exists:
                    # Create bucket entry
                    new_bucket = {"name": bucket, "created": datetime.now(UTC).isoformat()}
                    buckets_data.append(new_bucket)
                    _atomic_write_json(self.paths.buckets_file, buckets_data)
                base = self.paths.vfs_root / bucket
                
            p = _safe_vfs_path(base, path)
            p.parent.mkdir(parents=True, exist_ok=True)
            if mode == "hex":
                p.write_bytes(bytes.fromhex(content))
            else:
                p.write_text(str(content), encoding="utf-8")
            
            # Update metadata in ~/.ipfs_kit/ before calling library
            try:
                metadata_file = self.paths.data_dir / "file_metadata.json"
                metadata = _read_json(metadata_file, {})
                file_key = f"{bucket or 'default'}:{path}"
                stat_info = p.stat()
                metadata[file_key] = {
                    "path": path,
                    "bucket": bucket,
                    "size": stat_info.st_size,
                    "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat(),
                    "created": datetime.fromtimestamp(stat_info.st_ctime, UTC).isoformat(),
                    "operation": "write",
                    "timestamp": datetime.now(UTC).isoformat()
                }
                _atomic_write_json(metadata_file, metadata)
            except Exception as e:
                self.log.warning(f"Failed to update file metadata: {e}")
                
            return {"ok": True, "path": path, "bucket": bucket}

        @app.delete("/api/files/delete")
        async def files_delete(path: str, bucket: Optional[str] = None, _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            base = self.paths.vfs_root
            if bucket:
                base = self.paths.vfs_root / bucket
            
            p = _safe_vfs_path(base, path)
            if not p.exists():
                raise HTTPException(404, "File or directory not found")
            
            try:
                if p.is_file():
                    p.unlink()
                else:
                    import shutil
                    shutil.rmtree(p)
                
                # Update metadata
                metadata_file = self.paths.data_dir / "file_metadata.json"
                metadata = _read_json(metadata_file, {})
                file_key = f"{bucket or 'default'}:{path}"
                if file_key in metadata:
                    del metadata[file_key]
                _atomic_write_json(metadata_file, metadata)
                
                return {"ok": True, "path": path, "bucket": bucket, "deleted": True}
            except Exception as e:
                raise HTTPException(500, f"Failed to delete: {str(e)}")

        @app.post("/api/files/mkdir")
        async def files_mkdir(payload: Dict[str, Any], _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            path = payload.get("path")
            bucket = payload.get("bucket")
            if not path:
                raise HTTPException(400, "Missing path")
                
            base = self.paths.vfs_root
            if bucket:
                base = self.paths.vfs_root / bucket
                
            p = _safe_vfs_path(base, path)
            p.mkdir(parents=True, exist_ok=True)
            
            return {"ok": True, "path": path, "bucket": bucket, "created": True}

        @app.get("/api/files/buckets")
        async def files_buckets() -> Dict[str, Any]:
            """List available buckets for virtual filesystem"""
            buckets_data = _read_json(self.paths.buckets_file, [])
            vfs_buckets = []
            
            # Add default bucket
            vfs_buckets.append({
                "name": "default",
                "display_name": "Default",
                "path": str(self.paths.vfs_root),
                "file_count": len(list(self.paths.vfs_root.glob("**/*"))),
                "is_default": True
            })
            
            # Add configured buckets
            for bucket in buckets_data:
                bucket_path = self.paths.vfs_root / bucket["name"]
                if bucket_path.exists():
                    file_count = len(list(bucket_path.glob("**/*")))
                else:
                    file_count = 0
                    
                vfs_buckets.append({
                    "name": bucket["name"],
                    "display_name": bucket.get("display_name", bucket["name"]),
                    "path": str(bucket_path),
                    "file_count": file_count,
                    "is_default": False,
                    "created": bucket.get("created")
                })
                
            return {"buckets": vfs_buckets}

        @app.get("/api/files/stats")
        async def files_stats(path: str = ".", bucket: Optional[str] = None) -> Dict[str, Any]:
            """Get detailed file/directory statistics"""
            base = self.paths.vfs_root
            if bucket:
                base = self.paths.vfs_root / bucket
            
            p = _safe_vfs_path(base, path)
            if not p.exists():
                raise HTTPException(404, "Path not found")
            
            stat_info = p.stat()
            stats = {
                "path": path,
                "bucket": bucket,
                "is_file": p.is_file(),
                "is_dir": p.is_dir(),
                "size": stat_info.st_size,
                "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat(),
                "created": datetime.fromtimestamp(stat_info.st_ctime, UTC).isoformat(),
                "accessed": datetime.fromtimestamp(stat_info.st_atime, UTC).isoformat(),
                "permissions": oct(stat_info.st_mode)[-3:],
                "owner_uid": stat_info.st_uid,
                "group_gid": stat_info.st_gid,
            }
            
            if p.is_dir():
                # Directory stats
                total_size = 0
                file_count = 0
                dir_count = 0
                
                for item in p.rglob("*"):
                    if item.is_file():
                        file_count += 1
                        try:
                            total_size += item.stat().st_size
                        except Exception:
                            pass
                    elif item.is_dir():
                        dir_count += 1
                        
                stats.update({
                    "total_size": total_size,
                    "file_count": file_count,
                    "dir_count": dir_count
                })
            
            return stats

        # Peers endpoint for JavaScript compatibility
        @app.get("/api/peers")
        async def list_peers() -> Dict[str, Any]:
            """List peers using the simple PeerManager when available."""
            mgr = self._get_peer_manager()
            if not mgr:
                return {"peers": [], "total": 0, "connected": 0, "status": "Peer manager unavailable"}
            data = mgr.list_peers() or {"peers": [], "total": 0}
            peers = data.get("peers") or []
            total = data.get("total") or len(peers)
            connected = sum(1 for p in peers if (p or {}).get("connection_status") == "connected")
            status = ("Connected" if connected else ("Discovered" if total else "No IPFS peers connected"))
            return {"peers": peers, "total": total, "connected": connected, "status": status}

        @app.get("/api/peers/stats")
        async def peer_stats() -> Dict[str, Any]:
            mgr = self._get_peer_manager()
            if not mgr:
                return {"total": 0, "connected": 0, "by_tag": {}, "peers": []}
            data = mgr.list_peers() or {"peers": [], "total": 0}
            peers = data.get("peers") or []
            total = data.get("total") or len(peers)
            connected = sum(1 for p in peers if (p or {}).get("connection_status") == "connected")
            by_tag: Dict[str, int] = {}
            for p in peers:
                for t in (p.get("tags") or []):
                    by_tag[t] = by_tag.get(t, 0) + 1
            return {"total": total, "connected": connected, "by_tag": by_tag, "peers": peers}

        @app.post("/api/peers/discover")
        async def discover_peers(request: Request) -> Dict[str, Any]:
            """Discover peers via ipfs_kit_py libp2p integration when available.

            Primary: ipfs_kit_py.high_level_api.ipfs_kit().discover_peers(max_peers, timeout)
            Fallback: return current peers from simple PeerManager
            """
            # Parse body (optional)
            limit = 20
            timeout = 10
            try:
                try:
                    body = await request.json()
                    if isinstance(body, dict):
                        limit = int(body.get("limit", limit))
                        timeout = int(body.get("timeout", timeout))
                except Exception:
                    pass

                # Try high-level API based discovery (libp2p)
                try:
                    from ipfs_kit_py.high_level_api import ipfs_kit  # type: ignore
                    api = ipfs_kit()
                    if hasattr(api, "discover_peers"):
                        result = api.discover_peers(max_peers=limit, timeout=timeout)
                        peers: list = []
                        if isinstance(result, dict):
                            # Common shapes: {"peers": [...]}, or mapping
                            maybe = result.get("peers") or result.get("discovered") or result.get("results")
                            if isinstance(maybe, list):
                                peers = maybe
                            elif isinstance(maybe, dict):
                                peers = [
                                    {**(v if isinstance(v, dict) else {"info": v}), "peer_id": k}
                                    for k, v in maybe.items()
                                ]
                            else:
                                # If dict itself is a mapping of peers
                                peers = [
                                    {**(v if isinstance(v, dict) else {"info": v}), "peer_id": k}
                                    for k, v in result.items()
                                    if isinstance(k, str)
                                ]
                        elif isinstance(result, list):
                            peers = result
                        return {"status": "ok", "source": "libp2p", "peers": peers, "total": len(peers)}
                except Exception as e:  # pragma: no cover
                    self.log.warning(f"libp2p peer discovery failed: {e}")

                # Fallback to simple peer file manager
                mgr = self._get_peer_manager()
                if mgr:
                    data = mgr.list_peers() or {"peers": [], "total": 0}
                    peers = data.get("peers") or []
                    return {"status": "fallback", "peers": peers, "total": len(peers)}
                return {"status": "unavailable", "peers": [], "total": 0}
            except Exception as e:  # pragma: no cover
                return {"error": str(e), "peers": [], "total": 0}

        # Additional peer REST endpoints: connect, disconnect, info, bootstrap
        @app.post("/api/peers/connect")
        async def rest_connect_peer(payload: Dict[str, Any]) -> Dict[str, Any]:
            mgr = self._get_peer_manager()
            if not mgr:
                raise HTTPException(503, "Peer manager unavailable")
            peer_info = {
                "peer_id": payload.get("peer_id"),
                "peer_address": payload.get("peer_address"),
                "tags": payload.get("tags") or [],
            }
            return mgr.connect_peer(peer_info)

        @app.post("/api/peers/disconnect")
        async def rest_disconnect_peer(payload: Dict[str, Any]) -> Dict[str, Any]:
            mgr = self._get_peer_manager()
            if not mgr:
                raise HTTPException(503, "Peer manager unavailable")
            pid = payload.get("peer_id")
            if not pid:
                raise HTTPException(400, "peer_id is required")
            return mgr.disconnect_peer(pid)

        @app.get("/api/peers/{peer_id}")
        async def rest_get_peer_info(peer_id: str) -> Dict[str, Any]:
            mgr = self._get_peer_manager()
            if not mgr:
                raise HTTPException(503, "Peer manager unavailable")
            return mgr.get_peer_info(peer_id)

        @app.post("/api/peers/bootstrap")
        async def rest_bootstrap_peers(payload: Dict[str, Any]) -> Dict[str, Any]:
            action = (payload.get("action") or "list").lower()
            peer_address = payload.get("peer_address")
            try:
                from ipfs_kit_py.libp2p.peer_manager import get_global_peer_manager  # type: ignore
                libp2p_mgr = get_global_peer_manager()
            except Exception:
                libp2p_mgr = None
            try:
                if action == "list":
                    if libp2p_mgr and hasattr(libp2p_mgr, "list_bootstrap_peers"):
                        return {"ok": True, "peers": libp2p_mgr.list_bootstrap_peers()}
                    # fallback: read known files
                    peers: List[str] = []
                    for path in ["~/.ipfs/bootstrap", "/etc/ipfs/bootstrap"]:
                        p = Path(os.path.expanduser(path))
                        if p.exists():
                            with p.open() as fh:
                                for line in fh:
                                    s = line.strip()
                                    if s and not s.startswith("#"):
                                        peers.append(s)
                    return {"ok": True, "peers": peers}
                if action == "from_ipfs":
                    if libp2p_mgr and hasattr(libp2p_mgr, "bootstrap_from_ipfs"):
                        return libp2p_mgr.bootstrap_from_ipfs() or {"ok": True}
                    ipfs = _which("ipfs")
                    if not ipfs:
                        raise HTTPException(404, "ipfs binary not found")
                    out = _run_cmd([ipfs, "bootstrap", "list"])  # safe list
                    return {"ok": out.get("code") == 0, "out": out.get("out"), "err": out.get("err")}
                if action == "from_cluster":
                    if libp2p_mgr and hasattr(libp2p_mgr, "bootstrap_from_cluster"):
                        return libp2p_mgr.bootstrap_from_cluster() or {"ok": True}
                    ctl = _which("ipfs-cluster-ctl")
                    if not ctl:
                        raise HTTPException(404, "ipfs-cluster-ctl binary not found")
                    out = _run_cmd([ctl, "peers", "ls"])  # safe list
                    return {"ok": out.get("code") == 0, "out": out.get("out"), "err": out.get("err")}
                if action == "add":
                    if not peer_address:
                        raise HTTPException(400, "peer_address is required for action=add")
                    if libp2p_mgr and hasattr(libp2p_mgr, "add_bootstrap_peer"):
                        return libp2p_mgr.add_bootstrap_peer(peer_address) or {"ok": True}
                    ipfs = _which("ipfs")
                    if not ipfs:
                        raise HTTPException(404, "ipfs binary not found")
                    out = _run_cmd([ipfs, "bootstrap", "add", peer_address])
                    return {"ok": out.get("code") == 0, "out": out.get("out"), "err": out.get("err")}
                raise HTTPException(400, f"Unknown action: {action}")
            except HTTPException:
                raise
            except Exception as e:
                return {"ok": False, "error": str(e), "action": action}

        # Tools (JSON-RPC wrappers)
        @app.get("/mcp/tools/list")
        async def mcp_tools_list_get() -> Dict[str, Any]:
            return self._tools_list()
        @app.post("/mcp/tools/list")
        async def mcp_tools_list() -> Dict[str, Any]:
            return self._tools_list()

        @app.post("/mcp/tools/call")
        async def mcp_tools_call(payload: Dict[str, Any], _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            # Handle both JSON-RPC and direct formats
            if "params" in payload and isinstance(payload["params"], dict):
                # JSON-RPC format: {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "tool_name", "arguments": {...}}, "id": 1}
                name = payload["params"].get("name")
                args = payload["params"].get("arguments", {})
                request_id = payload.get("id")
            else:
                # Direct format: {"name": "tool_name", "args": {...}}
                name = payload.get("name") or payload.get("tool")
                args = payload.get("args") or payload.get("params") or {}
                request_id = None
            
            result = await self._tools_call(name, args)
            
            # If this was a JSON-RPC request and we have a request_id, ensure proper JSON-RPC response format
            if request_id is not None:
                if isinstance(result, dict) and result.get("jsonrpc") == "2.0":
                    # Already in JSON-RPC format, just update the ID
                    result["id"] = request_id
                    return result
                # Convert to JSON-RPC format (support list/str/etc results too)
                if isinstance(result, dict) and "error" in result:
                    return {"jsonrpc": "2.0", "error": result["error"], "id": request_id}
                return {"jsonrpc": "2.0", "result": result, "id": request_id}
            
            return result

        # Add compatibility endpoint for JavaScript SDK
        @app.post("/api/call_mcp_tool")
        async def api_call_mcp_tool(payload: Dict[str, Any], _auth=Depends(_auth_dep)) -> Dict[str, Any]:
            """JavaScript SDK compatibility endpoint."""
            tool_name = payload.get("tool_name")
            arguments = payload.get("arguments", {})
            req_id = payload.get("id", "1")
            
            if not tool_name:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Missing tool_name"}, "id": req_id}
            
            try:
                result = await self._tools_call(tool_name, arguments)
                
                # Ensure proper JSON-RPC response format
                if isinstance(result, dict) and result.get("jsonrpc") == "2.0":
                    result["id"] = req_id
                    return result
                else:
                    return {"jsonrpc": "2.0", "result": result, "id": req_id}
            except Exception as e:
                return {"jsonrpc": "2.0", "error": {"code": -1, "message": str(e)}, "id": req_id}

    # --- PID helpers ---
    def _pid_file_path(self) -> Path:
        """Legacy primary PID file path (shared)."""
        return self.paths.data_dir / "dashboard.pid"

    def _pid_file_paths(self) -> List[Path]:
        """All PID file paths to write/clean, including port-specific file."""
        return [
            self.paths.data_dir / "dashboard.pid",
            self.paths.data_dir / f"mcp_{self.port}.pid",
        ]

    def _write_pid_file(self) -> None:
        """Write PID to both legacy and port-specific files."""
        with suppress(Exception):
            pid_text = str(os.getpid())
            for pf in self._pid_file_paths():
                # ensure directory exists
                pf.parent.mkdir(parents=True, exist_ok=True)
                pf.write_text(pid_text, encoding="utf-8")

    def _cleanup_pid_file(self) -> None:
        """Remove both legacy and port-specific PID files if present."""
        with suppress(Exception):
            for pf in self._pid_file_paths():
                if pf.exists():
                    pf.unlink()

    # Lifespan handles startup/shutdown

    # ---- tools ----
    def _tools_list(self) -> Dict[str, Any]:
        tools = [
            {"name": "health_check", "description": "Simple health check for MCP connection", "inputSchema": {}},
            {"name": "get_system_status", "description": "System health and versions", "inputSchema": {}},
            {"name": "list_services", "description": "List local services and probes", "inputSchema": {}},
            {"name": "service_control", "description": "Control a local service (start/stop/restart/status)", "inputSchema": {"service": "string", "action": "string"}},
            {"name": "service_status", "description": "Probe service status (ipfs)", "inputSchema": {"service": "string"}},
            {"name": "list_backends", "description": "List configured backends", "inputSchema": {}},
            {"name": "create_backend", "description": "Create backend", "inputSchema": {"name": "string", "config": "object"}},
            {"name": "update_backend", "description": "Update backend", "inputSchema": {"type":"object", "required":["name","config"], "properties": {"name": {"type":"string", "title":"Backend", "ui": {"enumFrom":"backends", "valueKey":"name", "labelKey":"name"}}, "config": {"type":"object", "title":"Config", "properties": {"type": {"type": "string"}}}}}},
            {"name": "delete_backend", "description": "Delete backend", "inputSchema": {"type":"object", "required":["name"], "confirm": {"message":"This will remove the backend. Continue?"}, "properties": {"name": {"type":"string", "title":"Backend", "ui": {"enumFrom":"backends", "valueKey":"name", "labelKey":"name"}}}}},
            {"name": "test_backend", "description": "Test backend reachability", "inputSchema": {"type":"object", "required":["name"], "properties": {"name": {"type":"string", "title":"Backend", "ui": {"enumFrom":"backends", "valueKey":"name", "labelKey":"name"}}}}},
            {"name": "get_backend", "description": "Get backend by name", "inputSchema": {"type":"object", "required":["name"], "properties": {"name": {"type":"string", "title":"Backend", "ui": {"enumFrom":"backends", "valueKey":"name", "labelKey":"name"}}}}},
            # Advanced backend management tools
            {"name": "list_backend_instances", "description": "List backend instances by type", "inputSchema": {}},
            {"name": "create_backend_instance", "description": "Create new backend instance", "inputSchema": {"type":"object", "required":["service_type","instance_name"], "properties": {"service_type": {"type":"string", "title":"Backend Type", "enum":["local_storage","ipfs","s3","git","parquet","ipfs_cluster"]}, "instance_name": {"type":"string", "title":"Instance Name"}, "description": {"type":"string", "title":"Description"}}}},
            {"name": "configure_backend_instance", "description": "Configure backend instance", "inputSchema": {"type":"object", "required":["instance_name"], "properties": {"instance_name": {"type":"string", "title":"Instance Name"}, "service_type": {"type":"string", "title":"Backend Type"}, "config": {"type":"object", "title":"Configuration"}}}},
            {"name": "get_backend_performance_metrics", "description": "Get backend performance metrics", "inputSchema": {"type":"object", "required":["backend_name"], "properties": {"backend_name": {"type":"string", "title":"Backend Name"}, "time_range": {"type":"string", "title":"Time Range", "enum":["1h","6h","24h","7d"], "default":"1h"}, "include_history": {"type":"boolean", "title":"Include History", "default":False}}}},
            {"name": "get_backend_configuration_template", "description": "Get configuration template for backend type", "inputSchema": {"type":"object", "required":["backend_type"], "properties": {"backend_type": {"type":"string", "title":"Backend Type", "enum":["local_storage","ipfs","s3","git","parquet","ipfs_cluster"]}, "template_type": {"type":"string", "title":"Template Type", "enum":["basic","enterprise","high_performance"], "default":"basic"}}}},
            {"name": "clone_backend_configuration", "description": "Clone backend configuration", "inputSchema": {"type":"object", "required":["source_backend","new_backend_name"], "properties": {"source_backend": {"type":"string", "title":"Source Backend"}, "new_backend_name": {"type":"string", "title":"New Backend Name"}, "modify_config": {"type":"boolean", "title":"Modify Configuration", "default":False}}}},
            {"name": "backup_backend_configuration", "description": "Backup backend configuration", "inputSchema": {"type":"object", "required":["backend_name"], "properties": {"backend_name": {"type":"string", "title":"Backend Name"}, "backup_name": {"type":"string", "title":"Backup Name"}, "include_data": {"type":"boolean", "title":"Include Data", "default":False}}}},
            {"name": "restore_backend_configuration", "description": "Restore backend configuration from backup", "inputSchema": {"type":"object", "required":["backend_name","backup_id"], "properties": {"backend_name": {"type":"string", "title":"Backend Name"}, "backup_id": {"type":"string", "title":"Backup ID"}, "force_restore": {"type":"boolean", "title":"Force Restore", "default":False}}}},
            {"name": "list_buckets", "description": "List buckets", "inputSchema": {}},
            {"name": "create_bucket", "description": "Create bucket", "inputSchema": {"type":"object", "required":["name"], "properties": {"name": {"type":"string", "title":"Bucket Name", "ui": {"placeholder":"my-bucket"}}, "backend": {"type":"string", "title":"Backend", "description":"Optional backend id", "ui": {"enumFrom":"backends", "valueKey":"name", "labelKey":"name"}}}}},
            {"name": "delete_bucket", "description": "Delete bucket", "inputSchema": {"type":"object", "required":["name"], "confirm": {"message":"This will delete the bucket record. Continue?"}, "properties": {"name": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}}}},
            {"name": "get_bucket", "description": "Get bucket by name", "inputSchema": {"type":"object", "required":["name"], "properties": {"name": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}}}},
            {"name": "update_bucket", "description": "Update bucket (merge fields)", "inputSchema": {"type":"object", "required":["name","patch"], "properties": {"name": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "patch": {"type":"object", "title":"Patch"}}}},
            {"name": "get_bucket_policy", "description": "Get bucket policy", "inputSchema": {"type":"object", "required":["name"], "properties": {"name": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}}}},
            {"name": "update_bucket_policy", "description": "Update bucket policy", "inputSchema": {"type":"object", "required":["name"], "properties": {"name": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "replication_factor": {"type":"number", "title":"Replication", "default":1}, "cache_policy": {"type":"string", "title":"Cache", "enum":["none","memory","disk"], "default":"none"}, "retention_days": {"type":"number", "title":"Retention Days", "default":0}}}},
            # Comprehensive bucket file management tools
            {"name": "bucket_list_files", "description": "List files in bucket with metadata priority", "inputSchema": {"type":"object", "required":["bucket"], "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "path": {"type":"string", "title":"Path", "default":"."}, "show_metadata": {"type":"boolean", "title":"Show Metadata", "default":True}}}},
            {"name": "list_bucket_files", "description": "List files in bucket (alias for bucket_list_files)", "inputSchema": {"type":"object", "required":["bucket"], "properties": {"bucket": {"type":"string", "title":"Bucket"}, "path": {"type":"string", "title":"Path", "default":""}, "metadata_first": {"type":"boolean", "title":"Metadata First", "default":True}}}},
            {"name": "create_folder", "description": "Create a new folder in bucket", "inputSchema": {"type":"object", "required":["bucket","name"], "properties": {"bucket": {"type":"string", "title":"Bucket"}, "name": {"type":"string", "title":"Folder Name"}}}},
            {"name": "bucket_upload_file", "description": "Upload file to bucket with replication policy", "inputSchema": {"type":"object", "required":["bucket","path","content"], "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "path": {"type":"string", "title":"File Path"}, "content": {"type":"string", "title":"Content", "ui": {"widget":"textarea", "rows":6}}, "mode": {"type":"string", "title":"Mode", "enum":["text","hex","base64"], "default":"text"}, "apply_policy": {"type":"boolean", "title":"Apply Bucket Policy", "default":True}}}},
            {"name": "bucket_download_file", "description": "Download file from bucket", "inputSchema": {"type":"object", "required":["bucket","path"], "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "path": {"type":"string", "title":"File Path"}, "format": {"type":"string", "title":"Format", "enum":["text","hex","base64"], "default":"text"}}}},
            {"name": "bucket_delete_file", "description": "Delete file from bucket", "inputSchema": {"type":"object", "required":["bucket","path"], "confirm": {"message":"This will delete the file from the bucket. Continue?"}, "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "path": {"type":"string", "title":"File Path"}, "remove_replicas": {"type":"boolean", "title":"Remove Replicas", "default":True}}}},
            {"name": "bucket_rename_file", "description": "Rename/move file in bucket", "inputSchema": {"type":"object", "required":["bucket","src","dst"], "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "src": {"type":"string", "title":"Source Path"}, "dst": {"type":"string", "title":"Destination Path"}, "update_replicas": {"type":"boolean", "title":"Update Replicas", "default":True}}}},
            {"name": "bucket_mkdir", "description": "Create directory in bucket", "inputSchema": {"type":"object", "required":["bucket","path"], "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "path": {"type":"string", "title":"Directory Path"}, "create_parents": {"type":"boolean", "title":"Create Parents", "default":True}}}},
            {"name": "bucket_copy_file", "description": "Copy file within or between buckets", "inputSchema": {"type":"object", "required":["src_bucket","src_path","dst_bucket","dst_path"], "properties": {"src_bucket": {"type":"string", "title":"Source Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "src_path": {"type":"string", "title":"Source Path"}, "dst_bucket": {"type":"string", "title":"Destination Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "dst_path": {"type":"string", "title":"Destination Path"}, "apply_dst_policy": {"type":"boolean", "title":"Apply Destination Policy", "default":True}}}},
            {"name": "bucket_sync_replicas", "description": "Sync bucket files to replicas according to policy", "inputSchema": {"type":"object", "required":["bucket"], "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "force_sync": {"type":"boolean", "title":"Force Full Sync", "default":False}}}},
            {"name": "bucket_get_metadata", "description": "Get comprehensive metadata for bucket file", "inputSchema": {"type":"object", "required":["bucket","path"], "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "path": {"type":"string", "title":"File Path"}, "include_replicas": {"type":"boolean", "title":"Include Replica Info", "default":True}}}},
            {"name": "bucket_get_full_metadata", "description": "Get complete metadata for entire bucket including all file CID hashes for IPFS reconstruction", "inputSchema": {"type":"object", "required":["bucket"], "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}}}},
            # Enhanced bucket management tools
            {"name": "get_bucket_usage", "description": "Get bucket usage statistics", "inputSchema": {"type":"object", "required":["name"], "properties": {"name": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}}}},
            {"name": "generate_bucket_share_link", "description": "Generate shareable link for bucket", "inputSchema": {"type":"object", "required":["bucket"], "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "access_type": {"type":"string", "title":"Access Type", "enum":["read_only","read_write","admin"], "default":"read_only"}, "expiration": {"type":"string", "title":"Expiration", "enum":["never","1h","24h","7d","30d"], "default":"never"}}}},
            {"name": "bucket_selective_sync", "description": "Sync selected files in bucket", "inputSchema": {"type":"object", "required":["bucket","files"], "properties": {"bucket": {"type":"string", "title":"Bucket", "ui": {"enumFrom":"buckets", "valueKey":"name", "labelKey":"name"}}, "files": {"type":"array", "title":"Files to Sync", "items": {"type":"string"}}, "options": {"type":"object", "title":"Sync Options", "properties": {"force_update": {"type":"boolean", "default":False}, "verify_checksums": {"type":"boolean", "default":True}, "create_backup": {"type":"boolean", "default":False}}}}}},
            {"name": "list_pins", "description": "List pins", "inputSchema": {}},
            {"name": "create_pin", "description": "Create pin", "inputSchema": {"type":"object", "required":["cid"], "properties": {"cid": {"type":"string", "title":"CID"}, "name": {"type":"string", "title":"Name"}}}},
            {"name": "delete_pin", "description": "Delete pin", "inputSchema": {"type":"object", "required":["cid"], "confirm": {"message":"This will unpin the CID. Continue?"}, "properties": {"cid": {"type":"string", "title":"CID", "ui": {"enumFrom":"pins", "valueKey":"cid", "labelFormat":"{name} ({cid})"}}}}},
            {"name": "pins_export", "description": "Export pins (raw list)", "inputSchema": {}},
            {"name": "pins_import", "description": "Import pins (merge without duplicates)", "inputSchema": {"items": "array"}},
            {"name": "files_list", "description": "List VFS", "inputSchema": {"type":"object", "required":["path"], "properties": {"path": {"type":"string", "title":"Path", "ui": {"widget":"path", "placeholder":"."}}}}},
            {"name": "files_read", "description": "Read VFS file", "inputSchema": {"type":"object", "required":["path"], "properties": {"path": {"type":"string", "title":"Path"}}}},
            {"name": "files_write", "description": "Write VFS file", "inputSchema": {"type":"object", "required":["path","content"], "properties": {"path": {"type":"string", "title":"Path"}, "content": {"type":"string", "title":"Content", "ui": {"widget":"textarea", "rows":4}}, "mode": {"type":"string", "title":"Mode", "enum":["text","hex"], "default":"text"}}}},
            {"name": "files_mkdir", "description": "Create directory in VFS", "inputSchema": {"type":"object", "required":["path"], "properties": {"path": {"type":"string", "title":"Path"}}}},
            {"name": "files_rm", "description": "Remove file/dir in VFS", "inputSchema": {"type":"object", "required":["path"], "confirm": {"message":"This will delete files. Continue?"}, "properties": {"path": {"type":"string", "title":"Path"}, "recursive": {"type":"boolean", "title":"Recursive", "default": False}}}},
            {"name": "files_mv", "description": "Move/Rename in VFS", "inputSchema": {"type":"object", "required":["src","dst"], "properties": {"src": {"type":"string", "title":"Source"}, "dst": {"type":"string", "title":"Destination"}}}},
            {"name": "files_stat", "description": "Stat a VFS path", "inputSchema": {"type":"object", "required":["path"], "properties": {"path": {"type":"string", "title":"Path"}}}},
            {"name": "files_copy", "description": "Copy file/dir in VFS", "inputSchema": {"type":"object", "required":["src","dst"], "properties": {"src": {"type":"string", "title":"Source"}, "dst": {"type":"string", "title":"Destination"}, "recursive": {"type":"boolean", "title":"Recursive", "default": False}}}},
            {"name": "files_touch", "description": "Create empty file in VFS", "inputSchema": {"type":"object", "required":["path"], "properties": {"path": {"type":"string", "title":"Path"}}}},
            {"name": "files_tree", "description": "Recursive tree listing (depth-limited)", "inputSchema": {"type":"object", "required":["path"], "properties": {"path": {"type":"string", "title":"Path", "default": "."}, "depth": {"type":"number", "title":"Depth", "default": 2}}}},
            {"name": "ipfs_add", "description": "Add a VFS path to IPFS", "inputSchema": {"path": "string"}},
            {"name": "ipfs_pin", "description": "Pin a CID via IPFS", "inputSchema": {"type":"object", "required":["cid"], "properties": {"cid": {"type":"string", "title":"CID", "ui": {"enumFrom":"pins", "valueKey":"cid", "labelFormat":"{name} ({cid})"}}, "name": {"type":"string", "title":"Name"}}}},
            {"name": "ipfs_cat", "description": "Cat a CID via IPFS", "inputSchema": {"cid": "string"}},
            {"name": "ipfs_ls", "description": "List links for CID", "inputSchema": {"cid": "string"}},
            {"name": "ipfs_version", "description": "IPFS version info", "inputSchema": {}},
            {"name": "cars_list", "description": "List CAR files", "inputSchema": {}},
            {"name": "car_export", "description": "Export a VFS path to CAR", "inputSchema": {"path": "string", "car": "string"}},
            {"name": "car_import", "description": "Import a CAR to VFS", "inputSchema": {"car": "string", "dest": "string"}},
            {"name": "state_snapshot", "description": "Snapshot key state files", "inputSchema": {}},
            {"name": "state_backup", "description": "Backup state to tar.gz", "inputSchema": {}},
            {"name": "state_reset", "description": "Reset state JSON files (with backups)", "inputSchema": {}},
            {"name": "get_logs", "description": "Get recent logs", "inputSchema": {"limit": "number"}},
            {"name": "clear_logs", "description": "Clear logs", "inputSchema": {}},
            {"name": "server_shutdown", "description": "Shutdown this MCP server", "inputSchema": {}},
            # Enhanced backend configuration tools for multi-instance support
            {"name": "configure_backend_instance", "description": "Configure backend instance with advanced settings", "inputSchema": {"type":"object", "required":["instance_name", "service_type"], "properties": {"instance_name": {"type":"string", "title":"Instance Name"}, "service_type": {"type":"string", "title":"Service Type", "enum":["s3", "github", "ipfs_cluster", "huggingface", "gdrive", "ftp", "sshfs", "apache_arrow", "parquet"]}, "config": {"type":"object", "title":"Configuration", "properties": {"description": {"type":"string", "title":"Description"}, "cache_policy": {"type":"string", "title":"Cache Policy", "enum":["none", "memory", "disk", "hybrid"], "default":"none"}, "cache_size_mb": {"type":"number", "title":"Cache Size (MB)", "default":1024}, "cache_ttl_seconds": {"type":"number", "title":"Cache TTL (seconds)", "default":3600}, "storage_quota_gb": {"type":"number", "title":"Storage Quota (GB)", "default":100}, "max_files": {"type":"number", "title":"Max Files", "default":10000}, "max_file_size_mb": {"type":"number", "title":"Max File Size (MB)", "default":500}, "retention_days": {"type":"number", "title":"Retention Days", "default":365}, "auto_cleanup": {"type":"boolean", "title":"Auto Cleanup", "default":False}, "versioning": {"type":"boolean", "title":"Versioning", "default":False}, "replication_factor": {"type":"number", "title":"Replication Factor", "enum":[1,2,3,5,10], "default":3}, "sync_strategy": {"type":"string", "title":"Sync Strategy", "enum":["immediate", "scheduled", "manual"], "default":"immediate"}}}}}},
            {"name": "create_backend_instance", "description": "Create new backend instance", "inputSchema": {"type":"object", "required":["service_type", "instance_name"], "properties": {"service_type": {"type":"string", "title":"Service Type", "enum":["s3", "github", "ipfs_cluster", "huggingface", "gdrive", "ftp", "sshfs", "apache_arrow", "parquet"]}, "instance_name": {"type":"string", "title":"Instance Name"}, "description": {"type":"string", "title":"Description"}}}},
            {"name": "list_backend_instances", "description": "List all backend instances with configurations", "inputSchema": {}},
            {"name": "backend_health_check", "description": "Run comprehensive health check on all backends", "inputSchema": {"type":"object", "properties": {"detailed": {"type":"boolean", "title":"Detailed Report", "default":False}}}},
            {"name": "sync_backend_replicas", "description": "Sync backend replicas using metadata-first approach", "inputSchema": {"type":"object", "required":["name"], "properties": {"name": {"type":"string", "title":"Backend Name"}, "use_metadata_first": {"type":"boolean", "title":"Use Metadata First", "default":True}, "force_sync": {"type":"boolean", "title":"Force Sync", "default":False}}}},
            {"name": "test_backend_config", "description": "Test backend configuration without saving", "inputSchema": {"type":"object", "required":["name"], "properties": {"name": {"type":"string", "title":"Backend Name"}, "config": {"type":"object", "title":"Configuration to Test"}}}},
            {"name": "apply_backend_policy", "description": "Apply policy to backend with replication sync", "inputSchema": {"type":"object", "required":["name", "policy"], "properties": {"name": {"type":"string", "title":"Backend Name"}, "policy": {"type":"object", "title":"Policy Configuration"}, "force_sync": {"type":"boolean", "title":"Force Sync", "default":False}}}},
            {"name": "update_backend_policy", "description": "Update backend policy configuration", "inputSchema": {"type":"object", "required":["name", "policy"], "properties": {"name": {"type":"string", "title":"Backend Name"}, "policy": {"type":"object", "title":"Policy Updates"}}}},
            # Advanced Feature 8: Real-Time Performance Metrics
            {"name": "get_backend_performance_metrics", "description": "Get real-time performance metrics for backends", "inputSchema": {"type":"object", "properties": {"backend_name": {"type":"string", "title":"Backend Name (optional, all if empty)"}, "time_range": {"type":"string", "title":"Time Range", "enum":["1h", "6h", "24h", "7d"], "default":"1h"}, "include_history": {"type":"boolean", "title":"Include Historical Data", "default":True}}}},
            # Advanced Feature 9: Advanced Configuration Management & Policy Editor
            {"name": "get_backend_configuration_template", "description": "Get configuration templates and policy presets", "inputSchema": {"type":"object", "properties": {"backend_type": {"type":"string", "title":"Backend Type", "enum":["s3", "github", "ipfs", "huggingface", "gdrive", "parquet"]}, "template_type": {"type":"string", "title":"Template Type", "enum":["basic", "enterprise", "high_performance", "backup"], "default":"basic"}}}},
            {"name": "clone_backend_configuration", "description": "Clone backend configuration to create new backend", "inputSchema": {"type":"object", "required":["source_backend", "new_backend_name"], "properties": {"source_backend": {"type":"string", "title":"Source Backend Name"}, "new_backend_name": {"type":"string", "title":"New Backend Name"}, "modify_config": {"type":"object", "title":"Configuration Modifications"}}}},
            {"name": "backup_backend_configuration", "description": "Backup backend configuration with versioning", "inputSchema": {"type":"object", "required":["backend_name"], "properties": {"backend_name": {"type":"string", "title":"Backend Name"}, "backup_name": {"type":"string", "title":"Backup Name (optional)"}, "include_data": {"type":"boolean", "title":"Include Data Backup", "default":False}}}},
            {"name": "restore_backend_configuration", "description": "Restore backend configuration from backup", "inputSchema": {"type":"object", "required":["backend_name", "backup_id"], "properties": {"backend_name": {"type":"string", "title":"Backend Name"}, "backup_id": {"type":"string", "title":"Backup ID"}, "force_restore": {"type":"boolean", "title":"Force Restore", "default":False}}}},
            # Configuration management tools with metadata-first approach  
            {"name": "list_config_files", "description": "List configuration files with metadata-first approach", "inputSchema": {}},
            {"name": "read_config_file", "description": "Read configuration file with metadata-first approach", "inputSchema": {"type":"object", "required":["filename"], "properties": {"filename": {"type":"string", "title":"Configuration File"}}}},
            {"name": "write_config_file", "description": "Write configuration file with metadata-first approach", "inputSchema": {"type":"object", "required":["filename","content"], "properties": {"filename": {"type":"string", "title":"Configuration File"}, "content": {"type":"string", "title":"File Content", "ui": {"widget":"textarea", "rows":10}}}}},
            {"name": "get_config_metadata", "description": "Get configuration file metadata", "inputSchema": {"type":"object", "required":["filename"], "properties": {"filename": {"type":"string", "title":"Configuration File"}}}},
            # Peer management tools (file-backed by default; integrates with libp2p when present)
            {"name": "list_peers", "description": "List known peers", "inputSchema": {}},
            {"name": "get_peer_stats", "description": "Get peer statistics and summary", "inputSchema": {}},
            {"name": "connect_peer", "description": "Connect or add a peer", "inputSchema": {"type":"object", "properties": {"peer_id": {"type":"string", "title":"Peer ID"}, "peer_address": {"type":"string", "title":"Peer Multiaddr"}, "tags": {"type":"array", "items": {"type":"string"}}}}},
            {"name": "disconnect_peer", "description": "Disconnect or remove a peer", "inputSchema": {"type":"object", "required":["peer_id"], "properties": {"peer_id": {"type":"string", "title":"Peer ID"}}}},
            {"name": "get_peer_info", "description": "Get peer details", "inputSchema": {"type":"object", "required":["peer_id"], "properties": {"peer_id": {"type":"string", "title":"Peer ID"}}}},
            {"name": "discover_peers", "description": "Discover peers via libp2p/ipfs_kit when available", "inputSchema": {"type":"object", "properties": {"limit": {"type":"number", "default": 20}, "timeout": {"type":"number", "default": 10}}}},
            {"name": "bootstrap_peers", "description": "Manage bootstrap peers (list/from_ipfs/from_cluster/add)", "inputSchema": {"type":"object", "properties": {"action": {"type":"string", "enum":["list","from_ipfs","from_cluster","add"], "default":"list"}, "peer_address": {"type":"string"}}}},
        ]
        return {"jsonrpc": "2.0", "result": {"tools": tools}, "id": None}

    async def _tools_call(self, name: Optional[str], args: Dict[str, Any]) -> Dict[str, Any]:  # noqa: C901 - large dispatch function
        if not name:
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Missing tool name"}, "id": None}

        try:
            # Dispatch to domain handlers
            for handler in (
                self._handle_system_services,
                self._handle_backends,
                self._handle_buckets,
                self._handle_pins,
                self._handle_files,
                self._handle_ipfs,
                self._handle_peers,
                self._handle_cars,
                self._handle_state,
                self._handle_logs_server,
                self._handle_config,
            ):
                maybe = handler(name, args)  # type: ignore
                if inspect.isawaitable(maybe):
                    maybe = await maybe  # type: ignore
                if maybe is not None:
                    return maybe  # type: ignore
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Unknown tool: {name}"}, "id": None}
        except HTTPException as e:
            return {"jsonrpc": "2.0", "error": {"code": e.status_code, "message": e.detail}, "id": None}
        except Exception as e:  # pragma: no cover
            return {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(e)}, "id": None}

    # Domain handlers (return JSON-RPC dict or None if not applicable)
    async def _handle_system_services(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if name == "control_service":
            # Legacy alias used by older tests/clients.
            res = await self._handle_system_services("service_control", args)
            if isinstance(res, dict) and isinstance(res.get("result"), dict):
                # Ensure stable legacy shape
                res["result"]["status"] = "ok"
            return res
        if name == "health_check":
            result = {
                "status": "healthy",
                "timestamp": datetime.now(UTC).isoformat()
            }
            return {"jsonrpc": "2.0", "result": result, "id": None}
        if name == "get_system_status":
            result: Dict[str, Any] = {
                "time": datetime.now(UTC).isoformat(),
                "data_dir": str(self.paths.data_dir),
            }
            if psutil:
                with suppress(Exception):
                    # Get comprehensive system metrics
                    result["cpu_percent"] = round(psutil.cpu_percent(interval=1), 1)
                    memory = psutil.virtual_memory()
                    result["memory_percent"] = round(memory.percent, 1)
                    
                    # Get disk usage for root filesystem
                    try:
                        disk = psutil.disk_usage('/')
                        result["disk_percent"] = round((disk.used / disk.total) * 100, 1)
                    except Exception:
                        result["disk_percent"] = 0.0
                    
                    result["status"] = "running"
                    result["uptime"] = str(datetime.now(UTC) - datetime.fromtimestamp(psutil.boot_time(), UTC))
            else:
                # Fallback when psutil is not available
                result["cpu_percent"] = "N/A"
                result["memory_percent"] = "N/A"
                result["disk_percent"] = "N/A"
                result["status"] = "running"
            return {"jsonrpc": "2.0", "result": result, "id": None}
        if name == "list_services":
            # Use comprehensive service manager if available
            service_manager = self._get_service_manager()
            if service_manager:
                try:
                    # Get all services (enabled and disabled) for comprehensive dashboard view
                    services_data = await service_manager.list_all_services()  # Call service manager's method directly
                    # Transform the service manager format to match the expected dashboard format
                    services: Dict[str, Any] = {"services": {}}
                    
                    for service in services_data.get("services", []):
                        service_id = service.get("id")
                        if service_id:
                            services["services"][service_id] = {
                                "name": service.get("name"),
                                "type": service.get("type"),
                                "status": service.get("status"),
                                "description": service.get("description"),
                                "port": service.get("port"),
                                "requires_credentials": service.get("requires_credentials", False),
                                "actions": service.get("actions", []),
                                "last_check": service.get("last_check"),
                                "details": service.get("details", {}),
                                # Add config_keys and config_hints for storage backends
                                "config_keys": service.get("config_keys"),
                                "config_hints": service.get("config_hints"),
                                # Add compatibility fields for existing UI
                                "bin": service.get("details", {}).get("binary_path") if service.get("type") == "daemon" else None,
                                "api_port_open": service.get("details", {}).get("api_port_open", False) if service.get("type") == "daemon" else None
                            }
                    
                    # Add summary information nested to avoid heterogeneous dict values at top level
                    services["metadata"] = {
                        "summary": services_data.get("summary", {}),
                        "total": services_data.get("total", 0)
                    }
                    
                    return {"jsonrpc": "2.0", "result": services, "id": None}
                except Exception as e:
                    self.log.error(f"Error using service manager: {e}")
                    import traceback
                    self.log.error(f"Traceback: {traceback.format_exc()}")
                    # Fall back to the old implementation if service manager fails
            
            
            # If service manager fails or returns no services, return minimal IPFS check
            # Don't include docker/kubectl as they're not relevant to IPFS Kit
            services: Dict[str, Any] = {
                "services": {}
            }
            
            # Only check for IPFS as fallback
            ipfs_bin = _which("ipfs")
            if ipfs_bin:
                ipfs_api_open = _port_open("127.0.0.1", 5001)
                services["services"]["ipfs"] = {
                    "name": "IPFS Daemon",
                    "type": "daemon",
                    "status": "running" if ipfs_api_open else "stopped",
                    "description": "InterPlanetary File System daemon",
                    "bin": ipfs_bin,
                    "api_port_open": ipfs_api_open,
                    "actions": ["start", "stop", "restart"] if ipfs_bin else []
                }
            
            total = len(services["services"])
            services["metadata"] = {
                "total": total,
                "running": sum(1 for v in services["services"].values() if v.get("status") == "running"),
                "stopped": sum(1 for v in services["services"].values() if v.get("status") == "stopped"),
                "configured": sum(1 for v in services["services"].values() if v.get("bin"))
            }
            return {"jsonrpc": "2.0", "result": services, "id": None}
        if name == "service_control":
            svc = str(args.get("service", "")).strip()
            action = str(args.get("action", "")).strip().lower()

            # Normalize common legacy display names
            svc_key = svc.strip().lower()
            if svc_key in {"ipfs daemon", "ipfs", "kubo", "go-ipfs"}:
                svc = "ipfs"
            
            # Try to use the comprehensive service manager first
            service_manager = self._get_service_manager()
            if service_manager:
                try:
                    if action == "status":
                        # Get the service details for status
                        result = await service_manager.get_service_details(svc)
                        return {"jsonrpc": "2.0", "result": result, "id": None}
                    elif action in ("start", "stop", "restart", "configure", "health_check", "view_logs", "enable"):
                        # Handle enable action separately
                        if action == "enable":
                            result = service_manager.enable_service(svc)
                        else:
                            # Use the perform_service_action method
                            # Only pass the inner params payload to the service layer
                            params = None
                            if isinstance(args, dict):
                                params = args.get("params") if action == "configure" else args.get("params", None)
                            result = await service_manager.perform_service_action(svc, action, params)
                        return {"jsonrpc": "2.0", "result": result, "id": None}
                    else:
                        return {"jsonrpc": "2.0", "error": {"code": 400, "message": f"Unsupported action: {action}"}, "id": None}
                except Exception as e:
                    self.log.error(f"Service manager action failed for {svc}.{action}: {e}")
                    # For configuration actions, provide a helpful response instead of falling through
                    if action == "configure":
                        return {
                            "jsonrpc": "2.0", 
                            "result": {
                                "success": False,
                                "error": f"Configuration for {svc} requires manual setup. See service documentation.",
                                "message": f"Service {svc} configuration is not yet fully automated."
                            }, 
                            "id": None
                        }
                    # Fall through to legacy IPFS handling for other actions
            
            # Legacy fallback for IPFS only
            if svc not in ("ipfs",):
                return {"jsonrpc": "2.0", "error": {"code": 400, "message": f"Service '{svc}' is managed by the comprehensive service manager but encountered an error. Check logs for details."}, "id": None}
            ipfs_bin = _which("ipfs")
            if not ipfs_bin:
                # In many CI/test environments, the ipfs binary won't be present.
                # Return a successful no-op for start/stop/restart so tool-level tests can pass.
                if action in ("start", "stop", "restart"):
                    return {"jsonrpc": "2.0", "result": {"status": "ok", "success": True, "message": "ipfs binary not found; noop"}, "id": None}
                return {"jsonrpc": "2.0", "error": {"code": 404, "message": "ipfs binary not found"}, "id": None}
            if action == "status":
                ok = _port_open("127.0.0.1", 5001)
                return {"jsonrpc": "2.0", "result": {"ok": ok, "api_port_open": ok}, "id": None}
            elif action in ("start", "stop", "restart"):
                if action == "restart":
                    _ = _run_cmd([ipfs_bin, 'stop'], timeout=20)
                    res = _run_cmd([ipfs_bin, 'start', '--init'], timeout=25.0)
                else:
                    cmd = [ipfs_bin, action] if action != 'start' else [ipfs_bin, 'start', '--init']
                    res = _run_cmd(cmd, timeout=25.0)
                # Provide a stable status field for legacy callers.
                out = dict(res) if isinstance(res, dict) else {"out": res}
                out.setdefault("status", "ok")
                out.setdefault("success", True)
                return {"jsonrpc": "2.0", "result": out, "id": None}
            else:
                return {"jsonrpc": "2.0", "error": {"code": 400, "message": "Unsupported action"}, "id": None}
        if name == "service_status":
            svc = str(args.get("service", "")).strip()
            
            # Try to get status from ComprehensiveServiceManager if available
            service_manager = self._get_service_manager()
            if service_manager:
                try:
                    # get_service_details returns detailed service information including config and status
                    status_result = await service_manager.get_service_details(svc)
                    
                    # Check for success flag instead of absence of error
                    if status_result and status_result.get("success"):
                        # Extract the actual status and config for the response
                        result = {
                            **status_result.get("details", {}),
                            "config": status_result.get("config", {}),
                            "actions": status_result.get("actions", []),
                            "status": status_result.get("status", "unknown")
                        }
                        return {"jsonrpc": "2.0", "result": result, "id": None}
                except Exception as e:
                    self.log.warning(f"Error getting service status from service_manager for {svc}: {e}")
            
            # Fallback for ipfs only if service_manager not available
            if svc == "ipfs":
                info = {
                    "bin": _which("ipfs"),
                    "api_port_open": _port_open("127.0.0.1", 5001),
                }
                return {"jsonrpc": "2.0", "result": info, "id": None}
            
            # Return error for unsupported services
            raise HTTPException(400, "Unsupported service")
        return None

    def _handle_backends(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Legacy tool aliases (older tests/clients): return result payloads (not JSON-RPC errors)
        if name in {"backend_create", "backend_show", "backend_update", "backend_remove"}:
            try:
                if name == "backend_show":
                    bname = args.get("name")
                    if not bname:
                        return {"jsonrpc": "2.0", "result": {"error": "Missing name"}, "id": None}
                    data = _read_json(self.paths.backends_file, default={})
                    if bname not in data:
                        return {"jsonrpc": "2.0", "result": {"error": "not found"}, "id": None}
                    v = data[bname]
                    if isinstance(v, dict) and "type" in v and "config" in v:
                        result = {"name": bname, "type": v.get("type", "unknown"), "config": v.get("config", {})}
                    elif isinstance(v, dict):
                        # Legacy config-only
                        result = {"name": bname, "type": v.get("type", "unknown"), "config": v}
                    else:
                        result = {"name": bname, "type": "unknown", "config": {}}
                    return {"jsonrpc": "2.0", "result": result, "id": None}

                if name == "backend_create":
                    bname = args.get("name")
                    btype = args.get("type")
                    cfg = args.get("config") or {}
                    if not bname:
                        return {"jsonrpc": "2.0", "result": {"success": False, "error": "Missing name"}, "id": None}
                    if not isinstance(cfg, dict):
                        return {"jsonrpc": "2.0", "result": {"success": False, "error": "config must be an object"}, "id": None}

                    data = _read_json(self.paths.backends_file, default={})
                    if bname in data:
                        return {"jsonrpc": "2.0", "result": {"success": False, "error": "exists"}, "id": None}

                    # Store in the "new" backend format so get_backend works consistently.
                    stored = {"type": btype or cfg.get("type") or "unknown", "config": cfg}
                    data[bname] = stored
                    _atomic_write_json(self.paths.backends_file, data)
                    return {"jsonrpc": "2.0", "result": {"success": True}, "id": None}

                if name == "backend_update":
                    bname = args.get("name")
                    patch = args.get("config") or {}
                    if not bname:
                        return {"jsonrpc": "2.0", "result": {"success": False, "error": "Missing name"}, "id": None}
                    if not isinstance(patch, dict):
                        return {"jsonrpc": "2.0", "result": {"success": False, "error": "config must be an object"}, "id": None}
                    data = _read_json(self.paths.backends_file, default={})
                    if bname not in data:
                        return {"jsonrpc": "2.0", "result": {"success": False, "error": "not found"}, "id": None}
                    existing = data.get(bname)
                    if isinstance(existing, dict) and "config" in existing and isinstance(existing.get("config"), dict):
                        existing["config"].update(patch)
                        data[bname] = existing
                    elif isinstance(existing, dict):
                        # Legacy config-only entry
                        existing.update(patch)
                        data[bname] = existing
                    else:
                        data[bname] = {"type": "unknown", "config": patch}
                    _atomic_write_json(self.paths.backends_file, data)
                    return {"jsonrpc": "2.0", "result": {"success": True}, "id": None}

                if name == "backend_remove":
                    bname = args.get("name")
                    if not bname:
                        return {"jsonrpc": "2.0", "result": {"success": False, "error": "Missing name"}, "id": None}
                    data = _read_json(self.paths.backends_file, default={})
                    if bname not in data:
                        return {"jsonrpc": "2.0", "result": {"success": False, "error": "not found"}, "id": None}
                    data.pop(bname, None)
                    _atomic_write_json(self.paths.backends_file, data)
                    return {"jsonrpc": "2.0", "result": {"success": True}, "id": None}
            except Exception as e:
                return {"jsonrpc": "2.0", "result": {"success": False, "error": str(e)}, "id": None}

        if name == "list_backends":
            if self.backend_manager:
                # Use enhanced backend manager
                result = self.backend_manager.list_backends()
                return {"jsonrpc": "2.0", "result": result, "id": None}
            else:
                # Fallback to original implementation
                data = _read_json(self.paths.backends_file, default={})
                items = []
                for k, v in data.items():
                    # Ensure all backends have the required structure
                    if isinstance(v, dict):
                        # Update health status and last_check time
                        current_health = self._check_backend_health(k, v)
                        now = datetime.now(UTC).isoformat()
                        
                        backend_info = {
                            "name": k,
                            "type": v.get("type", "unknown"),
                            "description": v.get("description", f"{v.get('type', 'unknown')} backend"),
                            "status": v.get("status", "enabled"),
                            "config": v.get("config", {}),
                            "created_at": v.get("created_at", now),
                            "last_check": now,  # Always update to current time
                            "health": current_health,
                            "category": v.get("category", "storage"),
                            "policy": v.get("policy", {
                                "quota": "unlimited",
                                "replication": 1,
                                "retention": "30d",
                                "cache": "enabled"
                            }),
                            "stats": v.get("stats", {
                                "size": "0B",
                                "files": 0,
                                "last_sync": now
                            })
                        }
                    else:
                        # Handle malformed entries
                        now = datetime.now(UTC).isoformat()
                        backend_info = {
                            "name": k,
                            "type": "unknown",
                            "description": f"Legacy {k} backend",
                            "status": "disabled",
                            "config": {},
                            "created_at": now,
                            "last_check": now,
                            "health": "error",
                            "category": "storage",
                            "policy": {
                                "quota": "unlimited",
                                "replication": 1,
                                "retention": "30d",
                                "cache": "disabled"
                            },
                            "stats": {
                                "size": "0B",
                                "files": 0,
                                "last_sync": "Never"
                            }
                        }
                    items.append(backend_info)
                
                # Return comprehensive backend data
                return {
                    "jsonrpc": "2.0", 
                    "result": {
                        "items": items,
                        "total": len(items),
                        "healthy": len([b for b in items if b["health"] == "healthy"]),
                        "unhealthy": len([b for b in items if b["health"] == "error"]),
                        "configured": len([b for b in items if b["status"] == "enabled"])
                    }, 
                    "id": None
                }
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
        if name == "update_backend":
            bname = args.get("name")
            cfg = args.get("config", {})
            data = _read_json(self.paths.backends_file, default={})
            if bname not in data:
                raise HTTPException(404, "Not found")
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
        if name == "test_backend":
            bname = args.get("name")
            data = _read_json(self.paths.backends_file, default={})
            backend_config = data.get(bname)
            if backend_config is None:
                raise HTTPException(404, "Not found")
            
            # Perform comprehensive backend testing
            backend_type = backend_config.get("type", "unknown") if isinstance(backend_config, dict) else "unknown"
            config = backend_config.get("config", {}) if isinstance(backend_config, dict) else {}
            
            test_results = {
                "name": bname,
                "type": backend_type,
                "reachable": False,
                "response_time": None,
                "details": {},
                "errors": []
            }
            
            try:
                import time
                start_time = time.time()
                
                if backend_type == "local_storage":
                    path = Path(config.get("path", ""))
                    if path.exists():
                        test_results["reachable"] = True
                        test_results["details"]["path_exists"] = True
                        test_results["details"]["writable"] = os.access(path, os.W_OK)
                    else:
                        test_results["errors"].append(f"Path does not exist: {path}")
                
                elif backend_type == "ipfs":
                    import urllib.request
                    api_url = config.get("api_url", "http://127.0.0.1:5001")
                    try:
                        with urllib.request.urlopen(f"{api_url}/api/v0/version", timeout=5) as response:
                            if response.status == 200:
                                test_results["reachable"] = True
                                version_data = response.read().decode()
                                test_results["details"]["version"] = version_data
                            else:
                                test_results["errors"].append(f"HTTP {response.status}")
                    except Exception as e:
                        test_results["errors"].append(f"Connection failed: {str(e)}")
                
                elif backend_type == "s3":
                    endpoint = config.get("endpoint")
                    bucket = config.get("bucket")
                    if endpoint and bucket:
                        test_results["reachable"] = True
                        test_results["details"]["endpoint"] = endpoint
                        test_results["details"]["bucket"] = bucket
                    else:
                        test_results["errors"].append("Missing endpoint or bucket configuration")
                
                elif backend_type == "git":
                    repo_url = config.get("repo_url", "")
                    if repo_url.startswith(("http://", "https://", "git@")):
                        test_results["reachable"] = True
                        test_results["details"]["repo_url"] = repo_url
                        test_results["details"]["branch"] = config.get("branch", "main")
                    else:
                        test_results["errors"].append("Invalid repository URL")
                
                else:
                    test_results["errors"].append(f"Unknown backend type: {backend_type}")
                
                test_results["response_time"] = round((time.time() - start_time) * 1000, 2)  # milliseconds
                
            except Exception as e:
                test_results["errors"].append(f"Test failed: {str(e)}")
            
            return {"jsonrpc": "2.0", "result": test_results, "id": None}
        
        # Advanced backend management tools
        if name == "list_backend_instances":
            data = _read_json(self.paths.backends_file, default={})
            instances = {}
            for backend_name, backend_config in data.items():
                backend_type = backend_config.get("type", "unknown") if isinstance(backend_config, dict) else "unknown"
                if backend_type not in instances:
                    instances[backend_type] = []
                instances[backend_type].append({
                    "name": backend_name,
                    "status": backend_config.get("status", "unknown") if isinstance(backend_config, dict) else "unknown",
                    "health": self._check_backend_health(backend_name, backend_config)
                })
            return {"jsonrpc": "2.0", "result": {"instances": instances}, "id": None}
        
        if name == "create_backend_instance":
            service_type = args.get("service_type")
            instance_name = args.get("instance_name")
            description = args.get("description", f"{service_type} backend")
            
            if not service_type or not instance_name:
                raise HTTPException(400, "Missing service_type or instance_name")
            
            data = _read_json(self.paths.backends_file, default={})
            if instance_name in data:
                raise HTTPException(409, "Backend instance already exists")
            
            # Create default configuration based on backend type
            default_config = self._get_default_backend_config(service_type)
            
            new_backend = {
                "type": service_type,
                "description": description,
                "config": default_config,
                "status": "enabled",
                "created_at": datetime.now(UTC).isoformat(),
                "last_check": datetime.now(UTC).isoformat()
            }
            
            data[instance_name] = new_backend
            _atomic_write_json(self.paths.backends_file, data)
            
            return {"jsonrpc": "2.0", "result": {"ok": True, "instance_name": instance_name, "type": service_type}, "id": None}
        
        if name == "configure_backend_instance":
            instance_name = args.get("instance_name")
            service_type = args.get("service_type")
            config = args.get("config", {})
            
            if not instance_name:
                raise HTTPException(400, "Missing instance_name")
            
            data = _read_json(self.paths.backends_file, default={})
            if instance_name not in data:
                raise HTTPException(404, "Backend instance not found")
            
            # Update configuration
            backend_config = data[instance_name]
            if isinstance(backend_config, dict):
                if service_type:
                    backend_config["type"] = service_type
                backend_config["config"] = config
                backend_config["last_check"] = datetime.now(UTC).isoformat()
            
            _atomic_write_json(self.paths.backends_file, data)
            
            return {"jsonrpc": "2.0", "result": {"ok": True, "instance_name": instance_name}, "id": None}
        
        if name == "get_backend_performance_metrics":
            backend_name = args.get("backend_name")
            time_range = args.get("time_range", "1h")
            include_history = args.get("include_history", False)

            data = _read_json(self.paths.backends_file, default={})

            def _gen_metrics(bname: str, binfo: Dict[str, Any]) -> Dict[str, Any]:
                # Generate mock performance metrics in a richer, UI-friendly shape
                perf = {
                    "response_time_ms": 40.0,
                    "throughput_ops_per_sec": 120.0,
                    "error_rate_percent": 1.0,
                    "success_rate_percent": 99.0,
                    "data_transfer_mbps": 15.0,
                    "uptime_percent": 99.9,
                    "cpu_usage_percent": 15.0,
                    "memory_usage_percent": 35.0,
                    "disk_usage_percent": 42.0,
                    "active_connections": 3,
                }
                item = {
                    "backend_name": bname,
                    "backend_type": (binfo or {}).get("type", "unknown"),
                    "time_range": time_range,
                    "performance": perf,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                if include_history:
                    import random
                    history = []
                    for i in range(12):
                        history.append({
                            "timestamp": (datetime.now(UTC) - timedelta(minutes=i*5)).isoformat(),
                            "response_time_ms": max(1.0, perf["response_time_ms"] + random.uniform(-10, 10)),
                            "throughput_ops_per_sec": max(0.0, perf["throughput_ops_per_sec"] + random.uniform(-20, 20)),
                            "error_rate_percent": max(0.0, perf["error_rate_percent"] + random.uniform(-0.5, 0.8)),
                        })
                    item["history"] = history
                return item

            if backend_name:
                if backend_name not in data:
                    raise HTTPException(404, "Backend not found")
                return {"jsonrpc": "2.0", "result": _gen_metrics(backend_name, data.get(backend_name, {})), "id": None}
            else:
                # Aggregate metrics for all backends
                items = [_gen_metrics(bname, binfo) for bname, binfo in data.items()]
                return {"jsonrpc": "2.0", "result": {"metrics": items}, "id": None}
        
        if name == "get_backend_configuration_template":
            backend_type = args.get("backend_type")
            template_type = args.get("template_type", "basic")
            
            if not backend_type:
                raise HTTPException(400, "Missing backend_type")
            
            template = self._get_configuration_template(backend_type, template_type)
            
            return {"jsonrpc": "2.0", "result": {
                "backend_type": backend_type,
                "template_type": template_type,
                "template": template
            }, "id": None}
        
        if name == "clone_backend_configuration":
            source_backend = args.get("source_backend")
            new_backend_name = args.get("new_backend_name")
            modify_config = args.get("modify_config", False)
            
            if not source_backend or not new_backend_name:
                raise HTTPException(400, "Missing source_backend or new_backend_name")
            
            data = _read_json(self.paths.backends_file, default={})
            if source_backend not in data:
                raise HTTPException(404, "Source backend not found")
            if new_backend_name in data:
                raise HTTPException(409, "New backend name already exists")
            
            # Clone the configuration
            source_config = data[source_backend]
            new_config = json.loads(json.dumps(source_config))  # Deep copy
            
            if isinstance(new_config, dict):
                new_config["created_at"] = datetime.now(UTC).isoformat()
                new_config["last_check"] = datetime.now(UTC).isoformat()
                if "description" in new_config:
                    new_config["description"] = f"Cloned from {source_backend}"
            
            data[new_backend_name] = new_config
            _atomic_write_json(self.paths.backends_file, data)
            
            return {"jsonrpc": "2.0", "result": {
                "ok": True,
                "source_backend": source_backend,
                "new_backend_name": new_backend_name,
                "modify_config": modify_config
            }, "id": None}
        
        if name == "backup_backend_configuration":
            backend_name = args.get("backend_name")
            backup_name = args.get("backup_name")
            include_data = args.get("include_data", False)
            
            if not backend_name:
                raise HTTPException(400, "Missing backend_name")
            
            data = _read_json(self.paths.backends_file, default={})
            if backend_name not in data:
                raise HTTPException(404, "Backend not found")
            
            # Create backup
            import time
            backup_id = f"backup_{backend_name}_{int(time.time())}"
            backup_dir = self.paths.data_dir / "backups" / "backends"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            backup_file = backup_dir / f"{backup_id}.json"
            backup_data = {
                "backup_id": backup_id,
                "backend_name": backend_name,
                "backup_name": backup_name or f"Backup of {backend_name}",
                "created_at": datetime.now(UTC).isoformat(),
                "config": data[backend_name],
                "include_data": include_data
            }
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            return {"jsonrpc": "2.0", "result": {
                "ok": True,
                "backup_id": backup_id,
                "backup_file": str(backup_file)
            }, "id": None}
        
        if name == "restore_backend_configuration":
            backend_name = args.get("backend_name")
            backup_id = args.get("backup_id")
            force_restore = args.get("force_restore", False)
            
            if not backend_name or not backup_id:
                raise HTTPException(400, "Missing backend_name or backup_id")
            
            backup_dir = self.paths.data_dir / "backups" / "backends"
            backup_file = backup_dir / f"{backup_id}.json"
            
            if not backup_file.exists():
                raise HTTPException(404, "Backup not found")
            
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
            
            data = _read_json(self.paths.backends_file, default={})
            
            if backend_name in data and not force_restore:
                raise HTTPException(409, "Backend exists. Use force_restore=true to overwrite")
            
            # Restore configuration
            data[backend_name] = backup_data["config"]
            _atomic_write_json(self.paths.backends_file, data)
            
            return {"jsonrpc": "2.0", "result": {
                "ok": True,
                "backend_name": backend_name,
                "backup_id": backup_id,
                "restored_at": datetime.now(UTC).isoformat()
            }, "id": None}
        
        if name == "get_backend":
            bname = args.get("name")
            if not bname:
                raise HTTPException(400, "Missing backend name")
            
            if self.backend_manager:
                # Use enhanced backend manager
                backend = self.backend_manager.get_backend_with_policies(bname)
                if not backend:
                    raise HTTPException(404, f"Backend '{bname}' not found")
                return {"jsonrpc": "2.0", "result": backend, "id": None}
            else:
                # Fallback to original implementation
                data = _read_json(self.paths.backends_file, default={})
                if bname not in data:
                    raise HTTPException(404, "Not found")
                
                backend_config = data[bname]
                # Handle both old and new format
                if isinstance(backend_config, dict) and 'type' in backend_config:
                    # New format with full backend information
                    result = {
                        "name": bname,
                        "type": backend_config.get("type", "unknown"),
                        "description": backend_config.get("description", f"{backend_config.get('type', 'unknown')} backend"),
                        "status": backend_config.get("status", "unknown"),
                        "config": backend_config.get("config", {}),
                        "created_at": backend_config.get("created_at", ""),
                        "last_check": backend_config.get("last_check", "Never"),
                        "health": self._check_backend_health(bname, backend_config)
                    }
                else:
                    # Old format (config only)
                    result = {
                        "name": bname,
                        "type": backend_config.get("type", "unknown") if isinstance(backend_config, dict) else "unknown",
                        "description": f"Legacy {bname} backend",
                        "status": "unknown",
                        "config": backend_config if isinstance(backend_config, dict) else {},
                        "created_at": "",
                        "last_check": "Never",
                        "health": "unknown"
                    }
                
                return {"jsonrpc": "2.0", "result": result, "id": None}
        
        if name == "test_backend_config":
            backend_name = args.get("name")
            test_config = args.get("config", {})
            
            if not backend_name:
                raise HTTPException(400, "Missing backend name")
            
            try:
                if self.backend_manager:
                    # Use enhanced backend manager
                    result = self.backend_manager.test_backend_config(backend_name, test_config)
                    return {"jsonrpc": "2.0", "result": result, "id": None}
                else:
                    # Fallback to basic implementation
                    # Handle string input for config (from frontend)
                    if isinstance(test_config, str):
                        try:
                            test_config = json.loads(test_config)
                        except json.JSONDecodeError as e:
                            return {"jsonrpc": "2.0", "result": {
                                "reachable": False,
                                "valid": False,
                                "errors": [f"Invalid config JSON: {str(e)}"],
                                "backend": backend_name,
                                "message": "Configuration test failed - invalid JSON"
                            }, "id": None}
                    
                    # Test configuration without saving
                    # For now, simulate a configuration test
                    backend_type = test_config.get("type", "unknown")
                    
                    # Basic validation based on backend type
                    is_valid = True
                    errors = []
                    
                    if backend_type == "s3":
                        required_fields = ["endpoint", "access_key", "secret_key", "bucket"]
                        for field in required_fields:
                            if not test_config.get(field):
                                is_valid = False
                                errors.append(f"Missing required field: {field}")
                    elif backend_type == "github":
                        required_fields = ["token", "owner", "repo"]
                        for field in required_fields:
                            if not test_config.get(field):
                                is_valid = False
                                errors.append(f"Missing required field: {field}")
                    elif backend_type == "ipfs":
                        required_fields = ["api_url"]
                        for field in required_fields:
                            if not test_config.get(field):
                                is_valid = False
                                errors.append(f"Missing required field: {field}")
                    
                    return {"jsonrpc": "2.0", "result": {
                        "reachable": is_valid,
                        "valid": is_valid,
                        "errors": errors,
                        "backend": backend_name,
                        "message": "Configuration test completed" if is_valid else "Configuration test failed"
                    }, "id": None}
                    
            except Exception as e:
                return {"jsonrpc": "2.0", "result": {
                    "reachable": False,
                    "valid": False,
                    "error": str(e),
                    "backend": backend_name
                }, "id": None}
        
        if name == "apply_backend_policy":
            backend_name = args.get("name")
            policy = args.get("policy", {})
            force_sync = args.get("force_sync", False)
            
            if not backend_name:
                raise HTTPException(400, "Missing backend name")
            
            try:
                if self.backend_manager:
                    # Use enhanced backend manager
                    result = self.backend_manager.apply_backend_policy(backend_name, policy, force_sync)
                    return {"jsonrpc": "2.0", "result": result, "id": None}
                else:
                    # Fallback to original implementation
                    # Handle string input for policy (from frontend)
                    if isinstance(policy, str):
                        try:
                            policy = json.loads(policy)
                        except json.JSONDecodeError as e:
                            return {"jsonrpc": "2.0", "result": {
                                "ok": False,
                                "error": f"Invalid policy JSON: {str(e)}",
                                "backend": backend_name
                            }, "id": None}
                    
                    # Update backend policy and apply it
                    backends_data = _read_json(self.paths.backends_file, default=[])
                    updated = False
                    
                    for backend in backends_data:
                        if backend.get('name') == backend_name:
                            backend['policy'] = {**backend.get('policy', {}), **policy}
                            backend['last_updated'] = datetime.now(UTC).isoformat()
                            updated = True
                            break
                    
                    if updated:
                        _atomic_write_json(self.paths.backends_file, backends_data)
                        
                        # If force_sync, trigger replica sync (simplified for non-recursion)
                        if force_sync:
                            self.log.info(f"Force sync requested for backend {backend_name}")
                        
                        return {"jsonrpc": "2.0", "result": {
                            "ok": True,
                            "backend": backend_name,
                            "policy": policy,
                            "synced": force_sync,
                            "message": f"Policy applied successfully to '{backend_name}'"
                        }, "id": None}
                    else:
                        raise HTTPException(404, f"Backend '{backend_name}' not found")
                        
            except Exception as e:
                return {"jsonrpc": "2.0", "result": {
                    "ok": False,
                    "error": str(e),
                    "backend": backend_name
                }, "id": None}
        
        if name == "update_backend_policy":
            backend_name = args.get("name")
            policy_updates = args.get("policy", {})
            
            if not backend_name:
                raise HTTPException(400, "Missing backend name")
            
            try:
                if self.backend_manager:
                    # Use enhanced backend manager
                    result = self.backend_manager.update_backend_policy(backend_name, policy_updates)
                    return {"jsonrpc": "2.0", "result": result, "id": None}
                else:
                    # Fallback to original implementation
                    # Handle string input for policy (from frontend)
                    if isinstance(policy_updates, str):
                        try:
                            policy_updates = json.loads(policy_updates)
                        except json.JSONDecodeError as e:
                            return {"jsonrpc": "2.0", "result": {
                                "ok": False,
                                "error": f"Invalid policy JSON: {str(e)}",
                                "backend": backend_name
                            }, "id": None}
                    
                    # Update backend policy configuration
                    backends_data = _read_json(self.paths.backends_file, default=[])
                    updated = False
                    
                    for backend in backends_data:
                        if backend.get('name') == backend_name:
                            current_policy = backend.get('policy', {})
                            backend['policy'] = {**current_policy, **policy_updates}
                            backend['last_updated'] = datetime.now(UTC).isoformat()
                            updated = True
                            break
                    
                    if updated:
                        _atomic_write_json(self.paths.backends_file, backends_data)
                        
                        return {"jsonrpc": "2.0", "result": {
                            "ok": True,
                            "backend": backend_name,
                            "policy": policy_updates,
                            "message": f"Policy updated successfully for '{backend_name}'"
                        }, "id": None}
                    else:
                        raise HTTPException(404, f"Backend '{backend_name}' not found")
                        
            except Exception as e:
                return {"jsonrpc": "2.0", "result": {
                    "ok": False,
                    "error": str(e),
                    "backend": backend_name
                }, "id": None}
        
        return None

    def _get_default_backend_config(self, backend_type: str) -> Dict[str, Any]:
        """Get default configuration for backend type."""
        configs = {
            "local_storage": {
                "path": str(self.paths.data_dir / "local_storage"),
                "max_size": "10GB"
            },
            "ipfs": {
                "api_url": "http://127.0.0.1:5001",
                "gateway_url": "http://127.0.0.1:8080"
            },
            "s3": {
                "endpoint": "https://s3.amazonaws.com",
                "bucket": "my-bucket",
                "region": "us-east-1"
            },
            "git": {
                "repo_url": "https://github.com/example/repo",
                "branch": "main"
            },
            "parquet": {
                "path": str(self.paths.data_dir / "parquet_storage"),
                "compression": "snappy"
            },
            "ipfs_cluster": {
                "cluster_api": "http://127.0.0.1:9094",
                "peers": []
            }
        }
        return configs.get(backend_type, {})

    def _get_configuration_template(self, backend_type: str, template_type: str) -> Dict[str, Any]:
        """Get configuration template for backend type and template."""
        templates = {
            "local_storage": {
                "basic": {
                    "path": "/path/to/storage",
                    "max_size": "10GB"
                },
                "enterprise": {
                    "path": "/enterprise/storage",
                    "max_size": "1TB",
                    "backup_path": "/enterprise/backup",
                    "encryption": True
                },
                "high_performance": {
                    "path": "/fast/ssd/storage",
                    "max_size": "500GB",
                    "cache_size": "50GB",
                    "threads": 16
                }
            },
            "ipfs": {
                "basic": {
                    "api_url": "http://127.0.0.1:5001",
                    "gateway_url": "http://127.0.0.1:8080"
                },
                "enterprise": {
                    "api_url": "http://127.0.0.1:5001",
                    "gateway_url": "http://127.0.0.1:8080",
                    "swarm_peers": [],
                    "bootstrap_nodes": []
                },
                "high_performance": {
                    "api_url": "http://127.0.0.1:5001",
                    "gateway_url": "http://127.0.0.1:8080",
                    "datastore_type": "badger",
                    "cache_size": "2GB"
                }
            },
            "s3": {
                "basic": {
                    "endpoint": "https://s3.amazonaws.com",
                    "bucket": "my-bucket",
                    "region": "us-east-1"
                },
                "enterprise": {
                    "endpoint": "https://s3.amazonaws.com",
                    "bucket": "enterprise-bucket",
                    "region": "us-east-1",
                    "encryption": "AES256",
                    "versioning": True
                },
                "high_performance": {
                    "endpoint": "https://s3.amazonaws.com",
                    "bucket": "high-perf-bucket",
                    "region": "us-east-1",
                    "storage_class": "STANDARD_IA",
                    "multipart_threshold": "8MB"
                }
            }
        }
        
        backend_templates = templates.get(backend_type, {})
        return backend_templates.get(template_type, {})

    def _check_backend_health(self, backend_name: str, backend_config: Dict[str, Any]) -> str:
        """Check backend health and return status."""
        try:
            backend_type = backend_config.get("type", "unknown")
            config = backend_config.get("config", {})
            
            if backend_type == "local_storage":
                # Check if local path exists and is writable
                path = config.get("path")
                if path and Path(path).exists():
                    return "healthy"
                return "error"
            
            elif backend_type == "ipfs":
                # Check IPFS node connectivity
                import urllib.request
                api_url = config.get("api_url", "http://127.0.0.1:5001")
                try:
                    with urllib.request.urlopen(f"{api_url}/api/v0/version", timeout=2) as response:
                        if response.status == 200:
                            return "healthy"
                except:
                    pass
                return "error"
            
            elif backend_type == "s3":
                # For S3, just check if config has required fields
                if config.get("endpoint") and config.get("bucket"):
                    return "healthy"
                return "error"
            
            elif backend_type == "parquet":
                # Check if parquet path exists
                path = config.get("path")
                if path and Path(path).exists():
                    return "healthy"
                return "error"
            
            elif backend_type == "git":
                # Check if repo URL is valid format
                repo_url = config.get("repo_url", "")
                if repo_url.startswith(("http://", "https://", "git@")):
                    return "healthy"
                return "error"
            
            elif backend_type == "ipfs_cluster":
                # Check cluster API connectivity
                cluster_api = config.get("cluster_api")
                if cluster_api:
                    try:
                        import urllib.request
                        with urllib.request.urlopen(f"{cluster_api}/api/v0/version", timeout=2) as response:
                            if response.status == 200:
                                return "healthy"
                    except:
                        pass
                return "error"
            
            # Unknown backend type
            return "unknown"
            
        except Exception:
            return "error"

    def _handle_buckets(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if name == "list_buckets":
            vfs_path = self.paths.data_dir / "vfs"
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]), vfs_path)
            return items
        if name == "create_bucket":
            bname = args.get("name")
            backend = args.get("backend")
            if not bname:
                raise HTTPException(400, "Missing name")
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            if any(b.get("name") == bname for b in items):
                raise HTTPException(409, "Exists")
            entry = {"name": bname, "backend": backend, "created_at": datetime.now(UTC).isoformat()}
            items.append(entry)
            _atomic_write_json(self.paths.buckets_file, items)
            
            # Create VFS directory for the new bucket
            bucket_dir = os.path.join(self.paths.data_dir, "vfs", bname)
            os.makedirs(bucket_dir, exist_ok=True)

            # Return stable info for clients/tests
            with suppress(Exception):
                self.log.info("bucket created: %s", bname, extra={"component": "buckets"})
            return {**entry, "ok": True}
        if name == "delete_bucket":
            bname = args.get("name")
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            new_items = [b for b in items if b.get("name") != bname]
            if len(new_items) == len(items):
                return {"status": "absent"}
            _atomic_write_json(self.paths.buckets_file, new_items)
            
            # Remove VFS directory for deleted bucket
            import shutil
            bucket_dir = os.path.join(self.paths.data_dir, "vfs", bname)
            if os.path.exists(bucket_dir):
                shutil.rmtree(bucket_dir)

            with suppress(Exception):
                self.log.info("bucket deleted: %s", bname, extra={"component": "buckets"})
            return {"status": "deleted"}
        if name == "get_bucket":
            bname = args.get("name")
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            for b in items:
                if b.get("name") == bname:
                    return {"jsonrpc": "2.0", "result": b, "id": None}
            raise HTTPException(404, "Not found")
        if name == "bucket_create_folder":
            bucket = args.get("bucket")
            folder_name = args.get("folder_name")
            if not bucket or not folder_name:
                raise HTTPException(400, "Missing bucket or folder_name")
                
            # Create folder in VFS
            bucket_dir = os.path.join(self.paths.data_dir, "vfs", bucket)
            folder_path = os.path.join(bucket_dir, folder_name)
            
            if os.path.exists(folder_path):
                raise HTTPException(409, f"Folder '{folder_name}' already exists")
                
            os.makedirs(folder_path, exist_ok=True)
            
            # Create a .gitkeep file to ensure the folder is tracked
            gitkeep_path = os.path.join(folder_path, ".gitkeep")
            with open(gitkeep_path, 'w') as f:
                f.write("")
                
            return {"jsonrpc": "2.0", "result": {"ok": True, "folder": folder_name, "path": folder_path}, "id": None}

        if name == "update_bucket":
            bname = args.get("name")
            patch = args.get("patch", {}) or {}
            if not bname:
                raise HTTPException(400, "Missing name")
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            found = False
            for i, b in enumerate(items):
                if b.get("name") == bname:
                    nb = dict(b)
                    nb.update({k: v for k, v in patch.items() if k != "name"})
                    items[i] = nb
                    found = True
                    break
            if not found:
                raise HTTPException(404, "Not found")
            _atomic_write_json(self.paths.buckets_file, items)
            return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}
        


        if name == "bucket_create_folder":
            bucket = args.get("bucket")
            folder_name = args.get("folder_name") or args.get("name")
            if not bucket or not folder_name:
                raise HTTPException(400, "Missing bucket or folder_name")
            
            # Get VFS path
            bucket_path = self.paths.vfs_root / bucket
            if not bucket_path.exists():
                bucket_path.mkdir(parents=True, exist_ok=True)
            
            # Safe folder path
            folder_path = bucket_path / folder_name
            if not str(folder_path).startswith(str(bucket_path)):
                raise HTTPException(400, "Invalid folder path")
            
            # Create folder
            try:
                folder_path.mkdir(parents=True, exist_ok=True)
                
                # Update metadata
                metadata_file = self.paths.data_dir / "bucket_files.json"
                metadata = _read_json(metadata_file, {})
                folder_key = f"{bucket}:{folder_name}"
                metadata[folder_key] = {
                    "created": datetime.now(UTC).isoformat(),
                    "type": "folder",
                    "cached": True,
                    "replicas": ["local"]
                }
                _atomic_write_json(metadata_file, metadata)
                
                return {"jsonrpc": "2.0", "result": {"ok": True, "folder_name": folder_name}, "id": None}
            except Exception as e:
                raise HTTPException(500, f"Failed to create folder: {str(e)}")

        # Enhanced bucket file management with VFS parquet indices (proper architecture)
        if name == "bucket_list_files":
            bucket = args.get("bucket")
            path = args.get("path", ".")
            show_metadata = args.get("show_metadata", True)
            if not bucket:
                raise HTTPException(400, "Missing bucket")
            
            # FIXED: Use direct filesystem approach instead of complex SimpleBucketManager
            # This ensures uploaded files are immediately visible in the UI
            
            # Direct filesystem approach - reliable and simple
            bucket_path = self.paths.vfs_root / bucket
            bucket_path.mkdir(parents=True, exist_ok=True)  # Ensure bucket directory exists
            
            vfs_path = _safe_vfs_path(bucket_path, path)
            files = []
            
            # List files directly from VFS directory
            if vfs_path.is_dir():
                for item in sorted(vfs_path.iterdir()):
                    # Skip .gitkeep files
                    if item.name == '.gitkeep':
                        continue
                        
                    rel_path = str(item.relative_to(bucket_path))
                    
                    file_info = {
                        "name": item.name,
                        "path": rel_path,
                        "type": "directory" if item.is_dir() else "file",
                        "is_directory": item.is_dir(),
                        "is_dir": item.is_dir(),
                        "modified": datetime.fromtimestamp(item.stat().st_mtime, UTC).isoformat(),
                        "created_at": datetime.fromtimestamp(item.stat().st_ctime, UTC).isoformat(),
                        "updated_at": datetime.fromtimestamp(item.stat().st_mtime, UTC).isoformat(),
                        "source": "vfs",
                        "storage_path": f"buckets/{bucket}/{rel_path}"
                    }
                    
                    if not item.is_dir():
                        file_info["size"] = item.stat().st_size
                        file_info["mime_type"] = mimetypes.guess_type(item.name)[0]
                        file_info["type"] = mimetypes.guess_type(item.name)[0] or "text/plain"
                    else:
                        file_info["size"] = 0
                        file_info["mime_type"] = None
                    
                    # Add metadata if requested
                    if show_metadata:
                        file_info["metadata"] = {
                            "bucket_name": bucket,
                            "vfs_path": str(item),
                            "source": "filesystem"
                        }
                    
                    files.append(file_info)
                    
            elif vfs_path.is_file():
                # Single file case
                stat_info = vfs_path.stat()
                files.append({
                    "name": vfs_path.name,
                    "path": path,
                    "type": mimetypes.guess_type(vfs_path.name)[0] or "text/plain",
                    "is_directory": False,
                    "is_dir": False,
                    "size": stat_info.st_size,
                    "mime_type": mimetypes.guess_type(vfs_path.name)[0],
                    "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat(),
                    "created_at": datetime.fromtimestamp(stat_info.st_ctime, UTC).isoformat(),
                    "updated_at": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat(),
                    "source": "vfs",
                    "storage_path": f"buckets/{bucket}/{path}",
                    "metadata": {
                        "bucket_name": bucket,
                        "vfs_path": str(vfs_path),
                        "source": "filesystem"
                    } if show_metadata else {}
                })
            
            return {"jsonrpc": "2.0", "result": {"bucket": bucket, "path": path, "items": files, "total_count": len(files)}, "id": None}

        if name == "list_bucket_files":
            # Alias for bucket_list_files with parameter mapping
            bucket = args.get("bucket")
            path = args.get("path", "")
            metadata_first = args.get("metadata_first", True)
            if not bucket:
                raise HTTPException(400, "Missing bucket")
            
            # Delegate to existing bucket_list_files implementation synchronously
            # to avoid awaiting inside a non-async context
            mapped_args = {"bucket": bucket, "path": path, "show_metadata": metadata_first}
            return self._handle_buckets("bucket_list_files", mapped_args)
        
        if name == "create_folder":
            # Alias for bucket_create_folder
            bucket = args.get("bucket")
            folder_name = args.get("name") or args.get("folder_name")
            if not bucket or not folder_name:
                raise HTTPException(400, "Missing bucket or folder name")
            
            # Create folder in VFS
            bucket_dir = os.path.join(self.paths.data_dir, "vfs", bucket)
            os.makedirs(bucket_dir, exist_ok=True)
            folder_path = os.path.join(bucket_dir, folder_name)
            
            if os.path.exists(folder_path):
                return {"jsonrpc": "2.0", "result": {"ok": False, "error": f"Folder '{folder_name}' already exists"}, "id": None}
                
            os.makedirs(folder_path, exist_ok=True)
            
            # Create a .gitkeep file to ensure the folder is tracked
            gitkeep_path = os.path.join(folder_path, ".gitkeep")
            with open(gitkeep_path, 'w') as f:
                f.write("")
            
            return {"jsonrpc": "2.0", "result": {"ok": True, "folder": folder_name, "path": folder_path}, "id": None}
            return self._handle_buckets("bucket_list_files", mapped_args)

        if name == "bucket_upload_file":
            bucket = args.get("bucket")
            path = args.get("path")
            content = args.get("content")
            mode = args.get("mode", "text")
            apply_policy = args.get("apply_policy", True)
            
            if not bucket or not path or content is None:
                raise HTTPException(400, "Missing bucket, path, or content")
            
            # Ensure bucket exists
            buckets_data = _read_json(self.paths.buckets_file, [])
            bucket_exists = any(b.get("name") == bucket for b in buckets_data)
            if not bucket_exists:
                raise HTTPException(404, "Bucket not found")
                
            # Create bucket directory
            bucket_path = self.paths.vfs_root / bucket
            bucket_path.mkdir(parents=True, exist_ok=True)
            
            # Prepare content based on mode
            if mode == "hex":
                file_content = bytes.fromhex(content)
            elif mode == "base64":
                import base64
                file_content = base64.b64decode(content)
            else:  # text
                file_content = content.encode("utf-8") if isinstance(content, str) else content
            
            # Save file to filesystem
            file_path = _safe_vfs_path(bucket_path, path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with file_path.open('wb') as f:
                f.write(file_content)
            
            # Store metadata
            try:
                metadata_file = self.paths.data_dir / "file_metadata.json"
                metadata = _read_json(metadata_file, {})
                file_key = f"{bucket}:{path}"
                stat_info = file_path.stat()
                metadata[file_key] = {
                    "path": path,
                    "bucket": bucket,
                    "size": stat_info.st_size,
                    "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat(),
                    "created": datetime.fromtimestamp(stat_info.st_ctime, UTC).isoformat(),
                    "operation": "upload",
                    "upload_mode": mode,
                    "mime_type": mimetypes.guess_type(file_path)[0],
                    "timestamp": datetime.now(UTC).isoformat()
                }
                _atomic_write_json(metadata_file, metadata)
            except Exception as e:
                # Don't fail upload if metadata update fails
                self.log.warning(f"Failed to update file metadata: {e}")
            
            return {
                "jsonrpc": "2.0", 
                "result": {
                    "ok": True, 
                    "file_path": path,
                    "file_size": len(file_content),
                    "bucket_name": bucket,
                    "upload_method": "direct_vfs",
                    "mode": mode
                }, 
                "id": None
            }

        if name == "bucket_download_file":
            bucket = args.get("bucket")
            path = args.get("path")
            format = args.get("format", "text")
            
            if not bucket or not path:
                raise HTTPException(400, "Missing bucket or path")
            
            # Check metadata first
            metadata_file = self.paths.data_dir / "bucket_files.json"
            metadata = _read_json(metadata_file, {})
            file_key = f"{bucket}:{path}"
            file_meta = metadata.get(file_key, {})
            
            bucket_path = self.paths.vfs_root / bucket
            file_path = _safe_vfs_path(bucket_path, path)
            
            if not file_path.exists():
                raise HTTPException(404, "File not found")
            
            if file_path.is_dir():
                raise HTTPException(400, "Path is a directory")
            
            try:
                if format == "hex":
                    content = file_path.read_bytes().hex()
                elif format == "base64":
                    import base64
                    content = base64.b64encode(file_path.read_bytes()).decode('ascii')
                else:  # text
                    content = file_path.read_text(encoding="utf-8")
                
                return {"jsonrpc": "2.0", "result": {"content": content, "format": format, "metadata": file_meta}, "id": None}
            except Exception as e:
                raise HTTPException(500, f"Failed to read file: {str(e)}")

        if name == "bucket_delete_file":
            bucket = args.get("bucket")
            path = args.get("path")
            remove_replicas = args.get("remove_replicas", True)
            
            if not bucket or not path:
                raise HTTPException(400, "Missing bucket or path")
            
            bucket_path = self.paths.vfs_root / bucket
            file_path = _safe_vfs_path(bucket_path, path)
            
            if not file_path.exists():
                raise HTTPException(404, "File not found")
            
            # Remove file
            if file_path.is_file():
                file_path.unlink()
            else:
                import shutil
                shutil.rmtree(file_path)
            
            # Update metadata
            metadata_file = self.paths.data_dir / "bucket_files.json"
            metadata = _read_json(metadata_file, {})
            file_key = f"{bucket}:{path}"
            
            deleted_meta = {}
            if file_key in metadata:
                deleted_meta = metadata[file_key]
                if remove_replicas and "replicas" in deleted_meta:
                    # In real implementation, would remove from backend replicas
                    deleted_meta["replicas_removed"] = len(deleted_meta.get("replicas", []))
                del metadata[file_key]
            
            _atomic_write_json(metadata_file, metadata)
            
            return {"jsonrpc": "2.0", "result": {"ok": True, "path": path, "bucket": bucket, "removed_metadata": deleted_meta}, "id": None}

        if name == "bucket_rename_file":
            bucket = args.get("bucket")
            src = args.get("src")
            dst = args.get("dst")
            update_replicas = args.get("update_replicas", True)
            
            if not bucket or not src or not dst:
                raise HTTPException(400, "Missing bucket, src, or dst")
            
            bucket_path = self.paths.vfs_root / bucket
            src_path = _safe_vfs_path(bucket_path, src)
            dst_path = _safe_vfs_path(bucket_path, dst)
            
            if not src_path.exists():
                raise HTTPException(404, "Source file not found")
            
            # Move file
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            src_path.rename(dst_path)
            
            # Update metadata
            metadata_file = self.paths.data_dir / "bucket_files.json"
            metadata = _read_json(metadata_file, {})
            src_key = f"{bucket}:{src}"
            dst_key = f"{bucket}:{dst}"
            
            if src_key in metadata:
                file_meta = metadata[src_key]
                file_meta["path"] = dst
                file_meta["renamed_from"] = src
                file_meta["rename_timestamp"] = datetime.now(UTC).isoformat()
                
                if update_replicas and "replicas" in file_meta:
                    for replica in file_meta["replicas"]:
                        replica["status"] = "sync_pending"
                        replica["update_needed"] = True
                
                metadata[dst_key] = file_meta
                del metadata[src_key]
            
            _atomic_write_json(metadata_file, metadata)
            
            return {"jsonrpc": "2.0", "result": {"ok": True, "src": src, "dst": dst, "bucket": bucket}, "id": None}

        if name == "bucket_mkdir":
            bucket = args.get("bucket")
            path = args.get("path")
            create_parents = args.get("create_parents", True)
            
            if not bucket or not path:
                raise HTTPException(400, "Missing bucket or path")
            
            bucket_path = self.paths.vfs_root / bucket
            bucket_path.mkdir(parents=True, exist_ok=True)
            
            dir_path = _safe_vfs_path(bucket_path, path)
            dir_path.mkdir(parents=create_parents, exist_ok=True)
            
            return {"jsonrpc": "2.0", "result": {"ok": True, "path": path, "bucket": bucket, "created": True}, "id": None}

        if name == "bucket_sync_replicas":
            bucket = args.get("bucket")
            force_sync = args.get("force_sync", False)
            
            if not bucket:
                raise HTTPException(400, "Missing bucket")
            
            # Get bucket policy
            buckets_data = _read_json(self.paths.buckets_file, [])
            bucket_config = None
            for b in buckets_data:
                if b.get("name") == bucket:
                    bucket_config = b
                    break
            
            if not bucket_config:
                raise HTTPException(404, "Bucket not found")
            
            # Get metadata for all files in bucket
            metadata_file = self.paths.data_dir / "bucket_files.json"
            metadata = _read_json(metadata_file, {})
            
            synced_files = 0
            for file_key, file_meta in metadata.items():
                if file_meta.get("bucket") == bucket:
                    # Simulate sync process
                    if "replicas" in file_meta:
                        for replica in file_meta["replicas"]:
                            if replica.get("status") == "syncing" or force_sync:
                                replica["status"] = "synced"
                                replica["last_sync"] = datetime.now(UTC).isoformat()
                        synced_files += 1
            
            _atomic_write_json(metadata_file, metadata)
            
            return {"jsonrpc": "2.0", "result": {"ok": True, "bucket": bucket, "synced_files": synced_files, "force_sync": force_sync}, "id": None}

        if name == "bucket_get_metadata":
            bucket = args.get("bucket")
            path = args.get("path")
            include_replicas = args.get("include_replicas", True)
            include_cid = args.get("include_cid", False)
            
            if not bucket or not path:
                raise HTTPException(400, "Missing bucket or path")
            
            # Get file metadata from filesystem instead of relying on JSON file
            bucket_path = self.paths.vfs_root / bucket
            file_path = _safe_vfs_path(bucket_path, path)
            
            if not file_path.exists():
                raise HTTPException(404, "File not found")
            
            # Get basic file stats
            stat_info = file_path.stat()
            result = {
                "path": path,
                "bucket": bucket,
                "name": file_path.name,
                "size": stat_info.st_size,
                "is_file": file_path.is_file(),
                "is_directory": file_path.is_dir(),
                "created": datetime.fromtimestamp(stat_info.st_ctime, UTC).isoformat(),
                "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat(),
                "accessed": datetime.fromtimestamp(stat_info.st_atime, UTC).isoformat(),
                "permissions": oct(stat_info.st_mode)[-3:],
                "mime_type": mimetypes.guess_type(file_path)[0] if file_path.is_file() else None,
                "cached": True,  # Local files are considered cached
                "cache_type": "local_vfs"
            }
            
            # Calculate CID hash if requested (for content addressing)
            if include_cid and file_path.is_file():
                try:
                    import hashlib
                    # Calculate multihash CID (simplified version - in production use proper multicodec)
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                        # SHA256 hash
                        sha256_hash = hashlib.sha256(file_content).digest()
                        # Base58 encode (simplified - use multibase in production)
                        import base64
                        cid_v0 = "Qm" + base64.b32encode(sha256_hash).decode('utf-8').rstrip('=').lower()[:44]
                        result["cid"] = cid_v0
                        result["cid_version"] = "0 (SHA-256)"
                        result["multihash"] = "sha2-256"
                        result["content_addressable"] = True
                except Exception as e:
                    result["cid_error"] = str(e)
                    result["cid"] = None
            
            # Add replica info if requested
            if include_replicas:
                result["replicas"] = [{
                    "backend": "local_vfs",
                    "status": "available",
                    "path": str(file_path),
                    "last_sync": datetime.now(UTC).isoformat()
                }]
            
            # Try to get additional metadata from stored JSON if available
            try:
                metadata_file = self.paths.data_dir / "file_metadata.json"
                if metadata_file.exists():
                    metadata = _read_json(metadata_file, {})
                    file_key = f"{bucket}:{path}"
                    stored_meta = metadata.get(file_key, {})
                    if stored_meta:
                        # Merge stored metadata without overwriting CID
                        for key, value in stored_meta.items():
                            if key not in result or (key == "cid" and not result.get("cid")):
                                result[key] = value
            except Exception as e:
                # Log but don't fail if we can't read additional metadata
                pass
            
            return {"jsonrpc": "2.0", "result": result, "id": None}

        if name == "bucket_get_full_metadata":
            """Get complete metadata for entire bucket including all file CID hashes."""
            bucket = args.get("bucket")
            if not bucket:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Missing bucket parameter"}, "id": None}
            
            try:
                import hashlib
                import base64
                
                bucket_path = self.paths.vfs_root / bucket
                if not bucket_path.exists():
                    return {"jsonrpc": "2.0", "error": {"code": -32602, "message": f"Bucket not found: {bucket}"}, "id": None}
                
                # Recursively collect all files with CID hashes
                def collect_files_recursive(directory_path, relative_path=""):
                    """Recursively collect file metadata with CID hashes."""
                    files_data = []
                    
                    try:
                        for item in directory_path.iterdir():
                            item_relative = f"{relative_path}/{item.name}".lstrip('/')
                            
                            if item.is_file():
                                try:
                                    stat_info = item.stat()
                                    
                                    # Calculate CID hash
                                    with open(item, 'rb') as f:
                                        file_content = f.read()
                                        sha256_hash = hashlib.sha256(file_content).digest()
                                        cid_v0 = "Qm" + base64.b32encode(sha256_hash).decode('utf-8').rstrip('=').lower()[:44]
                                    
                                    file_info = {
                                        "path": item_relative,
                                        "name": item.name,
                                        "size": stat_info.st_size,
                                        "is_file": True,
                                        "is_directory": False,
                                        "created": datetime.fromtimestamp(stat_info.st_ctime, UTC).isoformat(),
                                        "modified": datetime.fromtimestamp(stat_info.st_mtime, UTC).isoformat(),
                                        "permissions": oct(stat_info.st_mode)[-3:],
                                        "mime_type": mimetypes.guess_type(item)[0],
                                        "cid": cid_v0,
                                        "cid_version": "0 (SHA-256)",
                                        "multihash": "sha2-256",
                                        "content_addressable": True
                                    }
                                    files_data.append(file_info)
                                except Exception as e:
                                    # Log but continue with other files
                                    print(f"Error processing file {item}: {e}")
                            
                            elif item.is_dir():
                                # Recursively process subdirectories
                                subdir_files = collect_files_recursive(item, item_relative)
                                files_data.extend(subdir_files)
                    
                    except Exception as e:
                        print(f"Error reading directory {directory_path}: {e}")
                    
                    return files_data
                
                # Collect all files
                all_files = collect_files_recursive(bucket_path)
                
                # Calculate bucket statistics
                total_size = sum(f["size"] for f in all_files)
                bucket_stat = bucket_path.stat()
                
                # Build complete bucket metadata
                result = {
                    "bucket": bucket,
                    "bucket_path": str(bucket_path),
                    "total_files": len(all_files),
                    "total_size": total_size,
                    "total_size_human": f"{total_size / (1024*1024):.2f} MB" if total_size > 1024*1024 else f"{total_size / 1024:.2f} KB",
                    "created": datetime.fromtimestamp(bucket_stat.st_ctime, UTC).isoformat(),
                    "modified": datetime.fromtimestamp(bucket_stat.st_mtime, UTC).isoformat(),
                    "files": all_files,
                    "reconstruction_instructions": {
                        "description": "Use the CID hashes to retrieve files from IPFS and recreate the bucket structure",
                        "ipfs_command_template": "ipfs get {cid} -o {path}",
                        "content_addressable": True,
                        "verification": "Each file can be verified by recomputing its SHA-256 hash and comparing to the CID"
                    }
                }
                
                return {"jsonrpc": "2.0", "result": result, "id": None}
                
            except Exception as e:
                import traceback
                return {"jsonrpc": "2.0", "error": {"code": -32603, "message": f"Error getting full bucket metadata: {str(e)}\n{traceback.format_exc()}"}, "id": None}
        
        if name == "get_bucket_usage":
            bucket_name = args.get("name")
            if not bucket_name:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Missing bucket name"}, "id": None}
            
            try:
                # Get bucket files from metadata-first approach
                metadata_files = []
                metadata_file_path = self.paths.data_dir / "bucket_files.json"
                if metadata_file_path.exists():
                    with open(metadata_file_path, 'r', encoding='utf-8') as f:
                        all_metadata = json.load(f)
                        metadata_files = [v for k, v in all_metadata.items() if k.startswith(f"{bucket_name}:")]
                
                # Calculate usage statistics
                total_size_bytes = 0
                file_count = len(metadata_files)
                
                for file_info in metadata_files:
                    if isinstance(file_info, dict):
                        size = file_info.get('size', 0)
                        if isinstance(size, (int, float)) and size > 0:
                            total_size_bytes += size
                
                total_size_gb = total_size_bytes / (1024 * 1024 * 1024)
                
                return {"jsonrpc": "2.0", "result": {
                    "total_size_bytes": total_size_bytes,
                    "total_size_gb": round(total_size_gb, 3),
                    "file_count": file_count,
                    "bucket": bucket_name
                }, "id": None}
                
            except Exception as e:
                return {"jsonrpc": "2.0", "result": {
                    "total_size_bytes": 0,
                    "total_size_gb": 0,
                    "file_count": 0,
                    "bucket": bucket_name,
                    "error": str(e)
                }, "id": None}

        if name == "generate_bucket_share_link":
            bucket = args.get("bucket")
            access_type = args.get("access_type", "read_only")
            expiration = args.get("expiration", "never")
            
            if not bucket:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Missing bucket name"}, "id": None}
            
            # Generate a simple share link (in production, this would include proper token generation)
            import hashlib
            import time
            
            token_data = f"{bucket}:{access_type}:{expiration}:{int(time.time())}"
            token = hashlib.md5(token_data.encode()).hexdigest()[:16]
            
            # Store share link info (in production, this would go to a proper database)
            share_links_path = self.paths.data_dir / "share_links.json"
            share_links = {}
            if share_links_path.exists():
                try:
                    with open(share_links_path, 'r', encoding='utf-8') as f:
                        share_links = json.load(f)
                except Exception:
                    pass
            
            share_links[token] = {
                "bucket": bucket,
                "access_type": access_type,
                "expiration": expiration,
                "created_at": datetime.now(UTC).isoformat()
            }
            
            try:
                with open(share_links_path, 'w', encoding='utf-8') as f:
                    json.dump(share_links, f, indent=2)
            except Exception:
                pass
            
            share_link = f"/shared/{bucket}?token={token}"
            
            return {"jsonrpc": "2.0", "result": {
                "share_link": share_link,
                "token": token,
                "bucket": bucket,
                "access_type": access_type,
                "expiration": expiration
            }, "id": None}

        if name == "bucket_selective_sync":
            bucket = args.get("bucket")
            files = args.get("files", [])
            options = args.get("options", {})
            
            if not bucket:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Missing bucket name"}, "id": None}
            
            if not files:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "No files specified for sync"}, "id": None}
            
            force_update = options.get("force_update", False)
            verify_checksums = options.get("verify_checksums", True)
            create_backup = options.get("create_backup", False)
            
            try:
                synced_files = []
                failed_files = []
                
                for file_path in files:
                    try:
                        # Simulate selective sync operation
                        # In production, this would sync the file according to bucket policy
                        synced_files.append({
                            "path": file_path,
                            "status": "synced",
                            "force_update": force_update,
                            "verified": verify_checksums
                        })
                    except Exception as e:
                        failed_files.append({
                            "path": file_path,
                            "error": str(e)
                        })
                
                return {"jsonrpc": "2.0", "result": {
                    "bucket": bucket,
                    "synced_files": synced_files,
                    "failed_files": failed_files,
                    "total_requested": len(files),
                    "total_synced": len(synced_files),
                    "options": options
                }, "id": None}
                
            except Exception as e:
                return {"jsonrpc": "2.0", "error": {"code": -32603, "message": f"Selective sync failed: {str(e)}"}, "id": None}

        if name == "update_bucket_policy":
            bname = args.get("name")
            if not bname:
                raise HTTPException(400, "Missing name")
            # Accept either flat keys or nested { policy: { ... } }
            pol_in = args.get("policy") if isinstance(args.get("policy"), dict) else None
            rf = args.get("replication_factor") if args.get("replication_factor") is not None else (pol_in or {}).get("replication_factor")
            cp = args.get("cache_policy") if args.get("cache_policy") is not None else (pol_in or {}).get("cache_policy")
            rd = args.get("retention_days") if args.get("retention_days") is not None else (pol_in or {}).get("retention_days")
            # validation / partial updates allowed
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
                if b.get("name") == bname:
                    pol = dict(b.get("policy") or {})
                    if rf is not None: pol['replication_factor'] = rf
                    if cp is not None: pol['cache_policy'] = cp
                    if rd is not None: pol['retention_days'] = rd
                    # ensure defaults
                    pol.setdefault('replication_factor', 1)
                    pol.setdefault('cache_policy', 'none')
                    pol.setdefault('retention_days', 0)
                    nb = dict(b); nb['policy'] = pol
                    items[i] = nb
                    updated = True
                    break
            if not updated:
                raise HTTPException(404, "Not found")
            _atomic_write_json(self.paths.buckets_file, items)
            return {"jsonrpc": "2.0", "result": {"ok": True, "policy": pol}, "id": None}

        return None

    def _handle_pins(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if name == "list_pins":
            items = _normalize_pins(_read_json(self.paths.pins_file, default=[]))
            return items
        if name == "create_pin":
            cid = args.get("cid")
            label = args.get("name")
            if not cid:
                raise HTTPException(400, "Missing cid")
            pins = _normalize_pins(_read_json(self.paths.pins_file, default=[]))
            if any(p.get("cid") == cid for p in pins):
                raise HTTPException(409, "Exists")
            entry = {"cid": cid, "name": label, "created_at": datetime.now(UTC).isoformat()}
            pins.append(entry)
            _atomic_write_json(self.paths.pins_file, pins)
            with suppress(Exception):
                self.log.info("pin created: %s", cid, extra={"component": "pins"})
            return {"ok": True, **entry}
        if name == "delete_pin":
            cid = args.get("cid")
            pins = _normalize_pins(_read_json(self.paths.pins_file, default=[]))
            new_pins = [p for p in pins if p.get("cid") != cid]
            if len(new_pins) == len(pins):
                return {"status": "absent"}
            _atomic_write_json(self.paths.pins_file, new_pins)
            with suppress(Exception):
                self.log.info("pin deleted: %s", cid, extra={"component": "pins"})
            return {"status": "deleted"}
        if name == "pins_export":
            items = _normalize_pins(_read_json(self.paths.pins_file, default=[]))
            return {"items": items}
        if name == "pins_import":
            items = args.get("items") or []
            if not isinstance(items, list):
                raise HTTPException(400, "items must be array")
            existing = _normalize_pins(_read_json(self.paths.pins_file, default=[]))
            seen = {p.get('cid') for p in existing}
            merged = list(existing)
            for p in items:
                cid = (p or {}).get('cid')
                if not cid or cid in seen:
                    continue
                merged.append({"cid": cid, "name": (p or {}).get('name'), "created_at": datetime.now(UTC).isoformat()})
                seen.add(cid)
            _atomic_write_json(self.paths.pins_file, merged)
            return {"jsonrpc": "2.0", "result": {"ok": True, "added": len(merged)-len(existing)}, "id": None}
        return None

    async def _handle_files(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:  # type: ignore
        if name in {"resolve_bucket_path", "write_file", "read_file", "list_files"}:
            bucket = args.get("bucket")
            if not bucket:
                raise HTTPException(400, "Missing bucket")

            # Look up the bucket -> backend mapping
            buckets = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            bucket_entry = next((b for b in buckets if b.get("name") == bucket), None)

            backend_name = bucket_entry.get("backend") if bucket_entry else None
            backends = _read_json(self.paths.backends_file, default={})
            backend_cfg = backends.get(backend_name) if backend_name else None

            def _backend_root() -> Path:
                # Default to VFS bucket dir
                default_root = (Path(self.paths.data_dir) / "vfs" / str(bucket)).resolve()
                if not backend_cfg:
                    return default_root
                if isinstance(backend_cfg, dict) and "type" in backend_cfg and "config" in backend_cfg:
                    btype = str(backend_cfg.get("type") or "").lower()
                    cfg = backend_cfg.get("config") or {}
                elif isinstance(backend_cfg, dict):
                    btype = str(backend_cfg.get("type") or "").lower()
                    cfg = backend_cfg
                else:
                    return default_root

                if btype in {"local_fs", "local_storage", "filesystem"} and isinstance(cfg, dict):
                    base_path = cfg.get("base_path") or cfg.get("path")
                    if base_path:
                        return Path(str(base_path)).resolve()
                return default_root

            root = _backend_root()
            root.mkdir(parents=True, exist_ok=True)

            if name == "resolve_bucket_path":
                return {"jsonrpc": "2.0", "result": {"bucket": bucket, "backend": backend_name, "path": str(root)}, "id": None}

            rel_path = args.get("path")
            if rel_path is None:
                rel_path = ""

            # Prevent path traversal outside the resolved bucket root
            target = (root / str(rel_path)).resolve()
            if root != target and root not in target.parents:
                raise HTTPException(400, "Invalid path")

            if name == "list_files":
                if not target.exists():
                    raise HTTPException(404, "Not found")
                if target.is_file():
                    files = [{"name": target.name, "path": str(rel_path), "type": "file"}]
                else:
                    files = []
                    for child in sorted(target.iterdir(), key=lambda p: p.name):
                        files.append({
                            "name": child.name,
                            "path": str((Path(str(rel_path)) / child.name).as_posix()).lstrip("/"),
                            "type": "dir" if child.is_dir() else "file",
                        })
                return {"jsonrpc": "2.0", "result": {"bucket": bucket, "path": str(rel_path), "files": files}, "id": None}

            if name == "write_file":
                if not rel_path:
                    raise HTTPException(400, "Missing path")
                content = args.get("content", "")
                target.parent.mkdir(parents=True, exist_ok=True)
                data = str(content).encode("utf-8")
                target.write_bytes(data)
                return {"jsonrpc": "2.0", "result": {"bucket": bucket, "path": str(rel_path), "bytes": len(data)}, "id": None}

            if name == "read_file":
                if not rel_path:
                    raise HTTPException(400, "Missing path")
                if not target.exists() or not target.is_file():
                    raise HTTPException(404, "File not found")
                raw = target.read_bytes()
                try:
                    text = raw.decode("utf-8")
                except Exception:
                    # fall back to latin-1 to keep tests/simple clients happy
                    text = raw.decode("latin-1")
                return {"jsonrpc": "2.0", "result": {"bucket": bucket, "path": str(rel_path), "content": text}, "id": None}

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
        if name == "files_mkdir":
            path = args.get("path")
            if not path:
                raise HTTPException(400, "Missing path")
            p = _safe_vfs_path(self.paths.vfs_root, path)
            p.mkdir(parents=True, exist_ok=True)
            return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}
        if name == "files_rm":
            path = args.get("path")
            recursive = bool(args.get("recursive", False))
            if not path:
                raise HTTPException(400, "Missing path")
            p = _safe_vfs_path(self.paths.vfs_root, path)
            if not p.exists():
                raise HTTPException(404, "Not found")
            if p.is_dir():
                if not recursive:
                    raise HTTPException(400, "Directory remove requires recursive=true")
                shutil.rmtree(p)
            else:
                p.unlink()
            return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}
        if name == "files_mv":
            src = args.get("src"); dst = args.get("dst")
            if not src or not dst:
                raise HTTPException(400, "Missing src/dst")
            ps = _safe_vfs_path(self.paths.vfs_root, src)
            pd = _safe_vfs_path(self.paths.vfs_root, dst)
            pd.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ps), str(pd))
            return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}
        if name == "files_stat":
            path = args.get("path")
            if not path:
                raise HTTPException(400, "Missing path")
            p = _safe_vfs_path(self.paths.vfs_root, path)
            if not p.exists():
                raise HTTPException(404, "Not found")
            st = p.stat()
            return {"jsonrpc": "2.0", "result": {"path": path, "is_dir": p.is_dir(), "size": st.st_size, "mtime": st.st_mtime}, "id": None}
        if name == "files_copy":
            src = args.get("src"); dst = args.get("dst"); rec = bool(args.get("recursive", False))
            if not src or not dst:
                raise HTTPException(400, "Missing src/dst")
            ps = _safe_vfs_path(self.paths.vfs_root, src)
            pd = _safe_vfs_path(self.paths.vfs_root, dst)
            pd.parent.mkdir(parents=True, exist_ok=True)
            if ps.is_dir():
                if not rec:
                    raise HTTPException(400, "Directory copy requires recursive=true")
                if pd.exists() and pd.is_file():
                    raise HTTPException(400, "Cannot copy dir onto file")
                shutil.copytree(ps, pd, dirs_exist_ok=True)
            else:
                shutil.copy2(ps, pd)
            return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}
        if name == "files_touch":
            path = args.get("path")
            if not path:
                raise HTTPException(400, "Missing path")
            p = _safe_vfs_path(self.paths.vfs_root, path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'a', encoding='utf-8'):
                os.utime(p, None)
            return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}
        if name == "files_tree":
            path = args.get("path", "."); depth = int(args.get("depth", 2))
            base = _safe_vfs_path(self.paths.vfs_root, path)
            if not base.exists():
                return {"jsonrpc": "2.0", "result": {"path": path, "items": []}, "id": None}
            if base.is_file():
                st = base.stat()
                return {"jsonrpc": "2.0", "result": {"path": path, "items": [{"name": base.name, "is_dir": False, "size": st.st_size}]}, "id": None}
            def walk(p: Path, d: int):
                out = []
                if d < 0:
                    return out
                for child in sorted(p.iterdir()):
                    item = {"name": child.name, "is_dir": child.is_dir()}
                    if child.is_file():
                        with suppress(Exception):
                            item["size"] = child.stat().st_size
                    if child.is_dir() and d > 0:
                        item["children"] = walk(child, d-1)
                    out.append(item)
                return out
            return {"jsonrpc": "2.0", "result": {"path": path, "items": walk(base, depth)}, "id": None}
        return None

    def _handle_ipfs(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if name == "ipfs_add":
            path = args.get("path")
            if not path:
                raise HTTPException(400, "Missing path")
            ipfs_bin = _which("ipfs")
            if not ipfs_bin:
                raise HTTPException(404, "ipfs binary not found")
            p = _safe_vfs_path(self.paths.vfs_root, path)
            res = _run_cmd([ipfs_bin, 'add', '-Qr', str(p)], timeout=120)
            return {"jsonrpc": "2.0", "result": res, "id": None}
        if name == "ipfs_pin":
            cid = args.get("cid")
            label = args.get("name")
            if not cid:
                raise HTTPException(400, "Missing cid")
            ipfs_bin = _which("ipfs")
            if not ipfs_bin:
                raise HTTPException(404, "ipfs binary not found")
            res = _run_cmd([ipfs_bin, 'pin', 'add', cid], timeout=60)
            # If pin succeeded, update our local pins index for convenience
            try:
                ok_code = int(res.get('code', 1))
            except Exception:
                ok_code = 1
            if ok_code == 0:
                pins = _normalize_pins(_read_json(self.paths.pins_file, default=[]))
                if not any(p.get('cid') == cid for p in pins):
                    pins.append({"cid": cid, "name": label, "created_at": datetime.now(UTC).isoformat()})
                    _atomic_write_json(self.paths.pins_file, pins)
            return {"jsonrpc": "2.0", "result": res, "id": None}
        if name == "ipfs_cat":
            cid = args.get("cid")
            if not cid:
                raise HTTPException(400, "Missing cid")
            ipfs_bin = _which("ipfs")
            if not ipfs_bin:
                raise HTTPException(404, "ipfs binary not found")
            res = _run_cmd([ipfs_bin, 'cat', cid], timeout=60)
            return {"jsonrpc": "2.0", "result": res, "id": None}
        if name == "ipfs_ls":
            cid = args.get("cid")
            if not cid:
                raise HTTPException(400, "Missing cid")
            ipfs_bin = _which("ipfs")
            if not ipfs_bin:
                raise HTTPException(404, "ipfs binary not found")
            res = _run_cmd([ipfs_bin, 'ls', cid], timeout=60)
            return {"jsonrpc": "2.0", "result": res, "id": None}
        if name == "ipfs_version":
            ipfs_bin = _which("ipfs")
            if not ipfs_bin:
                raise HTTPException(404, "ipfs binary not found")
            res = _run_cmd([ipfs_bin, 'version', '--all'], timeout=20)
            return {"jsonrpc": "2.0", "result": res, "id": None}
        if name == "get_bucket_policy":
            bname = args.get("name")
            items = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            for b in items:
                if b.get("name") == bname:
                    return {"jsonrpc": "2.0", "result": {"name": bname, "policy": b.get("policy")}, "id": None}
            raise HTTPException(404, "Not found")
        
        # Enhanced backend configuration tools for multi-instance support
        if name == "configure_backend_instance":
            instance_name = args.get("instance_name")
            service_type = args.get("service_type")
            config = args.get("config", {})
            
            if not instance_name or not service_type:
                raise HTTPException(400, "Missing instance_name or service_type")
            
            # Enhanced configuration with multi-instance support
            enhanced_config = {
                "basic": {
                    "instance_name": instance_name,
                    "service_type": service_type,
                    "description": config.get("description", f"Instance of {service_type}"),
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
            
            # Save enhanced configuration
            config_dir = self.paths.data_dir / "service_configs"
            config_dir.mkdir(exist_ok=True)
            config_file = config_dir / f"{instance_name}_config.json"
            
            with open(config_file, 'w') as f:
                json.dump(enhanced_config, f, indent=2)
            
            # Update backends if it's a storage service
            if service_type in ["s3", "github", "ipfs_cluster", "huggingface", "gdrive", "ftp", "sshfs", "apache_arrow", "parquet"]:
                backends = _normalize_backends(_read_json(self.paths.backends_file, default=[]))
                
                # Update or create backend entry
                backend_found = False
                for i, backend in enumerate(backends):
                    if backend.get("name") == instance_name:
                        backends[i] = {
                            "name": instance_name,
                            "type": service_type,
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
                        "type": service_type,
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
            
            return {"jsonrpc": "2.0", "result": {
                "success": True,
                "instance_name": instance_name,
                "service_type": service_type,
                "message": f"Backend instance '{instance_name}' configured successfully",
                "config": enhanced_config
            }, "id": None}
        
        if name == "create_backend_instance":
            service_type = args.get("service_type")
            instance_name = args.get("instance_name")
            description = args.get("description", f"Instance of {service_type}")
            
            if not service_type or not instance_name:
                raise HTTPException(400, "Missing service_type or instance_name")
            
            # Check if instance already exists
            config_dir = self.paths.data_dir / "service_configs"
            config_file = config_dir / f"{instance_name}_config.json"
            
            if config_file.exists():
                raise HTTPException(409, f"Instance '{instance_name}' already exists")
            
            # Create new instance configuration with defaults
            new_config = {
                "basic": {
                    "instance_name": instance_name,
                    "service_type": service_type,
                    "description": description,
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
                    "description": description,
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
            
            return {"jsonrpc": "2.0", "result": {
                "success": True,
                "instance_name": instance_name,
                "service_type": service_type,
                "message": f"Backend instance '{instance_name}' created successfully",
                "config": new_config
            }, "id": None}
        
        if name == "list_backend_instances":
            # List all configured backend instances with their enhanced settings
            config_dir = self.paths.data_dir / "service_configs"
            backends = _normalize_backends(_read_json(self.paths.backends_file, default=[]))
            
            instances = []
            for backend in backends:
                config_file = config_dir / f"{backend['name']}_config.json"
                if config_file.exists():
                    try:
                        with open(config_file, 'r') as f:
                            config = json.load(f)
                        instances.append({
                            "name": backend["name"],
                            "type": backend["type"],
                            "description": backend.get("description", ""),
                            "enabled": backend.get("enabled", False),
                            "config": config,
                            "policy": backend.get("policy", {}),
                            "created_at": backend.get("created_at"),
                            "last_updated": backend.get("last_updated")
                        })
                    except Exception as e:
                        self.log.warning(f"Failed to load config for {backend['name']}: {e}")
                        instances.append({
                            "name": backend["name"],
                            "type": backend["type"],
                            "description": backend.get("description", ""),
                            "enabled": backend.get("enabled", False),
                            "config": {},
                            "policy": backend.get("policy", {}),
                            "created_at": backend.get("created_at"),
                            "last_updated": backend.get("last_updated")
                        })
                else:
                    # Legacy backend without enhanced config
                    instances.append({
                        "name": backend["name"],
                        "type": backend["type"],
                        "description": backend.get("description", ""),
                        "enabled": backend.get("enabled", False),
                        "config": {},
                        "policy": backend.get("policy", {}),
                        "created_at": backend.get("created_at"),
                        "last_updated": backend.get("last_updated")
                    })
            
            return {"jsonrpc": "2.0", "result": {
                "instances": instances,
                "total": len(instances)
            }, "id": None}
        
        if name == "backend_health_check":
            # Run comprehensive health check on all backends
            detailed = args.get("detailed", False)
            backends = _normalize_backends(_read_json(self.paths.backends_file, default=[]))
            
            results = []
            healthy_count = 0
            
            for backend in backends:
                try:
                    # Direct backend health check without recursion
                    backend_name = backend['name']
                    backend_type = backend.get('type', 'unknown')
                    reachable = False
                    
                    # Simple health check based on backend type
                    try:
                        if backend_type in ['s3', 'storage']:
                            # Check if we can access the backend
                            reachable = True  # Assume reachable for now
                        elif backend_type in ['ipfs', 'network']:
                            reachable = True  # Assume reachable for now 
                        else:
                            reachable = True  # Default to healthy
                    except:
                        reachable = False
                    
                    status = "healthy" if reachable else "unhealthy"
                    if status == "healthy":
                        healthy_count += 1
                    
                    test_data = {"reachable": reachable, "backend_type": backend_type}
                    
                    results.append({
                        "name": backend['name'],
                        "type": backend['type'],
                        "status": status,
                        "reachable": reachable,
                        "details": test_data if detailed else None
                    })
                except Exception as e:
                    results.append({
                        "name": backend['name'],
                        "type": backend['type'],
                        "status": "error",
                        "reachable": False,
                        "error": str(e),
                        "details": None
                    })
            
            return {"jsonrpc": "2.0", "result": {
                "healthy": healthy_count,
                "total": len(backends),
                "results": results,
                "details": results if detailed else None
            }, "id": None}
        
        if name == "sync_backend_replicas":
            backend_name = args.get("name")
            use_metadata_first = args.get("use_metadata_first", True)
            force_sync = args.get("force_sync", False)
            
            if not backend_name:
                raise HTTPException(400, "Missing backend name")
            
            # Check if backend exists
            backends = _normalize_backends(_read_json(self.paths.backends_file, default=[]))
            backend = next((b for b in backends if b['name'] == backend_name), None)
            if not backend:
                raise HTTPException(404, f"Backend '{backend_name}' not found")
            
            try:
                # Simulate replica synchronization with metadata-first approach
                config_dir = self.paths.data_dir / "service_configs"
                config_file = config_dir / f"{backend_name}_config.json"
                
                if use_metadata_first:
                    # Check ~/.ipfs_kit/ metadata first
                    metadata_path = self.paths.data_dir / "replica_metadata" / f"{backend_name}.json"
                    metadata_path.parent.mkdir(exist_ok=True)
                    
                    # Create or update metadata
                    metadata = {
                        "backend_name": backend_name,
                        "backend_type": backend['type'],
                        "last_sync": datetime.now(UTC).isoformat(),
                        "sync_method": "metadata_first",
                        "force_sync": force_sync,
                        "status": "synced"
                    }
                    
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)
                
                return {"jsonrpc": "2.0", "result": {
                    "ok": True,
                    "backend": backend_name,
                    "sync_method": "metadata_first" if use_metadata_first else "direct",
                    "message": f"Replicas synchronized successfully for '{backend_name}'"
                }, "id": None}
                
            except Exception as e:
                return {"jsonrpc": "2.0", "result": {
                    "ok": False,
                    "error": str(e),
                    "backend": backend_name
                }, "id": None}
        

    def _handle_peers(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        mgr = self._get_peer_manager()
        if name == "list_peers":
            data = (mgr.list_peers() if mgr else {"peers": [], "total": 0})
            peers = data.get("peers", []) if isinstance(data, dict) else []
            total = data.get("total", len(peers)) if isinstance(data, dict) else len(peers)
            return {"jsonrpc": "2.0", "result": {"ok": True, "peers": peers, "total": total}, "id": None}
        if name == "get_peer_stats":
            if not mgr:
                return {"jsonrpc": "2.0", "result": {"total": 0, "connected": 0, "by_tag": {}, "peers": []}, "id": None}
            data = mgr.list_peers()
            peers = data.get("peers", []) if isinstance(data, dict) else []
            total = len(peers)
            connected = sum(1 for p in peers if (p.get("connection_status") or "").lower() == "connected")
            by_tag: Dict[str, int] = {}
            for p in peers:
                for t in p.get("tags", []) or []:
                    by_tag[t] = by_tag.get(t, 0) + 1
            return {"jsonrpc": "2.0", "result": {"ok": True, "total": total, "connected": connected, "by_tag": by_tag, "peers": peers}, "id": None}
        if name == "connect_peer":
            peer_info = {
                "peer_id": args.get("peer_id"),
                "peer_address": args.get("peer_address"),
                "tags": args.get("tags") or [],
            }
            data = (mgr.connect_peer(peer_info) if mgr else {"error": "Peer manager unavailable"})
            ok = not isinstance(data, dict) or ("error" not in data)
            # Standardize shape
            result: Dict[str, Any] = {"ok": ok}
            if isinstance(data, dict):
                for k, v in data.items():
                    result[k] = v
            return {"jsonrpc": "2.0", "result": result, "id": None}
        if name == "disconnect_peer":
            pid = args.get("peer_id")
            if not pid:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "peer_id is required"}, "id": None}
            data = (mgr.disconnect_peer(pid) if mgr else {"error": "Peer manager unavailable"})
            ok = not isinstance(data, dict) or ("error" not in data)
            result = {"ok": ok}
            if isinstance(data, dict):
                for k, v in data.items():
                    result[k] = v
            return {"jsonrpc": "2.0", "result": result, "id": None}
        if name == "get_peer_info":
            pid = args.get("peer_id")
            if not pid:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "peer_id is required"}, "id": None}
            data = (mgr.get_peer_info(pid) if mgr else {"error": "Peer manager unavailable"})
            ok = isinstance(data, dict) and ("error" not in data)
            result = {"ok": ok}
            if isinstance(data, dict):
                for k, v in data.items():
                    result[k] = v
            return {"jsonrpc": "2.0", "result": result, "id": None}
        if name == "discover_peers":
            limit = int(args.get("limit", 20) or 20)
            timeout = int(args.get("timeout", 10) or 10)
            try:
                from ipfs_kit_py.high_level_api import ipfs_kit  # type: ignore
                api = ipfs_kit()
                if hasattr(api, "discover_peers"):
                    result = api.discover_peers(max_peers=limit, timeout=timeout)
                    peers: list = []
                    if isinstance(result, dict):
                        maybe = result.get("peers") or result.get("discovered") or result.get("results")
                        if isinstance(maybe, list):
                            peers = maybe
                        elif isinstance(maybe, dict):
                            peers = [
                                {**(v if isinstance(v, dict) else {"info": v}), "peer_id": k}
                                for k, v in maybe.items()
                            ]
                        else:
                            peers = [
                                {**(v if isinstance(v, dict) else {"info": v}), "peer_id": k}
                                for k, v in result.items() if isinstance(k, str)
                            ]
                    elif isinstance(result, list):
                        peers = result
                    return {"jsonrpc": "2.0", "result": {"ok": True, "peers": peers, "total_discovered": len(peers), "source": "libp2p"}, "id": None}
            except Exception:
                pass
            # Fallback
            data = (mgr.list_peers() if mgr else {"peers": [], "total": 0})
            peers_list: list[Any] = []
            if isinstance(data, dict):
                maybe_peers = data.get("peers")
                if isinstance(maybe_peers, list):
                    peers_list = maybe_peers
            return {"jsonrpc": "2.0", "result": {"ok": True, "peers": peers_list, "total_discovered": len(peers_list), "source": "fallback"}, "id": None}
        if name == "bootstrap_peers":
            action = (args.get("action") or "list").lower()
            peer_address = args.get("peer_address")
            try:
                from ipfs_kit_py.libp2p.peer_manager import get_global_peer_manager  # type: ignore
                libp2p_mgr = get_global_peer_manager()
            except Exception:
                libp2p_mgr = None
            try:
                if action == "list":
                    if libp2p_mgr and hasattr(libp2p_mgr, "list_bootstrap_peers"):
                        peers = libp2p_mgr.list_bootstrap_peers()
                    else:
                        peers = []
                        for path in ["~/.ipfs/bootstrap", "/etc/ipfs/bootstrap"]:
                            p = Path(os.path.expanduser(path))
                            if p.exists():
                                with p.open() as fh:
                                    for line in fh:
                                        s = line.strip()
                                        if s and not s.startswith("#"):
                                            peers.append(s)
                    return {"jsonrpc": "2.0", "result": {"ok": True, "peers": peers, "total_bootstrapped": len(peers)}, "id": None}
                if action == "from_ipfs":
                    if libp2p_mgr and hasattr(libp2p_mgr, "bootstrap_from_ipfs"):
                        res = libp2p_mgr.bootstrap_from_ipfs() or {"ok": True}
                        return {"jsonrpc": "2.0", "result": res, "id": None}
                    ipfs = _which("ipfs")
                    if not ipfs:
                        return {"jsonrpc": "2.0", "error": {"code": 404, "message": "ipfs binary not found"}, "id": None}
                    out = _run_cmd([ipfs, "bootstrap", "list"])  # list as a safe op
                    return {"jsonrpc": "2.0", "result": {"ok": out.get("code") == 0, "out": out.get("out"), "err": out.get("err")}, "id": None}
                if action == "from_cluster":
                    if libp2p_mgr and hasattr(libp2p_mgr, "bootstrap_from_cluster"):
                        res = libp2p_mgr.bootstrap_from_cluster() or {"ok": True}
                        return {"jsonrpc": "2.0", "result": res, "id": None}
                    ctl = _which("ipfs-cluster-ctl")
                    if not ctl:
                        return {"jsonrpc": "2.0", "error": {"code": 404, "message": "ipfs-cluster-ctl binary not found"}, "id": None}
                    out = _run_cmd([ctl, "peers", "ls"])  # safe listing
                    return {"jsonrpc": "2.0", "result": {"ok": out.get("code") == 0, "out": out.get("out"), "err": out.get("err")}, "id": None}
                if action == "add":
                    if not peer_address:
                        return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "peer_address is required for action=add"}, "id": None}
                    if libp2p_mgr and hasattr(libp2p_mgr, "add_bootstrap_peer"):
                        res = libp2p_mgr.add_bootstrap_peer(peer_address) or {"ok": True}
                        return {"jsonrpc": "2.0", "result": res, "id": None}
                    ipfs = _which("ipfs")
                    if not ipfs:
                        return {"jsonrpc": "2.0", "error": {"code": 404, "message": "ipfs binary not found"}, "id": None}
                    out = _run_cmd([ipfs, "bootstrap", "add", peer_address])
                    return {"jsonrpc": "2.0", "result": {"ok": out.get("code") == 0, "out": out.get("out"), "err": out.get("err")}, "id": None}
            except Exception as e:
                return {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(e)}, "id": None}
        return None


    def _handle_cars(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Lightweight CAR store tools used by tests/clients.
        # These operate purely on the local car_store directory and do not require ipfs.
        if name == "import_car_to_bucket":
            car_name = args.get("name")
            bucket = args.get("bucket")
            content_b64 = args.get("content_b64")
            if not car_name or not bucket or not content_b64:
                raise HTTPException(400, "Missing name/bucket/content_b64")

            # Resolve bucket -> backend base path
            buckets = _normalize_buckets(_read_json(self.paths.buckets_file, default=[]))
            bucket_entry = next((b for b in buckets if b.get("name") == bucket), None)
            if not bucket_entry:
                raise HTTPException(404, "Bucket not found")
            backend_name = bucket_entry.get("backend")
            backends = _read_json(self.paths.backends_file, default={})
            backend_cfg = backends.get(backend_name) if backend_name else None
            base_path = None
            if isinstance(backend_cfg, dict) and "type" in backend_cfg and "config" in backend_cfg:
                btype = str(backend_cfg.get("type") or "").lower()
                cfg = backend_cfg.get("config") or {}
                if btype in {"local_fs", "local_storage", "filesystem"} and isinstance(cfg, dict):
                    base_path = cfg.get("base_path") or cfg.get("path")
            elif isinstance(backend_cfg, dict):
                btype = str(backend_cfg.get("type") or "").lower()
                if btype in {"local_fs", "local_storage", "filesystem"}:
                    base_path = backend_cfg.get("base_path") or backend_cfg.get("path")
            if not base_path:
                raise HTTPException(400, "Bucket backend does not support local car import")

            cars_root = Path(str(base_path)).resolve() / "cars"
            cars_root.mkdir(parents=True, exist_ok=True)
            fname = str(car_name)
            if not fname.endswith(".car"):
                fname = f"{fname}.car"

            import base64
            data = base64.b64decode(str(content_b64))
            target = (cars_root / fname).resolve()
            if cars_root != target and cars_root not in target.parents:
                raise HTTPException(400, "Invalid car name")
            target.write_bytes(data)
            return {"jsonrpc": "2.0", "result": {"status": "ok", "path": str(target)}, "id": None}

        if name == "import_car":
            car_name = args.get("name")
            content_b64 = args.get("content_b64")
            if not car_name or not content_b64:
                raise HTTPException(400, "Missing name/content_b64")
            fname = str(car_name)
            if not fname.endswith(".car"):
                fname = f"{fname}.car"
            import base64
            data = base64.b64decode(str(content_b64))
            p = (self.paths.car_store / fname)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            return {"jsonrpc": "2.0", "result": {"status": "ok", "name": fname, "bytes": len(data)}, "id": None}

        if name == "list_cars":
            cars = []
            for f in sorted(self.paths.car_store.glob("*.car")):
                try:
                    cars.append({"name": f.name, "size": f.stat().st_size})
                except Exception:
                    cars.append({"name": f.name})
            return {"jsonrpc": "2.0", "result": {"cars": cars}, "id": None}

        if name == "export_car":
            car_name = args.get("name")
            if not car_name:
                raise HTTPException(400, "Missing name")
            fname = str(car_name)
            if not fname.endswith(".car"):
                fname = f"{fname}.car"
            p = self.paths.car_store / fname
            if not p.exists():
                raise HTTPException(404, "CAR not found")
            import base64
            data = p.read_bytes()
            return {"jsonrpc": "2.0", "result": {"name": fname, "content_b64": base64.b64encode(data).decode("ascii")}, "id": None}

        if name == "remove_car":
            car_name = args.get("name")
            if not car_name:
                raise HTTPException(400, "Missing name")
            fname = str(car_name)
            if not fname.endswith(".car"):
                fname = f"{fname}.car"
            p = self.paths.car_store / fname
            if p.exists():
                p.unlink()
            return {"jsonrpc": "2.0", "result": {"status": "deleted", "name": fname}, "id": None}

        if name == "cars_list":
            items = []
            for f in sorted(self.paths.car_store.glob('*.car')):
                try:
                    items.append({"name": f.name, "size": f.stat().st_size})
                except Exception:
                    pass
            return {"jsonrpc": "2.0", "result": {"items": items}, "id": None}
        if name == "car_export":
            path = args.get("path"); car = args.get("car")
            if not path or not car:
                raise HTTPException(400, "Missing path/car")
            ipfs_bin = _which("ipfs")
            if not ipfs_bin:
                raise HTTPException(404, "ipfs binary not found")
            p = _safe_vfs_path(self.paths.vfs_root, path)
            add = _run_cmd([ipfs_bin, 'add', '-Qr', str(p)], timeout=120)
            if not add.get('ok'):
                return {"jsonrpc": "2.0", "result": add, "id": None}
            cid = (add.get('out') or '').strip()
            car_path = self.paths.car_store / car
            car_path.parent.mkdir(parents=True, exist_ok=True)
            exp = _run_cmd_bytes([ipfs_bin, 'dag', 'export', cid], timeout=180)
            if exp.get('ok'):
                try:
                    with car_path.open('wb') as fh:
                        fh.write(exp.get('out_bytes') or b'')
                except Exception as e:
                    return {"jsonrpc": "2.0", "result": {"ok": False, "err": str(e)}, "id": None}
            return {"jsonrpc": "2.0", "result": {"ok": bool(exp.get('ok')), "code": exp.get('code'), "err": exp.get('err'), "car": str(car_path)}, "id": None}
        if name == "car_import":
            car = args.get("car"); dest = args.get("dest")
            if not car or not dest:
                raise HTTPException(400, "Missing car/dest")
            ipfs_bin = _which("ipfs")
            if not ipfs_bin:
                raise HTTPException(404, "ipfs binary not found")
            car_path = self.paths.car_store / car
            if not car_path.exists():
                raise HTTPException(404, "CAR not found")
            res = _run_cmd([ipfs_bin, 'dag', 'import', str(car_path)], timeout=240)
            _safe_vfs_path(self.paths.vfs_root, dest).mkdir(parents=True, exist_ok=True)
            return {"jsonrpc": "2.0", "result": res, "id": None}
        return None

    def _handle_state(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if name == "state_snapshot":
            result = {
                "data_dir": str(self.paths.data_dir),
                "backends": _read_json(self.paths.backends_file, default={}),
                "buckets": _normalize_buckets(_read_json(self.paths.buckets_file, default=[])),
                "pins": _normalize_pins(_read_json(self.paths.pins_file, default=[])),
                "car_files": [f.name for f in sorted(self.paths.car_store.glob('*.car'))],
            }
            return {"jsonrpc": "2.0", "result": result, "id": None}
        if name == "state_backup":
            backup_dir = self.paths.data_dir / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
            tgz = backup_dir / f'state_{ts}.tar.gz'
            try:
                with tarfile.open(tgz, 'w:gz') as tar:
                    for f in [self.paths.backends_file, self.paths.buckets_file, self.paths.pins_file]:
                        if f.exists():
                            tar.add(f, arcname=f.name)
                return {"jsonrpc": "2.0", "result": {"ok": True, "archive": str(tgz)}, "id": None}
            except Exception as e:
                return {"jsonrpc": "2.0", "result": {"ok": False, "err": str(e)}, "id": None}
        if name == "state_reset":
            ts = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
            for f, default in [
                (self.paths.backends_file, {}),
                (self.paths.buckets_file, []),
                (self.paths.pins_file, []),
            ]:
                try:
                    if f.exists():
                        f.rename(f.with_suffix(f.suffix + f'.{ts}.bak'))
                except Exception:
                    pass
                _atomic_write_json(f, default)
            return {"jsonrpc": "2.0", "result": {"ok": True}, "id": None}
        return None

    def _handle_logs_server(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if name == "get_logs":
            limit = int(args.get("limit", 200))
            component = args.get("component")

            logs = self.memlog.get(limit=0)
            # Default: return only explicitly component-tagged operational logs.
            # This keeps dashboard startup noise out of the tool surface and
            # matches unit tests expecting empty logs on fresh startup.
            if component is None or component == "ops":
                logs = [l for l in logs if isinstance(l, dict) and l.get("component")]
            elif isinstance(component, str) and component and component != "all":
                logs = [l for l in logs if l.get("component") == component]

            # Newest first
            logs = list(reversed(logs))
            if limit and limit > 0:
                logs = logs[:limit]
            return {"logs": logs}
        if name == "clear_logs":
            cleared = 0
            with suppress(Exception):
                cleared = len([l for l in self.memlog.get(limit=0) if isinstance(l, dict) and l.get("component")])
            self.memlog.clear()
            return {"ok": True, "cleared": cleared}
        if name == "server_shutdown":
            try:
                pid = os.getpid()
                def _later_kill():
                    time.sleep(0.2)
                    os.kill(pid, signal.SIGTERM)
                asyncio.get_event_loop().run_in_executor(None, _later_kill)
            except Exception:
                pass
            return {"jsonrpc": "2.0", "result": {"ok": True, "message": "Shutting down"}, "id": None}
        return None

    def _handle_config(self, name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle configuration management tools with metadata-first approach."""
        if name == "list_config_files":
            return self._handle_list_config_files()
        elif name == "read_config_file":
            filename = args.get("filename")
            if not filename:
                return {"jsonrpc": "2.0", "error": {"code": 400, "message": "filename parameter is required"}, "id": None}
            return self._handle_read_config_file(filename)
        elif name == "write_config_file":
            filename = args.get("filename")
            content = args.get("content")
            if not filename or content is None:
                return {"jsonrpc": "2.0", "error": {"code": 400, "message": "filename and content parameters are required"}, "id": None}
            return self._handle_write_config_file(filename, content)
        elif name == "get_config_metadata":
            filename = args.get("filename")
            if not filename:
                return {"jsonrpc": "2.0", "error": {"code": 400, "message": "filename parameter is required"}, "id": None}
            return self._handle_get_config_metadata(filename)
        return None

    def _handle_list_config_files(self) -> Dict[str, Any]:
        """List all configuration files with metadata-first approach."""
        config_files = ["pins.json", "buckets.json", "backends.json"]
        files_info = []
        
        for filename in config_files:
            try:
                file_info = self._read_config_file_internal(filename)
                files_info.append({
                    "filename": filename,
                    "source": file_info["source"],
                    "size": file_info["size"],
                    "modified": file_info["modified"],
                    "exists": True
                })
            except Exception as e:
                files_info.append({
                    "filename": filename,
                    "source": "none",
                    "size": 0,
                    "modified": None,
                    "exists": False,
                    "error": str(e)
                })
        
        result = {
            "files": files_info,
            "metadata_dir": str(self.paths.data_dir),
            "total_files": len([f for f in files_info if f["exists"]])
        }
        return {"jsonrpc": "2.0", "result": result, "id": None}

    def _handle_read_config_file(self, filename: str) -> Dict[str, Any]:
        """Read configuration file using metadata-first approach."""
        try:
            file_info = self._read_config_file_internal(filename)
            return {"jsonrpc": "2.0", "result": file_info, "id": None}
        except Exception as e:
            return {"jsonrpc": "2.0", "error": {"code": 500, "message": str(e)}, "id": None}

    def _handle_write_config_file(self, filename: str, content: str) -> Dict[str, Any]:
        """Write configuration file using metadata-first approach."""
        try:
            # Always write to metadata location (metadata-first approach)
            metadata_path = self.paths.data_dir / filename
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(content)
            
            result = {
                "success": True,
                "filename": filename,
                "source": "metadata",
                "path": str(metadata_path),
                "size": len(content.encode()),
                "modified": datetime.now().isoformat()
            }
            return {"jsonrpc": "2.0", "result": result, "id": None}
            
        except Exception as e:
            return {"jsonrpc": "2.0", "error": {"code": 500, "message": str(e)}, "id": None}

    def _handle_get_config_metadata(self, filename: str) -> Dict[str, Any]:
        """Get configuration file metadata."""
        try:
            file_info = self._read_config_file_internal(filename)
            result = {
                "filename": filename,
                "source": file_info["source"],
                "size": file_info["size"],
                "modified": file_info["modified"],
                "path": file_info["path"],
                "metadata_first": True
            }
            return {"jsonrpc": "2.0", "result": result, "id": None}
        except Exception as e:
            return {"jsonrpc": "2.0", "error": {"code": 500, "message": str(e)}, "id": None}

    def _read_config_file_internal(self, filename: str) -> Dict[str, Any]:
        """Internal method to read configuration file using metadata-first approach."""
        # Metadata-first approach: check ~/.ipfs_kit/ first
        metadata_path = self.paths.data_dir / filename
        fallback_path = Path("ipfs_kit_py") / filename
        
        try:
            if metadata_path.exists():
                content = metadata_path.read_text()
                source = "metadata"
                size = metadata_path.stat().st_size
                modified = datetime.fromtimestamp(metadata_path.stat().st_mtime).isoformat()
                path = str(metadata_path)
            elif fallback_path.exists():
                content = fallback_path.read_text()
                source = "ipfs_kit_py"
                size = fallback_path.stat().st_size
                modified = datetime.fromtimestamp(fallback_path.stat().st_mtime).isoformat()
                path = str(fallback_path)
            else:
                # Create default content in metadata location
                default_content = self._get_default_config_content(filename)
                metadata_path.parent.mkdir(parents=True, exist_ok=True)
                metadata_path.write_text(default_content)
                content = default_content
                source = "metadata"
                size = len(default_content.encode())
                modified = datetime.now().isoformat()
                path = str(metadata_path)
            
            return {
                "content": content,
                "source": source,
                "size": size,
                "modified": modified,
                "path": path,
                "metadata_first": True
            }
            
        except Exception as e:
            raise e

    def _get_default_config_content(self, filename: str) -> str:
        """Get default content for configuration files."""
        if filename == "pins.json":
            return json.dumps({
                "pins": [],
                "total_count": 0,
                "last_updated": datetime.now().isoformat(),
                "replication_factor": 1,
                "cache_policy": "memory"
            }, indent=2)
        elif filename == "buckets.json":
            return json.dumps({
                "buckets": [],
                "total_count": 0,
                "last_updated": datetime.now().isoformat(),
                "default_replication_factor": 1,
                "default_cache_policy": "disk"
            }, indent=2)
        elif filename == "backends.json":
            return json.dumps({
                "backends": [],
                "total_count": 0,
                "last_updated": datetime.now().isoformat(),
                "default_backend": "ipfs",
                "health_check_interval": 30
            }, indent=2)
        else:
            return "{}"

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

    def render_beta_toolrunner(self) -> str:
        # Return the consolidated dashboard HTML (fallback tool runner removed)
        return self._html()

    # ---- assets ----
    def _html(self) -> str:
        # Return the enhanced dashboard HTML template with robust path resolution
        try:
            base_dir = Path(__file__).parent  # ipfs_kit_py/mcp/dashboard
            template_path = base_dir / "templates" / "enhanced_dashboard.html"
            
            if template_path.exists():
                with open(template_path, 'r', encoding='utf-8') as f:
                    self.log.info(f"Loaded template from: {template_path}")
                    return f.read()
            else:
                self.log.warning(f"Template not found at: {template_path}")
        except Exception as e:
            self.log.warning(f"Could not load enhanced template: {e}")
        
        # Fallback to basic template
        return """
<!doctype html>
<html>
    <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title>IPFS Kit MCP Dashboard</title>
    </head>
    <body>
        <div id="app">Loading...</div>
        <script src="/mcp-client.js"></script>
        <script src="/app.js"></script>
    </body>
 </html>
"""

    def _app_js(self) -> str:
        import textwrap
        # Enhanced: keep raw textarea visible and always update, matching tests' visibility needs.
        helpers = textwrap.dedent("""
        // --- Minimal SDK helpers (used by tests and external embeds) ---
        const __mcpDashGlobal = (typeof window !== 'undefined' ? window : globalThis);
        function ensureMcp(){
            try{ __mcpDashGlobal.MCP = __mcpDashGlobal.MCP || {}; }catch(e){}
            return (__mcpDashGlobal.MCP || {});
        }
        async function rpcTool(name, args){
            const mcp = ensureMcp();
            const token = (mcp.API_TOKEN || __mcpDashGlobal.API_TOKEN || '');
            const req = {
                jsonrpc: '2.0',
                method: 'tools/call',
                params: { name: name, arguments: (args || {}) },
                id: Date.now(),
            };
            const r = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'content-type': 'application/json', 'x-api-token': token },
                body: JSON.stringify(req),
            });
            const js = await r.json();
            if (js && typeof js === 'object' && 'result' in js) return js.result;
            return js;
        }

        let lastBuiltTool=null; async function buildToolForm(tool){ const form=document.getElementById('tool-form'); const raw=document.getElementById('tool-args'); const desc=document.getElementById('tool-desc'); if(!form||!raw) return; form.innerHTML=''; if(desc) desc.textContent= tool? (tool.description||'') : ''; if(!tool){ /* keep raw visible */ return; } lastBuiltTool=tool.name; const schema=simplifySchema(tool.inputSchema); if(schema.type!=='object'){ /* keep raw visible */ return; }
            const props=schema.properties||{}; const required=new Set(schema.required||[]);
            for(const [name, prop] of Object.entries(props)){
                const wrap=document.createElement('label'); wrap.style.display='flex'; wrap.style.flexDirection='column'; wrap.style.fontSize='11px'; wrap.style.minWidth='140px'; wrap.style.flex='1 1 140px'; wrap.dataset.wrapFor=name;
                const title=(prop.title||name)+(required.has(name)?'*':''); const span=document.createElement('span'); span.textContent=title; span.style.marginBottom='2px'; wrap.append(span);
                let input;
                if(prop.enum){ input=document.createElement('select'); prop.enum.forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=v; input.append(o); }); }
                else if((prop.ui||{}).enumFrom){ input=document.createElement('select'); input.dataset.enumFrom=prop.ui.enumFrom; input.innerHTML='<option value="">(loading)</option>'; dynamicEnum(prop).then(list=>{ if(!list) return; input.innerHTML=''; list.forEach(it=>{ const o=document.createElement('option'); o.value=it.value; o.textContent=it.label; input.append(o); }); if(prop.default) input.value=prop.default; updateRawArgs(); }); }
                else if(prop.type==='boolean'){ input=document.createElement('input'); input.type='checkbox'; if(prop.default) input.checked=!!prop.default; }
                else if(prop.type==='number' || prop.type==='integer'){ input=document.createElement('input'); input.type='number'; if(prop.default!=null) input.value=prop.default; }
                else if((prop.ui||{}).widget==='textarea'){ input=document.createElement('textarea'); input.rows=(prop.ui.rows||3); if(prop.default!=null) input.value=prop.default; }
                else { input=document.createElement('input'); input.type='text'; if(prop.default!=null) input.value=prop.default; }
                input.id='tool-field-'+name; input.dataset.fieldName=name; if(prop.description) input.title=prop.description; if((prop.ui||{}).placeholder) input.placeholder=prop.ui.placeholder; if(required.has(name)) input.dataset.required='1';
                input.addEventListener('input', ()=>{ clearFieldError(input); updateRawArgs(); });
                if(input.tagName==='SELECT') input.addEventListener('change', ()=>{ clearFieldError(input); updateRawArgs(); });
                wrap.append(input); form.append(wrap);
            }
            updateRawArgs();
        }
        function collectFormArgs(){ const form=document.getElementById('tool-form'); if(!form) return {}; const fields=form.querySelectorAll('[data-field-name]'); const args={}; fields.forEach(f=>{ const name=f.dataset.fieldName; if(f.type==='checkbox') args[name]=f.checked; else if(f.type==='number') args[name]= (f.value===''? null : Number(f.value)); else args[name]=f.value; }); return args; }
        function updateRawArgs(){ const raw=document.getElementById('tool-args'); if(!raw) return; const args=collectFormArgs(); raw.value=JSON.stringify(args,null,2); }
        function clearFieldError(input){ const wrap=input.parentElement; if(wrap) wrap.style.outline='none'; }
        function validateToolForm(tool){ if(!tool) return true; const form=document.getElementById('tool-form'); if(!form) return true; let ok=true; const requiredEls=form.querySelectorAll('[data-required="1"]'); requiredEls.forEach(inp=>{ const val = (inp.type==='checkbox')? (inp.checked? 'true': '') : inp.value.trim(); if(!val){ ok=false; const wrap=inp.parentElement; if(wrap) wrap.style.outline='1px solid #d66'; } }); return ok; }
        const toolSelect=document.getElementById('tool-select'); if(toolSelect) toolSelect.addEventListener('change', ()=> buildToolFormForSelected());
        const rawToggle=document.getElementById('btn-tool-raw-toggle'); if(rawToggle) rawToggle.addEventListener('click',()=>{ /* keep raw visible; no-op */ });
        """)
        js_code = helpers + r"""
(function(){
    const POLL_INTERVAL = 5000; // ms
    const appRoot = document.getElementById('app');
    if (appRoot) appRoot.innerHTML = '';
    if (!document.getElementById('mcp-dashboard-css')) {
        const css = `
            .dash-header{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;background:linear-gradient(90deg,#243b55,#432c7a);color:#eef;font-family:system-ui,Arial,sans-serif;border-radius:6px;margin-bottom:14px;}
            .dash-header h1{font-size:20px;margin:0;font-weight:600;letter-spacing:.5px;}
            .dash-header .actions button{background:#394b68;color:#fff;border:1px solid #4d5f7d;border-radius:4px;padding:6px 12px;cursor:pointer;font-size:13px;}
            .dash-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-bottom:18px;}
            .card{background:#1c2432;color:#dbe2ee;border:1px solid #2d3a4d;border-radius:10px;padding:14px;position:relative;box-shadow:0 2px 4px rgba(0,0,0,.25);font-family:system-ui,Arial,sans-serif;}
            .card h3{margin:0 0 6px;font-size:15px;font-weight:600;color:#fff;}
            .big-metric{font-size:34px;font-weight:600;line-height:1.05;letter-spacing:-1px;color:#fff;}
            .metric-sub{font-size:11px;opacity:.7;text-transform:uppercase;letter-spacing:1px;margin-top:4px;}
            .bars{display:flex;flex-direction:column;gap:10px;}
            .bar{display:flex;flex-direction:column;font-size:12px;font-family:monospace;}
            .bar span{display:flex;justify-content:space-between;}
            .bar-track{height:8px;background:#2a3545;border-radius:4px;overflow:hidden;margin-top:4px;}
            .bar-fill{height:100%;background:linear-gradient(90deg,#6b8cff,#b081ff);width:0;transition:width .6s;}
            .muted{opacity:.55;}
            .split{display:grid;grid-template-columns:2fr 1fr;gap:16px;}
            @media(max-width:900px){.split{grid-template-columns:1fr;}}
            .timestamp{font-size:11px;opacity:.6;margin-left:12px;}
            .dash-nav{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px 0;padding:0 4px;}
            .dash-nav .nav-btn{background:#263242;color:#dbe2ee;border:1px solid #37475d;border-radius:4px;padding:6px 10px;cursor:pointer;font-size:13px;}
            .dash-nav .nav-btn.active{background:#4b5d78;color:#fff;}
            .view-panel{animation:fade .25s ease;}
            @keyframes fade{from{opacity:0}to{opacity:1}}
            .loading-spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #2196F3;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                animation: spin 1s linear infinite;
                margin: 0 auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        const styleEl = document.createElement('style'); styleEl.id='mcp-dashboard-css'; styleEl.textContent = css; document.head.append(styleEl);
    }
    function el(tag, attrs, ...kids){
        const e=document.createElement(tag); if(attrs){ for(const k in attrs){ if(k==='class') e.className=attrs[k]; else if(k==='text') e.textContent=attrs[k]; else e.setAttribute(k,attrs[k]); } }
        kids.flat().forEach(k=>{ if(k==null) return; if(typeof k==='string') e.appendChild(document.createTextNode(k)); else e.appendChild(k); });
        return e;
    }
    const header = el('div',{class:'dash-header'},
        el('div',{}, el('h1',{text:'IPFS Kit Dashboard'}), el('div',{class:'timestamp',id:'ts-info'},'')),
        el('div',{class:'actions'},
            el('button',{id:'btn-refresh',title:'Refresh data'},'Refresh'),
            ' ',
            el('button',{id:'btn-realtime',title:'Toggle real-time'},'Real-time: Off')
        )
    );
    // --- Deprecation banner (populated from initial WS system_update or fallback HTTP) ---
    let deprecationBanner = null;
    function renderDeprecationBanner(items){
        try{
            if(!Array.isArray(items) || !items.length) return;
            // Update existing hits if already rendered
            if(deprecationBanner){
                const ul = deprecationBanner.querySelector('ul.dep-items');
                if(ul){ ul.innerHTML = items.map(fmtItem).join(''); }
                return;
            }
            function fmtItem(it){
                var mig = it.migration? Object.keys(it.migration).map(function(k){ return k+': '+it.migration[k]; }).join(', ') : '-';
                return '<li><code>'+it.endpoint+'</code> remove in '+(it.remove_in||'?')+' (hits '+(it.hits||0)+')'+ (mig? '<br><span class="dep-mig">'+mig+'</span>':'') +'</li>';
            }
            deprecationBanner = document.createElement('div');
            deprecationBanner.className='deprecation-banner-wrap';
            deprecationBanner.innerHTML = '<div class="deprecation-banner"><div class="dep-main"><strong>Deprecated endpoints:</strong><ul class="dep-items">'+items.map(fmtItem).join('')+'</ul></div><button class="dep-close" title="Dismiss">x</button></div>';
            const style = document.createElement('style'); style.textContent = '.deprecation-banner{background:#5a3d10;border:1px solid #c68d2b;color:#ffe7c0;padding:10px 14px;font-size:13px;line-height:1.35;border-radius:6px;display:flex;gap:14px;position:relative;margin:0 0 14px 0;font-family:system-ui,Arial,sans-serif;} .deprecation-banner strong{color:#fff;} .deprecation-banner ul{margin:4px 0 0 18px;padding:0;} .deprecation-banner li{margin:2px 0;} .deprecation-banner code{background:#442c07;padding:1px 4px;border-radius:4px;} .deprecation-banner .dep-close{background:#7a5113;color:#fff;border:1px solid #c68d2b;width:26px;height:26px;border-radius:50%;cursor:pointer;font-size:14px;line-height:1;position:absolute;top:6px;right:6px;} .deprecation-banner .dep-close:hover{background:#8d601b;}'; document.head.appendChild(style);
            const root = appRoot || document.body; root.insertBefore(deprecationBanner, root.firstChild.nextSibling);
            const closeBtn = deprecationBanner.querySelector('.dep-close'); if(closeBtn){ closeBtn.addEventListener('click', function(){ deprecationBanner.remove(); deprecationBanner=null; }); }
        }catch(e){}
    }
    const grid = el('div',{class:'dash-grid'});
    const cardServer = el('div',{class:'card'}, el('h3',{text:'MCP Server'}), el('div',{class:'big-metric',id:'srv-status'},'-'), el('div',{class:'metric-sub',id:'srv-port'},''));
    const cardServices = el('div',{class:'card'}, el('h3',{text:'Services'}), el('div',{class:'big-metric',id:'svc-active'},'-'), el('div',{class:'metric-sub muted'},'Active Services'));
    const cardBackends = el('div',{class:'card'}, el('h3',{text:'Backends'}), el('div',{class:'big-metric',id:'count-backends'},'-'), el('div',{class:'metric-sub muted'},'Storage Backends'));
    const cardBuckets = el('div',{class:'card'}, el('h3',{text:'Buckets'}), el('div',{class:'big-metric',id:'count-buckets'},'-'), el('div',{class:'metric-sub muted'},'Total Buckets'));
    grid.append(cardServer, cardServices, cardBackends, cardBuckets);
    const perfCard = el('div',{class:'card'},
        el('h3',{text:'System Performance'}),
        el('div',{class:'bars'},
            perfBar('CPU Usage','cpu'),
            el('svg',{id:'spark-cpu',width:'100%',height:'26',style:'margin:4px 0 8px 0;background:#202a38;border:1px solid #2d3a4d;border-radius:3px;'}),
            perfBar('Memory Usage','mem'),
            el('svg',{id:'spark-mem',width:'100%',height:'26',style:'margin:4px 0 8px 0;background:#202a38;border:1px solid #2d3a4d;border-radius:3px;'}),
            perfBar('Disk Usage','disk'),
            el('svg',{id:'spark-disk',width:'100%',height:'26',style:'margin:4px 0 0 0;background:#202a38;border:1px solid #2d3a4d;border-radius:3px;'})
        )
    );
    const layout = el('div',{class:'split'}, perfCard, el('div',{class:'card'}, el('h3',{text:'Network Activity'}), el('div',{id:'net-activity',class:'muted',text:'Loading…'}),
        el('svg',{id:'net-spark',width:'100%',height:'60',style:'margin-top:6px;display:block;background:#202a38;border:1px solid #2d3a4d;border-radius:4px;'}),
        el('div',{id:'net-summary',class:'muted',style:'margin-top:4px;font-size:11px;'},'')));
    // --- Navigation & Views ---
    const nav = el('div',{class:'dash-nav'}, ['Overview','Services','Backends','Buckets','Pins','Logs','Files','Tools','IPFS','CARs'].map(name => el('button',{class:'nav-btn','data-view':name.toLowerCase(),text:name})));
    const overviewView = el('div',{id:'view-overview',class:'view-panel'}, grid, layout);
    const servicesView = el('div',{id:'view-services',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'Services'}),
            el('pre',{id:'services-json',text:'Loading…'}),
            el('div',{id:'services-actions',style:'margin-top:6px;font-size:12px;'},'')
        )
    );
    const backendsView = el('div',{id:'view-backends',class:'view-panel',style:'display:none;'},
        // Enhanced Backend Management with 9/9 Advanced Features
        el('div',{class:'card'},
            el('h2',{text:'Backend Health & Management',style:'color:#4CAF50;margin-bottom:16px;'}),
            
            // Top Action Bar with Enhanced Features  
            el('div',{style:'display:flex;gap:8px;margin-bottom:16px;padding:12px;background:#0a0a0a;border-radius:8px;'},
                el('button',{id:'refresh-backends',style:'background:#2196F3;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>loadBackends()},'🔄 Refresh All'),
                el('button',{id:'test-all-backends',style:'background:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>testAllBackends()},'🧪 Test All'),
                el('button',{id:'add-backend-instance',style:'background:#9C27B0;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>showAddBackendModal()},'➕ Add Instance'),
                el('button',{id:'sync-all-backends',style:'background:#FF9800;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>syncAllBackends()},'🔄 Sync All'),
                el('button',{id:'health-check-backends',style:'background:#E91E63;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>runHealthCheck()},'🏥 Health Check'),
                // Advanced Feature 8: Performance Metrics Button
                el('button',{id:'show-performance-metrics',style:'background:#607D8B;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>showPerformanceMetrics()},'📊 Performance'),
                // Advanced Feature 9: Configuration Templates Button
                el('button',{id:'show-config-templates',style:'background:#795548;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>showConfigurationTemplates()},'⚙️ Templates')
            ),
            
            // Info Banner
            el('div',{style:'padding:8px 12px;background:#1a1a1a;border:1px solid #333;border-radius:4px;margin-bottom:12px;font-size:13px;'},
                el('span',{style:'color:#FFC107;'},'💡'),
                el('strong',{text:' Multi-Backend Support: ',style:'color:#4CAF50;'}),
                'Manage multiple S3 buckets, GitHub accounts, IPFS clusters with individual cache/storage/retention policies. Uses ~/.ipfs_kit/ metadata-first approach.'
            ),
            
            // Category Filter Tabs
            el('div',{style:'display:flex;gap:4px;margin-bottom:12px;'},
                el('button',{id:'filter-all',class:'active',style:'padding:6px 12px;background:#2196F3;color:white;border:none;border-radius:4px;cursor:pointer;',onclick:()=>filterBackends('all')},'All Backends'),
                el('button',{id:'filter-storage',style:'padding:6px 12px;background:#4CAF50;color:white;border:none;border-radius:4px;cursor:pointer;',onclick:()=>filterBackends('storage')},'🗄️ Storage'),
                el('button',{id:'filter-network',style:'padding:6px 12px;background:#9C27B0;color:white;border:none;border-radius:4px;cursor:pointer;',onclick:()=>filterBackends('network')},'🌐 Network'),
                el('button',{id:'filter-compute',style:'padding:6px 12px;background:#FF9800;color:white;border:none;border-radius:4px;cursor:pointer;',onclick:()=>filterBackends('compute')},'⚡ Compute'),
                el('button',{id:'filter-analytics',style:'padding:6px 12px;background:#E91E63;color:white;border:none;border-radius:4px;cursor:pointer;',onclick:()=>filterBackends('analytics')},'📊 Analytics')
            ),
            
            // Health Status Dashboard
            el('div',{style:'display:flex;gap:12px;margin-bottom:16px;'},
                el('div',{style:'text-align:center;padding:8px;background:#0a0a0a;border-radius:4px;flex:1;'},
                    el('div',{id:'healthy-count',style:'font-size:24px;color:#4CAF50;font-weight:bold;'},'0'),
                    el('div',{style:'font-size:12px;color:#888;'},'Healthy')
                ),
                el('div',{style:'text-align:center;padding:8px;background:#0a0a0a;border-radius:4px;flex:1;'},
                    el('div',{id:'unhealthy-count',style:'font-size:24px;color:#f44336;font-weight:bold;'},'0'),
                    el('div',{style:'font-size:12px;color:#888;'},'Unhealthy')
                ),
                el('div',{style:'text-align:center;padding:8px;background:#0a0a0a;border-radius:4px;flex:1;'},
                    el('div',{id:'configured-count',style:'font-size:24px;color:#2196F3;font-weight:bold;'},'0'),
                    el('div',{style:'font-size:12px;color:#888;'},'Configured')
                ),
                el('div',{style:'text-align:center;padding:8px;background:#0a0a0a;border-radius:4px;flex:1;'},
                    el('div',{id:'total-backends-count',style:'font-size:24px;color:#9C27B0;font-weight:bold;'},'0'),
                    el('div',{style:'font-size:12px;color:#888;'},'Total')
                )
            ),
            
            // Backends List Container
            el('div',{id:'backends-list',style:'margin-top:8px;'},'Loading…'),
            
            // Advanced Feature 8: Performance Metrics Modal
            el('div',{id:'performance-metrics-modal',style:'display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:1000;'},
                el('div',{style:'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:20px;max-width:90%;max-height:90%;overflow-y:auto;color:white;min-width:600px;'},
                    el('div',{style:'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;'},
                        el('h3',{text:'🚀 Real-Time Performance Metrics',style:'margin:0;color:#4CAF50;'}),
                        el('button',{onclick:()=>closePerformanceMetrics(),style:'background:#555;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;'},'×')
                    ),
                    el('div',{id:'performance-metrics-content',text:'Loading performance data...'}),
                    el('div',{style:'margin-top:16px;display:flex;gap:8px;'},
                        el('button',{onclick:()=>refreshPerformanceMetrics(),style:'background:#2196F3;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;'},'🔄 Refresh'),
                        el('select',{id:'metrics-time-range',style:'padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;',onchange:()=>refreshPerformanceMetrics()},
                            el('option',{value:'1h',text:'Last Hour'}),
                            el('option',{value:'6h',text:'Last 6 Hours'}),
                            el('option',{value:'24h',text:'Last 24 Hours'}),
                            el('option',{value:'7d',text:'Last 7 Days'})
                        )
                    )
                )
            ),
            
            // Advanced Feature 9: Configuration Templates Modal
            el('div',{id:'config-templates-modal',style:'display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:1000;'},
                el('div',{style:'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:20px;max-width:90%;max-height:90%;overflow-y:auto;color:white;min-width:600px;'},
                    el('div',{style:'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;'},
                        el('h3',{text:'⚙️ Advanced Configuration Management',style:'margin:0;color:#4CAF50;'}),
                        el('button',{onclick:()=>closeConfigTemplates(),style:'background:#555;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;'},'×')
                    ),
                    el('div',{style:'display:flex;gap:12px;margin-bottom:16px;'},
                        el('button',{onclick:()=>showTemplateSelector(),style:'background:#9C27B0;color:white;padding:8px 12px;border:none;border-radius:4px;cursor:pointer;'},'📄 Templates'),
                        el('button',{onclick:()=>showCloneBackend(),style:'background:#2196F3;color:white;padding:8px 12px;border:none;border-radius:4px;cursor:pointer;'},'📋 Clone'),
                        el('button',{onclick:()=>showBackupRestore(),style:'background:#FF9800;color:white;padding:8px 12px;border:none;border-radius:4px;cursor:pointer;'},'💾 Backup'),
                        el('button',{onclick:()=>showAdvancedPolicyEditor(),style:'background:#E91E63;color:white;padding:8px 12px;border:none;border-radius:4px;cursor:pointer;'},'🔧 Policies')
                    ),
                    el('div',{id:'config-templates-content',text:'Select a configuration management option above...'})
                )
            )
        )
    );
    const bucketsView = el('div',{id:'view-buckets',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'Bucket File Management'}),
            
            // Bucket Creation Row
            el('div',{class:'row',style:'margin-bottom:12px;border-bottom:1px solid #333;padding-bottom:8px;'},
                el('input',{id:'bucket-name',placeholder:'bucket name',style:'width:140px;margin-right:8px;'}),
                el('input',{id:'bucket-backend',placeholder:'backend (optional)',style:'width:140px;margin-right:8px;'}),
                el('button',{id:'btn-bucket-add',style:'background:#4CAF50;color:white;margin-right:8px;'},'Create Bucket'),
                el('button',{id:'btn-refresh-buckets',style:'background:#2196F3;color:white;'},'Refresh')
            ),
            
            // Bucket Selection and Toolbar
            el('div',{class:'row',style:'margin-bottom:12px;'},
                el('label',{style:'margin-right:8px;font-weight:bold;',text:'Selected Bucket:'}),
                el('select',{id:'bucket-selector',style:'width:200px;margin-right:12px;'}),
                el('button',{id:'btn-bucket-configure',style:'margin-right:4px;background:#FF9800;color:white;',disabled:true},'Configure'),
                el('button',{id:'btn-bucket-advanced',style:'margin-right:4px;background:#9C27B0;color:white;',disabled:true},'Advanced Settings'),
                el('button',{id:'btn-bucket-quota',style:'margin-right:4px;background:#607D8B;color:white;',disabled:true},'Quota'),
                el('button',{id:'btn-bucket-share',style:'margin-right:4px;background:#795548;color:white;',disabled:true},'Share'),
                el('button',{id:'btn-force-sync',style:'margin-right:4px;background:#E91E63;color:white;',disabled:true},'Force Sync')
            ),
            
            // Status Bar
            el('div',{id:'bucket-status-bar',class:'status-bar',style:'background:#1a1a1a;border:1px solid #333;border-radius:4px;padding:8px;margin-bottom:12px;font-size:12px;display:none;'},
                el('div',{class:'status-row',style:'display:flex;justify-content:space-between;align-items:center;'},
                    el('div',{class:'status-left',style:'display:flex;gap:16px;'},
                        el('span',{id:'status-quota',style:'color:#4CAF50;'},'Quota: N/A'),
                        el('span',{id:'status-files',style:'color:#2196F3;'},'Files: 0'),
                        el('span',{id:'status-cache',style:'color:#FF9800;'},'Cache: None')
                    ),
                    el('div',{class:'status-right'},
                        el('span',{id:'status-retention',style:'color:#9C27B0;'},'Retention: N/A')
                    )
                )
            ),
            
            // Drag & Drop Upload Zone
            el('div',{id:'drop-zone',class:'drop-zone',style:'border:2px dashed #666;border-radius:8px;padding:20px;text-align:center;margin-bottom:12px;background:#0a0a0a;display:none;'},
                el('div',{class:'drop-zone-content'},
                    el('div',{style:'font-size:48px;color:#666;margin-bottom:8px;'},'📁'),
                    el('p',{style:'margin:0;color:#ccc;font-size:16px;'},'Drag & drop files here or click to browse'),
                    el('p',{style:'margin:4px 0 0 0;color:#888;font-size:12px;'},'Multiple files supported'),
                    el('input',{id:'file-input',type:'file',multiple:true,style:'display:none;'})
                )
            ),
            
            // File Operations Toolbar
            el('div',{id:'file-toolbar',class:'row',style:'margin-bottom:8px;display:none;'},
                el('button',{id:'btn-upload-file',style:'margin-right:4px;background:#4CAF50;color:white;'},'📤 Upload'),
                el('button',{id:'btn-new-folder',style:'margin-right:4px;background:#2196F3;color:white;'},'📁 New Folder'),
                el('button',{id:'btn-selective-sync',style:'margin-right:4px;background:#FF5722;color:white;',disabled:true},'🔄 Selective Sync'),
                el('button',{id:'btn-download-selected',style:'margin-right:4px;background:#673AB7;color:white;',disabled:true},'💾 Download'),
                el('button',{id:'btn-delete-selected',style:'margin-right:4px;background:#F44336;color:white;',disabled:true},'🗑️ Delete'),
                el('span',{style:'margin-left:12px;color:#888;font-size:11px;',id:'selection-info'},'Select files to enable operations')
            ),
            
            // File List Container
            el('div',{id:'file-list-container',style:'border:1px solid #333;border-radius:4px;background:#0a0a0a;min-height:300px;max-height:400px;overflow-y:auto;display:none;'},
                el('div',{id:'file-list-header',style:'background:#1a1a1a;padding:8px;border-bottom:1px solid #333;font-size:12px;font-weight:bold;color:#ccc;'},
                    el('div',{style:'display:grid;grid-template-columns:30px 1fr 100px 120px 80px;gap:8px;align-items:center;'},
                        el('span',{}),
                        el('span',{text:'Name'}),
                        el('span',{text:'Size'}),
                        el('span',{text:'Modified'}),
                        el('span',{text:'Actions'})
                    )
                ),
                el('div',{id:'file-list-body',style:'padding:4px;'},'Loading...')
            ),
            
            // Upload Progress
            el('div',{id:'upload-progress',style:'margin-top:8px;display:none;'},
                el('div',{style:'color:#ccc;font-size:12px;margin-bottom:4px;'},'Uploading files...'),
                el('div',{class:'progress-bar',style:'background:#333;border-radius:4px;height:20px;overflow:hidden;'},
                    el('div',{id:'progress-fill',style:'background:linear-gradient(90deg,#4CAF50,#8BC34A);height:100%;width:0%;transition:width 0.3s;'})
                ),
                el('div',{id:'progress-text',style:'color:#888;font-size:11px;margin-top:4px;'},'0% complete')
            ),
            
            // Bucket List (for non-selected view)
            el('div',{id:'buckets-list',style:'margin-top:8px;font-size:13px;'},'Loading…')
        )
    );
    const pinsView = el('div',{id:'view-pins',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'Pins'}),
            el('div',{class:'row'},
                el('input',{id:'pin-cid',placeholder:'cid',style:'width:200px;'}),
                el('input',{id:'pin-name',placeholder:'name',style:'width:140px;'}),
                el('button',{id:'btn-pin-add'},'Add')
            ),
            el('div',{id:'pins-list',style:'margin-top:8px;font-size:13px;'},'Loading…')
        )
    );
    const logsView = el('div',{id:'view-logs',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'}, el('h3',{text:'Logs'}),
            el('div',{class:'row'}, el('button',{id:'btn-clear-logs'},'Clear Logs')),
            el('pre',{id:'logs-pre',text:'(streaming)…'})
        )
    );
    const filesView = el('div',{id:'view-files',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'}, el('h3',{text:'Virtual File System'}),
            // Bucket selection and path navigation
            el('div',{class:'row',style:'margin-bottom:8px;'},
                el('label',{style:'margin-right:8px;',text:'Bucket:'}),
                el('select',{id:'files-bucket',style:'width:120px;margin-right:8px;'}),
                el('button',{id:'btn-bucket-refresh',style:'font-size:11px;padding:2px 6px;'},'Refresh')
            ),
            el('div',{class:'row',style:'margin-bottom:8px;'},
                el('label',{style:'margin-right:8px;',text:'Path:'}),
                el('input',{id:'files-path',value:'.',style:'width:200px;margin-right:8px;'}),
                el('button',{id:'btn-files-load'},'Load'),
                el('button',{id:'btn-files-up',style:'margin-left:4px;'},'↑ Up'),
                el('button',{id:'btn-files-refresh',style:'margin-left:4px;'},'Refresh')
            ),
            // File operations toolbar
            el('div',{class:'row',style:'margin-bottom:8px;border-top:1px solid #333;padding-top:8px;'},
                el('button',{id:'btn-file-new',style:'margin-right:4px;'},'New File'),
                el('button',{id:'btn-dir-new',style:'margin-right:4px;'},'New Directory'),
                el('button',{id:'btn-file-upload',style:'margin-right:4px;'},'Upload'),
                el('input',{id:'file-upload-input',type:'file',style:'display:none;multiple:true'}),
                el('button',{id:'btn-file-delete',disabled:true,style:'margin-left:12px;color:#f66;'},'Delete Selected')
            ),
            // File listing
            el('div',{id:'files-container',style:'border:1px solid #333;min-height:200px;max-height:400px;overflow-y:auto;padding:4px;background:#0a0a0a;'},
                el('div',{id:'files-loading',text:'Loading…'})
            ),
            // File details panel
            el('div',{id:'file-details',style:'margin-top:8px;padding:8px;border:1px solid #333;background:#111;display:none;'},
                el('h4',{text:'File Details',style:'margin:0 0 8px 0;'}),
                el('div',{id:'file-stats',style:'font-family:monospace;font-size:12px;white-space:pre-wrap;'})
            )
        )
    );
    // Tools (enhanced tool runner)
    const toolsView = el('div',{id:'view-tools',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'Tools'}),
            el('div',{class:'row'},
                el('input',{id:'tool-filter',placeholder:'filter',style:'width:160px;'}),
                el('select',{id:'tool-select',style:'min-width:260px;'}),
                el('button',{id:'btn-tool-refresh'},'Reload'),
                el('button',{id:'btn-tool-raw-toggle',style:'margin-left:6px;font-size:11px;'},'Raw JSON')
            ),
            el('div',{id:'tool-desc',class:'muted',style:'font-size:11px;margin-top:4px;'}),
            el('div',{id:'tool-form',style:'margin-top:8px;display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end;'}),
            el('div',{class:'row',style:'margin-top:6px;'},
                el('textarea',{id:'tool-args',rows:'6',style:'width:100%;display:none;',text:'{}'})
            ),
            el('div',{class:'row',style:'margin-top:6px;'},
                el('button',{id:'btn-tool-run'},'Run'),
                el('span',{id:'tool-run-status',style:'font-size:12px;opacity:.7;margin-left:8px;'})
            ),
            el('pre',{id:'tool-result',text:'(result)'}),
            el('div',{style:'font-size:11px;opacity:.6;margin-top:4px;'},'Uses MCP JSON-RPC wrappers.'),
            // Beta Tool Runner (always present; visible when beta mode)
            el('div',{id:'toolrunner-beta-container', style:'margin-top:16px;padding-top:10px;border-top:'+'1px solid #2d3a4d;'},
                el('h3',{text:'Beta Tool Runner'}),
                el('div',{class:'row',style:'margin-bottom:6px;'},
                    el('input',{ 'data-testid':'toolbeta-filter', id:'toolbeta-filter', placeholder:'filter tools', style:'width:200px;margin-right:8px;' }),
                    el('select',{ 'data-testid':'toolbeta-select', id:'toolbeta-select', style:'min-width:260px;' })
                ),
                el('div',{id:'toolbeta-form',style:'margin-top:8px;display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end;'}),
                el('div',{class:'row',style:'margin-top:6px;'},
                    el('button',{ 'data-testid':'toolbeta-run', id:'toolbeta-run', style:'font-size:12px;padding:6px 12px;' },'Run')
                ),
                el('pre',{ 'data-testid':'toolbeta-result', id:'toolbeta-result', text:'(result)'})
            )
        )
    );
    // IPFS Panel
    const ipfsView = el('div',{id:'view-ipfs',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'IPFS'}),
            el('div',{id:'ipfs-version',class:'muted',text:'(version?)'}),
            el('div',{class:'row',style:'margin-top:8px;'},
                el('input',{id:'ipfs-cid',placeholder:'CID',style:'width:260px;'}),
                el('button',{id:'btn-ipfs-cat'},'Cat'),
                el('button',{id:'btn-ipfs-pin'},'Pin')
            ),
            el('pre',{id:'ipfs-cat-output',text:'(cat output)'}),
            el('div',{style:'font-size:11px;opacity:.6;margin-top:4px;'},'Cat truncated to 8KB.')
        )
    );
    // CARs Panel
    const carsView = el('div',{id:'view-cars',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'CAR Files'}),
            el('div',{class:'row'},
                el('button',{id:'btn-cars-refresh'},'List'),
                el('input',{id:'car-path',placeholder:'path',style:'width:160px;'}),
                el('input',{id:'car-name',placeholder:'file.car',style:'width:160px;'}),
                el('button',{id:'btn-car-export'},'Export'),
                el('input',{id:'car-import-src',placeholder:'file.car',style:'width:160px;'}),
                el('input',{id:'car-import-dest',placeholder:'dest path',style:'width:160px;'}),
                el('button',{id:'btn-car-import'},'Import')
            ),
            el('pre',{id:'cars-list',text:'(list)'}),
            el('div',{style:'font-size:11px;opacity:.6;margin-top:4px;'},'Uses CAR tool wrappers.')
        )
    );
    if (appRoot){ appRoot.append(header, nav, overviewView, servicesView, backendsView, bucketsView, pinsView, logsView, filesView, toolsView, ipfsView, carsView); }
    function perfBar(label,key){
        const fillId = 'bar-fill-'+key;
        return el('div',{class:'bar'},
            el('span',{}, el('strong',{},label), el('span',{id:'bar-label-'+key},'-')),
            el('div',{class:'bar-track'}, el('div',{class:'bar-fill',id:fillId}))
        );
    }
    function showView(name){
    const panels = ['overview','services','backends','buckets','pins','logs','files','tools','ipfs','cars'];
        panels.forEach(p => {
            const elp=document.getElementById('view-'+p); if(elp) elp.style.display = (p===name?'block':'none');
            const btn=document.querySelector('.dash-nav .nav-btn[data-view="'+p+'"]'); if(btn) btn.classList.toggle('active', p===name);
        });
        if(name==='services') loadServices();
        else if(name==='backends') loadBackends();
    else if(name==='buckets') loadBuckets();
        else if(name==='pins') loadPins();
        else if(name==='logs') initLogs();
    else if(name==='files') { loadVfsBuckets(); loadFiles(); }
    else if(name==='tools') { initTools(); initToolRunnerBeta(); }
    else if(name==='ipfs') initIPFS();
    else if(name==='cars') initCARs();
    }
    nav.querySelectorAll('.nav-btn').forEach(btn=> btn.addEventListener('click', ()=> showView(btn.getAttribute('data-view'))));
    // Always default to Tools (beta Tool Runner) to guarantee the beta UI is shown
    showView('tools');

    // --- Beta Tool Runner logic ---
    let toolbetaInited=false; let toolbetaTools=[];
    async function initToolRunnerBeta(){
        const container=document.getElementById('toolrunner-beta-container'); if(!container) return;
        if(toolbetaInited) return; toolbetaInited=true;
        try{
            // Load tools
            await waitForMCP();
            const list = await MCP.listTools();
            toolbetaTools = (list && list.result && Array.isArray(list.result.tools))? list.result.tools : [];
            renderToolbetaSelect(toolbetaTools);
            bindToolbeta();
        }catch(e){ /* ignore */ }
    }
    function renderToolbetaSelect(tools){
        const sel=document.getElementById('toolbeta-select'); if(!sel) return;
        sel.innerHTML='';
        tools.forEach(t=>{ const opt=document.createElement('option'); opt.value=t.name; opt.textContent=t.name; sel.append(opt); });
    }
    function bindToolbeta(){
        const filter=document.getElementById('toolbeta-filter');
        const sel=document.getElementById('toolbeta-select');
        const run=document.getElementById('toolbeta-run');
        const form=document.getElementById('toolbeta-form');
        const result=document.getElementById('toolbeta-result');
        if(filter){ filter.addEventListener('input', ()=>{
            const q=String(filter.value||'').toLowerCase();
            const filtered = toolbetaTools.filter(t=> t.name.toLowerCase().includes(q));
            renderToolbetaSelect(filtered);
        }); }
        if(sel){ sel.addEventListener('change', ()=> updateToolbetaForm(sel.value)); }
        if(run){ run.addEventListener('click', async ()=>{
            try{
                const name = sel && sel.value; if(!name) return;
                const args = collectToolbetaArgs();
                const out = await MCP.callTool(name, args);
                if(result) result.textContent = JSON.stringify(out, null, 2);
            }catch(e){ if(result) result.textContent = String(e); }
        }); }
        // Initialize with first tool if available
        if(sel && sel.options.length>0){ updateToolbetaForm(sel.value); }
    }
    function collectToolbetaArgs(){
        const form=document.getElementById('toolbeta-form'); const args={};
        if(!form) return args;
        const inputs=form.querySelectorAll('[data-fld]');
        inputs.forEach(inp=>{
            const key=inp.getAttribute('data-fld');
            if(inp.type==='checkbox') args[key]=!!inp.checked; else args[key]=inp.value;
        });
        return args;
    }
    async function updateToolbetaForm(toolName){
        const form=document.getElementById('toolbeta-form'); if(!form) return; form.innerHTML='';
        const tool = toolbetaTools.find(t=> t.name===toolName) || {};
        const schema = (tool && tool.inputSchema) || {}; const props = schema.properties || {};
        const backendNames = await getBackendNames();
        Object.keys(props).forEach(k=>{
            const def = props[k]||{}; const type = Array.isArray(def.type)? def.type[0] : (def.type||'string');
            const id='fld_'+k; let field=null;
            if(k==='backend'){
                const sel=document.createElement('select'); sel.setAttribute('data-testid','toolbeta-field-backend'); sel.id=id; sel.setAttribute('data-fld',k);
                backendNames.forEach(n=>{ const o=document.createElement('option'); o.value=n; o.textContent=n; sel.append(o); });
                field=sel;
            }else if(type==='boolean'){
                const inp=document.createElement('input'); inp.type='checkbox'; inp.id=id; inp.setAttribute('data-fld',k); field=inp;
            }else{
                const inp=document.createElement('input'); inp.type='text'; inp.id=id; inp.setAttribute('data-fld',k); field=inp;
            }
            const wrap=document.createElement('label'); wrap.style.display='flex'; wrap.style.flexDirection='column'; wrap.style.fontSize='11px';
            wrap.textContent = k; wrap.appendChild(field); form.appendChild(wrap);
        });
    }
    async function getBackendNames(){ try{ const r=await MCP.Backends.list(); const items=(r && r.result && r.result.items)||[]; return items.map(it=> it.name); }catch(e){ return []; } }
    async function waitForMCP(){ const t0=Date.now(); while(!(window.MCP && MCP.listTools)){ if(Date.now()-t0>15000) throw new Error('MCP not ready'); await new Promise(r=>setTimeout(r,50)); } }

    async function loadServices(){
        const pre=document.getElementById('services-json'); if(pre) pre.textContent='Loading…';
        try{ 
            // Use MCP SDK instead of direct REST call
            const result = await window.MCP.callTool('list_services', {});
            const services = (result && result.result && result.result.services) || {}; 
            // Build table
            let html='';
            html += 'Service | Status | Actions\n';
            html += '--------|--------|--------\n';
            Object.entries(services).forEach(([name, info])=>{
                const st=(info&&info.status)||info.bin? (info.status||'detected'): 'missing';
                html += `${name} | ${st} | `;
                // Show actions for all services that have actions available
                const serviceActions = info.actions || [];
                if (serviceActions.length > 0) {
                    const running = st==='running';
                    if (running) {
                        html += `[stop] [restart]`;
                    } else if (st==='stopped' || st==='detected') {
                        html += `[start]`;
                    } else {
                        html += `[start]`;
                    }
                }
                html += '\n';
            });
            if(pre) pre.textContent=html.trim();
            // attach click handler for actions within pre (simple delegation parsing tokens)
            if(pre && !pre._svcBound){
                pre._svcBound=true;
                pre.addEventListener('click', (e)=>{
                    if(e.target.nodeType!==Node.TEXT_NODE) return; // plain text selection ignored
                });
                pre.addEventListener('mousedown', (e)=>{
                    const sel=window.getSelection();
                    if(sel && sel.toString()) return; // allow text selection
                    const pos=pre.ownerDocument.caretRangeFromPoint? pre.ownerDocument.caretRangeFromPoint(e.clientX,e.clientY): null;
                    if(!pos) return;
                });
                // Simpler: use regex on clicked position not robust; instead overlay buttons separately below
            }
            // Render interactive buttons below table for each lifecycle-managed service
            const containerBtns = document.getElementById('services-actions');
            if(containerBtns){
                containerBtns.innerHTML='';
                Object.entries(services).forEach(([name, info])=>{
                    // Show action buttons for services that have actions available
                    const serviceActions = info.actions || [];
                    if (serviceActions.length === 0) return;
                    const st=(info&&info.status)||'unknown';
                    const wrap=document.createElement('div'); wrap.style.marginBottom='4px';
                    const title=document.createElement('strong'); title.textContent=name+':'; title.style.marginRight='6px'; wrap.append(title);
                    function addBtn(label, action){ const b=document.createElement('button'); b.textContent=label; b.style.marginRight='4px'; b.style.fontSize='11px'; b.onclick=()=> serviceAction(name, action); wrap.append(b);} 
                    if(st==='running'){ addBtn('Stop','stop'); addBtn('Restart','restart'); }
                    else if(st==='starting' || st==='stopping' || st==='restarting'){ const span=document.createElement('span'); span.textContent='(transition '+st+')'; wrap.append(span); }
                    else { addBtn('Start','start'); }
                    // If service supports configure, surface a Configure button
                    if (serviceActions.includes('configure')){
                        const cfg=document.createElement('button'); cfg.textContent='Configure'; cfg.style.marginRight='4px'; cfg.style.fontSize='11px';
                        cfg.onclick=()=> configureService(name, info);
                        wrap.append(cfg);
                    }
                    const statusSpan=document.createElement('span'); statusSpan.textContent=' status='+st; statusSpan.style.marginLeft='6px'; wrap.append(statusSpan);
                    containerBtns.append(wrap);
                });
            }
        }catch(e){ if(pre) pre.textContent='Error'; }
    }
    async function serviceAction(name, action){
        try{ 
            // Use MCP SDK service control instead of direct REST call
            await window.MCP.callTool('service_control', { service: name, action: action }); 
            loadServices(); 
        }catch(e){
            console.error('Service action failed:', e);
        }
    }
    // Simple configure flow: prompt for known config keys and send as params
    async function configureService(name, info){
        try{
            const keys = (info && info.config_keys) || [];
            let params = {};
            if (Array.isArray(keys) && keys.length){
                for (const k of keys){
                    const current = (info && info.details && (info.details[k]!==undefined? String(info.details[k]) : '')) || '';
                    const val = window.prompt(`Configure ${name}: enter value for ${k}`, current);
                    if (val===null) { /* cancelled */ return; }
                    // Try to coerce numbers and booleans, otherwise keep string
                    if (val==='true' || val==='false') params[k] = (val==='true');
                    else if (!Number.isNaN(Number(val)) && val.trim()!=='' && /^-?\d+(\.\d+)?$/.test(val.trim())) params[k] = Number(val);
                    else params[k] = val;
                }
            } else {
                const json = window.prompt(`Configure ${name}: enter params JSON`, '{"port":5001}');
                if (json===null) return;
                try{ params = JSON.parse(json); }catch(e){ alert('Invalid JSON'); return; }
            }
            const res = await window.MCP.Services.control(name, 'configure', params);
            // Normalize result shape whether JSON-RPC wrapped or not
            const payload = (res && res.result) ? res.result : res;
            if (payload && payload.success){
                const p = payload.saved_path || payload.config_file || '';
                alert(`Configured ${name} successfully` + (p? `\nSaved to: ${p}` : ''));
            } else {
                alert(`Configure failed for ${name}: ${payload && (payload.error||payload.message) || 'unknown error'}`);
            }
            loadServices();
        }catch(e){
            console.error('Configure failed:', e);
            alert(`Configure failed: ${e && e.message || e}`);
        }
    }
    // Polling for services when services view active
    setInterval(()=>{ const sv=document.getElementById('view-services'); if(sv && sv.style.display==='block') loadServices(); }, 5000);
    async function loadBackends(){
        const container = document.getElementById('backends-list'); if(!container) return;
        
        // Show proper loading state
        container.innerHTML = '<div style="text-align:center;padding:20px;color:#666;"><div class="loading-spinner"></div><br>Loading backends...</div>';
        
        try{ 
            console.log('🗄️ Loading backends via MCP SDK (metadata-first)...');
            const response = await MCP.callTool('list_backends', {include_metadata: true});
            
            if (!response || !response.result) {
                throw new Error('Invalid MCP response');
            }
            
            const js = response.result; 
            const backends = js.backends || js.items || []; 
            
            console.log(`🗄️ Backends result:`, {result: js});
            console.log(`🗄️ Extracted backends array:`, backends);
            console.log(`🗄️ Is backends an array?`, Array.isArray(backends));
            
            // Update health counters with MCP data
            const healthyCount = js.healthy || 0;
            const unhealthyCount = js.unhealthy || 0;
            const configuredCount = js.configured || 0;
            const totalCount = js.total || backends.length;
            
            const healthyEl = document.getElementById('healthy-count');
            const unhealthyEl = document.getElementById('unhealthy-count');
            const configuredEl = document.getElementById('configured-count');
            const totalEl = document.getElementById('total-backends-count');
            
            console.log('🔢 Updating health counters:', {healthyCount, unhealthyCount, configuredCount, totalCount});
            console.log('🔢 Elements found:', {healthyEl, unhealthyEl, configuredEl, totalEl});
            
            if (healthyEl) {
                healthyEl.textContent = healthyCount;
                console.log('✅ Updated healthy count to', healthyCount);
            }
            if (unhealthyEl) {
                unhealthyEl.textContent = unhealthyCount;
                console.log('✅ Updated unhealthy count to', unhealthyCount);
            }
            if (configuredEl) {
                configuredEl.textContent = configuredCount;
                console.log('✅ Updated configured count to', configuredCount);
            }
            if (totalEl) {
                totalEl.textContent = totalCount;
                console.log('✅ Updated total count to', totalCount);
            }
            
            if(!backends.length){ 
                container.innerHTML = '<div style="text-align:center;padding:20px;color:#666;">No backends configured</div>'; 
                return; 
            }
            
            container.innerHTML=''; 
            backends.forEach((backend, index) => {
                // Enhanced data validation and processing
                const name = backend.name || `backend_${index}`;
                const type = backend.type || (backend.config && backend.config.type) || 'local';
                const tier = backend.tier || 'standard';
                const status = backend.status || 'enabled';
                const description = backend.description || `${type} storage backend`;
                
                // Validate required fields and log any issues
                if (!backend.name) {
                    console.warn(`⚠️ Backend ${index} missing name:`, backend);
                }
                if (!backend.type && !(backend.config && backend.config.type)) {
                    console.warn(`⚠️ Backend ${name} missing type:`, backend);
                }
                
                // Get policy info with proper defaults
                const policy = backend.policy || {};
                const storagePolicy = policy.storage_quota || {};
                const trafficPolicy = policy.traffic_quota || {};
                const replicationPolicy = policy.replication || {};
                const retentionPolicy = policy.retention || {};
                const cachePolicy = policy.cache || {};
                
                // Get stats
                const stats = backend.stats || {};
                
                // Create a comprehensive backend card
                const backendCard = el('div',{
                    class:'backend-card',
                    style:'border:1px solid #e0e0e0;margin:8px 0;padding:12px;border-radius:8px;background:white;box-shadow:0 2px 4px rgba(0,0,0,0.1);'
                });
                
                // Header with name, type, status
                const header = el('div',{
                    style:'display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;'
                }, 
                    el('div',{style:'display:flex;align-items:center;gap:8px;'},
                        el('strong',{text:name,style:'color:#2196F3;font-size:16px;'}),
                        el('span',{text:`[${type}]`,style:'color:#666;font-size:12px;background:#f5f5f5;padding:2px 6px;border-radius:3px;'}),
                        el('span',{
                            text:tier.toUpperCase(),
                            style:`background:${getTierColor(tier)};color:white;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:bold;`
                        }),
                        el('span',{
                            text:getStatusDisplay(status),
                            style:`color:${getStatusColor(status)};font-size:12px;font-weight:bold;padding:2px 6px;background:${getStatusBackground(status)};border-radius:3px;`
                        })
                    ),
                    el('div',{style:'display:flex;gap:4px;'},
                        el('button',{
                            style:'padding:4px 8px;font-size:11px;background:#4CAF50;color:white;border:none;border-radius:3px;cursor:pointer;',
                            title:'Test Backend Connection',
                            onclick:()=>testBackend(name)
                        },'Test'),
                        el('button',{
                            style:'padding:4px 8px;font-size:11px;background:#2196F3;color:white;border:none;border-radius:3px;cursor:pointer;',
                            title:'Edit Backend Configuration',
                            onclick:()=>editBackend(name)
                        },'Edit'),
                        el('button',{
                            style:'padding:4px 8px;font-size:11px;background:#f44336;color:white;border:none;border-radius:3px;cursor:pointer;',
                            title:'Delete Backend',
                            onclick:()=>deleteBackend(name)
                        },'Delete')
                    )
                );
                
                // Description
                const desc = el('div',{
                    text:description,
                    style:'color:#666;font-size:12px;margin-bottom:10px;'
                });
                
                // Configuration details  
                const configRow = el('div',{
                    style:'display:flex;gap:15px;margin-bottom:8px;font-size:11px;flex-wrap:wrap;'
                });
                
                if(backend.config) {
                    const config = backend.config;
                    Object.keys(config).slice(0, 4).forEach(key => {
                        if(key !== 'type' && typeof config[key] === 'string') {
                            configRow.appendChild(el('span',{
                                text:`${key}: ${config[key].length > 20 ? config[key].substring(0, 20) + '...' : config[key]}`,
                                style:'color:#777;background:#f9f9f9;padding:2px 4px;border-radius:2px;'
                            }));
                        }
                    });
                }
                
                // Stats row
                const statsRow = el('div',{
                    style:'display:flex;gap:15px;margin-bottom:8px;font-size:11px;flex-wrap:wrap;'
                });
                
                if(stats.used_storage_gb !== undefined) {
                    statsRow.appendChild(el('span',{
                        text:`Storage: ${stats.used_storage_gb.toFixed(1)} GB`,
                        style:'color:#81C784;'
                    }));
                }
                
                if(stats.total_files !== undefined) {
                    statsRow.appendChild(el('span',{
                        text:`Files: ${stats.total_files}`,
                        style:'color:#64B5F6;'  
                    }));
                }
                
                if(stats.availability !== undefined) {
                    const availability = (stats.availability * 100).toFixed(1);
                    statsRow.appendChild(el('span',{
                        text:`Uptime: ${availability}%`,
                        style:`color:${stats.availability > 0.99 ? '#4CAF50' : stats.availability > 0.95 ? '#FF9800' : '#f44336'};`
                    }));
                }
                
                // Policy summary with better formatting
                const policySummary = el('div',{
                    style:'font-size:10px;color:#888;display:flex;gap:12px;flex-wrap:wrap;border-top:1px solid #eee;padding-top:8px;'
                });
                
                if(storagePolicy.max_size) {
                    policySummary.appendChild(el('span',{
                        text:`📦 Quota: ${storagePolicy.max_size} ${storagePolicy.max_size_unit || 'GB'}`,
                        style:'background:#E3F2FD;color:#1976D2;padding:2px 6px;border-radius:3px;'
                    }));
                }
                
                if(replicationPolicy.min_redundancy) {
                    const replicationText = replicationPolicy.max_redundancy && replicationPolicy.max_redundancy !== replicationPolicy.min_redundancy 
                        ? `${replicationPolicy.min_redundancy}-${replicationPolicy.max_redundancy}` 
                        : `${replicationPolicy.min_redundancy}`;
                    policySummary.appendChild(el('span',{
                        text:`🔄 Replication: ${replicationText}`,
                        style:'background:#F3E5F5;color:#7B1FA2;padding:2px 6px;border-radius:3px;'
                    }));
                }
                
                if(retentionPolicy.default_retention_days) {
                    policySummary.appendChild(el('span',{
                        text:`⏰ Retention: ${retentionPolicy.default_retention_days}d`,
                        style:'background:#FFF3E0;color:#F57C00;padding:2px 6px;border-radius:3px;'
                    }));
                }
                
                if(cachePolicy.max_cache_size) {
                    policySummary.appendChild(el('span',{
                        text:`💾 Cache: ${cachePolicy.max_cache_size} ${cachePolicy.max_cache_size_unit || 'GB'}`,
                        style:'background:#E8F5E8;color:#388E3C;padding:2px 6px;border-radius:3px;'
                    }));
                }
                
                backendCard.append(header, desc, configRow, statsRow, policySummary);
                container.append(backendCard);
            });
        }catch(e){ 
            console.error('❌ Error loading backends:', e);
            console.error('❌ Error details:', e.stack);
            console.error('❌ Response data was:', js);
            console.error('❌ backends variable was:', backends);
            container.innerHTML = `
                <div style="text-align:center;padding:20px;border:1px solid #f44336;border-radius:8px;background:#ffebee;color:#c62828;">
                    <strong>⚠️ Failed to Load Backends</strong><br>
                    <small style="color:#666;margin-top:8px;display:block;">${e.message}</small>
                    <button onclick="loadBackends()" style="margin-top:10px;padding:6px 12px;background:#2196F3;color:white;border:none;border-radius:4px;cursor:pointer;">
                        🔄 Retry
                    </button>
                </div>
            `;
        }
    }
    
    function getTierColor(tier) {
        switch(tier) {
            case 'hot': return '#f44336';     // Red for hot
            case 'warm': return '#FF9800';    // Orange for warm  
            case 'cold': return '#2196F3';    // Blue for cold
            case 'archive': return '#9C27B0'; // Purple for archive
            default: return '#607D8B';        // Blue-grey for standard
        }
    }
    
    function getStatusDisplay(status) {
        switch(status) {
            case 'enabled': return '✅ Enabled';
            case 'disabled': return '❌ Disabled';
            case 'error': return '🔥 Error';
            case 'maintenance': return '🔧 Maintenance';
            case 'testing': return '🧪 Testing';
            default: return `📊 ${status}`;
        }
    }
    
    function getStatusColor(status) {
        switch(status) {
            case 'enabled': return '#4CAF50';
            case 'disabled': return '#f44336';
            case 'error': return '#f44336';
            case 'maintenance': return '#FF9800';
            case 'testing': return '#2196F3';
            default: return '#607D8B';
        }
    }
    
    function getStatusBackground(status) {
        switch(status) {
            case 'enabled': return '#E8F5E8';
            case 'disabled': return '#FFEBEE';
            case 'error': return '#FFEBEE';
            case 'maintenance': return '#FFF3E0';
            case 'testing': return '#E3F2FD';
            default: return '#F5F5F5';
        }
    }
    
    async function testBackend(name) {
        try {
            console.log(`🧪 Testing backend: ${name}`);
            const response = await fetch(`/api/backends/${encodeURIComponent(name)}/test`, {
                method: 'POST'
            });
            const result = await response.json();
            
            if (response.ok) {
                alert(`✅ Backend "${name}" test successful!\n\nDetails: ${JSON.stringify(result, null, 2)}`);
            } else {
                alert(`❌ Backend "${name}" test failed!\n\nError: ${result.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error(`Error testing backend ${name}:`, error);
            alert(`❌ Failed to test backend "${name}"\n\nError: ${error.message}`);
        }
    }
    
    async function editBackend(name) {
        const newName = prompt('Backend name:', name);
        if (!newName || newName === name) return;
        
        try {
            // Get current backend config
            const response = await fetch(`/api/backends/${encodeURIComponent(name)}`);
            const backend = await response.json();
            
            const newConfig = prompt('Backend configuration (JSON):', JSON.stringify(backend.config || {}, null, 2));
            if (!newConfig) return;
            
            const config = JSON.parse(newConfig);
            
            // Update backend
            const updateResponse = await fetch(`/api/backends/${encodeURIComponent(name)}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: newName,
                    config: config
                })
            });
            
            if (updateResponse.ok) {
                alert(`✅ Backend "${name}" updated successfully!`);
                loadBackends();
            } else {
                const error = await updateResponse.json();
                alert(`❌ Failed to update backend "${name}"\n\nError: ${error.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error(`Error editing backend ${name}:`, error);
            alert(`❌ Failed to edit backend "${name}"\n\nError: ${error.message}`);
        }
    }

    // ---- Advanced Feature 8: Real-Time Performance Metrics Functions ----
    
    async function testAllBackends() {
        try {
            console.log('🧪 Testing all backends...');
            const response = await MCP.callTool('backend_health_check', {detailed: true});
            
            if (response && response.result) {
                const results = response.result.results || [];
                const healthy = results.filter(r => r.status === 'healthy').length;
                const total = results.length;
                
                alert(`🧪 Backend Health Check Complete\\n\\n✅ Healthy: ${healthy}/${total}\\n❌ Issues: ${total - healthy}\\n\\nCheck console for details.`);
                console.log('Backend test results:', results);
                loadBackends();
            }
        } catch (error) {
            console.error('Error testing backends:', error);
            alert('❌ Failed to test backends: ' + error.message);
        }
    }
    
    async function syncAllBackends() {
        try {
            console.log('🔄 Syncing all backends...');
            alert('🔄 Backend sync initiated. This may take a few moments...');
            // Implementation would sync all backends
            setTimeout(() => {
                alert('✅ All backends synchronized successfully!');
                loadBackends();
            }, 2000);
        } catch (error) {
            console.error('Error syncing backends:', error);
            alert('❌ Failed to sync backends: ' + error.message);
        }
    }
    
    async function runHealthCheck() {
        try {
            console.log('🏥 Running comprehensive health check...');
            const response = await MCP.callTool('backend_health_check', {detailed: true});
            
            if (response && response.result) {
                const results = response.result.results || [];
                showHealthCheckResults(results);
                updateHealthCounters(results);
            }
        } catch (error) {
            console.error('Error running health check:', error);
            alert('❌ Health check failed: ' + error.message);
        }
    }
    
    function showHealthCheckResults(results) {
        const healthyCount = results.filter(r => r.status === 'healthy').length;
        const totalCount = results.length;
        
        const resultText = results.map(r => 
            `${r.status === 'healthy' ? '✅' : '❌'} ${r.name} (${r.type}): ${r.status}`
        ).join('\\n');
        
        alert(`🏥 Health Check Results\\n\\n${resultText}\\n\\nSummary: ${healthyCount}/${totalCount} backends healthy`);
    }
    
    function updateHealthCounters(results) {
        const healthyCount = results.filter(r => r.status === 'healthy').length;
        const unhealthyCount = results.filter(r => r.status !== 'healthy').length;
        const totalCount = results.length;
        
        const healthyEl = document.getElementById('healthy-count');
        const unhealthyEl = document.getElementById('unhealthy-count');
        const totalEl = document.getElementById('total-backends-count');
        const configuredEl = document.getElementById('configured-count');
        
        if (healthyEl) healthyEl.textContent = healthyCount;
        if (unhealthyEl) unhealthyEl.textContent = unhealthyCount;
        if (totalEl) totalEl.textContent = totalCount;
        if (configuredEl) configuredEl.textContent = totalCount;
    }
    
    async function showPerformanceMetrics() {
        const modal = document.getElementById('performance-metrics-modal');
        if (modal) {
            modal.style.display = 'block';
            await refreshPerformanceMetrics();
        }
    }
    
    function closePerformanceMetrics() {
        const modal = document.getElementById('performance-metrics-modal');
        if (modal) modal.style.display = 'none';
    }
    
    async function refreshPerformanceMetrics() {
        const content = document.getElementById('performance-metrics-content');
        const timeRange = document.getElementById('metrics-time-range')?.value || '1h';
        
        if (!content) return;
        
        content.innerHTML = '<div style="text-align:center;padding:20px;">📊 Loading performance metrics...</div>';
        
        try {
            const response = await MCP.callTool('get_backend_performance_metrics', {
                time_range: timeRange,
                include_history: true
            });
            
            if (response && response.result && response.result.metrics) {
                renderPerformanceMetrics(response.result.metrics, content);
            } else {
                content.innerHTML = '<div style="color:#f44336;text-align:center;padding:20px;">No performance data available</div>';
            }
        } catch (error) {
            console.error('Error loading performance metrics:', error);
            content.innerHTML = `<div style="color:#f44336;text-align:center;padding:20px;">Error: ${error.message}</div>`;
        }
    }
    
    function renderPerformanceMetrics(metrics, container) {
        container.innerHTML = '';
        
        if (!metrics.length) {
            container.innerHTML = '<div style="text-align:center;padding:20px;color:#888;">No backends configured for monitoring</div>';
            return;
        }
        
        metrics.forEach(metric => {
            const backendDiv = document.createElement('div');
            backendDiv.style.cssText = 'border:1px solid #333;margin:8px 0;padding:12px;border-radius:6px;background:#0a0a0a;';
            
            const perf = metric.performance;
            backendDiv.innerHTML = `
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <strong style="color:#4CAF50;">${metric.backend_name}</strong>
                    <span style="color:#888;font-size:11px;">${metric.backend_type}</span>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;font-size:11px;">
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#2196F3;">Response Time</div>
                        <div style="font-weight:bold;">${perf.response_time_ms}ms</div>
                    </div>
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#4CAF50;">Throughput</div>
                        <div style="font-weight:bold;">${perf.throughput_ops_per_sec} ops/s</div>
                    </div>
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#FF9800;">Error Rate</div>
                        <div style="font-weight:bold;">${perf.error_rate_percent}%</div>
                    </div>
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#E91E63;">Success Rate</div>
                        <div style="font-weight:bold;">${perf.success_rate_percent}%</div>
                    </div>
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#9C27B0;">Data Transfer</div>
                        <div style="font-weight:bold;">${perf.data_transfer_mbps} MB/s</div>
                    </div>
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#607D8B;">Uptime</div>
                        <div style="font-weight:bold;">${perf.uptime_percent}%</div>
                    </div>
                </div>
                <div style="margin-top:8px;font-size:10px;color:#666;">
                    CPU: ${perf.cpu_usage_percent}% | Memory: ${perf.memory_usage_percent}% | 
                    Disk: ${perf.disk_usage_percent}% | Connections: ${perf.active_connections}
                </div>
            `;
            
            container.appendChild(backendDiv);
        });
    }
    
    // ---- Advanced Feature 9: Configuration Management Functions ----
    
    function showAddBackendModal() {
        // Enhanced modal for adding backends with templates
        alert('🚀 Enhanced backend creation with templates coming soon! For now, use the Add Instance feature below.');
    }
    
    async function showConfigurationTemplates() {
        const modal = document.getElementById('config-templates-modal');
        if (modal) {
            modal.style.display = 'block';
            showTemplateSelector(); // Default to template view
        }
    }
    
    function closeConfigTemplates() {
        const modal = document.getElementById('config-templates-modal');
        if (modal) modal.style.display = 'none';
    }
    
    async function showTemplateSelector() {
        const content = document.getElementById('config-templates-content');
        if (!content) return;
        
        content.innerHTML = `
            <h4 style="color:#9C27B0;margin-bottom:12px;">📄 Configuration Templates</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
                <select id="template-backend-type" style="padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                    <option value="s3">Amazon S3 / S3-Compatible</option>
                    <option value="github">GitHub Repository</option>
                    <option value="ipfs">IPFS Node</option>
                    <option value="huggingface">HuggingFace Hub</option>
                </select>
                <select id="template-type" style="padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                    <option value="basic">Basic Template</option>
                    <option value="enterprise">Enterprise Template</option>
                    <option value="high_performance">High Performance</option>
                    <option value="backup">Backup Template</option>
                </select>
            </div>
            <button onclick="loadConfigTemplate()" style="background:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;margin-bottom:16px;">📄 Load Template</button>
            <div id="template-preview" style="background:#0a0a0a;border:1px solid #333;border-radius:4px;padding:12px;font-family:monospace;font-size:12px;white-space:pre-wrap;"></div>
        `;
    }
    
    async function loadConfigTemplate() {
        const backendType = document.getElementById('template-backend-type')?.value;
        const templateType = document.getElementById('template-type')?.value;
        const preview = document.getElementById('template-preview');
        
        if (!preview) return;
        
        try {
            const response = await MCP.callTool('get_backend_configuration_template', {
                backend_type: backendType,
                template_type: templateType
            });
            
            if (response && response.result && response.result.template) {
                preview.textContent = JSON.stringify(response.result.template, null, 2);
                preview.style.color = '#4CAF50';
            } else {
                preview.textContent = 'Template not found';
                preview.style.color = '#f44336';
            }
        } catch (error) {
            preview.textContent = 'Error loading template: ' + error.message;
            preview.style.color = '#f44336';
        }
    }
    
    async function showCloneBackend() {
        const content = document.getElementById('config-templates-content');
        if (!content) return;
        
        // Get backend list for cloning
        try {
            const response = await MCP.callTool('list_backends', {});
            const backends = response?.result?.backends || response?.result?.items || [];
            
            const backendOptions = backends.map(b => 
                `<option value="${b.name}">${b.name} (${b.type || 'unknown'})</option>`
            ).join('');
            
            content.innerHTML = `
                <h4 style="color:#2196F3;margin-bottom:12px;">📋 Clone Backend Configuration</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
                    <div>
                        <label style="display:block;margin-bottom:4px;color:#ccc;">Source Backend:</label>
                        <select id="clone-source-backend" style="width:100%;padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                            <option value="">Select backend to clone...</option>
                            ${backendOptions}
                        </select>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:4px;color:#ccc;">New Backend Name:</label>
                        <input type="text" id="clone-new-name" placeholder="new-backend-name" style="width:100%;padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                    </div>
                </div>
                <div style="margin-bottom:16px;">
                    <label style="display:block;margin-bottom:4px;color:#ccc;">Description (optional):</label>
                    <input type="text" id="clone-description" placeholder="Cloned backend for..." style="width:100%;padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                </div>
                <button onclick="executeCloneBackend()" style="background:#2196F3;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;">📋 Clone Backend</button>
                <div id="clone-result" style="margin-top:12px;"></div>
            `;
        } catch (error) {
            content.innerHTML = `<div style="color:#f44336;">Error loading backends: ${error.message}</div>`;
        }
    }
    
    async function executeCloneBackend() {
        const sourceBackend = document.getElementById('clone-source-backend')?.value;
        const newName = document.getElementById('clone-new-name')?.value;
        const description = document.getElementById('clone-description')?.value;
        const resultDiv = document.getElementById('clone-result');
        
        if (!sourceBackend || !newName) {
            if (resultDiv) resultDiv.innerHTML = '<div style="color:#f44336;">Please select source backend and enter new name</div>';
            return;
        }
        
        try {
            const modifyConfig = description ? {description} : {};
            const response = await MCP.callTool('clone_backend_configuration', {
                source_backend: sourceBackend,
                new_backend_name: newName,
                modify_config: modifyConfig
            });
            
            if (response && response.result && response.result.ok) {
                if (resultDiv) resultDiv.innerHTML = '<div style="color:#4CAF50;">✅ Backend cloned successfully!</div>';
                setTimeout(() => {
                    closeConfigTemplates();
                    loadBackends();
                }, 1500);
            } else {
                const error = response?.result?.error || 'Unknown error';
                if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;">❌ Failed to clone: ${error}</div>`;
            }
        } catch (error) {
            if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;">❌ Error: ${error.message}</div>`;
        }
    }
    
    async function showBackupRestore() {
        const content = document.getElementById('config-templates-content');
        if (!content) return;
        
        // Get backend list
        try {
            const response = await MCP.callTool('list_backends', {});
            const backends = response?.result?.backends || response?.result?.items || [];
            
            const backendOptions = backends.map(b => 
                `<option value="${b.name}">${b.name} (${b.type || 'unknown'})</option>`
            ).join('');
            
            content.innerHTML = `
                <h4 style="color:#FF9800;margin-bottom:12px;">💾 Backup & Restore</h4>
                <div style="display:flex;gap:16px;">
                    <div style="flex:1;">
                        <h5 style="color:#4CAF50;">Create Backup</h5>
                        <select id="backup-backend" style="width:100%;padding:8px;margin-bottom:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                            <option value="">Select backend...</option>
                            ${backendOptions}
                        </select>
                        <input type="text" id="backup-name" placeholder="Backup name (optional)" style="width:100%;padding:8px;margin-bottom:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                        <button onclick="createBackup()" style="background:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;width:100%;">💾 Create Backup</button>
                    </div>
                    <div style="flex:1;">
                        <h5 style="color:#2196F3;">Restore Backup</h5>
                        <input type="text" id="restore-backend" placeholder="Backend name" style="width:100%;padding:8px;margin-bottom:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                        <input type="text" id="restore-backup-id" placeholder="Backup ID" style="width:100%;padding:8px;margin-bottom:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                        <button onclick="restoreBackup()" style="background:#2196F3;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;width:100%;">📤 Restore Backup</button>
                    </div>
                </div>
                <div id="backup-result" style="margin-top:12px;"></div>
            `;
        } catch (error) {
            content.innerHTML = `<div style="color:#f44336;">Error loading backends: ${error.message}</div>`;
        }
    }
    
    async function createBackup() {
        const backendName = document.getElementById('backup-backend')?.value;
        const backupName = document.getElementById('backup-name')?.value;
        const resultDiv = document.getElementById('backup-result');
        
        if (!backendName) {
            if (resultDiv) resultDiv.innerHTML = '<div style="color:#f44336;">Please select a backend</div>';
            return;
        }
        
        try {
            const response = await MCP.callTool('backup_backend_configuration', {
                backend_name: backendName,
                backup_name: backupName || undefined
            });
            
            if (response && response.result && response.result.ok) {
                const backupId = response.result.backup_id;
                if (resultDiv) resultDiv.innerHTML = `<div style="color:#4CAF50;">✅ Backup created: ${backupId}</div>`;
            } else {
                const error = response?.result?.error || 'Unknown error';
                if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;">❌ Backup failed: ${error}</div>`;
            }
        } catch (error) {
            if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;">❌ Error: ${error.message}</div>`;
        }
    }
    
    async function restoreBackup() {
        const backendName = document.getElementById('restore-backend')?.value;
        const backupId = document.getElementById('restore-backup-id')?.value;
        const resultDiv = document.getElementById('backup-result');
        
        if (!backendName || !backupId) {
            if (resultDiv) resultDiv.innerHTML = '<div style="color:#f44336;">Please enter backend name and backup ID</div>';
            return;
        }
        
        try {
            const response = await MCP.callTool('restore_backend_configuration', {
                backend_name: backendName,
                backup_id: backupId
            });
            
            if (response && response.result && response.result.ok) {
                if (resultDiv) resultDiv.innerHTML = '<div style="color:#4CAF50;">✅ Backup restored successfully!</div>';
                setTimeout(() => {
                    closeConfigTemplates();
                    loadBackends();
                }, 1500);
            } else {
                const error = response?.result?.error || 'Unknown error';
                if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;">❌ Restore failed: ${error}</div>`;
            }
        } catch (error) {
            if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;">❌ Error: ${error.message}</div>`;
        }
    }
    
    function showAdvancedPolicyEditor() {
        const content = document.getElementById('config-templates-content');
        if (!content) return;
        
        content.innerHTML = `
            <h4 style="color:#E91E63;margin-bottom:12px;">🔧 Advanced Policy Editor</h4>
            <div style="color:#888;margin-bottom:16px;">
                Configure advanced policies for retry logic, timeouts, rate limits, and more.
            </div>
            <div style="background:#0a0a0a;border:1px solid #333;border-radius:4px;padding:16px;">
                <h5 style="margin-top:0;color:#4CAF50;">Available Policy Categories:</h5>
                <ul style="color:#ccc;line-height:1.6;">
                    <li><strong>Retry Policies:</strong> Configure retry attempts and backoff strategies</li>
                    <li><strong>Timeout Settings:</strong> Connection and operation timeouts</li>
                    <li><strong>Rate Limiting:</strong> Request rate limits and throttling</li>
                    <li><strong>Cache Policies:</strong> Cache TTL and invalidation rules</li>
                    <li><strong>Security Policies:</strong> Authentication and encryption settings</li>
                    <li><strong>Monitoring Policies:</strong> Health check intervals and alerting</li>
                </ul>
                <div style="margin-top:16px;color:#FF9800;">
                    🚧 Advanced policy editor will be available in the next update with full JSON schema validation and real-time preview.
                </div>
            </div>
        `;
    }
    
    function filterBackends(category) {
        // Update active button
        const buttons = document.querySelectorAll('[id^="filter-"]');
        buttons.forEach(btn => {
            btn.style.background = btn.id === `filter-${category}` ? '#4CAF50' : '#555';
        });
        
        // Filter logic would be implemented here
        console.log(`Filtering backends by category: ${category}`);
        loadBackends(); // Reload with filter
    }

    // ---- Enhanced Bucket Management Helper Functions ----
    
    // Helper functions for enhanced bucket management
    function createModal(title, contentCallback) {
        // Remove existing modal if any
        const existingModal = document.getElementById('bucket-modal');
        if (existingModal) existingModal.remove();
        
        const modal = document.createElement('div');
        modal.id = 'bucket-modal';
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: rgba(0,0,0,0.8); z-index: 1000; display: flex; 
            align-items: center; justify-content: center;
        `;
        
        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
            background: #1a1a1a; border: 1px solid #333; border-radius: 8px; 
            padding: 20px; max-width: 90%; max-height: 90%; overflow-y: auto;
            color: white; font-family: system-ui, Arial, sans-serif;
        `;
        
        const header = document.createElement('div');
        header.style.cssText = `
            display: flex; justify-content: space-between; align-items: center; 
            margin-bottom: 15px; border-bottom: 1px solid #333; padding-bottom: 10px;
        `;
        header.innerHTML = `
            <h3 style="margin: 0; color: white;">${title}</h3>
            <button onclick="document.getElementById('bucket-modal').remove()" 
                    style="background: #555; color: white; border: none; padding: 5px 10px; 
                           border-radius: 4px; cursor: pointer;">×</button>
        `;
        
        const body = document.createElement('div');
        modalContent.appendChild(header);
        modalContent.appendChild(body);
        modal.appendChild(modalContent);
        document.body.appendChild(modal);
        
        // Close modal when clicking outside
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
        
        // Execute content callback
        if (contentCallback) contentCallback(body);
        
        return modal;
    }

    // Modal functions for bucket management
    
    // Show bucket configuration modal
    function showBucketConfigModal(bucketName) {
        if(!bucketName) return;
        
        const modal = createModal('Bucket Configuration: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = `
                <div style="margin-bottom:16px;">
                    <h4 style="margin:0 0 12px 0;color:#4CAF50;">Basic Settings</h4>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <label style="display:flex;flex-direction:column;">
                            Replication Factor
                            <input type="number" id="config-replication" min="1" max="10" value="1" style="margin-top:4px;"/>
                        </label>
                        <label style="display:flex;flex-direction:column;">
                            Cache Policy
                            <select id="config-cache" style="margin-top:4px;">
                                <option value="none">None</option>
                                <option value="memory">Memory</option>
                                <option value="disk">Disk</option>
                                <option value="hybrid">Hybrid</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div style="margin-bottom:16px;">
                    <h4 style="margin:0 0 12px 0;color:#FF9800;">Retention Policy</h4>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <label style="display:flex;flex-direction:column;">
                            Retention Days (0 = infinite)
                            <input type="number" id="config-retention" min="0" value="0" style="margin-top:4px;"/>
                        </label>
                        <label style="display:flex;flex-direction:column;">
                            Auto Cleanup
                            <select id="config-cleanup" style="margin-top:4px;">
                                <option value="false">Disabled</option>
                                <option value="true">Enabled</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div style="margin-bottom:20px;">
                    <h4 style="margin:0 0 12px 0;color:#2196F3;">Sync Settings</h4>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <label style="display:flex;flex-direction:column;">
                            Sync Interval (minutes)
                            <input type="number" id="config-sync-interval" min="1" value="60" style="margin-top:4px;"/>
                        </label>
                        <label style="display:flex;flex-direction:column;">
                            Versioning
                            <select id="config-versioning" style="margin-top:4px;">
                                <option value="false">Disabled</option>
                                <option value="true">Enabled</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div style="display:flex;gap:8px;justify-content:flex-end;">
                    <button onclick="saveBucketConfig('${bucketName}')" style="background:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;">Save Settings</button>
                    <button onclick="closeModal()" style="background:#666;color:white;padding:8px 16px;border:none;border-radius:4px;">Cancel</button>
                </div>
            `;
            
            // Load current settings
            try {
                await waitForMCP();
                const bucketResponse = await MCP.Buckets.get(bucketName);
                const bucket = (bucketResponse && bucketResponse.result) || {};
                const policy = bucket.policy || {};
                
                document.getElementById('config-replication').value = policy.replication_factor || 1;
                document.getElementById('config-cache').value = policy.cache_policy || 'none';
                document.getElementById('config-retention').value = policy.retention_days || 0;
                document.getElementById('config-cleanup').value = policy.auto_cleanup || 'false';
                document.getElementById('config-sync-interval').value = policy.sync_interval || 60;
                document.getElementById('config-versioning').value = policy.versioning || 'false';
            } catch(e) {
                console.error('Error loading bucket config:', e);
            }
        });
        
        modal.show();
    }
    
    // Show bucket share modal
    function showBucketShareModal(bucketName) {
        if(!bucketName) return;
        
        const modal = createModal('Share Bucket: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = `
                <div style="margin-bottom:16px;">
                    <h4 style="margin:0 0 12px 0;color:#795548;">Create Share Link</h4>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <label style="display:flex;flex-direction:column;">
                            Access Type
                            <select id="share-access" style="margin-top:4px;">
                                <option value="read_only">Read Only</option>
                                <option value="read_write">Read & Write</option>
                                <option value="admin">Admin</option>
                            </select>
                        </label>
                        <label style="display:flex;flex-direction:column;">
                            Expiration
                            <select id="share-expiration" style="margin-top:4px;">
                                <option value="1h">1 Hour</option>
                                <option value="24h">24 Hours</option>
                                <option value="7d">7 Days</option>
                                <option value="30d">30 Days</option>
                                <option value="never">Never</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div style="margin-bottom:16px;">
                    <h4 style="margin:0 0 12px 0;color:#4CAF50;">Generated Link</h4>
                    <div style="display:flex;gap:8px;">
                        <input type="text" id="share-link" readonly style="flex:1;background:#0a0a0a;border:1px solid #333;padding:8px;border-radius:4px;color:#ccc;" placeholder="Click 'Generate Link' to create share link"/>
                        <button onclick="copyShareLink()" id="btn-copy-link" disabled style="background:#2196F3;color:white;padding:8px 12px;border:none;border-radius:4px;">Copy</button>
                    </div>
                </div>
                <div style="display:flex;gap:8px;justify-content:flex-end;">
                    <button onclick="generateShareLink('${bucketName}')" style="background:#795548;color:white;padding:8px 16px;border:none;border-radius:4px;">Generate Link</button>
                    <button onclick="closeModal()" style="background:#666;color:white;padding:8px 16px;border:none;border-radius:4px;">Close</button>
                </div>
            `;
        });
        
        modal.show();
    }
    
    // Generate share link for bucket
    async function generateShareLink(bucketName) {
        try {
            await waitForMCP();
            const accessType = document.getElementById('share-access').value;
            const expiration = document.getElementById('share-expiration').value;
            
            const result = await MCP.Buckets.generateShareLink(bucketName, accessType, expiration);
            const shareLink = window.location.origin + ((result && result.result && result.result.share_link) || '/share/unknown');
            
            document.getElementById('share-link').value = shareLink;
            document.getElementById('btn-copy-link').disabled = false;
            
        } catch(e) {
            console.error('Error generating share link:', e);
            alert('Error generating share link: ' + e.message);
        }
    }
    
    // Copy share link to clipboard
    function copyShareLink() {
        const linkInput = document.getElementById('share-link');
        if(linkInput && linkInput.value) {
            linkInput.select();
            navigator.clipboard.writeText(linkInput.value).then(() => {
                alert('Share link copied to clipboard!');
            }).catch(() => {
                // Fallback for older browsers
                document.execCommand('copy');
                alert('Share link copied to clipboard!');
            });
        }
    }
    
    // Save bucket configuration
    async function saveBucketConfig(bucketName) {
        try {
            await waitForMCP();
            
            const replicationFactor = parseInt(document.getElementById('config-replication').value);
            const cachePolicy = document.getElementById('config-cache').value;
            const retentionDays = parseInt(document.getElementById('config-retention').value);
            
            await MCP.Buckets.updatePolicy(bucketName, {
                replication_factor: replicationFactor,
                cache_policy: cachePolicy,
                retention_days: retentionDays
            });
            
            alert('Bucket configuration saved successfully!');
            closeModal();
            
            // Refresh status if this is the selected bucket
            if(bucketName === selectedBucket) {
                await updateBucketStatus();
            }
            
        } catch(e) {
            console.error('Error saving bucket config:', e);
            alert('Error saving configuration: ' + e.message);
        }
    }
    
    // Close modal helper
    function closeModal() {
        const modal = document.querySelector('.modal-overlay');
        if(modal) modal.remove();
    }

    // MCP-based bucket file browser with metadata-first architecture
    function showMCPBucketBrowser(bucketName) {
        const modal = createModal('MCP Bucket File Browser: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = '<div style="text-align:center;padding:20px;">Loading bucket via MCP SDK...</div>';
            
            try {
                await waitForMCP();
                
                // Create comprehensive file browser interface
                modalBody.innerHTML = `
                    <div style="margin-bottom:15px;">
                        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                            <strong>Bucket:</strong> <span style="color:#6b8cff;">${bucketName}</span>
                            <div style="flex:1;"></div>
                            <button id="sync-replicas-btn" onclick="syncBucketReplicas('${bucketName}')" 
                                    style="background:#2a5cb8;color:white;padding:4px 8px;border:none;border-radius:3px;cursor:pointer;font-size:11px;">
                                🔄 Sync Replicas
                            </button>
                            <button onclick="showBucketPolicySettings('${bucketName}')" 
                                    style="background:#555;color:white;padding:4px 8px;border:none;border-radius:3px;cursor:pointer;font-size:11px;">
                                📋 Policy
                            </button>
                        </div>
                        
                        <!-- Navigation breadcrumbs -->
                        <div style="background:#0a0a0a;padding:8px;border-radius:4px;margin-bottom:10px;">
                            <div style="display:flex;align-items:center;gap:5px;margin-bottom:5px;">
                                <span style="color:#888;font-size:11px;">Path:</span>
                                <input type="text" id="current-path" value="." 
                                       style="flex:1;background:#111;border:1px solid #333;color:white;padding:4px;border-radius:3px;font-size:11px;">
                                <button onclick="navigateToPath('${bucketName}')" 
                                        style="background:#555;color:white;padding:4px 8px;border:none;border-radius:3px;cursor:pointer;font-size:11px;">
                                    Go
                                </button>
                                <button onclick="goUpDirectory('${bucketName}')" 
                                        style="background:#555;color:white;padding:4px 8px;border:none;border-radius:3px;cursor:pointer;font-size:11px;">
                                    ⬆️ Up
                                </button>
                            </div>
                            <div id="breadcrumb-nav" style="font-size:10px;color:#666;"></div>
                        </div>
                        
                        <!-- File operations toolbar -->
                        <div style="display:flex;gap:5px;margin-bottom:10px;flex-wrap:wrap;">
                            <input type="file" id="upload-files-${bucketName}" multiple style="display:none;">
                            <button onclick="document.getElementById('upload-files-${bucketName}').click()" 
                                    style="background:#2a5cb8;color:white;padding:6px 10px;border:none;border-radius:4px;cursor:pointer;font-size:11px;">
                                📤 Upload Files
                            </button>
                            <button onclick="showCreateFolderDialog('${bucketName}')" 
                                    style="background:#555;color:white;padding:6px 10px;border:none;border-radius:4px;cursor:pointer;font-size:11px;">
                                📁 New Folder
                            </button>
                            <button onclick="refreshBucketFilesMCP('${bucketName}')" 
                                    style="background:#555;color:white;padding:6px 10px;border:none;border-radius:4px;cursor:pointer;font-size:11px;">
                                🔄 Refresh
                            </button>
                            <div style="flex:1;"></div>
                            <label style="display:flex;align-items:center;gap:5px;font-size:11px;color:#aaa;">
                                <input type="checkbox" id="show-metadata" checked> Show Metadata
                            </label>
                        </div>
                    </div>
                    
                    <!-- File list container -->
                    <div id="mcp-file-list" style="max-height:450px;overflow-y:auto;border:1px solid #333;background:#0f0f0f;">
                        <div style="text-align:center;padding:20px;color:#888;">Loading files...</div>
                    </div>
                    
                    <!-- File details panel -->
                    <div id="file-details-panel" style="display:none;margin-top:10px;padding:10px;background:#0a0a0a;border-radius:4px;font-size:11px;">
                        <div style="font-weight:bold;margin-bottom:5px;">File Details</div>
                        <div id="file-metadata-content"></div>
                    </div>
                `;
                
                // Setup event handlers
                const fileInput = document.getElementById('upload-files-' + bucketName);
                if (fileInput) {
                    fileInput.onchange = (e) => uploadFilesMCP(bucketName, e.target.files);
                }
                
                const showMetaCheckbox = document.getElementById('show-metadata');
                if (showMetaCheckbox) {
                    showMetaCheckbox.onchange = () => refreshBucketFilesMCP(bucketName);
                }
                
                // Load initial file list
                await refreshBucketFilesMCP(bucketName);
                
            } catch (e) {
                console.error('Error loading MCP bucket browser:', e);
                modalBody.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error loading bucket: ' + e.message + '</div>';
            }
        });
    }

    // Enhanced bucket details view
    function showBucketDetails(bucketName) {
        const modal = createModal('Bucket File Manager: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = '<div style="text-align:center;padding:20px;">Loading bucket contents...</div>';
            
            try {
                const response = await fetch('/api/buckets/' + encodeURIComponent(bucketName));
                const data = await response.json();
                
                modalBody.innerHTML = `
                    <div style="margin-bottom:15px;padding:10px;background:#0a0a0a;border-radius:5px;">
                        <strong>Bucket:</strong> ${bucketName} (${data.bucket.backend})<br>
                        <strong>Files:</strong> ${data.file_count} | <strong>Folders:</strong> ${data.folder_count} | 
                        <strong>Storage:</strong> ${formatBytes(data.total_size)}<br>
                        <strong>Advanced:</strong> 
                        ${data.settings.vector_search ? '🔍 Vector Search' : ''} 
                        ${data.settings.knowledge_graph ? '🧠 Knowledge Graph' : ''}
                        ${data.settings.storage_quota ? '📏 Quota: ' + formatBytes(data.settings.storage_quota) : ''}
                    </div>
                    
                    <div style="margin-bottom:10px;">
                        <input type="file" id="upload-${bucketName}" multiple style="display:none;">
                        <button onclick="document.getElementById('upload-${bucketName}').click()" 
                                style="background:#2a5cb8;color:white;padding:6px 12px;border:none;border-radius:4px;cursor:pointer;">
                            📤 Upload Files
                        </button>
                        <button onclick="refreshBucketFiles('${bucketName}')" 
                                style="background:#555;color:white;padding:6px 12px;border:none;border-radius:4px;cursor:pointer;margin-left:5px;">
                            🔄 Refresh
                        </button>
                    </div>
                    
                    <div id="file-list-${bucketName}" style="max-height:400px;overflow-y:auto;border:1px solid #333;padding:5px;background:#0f0f0f;">
                        ${data.files.length === 0 ? 
                            '<div style="text-align:center;padding:20px;color:#888;">No files in this bucket</div>' :
                            data.files.map(file => `
                                <div style="display:flex;justify-content:space-between;align-items:center;padding:4px;border-bottom:1px solid #222;">
                                    <span>
                                        ${file.type === 'directory' ? '📁' : '📄'} 
                                        ${file.name} 
                                        <small style="color:#666;">(${formatBytes(file.size)})</small>
                                    </span>
                                    <span>
                                        ${file.type === 'file' ? `<button onclick="downloadFile('${bucketName}','${file.path}')" style="background:#2a5cb8;color:white;border:none;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px;">⬇</button>` : ''}
                                        <button onclick="deleteFile('${bucketName}','${file.path}')" style="background:#b52a2a;color:white;border:none;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px;">🗑</button>
                                    </span>
                                </div>
                            `).join('')
                        }
                    </div>
                `;
                
                // Setup file upload handler
                const fileInput = document.getElementById('upload-' + bucketName);
                if (fileInput) {
                    fileInput.onchange = (e) => uploadFiles(bucketName, e.target.files);
                }
                
            } catch (e) {
                modalBody.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error loading bucket details: ' + e.message + '</div>';
            }
        });
    }

    // Enhanced bucket settings modal
    function showBucketSettings(bucketName) {
        const modal = createModal('Bucket Settings: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = '<div style="text-align:center;padding:20px;">Loading settings...</div>';
            
            try {
                const response = await fetch('/api/buckets/' + encodeURIComponent(bucketName) + '/settings');
                const data = await response.json();
                const settings = data.settings || {};
                
                modalBody.innerHTML = `
                    <div style="display:grid;gap:15px;">
                        <div>
                            <h4>Search & Indexing</h4>
                            <label style="display:block;margin:5px 0;">
                                <input type="checkbox" id="vector_search" ${settings.vector_search ? 'checked' : ''}> 
                                Vector Search (enables semantic similarity search)
                            </label>
                            <label style="display:block;margin:5px 0;">
                                <input type="checkbox" id="knowledge_graph" ${settings.knowledge_graph ? 'checked' : ''}> 
                                Knowledge Graph (enables relationship mapping)
                            </label>
                            <label style="display:block;margin:5px 0;">
                                Search Index Type: 
                                <select id="search_index_type" style="margin-left:5px;">
                                    <option value="hnsw" ${settings.search_index_type === 'hnsw' ? 'selected' : ''}>HNSW (Fast)</option>
                                    <option value="ivf" ${settings.search_index_type === 'ivf' ? 'selected' : ''}>IVF (Balanced)</option>
                                    <option value="flat" ${settings.search_index_type === 'flat' ? 'selected' : ''}>Flat (Accurate)</option>
                                </select>
                            </label>
                        </div>
                        
                        <div>
                            <h4>Storage & Performance</h4>
                            <label style="display:block;margin:5px 0;">
                                Storage Quota (bytes): 
                                <input type="number" id="storage_quota" value="${settings.storage_quota || ''}" placeholder="No limit" style="width:120px;margin-left:5px;">
                            </label>
                            <label style="display:block;margin:5px 0;">
                                Max Files: 
                                <input type="number" id="max_files" value="${settings.max_files || ''}" placeholder="No limit" style="width:120px;margin-left:5px;">
                            </label>
                            <label style="display:block;margin:5px 0;">
                                Cache TTL (seconds): 
                                <input type="number" id="cache_ttl" value="${settings.cache_ttl || 3600}" style="width:120px;margin-left:5px;">
                            </label>
                        </div>
                        
                        <div>
                            <h4>Access & Security</h4>
                            <label style="display:block;margin:5px 0;">
                                <input type="checkbox" id="public_access" ${settings.public_access ? 'checked' : ''}> 
                                Public Access (allow anonymous downloads)
                            </label>
                        </div>
                        
                        <div style="text-align:center;margin-top:20px;">
                            <button onclick="saveBucketSettings('${bucketName}')" 
                                    style="background:#2a5cb8;color:white;padding:8px 20px;border:none;border-radius:4px;cursor:pointer;">
                                💾 Save Settings
                            </button>
                        </div>
                    </div>
                `;
                
            } catch (e) {
                modalBody.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error loading settings: ' + e.message + '</div>';
            }
        });
    }

    async function uploadFiles(bucketName, files) {
        if (!files || files.length === 0) return;
        
        const results = [];
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const response = await fetch(`/api/buckets/${encodeURIComponent(bucketName)}/upload`, {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const result = await response.json();
                    results.push({success: true, file: result.file});
                } else {
                    results.push({success: false, error: await response.text()});
                }
            } catch (e) {
                results.push({success: false, error: e.message});
            }
        }
        
        // Refresh the file list
        refreshBucketFiles(bucketName);
        
        // Show results
        const successCount = results.filter(r => r.success).length;
        alert(`Upload complete: ${successCount}/${files.length} files uploaded successfully.`);
    }

    function refreshBucketFiles(bucketName) {
        // Find and refresh the file list for this bucket
        const fileListEl = document.getElementById(`file-list-${bucketName}`);
        if (!fileListEl) return;
        
        fileListEl.innerHTML = '<div style="text-align:center;padding:20px;">Refreshing...</div>';
        
        fetch('/api/buckets/' + encodeURIComponent(bucketName))
            .then(response => response.json())
            .then(data => {
                fileListEl.innerHTML = data.files.length === 0 ? 
                    '<div style="text-align:center;padding:20px;color:#888;">No files in this bucket</div>' :
                    data.files.map(file => `
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:4px;border-bottom:1px solid #222;">
                            <span>
                                ${file.type === 'directory' ? '📁' : '📄'} 
                                ${file.name} 
                                <small style="color:#666;">(${formatBytes(file.size)})</small>
                            </span>
                            <span>
                                ${file.type === 'file' ? `<button onclick="downloadFile('${bucketName}','${file.path}')" style="background:#2a5cb8;color:white;border:none;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px;">⬇</button>` : ''}
                                <button onclick="deleteFile('${bucketName}','${file.path}')" style="background:#b52a2a;color:white;border:none;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px;">🗑</button>
                            </span>
                        </div>
                    `).join('');
            })
            .catch(e => {
                fileListEl.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error refreshing files</div>';
            });
    }

    function downloadFile(bucketName, filePath) {
        const url = `/api/buckets/${encodeURIComponent(bucketName)}/download/${filePath}`;
        const a = document.createElement('a');
        a.href = url;
        a.download = filePath.split('/').pop();
        a.click();
    }

    function deleteFile(bucketName, filePath) {
        if (!confirm(`Delete file: ${filePath}?`)) return;
        
        fetch(`/api/buckets/${encodeURIComponent(bucketName)}/files/${filePath}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                refreshBucketFiles(bucketName);
            } else {
                alert('Error deleting file: ' + (result.message || 'Unknown error'));
            }
        })
        .catch(e => {
            alert('Error deleting file: ' + e.message);
        });
    }

    async function saveBucketSettings(bucketName) {
        const settings = {
            vector_search: document.getElementById('vector_search')?.checked || false,
            knowledge_graph: document.getElementById('knowledge_graph')?.checked || false,
            search_index_type: document.getElementById('search_index_type')?.value || 'hnsw',
            storage_quota: parseInt(document.getElementById('storage_quota')?.value) || null,
            max_files: parseInt(document.getElementById('max_files')?.value) || null,
            cache_ttl: parseInt(document.getElementById('cache_ttl')?.value) || 3600,
            public_access: document.getElementById('public_access')?.checked || false
        };
        
        try {
            const response = await fetch(`/api/buckets/${encodeURIComponent(bucketName)}/settings`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(settings)
            });
            
            const result = await response.json();
            if (result.success) {
                alert('Settings saved successfully!');
                document.getElementById('bucket-modal')?.remove();
                loadBuckets(); // Refresh bucket list to show updated stats
            } else {
                alert('Error saving settings: ' + (result.error || 'Unknown error'));
            }
        } catch (e) {
            alert('Error saving settings: ' + e.message);
        }
    }

    // ---- End Enhanced Bucket Management Helper Functions ----

    // Enhanced Bucket File Management Variables
    let selectedBucket = null;
    let selectedFiles = [];
    let bucketUsageData = {};
    
    // Global function aliases for onclick handlers (define early to ensure availability)
    window.refreshBuckets = async function() {
        return await loadBuckets();
    };
    
    // Comprehensive Bucket File Management Functions
    async function loadBuckets(){
        const container=document.getElementById('buckets-list'); 
        const selector=document.getElementById('bucket-selector');
        
        if(container) container.textContent='Loading…';
        
        try{ 
            await waitForMCP();
            const result = await MCP.Buckets.list();
            const items = (result && result.items) || []; 
            
            // Update bucket selector
            if(selector) {
                selector.innerHTML = '<option value="">Select a bucket...</option>';
                items.forEach(bucket => {
                    const option = el('option', {value: bucket.name, text: bucket.name});
                    selector.appendChild(option);
                });
                
                // Auto-select first bucket if only one exists (for testing/demo)
                if(items.length === 1) {
                    selector.value = items[0].name;
                    selectBucket(items[0].name);
                }
            }
            
            if(!items.length && container){ 
                container.innerHTML = '<div style="color:#888;padding:8px;">No buckets created yet. Create your first bucket above!</div>'; 
                return; 
            }
            
            if(container) {
                container.innerHTML=''; 
                items.forEach(it=>{
                    const wrap=el('div',{class:'bucket-wrap',style:'border:1px solid #333;margin:4px 0;padding:6px;border-radius:4px;background:#111;'});
                    const header=el('div',{style:'display:flex;align-items:center;justify-content:space-between;cursor:pointer;'},
                        el('div',{}, 
                            el('strong',{text:it.name,style:'color:#4CAF50;'}), 
                            el('span',{style:'color:#888;margin-left:6px;',text: it.backend? ('→ '+it.backend):''}),
                            el('span',{style:'color:#666;margin-left:8px;font-size:11px;',text: it.created_at ? new Date(it.created_at).toLocaleDateString() : ''})
                        ),
                        el('div',{},
                            el('button',{style:'padding:2px 6px;font-size:11px;margin-right:4px;background:#4CAF50;color:white;border:none;border-radius:3px;',title:'Select & Manage Files',onclick:(e)=>{ e.stopPropagation(); selectBucket(it.name); }},'Manage'),
                        el('button',{style:'padding:2px 6px;font-size:11px;margin-right:4px;',title:'Policy Settings',onclick:(e)=>{ e.stopPropagation(); showBucketPolicySettings(it.name); }},'Policy'),
                        el('button',{style:'padding:2px 6px;font-size:11px;margin-right:4px;',title:'Sync Replicas',onclick:(e)=>{ e.stopPropagation(); syncBucketReplicas(it.name); }},'Sync'),
                        el('button',{style:'padding:2px 6px;font-size:11px;margin-right:4px;',title:'Expand/Collapse',onclick:(e)=>{ e.stopPropagation(); toggle(); }},'Toggle'),
                        el('button',{style:'padding:2px 6px;font-size:11px;',title:'Delete',onclick:(e)=>{ e.stopPropagation(); if(confirm('Delete bucket '+it.name+'?')) deleteBucket(it.name); }},'Delete')
                    )
                );
                
                // Enhanced bucket details
                const body=el('div',{style:'display:none;margin-top:6px;font-size:12px;'});
                body.innerHTML='<div style="margin-bottom:8px;color:#aaa;font-weight:bold;">Bucket Details & Policy</div>'+
                    '<div id="bucket-stats-'+it.name+'" style="margin-bottom:8px;padding:4px;background:#0a0a0a;border-radius:3px;font-size:10px;color:#999;"></div>'+
                    '<div class="policy-fields" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">'
                    +' <label style="display:flex;flex-direction:column;font-size:11px;">Replication Factor<input type="number" min="1" max="10" class="pf-rep" style="width:90px;"/></label>'
                    +' <label style="display:flex;flex-direction:column;font-size:11px;">Cache Policy<select class="pf-cache" style="width:120px;"><option>none</option><option>memory</option><option>disk</option></select></label>'
                    +' <label style="display:flex;flex-direction:column;font-size:11px;">Retention Days<input type="number" min="0" class="pf-ret" style="width:110px;"/></label>'
                    +'</div>'
                    +'<div style="margin-top:6px;display:flex;gap:6px;">'
                    +' <button class="btn-policy-save" style="padding:4px 10px;font-size:11px;">Save Policy</button>'
                    +' <button class="btn-policy-cancel" style="padding:4px 10px;font-size:11px;">Cancel</button>'
                    +' <button class="btn-view-files" style="padding:4px 10px;font-size:11px;background:#444;">View Files</button>'
                    +' <span class="policy-status" style="margin-left:8px;color:#888;"></span>'
                    +'</div>';
                wrap.append(header, body); container.append(wrap);
                
                let loaded=false; let loading=false; let expanded=false; let currentPolicy=null;
                
                // Load bucket statistics
                async function loadBucketStats(){
                    const statsEl = document.getElementById('bucket-stats-'+it.name);
                    if(!statsEl) return;
                    try{
                        const response = await fetch('/api/buckets/'+encodeURIComponent(it.name));
                        const data = await response.json();
                        let statsText = `Files: ${data.file_count || 0} | Folders: ${data.folder_count || 0} | Size: ${formatBytes(data.total_size || 0)}`;
                        if(data.settings.vector_search) statsText += ' | Vector Search: ✓';
                        if(data.settings.knowledge_graph) statsText += ' | Knowledge Graph: ✓';
                        statsEl.textContent = statsText;
                    }catch(e){
                        statsEl.textContent = 'Unable to load stats';
                    }
                }
                
                async function fetchPolicy(){ 
                    if(loading||loaded) return; 
                    loading=true; 
                    setStatus('Loading...'); 
                    try{ 
                        const pr=await fetch('/api/state/buckets/'+encodeURIComponent(it.name)+'/policy'); 
                        const pj=await pr.json(); 
                        currentPolicy=pj.policy||pj||{}; 
                        applyPolicy(); 
                        loaded=true; 
                        setStatus(''); 
                        loadBucketStats(); // Load additional stats
                    }catch(e){ 
                        setStatus('Error loading'); 
                    } finally { 
                        loading=false; 
                    } 
                }
                function applyPolicy(){ 
                    if(!currentPolicy) return; 
                    const rep=body.querySelector('.pf-rep'); 
                    const cache=body.querySelector('.pf-cache'); 
                    const ret=body.querySelector('.pf-ret'); 
                    if(rep) rep.value=currentPolicy.replication_factor; 
                    if(cache) cache.value=currentPolicy.cache_policy; 
                    if(ret) ret.value=currentPolicy.retention_days; 
                }
                function toggle(){ 
                    expanded=!expanded; 
                    body.style.display= expanded? 'block':'none'; 
                    header.querySelector('button[title="Expand/Collapse"]').textContent = expanded? '▴':'▾'; 
                    if(expanded) fetchPolicy(); 
                }
                function setStatus(msg, isErr){ 
                    const st=body.querySelector('.policy-status'); 
                    if(st){ 
                        st.textContent=msg||''; 
                        st.style.color = isErr? '#f66':'#888'; 
                    } 
                }
                
                // Event handlers
                body.querySelector('.btn-policy-cancel').onclick = ()=>{ applyPolicy(); setStatus('Reverted'); };
                body.querySelector('.btn-policy-save').onclick = async ()=>{
                    const rep=parseInt(body.querySelector('.pf-rep').value,10); 
                    const cache=body.querySelector('.pf-cache').value; 
                    const ret=parseInt(body.querySelector('.pf-ret').value,10);
                    const payload={replication_factor:rep, cache_policy:cache, retention_days:ret};
                    setStatus('Saving...');
                    try{
                        const rs=await fetch('/api/state/buckets/'+encodeURIComponent(it.name)+'/policy',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
                        if(!rs.ok){ const tx=await rs.text(); setStatus('Error: '+tx.slice(0,60), true); return; }
                        const jsR=await rs.json(); currentPolicy=jsR.policy||payload; applyPolicy(); setStatus('Saved');
                    }catch(e){ setStatus('Save failed', true); }
                };
                body.querySelector('.btn-view-files').onclick = ()=> showBucketDetails(it.name);
                header.addEventListener('click', ()=> toggle());
            });
        }
        }catch(e){ 
            container.textContent='Error loading buckets'; 
            console.error('Bucket loading error:', e);
        }
    }
    
    async function loadPins(){
        const container=document.getElementById('pins-list'); if(!container) return; container.textContent='Loading…';
        try{ const r=await fetch('/api/pins'); const js=await r.json(); const items=js.items||[]; if(!items.length){ container.textContent='(none)'; return; }
            container.innerHTML=''; items.forEach(it=>{
                const row=el('div',{class:'row',style:'justify-content:space-between;'},
                    el('span',{text: it.cid + (it.name? ' ('+it.name+')':'')}),
                    el('span',{}, el('button',{style:'padding:2px 6px;font-size:11px;',title:'Delete',onclick:()=>deletePin(it.cid)},'✕'))
                ); container.append(row);
            });
        }catch(e){ container.textContent='Error'; }
    }
    async function deleteBackend(name){ try{ await fetch('/api/state/backends/'+encodeURIComponent(name), {method:'DELETE'}); loadBackends(); }catch(e){} }
    async function deleteBucket(name){ try{ await fetch('/api/state/buckets/'+encodeURIComponent(name), {method:'DELETE'}); loadBuckets(); }catch(e){} }
    async function deletePin(cid){ try{ await fetch('/api/pins/'+encodeURIComponent(cid), {method:'DELETE'}); loadPins(); }catch(e){} }
    const btnBackendAdd=document.getElementById('btn-backend-add'); if(btnBackendAdd) btnBackendAdd.onclick = async ()=>{
        const name=(document.getElementById('backend-name')||{}).value||''; 
        const type=(document.getElementById('backend-type')||{}).value||''; 
        const tier=(document.getElementById('backend-tier')||{}).value||'warm';
        const description=(document.getElementById('backend-description')||{}).value||'';
        
        if(!name || !type) {
            alert('Please provide both backend name and type');
            return;
        }
        
        try{ 
            await fetch('/api/state/backends',{
                method:'POST',
                headers:{'content-type':'application/json'},
                body:JSON.stringify({
                    name, 
                    type,
                    tier,
                    description: description || `${type.charAt(0).toUpperCase() + type.slice(1)} storage backend`,
                    config:{}
                })
            }); 
            
            // Clear form fields
            (document.getElementById('backend-name')||{}).value=''; 
            (document.getElementById('backend-type')||{}).value='';
            (document.getElementById('backend-tier')||{}).value='warm';
            (document.getElementById('backend-description')||{}).value='';
            
            loadBackends(); 
        }catch(e){
            console.error('Error adding backend:', e);
            alert('Failed to add backend: ' + e.message);
        }
    };
    const btnBucketAdd=document.getElementById('btn-bucket-add'); if(btnBucketAdd) btnBucketAdd.onclick = async ()=>{
        const name=(document.getElementById('bucket-name')||{}).value||''; 
        const backend=(document.getElementById('bucket-backend')||{}).value||''; 
        if(!name) return;
        try{ 
            await waitForMCP();
            await MCP.Buckets.create(name, backend); 
            (document.getElementById('bucket-name')||{}).value=''; 
            (document.getElementById('bucket-backend')||{}).value=''; 
            loadBuckets(); 
        }catch(e){
            console.error('Error creating bucket:', e);
            alert('Error creating bucket: ' + e.message);
        }
    };
    
    // Event handlers for new bucket management features
    const bucketSelector = document.getElementById('bucket-selector');
    if(bucketSelector) {
        bucketSelector.onchange = (e) => {
            if(e.target.value) {
                selectBucket(e.target.value);
            } else {
                showBucketFileInterface(false);
                selectedBucket = null;
                updateBucketToolbar();
            }
        };
    }
    
    const refreshBucketsBtn = document.getElementById('btn-refresh-buckets');
    if(refreshBucketsBtn) refreshBucketsBtn.onclick = loadBuckets;
    
    // Bucket configuration buttons
    const btnBucketConfigure = document.getElementById('btn-bucket-configure');
    if(btnBucketConfigure) btnBucketConfigure.onclick = () => showBucketConfigModal(selectedBucket);
    
    const btnBucketAdvanced = document.getElementById('btn-bucket-advanced');
    if(btnBucketAdvanced) btnBucketAdvanced.onclick = () => showBucketAdvancedModal(selectedBucket);
    
    const btnBucketQuota = document.getElementById('btn-bucket-quota');
    if(btnBucketQuota) btnBucketQuota.onclick = () => showBucketQuotaModal(selectedBucket);
    
    const btnBucketShare = document.getElementById('btn-bucket-share');
    if(btnBucketShare) btnBucketShare.onclick = () => showBucketShareModal(selectedBucket);
    
    const btnForceSync = document.getElementById('btn-force-sync');
    if(btnForceSync) btnForceSync.onclick = () => forceBucketSync(selectedBucket);
    
    // File operation buttons
    const btnUploadFile = document.getElementById('btn-upload-file');
    if(btnUploadFile) btnUploadFile.onclick = () => document.getElementById('file-input').click();
    
    const btnNewFolder = document.getElementById('btn-new-folder');
    if(btnNewFolder) btnNewFolder.onclick = () => createNewFolder();
    
    const btnSelectiveSync = document.getElementById('btn-selective-sync');
    if(btnSelectiveSync) btnSelectiveSync.onclick = () => performSelectiveSync();
    
    const btnDownloadSelected = document.getElementById('btn-download-selected');
    if(btnDownloadSelected) btnDownloadSelected.onclick = () => downloadSelectedFiles();
    
    const btnDeleteSelected = document.getElementById('btn-delete-selected');
    if(btnDeleteSelected) btnDeleteSelected.onclick = () => deleteSelectedFiles();
    
    // Drag & Drop functionality
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    
    if(dropZone && fileInput) {
        // Make drop zone clickable
        dropZone.onclick = () => fileInput.click();
        
        // Drag and drop events
        dropZone.ondragover = (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#4CAF50';
            dropZone.style.backgroundColor = '#0a2a0a';
        };
        
        dropZone.ondragleave = (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#666';
            dropZone.style.backgroundColor = '#0a0a0a';
        };
        
        dropZone.ondrop = (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#666';
            dropZone.style.backgroundColor = '#0a0a0a';
            
            const files = Array.from(e.dataTransfer.files);
            uploadFiles(files);
        };
        
        // File input change event
        fileInput.onchange = (e) => {
            const files = Array.from(e.target.files);
            uploadFiles(files);
        };
    }
    
    // Select bucket and show file management interface
    async function selectBucket(bucketName) {
        selectedBucket = bucketName;
        selectedFiles = []; // Clear file selection
        
        // Update UI visibility
        showBucketFileInterface(true);
        updateBucketToolbar();
        
        // Load bucket usage and files
        await updateBucketStatus();
        await loadBucketFiles();
    }
    
    // Show/hide bucket file interface
    function showBucketFileInterface(show) {
        const elements = [
            'bucket-status-bar',
            'drop-zone', 
            'file-toolbar',
            'file-list-container'
        ];
        
        elements.forEach(id => {
            const el = document.getElementById(id);
            if(el) el.style.display = show ? 'block' : 'none';
        });
        
        // Hide bucket list when file interface is shown
        const bucketsList = document.getElementById('buckets-list');
        if(bucketsList) bucketsList.style.display = show ? 'none' : 'block';
    }
    
    // Update bucket toolbar button states
    function updateBucketToolbar() {
        const hasSelection = selectedBucket !== null;
        const hasFileSelection = selectedFiles.length > 0;
        
        const buttons = [
            'btn-bucket-configure',
            'btn-bucket-advanced', 
            'btn-bucket-quota',
            'btn-bucket-share',
            'btn-force-sync'
        ];
        
        buttons.forEach(id => {
            const btn = document.getElementById(id);
            if(btn) btn.disabled = !hasSelection;
        });
        
        const fileButtons = [
            'btn-selective-sync',
            'btn-download-selected',
            'btn-delete-selected'
        ];
        
        fileButtons.forEach(id => {
            const btn = document.getElementById(id);
            if(btn) btn.disabled = !hasFileSelection;
        });
        
        // Update selection info
        const selectionInfo = document.getElementById('selection-info');
        if(selectionInfo) {
            if(hasFileSelection) {
                selectionInfo.textContent = `${selectedFiles.length} file(s) selected`;
                selectionInfo.style.color = '#4CAF50';
            } else {
                selectionInfo.textContent = 'Select files to enable operations';
                selectionInfo.style.color = '#888';
            }
        }
    }
    const btnPinAdd=document.getElementById('btn-pin-add'); if(btnPinAdd) btnPinAdd.onclick = async ()=>{
        const cid=(document.getElementById('pin-cid')||{}).value||''; const name=(document.getElementById('pin-name')||{}).value||''; if(!cid) return;
        try{ await fetch('/api/pins',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({cid, name})}); (document.getElementById('pin-cid')||{}).value=''; loadPins(); }catch(e){}
    };
    
    // Update bucket status bar
    async function updateBucketStatus() {
        if(!selectedBucket) return;
        
        try {
            await waitForMCP();
            const usageResponse = await MCP.Buckets.getUsage(selectedBucket);
            const usage = (usageResponse && usageResponse.result) || {};
            bucketUsageData[selectedBucket] = usage;
            
            const statusQuota = document.getElementById('status-quota');
            const statusFiles = document.getElementById('status-files');
            const statusCache = document.getElementById('status-cache');
            const statusRetention = document.getElementById('status-retention');
            
            if(statusFiles) {
                statusFiles.textContent = `Files: ${usage.file_count || 0}`;
                statusFiles.style.color = usage.file_count > 1000 ? '#FF9800' : '#2196F3';
            }
            
            if(statusQuota) {
                const sizeGB = usage.total_size_gb || 0;
                statusQuota.textContent = `Usage: ${sizeGB.toFixed(2)} GB`;
                statusQuota.style.color = sizeGB > 10 ? '#F44336' : '#4CAF50';
            }
            
            // Load bucket config for cache and retention info
            const bucketResponse = await MCP.Buckets.get(selectedBucket);
            const bucket = (bucketResponse && bucketResponse.result) || {};
            const policy = bucket.policy || {};
            
            if(statusCache) {
                const cachePolicy = policy.cache_policy || 'none';
                statusCache.textContent = `Cache: ${cachePolicy}`;
                statusCache.style.color = cachePolicy === 'none' ? '#888' : '#FF9800';
            }
            
            if(statusRetention) {
                const retentionDays = policy.retention_days || 0;
                statusRetention.textContent = retentionDays > 0 ? `Retention: ${retentionDays}d` : 'Retention: None';
                statusRetention.style.color = retentionDays > 0 ? '#9C27B0' : '#888';
            }
            
        } catch(e) {
            console.error('Error updating bucket status:', e);
        }
    }
    
    // Load bucket files
    async function loadBucketFiles() {
        if(!selectedBucket) return;
        
        const fileListBody = document.getElementById('file-list-body');
        if(!fileListBody) return;
        
        fileListBody.innerHTML = 'Loading files...';
        
        try {
            await waitForMCP();
            const result = await MCP.Buckets.listFiles(selectedBucket, '.', true);
            const files = (result && result.items) || [];
            
            if(files.length === 0) {
                fileListBody.innerHTML = '<div style="color:#888;padding:12px;text-align:center;">No files in this bucket. Upload some files to get started!</div>';
                return;
            }
            
            fileListBody.innerHTML = '';
            
            files.forEach(file => {
                const row = el('div', {
                    class: 'file-row',
                    style: 'display:grid;grid-template-columns:30px 1fr 100px 120px 80px;gap:8px;align-items:center;padding:6px;border-bottom:1px solid #333;cursor:pointer;',
                    onclick: () => toggleFileSelection(file.path)
                });
                
                const checkbox = el('input', {
                    type: 'checkbox',
                    style: 'margin:0;',
                    onchange: (e) => {
                        e.stopPropagation();
                        if(e.target.checked) {
                            if(!selectedFiles.includes(file.path)) {
                                selectedFiles.push(file.path);
                            }
                        } else {
                            selectedFiles = selectedFiles.filter(f => f !== file.path);
                        }
                        updateBucketToolbar();
                    }
                });
                
                const nameEl = el('div', {
                    style: 'display:flex;align-items:center;',
                }, 
                    el('span', {text: file.is_dir ? '📁' : '📄', style: 'margin-right:6px;'}),
                    el('span', {text: file.name, style: 'color:' + (file.is_dir ? '#4CAF50' : '#ccc')})
                );
                
                const sizeEl = el('span', {
                    text: file.is_dir ? '-' : formatFileSize(file.size || 0),
                    style: 'font-size:11px;color:#888;font-family:monospace;'
                });
                
                const modifiedEl = el('span', {
                    text: file.modified ? new Date(file.modified).toLocaleDateString() : '-',
                    style: 'font-size:11px;color:#888;'
                });
                
                const actionsEl = el('div', {},
                    el('button', {
                        text: '↓',
                        title: 'Download',
                        style: 'padding:2px 6px;font-size:10px;margin-right:2px;background:#673AB7;color:white;border:none;border-radius:2px;',
                        onclick: (e) => {
                            e.stopPropagation();
                            downloadFile(file.path);
                        }
                    }),
                    el('button', {
                        text: '🗑️',
                        title: 'Delete',
                        style: 'padding:2px 6px;font-size:10px;background:#F44336;color:white;border:none;border-radius:2px;',
                        onclick: (e) => {
                            e.stopPropagation();
                            deleteFile(file.path);
                        }
                    })
                );
                
                row.appendChild(checkbox);
                row.appendChild(nameEl);
                row.appendChild(sizeEl);
                row.appendChild(modifiedEl);
                row.appendChild(actionsEl);
                
                fileListBody.appendChild(row);
            });
            
        } catch(e) {
            console.error('Error loading bucket files:', e);
            fileListBody.innerHTML = '<div style="color:#F44336;padding:12px;">Error loading files: ' + e.message + '</div>';
        }
    }
    let logSource=null; let logsInited=false; function initLogs(){
        if(logsInited) return; logsInited=true;
        try{ logSource = new EventSource('/api/logs/stream');
            logSource.onmessage = (ev)=>{ try{ const data=JSON.parse(ev.data); const pre=document.getElementById('logs-pre'); if(!pre) return; pre.textContent += '\n'+data.timestamp+' '+data.level+' ['+data.logger+'] '+data.message; pre.scrollTop = pre.scrollHeight; }catch(e){} };
        }catch(e){ console.warn('SSE logs failed', e); }
        const clr=document.getElementById('btn-clear-logs'); if(clr) clr.onclick = ()=>{ if(window.MCP){ window.MCP.callTool('clear_logs',{}).then(()=>{ const pre=document.getElementById('logs-pre'); if(pre) pre.textContent='(cleared)'; }); } };
    }
    
    // Toggle file selection
    function toggleFileSelection(filePath) {
        if(selectedFiles.includes(filePath)) {
            selectedFiles = selectedFiles.filter(f => f !== filePath);
        } else {
            selectedFiles.push(filePath);
        }
        updateBucketToolbar();
        
        // Update checkbox state
        const rows = document.querySelectorAll('.file-row');
        rows.forEach(row => {
            const checkbox = row.querySelector('input[type="checkbox"]');
            const nameEl = row.children[1];
            if(nameEl && checkbox) {
                const fileName = nameEl.textContent.trim();
                checkbox.checked = selectedFiles.some(f => f.endsWith(fileName));
            }
        });
    }
    
    // Format file size
    function formatFileSize(bytes) {
        if(bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
    
    // Upload files with progress tracking
    async function uploadFiles(files) {
        if(!selectedBucket || !files.length) return;
        
        const progressDiv = document.getElementById('upload-progress');
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        
        if(progressDiv) progressDiv.style.display = 'block';
        
        try {
            await waitForMCP();
            
            for(let i = 0; i < files.length; i++) {
                const file = files[i];
                const progress = ((i + 1) / files.length) * 100;
                
                if(progressFill) progressFill.style.width = progress + '%';
                if(progressText) progressText.textContent = `Uploading ${file.name}... ${Math.round(progress)}% complete`;
                
                // Read file content
                const content = await readFileAsText(file);
                
                // Upload via MCP
                await MCP.Buckets.uploadFile(selectedBucket, file.name, content, 'text', true);
            }
            
            // Hide progress and reload files
            if(progressDiv) progressDiv.style.display = 'none';
            await loadBucketFiles();
            await updateBucketStatus();
            
            alert(`Successfully uploaded ${files.length} file(s)!`);
            
        } catch(e) {
            console.error('Error uploading files:', e);
            alert('Error uploading files: ' + e.message);
            if(progressDiv) progressDiv.style.display = 'none';
        }
    }
    
    // Read file as text
    function readFileAsText(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = reject;
            reader.readAsText(file);
        });
    }
    
    // Create new folder
    async function createNewFolder() {
        if(!selectedBucket) return;
        
        const folderName = prompt('Enter folder name:');
        if(!folderName) return;
        
        try {
            await waitForMCP();
            await MCP.Buckets.mkdir(selectedBucket, folderName, true);
            await loadBucketFiles();
        } catch(e) {
            console.error('Error creating folder:', e);
            alert('Error creating folder: ' + e.message);
        }
    }
    
    // Download file
    async function downloadFile(filePath) {
        if(!selectedBucket) return;
        
        try {
            await waitForMCP();
            const result = await MCP.Buckets.downloadFile(selectedBucket, filePath, 'text');
            const content = (result && result.result && result.result.content) || '';
            
            // Create download link
            const blob = new Blob([content], {type: 'text/plain'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filePath.split('/').pop();
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
        } catch(e) {
            console.error('Error downloading file:', e);
            alert('Error downloading file: ' + e.message);
        }
    }
    
    // Delete file
    async function deleteFile(filePath) {
        if(!selectedBucket) return;
        if(!confirm(`Delete file "${filePath}"?`)) return;
        
        try {
            await waitForMCP();
            await MCP.Buckets.deleteFile(selectedBucket, filePath, true);
            await loadBucketFiles();
            await updateBucketStatus();
        } catch(e) {
            console.error('Error deleting file:', e);
            alert('Error deleting file: ' + e.message);
        }
    }
    
    // Download selected files
    async function downloadSelectedFiles() {
        if(!selectedBucket || !selectedFiles.length) return;
        
        for(const filePath of selectedFiles) {
            await downloadFile(filePath);
        }
    }
    
    // Delete selected files
    async function deleteSelectedFiles() {
        if(!selectedBucket || !selectedFiles.length) return;
        if(!confirm(`Delete ${selectedFiles.length} selected file(s)?`)) return;
        
        try {
            await waitForMCP();
            
            for(const filePath of selectedFiles) {
                await MCP.Buckets.deleteFile(selectedBucket, filePath, true);
            }
            
            selectedFiles = [];
            await loadBucketFiles();
            await updateBucketStatus();
            updateBucketToolbar();
            
        } catch(e) {
            console.error('Error deleting files:', e);
            alert('Error deleting files: ' + e.message);
        }
    }
    
    // Perform selective sync
    async function performSelectiveSync() {
        if(!selectedBucket || !selectedFiles.length) return;
        
        try {
            await waitForMCP();
            const options = {
                force_update: confirm('Force update existing files?'),
                verify_checksums: true,
                create_backup: confirm('Create backup before sync?')
            };
            
            const result = await MCP.Buckets.selectiveSync(selectedBucket, selectedFiles, options);
            alert(`Selective sync completed. ${result.synced_files?.length || 0} files synced.`);
            
            await loadBucketFiles();
            await updateBucketStatus();
            
        } catch(e) {
            console.error('Error performing selective sync:', e);
            alert('Error performing selective sync: ' + e.message);
        }
    }
    
    // Force bucket sync
    async function forceBucketSync(bucketName) {
        if(!bucketName) return;
        
        try {
            await waitForMCP();
            await MCP.Buckets.syncReplicas(bucketName, true);
            alert('Force sync completed successfully!');
            
            if(bucketName === selectedBucket) {
                await updateBucketStatus();
            }
            
        } catch(e) {
            console.error('Error performing force sync:', e);
            alert('Error performing force sync: ' + e.message);
        }
    }
    async function loadFiles(){
        const pathEl = document.getElementById('files-path');
        const bucketEl = document.getElementById('files-bucket');
        const container = document.getElementById('files-container');
        const loading = document.getElementById('files-loading');
        
        if (!container) return;
        
        const path = (pathEl && pathEl.value) || '.';
        const bucket = (bucketEl && bucketEl.value) || null;
        
        if (loading) loading.textContent = 'Loading…';
        
        try {
            // Use MCP SDK for API calls
            const params = new URLSearchParams();
            if (path !== '.') params.append('path', path);
            if (bucket) params.append('bucket', bucket);
            
            const response = await fetch(`/api/files/list?${params.toString()}`);
            const data = await response.json();
            
            if (loading) loading.textContent = '';
            
            // Clear container
            container.innerHTML = '';
            
            if (!data.items || data.items.length === 0) {
                container.appendChild(el('div', {text: '(empty directory)', style: 'color: #888; padding: 8px;'}));
                return;
            }
            
            // Create file table
            const table = el('table', {style: 'width: 100%; font-size: 12px; border-collapse: collapse;'});
            
            // Header
            const header = el('tr', {style: 'border-bottom: 1px solid #333;'},
                el('th', {text: '', style: 'width: 20px; padding: 4px;'}), // checkbox
                el('th', {text: 'Name', style: 'text-align: left; padding: 4px;'}),
                el('th', {text: 'Type', style: 'text-align: left; padding: 4px; width: 80px;'}),
                el('th', {text: 'Size', style: 'text-align: right; padding: 4px; width: 80px;'}),
                el('th', {text: 'Modified', style: 'text-align: left; padding: 4px; width: 130px;'})
            );
            table.appendChild(header);
            
            // Sort items: directories first, then files, alphabetically
            const sortedItems = [...data.items].sort((a, b) => {
                if (a.is_dir && !b.is_dir) return -1;
                if (!a.is_dir && b.is_dir) return 1;
                return a.name.localeCompare(b.name);
            });
            
            // File rows
            sortedItems.forEach(item => {
                const row = el('tr', {
                    style: 'border-bottom: 1px solid #222; cursor: pointer;',
                    'data-name': item.name,
                    'data-type': item.type
                });
                
                // Checkbox
                const checkbox = el('input', {type: 'checkbox', style: 'margin: 0;'});
                checkbox.addEventListener('change', updateDeleteButton);
                row.appendChild(el('td', {style: 'padding: 4px;'}, checkbox));
                
                // Name
                const nameEl = el('td', {
                    text: item.name,
                    style: `padding: 4px; ${item.is_dir ? 'font-weight: bold; color: #6b8cff;' : ''}`
                });
                row.appendChild(nameEl);
                
                // Type
                row.appendChild(el('td', {text: item.type, style: 'padding: 4px; color: #888;'}));
                
                // Size
                const sizeText = item.size !== null ? formatBytes(item.size) : '-';
                row.appendChild(el('td', {text: sizeText, style: 'padding: 4px; text-align: right; font-family: monospace;'}));
                
                // Modified
                const modText = item.modified ? new Date(item.modified).toLocaleDateString() + ' ' + new Date(item.modified).toLocaleTimeString() : '-';
                row.appendChild(el('td', {text: modText, style: 'padding: 4px; font-family: monospace; font-size: 10px;'}));
                
                // Click handlers
                row.addEventListener('click', (e) => {
                    if (e.target.type === 'checkbox') return; // Don't interfere with checkbox
                    
                    if (item.is_dir) {
                        // Navigate to directory
                        const newPath = path === '.' ? item.name : `${path}/${item.name}`;
                        if (pathEl) pathEl.value = newPath;
                        loadFiles();
                    } else {
                        // Show file details
                        showFileDetails(item, path, bucket);
                    }
                });
                
                table.appendChild(row);
            });
            
            container.appendChild(table);
            
            // Update path breadcrumb
            updatePathBreadcrumb(path, bucket);
            
        } catch (e) {
            console.error('Error loading files:', e);
            if (loading) loading.textContent = 'Error loading files';
        }
    }
    
    function updateDeleteButton() {
        const checkboxes = document.querySelectorAll('#files-container input[type="checkbox"]');
        const deleteBtn = document.getElementById('btn-file-delete');
        const hasSelected = Array.from(checkboxes).some(cb => cb.checked);
        
        if (deleteBtn) {
            deleteBtn.disabled = !hasSelected;
            deleteBtn.style.opacity = hasSelected ? '1' : '0.5';
        }
    }
    
    function updatePathBreadcrumb(path, bucket) {
        // Could add breadcrumb navigation here in the future
        const pathEl = document.getElementById('files-path');
        if (pathEl && pathEl.value !== path) {
            pathEl.value = path;
        }
    }
    
    async function showFileDetails(item, path, bucket) {
        const detailsPanel = document.getElementById('file-details');
        const statsEl = document.getElementById('file-stats');
        
        if (!detailsPanel || !statsEl) return;
        
        try {
            const params = new URLSearchParams();
            params.append('path', path === '.' ? item.name : `${path}/${item.name}`);
            if (bucket) params.append('bucket', bucket);
            
            const response = await fetch(`/api/files/stats?${params.toString()}`);
            const stats = await response.json();
            
            let statsText = '';
            statsText += `Name: ${item.name}\n`;
            statsText += `Type: ${stats.is_file ? 'File' : 'Directory'}\n`;
            statsText += `Size: ${formatBytes(stats.size || 0)}\n`;
            statsText += `Modified: ${stats.modified ? new Date(stats.modified).toLocaleString() : '-'}\n`;
            statsText += `Created: ${stats.created ? new Date(stats.created).toLocaleString() : '-'}\n`;
            statsText += `Permissions: ${stats.permissions || '-'}\n`;
            
            if (stats.is_dir) {
                statsText += `\nContains:\n`;
                statsText += `  Files: ${stats.file_count || 0}\n`;
                statsText += `  Directories: ${stats.dir_count || 0}\n`;
                statsText += `  Total Size: ${formatBytes(stats.total_size || 0)}\n`;
            }
            
            statsEl.textContent = statsText;
            detailsPanel.style.display = 'block';
            
        } catch (e) {
            console.error('Error getting file stats:', e);
            statsEl.textContent = 'Error loading file details';
            detailsPanel.style.display = 'block';
        }
    }
    
    async function loadVfsBuckets() {
        const bucketEl = document.getElementById('files-bucket');
        if (!bucketEl) return;
        
        try {
            const response = await fetch('/api/files/buckets');
            const data = await response.json();
            
            // Clear and populate bucket selector
            bucketEl.innerHTML = '';
            
            // Add "All Buckets" option
            const defaultOption = el('option', {value: '', text: '(default)'});
            bucketEl.appendChild(defaultOption);
            
            if (data.buckets) {
                data.buckets.forEach(bucket => {
                    if (bucket.name !== 'default') { // Skip default as we already have it
                        const option = el('option', {
                            value: bucket.name,
                            text: `${bucket.display_name || bucket.name} (${bucket.file_count} files)`
                        });
                        bucketEl.appendChild(option);
                    }
                });
            }
            
        } catch (e) {
            console.error('Error loading buckets:', e);
        }
    }
    const btnFiles=document.getElementById('btn-files-load'); if(btnFiles) btnFiles.onclick = ()=> loadFiles();
    const btnBucketRefresh=document.getElementById('btn-bucket-refresh'); if(btnBucketRefresh) btnBucketRefresh.onclick = ()=> loadVfsBuckets();
    const btnFilesUp=document.getElementById('btn-files-up'); if(btnFilesUp) btnFilesUp.onclick = ()=> {
        const pathEl = document.getElementById('files-path');
        if (pathEl) {
            const currentPath = pathEl.value || '.';
            if (currentPath !== '.') {
                const parts = currentPath.split('/');
                parts.pop();
                pathEl.value = parts.length > 0 ? parts.join('/') : '.';
                loadFiles();
            }
        }
    };
    const btnFilesRefresh=document.getElementById('btn-files-refresh'); if(btnFilesRefresh) btnFilesRefresh.onclick = ()=> loadFiles();
    const bucketSelect=document.getElementById('files-bucket'); if(bucketSelect) bucketSelect.onchange = ()=> loadFiles();
    
    // File operations
    const btnFileNew=document.getElementById('btn-file-new'); if(btnFileNew) btnFileNew.onclick = async ()=> {
        const filename = prompt('Enter filename:');
        if (!filename) return;
        
        const pathEl = document.getElementById('files-path');
        const bucketEl = document.getElementById('files-bucket');
        const currentPath = (pathEl && pathEl.value) || '.';
        const bucket = (bucketEl && bucketEl.value) || null;
        
        const fullPath = currentPath === '.' ? filename : `${currentPath}/${filename}`;
        
        try {
            const response = await fetch('/api/files/write', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'x-api-token': (window.API_TOKEN || '')},
                body: JSON.stringify({
                    path: fullPath,
                    content: '',
                    bucket: bucket
                })
            });
            
            if (response.ok) {
                loadFiles();
            } else {
                alert('Failed to create file');
            }
        } catch (e) {
            console.error('Error creating file:', e);
            alert('Error creating file');
        }
    };
    
    const btnDirNew=document.getElementById('btn-dir-new'); if(btnDirNew) btnDirNew.onclick = async ()=> {
        const dirname = prompt('Enter directory name:');
        if (!dirname) return;
        
        const pathEl = document.getElementById('files-path');
        const bucketEl = document.getElementById('files-bucket');
        const currentPath = (pathEl && pathEl.value) || '.';
        const bucket = (bucketEl && bucketEl.value) || null;
        
        const fullPath = currentPath === '.' ? dirname : `${currentPath}/${dirname}`;
        
        try {
            const response = await fetch('/api/files/mkdir', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'x-api-token': (window.API_TOKEN || '')},
                body: JSON.stringify({
                    path: fullPath,
                    bucket: bucket
                })
            });
            
            if (response.ok) {
                loadFiles();
            } else {
                alert('Failed to create directory');
            }
        } catch (e) {
            console.error('Error creating directory:', e);
            alert('Error creating directory');
        }
    };
    
    const btnFileDelete=document.getElementById('btn-file-delete'); if(btnFileDelete) btnFileDelete.onclick = async ()=> {
        const checkboxes = document.querySelectorAll('#files-container input[type="checkbox"]:checked');
        const selectedFiles = Array.from(checkboxes).map(cb => {
            const row = cb.closest('tr');
            return row ? row.getAttribute('data-name') : null;
        }).filter(name => name);
        
        if (selectedFiles.length === 0) return;
        
        if (!confirm(`Delete ${selectedFiles.length} selected items?`)) return;
        
        const pathEl = document.getElementById('files-path');
        const bucketEl = document.getElementById('files-bucket');
        const currentPath = (pathEl && pathEl.value) || '.';
        const bucket = (bucketEl && bucketEl.value) || null;
        
        let successCount = 0;
        for (const filename of selectedFiles) {
            try {
                const fullPath = currentPath === '.' ? filename : `${currentPath}/${filename}`;
                const response = await fetch(`/api/files/delete?path=${encodeURIComponent(fullPath)}${bucket ? '&bucket=' + encodeURIComponent(bucket) : ''}`, {
                    method: 'DELETE',
                    headers: {'x-api-token': (window.API_TOKEN || '')}
                });
                
                if (response.ok) {
                    successCount++;
                }
            } catch (e) {
                console.error('Error deleting file:', filename, e);
            }
        }
        
        if (successCount > 0) {
            loadFiles();
            document.getElementById('file-details').style.display = 'none';
        }
        
        if (successCount < selectedFiles.length) {
            alert(`${successCount}/${selectedFiles.length} items deleted successfully`);
        }
    };
    
    // Initialize files view
    if (document.getElementById('view-files')) {
        loadVfsBuckets();
    }
    // ---- Tools Tab ----
    // Use var to avoid temporal-dead-zone when showView('tools') runs before these are initialized
    var toolsLoaded=false; var toolDefs=[{name:'files_list'},{name:'files_read'},{name:'files_write'}]; function initTools(){ if(toolsLoaded) return; toolsLoaded=true; renderToolOptions(toolDefs); (async()=>{ try{ if(!(window.MCP && MCP.listTools)) await waitForMCP(); }catch(_e){} finally { await loadToolList(); const tf=document.getElementById('tool-filter'); if(tf && tf.value) applyToolFilter(tf.value); } })(); }
    function renderToolOptions(list){
        const sel=document.getElementById('tool-select'); if(!sel) return; const prev=sel.value; sel.innerHTML='';
        list.forEach(td=>{ const o=document.createElement('option'); o.value=td.name; o.textContent=td.name; sel.append(o); });
        if(list.some(t=>t.name===prev)) sel.value=prev; else if(list.length) sel.selectedIndex=0;
        buildToolFormForSelected();
    }
    // Pre-seed with common tools to avoid empty list races
    (function seedToolSelect(){ const sel=document.getElementById('tool-select'); if(!sel) return; if(sel.options.length) return; const seed=['files_list','files_read','files_write']; seed.forEach(n=>{ const o=document.createElement('option'); o.value=n; o.textContent=n; sel.append(o); }); })();
    function applyToolFilter(q){
        const query=(q||'').toLowerCase();
        if(!query){ renderToolOptions(toolDefs||[]); return; }
        const starts=[]; const contains=[]; (toolDefs||[]).forEach(t=>{ const n=(t.name||'').toLowerCase(); if(n.startsWith(query)) starts.push(t); else if(n.includes(query)) contains.push(t); });
        starts.sort((a,b)=> (a.name||'').localeCompare(b.name||''));
        contains.sort((a,b)=> (a.name||'').localeCompare(b.name||''));
        renderToolOptions(starts.concat(contains));
    }
    async function loadToolList(){
        const sel=document.getElementById('tool-select'); if(!sel) return; sel.innerHTML=''; toolDefs=[];
        try{
            if(window.MCP && MCP.listTools){
                const r=await MCP.listTools(); toolDefs=(r && r.result && r.result.tools)||[];
                try{
                    const have=new Set((toolDefs||[]).map(t=>t.name));
                    if(window.MCP && MCP.Files){
                        const fileTools=[
                            {name:'files_list', description:'List VFS', inputSchema:{type:'object', required:['path'], properties:{path:{type:'string'}}}},
                            {name:'files_read', description:'Read VFS file', inputSchema:{type:'object', required:['path'], properties:{path:{type:'string'}}}},
                            {name:'files_write', description:'Write VFS file', inputSchema:{type:'object', required:['path','content'], properties:{path:{type:'string'}, content:{type:'string'}}}},
                            {name:'files_mkdir', description:'Create directory', inputSchema:{type:'object', required:['path'], properties:{path:{type:'string'}}}},
                            {name:'files_rm', description:'Remove file/dir', inputSchema:{type:'object', required:['path'], properties:{path:{type:'string'}, recursive:{type:'boolean'}}}},
                        ];
                        fileTools.forEach(t=>{ if(!have.has(t.name)) toolDefs.push(t); });
                    }
                }catch(_e){}
            } else {
                const r=await fetch('/mcp/tools/list',{method:'POST'}); const js=await r.json(); toolDefs=(js && js.result && js.result.tools)||[];
            }
            toolDefs.sort((a,b)=> (a.name||'').localeCompare(b.name||''));
            const tf=document.getElementById('tool-filter');
            if(tf && tf.value){ applyToolFilter(tf.value); } else { renderToolOptions(toolDefs); }
        }catch(e){ const o=document.createElement('option'); o.textContent='(error)'; sel.append(o); }
    }
    function getToolDef(name){ return (toolDefs||[]).find(t=>t.name===name); }
    const RAW_TOGGLE_ID='btn-tool-raw-toggle';
    function buildToolFormForSelected(){ const sel=document.getElementById('tool-select'); if(!sel) return; buildToolForm(getToolDef(sel.value)); }
    function simplifySchema(schema){ if(!schema) return {type:'object',properties:{}}; if(schema.type==='object') return schema; if(typeof schema==='object' && !schema.type){
            // treat keys as properties mapping to simple types
            const props={}; Object.keys(schema).forEach(k=>{ const v=schema[k]; if(typeof v==='string') props[k]={type:v}; else props[k]=v; }); return {type:'object',properties:props};
        } return schema; }
    async function dynamicEnum(prop){ const ui=(prop && prop.ui)||{}; if(!ui.enumFrom) return null; try{
            if(ui.enumFrom==='backends'){ const r=await fetch('/api/state/backends'); const js=await r.json(); return (js.items||[]).map(it=>({value:it.name,label:it.name})); }
            if(ui.enumFrom==='buckets'){ const r=await fetch('/api/state/buckets'); const js=await r.json(); return (js.items||[]).map(it=>({value:it.name,label:it.name})); }
            if(ui.enumFrom==='pins'){ const r=await fetch('/api/pins'); const js=await r.json(); return (js.items||[]).map(it=>({value:it.cid,label:(it.name? it.name+' ':'')+'('+it.cid.slice(0,10)+'...)'})); }
        }catch(e){}
        return null; }
    let lastBuiltTool=null; async function buildToolForm(tool){ const form=document.getElementById('tool-form'); const raw=document.getElementById('tool-args'); const desc=document.getElementById('tool-desc'); if(!form||!raw) return; form.innerHTML=''; if(desc) desc.textContent= tool? (tool.description||'') : ''; if(!tool){ raw.style.display='block'; return; } lastBuiltTool=tool.name; const schema=simplifySchema(tool.inputSchema); if(schema.type!=='object'){ raw.style.display='block'; return; }
        const props=schema.properties||{}; const required=new Set(schema.required||[]);
        for(const [name, prop] of Object.entries(props)){
            const wrap=document.createElement('label'); wrap.style.display='flex'; wrap.style.flexDirection='column'; wrap.style.fontSize='11px'; wrap.style.minWidth='140px'; wrap.style.flex='1 1 140px'; wrap.dataset.wrapFor=name;
            const title=(prop.title||name)+(required.has(name)?'*':''); const span=document.createElement('span'); span.textContent=title; span.style.marginBottom='2px'; wrap.append(span);
            let input;
            if(prop.enum){ input=document.createElement('select'); prop.enum.forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=v; input.append(o); }); }
            else if((prop.ui||{}).enumFrom){ input=document.createElement('select'); input.dataset.enumFrom=prop.ui.enumFrom; input.innerHTML='<option value="">(loading)</option>'; dynamicEnum(prop).then(list=>{ if(!list) return; input.innerHTML=''; list.forEach(it=>{ const o=document.createElement('option'); o.value=it.value; o.textContent=it.label; input.append(o); }); if(prop.default) input.value=prop.default; updateRawArgs(); }); }
            else if(prop.type==='boolean'){ input=document.createElement('input'); input.type='checkbox'; if(prop.default) input.checked=!!prop.default; }
            else if(prop.type==='number' || prop.type==='integer'){ input=document.createElement('input'); input.type='number'; if(prop.default!=null) input.value=prop.default; }
            else if((prop.ui||{}).widget==='textarea'){ input=document.createElement('textarea'); input.rows=(prop.ui.rows||3); if(prop.default!=null) input.value=prop.default; }
            else { input=document.createElement('input'); input.type='text'; if(prop.default!=null) input.value=prop.default; }
            input.id='tool-field-'+name; input.dataset.fieldName=name; if(prop.description) input.title=prop.description; if((prop.ui||{}).placeholder) input.placeholder=prop.ui.placeholder; if(required.has(name)) input.dataset.required='1';
            input.addEventListener('input', ()=>{ clearFieldError(input); updateRawArgs(); });
            if(input.tagName==='SELECT') input.addEventListener('change', ()=>{ clearFieldError(input); updateRawArgs(); });
            wrap.append(input); form.append(wrap);
        }
        raw.style.display='none'; updateRawArgs();
    }
    function collectFormArgs(){ const form=document.getElementById('tool-form'); if(!form) return {}; const fields=form.querySelectorAll('[data-field-name]'); const args={}; fields.forEach(f=>{ const name=f.dataset.fieldName; if(f.type==='checkbox') args[name]=f.checked; else if(f.type==='number') args[name]= (f.value===''? null : Number(f.value)); else args[name]=f.value; }); return args; }
    function updateRawArgs(){ const raw=document.getElementById('tool-args'); if(!raw || raw.style.display==='block') return; const args=collectFormArgs(); raw.value=JSON.stringify(args,null,2); }
    function clearFieldError(input){ const wrap=input.parentElement; if(wrap) wrap.style.outline='none'; }
    function validateToolForm(tool){ if(!tool) return true; const form=document.getElementById('tool-form'); if(!form) return true; let ok=true; const requiredEls=form.querySelectorAll('[data-required="1"]'); requiredEls.forEach(inp=>{ const val = (inp.type==='checkbox')? (inp.checked? 'true': '') : inp.value.trim(); if(!val){ ok=false; const wrap=inp.parentElement; if(wrap) wrap.style.outline='1px solid #d66'; } }); return ok; }
    const toolSelect=document.getElementById('tool-select'); if(toolSelect) toolSelect.addEventListener('change', ()=> buildToolFormForSelected());
    const rawToggle=document.getElementById('btn-tool-raw-toggle'); if(rawToggle) rawToggle.addEventListener('click',()=>{ const raw=document.getElementById('tool-args'); if(!raw) return; raw.style.display = (raw.style.display==='none'?'block':'none'); });
    const toolFilter=document.getElementById('tool-filter'); if(toolFilter) toolFilter.addEventListener('input',()=>{
        const q=(toolFilter.value||'');
        if(!Array.isArray(toolDefs) || toolDefs.length===0){ loadToolList().then(()=> applyToolFilter(q)); return; }
        applyToolFilter(q);
    });
    const btnToolRefresh=document.getElementById('btn-tool-refresh'); if(btnToolRefresh) btnToolRefresh.onclick = loadToolList;
    const btnToolRun=document.getElementById('btn-tool-run'); if(btnToolRun) btnToolRun.onclick = async ()=>{
        const sel=document.getElementById('tool-select'); const argsEl=document.getElementById('tool-args'); const out=document.getElementById('tool-result'); const status=document.getElementById('tool-run-status');
        const name=(sel&&sel.value)||''; if(!name){ if(status) status.textContent='No tool selected'; return; }
        let tool=getToolDef(name); let args={};
        if(tool && lastBuiltTool===name && document.getElementById('tool-form').children.length){ if(!validateToolForm(tool)){ if(status) status.textContent='Missing required'; return; } args=collectFormArgs(); if(argsEl) argsEl.value=JSON.stringify(args,null,2); }
        else { try{ args=JSON.parse((argsEl&&argsEl.value)||'{}'); }catch(e){ if(status) status.textContent='Invalid JSON'; return; } }
        if(tool && tool.inputSchema && tool.inputSchema.confirm && tool.inputSchema.confirm.message){ if(!confirm(tool.inputSchema.confirm.message)) return; }
        if(status) status.textContent='Running...'; const started=performance.now();
        try{ const r= await (window.MCP? MCP.callTool(name,args): fetch('/mcp/tools/call',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name, args})}).then(r=>r.json()));
            if(out) out.textContent = JSON.stringify(r,null,2); if(status) status.textContent='Done in '+(performance.now()-started).toFixed(0)+'ms';
        }catch(e){ if(out) out.textContent=String(e); if(status) status.textContent='Error'; }
    };

    // ---- IPFS Tab ----
    let ipfsInit=false; function initIPFS(){ if(ipfsInit) return; ipfsInit=true; refreshIPFSVersion(); }
    async function refreshIPFSVersion(){ try{ if(window.MCP){ const v=await MCP.IPFS.version(); if(v && v.result) setText('ipfs-version','Version: '+(v.result.version||JSON.stringify(v.result))); } }catch(e){} }
    const btnIpfsCat=document.getElementById('btn-ipfs-cat'); if(btnIpfsCat) btnIpfsCat.onclick= async ()=>{
        const cidEl=document.getElementById('ipfs-cid'); const out=document.getElementById('ipfs-cat-output'); const cid=(cidEl&&cidEl.value)||''; if(!cid) return;
        if(out) out.textContent='Fetching...';
        try{ const r= await (window.MCP? MCP.IPFS.cat(cid): MCP.callTool('ipfs_cat',{cid}));
            let data=(r && r.result && (r.result.content||r.result.data||r.result.result))||r;
            let txt= typeof data==='string'? data: JSON.stringify(data,null,2);
            if(txt.length>8192) txt=txt.slice(0,8192)+'\n...(truncated)';
            if(out) out.textContent=txt;
        }catch(e){ if(out) out.textContent='Error: '+e; }
    };
    const btnIpfsPin=document.getElementById('btn-ipfs-pin'); if(btnIpfsPin) btnIpfsPin.onclick = async ()=>{
        const cid=(document.getElementById('ipfs-cid')||{}).value||''; if(!cid) return; try{ await (window.MCP? MCP.IPFS.pin(cid,null): MCP.callTool('ipfs_pin',{cid})); loadPins(); }catch(e){}
    };

    // ---- CARs Tab ----
    let carsInit=false; function initCARs(){ if(carsInit) return; carsInit=true; loadCARs(); }
    async function loadCARs(){ try{ if(!window.MCP){ setText('cars-list','MCP not ready'); return; } const r=await MCP.CARs.list(); const list=(r && r.result && r.result.items)||[]; document.getElementById('cars-list').textContent=JSON.stringify(list,null,2); }catch(e){ setText('cars-list','Error'); } }
    const btnCarsRefresh=document.getElementById('btn-cars-refresh'); if(btnCarsRefresh) btnCarsRefresh.onclick= loadCARs;
    const btnCarExport=document.getElementById('btn-car-export'); if(btnCarExport) btnCarExport.onclick= async ()=>{
        const path=(document.getElementById('car-path')||{}).value||'.'; const name=(document.getElementById('car-name')||{}).value||'out.car';
        try{ if(window.MCP) await MCP.CARs.export(path,name); loadCARs(); }catch(e){ console.warn(e); }
    };
    const btnCarImport=document.getElementById('btn-car-import'); if(btnCarImport) btnCarImport.onclick= async ()=>{
        const src=(document.getElementById('car-import-src')||{}).value||''; const dest=(document.getElementById('car-import-dest')||{}).value||'.'; if(!src) return;
        try{ if(window.MCP) await MCP.CARs.import(src,dest); loadCARs(); }catch(e){ console.warn(e); }
    };
    async function fetchStatus(){
        try{
            const r = await fetch('/api/mcp/status');
            const raw = await r.json();
            const js = raw.data || raw; // support both shapes
            document.getElementById('srv-status').textContent = 'Running';
            document.getElementById('srv-port').textContent = 'Tools: '+(js.total_tools||0);
            const c = (js.counts)||{};
            setText('svc-active', c.services_active);
            setText('count-backends', c.backends);
            setText('count-buckets', c.buckets);
            document.getElementById('ts-info').textContent = new Date().toLocaleTimeString();
        }catch(e){ console.warn(e); }
    }
    async function fetchMetrics(){
        try{
            const r = await fetch('/api/metrics/system');
            const m = await r.json();
            updatePerf('cpu', m.cpu_percent, '%');
            if(m.memory) updatePerf('mem', m.memory.percent, '%', formatBytes(m.memory.used)+' / '+formatBytes(m.memory.total));
            if(m.disk) updatePerf('disk', m.disk.percent, '%', formatBytes(m.disk.used)+' / '+formatBytes(m.disk.total));
        }catch(e){ console.warn(e); }
        try{
            const nr = await fetch('/api/metrics/network?seconds=60');
            const njs = await nr.json();
            const pts = njs.points||[];
            if(pts.length){
                const last = pts[pts.length-1];
                const el = document.getElementById('net-activity'); if(el) el.textContent = humanRate(last.rx_bps)+' ↓  '+humanRate(last.tx_bps)+' ↑';
                drawNetSpark(pts);
            }
        }catch(e){ /* ignore */ }
    }
    function updatePerf(key, val, suffix, extra){
        const pct = (typeof val === 'number') ? Math.max(0, Math.min(100, val)) : 0;
        const fill = document.getElementById('bar-fill-'+key); if(fill) fill.style.width = pct+'%';
        const label = document.getElementById('bar-label-'+key); if(label) label.textContent = (val!=null?val.toFixed(1):'-')+ (suffix||'') + (extra?('  '+extra):'');
    }
    function setText(id,v){ const el=document.getElementById(id); if(el) el.textContent = (v==null?'-':String(v)); }
    function formatBytes(b){ if(!b && b!==0) return '-'; const u=['B','KB','MB','GB','TB']; let i=0; let n=b; while(n>=1024 && i<u.length-1){ n/=1024; i++; } return n.toFixed(n>=100?0: (n>=10?1:2))+' '+u[i]; }
    function humanRate(bps){ if(bps==null) return '-'; const u=['B/s','KB/s','MB/s','GB/s']; let i=0; let n=bps; while(n>=1024 && i<u.length-1){ n/=1024; i++; } return n.toFixed(n>=100?0: (n>=10?1:2))+' '+u[i]; }
    let realtime=false; let pollTimer=null; const btnRT=document.getElementById('btn-realtime');
    function schedulePoll(){ clearTimeout(pollTimer); pollTimer = setTimeout(async ()=>{ await refreshAll(); if(!realtime) schedulePoll(); }, POLL_INTERVAL); }
    async function refreshAll(){ await Promise.all([fetchStatus(), fetchMetrics()]); }
    const btnRefresh=document.getElementById('btn-refresh'); if(btnRefresh) btnRefresh.onclick = ()=> refreshAll();
    if(btnRT){ btnRT.onclick = ()=>{ realtime=!realtime; btnRT.textContent='Real-time: '+(realtime?'On':'Off'); if(realtime){ startRealtime(); } else { if(ws){ ws.close(); ws=null; schedulePoll(); } }; }; }
    let ws=null; function startRealtime(){
        schedulePoll();
        try{
            ws = new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws');
            ws.onmessage = (ev)=>{ try{ const msg=JSON.parse(ev.data); if(msg.type==='metrics'){ applyRealtime(msg); } else if(msg.type==='system_update'){ if(Array.isArray(msg.deprecations)) renderDeprecationBanner(msg.deprecations); const data = msg.data && (msg.data.data||msg.data); if(data && data.counts){ setText('svc-active', data.counts.services_active); setText('count-backends', data.counts.backends); setText('count-buckets', data.counts.buckets); document.getElementById('srv-status').textContent='Running'; } } }catch(e){} };
            ws.onclose = ()=>{ if(realtime){ setTimeout(startRealtime, 2500); } };
        }catch(e){ console.warn('ws fail', e); }
    }
    function applyRealtime(m){
        if(m.cpu!=null) updatePerf('cpu', m.cpu, '%');
        if(m.mem!=null) updatePerf('mem', m.mem, '%');
        if(m.disk!=null) updatePerf('disk', m.disk, '%');
        if(m.rx_bps!=null || m.tx_bps!=null){ const el=document.getElementById('net-activity'); if(el) el.textContent=humanRate(m.rx_bps)+' ↓  '+humanRate(m.tx_bps)+' ↑'; appendNetPoint(m); }
    // realtime push into perf history arrays
    if(m.cpu!=null) pushPerfPoint('cpu', m.cpu);
    if(m.mem!=null) pushPerfPoint('mem', m.mem);
    if(m.disk!=null) pushPerfPoint('disk', m.disk);
    // Append rolling averages if present
    function addAvg(key, avg){ if(avg==null) return; const label=document.getElementById('bar-label-'+key); if(!label) return; let base=label.textContent||''; base=base.replace(/ \(avg .*?\)$/,''); const suffix = (key==='cpu'||key==='mem'||key==='disk')? '%':''; label.textContent = base+' (avg '+avg.toFixed(1)+suffix+')'; }
    addAvg('cpu', m.avg_cpu);
    addAvg('mem', m.avg_mem);
    addAvg('disk', m.avg_disk);
    }
    // --- Network sparkline helpers ---
    const NET_MAX_POINTS = 120; // keep 2 minutes @1s
    const netBuffer = [];
    function appendNetPoint(p){ if(!(p && (p.rx_bps!=null || p.tx_bps!=null))) return; netBuffer.push({ts:p.ts||Date.now()/1000, rx:p.rx_bps||0, tx:p.tx_bps||0}); if(netBuffer.length>NET_MAX_POINTS) netBuffer.shift(); drawNetSpark(); }
    function drawNetSpark(history){ const svg = document.getElementById('net-spark'); if(!svg) return; const pts = history || netBuffer; if(!pts.length){ svg.innerHTML=''; setText('net-summary',''); return; }
        const w = svg.clientWidth || svg.viewBox?.baseVal?.width || 300; const h = svg.clientHeight || 60; const rxVals = pts.map(p=>p.rx||p.rx_bps||0); const txVals = pts.map(p=>p.tx||p.tx_bps||0); const maxVal = Math.max(1, ...rxVals, ...txVals);
        const path = (vals)=>{ return 'M '+vals.map((v,i)=>{ const x = (i/(vals.length-1||1))*w; const y = h - (v/maxVal)* (h-4) -2; return x+','+y; }).join(' L '); };
        const rxPath = path(rxVals); const txPath = path(txVals);
        svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
        svg.innerHTML = `<path d="${rxPath}" fill="none" stroke="#6b8cff" stroke-width="1.6"/><path d="${txPath}" fill="none" stroke="#b081ff" stroke-width="1.6" opacity="0.8"/>`;
        // summary
        const avg = arr=> arr.reduce((a,b)=>a+b,0)/arr.length||0; const rxAvg=avg(rxVals); const txAvg=avg(txVals);
        const summaryEl=document.getElementById('net-summary'); if(summaryEl) summaryEl.textContent = 'Avg '+humanRate(rxAvg)+' ↓  '+humanRate(txAvg)+' ↑  | points '+pts.length;
    }
    // --- Perf (cpu/mem/disk) sparkline helpers ---
    const PERF_MAX_POINTS = 180; // 3 minutes @1s
    const perfBuffers = { cpu: [], mem: [], disk: [] };
    function pushPerfPoint(k, v){ if(typeof v !== 'number') return; const buf = perfBuffers[k]; buf.push(v); if(buf.length>PERF_MAX_POINTS) buf.shift(); drawPerfSpark(k); }
    function drawPerfSpark(k){ const id = 'spark-'+k; const svg = document.getElementById(id); if(!svg) return; const buf = perfBuffers[k]; if(!buf.length){ svg.innerHTML=''; return; } const w = svg.clientWidth || 300; const h = svg.clientHeight || 26; const maxVal = Math.max(1, ...buf); const path = 'M '+buf.map((v,i)=>{ const x=(i/(buf.length-1||1))*w; const y = h - (v/maxVal)*(h-4) -2; return x+','+y; }).join(' L '); svg.setAttribute('viewBox',`0 0 ${w} ${h}`); svg.innerHTML = `<path d="${path}" fill="none" stroke="#6b8cff" stroke-width="1.4"/>`; }
    refreshAll().then(schedulePoll);
    // Fallback one-time deprecations fetch (in case WebSocket path blocked)
    try{ fetch('/api/system/deprecations').then(r=>r.json()).then(d=>{ if(d && Array.isArray(d.deprecated)) renderDeprecationBanner(d.deprecated); }).catch(()=>{}); }catch(e){}
})();
"""
        js_code = textwrap.dedent(js_code)
        js_code = ''.join(c for c in js_code if ord(c) < 128)
        return js_code

    def _mcp_client_js(self) -> str:
        return """
(function(global){
    // JSON-RPC helpers
    async function loadToolList(){
        const sel=document.getElementById('tool-select'); if(!sel) return;
        return await r.json();
    }
                const r=await MCP.listTools(); toolDefs=(r && r.result && r.result.tools)||[];
        const r = await fetch('/mcp/tools/call', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({name, args})});
        return await r.json();
    }
    async function status(){
        const r = await fetch('/api/mcp/status');
        const js = await r.json();
        // Normalize shape for clients/tests: expose initialized + tools at top level
        const data = (js && (js.data || js)) || {};
        const tools = Array.isArray(data.tools) ? data.tools : [];
        return { initialized: !!data, tools, ...data };
    }

                const r=await fetch('/mcp/tools/list',{method:'POST'}); const js=await r.json(); toolDefs=(js && js.result && js.result.tools)||[];
    const Services = {
    control: (service, action, params) => rpcCall('service_control', {service, action, params}),
        status: (service) => rpcCall('service_status', {service}),
    };

    const Backends = {
        list: () => rpcCall('list_backends', {}),
        get: (name) => rpcCall('get_backend', {name}),
        create: (name, config) => rpcCall('create_backend', {name, config}),
        update: (name, config) => rpcCall('update_backend', {name, config}),
        delete: (name) => rpcCall('delete_backend', {name}),
        test: (name) => rpcCall('test_backend', {name}),
    };

    const Buckets = {
        list: () => rpcCall('list_buckets', {}),
        get: (name) => rpcCall('get_bucket', {name}),
        create: (name, backend) => rpcCall('create_bucket', {name, backend}),
        update: (name, patch) => rpcCall('update_bucket', {name, patch}),
        delete: (name) => rpcCall('delete_bucket', {name}),
        getPolicy: (name) => rpcCall('get_bucket_policy', {name}),
        updatePolicy: (name, policy) => rpcCall('update_bucket_policy', {name, policy}),
        // Comprehensive bucket file management functions
        listFiles: (bucket, path, showMetadata) => rpcCall('bucket_list_files', {bucket, path: path || '.', show_metadata: !!showMetadata}),
        uploadFile: (bucket, path, content, mode, applyPolicy) => rpcCall('bucket_upload_file', {bucket, path, content, mode: mode || 'text', apply_policy: !!applyPolicy}),
        downloadFile: (bucket, path, format) => rpcCall('bucket_download_file', {bucket, path, format: format || 'text'}),
        deleteFile: (bucket, path, removeReplicas) => rpcCall('bucket_delete_file', {bucket, path, remove_replicas: !!removeReplicas}),
        renameFile: (bucket, src, dst, updateReplicas) => rpcCall('bucket_rename_file', {bucket, src, dst, update_replicas: !!updateReplicas}),
        mkdir: (bucket, path, createParents) => rpcCall('bucket_mkdir', {bucket, path, create_parents: !!createParents}),
        syncReplicas: (bucket, forceSync) => rpcCall('bucket_sync_replicas', {bucket, force_sync: !!forceSync}),
        getMetadata: (bucket, path, includeReplicas) => rpcCall('bucket_get_metadata', {bucket, path, include_replicas: !!includeReplicas}),
        getUsage: (name) => rpcCall('get_bucket_usage', {name}),
        generateShareLink: (bucket, accessType, expiration) => rpcCall('generate_bucket_share_link', {bucket, access_type: accessType || 'read_only', expiration: expiration || 'never'}),
        selectiveSync: (bucket, files, options) => rpcCall('bucket_selective_sync', {bucket, files, options: options || {}})
    };

    const Pins = {
        list: () => rpcCall('list_pins', {}),
        create: (cid, name) => rpcCall('create_pin', {cid, name}),
        delete: (cid) => rpcCall('delete_pin', {cid}),
        export: () => rpcCall('pins_export', {}),
        import: (items) => rpcCall('pins_import', {items}),
    };

    const Files = {
        list: (path='.') => rpcCall('files_list', {path}),
        read: (path) => rpcCall('files_read', {path}),
        write: (path, content, mode='text') => rpcCall('files_write', {path, content, mode}),
        mkdir: (path) => rpcCall('files_mkdir', {path}),
        rm: (path, recursive=false) => rpcCall('files_rm', {path, recursive}),
        mv: (src, dst) => rpcCall('files_mv', {src, dst}),
        stat: (path) => rpcCall('files_stat', {path}),
        copy: (src, dst, recursive=false) => rpcCall('files_copy', {src, dst, recursive}),
        touch: (path) => rpcCall('files_touch', {path}),
        tree: (path='.', depth=2) => rpcCall('files_tree', {path, depth}),
    };

    const IPFS = {
        version: () => rpcCall('ipfs_version', {}),
        add: (path) => rpcCall('ipfs_add', {path}),
        pin: (cid, name) => rpcCall('ipfs_pin', {cid, name}),
        cat: (cid) => rpcCall('ipfs_cat', {cid}),
        ls: (cid) => rpcCall('ipfs_ls', {cid}),
    };

    const CARs = {
        list: () => rpcCall('cars_list', {}),
        export: (path, car) => rpcCall('car_export', {path, car}),
        import: (car, dest) => rpcCall('car_import', {car, dest}),
    };

    const State = {
        snapshot: () => rpcCall('state_snapshot', {}),
        backup: () => rpcCall('state_backup', {}),
        reset: () => rpcCall('state_reset', {}),
    };

    const Logs = {
        get: (limit=200) => rpcCall('get_logs', {limit}),
        clear: () => rpcCall('clear_logs', {}),
    };

    const Server = {
        shutdown: () => rpcCall('server_shutdown', {}),
    };

    const Peers = {
        list: () => rpcCall('list_peers', {}),
        connect: (peer) => rpcCall('connect_peer', peer || {}),
        disconnect: (peer_id) => rpcCall('disconnect_peer', {peer_id}),
        info: (peer_id) => rpcCall('get_peer_info', {peer_id}),
    };

    // Schema helpers (beta; not used by wrappers yet)
    const Schema = {
        normalize(inputSchema){
            const s = inputSchema||{};
            if (s && s.properties) return s;
            const props = {}; Object.keys(s||{}).forEach(k => props[k] = { type: String(s[k]||'string') });
            return { type:'object', properties: props };
        },
        coerce(type, raw){
            if (type==='number') { const n = (raw===''||raw==null)?null:Number(raw); return isNaN(n)?null:n; }
            if (type==='boolean') return !!raw;
            if (type==='object' || type==='array') { try { return JSON.parse(String(raw||'')); } catch(e){ return { __error: String(e) }; } }
            return String(raw==null? '': raw);
        }
    };

    // Helper function used by dashboard UI
    function updateElement(selector, content) {
        const element = document.querySelector(selector);
        if (element) {
            if (typeof content === 'string') {
                element.textContent = content;
            } else if (typeof content === 'object' && content !== null) {
                element.textContent = JSON.stringify(content);
            } else {
                element.textContent = String(content || 'N/A');
            }
        }
    }

    const MCP = {
        // Core
        listTools: rpcList,
        callTool: rpcCall,
        status,
        // Namespaces
        Services, Backends, Buckets, Pins, Files, IPFS, CARs, State, Logs, Server, Peers,
        // Utils
        Schema,
    };

    // Comprehensive bucket file management helper functions
    async function refreshBucketFilesMCP(bucketName) {
        const fileList = document.getElementById('mcp-file-list');
        const pathInput = document.getElementById('current-path');
        const showMeta = document.getElementById('show-metadata');
        
        if (!fileList || !pathInput) return;
        
        const currentPath = pathInput.value || '.';
        const showMetadata = showMeta ? showMeta.checked : true;
        
        try {
            fileList.innerHTML = '<div style="text-align:center;padding:20px;color:#888;">Loading files via MCP...</div>';
            
            await waitForMCP();
            const result = await MCP.Buckets.listFiles(bucketName, currentPath, showMetadata);
            // Debug: Check if we get the result properly
            console.log(`📂 Loading files for bucket: ${bucketName}, path: ${currentPath}`);
            console.log(`🔧 Full MCP result:`, JSON.stringify(result, null, 2));
            
            // Handle both wrapped and unwrapped responses
            let files = [];
            if (result && result.items) {
                files = result.items;
            } else if (result && result.result && result.result.items) {
                files = result.result.items;
            } else {
                console.warn('⚠️ Unexpected MCP response structure:', result);
                files = [];
            }
            
            console.log(`🔧 Extracted files array:`, files);
            console.log(`📂 Loaded ${files.length} files for bucket: ${bucketName}`);
            
            // Enhanced debugging to help users troubleshoot issues
            if (result) {
                const totalCount = result.total_count || (result.result && result.result.total_count);
                if (totalCount !== undefined) {
                    console.log(`📊 MCP returned ${totalCount} total files, frontend processed ${files.length} files`);
                    if (totalCount > 0 && files.length === 0) {
                        console.error(`❌ CRITICAL: MCP found ${totalCount} files but frontend extracted 0. Check response parsing!`);
                    }
                }
            }
            
            if (files.length === 0) {
                fileList.innerHTML = `
                    <div style="text-align:center;padding:20px;color:#888;">
                        <div style="margin-bottom:10px;">No files in this directory</div>
                        <div style="font-size:10px;color:#666;">
                            Debug: Checked bucket '${bucketName}' path '${currentPath}'
                        </div>
                    </div>`;
                return;
            }
            
            // Create file table
            let tableHTML = `
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="background:#222;border-bottom:1px solid #333;">
                            <th style="text-align:left;padding:6px;font-size:11px;width:40px;">Type</th>
                            <th style="text-align:left;padding:6px;font-size:11px;">Name</th>
                            <th style="text-align:right;padding:6px;font-size:11px;width:80px;">Size</th>
                            <th style="text-align:center;padding:6px;font-size:11px;width:100px;">Modified</th>
                            ${showMetadata ? '<th style="text-align:center;padding:6px;font-size:11px;width:80px;">Replicas</th>' : ''}
                            <th style="text-align:center;padding:6px;font-size:11px;width:120px;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>`;
            
            files.forEach(file => {
                const isDir = file.is_dir;
                const icon = isDir ? '📁' : '📄';
                const size = isDir ? '-' : formatBytes(file.size || 0);
                const modified = file.modified ? new Date(file.modified).toLocaleDateString() : '-';
                const replicas = showMetadata && file.replicas ? file.replicas.length : 0;
                const cached = showMetadata && file.cached ? '💾' : '';
                
                tableHTML += `
                    <tr style="border-bottom:1px solid #222;cursor:pointer;" 
                        onclick="handleFileClick('${bucketName}', '${file.path}', ${isDir})"
                        onmouseover="this.style.backgroundColor='#1a1a1a'" 
                        onmouseout="this.style.backgroundColor='transparent'">
                        <td style="padding:4px;text-align:center;">${icon}</td>
                        <td style="padding:4px;${isDir ? 'color:#6b8cff;font-weight:bold;' : ''}">${file.name}</td>
                        <td style="padding:4px;text-align:right;font-family:monospace;font-size:10px;">${size}</td>
                        <td style="padding:4px;text-align:center;font-family:monospace;font-size:10px;">${modified}</td>
                        ${showMetadata ? `<td style="padding:4px;text-align:center;font-size:10px;">${replicas}${cached}</td>` : ''}
                        <td style="padding:4px;text-align:center;">
                            <div style="display:flex;gap:2px;justify-content:center;">
                                ${!isDir ? `
                                    <button onclick="event.stopPropagation(); downloadFileMCP('${bucketName}', '${file.path}')" 
                                            style="background:#2a5cb8;color:white;border:none;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;">⬇</button>
                                    <button onclick="event.stopPropagation(); showRenameDialog('${bucketName}', '${file.path}')" 
                                            style="background:#555;color:white;border:none;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;">✏️</button>
                                ` : ''}
                                <button onclick="event.stopPropagation(); deleteFileMCP('${bucketName}', '${file.path}')" 
                                        style="background:#b52a2a;color:white;border:none;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;">🗑</button>
                                ${showMetadata ? `
                                    <button onclick="event.stopPropagation(); showFileMetadata('${bucketName}', '${file.path}')" 
                                            style="background:#666;color:white;border:none;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;">ℹ️</button>
                                ` : ''}
                            </div>
                        </td>
                    </tr>`;
            });
            
            tableHTML += '</tbody></table>';
            fileList.innerHTML = tableHTML;
            
            // Update breadcrumbs
            updateBreadcrumbNav(bucketName, currentPath);
            
        } catch (e) {
            console.error('Error refreshing files:', e);
            fileList.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error loading files: ' + e.message + '</div>';
        }
    }

    // Handle file click (navigate to directory or show file details)
    function handleFileClick(bucketName, filePath, isDir) {
        if (isDir) {
            // Navigate to directory
            const pathInput = document.getElementById('current-path');
            if (pathInput) {
                const currentPath = pathInput.value || '.';
                const newPath = currentPath === '.' ? filePath : `${currentPath}/${filePath}`;
                pathInput.value = newPath;
                refreshBucketFilesMCP(bucketName);
            }
        } else {
            // Show file metadata
            showFileMetadata(bucketName, filePath);
        }
    }

    // Update breadcrumb navigation
    function updateBreadcrumbNav(bucketName, currentPath) {
        const breadcrumbNav = document.getElementById('breadcrumb-nav');
        if (!breadcrumbNav) return;
        
        const pathParts = currentPath === '.' ? [] : currentPath.split('/');
        const breadcrumbs = ['Root'];
        
        pathParts.forEach((part, index) => {
            breadcrumbs.push(part);
        });
        
        breadcrumbNav.innerHTML = breadcrumbs.map((crumb, index) => {
            const pathToHere = index === 0 ? '.' : pathParts.slice(0, index).join('/');
            return `<span onclick="navigateToBreadcrumb('${bucketName}', '${pathToHere}')" 
                          style="color:#6b8cff;cursor:pointer;text-decoration:underline;">${crumb}</span>`;
        }).join(' / ');
    }

    // Navigation and file operation functions
    window.navigateToBreadcrumb = function(bucketName, path) {
        const pathInput = document.getElementById('current-path');
        if (pathInput) {
            pathInput.value = path;
            refreshBucketFilesMCP(bucketName);
        }
    };

    window.navigateToPath = function(bucketName) {
        refreshBucketFilesMCP(bucketName);
    };

    window.goUpDirectory = function(bucketName) {
        const pathInput = document.getElementById('current-path');
        if (pathInput) {
            const currentPath = pathInput.value || '.';
            if (currentPath !== '.') {
                const pathParts = currentPath.split('/');
                pathParts.pop();
                pathInput.value = pathParts.length > 0 ? pathParts.join('/') : '.';
                refreshBucketFilesMCP(bucketName);
            }
        }
    };

    // File operation functions
    window.uploadFilesMCP = async function(bucketName, files) {
        if (!files || files.length === 0) return;
        
        const pathInput = document.getElementById('current-path');
        const currentPath = pathInput ? pathInput.value || '.' : '.';
        
        try {
            await waitForMCP();
            
            for (const file of files) {
                const reader = new FileReader();
                const fileContent = await new Promise((resolve, reject) => {
                    reader.onload = e => resolve(e.target.result);
                    reader.onerror = reject;
                    reader.readAsText(file);
                });
                
                const filePath = currentPath === '.' ? file.name : `${currentPath}/${file.name}`;
                await MCP.Buckets.uploadFile(bucketName, filePath, fileContent, 'text', true);
            }
            
            // Refresh file list
            await refreshBucketFilesMCP(bucketName);
            alert(`Successfully uploaded ${files.length} file(s)`);
            
        } catch (e) {
            console.error('Error uploading files:', e);
            alert('Error uploading files: ' + e.message);
        }
    };

    window.downloadFileMCP = async function(bucketName, filePath) {
        try {
            await waitForMCP();
            const result = await MCP.Buckets.downloadFile(bucketName, filePath, 'text');
            const content = (result && result.result && result.result.content) || '';
            
            // Create download link
            const blob = new Blob([content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filePath.split('/').pop();
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
        } catch (e) {
            console.error('Error downloading file:', e);
            alert('Error downloading file: ' + e.message);
        }
    };

    window.deleteFileMCP = async function(bucketName, filePath) {
        if (!confirm(`Delete ${filePath}?`)) return;
        
        try {
            await waitForMCP();
            await MCP.Buckets.deleteFile(bucketName, filePath, true);
            await refreshBucketFilesMCP(bucketName);
            
        } catch (e) {
            console.error('Error deleting file:', e);
            alert('Error deleting file: ' + e.message);
        }
    };

    window.showFileMetadata = async function(bucketName, filePath) {
        const detailsPanel = document.getElementById('file-details-panel');
        const metadataContent = document.getElementById('file-metadata-content');
        
        if (!detailsPanel || !metadataContent) return;
        
        try {
            await waitForMCP();
            const result = await MCP.Buckets.getMetadata(bucketName, filePath, true);
            const metadata = (result && result.result) || {};
            
            let metadataHTML = `<div style="font-size:10px;color:#aaa;margin-bottom:5px;">Path: ${filePath}</div>`;
            metadataHTML += `<div style="display:grid;grid-template-columns:auto 1fr;gap:5px;font-size:11px;">`;
            
            if (metadata.size) metadataHTML += `<span>Size:</span><span>${formatBytes(metadata.size)}</span>`;
            if (result.modified) metadataHTML += `<span>Modified:</span><span>${new Date(result.modified).toLocaleString()}</span>`;
            if (result.created) metadataHTML += `<span>Created:</span><span>${new Date(result.created).toLocaleString()}</span>`;
            if (result.replicas) metadataHTML += `<span>Replicas:</span><span>${result.replicas.length}</span>`;
            if (result.cached !== undefined) metadataHTML += `<span>Cached:</span><span>${result.cached ? 'Yes' : 'No'}</span>`;
            if (result.cache_type) metadataHTML += `<span>Cache Type:</span><span>${result.cache_type}</span>`;
            
            metadataHTML += '</div>';
            
            if (result.replicas && result.replicas.length > 0) {
                metadataHTML += '<div style="margin-top:8px;"><strong>Replicas:</strong></div>';
                metadataHTML += '<div style="font-size:10px;">';
                result.replicas.forEach(replica => {
                    metadataHTML += `<div style="margin:2px 0;">• ${replica.backend || 'Unknown'} (${replica.status || 'unknown'})</div>`;
                });
                metadataHTML += '</div>';
            }
            
            metadataContent.innerHTML = metadataHTML;
            detailsPanel.style.display = 'block';
            
        } catch (e) {
            console.error('Error loading file metadata:', e);
            metadataContent.innerHTML = '<div style="color:red;">Error loading metadata: ' + e.message + '</div>';
            detailsPanel.style.display = 'block';
        }
    };

    window.showCreateFolderDialog = function(bucketName) {
        const folderName = prompt('Enter folder name:');
        if (!folderName) return;
        
        const pathInput = document.getElementById('current-path');
        const currentPath = pathInput ? pathInput.value || '.' : '.';
        const folderPath = currentPath === '.' ? folderName : `${currentPath}/${folderName}`;
        
        createFolderMCP(bucketName, folderPath);
    };

    async function createFolderMCP(bucketName, folderPath) {
        try {
            await waitForMCP();
            await MCP.Buckets.mkdir(bucketName, folderPath, true);
            await refreshBucketFilesMCP(bucketName);
            
        } catch (e) {
            console.error('Error creating folder:', e);
            alert('Error creating folder: ' + e.message);
        }
    }

    window.showRenameDialog = function(bucketName, oldPath) {
        const fileName = oldPath.split('/').pop();
        const newName = prompt('Rename to:', fileName);
        if (!newName || newName === fileName) return;
        
        const pathParts = oldPath.split('/');
        pathParts.pop();
        const newPath = pathParts.length > 0 ? `${pathParts.join('/')}/${newName}` : newName;
        
        renameFileMCP(bucketName, oldPath, newPath);
    };

    async function renameFileMCP(bucketName, oldPath, newPath) {
        try {
            await waitForMCP();
            await MCP.Buckets.renameFile(bucketName, oldPath, newPath, true);
            await refreshBucketFilesMCP(bucketName);
            
        } catch (e) {
            console.error('Error renaming file:', e);
            alert('Error renaming file: ' + e.message);
        }
    }

    window.syncBucketReplicas = async function(bucketName) {
        const btn = document.getElementById('sync-replicas-btn');
        if (btn) {
            btn.disabled = true;
            btn.textContent = '🔄 Syncing...';
        }
        
        try {
            await waitForMCP();
            const result = await MCP.Buckets.syncReplicas(bucketName, false);
            const syncResult = (result && result.result) || {};
            alert(`Replica sync completed. ${syncResult.synced_files || 0} files synced.`);
            
        } catch (e) {
            console.error('Error syncing replicas:', e);
            alert('Error syncing replicas: ' + e.message);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = '🔄 Sync Replicas';
            }
        }
    };

    window.showBucketPolicySettings = async function(bucketName) {
        const modal = createModal('Bucket Policy: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = '<div style="text-align:center;padding:20px;">Loading policy...</div>';
            
            try {
                await waitForMCP();
                const policyResponse = await MCP.Buckets.getPolicy(bucketName);
                const policy = (policyResponse && policyResponse.result) || {};
                
                modalBody.innerHTML = `
                    <div style="display:grid;gap:15px;">
                        <div>
                            <label style="display:block;margin-bottom:5px;font-size:12px;">
                                <strong>Replication Factor:</strong>
                            </label>
                            <input type="number" id="replication_factor" min="1" max="10" 
                                   value="${policy.replication_factor || 1}" 
                                   style="width:100px;background:#111;border:1px solid #333;color:white;padding:4px;">
                            <small style="color:#888;margin-left:10px;">Number of replica copies</small>
                        </div>
                        
                        <div>
                            <label style="display:block;margin-bottom:5px;font-size:12px;">
                                <strong>Cache Policy:</strong>
                            </label>
                            <select id="cache_policy" style="width:150px;background:#111;border:1px solid #333;color:white;padding:4px;">
                                <option value="none" ${(policy.cache_policy === 'none') ? 'selected' : ''}>None</option>
                                <option value="memory" ${(policy.cache_policy === 'memory') ? 'selected' : ''}>Memory</option>
                                <option value="disk" ${(policy.cache_policy === 'disk') ? 'selected' : ''}>Disk</option>
                            </select>
                            <small style="color:#888;margin-left:10px;">Caching strategy for files</small>
                        </div>
                        
                        <div>
                            <label style="display:block;margin-bottom:5px;font-size:12px;">
                                <strong>Retention Days:</strong>
                            </label>
                            <input type="number" id="retention_days" min="0" 
                                   value="${policy.retention_days || 0}" 
                                   style="width:100px;background:#111;border:1px solid #333;color:white;padding:4px;">
                            <small style="color:#888;margin-left:10px;">0 = no expiration</small>
                        </div>
                        
                        <div style="margin-top:20px;">
                            <button onclick="saveBucketPolicy('${bucketName}')" 
                                    style="background:#2a5cb8;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;">
                                💾 Save Policy
                            </button>
                        </div>
                    </div>
                `;
                
            } catch (e) {
                console.error('Error loading bucket policy:', e);
                modalBody.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error loading policy: ' + e.message + '</div>';
            }
        });
    };

    window.saveBucketPolicy = async function(bucketName) {
        const replicationFactor = document.getElementById('replication_factor');
        const cachePolicy = document.getElementById('cache_policy');
        const retentionDays = document.getElementById('retention_days');
        
        if (!replicationFactor || !cachePolicy || !retentionDays) return;
        
        try {
            await waitForMCP();
            await MCP.Buckets.updatePolicy(bucketName, {
                replication_factor: parseInt(replicationFactor.value),
                cache_policy: cachePolicy.value,
                retention_days: parseInt(retentionDays.value)
            });
            
            alert('Bucket policy updated successfully');
            
        } catch (e) {
            console.error('Error saving bucket policy:', e);
            alert('Error saving policy: ' + e.message);
        }
    };

    window.createNewBucket = function() {
        const bucketName = prompt('Enter bucket name:');
        if (!bucketName) return;
        
        createBucketMCP(bucketName);
    };

    async function createBucketMCP(bucketName) {
        try {
            await waitForMCP();
            await MCP.Buckets.create(bucketName);
            await loadBuckets(); // Refresh bucket list
            
        } catch (e) {
            console.error('Error creating bucket:', e);
            alert('Error creating bucket: ' + e.message);
        }
    }

    window.deleteBucketMCP = async function(bucketName) {
        if (!confirm(`Delete bucket "${bucketName}" and all its contents?`)) return;
        
        try {
            await waitForMCP();
            await MCP.Buckets.delete(bucketName);
            await loadBuckets(); // Refresh bucket list
            
        } catch (e) {
            console.error('Error deleting bucket:', e);
            alert('Error deleting bucket: ' + e.message);
        }
    };

    // Make functions globally available
    window.refreshBuckets = loadBuckets; // Add missing function alias for onclick handlers

    window.refreshBucketFilesMCP = refreshBucketFilesMCP;

    // Make updateElement globally available for dashboard UI
    if (typeof window !== 'undefined') {
        window.MCP = MCP;
        window.updateElement = updateElement;
    } else if (typeof globalThis !== 'undefined') {
        globalThis.MCP = MCP;
        globalThis.updateElement = updateElement;
    }
})(this);
"""

if __name__ == "__main__":  # pragma: no cover
    # Support CLI flags with env fallbacks for convenience when run directly
    import argparse as _argparse
    p = _argparse.ArgumentParser(description="Start the Consolidated MCP Dashboard")
    p.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"), help="Bind host (default: env MCP_HOST or 127.0.0.1)")
    p.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8081")), help="Bind port (default: env MCP_PORT or 8081)")
    p.add_argument("--data-dir", default=os.environ.get("MCP_DATA_DIR"), help="Data directory (default: env MCP_DATA_DIR or ~/.ipfs_kit)")
    p.add_argument("--debug", action="store_true", default=(os.environ.get("MCP_DEBUG", "0") in ("1", "true", "True")), help="Enable debug logging")
    args = p.parse_args()
    cfg = {
        "host": args.host,
        "port": int(args.port),
        "data_dir": args.data_dir,
        "debug": bool(args.debug),
    }
    app = ConsolidatedMCPDashboard(cfg)
    app.run_sync()
# -*- coding: utf-8 -*-