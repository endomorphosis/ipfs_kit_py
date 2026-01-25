#!/usr/bin/env python3
"""
Setup Real Lotus Client Connection

This script sets up a real Lotus client connection to the Filecoin network
by either installing a proper client or configuring the connection to use
a public Lotus gateway.
"""

import os
import sys
import subprocess
import platform
import json
import importlib
try:
    import requests
except ModuleNotFoundError:
    requests = None
import time
import logging
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def ensure_requests():
    """Ensure the requests library is available."""
    global requests
    if requests is not None:
        return True
    try:
        logger.info("Installing requests...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "requests"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            requests = importlib.import_module("requests")
            return True
        logger.warning(f"Failed to install requests: {result.stderr}")
    except Exception as e:
        logger.warning(f"Error installing requests: {e}")
    return False

# Configuration
LOTUS_BINARY_DIR = os.path.join(os.getcwd(), "bin", "lotus-bin")
LOTUS_HOME = os.path.expanduser("~/.lotus")
LOTUS_SCRIPT_PATH = os.path.join(os.getcwd(), "bin", "lotus")
LOTUS_TOKEN_PATH = os.path.join(LOTUS_HOME, "token")
LOTUS_API_PATH = os.path.join(LOTUS_HOME, "api")

# Available public gateways - Use these for read-only operations when local node isn't available
PUBLIC_GATEWAYS = [
    {
        "name": "Glif Node",
        "api": "https://api.node.glif.io/rpc/v0",
        "token": "",  # Public gateway, no token needed
        "read_only": True
    },
    {
        "name": "Infura",
        "api": "https://filecoin.infura.io",
        "token_env": "INFURA_API_KEY",  # Requires signup but has free tier
        "read_only": True
    }
]

def check_existing_lotus():
    """Check if a proper Lotus client is already installed"""
    # First check if there's a real Lotus binary in the system PATH
    try:
        result = subprocess.run(
            ["which", "lotus"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            lotus_path = result.stdout.strip()
            logger.info(f"Found system Lotus installation at: {lotus_path}")
            
            # Check if this is a real Lotus, not our mock
            try:
                version_result = subprocess.run(
                    [lotus_path, "version"],
                    capture_output=True,
                    text=True
                )
                
                if "mock" not in version_result.stdout.lower():
                    logger.info("System Lotus installation appears to be real")
                    return lotus_path
                else:
                    logger.info("System Lotus installation appears to be a mock implementation")
            except Exception as e:
                logger.warning(f"Error checking Lotus version: {e}")
    
    except Exception as e:
        logger.warning(f"Error checking for system Lotus: {e}")
    
    # Check for an existing Lotus installation in our project
    project_lotus = os.path.join(LOTUS_BINARY_DIR, "lotus")
    if os.path.exists(project_lotus) and os.access(project_lotus, os.X_OK):
        # Check if this is a real Lotus, not our mock
        try:
            version_result = subprocess.run(
                [project_lotus, "version"],
                capture_output=True,
                text=True
            )
            
            if "mock" not in version_result.stdout.lower():
                logger.info(f"Found real Lotus installation at: {project_lotus}")
                return project_lotus
            else:
                logger.info("Project Lotus installation appears to be a mock implementation")
        except Exception as e:
            logger.warning(f"Error checking project Lotus version: {e}")
    
    logger.info("No real Lotus client installation found")
    return None

def configure_public_gateway():
    """Configure connection to use a public gateway when local node isn't available"""
    logger.info("Configuring to use a public gateway...")
    
    # Choose the first public gateway
    gateway = PUBLIC_GATEWAYS[0]
    logger.info(f"Using public gateway: {gateway['name']} at {gateway['api']}")
    
    token = ""
    if "token_env" in gateway and gateway["token_env"]:
        token = os.environ.get(gateway["token_env"], "")
        if not token:
            logger.warning(f"Environment variable {gateway['token_env']} not set for {gateway['name']}")
    elif "token" in gateway:
        token = gateway["token"]
    
    # Create Lotus home directory if it doesn't exist
    os.makedirs(LOTUS_HOME, exist_ok=True)
    
    # Write API and token files
    with open(LOTUS_API_PATH, "w") as f:
        f.write(gateway["api"])
    logger.info(f"API endpoint set to: {gateway['api']}")
    
    with open(LOTUS_TOKEN_PATH, "w") as f:
        f.write(token)
    logger.info(f"API token set for {gateway['name']}")
    
    return gateway

def create_lotus_wrapper(gateway=None):
    """Create a Lotus wrapper script that uses the proper configuration"""
    logger.info("Creating Lotus wrapper script...")
    
    # Determine if we're using a gateway or real lotus
    use_gateway = gateway is not None
    
    script_content = f"""#!/bin/bash
# Lotus client wrapper script
# This script configures the environment for the Lotus client

# Set the Lotus path
export LOTUS_PATH="{LOTUS_HOME}"

# Execute the Lotus command
"""

    if use_gateway:
        # For gateway, we create a wrapper that simulates some commands locally
        # and forwards others to the gateway
        script_content += f"""
# Using public gateway: {gateway['name']} at {gateway['api']}
API_URL="{gateway['api']}"
API_TOKEN="$(cat "{LOTUS_TOKEN_PATH}")"

command="$1"
shift

case "$command" in
    version)
        echo "Lotus {gateway['name']} Gateway Client v1.0.0"
        echo "Note: Using remote Filecoin gateway, some commands may be limited"
        exit 0
        ;;
    net)
        if [ "$1" == "id" ]; then
            echo "Using remote gateway: full node ID not available"
            exit 0
        else
            # Forward to remote API
            curl -X POST -H "Content-Type: application/json" \\
                -H "Authorization: Bearer $API_TOKEN" \\
                -d '{{"jsonrpc":"2.0","method":"Filecoin.NetPeers","params":[],"id":1}}' \\
                "$API_URL"
            exit $?
        fi
        ;;
    *)
        # Forward other commands to the API
        echo "Forwarding command to {gateway['name']} gateway: Filecoin.$command"
        curl -X POST -H "Content-Type: application/json" \\
            -H "Authorization: Bearer $API_TOKEN" \\
            -d '{{"jsonrpc":"2.0","method":"Filecoin.$command","params":[],"id":1}}' \\
            "$API_URL"
        exit $?
        ;;
esac
"""
    else:
        # For local Lotus, just pass everything through
        lotus_binary = os.path.join(LOTUS_BINARY_DIR, "lotus")
        script_content += f"""
# Using locally installed lotus binary
"{lotus_binary}" "$@"
"""
    
    # Write the script
    with open(LOTUS_SCRIPT_PATH, "w") as f:
        f.write(script_content)
    
    # Make it executable
    os.chmod(LOTUS_SCRIPT_PATH, 0o755)
    
    logger.info(f"Created Lotus wrapper script at: {LOTUS_SCRIPT_PATH}")
    return LOTUS_SCRIPT_PATH

def test_lotus_connection(lotus_path):
    """Test the Lotus connection to ensure it's working"""
    logger.info("Testing Lotus connection...")
    
    try:
        # Test basic version command
        version_result = subprocess.run(
            [lotus_path, "version"],
            capture_output=True,
            text=True
        )
        
        if version_result.returncode == 0:
            logger.info(f"Lotus version command succeeded:\n{version_result.stdout.strip()}")
        else:
            logger.warning(f"Lotus version command failed: {version_result.stderr.strip()}")
            return False
        
        # Test chain head command
        chain_result = subprocess.run(
            [lotus_path, "chain", "head"],
            capture_output=True,
            text=True
        )
        
        if chain_result.returncode == 0:
            logger.info("Lotus chain head command succeeded")
            return True
        else:
            logger.warning(f"Lotus chain head command failed: {chain_result.stderr.strip()}")
            return False
    
    except Exception as e:
        logger.error(f"Error testing Lotus connection: {e}")
        return False

def update_mcp_filecoin_integration():
    """Update the Filecoin integration in the MCP server"""
    logger.info("Updating MCP Filecoin integration...")
    
    # Update the Filecoin storage implementation
    filecoin_storage_path = os.path.join(os.getcwd(), "filecoin_storage.py")
    
    try:
        with open(filecoin_storage_path, "r") as f:
            content = f.read()
        
        # Update the LOTUS_PATH initialization
        content = content.replace(
            "LOTUS_PATH = result.stdout.strip()",
            f"LOTUS_PATH = result.stdout.strip() if result.returncode == 0 else '{LOTUS_SCRIPT_PATH}'"
        )
        
        # Make sure we check for our wrapper script too
        content = content.replace(
            "# Check if lotus client is available by checking if the command exists",
            """# Check if lotus client is available by checking if the command exists
# Also look for our wrapper script
wrapper_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "lotus")
if os.path.exists(wrapper_path) and os.access(wrapper_path, os.X_OK):
    LOTUS_PATH = wrapper_path
    LOTUS_AVAILABLE = True
    logger.info(f"Found Lotus wrapper script at: {LOTUS_PATH}")
"""
        )
        
        # Write the updated file
        with open(filecoin_storage_path, "w") as f:
            f.write(content)
        
        logger.info(f"Updated Filecoin storage implementation at: {filecoin_storage_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error updating MCP Filecoin integration: {e}")
        return False

def update_mcp_config():
    """Update MCP configuration with the Filecoin settings"""
    config_file = os.path.join(os.getcwd(), "mcp_unified_config.sh")
    
    try:
        # Read existing file if it exists
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                lines = f.readlines()
            
            # Find Filecoin section and update it
            filecoin_section_start = -1
            filecoin_section_end = -1
            
            for i, line in enumerate(lines):
                if "# Filecoin configuration" in line:
                    filecoin_section_start = i
                elif filecoin_section_start > -1 and line.strip() and not line.strip().startswith("#") and filecoin_section_end == -1:
                    # Find the end of the section (next non-comment, non-empty line)
                    for j in range(i, len(lines)):
                        if "# " in lines[j] and not lines[j].strip().startswith("export"):
                            filecoin_section_end = j
                            break
                    if filecoin_section_end == -1:
                        filecoin_section_end = len(lines)
            
            if filecoin_section_start > -1 and filecoin_section_end > -1:
                # Create new Filecoin configuration
                new_filecoin_config = [
                    "# Filecoin configuration\n",
                    "# Using real Lotus connection\n",
                    f"export LOTUS_PATH=\"{LOTUS_HOME}\"\n"
                ]
                
                if os.path.exists(LOTUS_TOKEN_PATH):
                    with open(LOTUS_TOKEN_PATH, "r") as f:
                        token = f.read().strip()
                    new_filecoin_config.append(f"export LOTUS_API_TOKEN=\"{token}\"\n")
                
                if os.path.exists(LOTUS_API_PATH):
                    with open(LOTUS_API_PATH, "r") as f:
                        api = f.read().strip()
                    new_filecoin_config.append(f"export LOTUS_API_ENDPOINT=\"{api}\"\n")
                
                # Add bin directory to PATH
                new_filecoin_config.append(f"export PATH=\"{os.path.dirname(LOTUS_SCRIPT_PATH)}:$PATH\"\n")
                
                # Replace the section
                lines[filecoin_section_start:filecoin_section_end] = new_filecoin_config
                
                # Write updated file
                with open(config_file, "w") as f:
                    f.writelines(lines)
                
                logger.info(f"Updated MCP configuration file with Filecoin settings")
                return True
        
        # If we couldn't update an existing file, create a new one
        with open(config_file, "w") as f:
            f.write(f"""#!/bin/bash
# MCP Unified Configuration
# Generated by setup_real_lotus.py

# Filecoin configuration
# Using real Lotus connection
export LOTUS_PATH="{LOTUS_HOME}"
""")
            
            if os.path.exists(LOTUS_TOKEN_PATH):
                with open(LOTUS_TOKEN_PATH, "r") as f:
                    token = f.read().strip()
                f.write(f"export LOTUS_API_TOKEN=\"{token}\"\n")
            
            if os.path.exists(LOTUS_API_PATH):
                with open(LOTUS_API_PATH, "r") as f:
                    api = f.read().strip()
                f.write(f"export LOTUS_API_ENDPOINT=\"{api}\"\n")
            
            # Add bin directory to PATH
            f.write(f"export PATH=\"{os.path.dirname(LOTUS_SCRIPT_PATH)}:$PATH\"\n")
        
        # Make it executable
        os.chmod(config_file, 0o755)
        
        logger.info(f"Created new MCP configuration file with Filecoin settings")
        return True
    
    except Exception as e:
        logger.error(f"Error updating MCP configuration: {e}")
        return False

def restart_mcp_server():
    """Restart the MCP server with the new configuration"""
    logger.info("Restarting MCP server...")
    
    try:
        # First stop any running MCP servers
        subprocess.run(
            ["pkill", "-f", "enhanced_mcp_server.py"],
            capture_output=True
        )
        
        # Wait for the processes to stop
        time.sleep(2)
        
        # Start the MCP server with the new configuration
        cmd = f"""
        cd {os.getcwd()} && 
        source .venv/bin/activate && 
        source {os.path.join(os.getcwd(), "mcp_unified_config.sh")} &&
        python enhanced_mcp_server.py --port 9997 --debug > logs/enhanced_mcp_real.log 2>&1 &
        echo $! > mcp_server.pid
        """
        
        subprocess.run(cmd, shell=True, executable="/bin/bash")
        
        logger.info("MCP server restarted with new Filecoin configuration")
        
        # Wait for the server to start
        time.sleep(5)
        
        return True
    
    except Exception as e:
        logger.error(f"Error restarting MCP server: {e}")
        return False

def main():
    """Main function"""
    logger.info("Setting up real Lotus client connection...")
    
    # Create directories
    os.makedirs(LOTUS_BINARY_DIR, exist_ok=True)
    os.makedirs(LOTUS_HOME, exist_ok=True)
    
    # Check for existing Lotus installation
    lotus_path = check_existing_lotus()
    
    gateway = None
    
    if not lotus_path:
        logger.info("No real Lotus installation found, configuring to use a public gateway")
        gateway = configure_public_gateway()
    
    # Create Lotus wrapper script
    lotus_wrapper = create_lotus_wrapper(gateway)
    
    # Test the Lotus connection
    connection_ok = test_lotus_connection(lotus_wrapper)
    
    if connection_ok:
        logger.info("Lotus connection is working!")
        
        # Update MCP Filecoin integration
        update_mcp_filecoin_integration()
        
        # Update MCP configuration
        update_mcp_config()
        
        # Restart MCP server
        restart_mcp_server()
        
        logger.info("Lotus client connection has been successfully set up!")
    else:
        logger.warning("Lotus connection is not working. Please check your configuration.")
    
if __name__ == "__main__":
    main()