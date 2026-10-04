
'''
Real API implementations for MCP storage backends.
This module provides the integration between simulation endpoints and real API implementations.
'''

import os
import sys
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Configuration paths
CONFIG_DIR = Path.home() / ".ipfs_kit"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
CONFIG_PATH = CONFIG_DIR / "storage_backends.json"

def load_config():
    """Load backend configuration."""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        else:
            logger.warning(f"Config file not found: {CONFIG_PATH}")
            return {}
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}

def load_credentials():
    """Load backend credentials."""
    try:
        if CREDENTIALS_PATH.exists():
            with open(CREDENTIALS_PATH, "r") as f:
                return json.load(f)
        else:
            logger.warning(f"Credentials file not found: {CREDENTIALS_PATH}")
            return {}
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return {}

# Load configuration
config = load_config()
credentials = load_credentials()

# Check which backends are enabled
ENABLED_BACKENDS = []
for backend, settings in config.get("backends", {}).items():
    if settings.get("enabled", False):
        ENABLED_BACKENDS.append(backend)
        logger.info(f"Backend enabled: {backend}")
        
        # Set simulation mode in environment for each backend
        sim_var = f"{backend.upper()}_SIMULATION_MODE"
        sim_mode = "1" if settings.get("simulation_mode", False) else "0"
        os.environ[sim_var] = sim_mode
        
        # Set cache directory
        cache_var = f"{backend.upper()}_CACHE_DIR"
        os.environ[cache_var] = settings.get("cache_dir", "")

# Set credentials as environment variables
for backend, creds in credentials.items():
    for key, value in creds.items():
        if value:  # Only set if value is not empty
            env_var = f"{backend.upper()}_{key.upper()}"
            os.environ[env_var] = value
            logger.debug(f"Set credential: {env_var}")

def get_backend_status(backend_name):
    """Get status of a backend."""
    backend = backend_name.lower()
    
    # Backend exists in config
    if backend in config.get("backends", {}):
        # Backend is enabled
        if config["backends"][backend].get("enabled", False):
            # Simulation mode check
            simulation = config["backends"][backend].get("simulation_mode", False)
            
            # Has credentials (if needed)
            has_creds = True
            if backend in credentials:
                # Check if any credential is empty
                for key, value in credentials[backend].items():
                    if not value:
                        has_creds = False
                        break
            
            return {
                "exists": True,
                "enabled": True,
                "simulation": simulation,
                "has_credentials": has_creds,
                "status": "simulation" if simulation else ("active" if has_creds else "missing_credentials")
            }
        else:
            return {
                "exists": True,
                "enabled": False,
                "status": "disabled"
            }
    else:
        return {
            "exists": False,
            "status": "not_found"
        }

def get_all_backends_status():
    """Get status of all backends."""
    backends = {}
    for backend in ["huggingface", "storacha", "filecoin", "lassie", "s3"]:
        backends[backend] = get_backend_status(backend)
    return backends
