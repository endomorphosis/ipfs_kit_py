#!/usr/bin/env python3
"""
Install and configure IPFS cluster backends
===========================================

This script will install and configure the IPFS cluster tools needed
for the ipfs_cluster and ipfs_cluster_follow storage backends.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add project root to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import the install_ipfs module
from ipfs_kit_py.install_ipfs import install_ipfs

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def install_cluster_backends():
    """Install and configure IPFS cluster backends."""
    
    print("🚀 Installing IPFS Cluster backends...")
    print("=" * 50)
    
    # Initialize the installer
    installer = install_ipfs()
    
    try:
        # Install IPFS cluster service
        print("\n📦 Installing IPFS Cluster Service...")
        cluster_service_result = installer.install_ipfs_cluster_service()
        if cluster_service_result:
            print("✅ IPFS Cluster Service installed successfully")
        else:
            print("❌ Failed to install IPFS Cluster Service")
            
        # Install IPFS cluster control
        print("\n📦 Installing IPFS Cluster Control...")
        cluster_ctl_result = installer.install_ipfs_cluster_ctl()
        if cluster_ctl_result:
            print("✅ IPFS Cluster Control installed successfully")
        else:
            print("❌ Failed to install IPFS Cluster Control")
            
        # Install IPFS cluster follow
        print("\n📦 Installing IPFS Cluster Follow...")
        cluster_follow_result = installer.install_ipfs_cluster_follow()
        if cluster_follow_result:
            print("✅ IPFS Cluster Follow installed successfully")
        else:
            print("❌ Failed to install IPFS Cluster Follow")
            
        print("\n⚙️ Configuring IPFS Cluster Service...")
        cluster_service_config = installer.config_ipfs_cluster_service()
        if cluster_service_config:
            print("✅ IPFS Cluster Service configured successfully")
        else:
            print("❌ Failed to configure IPFS Cluster Service")
            
        print("\n⚙️ Configuring IPFS Cluster Follow...")
        cluster_follow_config = installer.config_ipfs_cluster_follow()
        if cluster_follow_config:
            print("✅ IPFS Cluster Follow configured successfully")
        else:
            print("❌ Failed to configure IPFS Cluster Follow")
            
        print("\n✨ Installation and configuration complete!")
        print("\nYou can now use the ipfs_cluster and ipfs_cluster_follow storage backends.")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during installation: {e}")
        print(f"❌ Installation failed: {e}")
        return False

if __name__ == "__main__":
    success = install_cluster_backends()
    sys.exit(0 if success else 1)
