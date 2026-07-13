"""Validated, atomic management of named storage backends."""
from __future__ import annotations
import copy, os, tempfile
from pathlib import Path
from typing import Any, Mapping
import yaml
from .backend_registry import BackendConfigError, BackendTypeRegistry, UnknownBackendTypeError, get_backend_type_registry, redact_backend_config, validate_backend_name

def list_supported_backends() -> list[str]:
    return list(get_backend_type_registry().types())

class BackendManager:
    def __init__(self, ipfs_kit_path=None, *, registry=None, health_probes=None):
        self.ipfs_kit_path = Path(ipfs_kit_path or Path.home() / ".ipfs_kit")
        self.backends_path = self.ipfs_kit_path / "backends"
        self.registry = registry or get_backend_type_registry()
        self.health_probes = dict(health_probes or {})
    def _path(self, name): return self.backends_path / f"{validate_backend_name(name)}.yaml"
    def _read_raw(self, name):
        path = self._path(name)
        if not path.is_file(): raise FileNotFoundError(f"Backend not found: {name}")
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict): raise BackendConfigError("backend document must be an object")
        return value
    def _normalize(self, value):
        plugin = self.registry.get(value.get("type"))
        return plugin.migrate(value) if value.get("type") == "iroh" else plugin.validate(value)
    def _write(self, name, value):
        path = self._path(name); path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                yaml.safe_dump(dict(value), stream, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path); os.chmod(path, 0o600)
        except Exception:
            try: os.close(fd)
            except OSError: pass
            try: os.unlink(temporary)
            except OSError: pass
            raise
        return path
    @staticmethod
    def _error(error): return {"error": str(error), "code": getattr(error, "code", "backend_error")}
    def create_backend(self, name, type, config=None, **kwargs):
        try:
            if self._path(name).exists(): return {"error": "Backend with this name already exists", "code": "backend_exists"}
            document = {"name": name, "type": type}; document.update(copy.deepcopy(dict(config or {}))); document.update(copy.deepcopy(kwargs))
            normalized = self.registry.get(type).validate(document); self._write(name, normalized)
            return {"status": "Backend created", "backend": redact_backend_config(normalized)}
        except (BackendConfigError, UnknownBackendTypeError, ValueError) as error: return self._error(error)
    def update_backend(self, name, **kwargs):
        try:
            candidate = copy.deepcopy(self._normalize(self._read_raw(name))); candidate.update(copy.deepcopy(kwargs))
            normalized = self.registry.get(candidate["type"]).validate(candidate); self._write(name, normalized)
            return {"status": "Backend updated", "backend": redact_backend_config(normalized)}
        except Exception as error: return self._error(error)
    def remove_backend(self, name):
        try: self._path(name).unlink(); return {"status": "Backend removed"}
        except Exception as error: return self._error(error)
    def get_backend_config(self, name, *, redact=True):
        value = self._normalize(self._read_raw(name)); return redact_backend_config(value) if redact else value
    def show_backend(self, name):
        try: return self.get_backend_config(name)
        except Exception as error: return self._error(error)
    def list_backends(self):
        values = []
        if self.backends_path.is_dir():
            for path in sorted(self.backends_path.glob("*.yaml")):
                value = self.show_backend(path.stem)
                if "error" not in value: values.append(value)
        return {"backends": values, "total": len(values)}
    def validate_backend_config(self, config): return self.registry.get(config.get("type")).validate(config)
    def get_backend_schema(self, backend_type): return self.registry.get(backend_type).schema()
    def get_backend_capabilities(self, name):
        config = self.get_backend_config(name, redact=False); return self.registry.get(config["type"]).capabilities(config)
    def get_backend_health(self, name):
        config = self.get_backend_config(name, redact=False); probe = self.health_probes.get(config["type"])
        return redact_backend_config(probe(copy.deepcopy(config)) if probe else self.registry.get(config["type"]).health(config))
    def get_backend_info(self, name):
        config = self.get_backend_config(name); return {"name": name, "type": config["type"], "config": config, "capabilities": self.get_backend_capabilities(name), "health": self.get_backend_health(name)}
    def migrate_backend(self, name):
        raw = self._read_raw(name); migrated = self.registry.get(raw.get("type")).migrate(raw)
        if migrated == raw: return {"changed": False, "backend": redact_backend_config(migrated)}
        path = self._path(name); backup = path.with_suffix(path.suffix + ".bak"); backup.write_bytes(path.read_bytes()); os.chmod(backup, 0o600); self._write(name, migrated)
        return {"changed": True, "backup": str(backup), "backend": redact_backend_config(migrated)}
    def get_backend_adapter(self, name, **storage_options):
        config = self.get_backend_config(name, redact=False); return self.registry.get(config["type"]).create_filesystem(config, **storage_options)

__all__ = ["BackendManager", "list_supported_backends"]
