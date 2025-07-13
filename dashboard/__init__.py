"""
Dashboard Module for IPFS Kit

Centralized monitoring and analytics dashboard that provides:
- Real-time metrics visualization
- System health monitoring
- Performance analytics
- Virtual filesystem insights
- MCP server telemetry
- Interactive web interface with WebSocket updates
"""

__version__ = "1.0.0"
__author__ = "IPFS Kit Team"

# Import components with error handling
try:
    from .config import DashboardConfig
    CONFIG_AVAILABLE = True
except ImportError as e:
    CONFIG_AVAILABLE = False
    _config_error = e

try:
    from .data_collector import DataCollector
    DATA_COLLECTOR_AVAILABLE = True
except ImportError as e:
    DATA_COLLECTOR_AVAILABLE = False
    _data_collector_error = e

try:
    from .metrics_aggregator import MetricsAggregator
    METRICS_AGGREGATOR_AVAILABLE = True
except ImportError as e:
    METRICS_AGGREGATOR_AVAILABLE = False
    _metrics_aggregator_error = e

try:
    from .web_dashboard import WebDashboard
    WEB_DASHBOARD_AVAILABLE = True
except ImportError as e:
    WEB_DASHBOARD_AVAILABLE = False
    _web_dashboard_error = e

__all__ = []

# Add available components to __all__
if CONFIG_AVAILABLE:
    __all__.append('DashboardConfig')

if DATA_COLLECTOR_AVAILABLE:
    __all__.append('DataCollector')

if METRICS_AGGREGATOR_AVAILABLE:
    __all__.append('MetricsAggregator')

if WEB_DASHBOARD_AVAILABLE:
    __all__.append('WebDashboard')


def get_import_status():
    """Get the status of component imports."""
    return {
        'config': {
            'available': CONFIG_AVAILABLE,
            'error': _config_error if not CONFIG_AVAILABLE else None
        },
        'data_collector': {
            'available': DATA_COLLECTOR_AVAILABLE,
            'error': _data_collector_error if not DATA_COLLECTOR_AVAILABLE else None
        },
        'metrics_aggregator': {
            'available': METRICS_AGGREGATOR_AVAILABLE,
            'error': _metrics_aggregator_error if not METRICS_AGGREGATOR_AVAILABLE else None
        },
        'web_dashboard': {
            'available': WEB_DASHBOARD_AVAILABLE,
            'error': _web_dashboard_error if not WEB_DASHBOARD_AVAILABLE else None
        }
    }


def check_dependencies():
    """Check if all required dependencies are available."""
    import importlib
    
    required_packages = [
        'fastapi',
        'uvicorn', 
        'jinja2',
        'aiohttp',
        'psutil',
        'yaml'
    ]
    
    missing = []
    for package in required_packages:
        try:
            importlib.import_module(package)
        except ImportError:
            missing.append(package)
    
    return {
        'all_available': len(missing) == 0,
        'missing_packages': missing,
        'required_packages': required_packages
    }


# Convenience functions for creating dashboard components
def create_config(**kwargs):
    """Create a dashboard configuration."""
    if not CONFIG_AVAILABLE:
        raise ImportError(f"DashboardConfig not available: {_config_error}")
    return DashboardConfig(**kwargs)


def create_dashboard(config=None, **kwargs):
    """Create a dashboard instance."""
    if not WEB_DASHBOARD_AVAILABLE:
        raise ImportError(f"WebDashboard not available: {_web_dashboard_error}")
    
    if config is None:
        if not CONFIG_AVAILABLE:
            raise ImportError(f"DashboardConfig not available: {_config_error}")
        config = DashboardConfig(**kwargs)
    
    return WebDashboard(config)
