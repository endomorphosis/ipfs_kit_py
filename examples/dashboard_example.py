#!/usr/bin/env python3
"""
Dashboard Example and Demo Script

Demonstrates how to use the IPFS Kit Dashboard module.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.config import DashboardConfig
from dashboard.web_dashboard import WebDashboard

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_dashboard_demo():
    """Run a dashboard demonstration."""
    print("🚀 IPFS Kit Dashboard Demo")
    print("=" * 50)
    
    try:
        # Create configuration
        config = DashboardConfig(
            host="127.0.0.1",
            port=8080,
            debug=True,
            # Use demo URLs if real services aren't available
            mcp_server_url="http://localhost:8000",
            ipfs_kit_url="http://localhost:9090",
            data_collection_interval=5,  # More frequent updates for demo
            metrics_update_interval=2
        )
        
        print(f"📊 Dashboard Configuration:")
        print(f"   Host: {config.host}")
        print(f"   Port: {config.port}")
        print(f"   Dashboard URL: http://{config.host}:{config.port}{config.dashboard_path}")
        print(f"   API URL: http://{config.host}:{config.port}{config.api_path}")
        print(f"   MCP Server: {config.mcp_server_url}")
        print(f"   IPFS Kit: {config.ipfs_kit_url}")
        print()
        
        # Validate configuration
        config.validate()
        print("✅ Configuration validated successfully")
        
        # Create dashboard
        dashboard = WebDashboard(config)
        print("✅ Dashboard instance created")
        
        print("\n🌟 Starting Dashboard Server...")
        print("   Press Ctrl+C to stop the server")
        print(f"   Open your browser to: http://{config.host}:{config.port}{config.dashboard_path}")
        print()
        
        # Start the dashboard
        await dashboard.start()
        
    except KeyboardInterrupt:
        print("\n🛑 Dashboard demo stopped by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\n❌ Demo failed: {e}")
    finally:
        if 'dashboard' in locals():
            await dashboard.stop()


def show_dashboard_info():
    """Show information about the dashboard module."""
    print("📋 IPFS Kit Dashboard Information")
    print("=" * 50)
    
    print("🎯 Purpose:")
    print("   Centralized monitoring and analytics dashboard for IPFS Kit")
    print("   Provides real-time visualization of system performance,")
    print("   MCP server metrics, and virtual filesystem behavior.")
    print()
    
    print("🔧 Features:")
    print("   • Real-time WebSocket updates")
    print("   • Interactive charts and visualizations")
    print("   • Health monitoring and alerting")
    print("   • Performance analytics")
    print("   • Virtual filesystem analytics")
    print("   • REST API for metric access")
    print("   • Responsive web interface")
    print()
    
    print("📊 Data Sources:")
    print("   • MCP Server (/metrics and /health endpoints)")
    print("   • IPFS Kit Prometheus metrics")
    print("   • System resource monitoring (CPU, Memory, Disk)")
    print("   • Virtual filesystem operation tracking")
    print()
    
    print("🚀 Quick Start:")
    print("   1. Install dependencies: pip install fastapi uvicorn jinja2")
    print("   2. Run demo: python dashboard_example.py")
    print("   3. Or use CLI: python -m dashboard start")
    print("   4. Open browser to http://localhost:8080/dashboard")
    print()
    
    print("⚙️  Configuration:")
    print("   • Environment variables (DASHBOARD_HOST, DASHBOARD_PORT, etc.)")
    print("   • YAML configuration file")
    print("   • Command-line arguments")
    print("   • Create sample config: python -m dashboard config")
    print()


def check_dependencies():
    """Check if required dependencies are available."""
    print("🔍 Checking Dependencies...")
    print("-" * 30)
    
    required_packages = [
        ('fastapi', 'FastAPI web framework'),
        ('uvicorn', 'ASGI server'),
        ('jinja2', 'Template engine'),
        ('aiohttp', 'HTTP client'),
        ('psutil', 'System monitoring'),
        ('pyyaml', 'YAML configuration')
    ]
    
    missing_packages = []
    
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"✅ {package:<10} - {description}")
        except ImportError:
            print(f"❌ {package:<10} - {description} (MISSING)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📦 Install missing packages:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    else:
        print("\n✅ All dependencies are available!")
        return True


def show_usage_examples():
    """Show usage examples."""
    print("💡 Usage Examples")
    print("=" * 50)
    
    print("🖥️  Command Line Interface:")
    print("   # Start dashboard with default settings")
    print("   python -m dashboard start")
    print()
    print("   # Start with custom host and port")
    print("   python -m dashboard start --host 0.0.0.0 --port 3000")
    print()
    print("   # Start with configuration file")
    print("   python -m dashboard start --config my_config.yaml")
    print()
    print("   # Create sample configuration")
    print("   python -m dashboard config --output my_config.yaml")
    print()
    print("   # Validate configuration")
    print("   python -m dashboard validate --config my_config.yaml")
    print()
    
    print("🐍 Python API:")
    print("   ```python")
    print("   from dashboard.config import DashboardConfig")
    print("   from dashboard.web_dashboard import WebDashboard")
    print("   ")
    print("   # Create configuration")
    print("   config = DashboardConfig(host='0.0.0.0', port=8080)")
    print("   ")
    print("   # Create and start dashboard")
    print("   dashboard = WebDashboard(config)")
    print("   await dashboard.start()")
    print("   ```")
    print()
    
    print("🌐 Web Interface URLs:")
    print("   • Main Dashboard:     http://localhost:8080/dashboard")
    print("   • Metrics View:       http://localhost:8080/dashboard/metrics")
    print("   • Health Status:      http://localhost:8080/dashboard/health")
    print("   • VFS Analytics:      http://localhost:8080/dashboard/vfs")
    print("   • API Summary:        http://localhost:8080/dashboard/api/summary")
    print("   • WebSocket Updates:  ws://localhost:8080/dashboard/ws")
    print()


def main():
    """Main entry point for the dashboard example."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'info':
            show_dashboard_info()
        elif command == 'check':
            check_dependencies()
        elif command == 'examples':
            show_usage_examples()
        elif command == 'demo':
            if not check_dependencies():
                print("\n❌ Cannot run demo - missing dependencies")
                return 1
            asyncio.run(run_dashboard_demo())
        else:
            print(f"Unknown command: {command}")
            print("Available commands: info, check, examples, demo")
            return 1
    else:
        # Default: show info and run demo
        show_dashboard_info()
        
        if check_dependencies():
            print("\n" + "=" * 50)
            response = input("Would you like to run the dashboard demo? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                asyncio.run(run_dashboard_demo())
        else:
            print("\n❌ Install missing dependencies to run the demo")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
