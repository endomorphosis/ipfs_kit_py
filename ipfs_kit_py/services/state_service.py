#!/usr/bin/env python3
"""
StateService - Shared lightweight service for MCP/CLI parity

Provides a unified, light-initialization API to read/write program and daemon
state from the IPFS Kit data directory (default: ~/.ipfs_kit). Avoids heavy
imports and focuses on file-based state and simple system introspection so it
can be safely used by both the CLI and the MCP server tools.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import yaml


@dataclass
class StateService:
    data_dir: Path
    start_time: Optional[datetime] = None

    def __post_init__(self):
        self.data_dir = Path(self.data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_structure()
        if self.start_time is None:
            self.start_time = datetime.now()

    # Files
    @property
    def backends_dir(self) -> Path:
        return self.data_dir / "backend_configs"

    @property
    def buckets_file(self) -> Path:
        return self.data_dir / "buckets.json"

    @property
    def pins_file(self) -> Path:
        return self.data_dir / "pins.json"

    def _ensure_structure(self):
        self.backends_dir.mkdir(parents=True, exist_ok=True)
        # Initialize basic files if missing
        if not self.buckets_file.exists():
            self.buckets_file.write_text(json.dumps({"buckets": []}, indent=2))
        if not self.pins_file.exists():
            self.pins_file.write_text(json.dumps({"pins": []}, indent=2))

    # Utilities
    def _read_json(self, path: Path, default: Any) -> Any:
        try:
            if path.exists():
                return json.loads(path.read_text())
        except Exception:
            pass
        return default

    def _write_json(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, indent=2))

    # System
    def get_system_status(self) -> Dict[str, Any]:
        uptime = datetime.now() - (self.start_time or datetime.now())
        mem = psutil.virtual_memory()
        status = {
            "timestamp": datetime.now().isoformat(),
            "uptime": str(uptime),
            # These can be wired to real checks later
            "ipfs_api": "unavailable",
            "bucket_manager": "unavailable",
            "unified_bucket_interface": "unavailable",
            "data_dir": str(self.data_dir),
            "data_dir_exists": self.data_dir.exists(),
            "component_status": {
                "ipfs": False,
                "bucket_manager": False,
                "unified_bucket_interface": False,
                "pin_metadata": False,
                "psutil": True,
                "yaml": True,
            },
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "memory_percent": mem.percent,
            "memory_available": mem.available,
            "memory_total": mem.total,
        }
        return status

    def get_system_overview(self) -> Dict[str, Any]:
        services_count = 3
        backends_count = len(self.list_backends())
        buckets_count = len(self.list_buckets())
        pins_count = len(self.list_pins())
        uptime = datetime.now() - (self.start_time or datetime.now())
        return {
            "services": services_count,
            "backends": backends_count,
            "buckets": buckets_count,
            "pins": pins_count,
            "uptime": str(uptime),
            "status": "running",
        }

    # Services (mocked for now, unified interface)
    def list_services(self) -> List[Dict[str, Any]]:
        return [
            {"name": "IPFS Node", "type": "ipfs", "status": "stopped", "description": "IPFS node connection"},
            {"name": "Bucket Manager", "type": "bucket", "status": "stopped", "description": "Bucket VFS manager"},
            {"name": "Unified Interface", "type": "interface", "status": "stopped", "description": "Unified bucket interface"},
        ]

    def control_service(self, service: str, action: str) -> Dict[str, Any]:
        return {
            "service": service,
            "action": action,
            "status": "success",
            "message": f"Service '{service}' {action} command executed",
        }

    # Backends
    def list_backends(self) -> List[Dict[str, Any]]:
        backends: List[Dict[str, Any]] = []
        if self.backends_dir.exists():
            for config_file in sorted(self.backends_dir.glob("*.yaml")):
                try:
                    config = yaml.safe_load(config_file.read_text()) or {}
                    backends.append({
                        "name": config_file.stem,
                        "type": config.get("type", "unknown"),
                        "status": "configured",
                        "config_file": str(config_file),
                    })
                except Exception:
                    continue
        return backends

    # Buckets (file-based store)
    def list_buckets(self) -> List[Dict[str, Any]]:
        data = self._read_json(self.buckets_file, {"buckets": []})
        return data.get("buckets", [])

    def create_bucket(self, name: str, backend: str) -> Dict[str, Any]:
        data = self._read_json(self.buckets_file, {"buckets": []})
        bucket = {
            "name": name,
            "backend": backend,
            "status": "created",
            "created_at": datetime.now().isoformat(),
        }
        data.setdefault("buckets", []).append(bucket)
        self._write_json(self.buckets_file, data)
        return bucket

    # Pins (file-based store)
    def list_pins(self) -> List[Dict[str, Any]]:
        data = self._read_json(self.pins_file, {"pins": []})
        return data.get("pins", [])

    def create_pin(self, cid: str, name: str = "") -> Dict[str, Any]:
        data = self._read_json(self.pins_file, {"pins": []})
        pin = {
            "cid": cid,
            "name": name,
            "status": "pinned",
            "pinned_at": datetime.now().isoformat(),
        }
        data.setdefault("pins", []).append(pin)
        self._write_json(self.pins_file, data)
        return pin
