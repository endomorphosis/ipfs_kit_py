"""
Standalone MCP Manager for CLI operations
"""

import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, Any


class StandaloneMCPManager:
    """Standalone MCP manager that doesn't trigger problematic imports."""
    
    def __init__(self):
        self.server_process = None
        self.dashboard_process = None
        
    def start_server(self, host: str = "127.0.0.1", port: int = 8000, debug: bool = False):
        """Start the MCP server with integrated dashboard."""
        print(f"🚀 Starting MCP server with integrated dashboard on {host}:{port}")
        print(f"🔧 Debug mode: {debug}")
        
        # Use the comprehensive dashboard which already has MCP integration
        mcp_server_path = None
        possible_paths = [
            # The comprehensive dashboard IS the MCP server with dashboard
            Path(__file__).parent / "deprecated_dashboards" / "comprehensive_mcp_dashboard.py",
            Path(__file__).parent.parent / "deprecated_dashboards" / "comprehensive_mcp_dashboard.py",
            Path(__file__).parent.parent.parent / "deprecated_dashboards" / "comprehensive_mcp_dashboard.py"
        ]
        
        for path in possible_paths:
            if path.exists():
                mcp_server_path = path
                break
        
        if mcp_server_path:
            print(f"✅ Found integrated MCP server + dashboard at: {mcp_server_path}")
            
            # Start the integrated MCP server + dashboard
            cmd = [
                sys.executable, 
                str(mcp_server_path),
                "--host", host,
                "--port", str(port)
            ]
            
            if debug:
                cmd.append("--debug")
            
            print(f"🔧 Server command: {' '.join(cmd)}")
            print(f"📊 MCP Server + Dashboard will be available at: http://{host}:{port}")
            print(f"🔧 MCP tools accessible via: http://{host}:{port}/api/mcp/tools")
            print(f"🔧 Dashboard uses MCP tools to provide data for rendering")
            
            try:
                # Start the integrated MCP server + dashboard
                self.server_process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                print(f"✅ Integrated MCP server + dashboard started with PID: {self.server_process.pid}")
                return True
            except Exception as e:
                print(f"❌ Failed to start integrated MCP server subprocess: {e}")
                return False
        else:
            print(f"❌ Integrated MCP server not found at expected locations")
            return False
    
    def start_dashboard_fallback(self, host: str = "127.0.0.1", port: int = 8080):
        """Fallback: Start the comprehensive dashboard only."""
        # Find the comprehensive dashboard
        dashboard_path = None
        possible_paths = [
            Path(__file__).parent / "deprecated_dashboards" / "comprehensive_mcp_dashboard.py",
            Path(__file__).parent.parent / "deprecated_dashboards" / "comprehensive_mcp_dashboard.py",
            Path(__file__).parent.parent.parent / "deprecated_dashboards" / "comprehensive_mcp_dashboard.py"
        ]
        
        for path in possible_paths:
            if path.exists():
                dashboard_path = path
                break
        
        if dashboard_path:
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
            
            try:
                # Actually start the dashboard
                self.dashboard_process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                print(f"✅ Dashboard started with PID: {self.dashboard_process.pid}")
                return True
            except Exception as e:
                print(f"❌ Failed to start dashboard subprocess: {e}")
                return False
        else:
            print(f"❌ Dashboard not found at expected locations")
            return False
    
    def start_dashboard(self, host: str = "127.0.0.1", port: int = 8080):
        """Start the MCP dashboard (deprecated - use start_server for integrated mode)."""
        print(f"⚠️  Note: Dashboard is now integrated with MCP server")
        print(f"💡 Use 'ipfs-kit mcp start' for unified server + dashboard on the same port")
        print(f"� Starting dashboard-only mode on {host}:{port}...")
        
        return self.start_dashboard_fallback(host, port)
    
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
