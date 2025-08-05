import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigManager:
    """Manages reading and writing of YAML configuration files."""

    def __init__(self, config_dir: Path = Path.home() / ".ipfs_kit" / "config"):
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)

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