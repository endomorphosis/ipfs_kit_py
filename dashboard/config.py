"""
Dashboard Configuration Module

Centralized configuration for the IPFS Kit Dashboard.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DashboardConfig:
    """Configuration for the IPFS Kit Dashboard."""
    
    # Web server settings
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    
    # Dashboard paths
    dashboard_path: str = "/dashboard"
    static_path: str = "/dashboard/static" 
    api_path: str = "/dashboard/api"
    
    # External service URLs
    mcp_server_url: str = "http://localhost:8765"
    ipfs_kit_url: str = "http://localhost:9090"
    
    # Data collection settings
    data_collection_interval: int = 10  # seconds
    metrics_update_interval: int = 5  # seconds
    max_data_points: int = 1000
    data_retention_hours: int = 24
    
    # MCP server endpoints
    mcp_metrics_endpoint: str = "/metrics"
    mcp_health_endpoint: str = "/health"
    
    # IPFS Kit integration
    ipfs_kit_enabled: bool = True
    prometheus_endpoint: str = "/metrics"
    prometheus_enabled: bool = True
    
    # Features
    enable_real_time_updates: bool = True
    enable_historical_data: bool = True
    enable_alerts: bool = True
    enable_charts: bool = True
    
    # Alerting
    alert_enabled: bool = True
    alert_cooldown_minutes: int = 5
    
    # Health monitoring thresholds
    health_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "cpu_usage_percent": 80.0,
        "memory_usage_percent": 85.0,
        "disk_usage_percent": 90.0,
        "response_time_seconds": 5.0
    })
    
    # Storage for dashboard data
    data_storage_type: str = "memory"  # "memory", "redis", "file"
    data_storage_config: Dict[str, Any] = field(default_factory=dict)
    
    # Chart settings
    chart_library: str = "chartjs"  # "chartjs", "plotly"
    chart_refresh_interval: int = 30  # seconds
    
    # Authentication (optional)
    enable_auth: bool = False
    auth_type: str = "simple"  # "simple", "oauth", "ldap"
    auth_config: Dict[str, Any] = field(default_factory=dict)
    
    # Alerting settings
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "cpu_usage": 80.0,
        "memory_usage": 90.0,
        "disk_usage": 95.0,
        "error_rate": 5.0,
        "response_time": 5000.0  # milliseconds
    })
    
    @classmethod
    def from_env(cls) -> 'DashboardConfig':
        """Create configuration from environment variables."""
        return cls(
            host=os.getenv("DASHBOARD_HOST", "0.0.0.0"),
            port=int(os.getenv("DASHBOARD_PORT", "8080")),
            debug=os.getenv("DASHBOARD_DEBUG", "false").lower() == "true",
            
            dashboard_path=os.getenv("DASHBOARD_PATH", "/dashboard"),
            static_path=os.getenv("DASHBOARD_STATIC_PATH", "/dashboard/static"),
            api_path=os.getenv("DASHBOARD_API_PATH", "/dashboard/api"),
            
            mcp_server_url=os.getenv("DASHBOARD_MCP_SERVER_URL", "http://localhost:8765"),
            ipfs_kit_url=os.getenv("DASHBOARD_IPFS_KIT_URL", "http://localhost:9090"),
            
            data_collection_interval=int(os.getenv("DASHBOARD_DATA_COLLECTION_INTERVAL", "10")),
            metrics_update_interval=int(os.getenv("DASHBOARD_METRICS_UPDATE_INTERVAL", "5")),
            max_data_points=int(os.getenv("DASHBOARD_MAX_DATA_POINTS", "1000")),
            data_retention_hours=int(os.getenv("DASHBOARD_DATA_RETENTION_HOURS", "24")),
            
            alert_enabled=os.getenv("DASHBOARD_ALERT_ENABLED", "true").lower() == "true",
            alert_cooldown_minutes=int(os.getenv("DASHBOARD_ALERT_COOLDOWN_MINUTES", "5")),
            
            data_storage_type=os.getenv("DASHBOARD_STORAGE_TYPE", "memory")
        )
    
    @classmethod
    def from_file(cls, config_path: str) -> 'DashboardConfig':
        """Create configuration from YAML file."""
        try:
            import yaml
            
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Extract dashboard section if it exists
            dashboard_config = config_data.get("dashboard", config_data)
            
            return cls(**dashboard_config)
            
        except ImportError:
            raise ImportError("PyYAML is required to load configuration from file")
        except Exception as e:
            raise ValueError(f"Failed to load configuration from {config_path}: {e}")
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'DashboardConfig':
        """Create configuration from dictionary."""
        return cls(**config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "debug": self.debug,
            "dashboard_path": self.dashboard_path,
            "static_path": self.static_path,
            "api_path": self.api_path,
            "mcp_server_url": self.mcp_server_url,
            "ipfs_kit_url": self.ipfs_kit_url,
            "data_collection_interval": self.data_collection_interval,
            "metrics_update_interval": self.metrics_update_interval,
            "max_data_points": self.max_data_points,
            "data_retention_hours": self.data_retention_hours,
            "mcp_metrics_endpoint": self.mcp_metrics_endpoint,
            "mcp_health_endpoint": self.mcp_health_endpoint,
            "ipfs_kit_enabled": self.ipfs_kit_enabled,
            "prometheus_endpoint": self.prometheus_endpoint,
            "prometheus_enabled": self.prometheus_enabled,
            "enable_real_time_updates": self.enable_real_time_updates,
            "enable_historical_data": self.enable_historical_data,
            "enable_alerts": self.enable_alerts,
            "enable_charts": self.enable_charts,
            "alert_enabled": self.alert_enabled,
            "alert_cooldown_minutes": self.alert_cooldown_minutes,
            "health_thresholds": self.health_thresholds,
            "data_storage_type": self.data_storage_type,
            "data_storage_config": self.data_storage_config,
        }
    
    def get_mcp_server_url(self) -> str:
        """Get the full MCP server URL."""
        return self.mcp_server_url
    
    def get_dashboard_url(self) -> str:
        """Get the dashboard URL."""
        return f"http://{self.host}:{self.port}{self.dashboard_path}"
    
    def validate(self) -> None:
        """Validate configuration settings."""
        errors = []
        
        # Validate port numbers
        if not (1 <= self.port <= 65535):
            errors.append(f"Invalid dashboard port: {self.port}")
        
        # Validate URLs
        try:
            from urllib.parse import urlparse
            mcp_parsed = urlparse(self.mcp_server_url)
            if not mcp_parsed.scheme or not mcp_parsed.netloc:
                errors.append(f"Invalid MCP server URL: {self.mcp_server_url}")
            
            ipfs_parsed = urlparse(self.ipfs_kit_url)
            if not ipfs_parsed.scheme or not ipfs_parsed.netloc:
                errors.append(f"Invalid IPFS Kit URL: {self.ipfs_kit_url}")
        except Exception as e:
            errors.append(f"URL validation error: {e}")
        
        # Validate intervals
        if self.metrics_update_interval <= 0:
            errors.append(f"Invalid metrics update interval: {self.metrics_update_interval}")
            
        if self.data_collection_interval <= 0:
            errors.append(f"Invalid data collection interval: {self.data_collection_interval}")
        
        # Validate paths
        if not self.dashboard_path.startswith("/"):
            errors.append(f"Dashboard path must start with '/': {self.dashboard_path}")
        
        if not self.api_path.startswith("/"):
            errors.append(f"API path must start with '/': {self.api_path}")
        
        if not self.static_path.startswith("/"):
            errors.append(f"Static path must start with '/': {self.static_path}")
        
        # Validate data retention
        if self.max_data_points <= 0:
            errors.append(f"Invalid max data points: {self.max_data_points}")
            
        if self.data_retention_hours <= 0:
            errors.append(f"Invalid data retention hours: {self.data_retention_hours}")
        
        # Validate health thresholds
        for metric, threshold in self.health_thresholds.items():
            if not (0 <= threshold <= 100) and 'percent' in metric:
                errors.append(f"Invalid threshold for {metric}: {threshold} (should be 0-100)")
        
        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors))


def _parse_storage_config(config_str: str) -> Dict[str, Any]:
    """Parse storage configuration from string."""
    try:
        import json
        return json.loads(config_str)
    except json.JSONDecodeError:
        return {}


def _parse_auth_config(config_str: str) -> Dict[str, Any]:
    """Parse auth configuration from string."""
    try:
        import json
        return json.loads(config_str)
    except json.JSONDecodeError:
        return {}


# Default configuration instance
default_config = DashboardConfig()
