#!/usr/bin/env python3
"""
Update MCP server with credentials from configuration.
This script loads credentials from config file or environment variables
and configures the MCP server to use them.
"""

import os
import json
import sys
import subprocess
import signal
import time

CONFIG_DIR = os.path.expanduser("~/.ipfs_kit")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
MCP_SERVER_SCRIPT = "run_mcp_server.py"
MCP_SERVER_PID_FILE = "server.pid"

def load_config():
    """Load credentials from configuration file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {CONFIG_FILE} contains invalid JSON. Using environment variables only.")
            return {"credentials": {}}
    else:
        return {"credentials": {}}

def get_credential_env_vars(config):
    """Extract credentials into environment variables."""
    env = os.environ.copy()
    creds = config.get("credentials", {})
    
    # HuggingFace
    if "huggingface" in creds:
        hf = creds["huggingface"]
        if "token" in hf and "HUGGINGFACE_TOKEN" not in env:
            env["HUGGINGFACE_TOKEN"] = hf["token"]
        if "test_repo" in hf and "HF_TEST_REPO" not in env:
            env["HF_TEST_REPO"] = hf["test_repo"]
    
    # AWS/S3
    if "aws" in creds:
        aws = creds["aws"]
        if "access_key_id" in aws and "AWS_ACCESS_KEY_ID" not in env:
            env["AWS_ACCESS_KEY_ID"] = aws["access_key_id"]
        if "secret_access_key" in aws and "AWS_SECRET_ACCESS_KEY" not in env:
            env["AWS_SECRET_ACCESS_KEY"] = aws["secret_access_key"]
        if "region" in aws and "AWS_REGION" not in env:
            env["AWS_REGION"] = aws["region"]
    
    if "s3" in creds and "test_bucket" in creds["s3"] and "S3_TEST_BUCKET" not in env:
        env["S3_TEST_BUCKET"] = creds["s3"]["test_bucket"]
    
    # Storacha/Web3.Storage
    if "storacha" in creds and "token" in creds["storacha"] and "W3_TOKEN" not in env:
        env["W3_TOKEN"] = creds["storacha"]["token"]
        
    return env

def is_server_running():
    """Check if MCP server is already running."""
    if os.path.exists(MCP_SERVER_PID_FILE):
        try:
            with open(MCP_SERVER_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
                
            # Check if process exists
            try:
                os.kill(pid, 0)
                return pid  # Process exists
            except OSError:
                return None  # Process doesn't exist
        except (ValueError, FileNotFoundError):
            return None
    return None

def stop_server(pid):
    """Stop the running MCP server."""
    if pid:
        print(f"Stopping MCP server (PID {pid})...")
        try:
            os.kill(pid, signal.SIGTERM)
            # Wait for server to stop
            for _ in range(10):
                try:
                    os.kill(pid, 0)
                    time.sleep(0.5)
                except OSError:
                    break
            else:
                print("Server didn't stop gracefully, forcing shutdown...")
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        except OSError as e:
            print(f"Error stopping server: {e}")
        
        # Remove PID file
        if os.path.exists(MCP_SERVER_PID_FILE):
            os.remove(MCP_SERVER_PID_FILE)

def start_server(env):
    """Start the MCP server with credentials in environment."""
    print("Starting MCP server with credentials...")
    
    # Check if script exists
    if not os.path.exists(MCP_SERVER_SCRIPT):
        print(f"Error: MCP server script '{MCP_SERVER_SCRIPT}' not found.")
        return False
    
    try:
        # Start server in background
        process = subprocess.Popen(
            [sys.executable, MCP_SERVER_SCRIPT],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Give it a moment to start
        time.sleep(2)
        
        if process.poll() is None:
            print(f"MCP server started with PID {process.pid}")
            # Save PID
            with open(MCP_SERVER_PID_FILE, 'w') as f:
                f.write(str(process.pid))
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"Failed to start MCP server:")
            print(f"STDOUT: {stdout.decode('utf-8')}")
            print(f"STDERR: {stderr.decode('utf-8')}")
            return False
    except Exception as e:
        print(f"Error starting server: {e}")
        return False

def check_missing_credentials(env):
    """Check for missing credentials and return a list."""
    missing = []
    
    if "HUGGINGFACE_TOKEN" not in env:
        missing.append("HuggingFace token (HUGGINGFACE_TOKEN)")
    if "HF_TEST_REPO" not in env:
        missing.append("HuggingFace test repo (HF_TEST_REPO)")
        
    if "AWS_ACCESS_KEY_ID" not in env or "AWS_SECRET_ACCESS_KEY" not in env:
        missing.append("AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)")
    if "S3_TEST_BUCKET" not in env:
        missing.append("S3 test bucket (S3_TEST_BUCKET)")
        
    if "W3_TOKEN" not in env:
        missing.append("Web3.Storage token (W3_TOKEN)")
        
    return missing

def main():
    # Load credentials from config
    config = load_config()
    env = get_credential_env_vars(config)
    
    # Check for missing credentials
    missing = check_missing_credentials(env)
    if missing:
        print("Warning: The following credentials are missing:")
        for cred in missing:
            print(f"  - {cred}")
        print("\nTo add credentials, run: python manage_credentials.py")
        
        proceed = input("\nDo you want to proceed with available credentials? (y/n): ")
        if proceed.lower() != 'y':
            print("Exiting. No changes made.")
            return
    
    # Check if server is running
    pid = is_server_running()
    if pid:
        print(f"MCP server is already running (PID {pid})")
        restart = input("Do you want to restart with updated credentials? (y/n): ")
        if restart.lower() == 'y':
            stop_server(pid)
            start_server(env)
        else:
            print("Server left running with current credentials.")
    else:
        start_server(env)
        
if __name__ == "__main__":
    main()