#!/usr/bin/env python3
"""
VFS MCP Health Monitor

This script monitors the health of the MCP server with virtual filesystem integration.
It periodically checks the server status, ensures key components are working, and 
can automatically restart the server if issues are detected.

Run this script in the background to ensure continuous operation of your VFS-MCP server.
"""

import os
import sys
import json
import logging
import asyncio
import time
import argparse
import subprocess
import signal
import requests
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("vfs_health_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("vfs-health-monitor")

# Default settings
DEFAULT_MCP_URL = "http://localhost:3000"
DEFAULT_CHECK_INTERVAL = 30  # seconds
DEFAULT_RESTART_THRESHOLD = 3  # failures before restart
DEFAULT_RESTART_COMMAND = "./restart_mcp_with_vfs.sh"
DEFAULT_PID_FILE = "direct_mcp_server.pid"

class VFSHealthMonitor:
    """Monitor health of MCP server with VFS integration"""
    
    def __init__(self, 
                 mcp_url: str = DEFAULT_MCP_URL,
                 check_interval: int = DEFAULT_CHECK_INTERVAL,
                 restart_threshold: int = DEFAULT_RESTART_THRESHOLD,
                 restart_command: str = DEFAULT_RESTART_COMMAND,
                 pid_file: str = DEFAULT_PID_FILE,
                 auto_restart: bool = True):
        """Initialize health monitor"""
        self.mcp_url = mcp_url
        self.check_interval = check_interval
        self.restart_threshold = restart_threshold
        self.restart_command = restart_command
        self.pid_file = pid_file
        self.auto_restart = auto_restart
        
        self.last_successful_check = None
        self.failure_count = 0
        self.restart_count = 0
        self.total_checks = 0
        self.running = True
        self.tool_availability = {}
        
        logger.info(f"VFS Health Monitor initialized with URL: {mcp_url}")
        logger.info(f"Check interval: {check_interval}s, Restart threshold: {restart_threshold}")
        logger.info(f"Auto-restart: {'Enabled' if auto_restart else 'Disabled'}")
    
    async def check_server_health(self) -> Dict[str, Any]:
        """Check server health and return status"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "server_up": False,
            "health_check_passed": False,
            "jsonrpc_working": False,
            "vfs_tools_available": False,
            "tools_responsive": False,
            "failures": [],
            "details": {}
        }
        
        # Check if server is up
        try:
            response = await self._async_get(f"{self.mcp_url}/health")
            if response.status == 200:
                status["server_up"] = True
                status["details"]["health_response"] = await response.json()
            else:
                status["failures"].append(f"Health endpoint returned {response.status}")
        except Exception as e:
            status["failures"].append(f"Server connection error: {str(e)}")
            return status
        
        # Check JSON-RPC functionality
        try:
            json_data = {
                "jsonrpc": "2.0",
                "method": "get_tools",
                "params": {},
                "id": 1
            }
            response = await self._async_post(f"{self.mcp_url}/jsonrpc", json=json_data)
            if response.status == 200:
                status["jsonrpc_working"] = True
                result = await response.json()
                
                # Parse available tools
                tools = []
                if "result" in result:
                    if isinstance(result["result"], list):
                        tools = [t.get("name") for t in result["result"] if "name" in t]
                    elif "tools" in result["result"]:
                        tools = [t.get("name") for t in result["result"]["tools"] if "name" in t]
                
                status["details"]["available_tools"] = tools
                
                # Check VFS tools availability
                vfs_tools = [t for t in tools if t.startswith(("vfs_", "fs_journal_", "ipfs_fs_"))]
                status["vfs_tools_available"] = len(vfs_tools) > 0
                status["details"]["vfs_tools"] = vfs_tools
                
                # Update tool availability tracking
                self.tool_availability = {tool: True for tool in tools}
            else:
                status["failures"].append(f"JSON-RPC endpoint returned {response.status}")
                json_response = await response.text()
                status["details"]["jsonrpc_error"] = json_response
        except Exception as e:
            status["failures"].append(f"JSON-RPC error: {str(e)}")
        
        # If VFS tools are available, test a simple tool
        if status["vfs_tools_available"]:
            try:
                response = await self._async_post(f"{self.mcp_url}/jsonrpc", json={
                    "jsonrpc": "2.0",
                    "method": "use_tool",
                    "params": {
                        "tool_name": "vfs_get_config" if "vfs_get_config" in self.tool_availability else "fs_journal_status",
                        "arguments": {}
                    },
                    "id": 2
                })
                
                if response.status == 200:
                    result = await response.json()
                    if "result" in result and not "error" in result:
                        status["tools_responsive"] = True
                        status["details"]["tool_response"] = result["result"]
                    else:
                        status["failures"].append("Tool returned error response")
                        status["details"]["tool_error"] = result.get("error", "Unknown error")
                else:
                    status["failures"].append(f"Tool endpoint returned {response.status}")
            except Exception as e:
                status["failures"].append(f"Tool test error: {str(e)}")
        
        # Overall health check passed if all important checks passed
        status["health_check_passed"] = (
            status["server_up"] and 
            status["jsonrpc_working"] and 
            status["vfs_tools_available"] and 
            status["tools_responsive"]
        )
        
        return status
    
    async def _async_get(self, url: str, **kwargs):
        """Make async GET request"""
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, **kwargs) as response:
                return response
    
    async def _async_post(self, url: str, **kwargs):
        """Make async POST request"""
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, **kwargs) as response:
                return response
    
    def get_server_pid(self) -> Optional[int]:
        """Get PID of the server process from PID file"""
        try:
            if os.path.exists(self.pid_file):
                with open(self.pid_file, "r") as f:
                    return int(f.read().strip())
            return None
        except Exception as e:
            logger.error(f"Error reading PID file: {e}")
            return None
    
    def restart_server(self) -> bool:
        """Restart the MCP server"""
        logger.warning("Attempting to restart MCP server...")
        
        # Try to kill existing process
        pid = self.get_server_pid()
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to process {pid}")
                time.sleep(2)  # Give it time to shut down
                
                # Check if process is still running
                try:
                    os.kill(pid, 0)  # This will raise an exception if process is not running
                    logger.warning(f"Process {pid} still running, sending SIGKILL")
                    os.kill(pid, signal.SIGKILL)
                    time.sleep(1)
                except OSError:
                    logger.info(f"Process {pid} has terminated")
            except Exception as e:
                logger.error(f"Error terminating process {pid}: {e}")
        
        # Start new server
        try:
            logger.info(f"Running restart command: {self.restart_command}")
            subprocess.Popen(self.restart_command, shell=True)
            self.restart_count += 1
            logger.info(f"Restart command executed (restart #{self.restart_count})")
            time.sleep(5)  # Give it time to start up
            return True
        except Exception as e:
            logger.error(f"Error restarting server: {e}")
            return False
    
    async def run_check_cycle(self):
        """Run a single health check cycle"""
        self.total_checks += 1
        logger.info(f"Running health check #{self.total_checks}...")
        
        try:
            health_status = await self.check_server_health()
            
            if health_status["health_check_passed"]:
                # Reset failure count on success
                if self.failure_count > 0:
                    logger.info(f"Server recovered after {self.failure_count} failures")
                
                self.failure_count = 0
                self.last_successful_check = datetime.now()
                
                logger.info("Health check passed ✅")
                # Log some details
                up_time = "unknown"
                if "details" in health_status and "health_response" in health_status["details"]:
                    health_response = health_status["details"]["health_response"]
                    if "uptime" in health_response:
                        up_time = health_response["uptime"]
                
                vfs_tools_count = 0
                if "details" in health_status and "vfs_tools" in health_status["details"]:
                    vfs_tools_count = len(health_status["details"]["vfs_tools"])
                
                logger.info(f"Server uptime: {up_time}, VFS tools: {vfs_tools_count}")
                
            else:
                # Increment failure count
                self.failure_count += 1
                
                # Log failures
                failures = health_status["failures"]
                logger.warning(f"Health check failed ❌ ({self.failure_count}/{self.restart_threshold})")
                for failure in failures:
                    logger.warning(f"Failure: {failure}")
                
                # Check if restart is needed
                if self.auto_restart and self.failure_count >= self.restart_threshold:
                    logger.warning(f"Reached failure threshold ({self.failure_count}), restarting server")
                    self.restart_server()
                    self.failure_count = 0
        
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            self.failure_count += 1
    
    async def run(self):
        """Run the health monitor"""
        logger.info("Starting VFS Health Monitor")
        
        while self.running:
            try:
                await self.run_check_cycle()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("Monitor task cancelled")
                self.running = False
            except Exception as e:
                logger.error(f"Unexpected error in monitor loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    def stop(self):
        """Stop the health monitor"""
        logger.info("Stopping VFS Health Monitor")
        self.running = False

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="VFS MCP Health Monitor")
    parser.add_argument("--url", default=DEFAULT_MCP_URL, help="MCP server URL")
    parser.add_argument("--interval", type=int, default=DEFAULT_CHECK_INTERVAL, help="Check interval in seconds")
    parser.add_argument("--threshold", type=int, default=DEFAULT_RESTART_THRESHOLD, help="Failures before restart")
    parser.add_argument("--restart-command", default=DEFAULT_RESTART_COMMAND, help="Command to restart the server")
    parser.add_argument("--pid-file", default=DEFAULT_PID_FILE, help="PID file path")
    parser.add_argument("--no-restart", action="store_true", help="Disable auto-restart")
    
    args = parser.parse_args()
    
    # Create and run monitor
    monitor = VFSHealthMonitor(
        mcp_url=args.url,
        check_interval=args.interval,
        restart_threshold=args.threshold,
        restart_command=args.restart_command,
        pid_file=args.pid_file,
        auto_restart=not args.no_restart
    )
    
    try:
        await monitor.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        monitor.stop()
    
    logger.info("Monitor stopped")

if __name__ == "__main__":
    asyncio.run(main())
