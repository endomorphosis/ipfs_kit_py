#!/usr/bin/env python3
'''
Helper script for managing Lassie daemon.

This script provides simplified commands for starting, stopping, and
checking the status of the Lassie daemon.
'''

import argparse
import os
import signal
import subprocess
import sys
import time
import json
import re
import urllib.request
import socket

# Setup paths
BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
LASSIE_BIN = os.path.join(BIN_DIR, "lassie")
if sys.platform == "win32":
    LASSIE_BIN += ".exe"

# Default port for Lassie daemon
DEFAULT_PORT = 41443

# Get PID of running Lassie daemon
def get_daemon_pid():
    # Try to find process by port
    port = DEFAULT_PORT
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(
                'netstat -ano | findstr ":%s"' % port,
                shell=True,
                text=True
            )
            for line in output.strip().split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    return int(pid)
        except subprocess.CalledProcessError:
            pass
    else:
        try:
            output = subprocess.check_output(
                "lsof -i :%s -t" % port,
                shell=True,
                text=True
            )
            return int(output.strip())
        except subprocess.CalledProcessError:
            pass
    
    # Try listing processes
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq lassie.exe" /FO CSV /NH',
                shell=True,
                text=True
            )
            if "lassie.exe" in output:
                pid_match = re.search(r'"lassie.exe","([0-9]+)"', output)
                if pid_match:
                    return int(pid_match.group(1))
        except subprocess.CalledProcessError:
            pass
    else:
        try:
            output = subprocess.check_output(
                "pgrep -f 'lassie daemon'",
                shell=True,
                text=True
            )
            if output.strip():
                return int(output.strip())
        except subprocess.CalledProcessError:
            pass
    
    return None

# Check if Lassie daemon is running
def is_daemon_running():
    # First check process
    pid = get_daemon_pid()
    if pid is None:
        return False
    
    # Check if process exists
    try:
        os.kill(pid, 0)
        # Additionally check if API is responsive
        try:
            urllib.request.urlopen(f"http://localhost:{DEFAULT_PORT}/health", timeout=1)
            return True
        except (urllib.error.URLError, socket.timeout):
            # Process exists but API not responding
            return False
    except OSError:
        return False

# Start Lassie daemon
def start_daemon(port=DEFAULT_PORT):
    if is_daemon_running():
        print("Lassie daemon is already running")
        return True
    
    # Build command
    cmd = [LASSIE_BIN, "daemon", "-p", str(port)]
        
    # Start daemon process
    try:
        print(f"Starting Lassie daemon on port {port}...")
        
        if sys.platform == "win32":
            # Use subprocess.CREATE_NEW_CONSOLE on Windows
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # Use nohup on Unix-like systems
            nohup_cmd = f"nohup {' '.join(cmd)} > /tmp/lassie-daemon.log 2>&1 &"
            subprocess.run(nohup_cmd, shell=True, check=True)
        
        # Wait for daemon to start
        for i in range(10):
            time.sleep(1)
            if is_daemon_running():
                print("Lassie daemon started successfully")
                return True
        
        print("Warning: Daemon process started but API not responding yet. Will retry a few more times...")
        
        # Extra wait time
        for i in range(5):
            time.sleep(2)
            if is_daemon_running():
                print("Lassie daemon started successfully")
                return True
                
        print("Warning: Daemon seems to be starting, but API not yet available")
        return True
    except Exception as e:
        print(f"Error starting Lassie daemon: {{e}}")
        return False

# Stop Lassie daemon
def stop_daemon():
    pid = get_daemon_pid()
    if pid is None:
        print("Lassie daemon is not running")
        return True
    
    try:
        # Try graceful shutdown first (Ctrl+C)
        if sys.platform == "win32":
            subprocess.run(f"taskkill /PID {pid}", shell=True, check=False)
        else:
            os.kill(pid, signal.SIGTERM)
        
        # Wait for process to exit
        for i in range(10):
            time.sleep(1)
            if not is_daemon_running():
                print("Lassie daemon stopped successfully")
                return True
        
        # Force kill if still running
        print("Daemon not responding to graceful shutdown, force killing...")
        if sys.platform == "win32":
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=False)
        else:
            os.kill(pid, signal.SIGKILL)
        
        time.sleep(1)
        if not is_daemon_running():
            print("Lassie daemon stopped successfully (force kill)")
            return True
        else:
            print("Failed to stop Lassie daemon")
            return False
    except Exception as e:
        print(f"Error stopping Lassie daemon: {{e}}")
        return False

# Check daemon status
def check_status():
    if is_daemon_running():
        pid = get_daemon_pid()
        print(f"Lassie daemon is running (PID: {{pid}}, Port: {DEFAULT_PORT})")
        
        # Get additional info
        try:
            with urllib.request.urlopen(f"http://localhost:{DEFAULT_PORT}/health") as response:
                health_data = json.loads(response.read().decode())
                print(f"Health status: {{'uptime': {health_data.get('uptime', 'unknown')}, 'version': {health_data.get('version', 'unknown')}}}")
        except Exception as e:
            print(f"Warning: Could not get daemon health status: {e}")
    else:
        print("Lassie daemon is not running")

# Simple fetch test
def fetch_test(cid="bafybeic56z3yccnla3cutmvqsn5zy3g24muupcsjtoyp3pu5pm5amurjx4"):
    if not is_daemon_running():
        print("Lassie daemon is not running. Starting daemon...")
        start_daemon()
        if not is_daemon_running():
            print("Failed to start Lassie daemon")
            return False
    
    try:
        print(f"Testing Lassie fetch with CID: {cid}")
        temp_file = os.path.join(tempfile.gettempdir(), f"{cid}.car")
        
        # Use API endpoint
        api_url = f"http://localhost:{DEFAULT_PORT}/ipfs/{cid}?filename=test.car"
        print(f"Fetching from: {api_url}")
        
        # Use urllib to fetch with a longer timeout (30 seconds)
        try:
            with urllib.request.urlopen(api_url, timeout=30) as response:
                with open(temp_file, 'wb') as f:
                    f.write(response.read())
                    
            print(f"Successfully fetched CID {cid} to {temp_file}")
            print("Test passed!")
            return True
        except Exception as e:
            print(f"Error fetching via API: {e}")
            
            # Try direct command
            print("Trying direct command...")
            result = subprocess.run(
                [LASSIE_BIN, "fetch", "-o", temp_file, cid],
                check=False,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"Successfully fetched CID {cid} to {temp_file}")
                print("Test passed!")
                return True
            else:
                print(f"Error fetching with direct command: {result.stderr}")
                return False
                
    except Exception as e:
        print(f"Error during fetch test: {e}")
        return False

# Main function
def main():
    parser = argparse.ArgumentParser(description="Lassie daemon helper")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start Lassie daemon")
    start_parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help=f"Port number (default: {DEFAULT_PORT})")
    
    # Stop command
    subparsers.add_parser("stop", help="Stop Lassie daemon")
    
    # Status command
    subparsers.add_parser("status", help="Check Lassie daemon status")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test Lassie fetch with a sample CID")
    test_parser.add_argument("-c", "--cid", default="bafybeic56z3yccnla3cutmvqsn5zy3g24muupcsjtoyp3pu5pm5amurjx4", 
                           help="CID to fetch (default: sample birb.mp4)")
    
    args = parser.parse_args()
    
    if args.command == "start":
        start_daemon(args.port)
    elif args.command == "stop":
        stop_daemon()
    elif args.command == "status":
        check_status()
    elif args.command == "test":
        fetch_test(args.cid)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
