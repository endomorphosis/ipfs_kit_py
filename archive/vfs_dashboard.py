#!/usr/bin/env python3
"""
IPFS-VFS Dashboard

A simple dashboard to monitor the status of the IPFS virtual filesystem integration.
This dashboard connects to the MCP server and displays real-time information about
the virtual filesystem, IPFS bridge, and operation history.
"""

import os
import sys
import json
import logging
import asyncio
import time
import requests
import curses
import threading
import traceback
from datetime import datetime
from typing import Dict, List, Any

# Configure logging to file
logging.basicConfig(
    filename="vfs_dashboard.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# MCP Server URL
MCP_URL = "http://localhost:3000"
POLL_INTERVAL = 5  # seconds

# Global state
global_data = {
    "last_update": None,
    "server_status": "Unknown",
    "fs_journal": {},
    "fs_bridge": {},
    "vfs_listing": [],
    "operation_history": [],
    "error": None
}

# --- API functions ---

def call_tool(tool_name: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
    """Call a tool on the MCP server"""
    if args is None:
        args = {}
    
    try:
        response = requests.post(f"{MCP_URL}/jsonrpc", json={
            "jsonrpc": "2.0",
            "method": "use_tool",
            "params": {
                "tool_name": tool_name,
                "arguments": args
            },
            "id": int(time.time() * 1000)
        }, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                return data["result"]
            elif "error" in data:
                return {"error": data["error"]}
            
        return {"error": f"HTTP {response.status_code}"}
    
    except Exception as e:
        return {"error": str(e)}

def check_server():
    """Check if MCP server is running"""
    try:
        response = requests.get(f"{MCP_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

# --- Update functions ---

def update_data():
    """Update all data from the server"""
    global global_data
    
    try:
        # Check server status
        server_up = check_server()
        global_data["server_status"] = "Running" if server_up else "Down"
        
        if not server_up:
            global_data["error"] = "MCP server is not responding"
            return
        
        # Get FS journal status
        fs_journal = call_tool("fs_journal_status", {})
        if "error" not in fs_journal:
            global_data["fs_journal"] = fs_journal
        
        # Get FS bridge status
        fs_bridge = call_tool("ipfs_fs_bridge_status", {})
        if "error" not in fs_bridge:
            global_data["fs_bridge"] = fs_bridge
        
        # Get VFS listing
        vfs_listing = call_tool("vfs_list", {"path": "/"})
        if "error" not in vfs_listing and "entries" in vfs_listing:
            global_data["vfs_listing"] = vfs_listing["entries"]
        
        # Get operation history
        history = call_tool("fs_journal_get_history", {"limit": 10})
        if "error" not in history and "operations" in history:
            global_data["operation_history"] = history["operations"]
        
        global_data["last_update"] = datetime.now()
        global_data["error"] = None
        
    except Exception as e:
        logger.error(f"Error updating data: {e}")
        logger.error(traceback.format_exc())
        global_data["error"] = str(e)

def update_thread():
    """Thread function to update data periodically"""
    while True:
        try:
            update_data()
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            logger.error(f"Error in update thread: {e}")
            time.sleep(POLL_INTERVAL)

# --- UI functions ---

def draw_box(win, y, x, height, width, title=None):
    """Draw a box with an optional title"""
    win.box()
    if title:
        win.addstr(0, 2, f" {title} ")

def draw_dashboard(stdscr):
    """Draw the dashboard UI"""
    global global_data
    
    # Clear screen
    stdscr.clear()
    
    # Get screen dimensions
    height, width = stdscr.getmaxyx()
    
    # Draw title bar
    stdscr.addstr(0, 0, "IPFS Virtual Filesystem Dashboard".center(width), curses.A_REVERSE)
    
    # Draw status line
    status_line = f"Server: {global_data['server_status']}"
    if global_data["last_update"]:
        status_line += f" | Last Update: {global_data['last_update'].strftime('%H:%M:%S')}"
    stdscr.addstr(1, 0, status_line)
    
    # Show error if any
    if global_data["error"]:
        stdscr.addstr(2, 0, f"Error: {global_data['error']}", curses.A_BOLD)
    
    # Draw panels
    if height < 20 or width < 80:
        stdscr.addstr(3, 0, "Terminal too small. Please resize.")
        return
    
    # Create panels for different sections
    
    # File System Journal panel
    fs_journal_win = curses.newwin(8, width // 2 - 1, 3, 0)
    draw_box(fs_journal_win, 0, 0, 8, width // 2 - 1, "File System Journal")
    
    if "status" in global_data["fs_journal"]:
        fs_journal_win.addstr(1, 2, f"Status: {global_data['fs_journal'].get('status', 'Unknown')}")
    if "operations_count" in global_data["fs_journal"]:
        fs_journal_win.addstr(2, 2, f"Operations: {global_data['fs_journal'].get('operations_count', 0)}")
    if "tracked_paths" in global_data["fs_journal"] and global_data["fs_journal"]["tracked_paths"]:
        fs_journal_win.addstr(3, 2, "Tracked paths:")
        for i, path in enumerate(global_data["fs_journal"]["tracked_paths"][:3]):
            fs_journal_win.addstr(4 + i, 4, path)
    fs_journal_win.refresh()
    
    # IPFS-FS Bridge panel
    bridge_win = curses.newwin(8, width // 2, 3, width // 2)
    draw_box(bridge_win, 0, 0, 8, width // 2, "IPFS-FS Bridge")
    
    if "status" in global_data["fs_bridge"]:
        bridge_win.addstr(1, 2, f"Status: {global_data['fs_bridge'].get('status', 'Unknown')}")
    if "patched" in global_data["fs_bridge"]:
        bridge_win.addstr(2, 2, f"Patched: {global_data['fs_bridge'].get('patched', False)}")
    if "mappings_count" in global_data["fs_bridge"]:
        bridge_win.addstr(3, 2, f"Mappings: {global_data['fs_bridge'].get('mappings_count', 0)}")
    if "cids_count" in global_data["fs_bridge"]:
        bridge_win.addstr(4, 2, f"CIDs: {global_data['fs_bridge'].get('cids_count', 0)}")
    bridge_win.refresh()
    
    # Virtual Filesystem listing panel
    vfs_win = curses.newwin(height - 11, width // 2 - 1, 11, 0)
    draw_box(vfs_win, 0, 0, height - 11, width // 2 - 1, "Virtual Filesystem")
    
    vfs_win.addstr(1, 2, "Root directory contents:")
    for i, entry in enumerate(global_data["vfs_listing"][:height - 15]):
        entry_str = f"{entry.get('name', 'unknown')} ({entry.get('type', 'unknown')})"
        vfs_win.addstr(2 + i, 4, entry_str)
    vfs_win.refresh()
    
    # Operation history panel
    history_win = curses.newwin(height - 11, width // 2, 11, width // 2)
    draw_box(history_win, 0, 0, height - 11, width // 2, "Recent Operations")
    
    history_win.addstr(1, 2, "Last 10 operations:")
    for i, op in enumerate(global_data["operation_history"][:height - 15]):
        timestamp = op.get("timestamp", "unknown")
        if isinstance(timestamp, str) and len(timestamp) > 19:
            timestamp = timestamp[:19]  # Truncate to make it readable
        
        op_type = op.get("operation_type", "unknown")
        path = op.get("path", "unknown")
        
        # Truncate path if too long
        if len(path) > width // 4:
            path = path[:width // 4 - 3] + "..."
        
        op_str = f"{timestamp} - {op_type} - {path}"
        history_win.addstr(2 + i, 4, op_str)
    history_win.refresh()
    
    # Footer
    stdscr.addstr(height - 1, 0, "Press 'q' to quit, 'r' to refresh".center(width), curses.A_REVERSE)
    
    stdscr.refresh()

def run_ui(stdscr):
    """Run the curses UI"""
    # Set up curses
    curses.curs_set(0)  # Hide cursor
    stdscr.timeout(1000)  # Set getch timeout to 1 second
    
    # Start update thread
    update_thread_obj = threading.Thread(target=update_thread)
    update_thread_obj.daemon = True
    update_thread_obj.start()
    
    # Initial update
    update_data()
    
    # Main loop
    while True:
        draw_dashboard(stdscr)
        
        # Get input
        c = stdscr.getch()
        if c == ord('q'):
            break
        elif c == ord('r'):
            update_data()

def main():
    """Main entry point"""
    try:
        # Check if terminal supports curses
        curses.wrapper(run_ui)
    except Exception as e:
        print(f"Error: {e}")
        logger.error(f"Error in main: {e}")
        logger.error(traceback.format_exc())
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
