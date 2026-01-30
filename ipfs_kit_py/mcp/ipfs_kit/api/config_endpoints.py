"""
Configuration endpoints for API routes.
"""

import logging
from typing import Dict, Any, Optional
import json
import os
import yaml
from pathlib import Path
from datetime import datetime, timedelta
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
    
    async def set_backend_config(self, backend_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set backend configuration."""
        try:
            # Get current comprehensive backend config
            current_config = await self.get_backend_config(backend_name)

            # Update current_config with incoming flat config_data
            # This logic needs to correctly map flat keys to nested structure
            updated_config = current_config.copy()

            # Handle top-level keys directly
            if "enabled" in config_data: updated_config["enabled"] = self._to_bool(config_data["enabled"])

            # Handle nested 'connection' section
            if "connection.url" in config_data: updated_config["connection"]["url"] = config_data["connection.url"]
            if "connection.timeout" in config_data: updated_config["connection"]["timeout"] = int(config_data["connection.timeout"])
            if "connection.retry_attempts" in config_data: updated_config["connection"]["retry_attempts"] = int(config_data["connection.retry_attempts"])
            if "connection.connection_pool_size" in config_data: updated_config["connection"]["connection_pool_size"] = int(config_data["connection.connection_pool_size"])
            if "connection.keep_alive" in config_data: updated_config["connection"]["keep_alive"] = self._to_bool(config_data["connection.keep_alive"])

            # Handle nested 'performance' section
            if "performance.max_concurrent_requests" in config_data: updated_config["performance"]["max_concurrent_requests"] = int(config_data["performance.max_concurrent_requests"])
            if "performance.request_timeout" in config_data: updated_config["performance"]["request_timeout"] = int(config_data["performance.request_timeout"])
            if "performance.circuit_breaker_enabled" in config_data: updated_config["performance"]["circuit_breaker_enabled"] = self._to_bool(config_data["performance.circuit_breaker_enabled"])
            if "performance.cache_enabled" in config_data: updated_config["performance"]["cache_enabled"] = self._to_bool(config_data["performance.cache_enabled"])
            if "performance.compression_enabled" in config_data: updated_config["performance"]["compression_enabled"] = self._to_bool(config_data["performance.compression_enabled"])

            # Handle nested 'monitoring' section
            if "monitoring.health_check_enabled" in config_data: updated_config["monitoring"]["health_check_enabled"] = self._to_bool(config_data["monitoring.health_check_enabled"])
            if "monitoring.health_check_interval" in config_data: updated_config["monitoring"]["health_check_interval"] = int(config_data["monitoring.health_check_interval"])
            if "monitoring.metrics_collection_enabled" in config_data: updated_config["monitoring"]["metrics_collection_enabled"] = self._to_bool(config_data["monitoring.metrics_collection_enabled"])
            if "monitoring.log_collection_enabled" in config_data: updated_config["monitoring"]["log_collection_enabled"] = self._to_bool(config_data["monitoring.log_collection_enabled"])
            if "monitoring.alert_enabled" in config_data: updated_config["monitoring"]["alert_enabled"] = self._to_bool(config_data["monitoring.alert_enabled"])

            # Handle nested 'authentication' section
            if "authentication.auth_type" in config_data: updated_config["authentication"]["auth_type"] = config_data["authentication.auth_type"]
            if "authentication.api_key" in config_data: updated_config["authentication"]["api_key"] = config_data["authentication.api_key"]
            if "authentication.username" in config_data: updated_config["authentication"]["username"] = config_data["authentication.username"]
            if "authentication.password" in config_data: updated_config["authentication"]["password"] = config_data["authentication.password"]
            if "authentication.token" in config_data: updated_config["authentication"]["token"] = config_data["authentication.token"]

            # Handle nested 'advanced' section
            if "advanced.ssl_verify" in config_data: updated_config["advanced"]["ssl_verify"] = self._to_bool(config_data["advanced.ssl_verify"])
            if "advanced.proxy_enabled" in config_data: updated_config["advanced"]["proxy_enabled"] = self._to_bool(config_data["advanced.proxy_enabled"])
            if "advanced.proxy_url" in config_data: updated_config["advanced"]["proxy_url"] = config_data["advanced.proxy_url"]
            
            # Special handling for custom_headers (JSON string to dict)
            if "advanced.custom_headers" in config_data:
                try:
                    updated_config["advanced"]["custom_headers"] = json.loads(config_data["advanced.custom_headers"])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON for custom_headers: {config_data['advanced.custom_headers']}")
                    # Optionally, add an error to validation_errors or return an error response

            # Special handling for custom_options (JSON string to dict)
            if "advanced.custom_options" in config_data:
                try:
                    updated_config["advanced"]["custom_options"] = json.loads(config_data["advanced.custom_options"])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON for custom_options: {config_data['advanced.custom_options']}")
                    # Optionally, add an error to validation_errors or return an error response

            # Validate the fully formed updated_config
            validation_result = self._validate_backend_config(backend_name, updated_config)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "Configuration validation failed",
                    "validation_errors": validation_result["errors"]
                }
            
            # Save to backend monitor
            result = await self.backend_monitor.set_backend_config(backend_name, updated_config)
            
            # Save to file for persistence (using the updated_config)
            backend_config_file = self.config_dir / f"{backend_name}_config.yaml"
            with open(backend_config_file, 'w') as f:
                yaml.dump(updated_config, f, default_flow_style=False)
            
            return {
                "success": True,
                "message": f"Configuration for {backend_name} updated successfully",
                "restart_required": self._config_requires_restart(updated_config)
            }
        except Exception as e:
            logger.error(f"Error setting config for {backend_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def _to_bool(self, value: Any) -> bool:
        """Converts various input values to a boolean."""
        if isinstance(value, str):
            return value.lower() in ('true', '1', 't', 'y', 'yes', 'on')
        return bool(value)
    
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
    
    async def set_package_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
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
            result = await self.backend_monitor.set_package_config(config)
            
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
        """Get configuration for all backends with comprehensive settings."""
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
                "storage": {
                    "quota_gb": self._get_backend_quota(backend_name),
                    "quota_enabled": True,
                    "quota_warning_threshold": 0.8,
                    "quota_enforcement": "soft",
                    "used_gb": 0.0,
                    "available_gb": self._get_backend_quota(backend_name)
                },
                "cache_policy": {
                    "enabled": True,
                    "type": "lru",  # lru, lfu, fifo, ttl
                    "max_size_gb": self._get_cache_size(backend_name),
                    "ttl_hours": 24,
                    "eviction_policy": "size_based",  # size_based, time_based, hybrid
                    "compression_enabled": True,
                    "auto_cleanup": True,
                    "cleanup_interval_hours": 6
                },
                "replication": {
                    "enabled": backend_name in ["ipfs", "cluster"],
                    "priority": self._get_replication_priority(backend_name),
                    "auto_replicate": True,
                    "min_replicas": 1,
                    "max_replicas": 3,
                    "replication_strategy": "balanced",  # balanced, performance, redundancy
                    "verify_integrity": True,
                    "repair_on_failure": True
                },
                "metadata": {
                    "import_enabled": True,
                    "export_enabled": True,
                    "auto_import": backend_name in ["ipfs", "cluster"],
                    "auto_export": backend_name in ["ipfs", "cluster"],
                    "import_format": "json",  # json, yaml, csv
                    "export_format": "json",
                    "include_vfs_metadata": True,
                    "include_traffic_data": True,
                    "metadata_compression": True
                },
                "pins": {
                    "import_enabled": True,
                    "export_enabled": True,
                    "auto_import": backend_name in ["ipfs", "cluster"],
                    "auto_export": backend_name in ["ipfs", "cluster"],
                    "pin_format": "json",
                    "recursive_pins": True,
                    "verify_pins": True,
                    "pin_metadata": True
                },
                "traffic_monitoring": {
                    "enabled": True,
                    "track_requests": True,
                    "track_data_transfer": True,
                    "track_response_times": True,
                    "detailed_logging": False,
                    "analytics_retention_days": 30,
                    "real_time_alerts": False
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

    def _get_backend_quota(self, backend_name: str) -> float:
        """Get default storage quota for backend in GB."""
        quotas = {
            "ipfs": 100.0,
            "cluster": 200.0,
            "lotus": 500.0,
            "storacha": 1000.0,
            "s3": 2000.0,
            "huggingface": 50.0,
            "pinata": 100.0
        }
        return quotas.get(backend_name, 100.0)
    
    def _get_cache_size(self, backend_name: str) -> float:
        """Get default cache size for backend in GB."""
        cache_sizes = {
            "ipfs": 10.0,
            "cluster": 20.0,
            "lotus": 50.0,
            "storacha": 100.0,
            "s3": 200.0,
            "huggingface": 5.0,
            "pinata": 10.0
        }
        return cache_sizes.get(backend_name, 10.0)
    
    def _get_replication_priority(self, backend_name: str) -> int:
        """Get replication priority for backend (1-10, higher = more priority)."""
        priorities = {
            "ipfs": 8,
            "cluster": 9,
            "lotus": 7,
            "storacha": 6,
            "s3": 5,
            "huggingface": 4,
            "pinata": 3
        }
        return priorities.get(backend_name, 5)

    async def get_backend_storage_stats(self, backend_name: str) -> Dict[str, Any]:
        """Get storage statistics for a specific backend."""
        try:
            # Get basic storage info
            config = await self.get_backend_config(backend_name)
            storage_config = config.get("storage", {})
            
            # Calculate storage usage (mock data for now)
            quota_gb = storage_config.get("quota_gb", 100.0)
            used_gb = await self._calculate_backend_usage(backend_name)
            available_gb = max(0, quota_gb - used_gb)
            usage_percentage = (used_gb / quota_gb) * 100 if quota_gb > 0 else 0
            
            return {
                "success": True,
                "backend": backend_name,
                "storage": {
                    "quota_gb": quota_gb,
                    "used_gb": used_gb,
                    "available_gb": available_gb,
                    "usage_percentage": round(usage_percentage, 2),
                    "quota_enabled": storage_config.get("quota_enabled", True),
                    "warning_threshold": storage_config.get("quota_warning_threshold", 0.8),
                    "enforcement": storage_config.get("quota_enforcement", "soft")
                },
                "cache": await self._get_backend_cache_stats(backend_name),
                "traffic": await self._get_backend_traffic_stats(backend_name)
            }
        except Exception as e:
            logger.error(f"Error getting storage stats for {backend_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def set_backend_storage_config(self, backend_name: str, storage_config: Dict[str, Any]) -> Dict[str, Any]:
        """Set storage configuration for a backend."""
        try:
            # Get current backend config
            current_config = await self.get_backend_config(backend_name)
            
            # Update storage section
            current_config["storage"].update(storage_config)
            
            # Validate storage config
            validation_result = self._validate_storage_config(storage_config)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "Storage configuration validation failed",
                    "validation_errors": validation_result["errors"]
                }
            
            # Save updated config
            result = await self.set_backend_config(backend_name, current_config)
            
            return {
                "success": True,
                "message": f"Storage configuration for {backend_name} updated successfully",
                "requires_restart": result.get("restart_required", False)
            }
        except Exception as e:
            logger.error(f"Error setting storage config for {backend_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def export_backend_metadata(self, backend_name: str, export_type: str = "both") -> Dict[str, Any]:
        """Export filesystem metadata and/or pins for a backend."""
        try:
            result = {
                "success": True,
                "backend": backend_name,
                "export_type": export_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": {}
            }
            
            # Export filesystem metadata
            if export_type in ["metadata", "both"]:
                result["data"]["filesystem_metadata"] = await self._export_filesystem_metadata(backend_name)
            
            # Export pins
            if export_type in ["pins", "both"]:
                result["data"]["pins"] = await self._export_pins_data(backend_name)
            
            # Export traffic data if enabled
            config = await self.get_backend_config(backend_name)
            if config.get("metadata", {}).get("include_traffic_data", True):
                result["data"]["traffic_stats"] = await self._get_backend_traffic_stats(backend_name)
            
            # Export VFS metadata if enabled
            if config.get("metadata", {}).get("include_vfs_metadata", True):
                result["data"]["vfs_metadata"] = await self._export_vfs_metadata(backend_name)
            
            return result
        except Exception as e:
            logger.error(f"Error exporting metadata for {backend_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def import_backend_metadata(self, backend_name: str, import_data: Dict[str, Any], import_type: str = "both") -> Dict[str, Any]:
        """Import filesystem metadata and/or pins for a backend."""
        try:
            imported_items = []
            
            # Import filesystem metadata
            if import_type in ["metadata", "both"] and "filesystem_metadata" in import_data:
                metadata_result = await self._import_filesystem_metadata(backend_name, import_data["filesystem_metadata"])
                imported_items.append(f"filesystem_metadata: {metadata_result.get('count', 0)} items")
            
            # Import pins
            if import_type in ["pins", "both"] and "pins" in import_data:
                pins_result = await self._import_pins_data(backend_name, import_data["pins"])
                imported_items.append(f"pins: {pins_result.get('count', 0)} items")
            
            # Import VFS metadata if present
            if "vfs_metadata" in import_data:
                vfs_result = await self._import_vfs_metadata(backend_name, import_data["vfs_metadata"])
                imported_items.append(f"vfs_metadata: {vfs_result.get('count', 0)} items")
            
            return {
                "success": True,
                "backend": backend_name,
                "import_type": import_type,
                "imported": imported_items,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error importing metadata for {backend_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_backend_cache_stats(self, backend_name: str) -> Dict[str, Any]:
        """Get cache statistics for a backend."""
        try:
            return await self._get_backend_cache_stats(backend_name)
        except Exception as e:
            logger.error(f"Error getting cache stats for {backend_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def clear_backend_cache(self, backend_name: str, cache_type: str = "all") -> Dict[str, Any]:
        """Clear cache for a backend."""
        try:
            # Clear different types of cache
            cleared_items = []
            
            if cache_type in ["all", "data"]:
                data_result = await self._clear_data_cache(backend_name)
                cleared_items.append(f"data_cache: {data_result.get('count', 0)} items")
            
            if cache_type in ["all", "metadata"]:
                metadata_result = await self._clear_metadata_cache(backend_name)
                cleared_items.append(f"metadata_cache: {metadata_result.get('count', 0)} items")
            
            if cache_type in ["all", "traffic"]:
                traffic_result = await self._clear_traffic_cache(backend_name)
                cleared_items.append(f"traffic_cache: {traffic_result.get('count', 0)} items")
            
            return {
                "success": True,
                "backend": backend_name,
                "cache_type": cache_type,
                "cleared": cleared_items,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error clearing cache for {backend_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def optimize_backend_cache(self, backend_name: str) -> Dict[str, Any]:
        """Optimize cache for a backend based on its policy."""
        try:
            config = await self.get_backend_config(backend_name)
            cache_policy = config.get("cache_policy", {})
            
            # Run optimization based on policy
            optimization_result = await self._run_cache_optimization(backend_name, cache_policy)
            
            return {
                "success": True,
                "backend": backend_name,
                "optimization": optimization_result,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error optimizing cache for {backend_name}: {e}")
            return {"success": False, "error": str(e)}
    
    # Helper methods for backend operations
    async def _calculate_backend_usage(self, backend_name: str) -> float:
        """Calculate storage usage for backend in GB."""
        # Mock implementation - would integrate with actual backend
        usage_mock = {
            "ipfs": 25.5,
            "cluster": 45.2,
            "lotus": 125.8,
            "storacha": 234.1,
            "s3": 567.9,
            "huggingface": 12.3,
            "pinata": 34.7
        }
        return usage_mock.get(backend_name, 10.0)
    
    async def _get_backend_cache_stats(self, backend_name: str) -> Dict[str, Any]:
        """Get cache statistics for a backend."""
        return {
            "cache_size_gb": self._get_cache_size(backend_name),
            "used_gb": await self._calculate_backend_usage(backend_name) * 0.2,  # Mock: 20% of storage is cache
            "hit_rate": 0.75,  # Mock cache hit rate
            "miss_rate": 0.25,
            "evictions": 145,
            "last_cleanup": (datetime.utcnow() - timedelta(hours=3)).isoformat()
        }
    
    async def _get_backend_traffic_stats(self, backend_name: str) -> Dict[str, Any]:
        """Get traffic statistics for a backend."""
        return {
            "requests_total": 1250,
            "requests_success": 1175,
            "requests_failed": 75,
            "data_transferred_gb": 45.2,
            "avg_response_time_ms": 150,
            "last_request": (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        }
    
    async def _export_filesystem_metadata(self, backend_name: str) -> Dict[str, Any]:
        """Export filesystem metadata for a backend."""
        # Mock implementation
        return {
            "count": 150,
            "metadata": [
                {"path": "/example/file.txt", "size": 1024, "cid": "QmExample1"},
                {"path": "/example/dir/", "type": "directory", "cid": "QmExample2"}
            ]
        }
    
    async def _export_pins_data(self, backend_name: str) -> Dict[str, Any]:
        """Export pins data for a backend."""
        # Mock implementation
        return {
            "count": 75,
            "pins": [
                {"cid": "QmPin1", "type": "recursive", "size": 2048},
                {"cid": "QmPin2", "type": "direct", "size": 1024}
            ]
        }
    
    async def _export_vfs_metadata(self, backend_name: str) -> Dict[str, Any]:
        """Export VFS metadata for a backend."""
        # Mock implementation
        return {
            "count": 200,
            "vfs_entries": [
                {"vfs_id": "vfs_001", "backend_cid": "QmVFS1", "metadata": {}},
                {"vfs_id": "vfs_002", "backend_cid": "QmVFS2", "metadata": {}}
            ]
        }
    
    async def _import_filesystem_metadata(self, backend_name: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Import filesystem metadata for a backend."""
        # Mock implementation
        return {"count": len(metadata.get("metadata", [])), "success": True}
    
    async def _import_pins_data(self, backend_name: str, pins_data: Dict[str, Any]) -> Dict[str, Any]:
        """Import pins data for a backend."""
        # Mock implementation
        return {"count": len(pins_data.get("pins", [])), "success": True}
    
    async def _import_vfs_metadata(self, backend_name: str, vfs_data: Dict[str, Any]) -> Dict[str, Any]:
        """Import VFS metadata for a backend."""
        # Mock implementation
        return {"count": len(vfs_data.get("vfs_entries", [])), "success": True}
    
    async def _clear_data_cache(self, backend_name: str) -> Dict[str, Any]:
        """Clear data cache for a backend."""
        # Mock implementation
        return {"count": 50, "success": True}
    
    async def _clear_metadata_cache(self, backend_name: str) -> Dict[str, Any]:
        """Clear metadata cache for a backend."""
        # Mock implementation
        return {"count": 25, "success": True}
    
    async def _clear_traffic_cache(self, backend_name: str) -> Dict[str, Any]:
        """Clear traffic cache for a backend."""
        # Mock implementation
        return {"count": 15, "success": True}
    
    async def _run_cache_optimization(self, backend_name: str, cache_policy: Dict[str, Any]) -> Dict[str, Any]:
        """Run cache optimization based on policy."""
        # Mock implementation
        return {
            "items_evicted": 25,
            "space_freed_gb": 2.5,
            "optimization_type": cache_policy.get("type", "lru"),
            "duration_ms": 150
        }
    
    def _validate_storage_config(self, storage_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate storage configuration."""
        errors = []
        
        quota_gb = storage_config.get("quota_gb")
        if quota_gb is not None and (not isinstance(quota_gb, (int, float)) or quota_gb <= 0):
            errors.append("quota_gb must be a positive number")
        
        warning_threshold = storage_config.get("quota_warning_threshold")
        if warning_threshold is not None and (not isinstance(warning_threshold, (int, float)) or not 0 < warning_threshold <= 1):
            errors.append("quota_warning_threshold must be between 0 and 1")
        
        enforcement = storage_config.get("quota_enforcement")
        if enforcement is not None and enforcement not in ["soft", "hard"]:
            errors.append("quota_enforcement must be 'soft' or 'hard'")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

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
