"""
Setup script for IPFS Kit to ensure binaries are installed and configured.
"""

import os
import platform
import shutil
import subprocess
import logging
import sys

# It's better to place imports at the top level
try:
    from ipfs_kit_py.ipfs_cluster_service import ipfs_cluster_service
    from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow
except ImportError:
    # Add handling for when the script is run in a way that modules are not found
    # This can happen in certain testing or execution contexts
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from ipfs_kit_py.ipfs_cluster_service import ipfs_cluster_service
    from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow


logger = logging.getLogger(__name__)

class SetupManager:
    """Manages the setup of IPFS Kit binaries and configurations."""

    def __init__(self, bin_dir="/usr/local/bin", disabled_components=None):
        self.bin_dir = bin_dir
        self.system = platform.system().lower()
        self.disabled_components = disabled_components or []

    def run_setup(self):
        """Run the full setup process."""
        self.install_ipfs()
        self.install_lassie()
        self.configure_ipfs()
        
        # Only start cluster services if not disabled
        if "ipfs_cluster" not in self.disabled_components:
            self.start_ipfs_cluster_service()
        else:
            logger.info("Skipping IPFS Cluster service - disabled for this role")
            
        if "ipfs_cluster_follow" not in self.disabled_components:
            self.start_ipfs_cluster_follow()
        else:
            logger.info("Skipping IPFS Cluster Follow service - disabled for this role")

    def install_ipfs(self):
        """Install the IPFS binary if it's not already installed."""
        if self._is_binary_installed("ipfs"):
            logger.info("IPFS is already installed.")
            return

        logger.info("Installing IPFS...")
        try:
            if self.system == "linux":
                subprocess.run(["sudo", "snap", "install", "ipfs"], check=True)
            elif self.system == "darwin":
                subprocess.run(["brew", "install", "ipfs"], check=True)
            else:
                logger.error(f"Unsupported system for IPFS installation: {self.system}")
                return
            logger.info("IPFS installed successfully.")
        except Exception as e:
            logger.error(f"Failed to install IPFS: {e}")

    def install_lassie(self):
        """Install the Lassie binary if it's not already installed."""
        if self._is_binary_installed("lassie"):
            logger.info("Lassie is already installed.")
            return

        logger.info("Installing Lassie...")
        try:
            if self.system == "linux":
                # Assuming a deb package is available
                subprocess.run(["sudo", "apt-get", "install", "-y", "lassie"], check=True)
            elif self.system == "darwin":
                subprocess.run(["brew", "install", "lassie"], check=True)
            else:
                logger.error(f"Unsupported system for Lassie installation: {self.system}")
                return
            logger.info("Lassie installed successfully.")
        except Exception as e:
            logger.error(f"Failed to install Lassie: {e}")

    def configure_ipfs(self):
        """Configure IPFS if it's not already configured."""
        ipfs_repo_path = os.path.expanduser("~/.ipfs")
        if os.path.exists(ipfs_repo_path):
            logger.info("IPFS is already configured.")
            return

        logger.info("Configuring IPFS...")
        try:
            subprocess.run(["ipfs", "init"], check=True)
            logger.info("IPFS configured successfully.")
        except Exception as e:
            logger.error(f"Failed to configure IPFS: {e}")

    def start_ipfs_cluster_service(self):
        """Start the IPFS Cluster service daemon."""
        logger.info("Starting IPFS Cluster service...")
        try:
            cluster_service = ipfs_cluster_service()
            result = cluster_service.ipfs_cluster_service_start()
            if result.get("success"):
                logger.info("IPFS Cluster service started successfully.")
            else:
                logger.error(f"Failed to start IPFS Cluster service: {result.get('error')}")
        except Exception as e:
            logger.error(f"An error occurred while starting IPFS Cluster service: {e}")

    def start_ipfs_cluster_follow(self):
        """Start the IPFS Cluster Follow daemon."""
        logger.info("Starting IPFS Cluster Follow service...")
        try:
            cluster_follow = ipfs_cluster_follow(metadata={"cluster_name": "ipfs_kit_cluster"})
            # Initialize first, in case it's not.
            cluster_follow.ipfs_follow_init(
                cluster_name="ipfs_kit_cluster",
                bootstrap_peer="/ip4/127.0.0.1/tcp/9096/p2p/12D3KooWSipNgSzxfHJLBUVBwxih8yYzFzJ6e5WrrUVPbNRBgXXu"
            )
            result = cluster_follow.ipfs_follow_start(cluster_name="ipfs_kit_cluster")
            if result.get("success"):
                logger.info("IPFS Cluster Follow service started successfully.")
            else:
                logger.error(f"Failed to start IPFS Cluster Follow service: {result.get('error')}")
        except Exception as e:
            logger.error(f"An error occurred while starting IPFS Cluster Follow service: {e}")

    def _is_binary_installed(self, binary_name):
        """Check if a binary is installed and in the PATH."""
        return shutil.which(binary_name) is not None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_manager = SetupManager()
    setup_manager.run_setup()
