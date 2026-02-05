import yaml
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

class ConfigManager:
    """Manages reading and writing of YAML configuration files."""

    def __init__(self, config_dir: Path = Path.home() / ".ipfs_kit" / "config"):
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create buckets and metadata directories
        self.buckets_dir = config_dir.parent / "buckets"
        self.metadata_dir = config_dir.parent / "metadata"
        self.buckets_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def get_config(self, backend: str) -> Dict[str, Any]:
        """Get the configuration for a specific backend."""
        config_file = self.config_dir / f"{backend}.yaml"
        if not config_file.exists():
            return {}
        with open(config_file, "r") as f:
            return yaml.safe_load(f) or {}

    def save_config(self, backend: str, config: Dict[str, Any]) -> None:
        """Save the configuration for a specific backend."""
        config_file = self.config_dir / f"{backend}.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

    def get_all_configs(self) -> Dict[str, Any]:
        """Get all backend configurations."""
        configs = {}
        for config_file in self.config_dir.glob("*.yaml"):
            backend = config_file.stem
            configs[backend] = self.get_config(backend)
        return configs
    
    def get_bucket_config(self, bucket_name: str) -> Dict[str, Any]:
        """Get configuration for a specific bucket."""
        bucket_config_file = self.buckets_dir / f"{bucket_name}.yaml"
        if not bucket_config_file.exists():
            return {}
        with open(bucket_config_file, "r") as f:
            return yaml.safe_load(f) or {}
    
    def save_bucket_config(self, bucket_name: str, config: Dict[str, Any]) -> None:
        """Save configuration for a specific bucket."""
        bucket_config_file = self.buckets_dir / f"{bucket_name}.yaml"
        config['updated_at'] = time.time()
        with open(bucket_config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
    
    def list_buckets(self) -> List[str]:
        """List all configured buckets."""
        return [f.stem for f in self.buckets_dir.glob("*.yaml")]
    
    def delete_bucket_config(self, bucket_name: str) -> bool:
        """Delete configuration for a specific bucket."""
        bucket_config_file = self.buckets_dir / f"{bucket_name}.yaml"
        if bucket_config_file.exists():
            bucket_config_file.unlink()
            return True
        return False
    
    def get_metadata(self, key: str) -> Any:
        """Get metadata value by key."""
        metadata_file = self.metadata_dir / "metadata.json"
        if not metadata_file.exists():
            return None
        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
                return metadata.get(key)
        except (json.JSONDecodeError, FileNotFoundError):
            return None
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value by key."""
        metadata_file = self.metadata_dir / "metadata.json"
        metadata = {}
        if metadata_file.exists():
            try:
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                metadata = {}
        
        metadata[key] = value
        metadata['updated_at'] = time.time()
        
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)


def get_config_manager(config_dir: Optional[Path] = None) -> ConfigManager:
    """Return a default ConfigManager instance.

    Several legacy subsystems expect a `get_config_manager()` factory.
    """
    return ConfigManager(config_dir=config_dir or (Path.home() / ".ipfs_kit" / "config"))