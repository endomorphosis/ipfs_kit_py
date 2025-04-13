#!/usr/bin/env python3
"""
Script to restart the MCP server.
"""

import os
import sys
import time
import signal
import subprocess
import psutil

def find_mcp_server_processes():
    """Find all MCP server processes."""
    mcp_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check if this is an MCP server process
            if proc.info['cmdline'] and any('run_mcp_server' in cmd for cmd in proc.info['cmdline']):
                mcp_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return mcp_processes

def kill_mcp_server_processes():
    """Kill all MCP server processes."""
    processes = find_mcp_server_processes()
    if not processes:
        print("No MCP server processes found")
        return

    print(f"Found {len(processes)} MCP server processes:")
    for proc in processes:
        print(f"  PID {proc.pid}: {' '.join(proc.info['cmdline'])}")

    # Attempt graceful shutdown
    print("Attempting graceful shutdown...")
    for proc in processes:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except OSError as e:
            print(f"Failed to send SIGTERM to process {proc.pid}: {e}")

    # Wait for processes to exit
    grace_time = 5
    print(f"Waiting {grace_time} seconds for processes to exit...")
    time.sleep(grace_time)

    # Check if processes exited
    remaining = find_mcp_server_processes()
    if remaining:
        print(f"{len(remaining)} processes still running, sending SIGKILL...")
        for proc in remaining:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except OSError as e:
                print(f"Failed to send SIGKILL to process {proc.pid}: {e}")

def start_mcp_server():
    """Start a new MCP server."""
    print("Starting new MCP server...")
    
    # Start the server as a new process and detach
    server_process = subprocess.Popen(
        [sys.executable, "run_mcp_server_anyio.py", "--isolation", "--debug", "--skip-daemon"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setpgrp  # Detach the process
    )
    
    # Wait a bit to make sure it starts
    time.sleep(2)
    
    if server_process.poll() is not None:
        print("Server failed to start!")
        stdout, stderr = server_process.communicate()
        print("STDOUT:", stdout.decode())
        print("STDERR:", stderr.decode())
        return False
    
    print(f"MCP server started with PID {server_process.pid}")
    return True

def main():
    """Main function."""
    # Kill existing MCP server processes
    kill_mcp_server_processes()
    
    # Start a new MCP server
    success = start_mcp_server()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())