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

logger = logging.getLogger(__name__)


class SecureConfigManager:
    """Secure configuration manager that handles credentials safely."""
    
    def __init__(self, config_dir: str = "/tmp/ipfs_kit_config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # Secure config files (not committed to git)
        self.credentials_file = self.config_dir / "credentials.json"
        self.backend_configs_file = self.config_dir / "backend_configs.json"
        
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
                json.dump(credentials, f, indent=2)
            
            # Set secure permissions
            os.chmod(self.credentials_file, 0o600)
            
            logger.info(f"✓ Set {service} {credential_type} in secure config")
            
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
    
    def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get backend configuration with credentials safely injected."""
        
        # Start with default config
        config = self.default_backend_configs.get(backend_name, {}).copy()
        
        # Load any custom config from file
        try:
            if self.backend_configs_file.exists():
                with open(self.backend_configs_file, 'r') as f:
                    custom_configs = json.load(f)
                    if backend_name in custom_configs:
                        config.update(custom_configs[backend_name])
        except Exception as e:
            logger.error(f"Error loading backend configs: {e}")
        
        # Inject credentials securely
        if backend_name == "huggingface":
            token = self.get_credential("huggingface", "token")
            if token:
                config["token"] = token
        
        elif backend_name == "s3":
            access_key = self.get_credential("s3", "access_key")
            secret_key = self.get_credential("s3", "secret_key")
            if access_key and secret_key:
                config["access_key"] = access_key
                config["secret_key"] = secret_key
        
        elif backend_name == "storacha":
            token = self.get_credential("storacha", "token")
            if token:
                config["token"] = token
        
        return config
    
    def get_all_backend_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get all backend configurations with credentials safely injected."""
        
        configs = {}
        for backend_name in self.default_backend_configs.keys():
            configs[backend_name] = self.get_backend_config(backend_name)
        
        return configs
    
    def save_backend_config(self, backend_name: str, config: Dict[str, Any]):
        """Save backend configuration (without credentials)."""
        
        # Remove credentials from config before saving
        safe_config = config.copy()
        for cred_key in ["token", "access_key", "secret_key", "password"]:
            if cred_key in safe_config:
                del safe_config[cred_key]
        
        # Load existing configs
        configs = {}
        if self.backend_configs_file.exists():
            try:
                with open(self.backend_configs_file, 'r') as f:
                    configs = json.load(f)
            except Exception as e:
                logger.error(f"Error loading backend configs: {e}")
        
        # Update and save
        configs[backend_name] = safe_config
        
        try:
            with open(self.backend_configs_file, 'w') as f:
                json.dump(configs, f, indent=2)
            
            logger.info(f"✓ Saved backend config for {backend_name}")
            
        except Exception as e:
            logger.error(f"Error saving backend config: {e}")
    
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
