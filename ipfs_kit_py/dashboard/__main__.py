#!/usr/bin/env python3
"""
Dashboard CLI Module

Command-line interface for the IPFS Kit monitoring dashboard.
Provides commands to start, stop, and configure the dashboard server.
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from .config import DashboardConfig
from .web_dashboard import WebDashboard

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DashboardCLI:
    """Command-line interface for the dashboard."""
    
    def __init__(self):
        self.dashboard: Optional[WebDashboard] = None
        self.shutdown_event = asyncio.Event()
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start_dashboard(self, args):
        """Start the dashboard server."""
        try:
            # Load configuration
            if args.config:
                config = DashboardConfig.from_file(args.config)
            else:
                config = DashboardConfig.from_env()
            
            # Override with command-line arguments
            if args.host:
                config.host = args.host
            if args.port:
                config.port = args.port
            if args.debug:
                config.debug = True
            if args.mcp_url:
                config.mcp_server_url = args.mcp_url
            if args.ipfs_url:
                config.ipfs_kit_url = args.ipfs_url
            
            # Validate configuration
            config.validate()
            
            # Create and start dashboard
            self.dashboard = WebDashboard(config)
            
            logger.info("Starting IPFS Kit Dashboard...")
            logger.info(f"Dashboard URL: http://{config.host}:{config.port}{config.dashboard_path}")
            logger.info(f"API URL: http://{config.host}:{config.port}{config.api_path}")
            
            # Setup signal handlers
            self.setup_signal_handlers()
            
            # Start the server
            server_task = asyncio.create_task(
                self.dashboard.start(config.host, config.port)
            )
            
            # Wait for shutdown signal
            shutdown_task = asyncio.create_task(self.shutdown_event.wait())
            
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [server_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
        except Exception as e:
            logger.error(f"Failed to start dashboard: {e}")
            return 1
        finally:
            if self.dashboard:
                await self.dashboard.stop()
        
        return 0
    
    def validate_config(self, args):
        """Validate dashboard configuration."""
        try:
            if args.config:
                config = DashboardConfig.from_file(args.config)
            else:
                config = DashboardConfig.from_env()
            
            config.validate()
            
            print("✓ Configuration is valid")
            print(f"  Host: {config.host}")
            print(f"  Port: {config.port}")
            print(f"  Dashboard Path: {config.dashboard_path}")
            print(f"  API Path: {config.api_path}")
            print(f"  MCP Server URL: {config.mcp_server_url}")
            print(f"  IPFS Kit URL: {config.ipfs_kit_url}")
            print(f"  Debug Mode: {config.debug}")
            
            return 0
            
        except Exception as e:
            print(f"✗ Configuration validation failed: {e}")
            return 1
    
    def show_status(self, args):
        """Show dashboard status."""
        # This would typically check if the dashboard is running
        # For now, just show configuration
        return self.validate_config(args)
    
    def create_config(self, args):
        """Create a sample configuration file."""
        try:
            config = DashboardConfig()
            config_path = Path(args.output or "dashboard_config.yaml")
            
            with open(config_path, 'w') as f:
                f.write(f"""# IPFS Kit Dashboard Configuration
# Generated configuration file

# Server settings
host: "{config.host}"
port: {config.port}

# URL paths
dashboard_path: "{config.dashboard_path}"
api_path: "{config.api_path}"
static_path: "{config.static_path}"

# External service URLs
mcp_server_url: "{config.mcp_server_url}"
ipfs_kit_url: "{config.ipfs_kit_url}"

# Update intervals (seconds)
data_collection_interval: {config.data_collection_interval}
metrics_update_interval: {config.metrics_update_interval}

# Data retention
max_data_points: {config.max_data_points}
data_retention_hours: {config.data_retention_hours}

# Alerting
alert_enabled: {config.alert_enabled}
alert_cooldown_minutes: {config.alert_cooldown_minutes}

# Health monitoring thresholds
health_thresholds:
  cpu_usage_percent: {config.health_thresholds['cpu_usage_percent']}
  memory_usage_percent: {config.health_thresholds['memory_usage_percent']}
  disk_usage_percent: {config.health_thresholds['disk_usage_percent']}
  response_time_seconds: {config.health_thresholds['response_time_seconds']}

# Debug mode
debug: {config.debug}
""")
            
            print(f"✓ Created configuration file: {config_path}")
            print("  Edit the file to customize settings, then run:")
            print(f"  python -m dashboard start --config {config_path}")
            
            return 0
            
        except Exception as e:
            print(f"✗ Failed to create configuration: {e}")
            return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="IPFS Kit Dashboard - Monitoring and analytics interface"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start the dashboard server')
    start_parser.add_argument(
        '--host',
        default=None,
        help='Server host address (default: from config/env)'
    )
    start_parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='Server port (default: from config/env)'
    )
    start_parser.add_argument(
        '--config',
        help='Configuration file path (YAML)'
    )
    start_parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    start_parser.add_argument(
        '--mcp-url',
        help='MCP server URL override'
    )
    start_parser.add_argument(
        '--ipfs-url',
        help='IPFS Kit URL override'
    )
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration')
    validate_parser.add_argument(
        '--config',
        help='Configuration file path (YAML)'
    )
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show dashboard status')
    status_parser.add_argument(
        '--config',
        help='Configuration file path (YAML)'
    )
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Create sample configuration')
    config_parser.add_argument(
        '--output',
        help='Output file path (default: dashboard_config.yaml)'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    cli = DashboardCLI()
    
    try:
        if args.command == 'start':
            return asyncio.run(cli.start_dashboard(args))
        elif args.command == 'validate':
            return cli.validate_config(args)
        elif args.command == 'status':
            return cli.show_status(args)
        elif args.command == 'config':
            return cli.create_config(args)
        else:
            parser.print_help()
            return 1
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
