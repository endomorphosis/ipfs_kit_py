"""
Configuration endpoints for API routes.
"""

import logging
from typing import Dict, Any, Optional
import json
import os
import yaml
from pathlib import Path
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ConfigEndpoints:
    """Configuration-related API endpoints."""
    
    def __init__(self, backend_monitor):
        self.backend_monitor = backend_monitor
        self.config_dir = Path.home() / ".ipfs_kit"
        self.config_file = self.config_dir / "config.yaml"
        self.package_config_file = self.config_dir / "package_config.yaml"
        
        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)
    
    async def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get backend configuration."""
        try:
            # Get from backend monitor and enhance with comprehensive config
            base_config = await self.backend_monitor.get_backend_config(backend_name)
            
            # Enhance with comprehensive configuration options
            enhanced_config = {
                "name": backend_name,
                "enabled": base_config.get("enabled", True),
                "connection": {
                    "url": base_config.get("url", f"http://localhost:{self._get_default_port(backend_name)}"),
                    "timeout": base_config.get("timeout", 30),
                    "retry_attempts": base_config.get("retry_attempts", 3),
                    "connection_pool_size": 10,
                    "keep_alive": True
                },
                "performance": {
                    "max_concurrent_requests": 50,
                    "request_timeout": 30,
                    "circuit_breaker_enabled": True,
                    "cache_enabled": True,
                    "compression_enabled": True
                },
                "monitoring": {
                    "health_check_enabled": True,
                    "health_check_interval": 60,
                    "metrics_collection_enabled": True,
                    "log_collection_enabled": True,
                    "alert_enabled": True
                },
                "authentication": {
                    "auth_type": "none",
                    "api_key": "",
                    "username": "",
                    "password": "",
                    "token": ""
                },
                "advanced": {
                    "custom_headers": {},
                    "ssl_verify": True,
                    "proxy_enabled": False,
                    "proxy_url": "",
                    "custom_options": {}
                }
            }
            
            return enhanced_config
        except Exception as e:
            logger.error(f"Error getting config for {backend_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def set_backend_config(self, backend_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Set backend configuration."""
        try:
            # Validate configuration
            validation_result = self._validate_backend_config(backend_name, config)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "Configuration validation failed",
                    "validation_errors": validation_result["errors"]
                }
            
            # Save to backend monitor
            result = await self.backend_monitor.set_backend_config(backend_name, config)
            
            # Save to file for persistence
            backend_config_file = self.config_dir / f"{backend_name}_config.yaml"
            with open(backend_config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            return {
                "success": True,
                "message": f"Configuration for {backend_name} updated successfully",
                "restart_required": self._config_requires_restart(config)
            }
        except Exception as e:
            logger.error(f"Error setting config for {backend_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def get_package_config(self) -> Dict[str, Any]:
        """Get comprehensive package configuration."""
        try:
            base_config = self.backend_monitor.get_package_config()
            
            # Enhance with comprehensive package information
            enhanced_config = {
                "package_info": {
                    "version": "0.3.0",
                    "name": "ipfs_kit_py",
                    "description": "IPFS Kit Python Package with MCP Server",
                    "author": "IPFS Kit Team",
                    "repository": "https://github.com/ipfs-kit/ipfs_kit_py"
                },
                "environment": self._get_environment_info(),
                "dependencies": self._get_dependency_info(),
                "features": self._get_enabled_features(),
                "installation": self._get_installation_info(),
                "development": self._get_development_config(),
                "runtime": self._get_runtime_config()
            }
            
            return enhanced_config
        except Exception as e:
            logger.error(f"Error getting package config: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def set_package_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Set package configuration."""
        try:
            # Validate package configuration
            validation_result = self._validate_package_config(config)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "Package configuration validation failed",
                    "validation_errors": validation_result["errors"]
                }
            
            # Save to backend monitor
            result = self.backend_monitor.set_package_config(config)
            
            # Save to file for persistence
            with open(self.package_config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            return {
                "success": True,
                "message": "Package configuration updated successfully"
            }
        except Exception as e:
            logger.error(f"Error setting package config: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def export_config(self) -> Dict[str, Any]:
        """Export comprehensive configuration."""
        try:
            base_export = self.backend_monitor.export_config()
            
            # Create comprehensive configuration export
            comprehensive_config = {
                "metadata": {
                    "export_version": "1.0",
                    "export_timestamp": self._get_current_timestamp(),
                    "package_version": "0.3.0"
                },
                "system": self._get_system_config(),
                "package": self.get_package_config(),
                "backends": {},
                "dashboard": self._get_dashboard_config(),
                "monitoring": self._get_monitoring_config(),
                "vfs": self._get_vfs_config(),
                "security": self._get_security_config(),
                "performance": self._get_performance_config()
            }
            
            # Add all backend configurations
            backend_names = ["ipfs", "cluster", "lotus", "storacha", "s3", "huggingface", "pinata"]
            for backend_name in backend_names:
                try:
                    backend_config = self.get_backend_config(backend_name)
                    comprehensive_config["backends"][backend_name] = backend_config
                except Exception as e:
                    logger.warning(f"Could not export config for {backend_name}: {e}")
            
            return {
                "success": True,
                "config": comprehensive_config
            }
        except Exception as e:
            logger.error(f"Error exporting config: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_config(self) -> Dict[str, Any]:
        """Get comprehensive system configuration."""
        try:
            config = {
                "system": self._get_system_config(),
                "backends": await self._get_all_backend_configs(),
                "dashboard": self._get_dashboard_config(),
                "monitoring": self._get_monitoring_config(),
                "vfs": self._get_vfs_config(),
                "security": self._get_security_config(),
                "performance": self._get_performance_config()
            }
            
            return {
                "success": True,
                "config": config,
                "meta": {
                    "config_version": "1.0",
                    "last_modified": self._get_config_mtime(),
                    "config_file": str(self.config_file)
                }
            }
        except Exception as e:
            logger.error(f"Error getting configuration: {e}")
            return {"success": False, "error": str(e)}
    
    async def save_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save comprehensive system configuration."""
        try:
            # Validate configuration
            validation_result = self._validate_config(config_data)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "Configuration validation failed",
                    "validation_errors": validation_result["errors"]
                }
            
            # Save configuration to file
            with open(self.config_file, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
            
            return {
                "success": True,
                "message": "Configuration saved successfully",
                "restart_required": self._config_requires_restart(config_data)
            }
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_system_config(self) -> Dict[str, Any]:
        """Get system-level configuration."""
        return {
            "server": {
                "host": "0.0.0.0",
                "port": 8000,
                "debug": False,
                "log_level": "INFO"
            },
            "database": {
                "type": "sqlite",
                "path": str(self.config_dir / "data.db"),
                "pool_size": 10
            },
            "cache": {
                "type": "memory",
                "max_size_mb": 512,
                "ttl_seconds": 3600
            }
        }
    
    async def _get_all_backend_configs(self) -> Dict[str, Any]:
        """Get configuration for all backends."""
        backends = {}
        backend_names = ["ipfs", "cluster", "lotus", "storacha", "s3", "huggingface", "pinata"]
        
        for backend_name in backend_names:
            backends[backend_name] = {
                "enabled": backend_name in ["ipfs", "cluster"],
                "url": f"http://localhost:{self._get_default_port(backend_name)}",
                "timeout": 30,
                "retry_attempts": 3,
                "health_check_interval": 60,
                "connection": {
                    "url": f"http://localhost:{self._get_default_port(backend_name)}",
                    "timeout": 30,
                    "retry_attempts": 3,
                    "connection_pool_size": 10,
                    "keep_alive": True
                },
                "performance": {
                    "max_concurrent_requests": 50,
                    "request_timeout": 30,
                    "circuit_breaker_enabled": True,
                    "cache_enabled": True,
                    "compression_enabled": True
                },
                "monitoring": {
                    "health_check_enabled": True,
                    "health_check_interval": 60,
                    "metrics_collection_enabled": True,
                    "log_collection_enabled": True,
                    "alert_enabled": True
                }
            }
        
        return backends
    
    def _get_dashboard_config(self) -> Dict[str, Any]:
        """Get dashboard configuration."""
        return {
            "title": "IPFS Kit MCP Server",
            "theme": "dark",
            "auto_refresh": True,
            "refresh_interval": 5000,
            "chart_type": "line",
            "show_debug_info": False,
            "tabs": {
                "monitoring": {"enabled": True, "default": True},
                "vfs_observatory": {"enabled": True, "default": False},
                "vector_kb": {"enabled": True, "default": False},
                "configuration": {"enabled": True, "default": False}
            }
        }
    
    def _get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration."""
        return {
            "enabled": True,
            "metrics_retention_days": 30,
            "alert_threshold": {
                "cpu_percent": 80,
                "memory_percent": 85,
                "disk_percent": 90,
                "response_time_ms": 1000,
                "error_rate_percent": 5
            },
            "notifications": {
                "email_enabled": False,
                "webhook_enabled": False,
                "log_enabled": True
            }
        }
    
    def _get_vfs_config(self) -> Dict[str, Any]:
        """Get VFS configuration."""
        return {
            "cache_size_mb": 256,
            "index_enabled": True,
            "compression_enabled": True,
            "encryption_enabled": False,
            "backup_enabled": False,
            "analytics_enabled": True,
            "performance_tracking": True
        }
    
    def _get_security_config(self) -> Dict[str, Any]:
        """Get security configuration."""
        return {
            "authentication": {
                "enabled": False,
                "type": "bearer_token",
                "token_expiry_hours": 24
            },
            "cors": {
                "enabled": True,
                "origins": ["*"],
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "headers": ["*"]
            },
            "rate_limiting": {
                "enabled": False,
                "requests_per_minute": 60,
                "burst_size": 10
            }
        }
    
    def _get_performance_config(self) -> Dict[str, Any]:
        """Get performance configuration."""
        return {
            "connection_pool_size": 20,
            "request_timeout": 30,
            "max_concurrent_requests": 100,
            "compression_enabled": True,
            "caching_enabled": True,
            "async_operations": True
        }
    
    def _get_environment_info(self) -> Dict[str, Any]:
        """Get environment information."""
        import sys
        import platform
        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "architecture": platform.architecture()[0],
            "hostname": platform.node(),
            "working_directory": os.getcwd()
        }
    
    def _get_dependency_info(self) -> Dict[str, Any]:
        """Get dependency information."""
        return {
            "fastapi": "^0.104.0",
            "uvicorn": "^0.24.0",
            "pydantic": "^2.0.0",
            "requests": "^2.31.0",
            "aiohttp": "^3.9.0",
            "websockets": "^12.0",
            "pyyaml": "^6.0"
        }
    
    def _get_enabled_features(self) -> Dict[str, Any]:
        """Get enabled features."""
        return {
            "modular_architecture": True,
            "web_dashboard": True,
            "websocket_support": True,
            "backend_monitoring": True,
            "vfs_analytics": True,
            "configuration_management": True,
            "real_time_updates": True,
            "api_endpoints": True
        }
    
    def _get_installation_info(self) -> Dict[str, Any]:
        """Get installation information."""
        return {
            "install_type": "development",
            "install_date": "2024-01-15",
            "install_path": os.getcwd(),
            "editable_install": True,
            "pip_version": "23.3.1"
        }
    
    def _get_development_config(self) -> Dict[str, Any]:
        """Get development configuration."""
        return {
            "debug_mode": True,
            "hot_reload": True,
            "log_level": "DEBUG",
            "test_mode": False,
            "profiling_enabled": False,
            "development_server": True
        }
    
    def _get_runtime_config(self) -> Dict[str, Any]:
        """Get runtime configuration."""
        return {
            "memory_limit_mb": 1024,
            "cpu_limit_percent": 80,
            "concurrent_workers": 4,
            "auto_scaling": False,
            "health_checks": True
        }
    
    def _get_default_port(self, backend_name: str) -> int:
        """Get default port for a backend."""
        ports = {
            "ipfs": 5001,
            "cluster": 9094,
            "lotus": 1234,
            "storacha": 443,
            "s3": 9000,
            "huggingface": 443,
            "pinata": 443
        }
        return ports.get(backend_name, 8080)
    
    def _get_config_mtime(self) -> Optional[str]:
        """Get configuration file modification time."""
        try:
            if self.config_file.exists():
                mtime = self.config_file.stat().st_mtime
                from datetime import datetime
                return datetime.fromtimestamp(mtime).isoformat()
            return None
        except Exception:
            return None
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _validate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration data."""
        errors = []
        
        if not isinstance(config_data, dict):
            errors.append("Configuration must be a dictionary")
        
        # Add more specific validation rules here
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _validate_backend_config(self, backend_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate backend-specific configuration."""
        errors = []
        
        if not isinstance(config_data, dict):
            errors.append("Backend configuration must be a dictionary")
        
        # Add backend-specific validation rules here
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _validate_package_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate package configuration."""
        errors = []
        
        if not isinstance(config_data, dict):
            errors.append("Package configuration must be a dictionary")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _config_requires_restart(self, config_data: Dict[str, Any]) -> bool:
        """Determine if configuration changes require a restart."""
        restart_triggers = ["server", "database", "security"]
        
        for trigger in restart_triggers:
            if trigger in config_data:
                return True
        
        return False

    async def get_global_config(self) -> Dict[str, Any]:
        """Get global configuration for the dashboard."""
        try:
            config = {
                "package": self.get_package_config(),
                "system": self._get_system_config(),
                "backends": await self._get_all_backend_configs(),
                "dashboard": self._get_dashboard_config(),
                "monitoring": self._get_monitoring_config(),
                "vfs": self._get_vfs_config(),
                "security": self._get_security_config(),
                "performance": self._get_performance_config()
            }
            
            return {
                "success": True,
                "config": config,
                "meta": {
                    "config_version": "1.0",
                    "last_modified": self._get_config_mtime(),
                    "config_file": str(self.config_file)
                }
            }
        except Exception as e:
            logger.error(f"Error getting global configuration: {e}")
            return {"success": False, "error": str(e)}
