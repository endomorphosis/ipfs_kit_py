#!/usr/bin/env python3
"""
HuggingFace Integration Setup

This script verifies and sets up proper HuggingFace integration for the MCP server.
It checks for the required libraries, validates credentials, and ensures the repository exists.
"""

import os
import sys
import logging
import json
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_huggingface_cli():
    """Check if HuggingFace CLI is installed and configured."""
    try:
        result = subprocess.run(
            ["huggingface-cli", "whoami"], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            logger.info("HuggingFace CLI is properly configured")
            return True
        else:
            logger.warning(f"HuggingFace CLI is not properly configured: {result.stderr}")
            return False
    except FileNotFoundError:
        logger.warning("HuggingFace CLI is not installed")
        return False

def install_huggingface_hub():
    """Install the HuggingFace Hub library."""
    try:
        logger.info("Installing huggingface_hub...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "huggingface_hub"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info("Successfully installed huggingface_hub")
            return True
        else:
            logger.error(f"Failed to install huggingface_hub: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error installing huggingface_hub: {e}")
        return False

def setup_huggingface_login(token=None):
    """Setup HuggingFace login with a token."""
    if not token:
        token = os.environ.get("HUGGINGFACE_TOKEN")
        if not token:
            logger.warning("No HuggingFace token provided")
            return False
    
    # Create token file
    try:
        home_dir = Path.home()
        token_path = home_dir / ".huggingface" / "token"
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        
        with open(token_path, "w") as f:
            f.write(token)
        
        logger.info(f"HuggingFace token saved to {token_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving HuggingFace token: {e}")
        return False

def verify_huggingface_access():
    """Verify access to HuggingFace API."""
    try:
        # First try importing the library
        from huggingface_hub import HfApi
        
        # Initialize API
        api = HfApi()
        
        # Try getting user info
        user_info = api.whoami()
        
        if user_info:
            logger.info(f"Successfully authenticated with HuggingFace as {user_info.get('name')}")
            return True
        else:
            logger.warning("Failed to get user info from HuggingFace")
            return False
    except ImportError:
        logger.error("huggingface_hub library is not installed")
        if install_huggingface_hub():
            # Try again after installation
            return verify_huggingface_access()
        return False
    except Exception as e:
        logger.error(f"Error verifying HuggingFace access: {e}")
        return False

def create_or_verify_repo(repo_name=None, organization=None):
    """Create or verify a HuggingFace repository."""
    if not repo_name:
        repo_name = os.environ.get("HUGGINGFACE_REPO_NAME", "ipfs-storage")
    
    if organization:
        full_repo_name = f"{organization}/{repo_name}"
    else:
        org = os.environ.get("HUGGINGFACE_ORGANIZATION", "")
        if org:
            full_repo_name = f"{org}/{repo_name}"
        else:
            full_repo_name = repo_name
    
    try:
        from huggingface_hub import HfApi, repository_exists
        
        # Initialize API
        api = HfApi()
        
        # Check if repo exists
        if repository_exists(repo_id=full_repo_name, repo_type="dataset"):
            logger.info(f"Repository {full_repo_name} already exists")
            return True
        
        # Create repo if it doesn't exist
        try:
            api.create_repo(
                repo_id=repo_name if not organization else None,
                organization=organization,
                private=True,
                repo_type="dataset",
                exist_ok=True
            )
            logger.info(f"Created repository {full_repo_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating repository {full_repo_name}: {e}")
            return False
    except ImportError:
        logger.error("huggingface_hub library is not installed")
        return False
    except Exception as e:
        logger.error(f"Error checking repository: {e}")
        return False

def main():
    """Main function to setup HuggingFace integration."""
    logger.info("Setting up HuggingFace integration...")
    
    # Load token from environment
    token = os.environ.get("HUGGINGFACE_TOKEN")
    organization = os.environ.get("HUGGINGFACE_ORGANIZATION")
    repo_name = os.environ.get("HUGGINGFACE_REPO_NAME", "ipfs-storage")
    
    # Check if token exists
    if not token:
        logger.warning("No HuggingFace token found in environment")
        logger.info("You can get a token from https://huggingface.co/settings/tokens")
        logger.warning("Skipping HuggingFace setup due to missing token")
        return True
    
    # Install library if needed
    try:
        import huggingface_hub
        logger.info(f"huggingface_hub version {huggingface_hub.__version__} is installed")
    except ImportError:
        if not install_huggingface_hub():
            logger.warning("Failed to install huggingface_hub, skipping HuggingFace setup")
            return True
    
    # Setup login
    if not setup_huggingface_login(token):
        logger.warning("Failed to setup HuggingFace login")
        logger.warning("Skipping HuggingFace setup")
        return True
    
    # Verify access
    if not verify_huggingface_access():
        logger.warning("Failed to verify HuggingFace access")
        logger.warning("Skipping HuggingFace setup")
        return True
    
    # Create or verify repository
    if not create_or_verify_repo(repo_name, organization):
        logger.warning(f"Failed to create or verify repository {repo_name}")
        logger.warning("Skipping HuggingFace repository setup")
        return True
    
    logger.info("HuggingFace integration setup complete!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)