#!/usr/bin/env python3
"""
Script to properly initialize the HuggingFace storage backend with real credentials.

This script updates the MCP server to use real HuggingFace credentials instead of mock mode.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def get_huggingface_token():
    """Get the HuggingFace token from the default location or environment."""
    # First check environment variable
    token = os.environ.get("HUGGINGFACE_TOKEN")
    if token:
        print(f"Found HuggingFace token in environment variables")
        return token
    
    # Check standard token file location
    token_path = Path.home() / ".cache" / "huggingface" / "token"
    if token_path.exists():
        try:
            token = token_path.read_text().strip()
            if token:
                print(f"Found HuggingFace token in {token_path}")
                return token
        except Exception as e:
            print(f"Error reading token file: {e}")
    
    # Try using huggingface-cli to get token
    try:
        result = subprocess.run(
            ["huggingface-cli", "whoami", "--token"], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            token = result.stdout.strip()
            print("Found HuggingFace token via CLI")
            return token
    except Exception as e:
        print(f"Error getting token from CLI: {e}")
    
    return None

def update_environment_file():
    """Update the environment file with the HuggingFace token."""
    token = get_huggingface_token()
    if not token:
        print("No HuggingFace token found")
        return False
    
    # Update environment
    os.environ["HUGGINGFACE_TOKEN"] = token
    os.environ["MCP_USE_MOCK_MODE"] = "false"
    
    # Create a credentials file for persistence
    creds_file = Path('mcp_real_credentials.sh')
    
    # Read existing file if it exists
    existing_content = ""
    if creds_file.exists():
        existing_content = creds_file.read_text()
    
    # Update the HUGGINGFACE_TOKEN line or add it
    if "HUGGINGFACE_TOKEN=" in existing_content:
        lines = existing_content.splitlines()
        updated_lines = []
        for line in lines:
            if line.startswith("HUGGINGFACE_TOKEN="):
                updated_lines.append(f'export HUGGINGFACE_TOKEN="{token}"')
            elif line.startswith("MCP_USE_MOCK_MODE="):
                updated_lines.append('export MCP_USE_MOCK_MODE="false"')
            else:
                updated_lines.append(line)
        
        new_content = "\n".join(updated_lines)
    else:
        new_content = existing_content + f'\nexport HUGGINGFACE_TOKEN="{token}"\nexport MCP_USE_MOCK_MODE="false"\n'
    
    # Write the updated file
    creds_file.write_text(new_content)
    print(f"Updated {creds_file} with HuggingFace token")
    
    return True

def restart_mcp_server():
    """Restart the MCP server with the updated configuration."""
    try:
        # Kill any existing MCP servers
        subprocess.run(["pkill", "-f", "python.*enhanced_mcp_server.py"])
        print("Stopped existing MCP server processes")
        
        # Wait a moment for processes to terminate
        import time
        time.sleep(2)
        
        # Source the credentials file and start the server
        cmd = f"""
        cd {os.getcwd()} && 
        source .venv/bin/activate && 
        source mcp_real_credentials.sh &&
        python enhanced_mcp_server.py --port 9997 --debug > logs/enhanced_mcp_real.log 2>&1 &
        """
        
        result = subprocess.run(cmd, shell=True, executable="/bin/bash")
        
        if result.returncode == 0:
            print("MCP server restarted with real HuggingFace credentials")
            return True
        else:
            print(f"Failed to restart MCP server: {result.returncode}")
            return False
    
    except Exception as e:
        print(f"Error restarting MCP server: {e}")
        return False

if __name__ == "__main__":
    print("Initializing HuggingFace storage backend with real credentials...")
    
    if update_environment_file():
        if restart_mcp_server():
            print("Successfully configured MCP server with real HuggingFace credentials")
            sys.exit(0)
    
    print("Failed to configure MCP server with real HuggingFace credentials")
    sys.exit(1)