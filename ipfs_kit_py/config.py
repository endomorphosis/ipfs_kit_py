
import yaml
import json
from pathlib import Path

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'
CONFIG_PATH = IPFS_KIT_PATH / 'config.yaml'

def get_config():
    """Reads the main configuration file."""
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def save_config(config_data):
    """Saves the main configuration file."""
    IPFS_KIT_PATH.mkdir(exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False)

def get_config_as_json():
    """Returns the configuration as a JSON string for the dashboard."""
    return json.dumps(get_config(), indent=2)

def save_config_from_json(json_string):
    """Saves the configuration from a JSON string from the dashboard."""
    save_config(json.loads(json_string))
