#!/usr/bin/env python3
"""
Enhanced Daemon Configuration Manager

This module ensures that all daemons (IPFS, Lotus, Lassie) have proper configuration
before they are started. It provides default configurations and validation.
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("daemon_config_manager")

class DaemonConfigManager:
    """Manages configuration for all daemons used in ipfs_kit_py."""
    
    def __init__(self, ipfs_kit_instance=None):
        """Initialize the daemon configuration manager.
        
        Args:
            ipfs_kit_instance: Optional ipfs_kit instance for accessing installers
        """
        self.ipfs_kit = ipfs_kit_instance
        self.config_status = {}
        
        # Default paths
        self.ipfs_path = os.path.join(os.path.expanduser("~"), ".ipfs")
        self.lotus_path = os.path.join(os.path.expanduser("~"), ".lotus")
        self.lassie_path = os.path.join(os.path.expanduser("~"), ".lassie")
        self.ipfs_cluster_path = os.path.join(os.path.expanduser("~"), ".ipfs-cluster")
        self.ipfs_cluster_follow_path = os.path.join(os.path.expanduser("~"), ".ipfs-cluster-follow")
        self.s3_config_path = os.path.join(os.path.expanduser("~"), ".s3cfg")
        self.hf_config_path = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
        self.storacha_config_path = os.path.join(os.path.expanduser("~"), ".storacha")
        
    def check_and_configure_all_daemons(self) -> Dict[str, Any]:
        """Check and configure all daemons if needed.
        
        Returns:
            Dictionary with configuration status for all daemons
        """
        logger.info("🔧 Checking and configuring all daemons...")
        
        result_dict = {
            "ipfs": self.check_and_configure_ipfs(),
            "lotus": self.check_and_configure_lotus(),
            "lassie": self.check_and_configure_lassie(),
            "ipfs_cluster_service": self.check_and_configure_ipfs_cluster_service(),
            "ipfs_cluster_follow": self.check_and_configure_ipfs_cluster_follow(),
            "ipfs_cluster_ctl": self.check_and_configure_ipfs_cluster_ctl(),
            "s3": self.check_and_configure_s3(),
            "huggingface": self.check_and_configure_huggingface(),
            "storacha": self.check_and_configure_storacha()
        }
        
        overall_success = all(
            result.get("success", False) or result.get("already_configured", False)
            for result in result_dict.values()
        )
        
        results: Dict[str, Any] = {
            "overall_success": overall_success,
            "summary": self._generate_summary(result_dict)
        }
        results.update(result_dict)
        
        return results
        
    def check_and_configure_ipfs(self) -> Dict[str, Any]:
        """Check and configure IPFS daemon if needed.
        
        Returns:
            Dictionary with IPFS configuration status
        """
        logger.info("🔧 Checking IPFS configuration...")
        
        # Check if IPFS is already configured
        config_file = os.path.join(self.ipfs_path, "config")
        if os.path.exists(config_file):
            logger.info("✅ IPFS already configured")
            return {"already_configured": True, "config_path": config_file}
        
        # Need to configure IPFS
        logger.info("⚙️ Configuring IPFS daemon...")
        
        try:
            # Import installer if not already available
            if not hasattr(self, '_ipfs_installer'):
                from ipfs_kit_py.install_ipfs import install_ipfs
                self._ipfs_installer = install_ipfs()
            
            # Run configuration
            config_result = self._ipfs_installer.config_ipfs(
                ipfs_path=self.ipfs_path,
                cluster_name="ipfs-kit-cluster"
            )
            
            if config_result.get("error"):
                logger.error(f"❌ IPFS configuration failed: {config_result['error']}")
                return {"success": False, "error": config_result["error"]}
            
            logger.info("✅ IPFS configured successfully")
            return {
                "success": True,
                "config_path": self.ipfs_path,
                "identity": config_result.get("identity"),
                "cluster_name": config_result.get("cluster_name")
            }
            
        except Exception as e:
            logger.error(f"❌ Error configuring IPFS: {e}")
            return {"success": False, "error": str(e)}
    
    def check_and_configure_lotus(self) -> Dict[str, Any]:
        """Check and configure Lotus daemon if needed.
        
        Returns:
            Dictionary with Lotus configuration status
        """
        logger.info("🔧 Checking Lotus configuration...")
        
        # Check if Lotus is already configured
        config_file = os.path.join(self.lotus_path, "config.toml")
        if os.path.exists(config_file):
            logger.info("✅ Lotus already configured")
            return {"already_configured": True, "config_path": config_file}
        
        # Need to configure Lotus
        logger.info("⚙️ Configuring Lotus daemon...")
        
        try:
            # Import installer if not already available
            if not hasattr(self, '_lotus_installer'):
                from ipfs_kit_py.install_lotus import install_lotus
                self._lotus_installer = install_lotus()
            
            # Run configuration
            config_result = self._lotus_installer.config_lotus(
                api_port=1234,
                p2p_port=1235
            )
            
            if not config_result.get("success", False):
                error_msg = config_result.get("error", "Unknown error")
                logger.error(f"❌ Lotus configuration failed: {error_msg}")
                return {"success": False, "error": error_msg}
            
            logger.info("✅ Lotus configured successfully")
            return {
                "success": True,
                "config_path": self.lotus_path,
                "identity": config_result.get("identity"),
                "storage_configured": config_result.get("storage_configured", False)
            }
            
        except Exception as e:
            logger.error(f"❌ Error configuring Lotus: {e}")
            return {"success": False, "error": str(e)}
    
    def check_and_configure_lassie(self) -> Dict[str, Any]:
        """Check and configure Lassie daemon if needed.
        
        Returns:
            Dictionary with Lassie configuration status
        """
        logger.info("🔧 Checking Lassie configuration...")
        
        # Lassie typically doesn't need explicit configuration like IPFS/Lotus
        # but we can create a basic config directory and settings
        
        try:
            # Create lassie config directory
            os.makedirs(self.lassie_path, exist_ok=True)
            
            # Create basic config file if it doesn't exist
            config_file = os.path.join(self.lassie_path, "config.json")
            if not os.path.exists(config_file):
                logger.info("⚙️ Creating basic Lassie configuration...")
                
                lassie_config = {
                    "retrieval_timeout": "30m",
                    "bitswap_concurrent": 6,
                    "bitswap_requests_per_peer": 10,
                    "http_concurrent": 6,
                    "http_requests_per_peer": 10,
                    "providers": ["127.0.0.1:1234"]  # Default to local Lotus
                }
                
                with open(config_file, 'w') as f:
                    json.dump(lassie_config, f, indent=2)
                
                logger.info("✅ Lassie configured successfully")
                return {
                    "success": True,
                    "config_path": config_file,
                    "created_new_config": True
                }
            else:
                logger.info("✅ Lassie already configured")
                return {"already_configured": True, "config_path": config_file}
                
        except Exception as e:
            logger.error(f"❌ Error configuring Lassie: {e}")
            return {"success": False, "error": str(e)}
    
    def check_and_configure_ipfs_cluster_service(self) -> Dict[str, Any]:
        """Check and configure IPFS cluster service if needed.
        
        Returns:
            Dictionary with IPFS cluster service configuration status
        """
        logger.info("🔧 Checking IPFS cluster service configuration...")
        
        # Check if IPFS cluster service is already configured
        config_file = os.path.join(self.ipfs_cluster_path, "service.json")
        if os.path.exists(config_file):
            logger.info("✅ IPFS cluster service already configured")
            return {"already_configured": True, "config_path": config_file}
        
        # Need to configure IPFS cluster service
        logger.info("⚙️ Configuring IPFS cluster service...")
        
        try:
            # Import installer if not already available
            if not hasattr(self, '_ipfs_installer'):
                from ipfs_kit_py.install_ipfs import install_ipfs
                self._ipfs_installer = install_ipfs()
            
            # Run configuration
            config_result = self._ipfs_installer.config_ipfs_cluster_service(
                cluster_name="ipfs-kit-cluster",
                cluster_path=self.ipfs_cluster_path
            )
            
            if config_result.get("error"):
                logger.error(f"❌ IPFS cluster service configuration failed: {config_result['error']}")
                return {"success": False, "error": config_result["error"]}
            
            logger.info("✅ IPFS cluster service configured successfully")
            return {
                "success": True,
                "config_path": self.ipfs_cluster_path,
                "cluster_name": config_result.get("cluster_name")
            }
            
        except Exception as e:
            logger.error(f"❌ Error configuring IPFS cluster service: {e}")
            return {"success": False, "error": str(e)}

    def check_and_configure_ipfs_cluster_follow(self) -> Dict[str, Any]:
        """Check and configure IPFS cluster follow if needed.
        
        Returns:
            Dictionary with IPFS cluster follow configuration status
        """
        logger.info("🔧 Checking IPFS cluster follow configuration...")
        
        # Check if IPFS cluster follow is already configured
        cluster_name = "ipfs-kit-cluster"
        config_path = os.path.join(self.ipfs_cluster_follow_path, cluster_name)
        config_file = os.path.join(config_path, "service.json")
        
        if os.path.exists(config_file):
            logger.info("✅ IPFS cluster follow already configured")
            return {"already_configured": True, "config_path": config_file}
        
        # Need to configure IPFS cluster follow
        logger.info("⚙️ Configuring IPFS cluster follow...")
        
        try:
            # Import installer if not already available
            if not hasattr(self, '_ipfs_installer'):
                from ipfs_kit_py.install_ipfs import install_ipfs
                self._ipfs_installer = install_ipfs()
            
            # Run configuration
            config_result = self._ipfs_installer.config_ipfs_cluster_follow(
                cluster_name=cluster_name,
                ipfs_path=self.ipfs_path
            )
            
            if config_result.get("error"):
                logger.error(f"❌ IPFS cluster follow configuration failed: {config_result['error']}")
                return {"success": False, "error": config_result["error"]}
            
            logger.info("✅ IPFS cluster follow configured successfully")
            return {
                "success": True,
                "config_path": config_path,
                "cluster_name": cluster_name
            }
            
        except Exception as e:
            logger.error(f"❌ Error configuring IPFS cluster follow: {e}")
            return {"success": False, "error": str(e)}

    def check_and_configure_ipfs_cluster_ctl(self) -> Dict[str, Any]:
        """Check and configure IPFS cluster ctl if needed.
        
        Returns:
            Dictionary with IPFS cluster ctl configuration status
        """
        logger.info("🔧 Checking IPFS cluster ctl configuration...")
        
        # IPFS cluster ctl typically doesn't need explicit configuration
        # but we can create a basic config file for consistency
        try:
            # Create cluster ctl config directory
            ctl_config_path = os.path.join(self.ipfs_cluster_path, "ctl")
            os.makedirs(ctl_config_path, exist_ok=True)
            
            # Create basic config file if it doesn't exist
            config_file = os.path.join(ctl_config_path, "config.json")
            if not os.path.exists(config_file):
                logger.info("⚙️ Creating basic IPFS cluster ctl configuration...")
                
                # Import installer if not already available
                if not hasattr(self, '_ipfs_installer'):
                    from ipfs_kit_py.install_ipfs import install_ipfs
                    self._ipfs_installer = install_ipfs()
                
                # Run configuration
                config_result = self._ipfs_installer.config_ipfs_cluster_ctl(
                    cluster_name="ipfs-kit-cluster"
                )
                
                if config_result.get("error"):
                    logger.error(f"❌ IPFS cluster ctl configuration failed: {config_result['error']}")
                    return {"success": False, "error": config_result["error"]}
                
                logger.info("✅ IPFS cluster ctl configured successfully")
                return {
                    "success": True,
                    "config_path": config_file,
                    "created_new_config": True
                }
            else:
                logger.info("✅ IPFS cluster ctl already configured")
                return {"already_configured": True, "config_path": config_file}
                
        except Exception as e:
            logger.error(f"❌ Error configuring IPFS cluster ctl: {e}")
            return {"success": False, "error": str(e)}

    def check_and_configure_s3(self) -> Dict[str, Any]:
        """Check and configure S3 if needed.
        
        Returns:
            Dictionary with S3 configuration status
        """
        logger.info("🔧 Checking S3 configuration...")
        
        # Check if S3 is already configured
        if os.path.exists(self.s3_config_path):
            logger.info("✅ S3 already configured")
            return {"already_configured": True, "config_path": self.s3_config_path}
        
        # Need to configure S3
        logger.info("⚙️ Creating default S3 configuration...")
        
        try:
            # Create default S3 config
            s3_config = self.get_default_s3_config()
            
            # Create config directory if needed
            config_dir = os.path.dirname(self.s3_config_path)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)
            
            # Write S3 config file
            with open(self.s3_config_path, 'w') as f:
                for key, value in s3_config.items():
                    f.write(f"{key} = {value}\n")
            
            logger.info("✅ S3 configured successfully")
            return {
                "success": True,
                "config_path": self.s3_config_path,
                "created_new_config": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error configuring S3: {e}")
            return {"success": False, "error": str(e)}

    def check_and_configure_huggingface(self) -> Dict[str, Any]:
        """Check and configure HuggingFace if needed.
        
        Returns:
            Dictionary with HuggingFace configuration status
        """
        logger.info("🔧 Checking HuggingFace configuration...")
        
        # Check if HuggingFace is already configured
        hf_token_path = os.path.join(self.hf_config_path, "token")
        hf_config_file = os.path.join(self.hf_config_path, "config.json")
        
        if os.path.exists(hf_token_path) or os.path.exists(hf_config_file):
            logger.info("✅ HuggingFace already configured")
            return {"already_configured": True, "config_path": self.hf_config_path}
        
        # Need to configure HuggingFace
        logger.info("⚙️ Creating default HuggingFace configuration...")
        
        try:
            # Create HuggingFace config directory
            os.makedirs(self.hf_config_path, exist_ok=True)
            
            # Create basic config file
            hf_config = self.get_default_huggingface_config()
            
            with open(hf_config_file, 'w') as f:
                json.dump(hf_config, f, indent=2)
            
            logger.info("✅ HuggingFace configured successfully")
            return {
                "success": True,
                "config_path": self.hf_config_path,
                "created_new_config": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error configuring HuggingFace: {e}")
            return {"success": False, "error": str(e)}

    def check_and_configure_storacha(self) -> Dict[str, Any]:
        """Check and configure Storacha if needed.
        
        Returns:
            Dictionary with Storacha configuration status
        """
        logger.info("🔧 Checking Storacha configuration...")
        
        # Check if Storacha is already configured
        config_file = os.path.join(self.storacha_config_path, "config.json")
        if os.path.exists(config_file):
            logger.info("✅ Storacha already configured")
            return {"already_configured": True, "config_path": config_file}
        
        # Need to configure Storacha
        logger.info("⚙️ Creating default Storacha configuration...")
        
        try:
            # Create Storacha config directory
            os.makedirs(self.storacha_config_path, exist_ok=True)
            
            # Create basic config file
            storacha_config = self.get_default_storacha_config()
            
            with open(config_file, 'w') as f:
                json.dump(storacha_config, f, indent=2)
            
            logger.info("✅ Storacha configured successfully")
            return {
                "success": True,
                "config_path": config_file,
                "created_new_config": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error configuring Storacha: {e}")
            return {"success": False, "error": str(e)}
    
    def validate_daemon_configs(self) -> Dict[str, Any]:
        """Validate that all daemon configurations are valid.
        
        Returns:
            Dictionary with validation results
        """
        logger.info("🔍 Validating daemon configurations...")
        
        results = {
            "ipfs": self._validate_ipfs_config(),
            "lotus": self._validate_lotus_config(),
            "lassie": self._validate_lassie_config(),
            "ipfs_cluster_service": self._validate_ipfs_cluster_service_config(),
            "ipfs_cluster_follow": self._validate_ipfs_cluster_follow_config(),
            "ipfs_cluster_ctl": self._validate_ipfs_cluster_ctl_config(),
            "s3": self._validate_s3_config(),
            "huggingface": self._validate_huggingface_config(),
            "storacha": self._validate_storacha_config()
        }
        
        overall_valid = all(
            result.get("valid", False) for result in results.values()
        )
        
        results["overall_valid"] = overall_valid
        
        return results
    
    def _validate_ipfs_config(self) -> Dict[str, Any]:
        """Validate IPFS configuration."""
        config_file = os.path.join(self.ipfs_path, "config")
        
        if not os.path.exists(config_file):
            return {"valid": False, "error": "Config file not found"}
        
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Check required fields
            required_fields = ["Identity", "Addresses", "Datastore"]
            missing_fields = [field for field in required_fields if field not in config_data]
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Missing required fields: {missing_fields}"
                }
            
            return {"valid": True, "identity": config_data["Identity"]["PeerID"]}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def _validate_lotus_config(self) -> Dict[str, Any]:
        """Validate Lotus configuration."""
        config_file = os.path.join(self.lotus_path, "config.toml")
        
        if not os.path.exists(config_file):
            return {"valid": False, "error": "Config file not found"}
        
        try:
            # Basic validation - check if file is readable
            with open(config_file, 'r') as f:
                content = f.read()
            
            # Check for basic sections
            required_sections = ["[API]", "[Libp2p]"]
            missing_sections = [
                section for section in required_sections 
                if section not in content
            ]
            
            if missing_sections:
                return {
                    "valid": False,
                    "error": f"Missing required sections: {missing_sections}"
                }
            
            return {"valid": True}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def _validate_lassie_config(self) -> Dict[str, Any]:
        """Validate Lassie configuration."""
        config_file = os.path.join(self.lassie_path, "config.json")
        
        if not os.path.exists(config_file):
            return {"valid": False, "error": "Config file not found"}
        
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Check for basic settings
            if "retrieval_timeout" not in config_data:
                return {"valid": False, "error": "Missing retrieval_timeout setting"}
            
            return {"valid": True}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def _validate_ipfs_cluster_service_config(self) -> Dict[str, Any]:
        """Validate IPFS cluster service configuration."""
        config_file = os.path.join(self.ipfs_cluster_path, "service.json")
        
        if not os.path.exists(config_file):
            return {"valid": False, "error": "Config file not found"}
        
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Check required fields
            required_fields = ["cluster", "id", "secret"]
            missing_fields = [field for field in required_fields if field not in config_data]
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Missing required fields: {missing_fields}"
                }
            
            return {"valid": True, "cluster_id": config_data.get("id")}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _validate_ipfs_cluster_follow_config(self) -> Dict[str, Any]:
        """Validate IPFS cluster follow configuration."""
        cluster_name = "ipfs-kit-cluster"
        config_path = os.path.join(self.ipfs_cluster_follow_path, cluster_name)
        config_file = os.path.join(config_path, "service.json")
        
        if not os.path.exists(config_file):
            return {"valid": False, "error": "Config file not found"}
        
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Check required fields
            required_fields = ["cluster", "id"]
            missing_fields = [field for field in required_fields if field not in config_data]
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Missing required fields: {missing_fields}"
                }
            
            return {"valid": True, "cluster_name": config_data.get("cluster")}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _validate_ipfs_cluster_ctl_config(self) -> Dict[str, Any]:
        """Validate IPFS cluster ctl configuration."""
        config_file = os.path.join(self.ipfs_cluster_path, "ctl", "config.json")
        
        if not os.path.exists(config_file):
            return {"valid": False, "error": "Config file not found"}
        
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # IPFS cluster ctl config is simple, just check it's valid JSON
            return {"valid": True, "config_path": config_file}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _validate_s3_config(self) -> Dict[str, Any]:
        """Validate S3 configuration."""
        if not os.path.exists(self.s3_config_path):
            return {"valid": False, "error": "Config file not found"}
        
        try:
            with open(self.s3_config_path, 'r') as f:
                config_content = f.read()
            
            # Check for required fields
            required_fields = ["access_key", "secret_key", "host_base"]
            missing_fields = []
            
            for field in required_fields:
                if field not in config_content:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Missing required fields: {missing_fields}"
                }
            
            return {"valid": True, "config_path": self.s3_config_path}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _validate_huggingface_config(self) -> Dict[str, Any]:
        """Validate HuggingFace configuration."""
        config_file = os.path.join(self.hf_config_path, "config.json")
        
        if not os.path.exists(config_file):
            return {"valid": False, "error": "Config file not found"}
        
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Check required fields
            required_fields = ["cache_dir"]
            missing_fields = [field for field in required_fields if field not in config_data]
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Missing required fields: {missing_fields}"
                }
            
            return {"valid": True, "cache_dir": config_data.get("cache_dir")}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _validate_storacha_config(self) -> Dict[str, Any]:
        """Validate Storacha configuration."""
        config_file = os.path.join(self.storacha_config_path, "config.json")
        
        if not os.path.exists(config_file):
            return {"valid": False, "error": "Config file not found"}
        
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Check required fields
            required_fields = ["endpoints"]
            missing_fields = [field for field in required_fields if field not in config_data]
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Missing required fields: {missing_fields}"
                }
            
            return {"valid": True, "endpoints": config_data.get("endpoints")}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def _generate_summary(self, results: Dict[str, Any]) -> str:
        """Generate a human-readable summary of configuration results."""
        summary_lines = []
        
        for daemon, result in results.items():
            if daemon == "overall_success":
                continue
                
            if result.get("already_configured"):
                summary_lines.append(f"✅ {daemon.upper()}: Already configured")
            elif result.get("success"):
                summary_lines.append(f"✅ {daemon.upper()}: Configured successfully")
            else:
                error = result.get("error", "Unknown error")
                summary_lines.append(f"❌ {daemon.upper()}: Configuration failed - {error}")
        
        return "\n".join(summary_lines)
    
    def get_default_ipfs_config(self) -> Dict[str, Any]:
        """Get default IPFS configuration template."""
        return {
            "cluster_name": "ipfs-kit-cluster",
            "profile": "badgerds",
            "swarm_addresses": [
                "/ip4/0.0.0.0/tcp/4001",
                "/ip6/::/tcp/4001",
                "/ip4/0.0.0.0/udp/4001/quic",
                "/ip6/::/udp/4001/quic"
            ],
            "api_address": "/ip4/127.0.0.1/tcp/5001",
            "gateway_address": "/ip4/127.0.0.1/tcp/8080"
        }
    
    def get_default_lotus_config(self) -> Dict[str, Any]:
        """Get default Lotus configuration template."""
        return {
            "api_port": 1234,
            "p2p_port": 1235,
            "api_address": "/ip4/127.0.0.1/tcp/1234/http",
            "listen_addresses": [
                "/ip4/0.0.0.0/tcp/1235",
                "/ip6/::/tcp/1235"
            ],
            "bootstrap_peers": [
                "/dns4/bootstrap-0.mainnet.filops.net/tcp/1347/p2p/12D3KooWCVe8MmsEMes2FzgTpt9fXtmCY7wrq91GRiaC8PHSCCBj",
                "/dns4/bootstrap-1.mainnet.filops.net/tcp/1347/p2p/12D3KooWCwevHg1yLCvktf2nvLu7L9894mcrJR4MsBCcm4syShVc"
            ]
        }
    
    def get_default_lassie_config(self) -> Dict[str, Any]:
        """Get default Lassie configuration template."""
        return {
            "retrieval_timeout": "30m",
            "bitswap_concurrent": 6,
            "bitswap_requests_per_peer": 10,
            "http_concurrent": 6,
            "http_requests_per_peer": 10,
            "providers": ["127.0.0.1:1234"]
        }
    
    def get_default_s3_config(self) -> Dict[str, Any]:
        """Get default S3 configuration template."""
        return {
            "access_key": "your-access-key",
            "secret_key": "your-secret-key",
            "host_base": "s3.amazonaws.com",
            "host_bucket": "%(bucket)s.s3.amazonaws.com",
            "bucket_location": "us-east-1",
            "use_https": "True",
            "signature_v2": "False"
        }
    
    def get_default_huggingface_config(self) -> Dict[str, Any]:
        """Get default HuggingFace configuration template."""
        return {
            "cache_dir": self.hf_config_path,
            "use_auth_token": False,
            "offline": False,
            "proxies": {},
            "user_agent": "ipfs_kit_py/1.0"
        }
    
    def get_default_storacha_config(self) -> Dict[str, Any]:
        """Get default Storacha configuration template."""
        return {
            "endpoints": [
                "https://up.storacha.network/bridge",
                "https://api.web3.storage",
                "https://up.web3.storage/bridge"
            ],
            "timeout": 30,
            "retries": 3,
            "mock_mode": False,
            "api_key": "your-api-key-here"
        }

    def update_daemon_config(self, daemon_name: str, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update configuration for a specific daemon.
        
        Args:
            daemon_name: Name of the daemon to update
            config_updates: Dictionary of configuration updates
            
        Returns:
            Dictionary with update status
        """
        logger.info(f"🔧 Updating {daemon_name} configuration...")
        
        try:
            if daemon_name == "ipfs":
                return self._update_ipfs_config(config_updates)
            elif daemon_name == "lotus":
                return self._update_lotus_config(config_updates)
            elif daemon_name == "lassie":
                return self._update_lassie_config(config_updates)
            elif daemon_name == "ipfs_cluster_service":
                return self._update_ipfs_cluster_service_config(config_updates)
            elif daemon_name == "ipfs_cluster_follow":
                return self._update_ipfs_cluster_follow_config(config_updates)
            elif daemon_name == "ipfs_cluster_ctl":
                return self._update_ipfs_cluster_ctl_config(config_updates)
            elif daemon_name == "s3":
                return self._update_s3_config(config_updates)
            elif daemon_name == "huggingface":
                return self._update_huggingface_config(config_updates)
            elif daemon_name == "storacha":
                return self._update_storacha_config(config_updates)
            else:
                return {"success": False, "error": f"Unknown daemon: {daemon_name}"}
                
        except Exception as e:
            logger.error(f"❌ Error updating {daemon_name} configuration: {e}")
            return {"success": False, "error": str(e)}

    def _update_ipfs_config(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update IPFS configuration."""
        config_file = os.path.join(self.ipfs_path, "config")
        
        try:
            if not os.path.exists(config_file):
                return {"success": False, "error": "IPFS config file not found"}
            
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Update configuration
            config_data.update(config_updates)
            
            # Write back to file
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            return {"success": True, "updated_fields": list(config_updates.keys())}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_lotus_config(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update Lotus configuration."""
        config_file = os.path.join(self.lotus_path, "config.toml")
        
        try:
            if not os.path.exists(config_file):
                return {"success": False, "error": "Lotus config file not found"}
            
            # For TOML files, we need to be more careful about updates
            # For now, we'll create a backup and update specific fields
            import shutil
            backup_file = config_file + ".backup"
            shutil.copy2(config_file, backup_file)
            
            # Read current config
            with open(config_file, 'r') as f:
                config_content = f.read()
            
            # Simple approach: append new config at the end
            with open(config_file, 'a') as f:
                f.write("\n# Updated by daemon_config_manager\n")
                for key, value in config_updates.items():
                    f.write(f"{key} = {repr(value)}\n")
            
            return {"success": True, "updated_fields": list(config_updates.keys())}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_lassie_config(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update Lassie configuration."""
        config_file = os.path.join(self.lassie_path, "config.json")
        
        try:
            if not os.path.exists(config_file):
                return {"success": False, "error": "Lassie config file not found"}
            
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Update configuration
            config_data.update(config_updates)
            
            # Write back to file
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            return {"success": True, "updated_fields": list(config_updates.keys())}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_ipfs_cluster_service_config(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update IPFS cluster service configuration."""
        config_file = os.path.join(self.ipfs_cluster_path, "service.json")
        
        try:
            if not os.path.exists(config_file):
                return {"success": False, "error": "IPFS cluster service config file not found"}
            
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Update configuration
            config_data.update(config_updates)
            
            # Write back to file
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            return {"success": True, "updated_fields": list(config_updates.keys())}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_ipfs_cluster_follow_config(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update IPFS cluster follow configuration."""
        cluster_name = "ipfs-kit-cluster"
        config_path = os.path.join(self.ipfs_cluster_follow_path, cluster_name)
        config_file = os.path.join(config_path, "service.json")
        
        try:
            if not os.path.exists(config_file):
                return {"success": False, "error": "IPFS cluster follow config file not found"}
            
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Update configuration
            config_data.update(config_updates)
            
            # Write back to file
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            return {"success": True, "updated_fields": list(config_updates.keys())}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_ipfs_cluster_ctl_config(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update IPFS cluster ctl configuration."""
        config_file = os.path.join(self.ipfs_cluster_path, "ctl", "config.json")
        
        try:
            if not os.path.exists(config_file):
                return {"success": False, "error": "IPFS cluster ctl config file not found"}
            
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Update configuration
            config_data.update(config_updates)
            
            # Write back to file
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            return {"success": True, "updated_fields": list(config_updates.keys())}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_s3_config(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update S3 configuration."""
        try:
            if not os.path.exists(self.s3_config_path):
                return {"success": False, "error": "S3 config file not found"}
            
            # Read current config
            with open(self.s3_config_path, 'r') as f:
                config_content = f.read()
            
            # Parse existing config
            config_dict = {}
            for line in config_content.split('\n'):
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.split('=', 1)
                    config_dict[key.strip()] = value.strip()
            
            # Update configuration
            config_dict.update(config_updates)
            
            # Write back to file
            with open(self.s3_config_path, 'w') as f:
                for key, value in config_dict.items():
                    f.write(f"{key} = {value}\n")
            
            return {"success": True, "updated_fields": list(config_updates.keys())}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_huggingface_config(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update HuggingFace configuration."""
        config_file = os.path.join(self.hf_config_path, "config.json")
        
        try:
            if not os.path.exists(config_file):
                return {"success": False, "error": "HuggingFace config file not found"}
            
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Update configuration
            config_data.update(config_updates)
            
            # Write back to file
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            return {"success": True, "updated_fields": list(config_updates.keys())}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_storacha_config(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update Storacha configuration."""
        config_file = os.path.join(self.storacha_config_path, "config.json")
        
        try:
            if not os.path.exists(config_file):
                return {"success": False, "error": "Storacha config file not found"}
            
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Update configuration
            config_data.update(config_updates)
            
            # Write back to file
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            return {"success": True, "updated_fields": list(config_updates.keys())}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
        

def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Daemon Configuration Manager for ipfs_kit_py"
    )
    parser.add_argument(
        "--daemon", 
        choices=["ipfs", "lotus", "lassie", "ipfs_cluster_service", "ipfs_cluster_follow", "ipfs_cluster_ctl", "s3", "huggingface", "storacha", "all"],
        default="all",
        help="Daemon to configure"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing configurations"
    )
    parser.add_argument(
        "--force-reconfigure",
        action="store_true",
        help="Force reconfiguration even if config exists"
    )
    
    args = parser.parse_args()
    
    # Initialize manager
    manager = DaemonConfigManager()
    
    if args.validate_only:
        # Validation only
        results = manager.validate_daemon_configs()
        print(f"Validation results: {json.dumps(results, indent=2)}")
        return 0 if results["overall_valid"] else 1
    
    # Configuration
    results: Dict[str, Any] = {}
    if args.daemon == "all":
        results = manager.check_and_configure_all_daemons()
    elif args.daemon == "ipfs":
        results = {"ipfs": manager.check_and_configure_ipfs()}
    elif args.daemon == "lotus":
        results = {"lotus": manager.check_and_configure_lotus()}
    elif args.daemon == "lassie":
        results = {"lassie": manager.check_and_configure_lassie()}
    elif args.daemon == "ipfs_cluster_service":
        results = {"ipfs_cluster_service": manager.check_and_configure_ipfs_cluster_service()}
    elif args.daemon == "ipfs_cluster_follow":
        results = {"ipfs_cluster_follow": manager.check_and_configure_ipfs_cluster_follow()}
    elif args.daemon == "ipfs_cluster_ctl":
        results = {"ipfs_cluster_ctl": manager.check_and_configure_ipfs_cluster_ctl()}
    elif args.daemon == "s3":
        results = {"s3": manager.check_and_configure_s3()}
    elif args.daemon == "huggingface":
        results = {"huggingface": manager.check_and_configure_huggingface()}
    elif args.daemon == "storacha":
        results = {"storacha": manager.check_and_configure_storacha()}
    
    print(f"Configuration results: {json.dumps(results, indent=2)}")
    
    # Return success code
    if "overall_success" in results:
        return 0 if results["overall_success"] else 1
    else:
        return 0 if all(r.get("success", False) or r.get("already_configured", False) for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
