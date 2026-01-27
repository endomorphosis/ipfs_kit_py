#!/usr/bin/env python3
"""
Synapse SDK configuration module for ipfs_kit_py.

This module handles configuration management for the Synapse SDK integration,
including network settings, wallet management, payment configuration, and
storage preferences.

Usage:
    from config_synapse_sdk import config_synapse_sdk
    
    config = config_synapse_sdk(metadata={
        "network": "calibration",
        "private_key": "0x...",
        "auto_approve": True
    })
    
    config.setup_configuration()
    settings = config.get_configuration()
"""

import os
import sys
import json
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CONFIG = {
    "network": "calibration",
    "rpc_urls": {
        "mainnet": {
            "http": "https://api.node.glif.io/rpc/v1",
            "websocket": "wss://wss.node.glif.io/apigw/lotus/rpc/v1"
        },
        "calibration": {
            "http": "https://api.calibration.node.glif.io/rpc/v1",
            "websocket": "wss://wss.calibration.node.glif.io/apigw/lotus/rpc/v1"
        }
    },
    "payment": {
        "auto_approve": True,
        "default_allowance": "1000",
        "rate_allowance": "10",
        "token": "USDFC"
    },
    "storage": {
        "with_cdn": False,
        "default_replication": 1,
        "max_file_size": 209715200,  # 200 MiB
        "min_file_size": 16
    },
    "providers": {
        "preferred": [],
        "excluded": [],
        "auto_select": True
    },
    "timeouts": {
        "upload": 600,
        "download": 300,
        "payment": 120
    }
}

# Network-specific contract addresses (from Synapse SDK)
NETWORK_CONTRACTS = {
    "mainnet": {
        "chain_id": 314,
        "usdfc_token": "0x80B98d3aa09ffff255c3ba4A241111Ff1262F045"
    },
    "calibration": {
        "chain_id": 314159,
        "usdfc_token": "0xb3042734b608a1B16e9e86B374A3f3e389B4cDf0"
    }
}


class SynapseConfigurationError(Exception):
    """Error in Synapse SDK configuration."""
    pass


class config_synapse_sdk:
    """Class for managing Synapse SDK configuration."""
    
    def __init__(self, resources: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize Synapse SDK configuration manager.
        
        Args:
            resources: Dictionary of shared resources
            metadata: Configuration metadata
        """
        self.resources = resources or {}
        self.metadata = metadata or {}
        
        # Setup paths
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.config_dir = os.path.join(os.path.dirname(self.this_dir), "config")
        self.config_file = os.path.join(self.config_dir, "synapse_config.yaml")
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Initialize configuration
        self.config = self._load_default_config()
        self._apply_metadata_overrides()
        self._apply_environment_overrides()
        
        logger.info("Synapse SDK configuration manager initialized")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration."""
        return DEFAULT_CONFIG.copy()
    
    def _apply_metadata_overrides(self):
        """Apply configuration overrides from metadata."""
        if not self.metadata:
            return
        
        # Network configuration
        if "network" in self.metadata:
            network = self.metadata["network"]
            if network in ["mainnet", "calibration"]:
                self.config["network"] = network
            else:
                logger.warning(f"Invalid network '{network}', using default")
        
        # RPC URL overrides
        if "rpc_url" in self.metadata:
            self.config["rpc_url"] = self.metadata["rpc_url"]
        
        # Authorization header
        if "authorization" in self.metadata:
            self.config["authorization"] = self.metadata["authorization"]
        
        # Pandora service address override
        if "pandora_address" in self.metadata:
            self.config["pandora_address"] = self.metadata["pandora_address"]
        
        # Payment configuration
        payment_keys = ["auto_approve", "default_allowance", "rate_allowance", "token"]
        for key in payment_keys:
            if key in self.metadata:
                self.config["payment"][key] = self.metadata[key]
        
        # Storage configuration
        storage_keys = ["with_cdn", "default_replication", "max_file_size", "min_file_size"]
        for key in storage_keys:
            if key in self.metadata:
                self.config["storage"][key] = self.metadata[key]
        
        # Provider preferences
        if "preferred_providers" in self.metadata:
            self.config["providers"]["preferred"] = self.metadata["preferred_providers"]
        
        if "excluded_providers" in self.metadata:
            self.config["providers"]["excluded"] = self.metadata["excluded_providers"]
        
        # Timeout configuration
        timeout_keys = ["upload", "download", "payment"]
        for key in timeout_keys:
            timeout_key = f"{key}_timeout"
            if timeout_key in self.metadata:
                self.config["timeouts"][key] = self.metadata[timeout_key]
    
    def _apply_environment_overrides(self):
        """Apply configuration overrides from environment variables."""
        env_mappings = {
            "SYNAPSE_NETWORK": ("network",),
            "SYNAPSE_PRIVATE_KEY": ("private_key",),
            "SYNAPSE_RPC_URL": ("rpc_url",),
            "GLIF_TOKEN": ("authorization",),
            "SYNAPSE_PANDORA_ADDRESS": ("pandora_address",),
            "SYNAPSE_AUTO_APPROVE": ("payment", "auto_approve"),
            "SYNAPSE_DEFAULT_ALLOWANCE": ("payment", "default_allowance"),
            "SYNAPSE_RATE_ALLOWANCE": ("payment", "rate_allowance"),
            "SYNAPSE_WITH_CDN": ("storage", "with_cdn"),
            "SYNAPSE_MAX_FILE_SIZE": ("storage", "max_file_size"),
            "SYNAPSE_UPLOAD_TIMEOUT": ("timeouts", "upload"),
            "SYNAPSE_DOWNLOAD_TIMEOUT": ("timeouts", "download"),
            "SYNAPSE_PAYMENT_TIMEOUT": ("timeouts", "payment")
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Convert string values to appropriate types
                if env_var.endswith("_TIMEOUT") or env_var.endswith("_SIZE") or env_var.endswith("_ALLOWANCE"):
                    try:
                        value = int(value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {env_var}: {value}")
                        continue
                elif env_var.endswith("_APPROVE") or env_var.endswith("_CDN"):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                
                # Set nested configuration value
                current_dict = self.config
                for key in config_path[:-1]:
                    if key not in current_dict:
                        current_dict[key] = {}
                    current_dict = current_dict[key]
                current_dict[config_path[-1]] = value
    
    def get_configuration(self) -> Dict[str, Any]:
        """
        Get the complete configuration dictionary.
        
        Returns:
            Complete configuration dictionary
        """
        return self.config.copy()
    
    def get_network_config(self) -> Dict[str, Any]:
        """
        Get network-specific configuration.
        
        Returns:
            Network configuration including RPC URLs and contract addresses
        """
        network = self.config["network"]
        
        config = {
            "network": network,
            "chain_id": NETWORK_CONTRACTS[network]["chain_id"],
            "usdfc_token": NETWORK_CONTRACTS[network]["usdfc_token"]
        }
        
        # Add RPC URL (custom or default)
        if "rpc_url" in self.config:
            config["rpc_url"] = self.config["rpc_url"]
        else:
            config["rpc_url"] = self.config["rpc_urls"][network]["http"]
            config["rpc_urls"] = self.config["rpc_urls"][network]
        
        # Add authorization if present
        if "authorization" in self.config:
            config["authorization"] = self.config["authorization"]
        
        # Add Pandora address if present
        if "pandora_address" in self.config:
            config["pandora_address"] = self.config["pandora_address"]
        
        return config
    
    def get_payment_config(self) -> Dict[str, Any]:
        """
        Get payment configuration.
        
        Returns:
            Payment configuration dictionary
        """
        return self.config["payment"].copy()
    
    def get_storage_config(self) -> Dict[str, Any]:
        """
        Get storage configuration.
        
        Returns:
            Storage configuration dictionary
        """
        return self.config["storage"].copy()
    
    def get_provider_config(self) -> Dict[str, Any]:
        """
        Get provider configuration.
        
        Returns:
            Provider configuration dictionary
        """
        return self.config["providers"].copy()
    
    def get_wallet_config(self) -> Dict[str, Any]:
        """
        Get wallet configuration including private key.
        
        Returns:
            Wallet configuration dictionary
        """
        config = {}
        
        # Get private key from multiple sources
        private_key = (
            self.config.get("private_key") or
            self.metadata.get("private_key") or
            os.environ.get("SYNAPSE_PRIVATE_KEY") or
            os.environ.get("PRIVATE_KEY")
        )
        
        if private_key:
            config["private_key"] = private_key
        
        return config
    
    def validate_configuration(self) -> bool:
        """
        Validate the current configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required network
            network = self.config["network"]
            if network not in ["mainnet", "calibration"]:
                logger.error(f"Invalid network: {network}")
                return False
            
            # Check wallet configuration
            wallet_config = self.get_wallet_config()
            if not wallet_config.get("private_key"):
                logger.warning("No private key configured - some operations will not be available")
            
            # Validate file size limits
            storage_config = self.get_storage_config()
            if storage_config["min_file_size"] >= storage_config["max_file_size"]:
                logger.error("Invalid file size limits: min_file_size >= max_file_size")
                return False
            
            # Validate timeout values
            timeouts = self.config["timeouts"]
            for timeout_name, timeout_value in timeouts.items():
                if not isinstance(timeout_value, int) or timeout_value <= 0:
                    logger.error(f"Invalid timeout value for {timeout_name}: {timeout_value}")
                    return False
            
            # Validate allowance values
            payment_config = self.get_payment_config()
            try:
                float(payment_config["default_allowance"])
                float(payment_config["rate_allowance"])
            except ValueError:
                logger.error("Invalid allowance values in payment configuration")
                return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def save_configuration(self, file_path: Optional[str] = None) -> bool:
        """
        Save configuration to YAML file.
        
        Args:
            file_path: Optional custom file path
            
        Returns:
            True if save successful, False otherwise
        """
        file_path = file_path or self.config_file
        
        try:
            # Create a sanitized version of config for saving
            # (exclude sensitive data like private keys)
            save_config = self.config.copy()
            
            # Remove sensitive information
            if "private_key" in save_config:
                del save_config["private_key"]
            
            with open(file_path, 'w') as f:
                yaml.dump(save_config, f, default_flow_style=False, indent=2)
            
            logger.info(f"Configuration saved to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def load_configuration(self, file_path: Optional[str] = None) -> bool:
        """
        Load configuration from YAML file.
        
        Args:
            file_path: Optional custom file path
            
        Returns:
            True if load successful, False otherwise
        """
        file_path = file_path or self.config_file
        
        if not os.path.exists(file_path):
            logger.info(f"Configuration file {file_path} does not exist, using defaults")
            return True
        
        try:
            with open(file_path, 'r') as f:
                loaded_config = yaml.safe_load(f)
            
            if loaded_config:
                # Merge loaded config with defaults
                self._merge_config(self.config, loaded_config)
                logger.info(f"Configuration loaded from {file_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load configuration from {file_path}: {e}")
            return False
    
    def _merge_config(self, base_config: Dict[str, Any], new_config: Dict[str, Any]):
        """Recursively merge configuration dictionaries."""
        for key, value in new_config.items():
            if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
                self._merge_config(base_config[key], value)
            else:
                base_config[key] = value
    
    def setup_configuration(self) -> bool:
        """
        Set up complete configuration including validation and saving.
        
        Returns:
            True if setup successful, False otherwise
        """
        logger.info("Setting up Synapse SDK configuration...")
        
        # Load existing configuration if present
        self.load_configuration()
        
        # Apply overrides again in case they were loaded from file
        self._apply_metadata_overrides()
        self._apply_environment_overrides()
        
        # Validate configuration
        if not self.validate_configuration():
            logger.error("Configuration validation failed")
            return False
        
        # Save configuration
        if not self.save_configuration():
            logger.warning("Failed to save configuration, continuing anyway")
        
        logger.info("Synapse SDK configuration setup completed")
        return True
    
    def get_js_bridge_config(self) -> Dict[str, Any]:
        """
        Get configuration formatted for JavaScript bridge communication.
        
        Returns:
            Configuration dictionary for JavaScript bridge
        """
        network_config = self.get_network_config()
        wallet_config = self.get_wallet_config()
        payment_config = self.get_payment_config()
        storage_config = self.get_storage_config()
        
        js_config = {
            "network": network_config["network"],
            "rpcUrl": network_config["rpc_url"],
            "chainId": network_config["chain_id"]
        }
        
        # Add private key if available
        if "private_key" in wallet_config:
            js_config["privateKey"] = wallet_config["private_key"]
        
        # Add authorization if available
        if "authorization" in network_config:
            js_config["authorization"] = network_config["authorization"]
        
        # Add Pandora address if available
        if "pandora_address" in network_config:
            js_config["pandoraAddress"] = network_config["pandora_address"]
        
        # Add payment configuration
        js_config["payment"] = {
            "autoApprove": payment_config["auto_approve"],
            "defaultAllowance": payment_config["default_allowance"],
            "rateAllowance": payment_config["rate_allowance"],
            "token": payment_config["token"]
        }
        
        # Add storage configuration
        js_config["storage"] = {
            "withCDN": storage_config["with_cdn"],
            "defaultReplication": storage_config["default_replication"],
            "maxFileSize": storage_config["max_file_size"],
            "minFileSize": storage_config["min_file_size"]
        }
        
        return js_config
    
    def print_configuration_summary(self):
        """Print a summary of the current configuration."""
        print("\n=== Synapse SDK Configuration Summary ===")
        
        network_config = self.get_network_config()
        print(f"Network: {network_config['network']} (Chain ID: {network_config['chain_id']})")
        print(f"RPC URL: {network_config['rpc_url']}")
        
        wallet_config = self.get_wallet_config()
        if "private_key" in wallet_config:
            key_preview = wallet_config["private_key"][:10] + "..." if len(wallet_config["private_key"]) > 10 else "..."
            print(f"Private Key: {key_preview}")
        else:
            print("Private Key: Not configured")
        
        payment_config = self.get_payment_config()
        print(f"\nPayment Configuration:")
        print(f"  Auto-approve: {payment_config['auto_approve']}")
        print(f"  Default allowance: {payment_config['default_allowance']} {payment_config['token']}")
        print(f"  Rate allowance: {payment_config['rate_allowance']} {payment_config['token']}")
        
        storage_config = self.get_storage_config()
        print(f"\nStorage Configuration:")
        print(f"  CDN enabled: {storage_config['with_cdn']}")
        print(f"  Default replication: {storage_config['default_replication']}")
        print(f"  File size limits: {storage_config['min_file_size']} - {storage_config['max_file_size']} bytes")
        
        provider_config = self.get_provider_config()
        print(f"\nProvider Configuration:")
        print(f"  Auto-select: {provider_config['auto_select']}")
        print(f"  Preferred providers: {len(provider_config['preferred'])}")
        print(f"  Excluded providers: {len(provider_config['excluded'])}")
        
        print("\n" + "=" * 41)


def main():
    """Main function for testing configuration module."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Synapse SDK Configuration Manager")
    parser.add_argument("--network", choices=["mainnet", "calibration"], 
                       help="Filecoin network to use")
    parser.add_argument("--save", action="store_true", 
                       help="Save configuration to file")
    parser.add_argument("--load", action="store_true", 
                       help="Load configuration from file")
    parser.add_argument("--validate", action="store_true", 
                       help="Validate configuration")
    parser.add_argument("--summary", action="store_true", 
                       help="Show configuration summary")
    args = parser.parse_args()
    
    # Create configuration manager
    metadata = {}
    if args.network:
        metadata["network"] = args.network
    
    config_mgr = config_synapse_sdk(metadata=metadata)
    
    if args.load:
        config_mgr.load_configuration()
    
    if args.validate:
        is_valid = config_mgr.validate_configuration()
        print(f"Configuration valid: {is_valid}")
    
    if args.save:
        config_mgr.save_configuration()
    
    if args.summary:
        config_mgr.print_configuration_summary()
    
    if not any([args.save, args.load, args.validate, args.summary]):
        config_mgr.print_configuration_summary()


if __name__ == "__main__":
    main()
