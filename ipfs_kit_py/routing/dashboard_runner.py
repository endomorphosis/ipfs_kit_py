"""
Routing Dashboard Runner

This standalone module allows running the routing dashboard outside
of the MCP server context, providing direct access to the dashboard
from the ipfs_kit_py package.
"""

import os
import sys
import argparse
import asyncio
import logging
import uvicorn
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ipfs_kit_py.routing.dashboard_runner')

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Start the Optimized Routing Dashboard'
    )
    parser.add_argument(
        '--host', type=str, default='127.0.0.1',
        help='Host to bind the dashboard server to'
    )
    parser.add_argument(
        '--port', type=int, default=8050,
        help='Port to bind the dashboard server to'
    )
    parser.add_argument(
        '--config', type=str, default=None,
        help='Path to configuration file'
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='Enable debug mode'
    )
    return parser.parse_args()

async def main():
    """Main entry point for the dashboard runner."""
    args = parse_args()
    
    try:
        # Import dashboard components
        from ipfs_kit_py.routing.dashboard import (
            create_dashboard_app, DashboardSettings
        )
        
        # Load configuration if provided
        config = {}
        if args.config and os.path.exists(args.config):
            import json
            with open(args.config, 'r') as f:
                config = json.load(f)
        
        # Create dashboard settings
        settings = DashboardSettings(
            debug=args.debug,
            routing_data_dir=config.get('routing_data_dir', None),
            **config.get('dashboard', {})
        )
        
        # Create dashboard app
        app = create_dashboard_app(settings)
        
        # Start the dashboard
        config = uvicorn.Config(
            app=app,
            host=args.host,
            port=args.port,
            log_level="debug" if args.debug else "info",
            reload=args.debug
        )
        server = uvicorn.Server(config)
        logger.info(f"Starting routing dashboard on http://{args.host}:{args.port}")
        await server.serve()
        
    except Exception as e:
        logger.error(f"Error starting dashboard: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)