"""
Secure configuration manager for IPFS Kit.

This module handles secure credential management using environment variables
and configuration files that are excluded from version control.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import toml

logger = logging.getLogger(__name__)


class SecureConfigManager:
    """Secure configuration manager that handles credentials safely."""
    
    def __init__(self, config_dir: str = "/tmp/ipfs_kit_config", project_root: Optional[str] = None):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # Determine project root
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Heuristic to find project root by looking for pyproject.toml
            self.project_root = Path.cwd()
            while self.project_root != self.project_root.parent and not (self.project_root / 'pyproject.toml').exists():
                self.project_root = self.project_root.parent
        
        if not (self.project_root / 'pyproject.toml').exists():
            logger.warning(f"Could not find pyproject.toml in parent directories of {Path.cwd()}. Package config operations will fail.")

        # Secure config files (not committed to git)
        self.credentials_file = self.config_dir / "credentials.json"
        self.backend_configs_file = self.config_dir / "backend_configs.json"
        self.pyproject_file = self.project_root / "pyproject.toml"
        
        # Default configurations (without credentials)
        self.default_backend_configs = {
            "ipfs": {
                "endpoint": "http://127.0.0.1:5001",
                "timeout": 30
            },
            "ipfs_cluster": {
                "endpoint": "http://127.0.0.1:9094",
                "timeout": 30
            },
            "lotus": {
                "endpoint": "http://127.0.0.1:1234/rpc/v0",
                "timeout": 30
            },
            "storacha": {
                "endpoint": "https://up.web3.storage",
                "timeout": 30
            },
            "synapse": {
                "endpoint": "http://127.0.0.1:8008",
                "timeout": 30
            },
            "s3": {
                "endpoint": "http://object.lga1.coreweave.com",
                "timeout": 30
            },
            "huggingface": {
                "endpoint": "https://huggingface.co",
                "timeout": 30
            },
            "parquet": {
                "data_dir": "/tmp/parquet_data"
            }
        }
        
        logger.info(f"✓ Secure config manager initialized with config dir: {config_dir}")
        logger.info(f"✓ Project root detected as: {self.project_root}")
    
    def get_credential(self, service: str, credential_type: str) -> Optional[str]:
        """Get a credential safely from environment variables or config file."""
        
        # First try environment variables (preferred)
        env_var = f"IPFS_KIT_{service.upper()}_{credential_type.upper()}"
        credential = os.getenv(env_var)
        
        if credential:
            logger.debug(f"✓ Retrieved {service} {credential_type} from environment variable")
            return credential
        
        # Fallback to config file
        try:
            if self.credentials_file.exists():
                with open(self.credentials_file, 'r') as f:
                    credentials = json.load(f)
                    
                service_creds = credentials.get(service, {})
                credential = service_creds.get(credential_type)
                
                if credential:
                    logger.debug(f"✓ Retrieved {service} {credential_type} from config file")
                    return credential
                    
        except Exception as e:
            logger.error(f"Error reading credentials file: {e}")
        
        logger.warning(f"⚠️  No credential found for {service} {credential_type}")
        return None
    
    def set_credential(self, service: str, credential_type: str, value: str):
        """Set a credential in the secure config file."""
        
        credentials = {}
        if self.credentials_file.exists():
            try:
                with open(self.credentials_file, 'r') as f:
                    credentials = json.load(f)
            except Exception as e:
                logger.error(f"Error reading existing credentials: {e}")
        
        if service not in credentials:
            credentials[service] = {}
        
        credentials[service][credential_type] = value
        
        try:
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=4)
            
            logger.info(f"✓ Set {service} {credential_type} in secure config file")
            
        except Exception as e:
            logger.error(f"Error setting credential: {e}")

    def get_package_config(self) -> Dict[str, Any]:
        """Get package configuration from pyproject.toml."""
        if not self.pyproject_file.exists():
            logger.error(f"pyproject.toml not found at {self.pyproject_file}")
            return {"error": "pyproject.toml not found"}
        
        try:
            with open(self.pyproject_file, 'r') as f:
                return toml.load(f)
        except Exception as e:
            logger.error(f"Error reading pyproject.toml: {e}")
            return {"error": str(e)}

    def save_package_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Save package configuration to pyproject.toml."""
        if not self.pyproject_file.exists():
            logger.error(f"pyproject.toml not found at {self.pyproject_file}")
            return {"error": "pyproject.toml not found"}
            
        try:
            with open(self.pyproject_file, 'w') as f:
                toml.dump(config, f)
            logger.info(f"✓ Saved package configuration to {self.pyproject_file}")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Error writing to pyproject.toml: {e}")
            return {"error": str(e)}

    def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get a specific backend configuration, merged with defaults."""
        # Start with default config
        config = self.default_backend_configs.get(backend_name, {}).copy()
        
        # Load saved configs from file
        saved_configs = {}
        if self.backend_configs_file.exists():
            try:
                with open(self.backend_configs_file, 'r') as f:
                    saved_configs = json.load(f)
            except Exception as e:
                logger.error(f"Error reading backend configs file: {e}")
        
        # Merge saved config with defaults
        saved_config = saved_configs.get(backend_name, {})
        config.update(saved_config)
        
        return config

    def get_all_backend_configs(self) -> Dict[str, Any]:
        """Get all backend configurations, merging defaults with saved configs."""
        
        configs = {}
        for backend_name in self.default_backend_configs.keys():
            configs[backend_name] = self.get_backend_config(backend_name)
        
        return configs
    
    def save_backend_config(self, backend_name: str, config: Dict[str, Any]):
        """Save a specific backend configuration."""
        
        saved_configs = {}
        if self.backend_configs_file.exists():
            try:
                with open(self.backend_configs_file, 'r') as f:
                    saved_configs = json.load(f)
            except Exception as e:
                logger.error(f"Error reading backend configs file for saving: {e}")

        saved_configs[backend_name] = config
        
        try:
            with open(self.backend_configs_file, 'w') as f:
                json.dump(saved_configs, f, indent=4)
            logger.info(f"✓ Saved {backend_name} configuration.")
        except Exception as e:
            logger.error(f"Error saving backend config for {backend_name}: {e}")

    def get_full_config(self) -> Dict[str, Any]:
        """Get the full configuration, including package and all backends."""
        
        package_config = self.get_package_config()
        backend_configs = self.get_all_backend_configs()
        
        return {
            "package_config": package_config,
            "backend_configs": backend_configs
        }

    def save_full_config(self, full_config: Dict[str, Any]):
        """Save the full configuration."""
        
        if "package_config" in full_config:
            self.save_package_config(full_config["package_config"])
            
        if "backend_configs" in full_config:
            for backend_name, config in full_config["backend_configs"].items():
                self.save_backend_config(backend_name, config)
        
        logger.info("✓ Full configuration saved.")

    def initialize_example_credentials(self):
        """Initialize example credentials file with placeholders."""
        
        example_file = self.config_dir / "credentials.example.json"
        
        example_credentials = {
            "huggingface": {
                "token": "hf_your_token_here",
                "test_repo": "your-org/your-test-repo"
            },
            "s3": {
                "access_key": "your_access_key_here",
                "secret_key": "your_secret_key_here",
                "server": "object.lga1.coreweave.com",
                "test_bucket": "your-test-bucket"
            },
            "storacha": {
                "token": "your_storacha_token_here"
            }
        }
        
        try:
            with open(example_file, 'w') as f:
                json.dump(example_credentials, f, indent=2)
            
            logger.info(f"✓ Created example credentials file at {example_file}")
            logger.info("📝 Copy credentials.example.json to credentials.json and fill in your actual credentials")
            
        except Exception as e:
            logger.error(f"Error creating example credentials file: {e}")
    
    def create_gitignore(self):
        """Create .gitignore file to exclude credential files."""
        
        gitignore_path = self.config_dir / ".gitignore"
        
        gitignore_content = """# Credential files - DO NOT COMMIT
credentials.json
*.key
*.pem
*.p12
*.pfx

# Backup files
*.backup
*.bak

# OS files
.DS_Store
Thumbs.db
"""
        
        try:
            with open(gitignore_path, 'w') as f:
                f.write(gitignore_content)
            
            logger.info(f"✓ Created .gitignore at {gitignore_path}")
            
        except Exception as e:
            logger.error(f"Error creating .gitignore: {e}")
