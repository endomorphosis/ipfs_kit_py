#!/usr/bin/env python3
"""
Enhanced Dashboard Runner

This script runs the enhanced MCP dashboard with full integration to the IPFS Kit
system, backend management, bucket operations, VFS, and Parquet analytics.

Usage:
    python run_enhanced_dashboard.py [--port PORT] [--host HOST] [--mcp-url URL]
"""

import anyio
import argparse
import logging
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "ipfs_kit_py"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to run the enhanced dashboard."""
    parser = argparse.ArgumentParser(description='Enhanced MCP Dashboard')
    parser.add_argument('--port', type=int, default=8083, help='Dashboard port (default: 8083)')
    parser.add_argument('--host', default='127.0.0.1', help='Dashboard host (default: 127.0.0.1)')
    parser.add_argument('--mcp-url', default='http://127.0.0.1:8001', help='MCP server URL (default: http://127.0.0.1:8001)')
    parser.add_argument('--metadata-path', default='~/.ipfs_kit', help='Metadata path (default: ~/.ipfs_kit)')
    
    args = parser.parse_args()
    
    try:
        # Import the enhanced dashboard
        from ipfs_kit_py.mcp.enhanced_dashboard import EnhancedMCPDashboard
        
        # Create and configure the dashboard
        dashboard = EnhancedMCPDashboard(
            dashboard_host=args.host,
            dashboard_port=args.port,
            mcp_server_url=args.mcp_url,
            metadata_path=str(Path(args.metadata_path).expanduser())
        )
        
        logger.info("="*80)
        logger.info("ENHANCED MCP DASHBOARD - COMPREHENSIVE IPFS KIT INTERFACE")
        logger.info("="*80)
        logger.info("")
        logger.info("🚀 Features enabled:")
        logger.info("   • Real-time IPFS daemon monitoring and control")
        logger.info("   • Backend health monitoring (S3, GitHub, HuggingFace, FTP, SSH, Storacha)")
        logger.info("   • Bucket management with VFS integration")
        logger.info("   • Pin management with content addressing")
        logger.info("   • VFS operations and browsing")
        logger.info("   • Parquet/Arrow analytics integration")
        logger.info("   • Conflict-free content addressed operations")
        logger.info("   • Real-time WebSocket updates")
        logger.info("   • Configuration management with widgets")
        logger.info("   • Comprehensive logging and metrics")
        logger.info("")
        logger.info(f"🌐 Dashboard URL: http://{args.host}:{args.port}")
        logger.info(f"🔗 MCP Server: {args.mcp_url}")
        logger.info(f"📁 Metadata Path: {args.metadata_path}")
        logger.info("")
        logger.info("Available endpoints:")
        logger.info("   • / - Main dashboard interface")
        logger.info("   • /daemon - Daemon control and monitoring")
        logger.info("   • /backends - Backend management")
        logger.info("   • /buckets - Bucket operations")
        logger.info("   • /pins - Pin management")
        logger.info("   • /vfs - Virtual filesystem browser")
        logger.info("   • /parquet - Analytics and data operations")
        logger.info("   • /api/* - REST API endpoints")
        logger.info("   • /ws - WebSocket for real-time updates")
        logger.info("")
        logger.info("Press Ctrl+C to stop the dashboard")
        logger.info("="*80)
        
        # Run the dashboard
        await dashboard.run()
        
    except ImportError as e:
        logger.error("Failed to import dashboard components:")
        logger.error(f"  {e}")
        logger.error("")
        logger.error("Please ensure the ipfs_kit_py package is properly installed.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Error running dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    anyio.run(main)
