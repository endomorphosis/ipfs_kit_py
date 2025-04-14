#!/usr/bin/env python3
"""
Storacha Integration Setup

This script verifies and sets up proper Storacha integration for the MCP server.
It checks for the required libraries, validates API access, and ensures correct configuration.
"""

import os
import sys
import logging
import json
import subprocess
import time
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def install_dependencies():
    """Install required dependencies for Storacha integration."""
    try:
        logger.info("Installing required libraries for Storacha integration...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "requests"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Successfully installed required libraries")
            return True
        else:
            logger.error(f"Failed to install required libraries: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error installing dependencies: {e}")
        return False

def verify_api_key():
    """Verify the Storacha API key."""
    api_key = os.environ.get("STORACHA_API_KEY")
    api_url = os.environ.get("STORACHA_API_URL", "https://api.storacha.io")
    
    if not api_key:
        logger.warning("No Storacha API key found in environment")
        logger.info("Set the STORACHA_API_KEY environment variable")
        return False
    
    try:
        # Test API by making a simple status request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{api_url}/v1/status",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Successfully connected to Storacha API: {data}")
            return True
        else:
            logger.error(f"Failed to connect to Storacha API. Status code: {response.status_code}")
            if response.status_code == 401:
                logger.error("Authentication failed. Check your API key.")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Storacha API: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def setup_local_mock():
    """Set up a local mock if real API connection fails."""
    logger.info("Setting up local mock for Storacha...")
    
    # Create mock directory
    mock_dir = os.path.expanduser("~/.ipfs_kit/mock_storacha")
    os.makedirs(mock_dir, exist_ok=True)
    
    # Create mock configuration
    mock_config = {
        "version": "1.0.0",
        "mock": True,
        "api_url": os.environ.get("STORACHA_API_URL", "https://api.storacha.io"),
        "api_key": os.environ.get("STORACHA_API_KEY", "mock_key"),
        "storage_dir": mock_dir
    }
    
    # Save mock configuration
    config_path = os.path.join(mock_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump(mock_config, f, indent=2)
    
    logger.info(f"Created mock configuration at {config_path}")
    return True

def test_store_retrieve():
    """Test storing and retrieving data through Storacha."""
    api_key = os.environ.get("STORACHA_API_KEY")
    api_url = os.environ.get("STORACHA_API_URL", "https://api.storacha.io")
    
    if not api_key:
        logger.warning("No Storacha API key, skipping store/retrieve test")
        return False
    
    try:
        # Create test content
        test_content = "This is a test content for Storacha integration. " + str(time.time())
        
        # Store content
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # First, store the content
        store_payload = {
            "content": test_content,
            "name": "storacha_test.txt",
            "tags": ["test", "integration"]
        }
        
        logger.info("Attempting to store test content in Storacha...")
        
        try:
            store_response = requests.post(
                f"{api_url}/v1/store",
                headers=headers,
                json=store_payload,
                timeout=30
            )
            
            if store_response.status_code == 200 or store_response.status_code == 201:
                store_data = store_response.json()
                content_id = store_data.get("id") or store_data.get("content_id")
                
                if content_id:
                    logger.info(f"Successfully stored content. ID: {content_id}")
                    
                    # Now retrieve the content
                    logger.info(f"Attempting to retrieve content with ID: {content_id}")
                    
                    retrieve_response = requests.get(
                        f"{api_url}/v1/retrieve/{content_id}",
                        headers=headers,
                        timeout=30
                    )
                    
                    if retrieve_response.status_code == 200:
                        retrieve_data = retrieve_response.json() if retrieve_response.headers.get('content-type') == 'application/json' else {"content": retrieve_response.text}
                        retrieved_content = retrieve_data.get("content")
                        
                        if retrieved_content and retrieved_content == test_content:
                            logger.info("Successfully retrieved content, matches original")
                            return True
                        else:
                            logger.warning("Retrieved content does not match original")
                            return False
                    else:
                        logger.error(f"Failed to retrieve content. Status code: {retrieve_response.status_code}")
                        return False
                else:
                    logger.error("No content ID returned from store operation")
                    return False
            else:
                logger.error(f"Failed to store content. Status code: {store_response.status_code}")
                if store_response.headers.get('content-type') == 'application/json':
                    logger.error(f"Error details: {store_response.json()}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error in Storacha API request: {e}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error in test_store_retrieve: {e}")
        return False

def main():
    """Main function to setup Storacha integration."""
    logger.info("Setting up Storacha integration...")
    
    # Install dependencies
    if not install_dependencies():
        logger.warning("Failed to install dependencies")
    
    # Check if API key is set
    api_key = os.environ.get("STORACHA_API_KEY")
    api_url = os.environ.get("STORACHA_API_URL", "https://api.storacha.io")
    
    # Log current configuration
    logger.info(f"Storacha API URL: {api_url}")
    if api_key:
        logger.info("Storacha API key is set")
    else:
        logger.warning("Storacha API key is not set")
    
    # Verify API key if available
    api_works = False
    if api_key:
        api_works = verify_api_key()
        if api_works:
            logger.info("Storacha API key verified successfully")
            
            # Test store and retrieve functionality
            if test_store_retrieve():
                logger.info("Storacha store/retrieve test successful")
            else:
                logger.warning("Storacha store/retrieve test failed")
        else:
            logger.warning("Failed to verify Storacha API key")
    
    # Set up mock if real API doesn't work
    if not api_works:
        if setup_local_mock():
            logger.info("Set up local mock for Storacha")
            
            # Set environment variable to indicate mock mode
            os.environ["STORACHA_MOCK_MODE"] = "true"
            
            return True
        else:
            logger.error("Failed to set up Storacha integration")
            return False
    
    logger.info("Storacha integration setup complete!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)