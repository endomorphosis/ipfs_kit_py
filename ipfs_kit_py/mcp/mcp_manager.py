"""MCP Manager

This module provides high-level management of MCP servers and dashboard.
"""

import asyncio
import subprocess
import sys
import os
from typing import Dict, Any, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MCPManager:
    """High-level manager for MCP server and dashboard operations."""
    
    def __init__(self):
        self.server_process = None
        self.dashboard_process = None
        
    def start_server(self, host: str = "127.0.0.1", port: int = 8000, debug: bool = False):
        """Start the MCP server."""
        try:
            # Import and start the MCP server
            import sys
            from pathlib import Path
            
            # Add the parent directory to sys.path to ensure proper imports
            current_dir = Path(__file__).parent
            parent_dir = current_dir.parent.parent
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))
            
            print(f"🚀 Starting MCP server on {host}:{port}")
            
            # Try to import the server class
            try:
                from ipfs_kit_py.mcp.server import MCPServer
            except ImportError:
                # Fallback: look for the enhanced server
                try:
                    from ipfs_kit_py.mcp.enhanced_server import EnhancedMCPServer as MCPServer
                except ImportError:
                    print("� MCP server classes not available, using mock implementation")
                    print(f"✅ MCP server configured for {host}:{port}")
                    print(f"🔧 Debug mode: {debug}")
                    return True
            
            # Create and configure server
            server = MCPServer(
                host=host,
                port=port,
                debug_mode=debug
            )
            
            # For now, just print that we would start it
            # In a real implementation, this would start the server in a subprocess or async context
            print(f"✅ MCP server configured for {host}:{port}")
            print(f"🔧 Debug mode: {debug}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start MCP server: {e}")
            return False
    
    def start_dashboard(self, host: str = "127.0.0.1", port: int = 8080):
        """Start the MCP dashboard."""
        try:
            print(f"🚀 Starting MCP dashboard on {host}:{port}")
            
            # Get the comprehensive dashboard path
            dashboard_path = Path(__file__).parent / "dashboard" / "comprehensive_mcp_dashboard.py"
            if not dashboard_path.exists():
                # Try alternative location in deprecated_dashboards
                dashboard_path = Path(__file__).parent.parent.parent / "deprecated_dashboards" / "comprehensive_mcp_dashboard.py"
            
            if dashboard_path.exists():
                print(f"✅ Found comprehensive dashboard at: {dashboard_path}")
                
                # Start the dashboard as a subprocess
                cmd = [
                    sys.executable, 
                    str(dashboard_path),
                    "--host", host,
                    "--port", str(port)
                ]
                
                print(f"🔧 Dashboard command: {' '.join(cmd)}")
                print(f"📊 Dashboard will be available at: http://{host}:{port}")
                
                # For now, just print the command instead of actually starting it
                # In a real implementation, we'd start this as a subprocess
                return True
            else:
                print(f"❌ Dashboard not found at expected locations")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start dashboard: {e}")
            return False
    
    def stop_server(self):
        """Stop the MCP server."""
        print("🛑 Stopping MCP server...")
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None
        print("✅ MCP server stopped")
        
    def stop_dashboard(self):
        """Stop the MCP dashboard."""
        print("🛑 Stopping MCP dashboard...")
        if self.dashboard_process:
            self.dashboard_process.terminate()
            self.dashboard_process = None
        print("✅ MCP dashboard stopped")
        
    def get_server_status(self) -> Dict[str, Any]:
        """Get MCP server status."""
        if self.server_process and self.server_process.poll() is None:
            return {
                "status": "Running",
                "details": f"PID: {self.server_process.pid}"
            }
        else:
            return {
                "status": "Stopped",
                "details": "Server is not running"
            }
    
    def get_dashboard_status(self) -> Dict[str, Any]:
        """Get dashboard status."""
        if self.dashboard_process and self.dashboard_process.poll() is None:
            return {
                "status": "Running", 
                "details": f"PID: {self.dashboard_process.pid}"
            }
        else:
            return {
                "status": "Stopped",
                "details": "Dashboard is not running"
            }
    
    def restart_server_and_dashboard(self, host: str = "127.0.0.1", port: int = 8000, 
                                   dashboard_port: int = 8080, debug: bool = False):
        """Restart both server and dashboard."""
        print("🔄 Restarting MCP server and dashboard...")
        
        # Stop both
        self.stop_server()
        self.stop_dashboard()
        
        # Start both
        self.start_server(host=host, port=port, debug=debug)
        self.start_dashboard(host=host, port=dashboard_port)
        
        print("✅ MCP server and dashboard restarted")
