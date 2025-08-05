import os
import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class BackendManager:
    def __init__(self, ipfs_kit_path=None):
        self.ipfs_kit_path = Path(ipfs_kit_path or os.path.expanduser("~/.ipfs_kit"))
        self.backends_path = self.ipfs_kit_path / "backends"
        self.backends_path.mkdir(parents=True, exist_ok=True)

    def _get_backend_config_path(self, name):
        return self.backends_path / f"{name}.yaml"

    def list_backends(self):
        backends = []
        for config_file in self.backends_path.glob("*.yaml"):
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                    backends.append(config)
            except Exception as e:
                logger.error(f"Error loading backend config {config_file}: {e}")
        return {"backends": backends, "total": len(backends)}

    def show_backend(self, name):
        config_path = self._get_backend_config_path(name)
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.error(f"Error loading backend config {config_path}: {e}")
                return {"error": str(e)}
        return {"error": "Backend not found"}

    def create_backend(self, name, type, **kwargs):
        config_path = self._get_backend_config_path(name)
        if config_path.exists():
            return {"error": "Backend with this name already exists"}
        
        config = {"name": name, "type": type, **kwargs}
        try:
            with open(config_path, 'w') as f:
                yaml.safe_dump(config, f)
            return {"status": "Backend created", "backend": config}
        except Exception as e:
            logger.error(f"Error creating backend {name}: {e}")
            return {"error": str(e)}

    def update_backend(self, name, **kwargs):
        config_path = self._get_backend_config_path(name)
        if not config_path.exists():
            return {"error": "Backend not found"}
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            config.update(kwargs)
            with open(config_path, 'w') as f:
                yaml.safe_dump(config, f)
            return {"status": "Backend updated", "backend": config}
        except Exception as e:
            logger.error(f"Error updating backend {name}: {e}")
            return {"error": str(e)}

    def remove_backend(self, name):
        config_path = self._get_backend_config_path(name)
        if not config_path.exists():
            return {"error": "Backend not found"}
        
        try:
            os.remove(config_path)
            return {"status": "Backend removed"}
        except Exception as e:
            logger.error(f"Error removing backend {name}: {e}")
            return {"error": str(e)}
