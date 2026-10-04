#!/usr/bin/env python3
"""
Unified Comprehensive Dashboard Startup Script

This script provides an easy way to start the integrated dashboard
with all comprehensive features.
"""

import argparse
import sys
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


def main():
    """Main startup function."""
    parser = argparse.ArgumentParser(
        description="IPFS Kit - Unified Comprehensive Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Start with default settings (port 8080)
  %(prog)s --port 8090              # Start on port 8090
  %(prog)s --host 0.0.0.0           # Bind to all interfaces
  %(prog)s --debug                  # Enable debug mode
  %(prog)s --no-websocket           # Disable WebSocket support
  %(prog)s --data-dir ~/my_ipfs     # Use custom data directory

Features:
  • Service Management & Monitoring
  • Backend Health & Management  
  • Peer Management
  • Advanced Analytics & Monitoring
  • Real-time Log Streaming
  • Configuration Management
  • WebSocket Real-time Updates
  • MCP JSON-RPC Protocol Support
  • Bucket VFS Operations
  • Light Initialization with Fallbacks
        """,
    )

    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to (default: 8080)")
    parser.add_argument(
        "--data-dir",
        default="~/.ipfs_kit",
        help="Data directory for state management (default: ~/.ipfs_kit)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-websocket", action="store_true", help="Disable WebSocket support")
    parser.add_argument("--no-log-streaming", action="store_true", help="Disable log streaming")
    parser.add_argument(
        "--update-interval", type=int, default=3, help="Update interval in seconds (default: 3)"
    )

    args = parser.parse_args()

    # Print startup banner
    print("🚀 IPFS Kit - Unified Comprehensive Dashboard")
    print("=" * 60)
    print("🎯 All comprehensive features integrated!")
    print()
    print(f"🌐 Dashboard URL: http://{args.host}:{args.port}/")
    print(f"📡 MCP Protocol: http://{args.host}:{args.port}/mcp/")
    if not args.no_websocket:
        print(f"🔌 WebSocket: ws://{args.host}:{args.port}/ws")
    print(f"📁 Data Directory: {args.data_dir}")
    print()
    print("✅ Features Available:")
    print("  • Service Management & Monitoring")
    print("  • Backend Health & Management")
    print("  • Peer Management")
    print("  • Advanced Analytics & Monitoring")
    print("  • Real-time Log Streaming")
    print("  • Configuration Management")
    if not args.no_websocket:
        print("  • WebSocket Real-time Updates")
    print("  • MCP JSON-RPC Protocol Support")
    print("  • Bucket VFS Operations")
    print("  • Light Initialization with Fallbacks")
    print()

    # Import and initialize dashboard
    try:
        from ipfs_kit_py.dashboard.unified_comprehensive_dashboard import (
            UnifiedComprehensiveDashboard,
        )

        config = {
            "host": args.host,
            "port": args.port,
            "data_dir": args.data_dir,
            "debug": args.debug,
            "websocket_enabled": not args.no_websocket,
            "log_streaming": not args.no_log_streaming,
            "update_interval": args.update_interval,
        }

        print("🔧 Initializing dashboard...")
        dashboard = UnifiedComprehensiveDashboard(config)

        print("✅ Dashboard initialized successfully!")
        print()
        print("🚀 Starting server...")
        print("🛑 Press Ctrl+C to stop")
        print("=" * 60)

        # Start the dashboard
        dashboard.run()

    except ImportError as e:
        print(f"❌ Failed to import dashboard: {e}")
        print("💡 Make sure you're in the correct directory and all dependencies are installed")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        import traceback

        if args.debug:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
