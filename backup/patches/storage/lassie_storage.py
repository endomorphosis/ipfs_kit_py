"""
Enhanced Lassie storage backend implementation for MCP server.

This module provides robust integration with Lassie for retrieving IPFS content,
with improved error handling, fallback mechanisms, and support for well-known CIDs.
"""

import os
import json
import logging
import tempfile
import time
import subprocess
import random
import requests
from typing import Dict, Any, Optional, Union, List, Tuple
import uuid
import shutil

# Configure logging
logger = logging.getLogger(__name__)

# Check if lassie client is available
LASSIE_AVAILABLE = False
LASSIE_PATH = None  # Default to None

try:
    result = subprocess.run(["which", "lassie"], capture_output=True, text=True)
    if result.returncode == 0:
        LASSIE_PATH = result.stdout.strip()
        LASSIE_AVAILABLE = True
        logger.info(f"Found Lassie client at: {LASSIE_PATH}")
    else:
        # Also check in common locations
        common_paths = [
            "/usr/local/bin/lassie",
            "/usr/bin/lassie",
            os.path.expanduser("~/bin/lassie"),
            os.path.expanduser("~/.local/bin/lassie"),
            # Check if we have a local lassie binary in the project
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin/lassie"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin/lassie")
        ]

        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                LASSIE_PATH = path
                LASSIE_AVAILABLE = True
                logger.info(f"Found Lassie client at: {LASSIE_PATH}")
                break

        if not LASSIE_AVAILABLE:
            logger.warning("Lassie client not found in PATH or common locations")
except Exception as e:
    logger.error(f"Error checking for Lassie client: {e}")

# Well-known CIDs that are widely available on the IPFS network
# These can be used for testing when user-created content isn't widely distributed
WELL_KNOWN_CIDS = {
    # IPFS documentation
    "docs": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",

    # Commonly used test files
    "hello_world": "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx",
    "small_text": "QmTkzDwWqPbnAh5YiV5VwcTLnGdwSNsNTn2aDxdXBFca7D/example",

    # Test image file (goes-devnet.car)
    "test_image": "bafybeiegxwlgmoh2yvy6xkdxrjssjqe2ndnlz4nq4ptgkepk3mug5sth4m",

    # Common IPFS directories
    "dir_example": "QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn",

    # CID for the IPFS logo
    "ipfs_logo": "QmRcFsCvTgGrB52UQfQMvb5GsqN2EX6ajC1RSLjp9aHRwg",

    # A small test file hosted by Protocol Labs
    "test_file": "QmeeLUVdiSTTKQqhWqsffYDtNvvvcTfJdotkNyi1KDEJtQ"
}

# Public IPFS gateways for fallback
PUBLIC_GATEWAYS = [
    "https://ipfs.io/ipfs/",
    "https://gateway.ipfs.io/ipfs/",
    "https://cloudflare-ipfs.com/ipfs/",
    "https://dweb.link/ipfs/",
    "https://ipfs.filebase.io/ipfs/",
    "https://w3s.link/ipfs/",
    "https://gateway.pinata.cloud/ipfs/"
]

class EnhancedLassieStorage:
    """
    Enhanced implementation of Lassie storage backend for IPFS content.

    This class provides improved methods to retrieve IPFS content using Lassie,
    with better error handling, fallback mechanisms, and support for well-known CIDs.
    """

    def __init__(self, lassie_path=None, timeout=300, max_retries=3, use_fallbacks=True):
        """
        Initialize the enhanced Lassie storage backend.

        Args:
            lassie_path: Path to the Lassie client binary. If None, will try to find it.
            timeout: Default timeout for Lassie operations in seconds
            max_retries: Maximum number of retry attempts for failed operations
            use_fallbacks: Whether to use fallback mechanisms (public gateways, etc.)
        """
        self.lassie_path = lassie_path or LASSIE_PATH
        self.timeout = timeout
        self.max_retries = max_retries
        self.use_fallbacks = use_fallbacks
        self.mock_mode = os.environ.get("MCP_USE_LASSIE_MOCK", "").lower() in ["true", "1", "yes"]
        self.simulation_mode = not LASSIE_AVAILABLE and not self.mock_mode

        # If we can't find real Lassie or mock mode is forced, use mock mode
        if self.simulation_mode or self.mock_mode:
            logger.info("Using Lassie in mock mode (simulated functionality)")
            self.mock_mode = True
            self.simulation_mode = False

        # Set up mock directory
        if self.mock_mode:
            self._setup_mock_storage()

        # Version info (to be populated later)
        self.version_info = None
        self.features = {}

        # If real Lassie is available, check its version and capabilities
        if not self.mock_mode and self.lassie_path:
            self._check_version_and_capabilities()

    def _setup_mock_storage(self):
        """Set up mock storage directories."""
        try:
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_lassie")
            os.makedirs(mock_dir, exist_ok=True)
            logger.info(f"Set up mock Lassie storage at {mock_dir}")
        except Exception as e:
            logger.error(f"Error setting up mock storage: {e}")

    def _check_version_and_capabilities(self):
        """Check Lassie version and available features."""
        try:
            # Get version info
            version_cmd = subprocess.run(
                [self.lassie_path, "version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if version_cmd.returncode == 0:
                self.version_info = version_cmd.stdout.strip()
                logger.info(f"Lassie version: {self.version_info}")

                # Check available features by parsing help output
                help_cmd = subprocess.run(
                    [self.lassie_path, "fetch", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if help_cmd.returncode == 0:
                    help_text = help_cmd.stdout

                    # Check for various features
                    self.features = {
                        "dry_run": "--dry-run" in help_text,
                        "no_retrieval": "--no-retrieval" in help_text,
                        "output_dir": "--output-dir" in help_text,
                        "timeout": "--timeout" in help_text or "-t" in help_text,
                        "verbose": "--verbose" in help_text
                    }

                    logger.info(f"Detected Lassie features: {self.features}")
            else:
                logger.warning(f"Failed to get Lassie version: {version_cmd.stderr}")
        except Exception as e:
            logger.error(f"Error checking Lassie version and capabilities: {e}")

    def status(self) -> Dict[str, Any]:
        """
        Get the status of the Lassie storage backend.

        Returns:
            Dict containing detailed status information
        """
        status_info = {
            "success": True,
            "available": LASSIE_AVAILABLE or self.mock_mode,
            "simulation": self.simulation_mode,
            "mock": self.mock_mode,
            "timestamp": time.time()
        }

        if self.simulation_mode:
            status_info["message"] = "Running in simulation mode"
            status_info["error"] = "Lassie client not found"
        elif self.mock_mode:
            status_info["message"] = "Running in mock mode"

            # Add mock storage path
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_lassie")
            if os.path.exists(mock_dir):
                status_info["mock_storage_path"] = mock_dir
        else:
            # Test Lassie functionality
            try:
                # Run lassie version command to test the binary
                result = subprocess.run(
                    [self.lassie_path, "version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    status_info["message"] = "Lassie client is available"
                    status_info["version"] = result.stdout.strip()

                    # Add features information if available
                    if self.features:
                        status_info["features"] = self.features
                else:
                    status_info["message"] = "Lassie client returned an error"
                    status_info["error"] = result.stderr.strip()
                    status_info["success"] = False
            except Exception as e:
                status_info["error"] = str(e)
                status_info["success"] = False

        return status_info

    def to_ipfs(self, cid: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve content from the network to IPFS using Lassie with enhanced fallbacks.

        Args:
            cid: Content ID to retrieve
            timeout: Optional timeout for this operation, overrides default

        Returns:
            Dict with retrieval status and detailed information
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Lassie backend is in simulation mode"
            }

        # If in mock mode, simulate Lassie functionality
        if self.mock_mode:
            return self._mock_to_ipfs(cid)

        # First check if it's a well-known CID
        well_known = self._check_if_well_known(cid)
        if well_known:
            logger.info(f"CID {cid} is a well-known CID ({well_known})")

        # Check if content is already in IPFS before trying to retrieve it
        if self._check_already_in_ipfs(cid):
            logger.info(f"CID {cid} is already in IPFS, no need to retrieve")
            return {
                "success": True,
                "message": "Content already available in IPFS",
                "cid": cid,
                "in_ipfs": True,
                "method": "already_available",
                "timestamp": time.time()
            }

        # Create a structured result object that will be updated throughout the process
        result = {
            "success": False,
            "cid": cid,
            "timestamp": time.time(),
            "attempts": [],
            "in_ipfs": False
        }

        # Try retrieving with Lassie first
        attempt_result = self._retrieve_with_lassie(cid, timeout)
        result["attempts"].append({
            "method": "lassie",
            "success": attempt_result.get("success", False),
            "error": attempt_result.get("error") if not attempt_result.get("success", False) else None
        })

        # If Lassie succeeded, we're done
        if attempt_result.get("success", False):
            result.update(attempt_result)
            result["success"] = True
            return result

        # Check error for "no candidates" to trigger fallbacks
        error = attempt_result.get("error", "")
        if "no candidates" in error and self.use_fallbacks:
            logger.info(f"Lassie failed with 'no candidates' for CID {cid}, trying fallbacks")

            # Try IPFS gateway fallback
            gateway_result = self._retrieve_from_gateway(cid)
            result["attempts"].append({
                "method": "gateway",
                "success": gateway_result.get("success", False),
                "error": gateway_result.get("error") if not gateway_result.get("success", False) else None
            })

            if gateway_result.get("success", False):
                result.update(gateway_result)
                result["success"] = True
                return result

            # If gateway fallback failed and it's a well-known CID, try peer-based approach
            if well_known:
                peer_result = self._retrieve_using_ipfs_peers(cid)
                result["attempts"].append({
                    "method": "peer_connect",
                    "success": peer_result.get("success", False),
                    "error": peer_result.get("error") if not peer_result.get("success", False) else None
                })

                if peer_result.get("success", False):
                    result.update(peer_result)
                    result["success"] = True
                    return result

        # If we reach here, all attempts failed
        result["error"] = "All retrieval methods failed"
        result["details"] = "No candidates found and fallback methods were unsuccessful"

        # Provide suggestions for next steps
        result["suggestions"] = [
            "Try with a widely-distributed CID that has active providers",
            "Ensure you have connectivity to the IPFS network",
            "Try a different IPFS daemon or network configuration",
            "Some CIDs may no longer be available on the network"
        ]

        if not well_known:
            result["suggestions"].append(
                "Try with a well-known CID to verify your setup (use /api/v0/lassie/well_known_cids endpoint)"
            )

        return result

    def _mock_to_ipfs(self, cid: str) -> Dict[str, Any]:
        """
        Mock implementation of to_ipfs for testing without a real Lassie client.

        Args:
            cid: Content ID to retrieve

        Returns:
            Dict with mock retrieval results
        """
        try:
            logger.info(f"Mock Lassie: Retrieving CID {cid}")

            # Create a mock storage directory if it doesn't exist
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_lassie")
            os.makedirs(mock_dir, exist_ok=True)

            # Check if the CID is already in IPFS
            is_in_ipfs = self._check_already_in_ipfs(cid)

            # For well-known CIDs, always succeed
            well_known = self._check_if_well_known(cid)

            # If not in IPFS and not well-known, simulate with 70% success rate
            if not is_in_ipfs and not well_known:
                success = random.random() < 0.7

                if not success:
                    # Simulate failure for some CIDs
                    return {
                        "success": False,
                        "mock": True,
                        "cid": cid,
                        "error": "Mock Lassie: Could not retrieve content. No candidates.",
                        "details": "This is a simulated failure in mock mode.",
                        "timestamp": time.time(),
                        "suggestions": [
                            "This is a mock failure - in mock mode, about 30% of retrievals for non-well-known CIDs fail",
                            "Try with a well-known CID (see /api/v0/lassie/well_known_cids endpoint)",
                            "Ensure your content is widely distributed on the network"
                        ]
                    }

            # Create a filename for the mock file
            mock_file = os.path.join(mock_dir, f"{cid}_{int(time.time())}.data")

            # If not in IPFS, simulate a successful retrieval by creating a mock file
            if not is_in_ipfs:
                # Create a mock file with random content
                with open(mock_file, "wb") as f:
                    # Generate 1KB of random data
                    f.write(os.urandom(1024))

                # Add to IPFS
                add_result = subprocess.run(
                    ["ipfs", "add", "-q", mock_file],
                    capture_output=True,
                    text=True
                )

                if add_result.returncode == 0:
                    actual_cid = add_result.stdout.strip()
                    logger.info(f"Mock Lassie: Added mock content with CID {actual_cid} (simulating {cid})")
                    is_in_ipfs = True

            # Generate mock Lassie output
            mock_output = f"""
Fetching {cid}...
Found provider [peer ID]
Connected to provider
Received block {cid}
Fetch completed successfully!
"""

            return {
                "success": True,
                "mock": True,
                "message": "Content retrieved with mock Lassie implementation",
                "cid": cid,
                "in_ipfs": is_in_ipfs,
                "mock_file": mock_file if not is_in_ipfs else None,
                "method": "mock_lassie",
                "well_known": well_known is not None,
                "lassie_output": mock_output,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error in mock Lassie to_ipfs: {e}")
            return {
                "success": False,
                "mock": True,
                "error": str(e)
            }

    def _check_already_in_ipfs(self, cid: str) -> bool:
        """
        Check if content is already available in the local IPFS node.

        Args:
            cid: Content ID to check

        Returns:
            bool: True if content is available, False otherwise
        """
        try:
            # Perform a lightweight check using ipfs block stat
            stat_result = subprocess.run(
                ["ipfs", "block", "stat", cid],
                capture_output=True,
                text=True,
                timeout=5
            )

            return stat_result.returncode == 0
        except Exception as e:
            logger.warning(f"Error checking if CID {cid} is in IPFS: {e}")
            return False

    def _check_if_well_known(self, cid: str) -> Optional[str]:
        """
        Check if a CID is in our list of well-known CIDs.

        Args:
            cid: Content ID to check

        Returns:
            Optional[str]: Name of the well-known CID, or None if not well-known
        """
        # Check in the dictionary values
        for name, known_cid in WELL_KNOWN_CIDS.items():
            if cid == known_cid:
                return name
        return None

    def _retrieve_with_lassie(self, cid: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve content using the Lassie client.

        Args:
            cid: Content ID to retrieve
            timeout: Optional timeout for this operation

        Returns:
            Dict with retrieval results
        """
        try:
            fetch_timeout = timeout or self.timeout
            timeout_str = str(fetch_timeout)

            # Build command based on the features available
            cmd = [self.lassie_path, "fetch"]

            # Add timeout parameter
            if self.features.get("timeout", True):
                cmd.extend(["--timeout", timeout_str])

            # Add verbose mode for better logging
            if self.features.get("verbose", False):
                cmd.append("--verbose")

            # Add the CID last
            cmd.append(cid)

            logger.info(f"Running Lassie command: {' '.join(cmd)}")

            # Execute the Lassie fetch command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=fetch_timeout + 10  # Add a buffer to the timeout
            )

            if result.returncode == 0:
                logger.info(f"Lassie fetch successful for CID {cid}")

                # Check if the content is now in IPFS
                is_in_ipfs = self._check_already_in_ipfs(cid)

                # If not in IPFS but Lassie reported success, try to pin it
                if not is_in_ipfs:
                    logger.warning(f"Lassie fetch was successful but CID {cid} not found in IPFS")
                    # Try an IPFS pin add
                    try:
                        pin_result = subprocess.run(
                            ["ipfs", "pin", "add", cid],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        is_in_ipfs = pin_result.returncode == 0
                    except Exception as pin_err:
                        logger.warning(f"Error trying to pin CID: {pin_err}")

                return {
                    "success": True,
                    "message": "Content retrieved with Lassie",
                    "cid": cid,
                    "in_ipfs": is_in_ipfs,
                    "method": "lassie",
                    "lassie_output": result.stdout.strip(),
                    "timestamp": time.time()
                }
            else:
                logger.error(f"Lassie fetch failed for CID {cid}: {result.stderr}")
                return {
                    "success": False,
                    "error": f"Lassie failed to retrieve content: {result.stderr}"
                }

        except subprocess.TimeoutExpired:
            logger.error(f"Lassie operation timed out for CID {cid}")
            return {
                "success": False,
                "error": f"Lassie operation timed out after {timeout or self.timeout} seconds"
            }
        except Exception as e:
            logger.error(f"Error retrieving content with Lassie: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _retrieve_from_gateway(self, cid: str) -> Dict[str, Any]:
        """
        Try to retrieve content from public IPFS gateways as a fallback.

        Args:
            cid: Content ID to retrieve

        Returns:
            Dict with retrieval results
        """
        logger.info(f"Attempting to retrieve {cid} from public gateways")

        # Try each gateway until one works
        for gateway in PUBLIC_GATEWAYS:
            try:
                url = f"{gateway}{cid}"
                logger.info(f"Trying gateway: {url}")

                # Download from gateway
                response = requests.get(url, timeout=30, stream=True)

                if response.status_code == 200:
                    # Create a temporary file to store the content
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        # Download the content
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                temp_file.write(chunk)
                        temp_path = temp_file.name

                    # Add the content to IPFS
                    add_result = subprocess.run(
                        ["ipfs", "add", "-q", temp_path],
                        capture_output=True,
                        text=True
                    )

                    # Clean up the temporary file
                    os.unlink(temp_path)

                    if add_result.returncode == 0:
                        actual_cid = add_result.stdout.strip()

                        # If the CID from the add operation doesn't match the requested CID,
                        # something is wrong - the gateway might have returned an error page
                        if actual_cid != cid:
                            logger.warning(f"Gateway returned content with different CID: {actual_cid} != {cid}")
                            continue

                        # Pin the content
                        subprocess.run(
                            ["ipfs", "pin", "add", cid],
                            capture_output=True,
                            text=True
                        )

                        logger.info(f"Successfully retrieved {cid} from gateway {gateway}")

                        return {
                            "success": True,
                            "message": "Content retrieved from public gateway",
                            "cid": cid,
                            "in_ipfs": True,
                            "method": "public_gateway",
                            "gateway": gateway,
                            "timestamp": time.time()
                        }
            except Exception as e:
                logger.warning(f"Failed to retrieve from gateway {gateway}: {e}")
                continue

        # If we get here, all gateways failed
        return {
            "success": False,
            "error": "Failed to retrieve from any public gateway",
            "gateways_tried": len(PUBLIC_GATEWAYS)
        }

    def _retrieve_using_ipfs_peers(self, cid: str) -> Dict[str, Any]:
        """
        Try to retrieve content by connecting to specific IPFS peers known to host the content.

        Args:
            cid: Content ID to retrieve

        Returns:
            Dict with retrieval results
        """
        logger.info(f"Attempting to retrieve {cid} using direct peer connections")

        # List of well-known IPFS peers that might have the content
        # These are public IPFS bootstrap nodes and other reliable nodes
        well_known_peers = [
            "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
            "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
            "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
            "/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
            "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
            "/ip4/104.131.131.82/udp/4001/quic/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
        ]

        try:
            # First, try to connect to several peers
            connected_peers = []
            for peer in well_known_peers:
                try:
                    logger.info(f"Connecting to peer {peer}")
                    connect_result = subprocess.run(
                        ["ipfs", "swarm", "connect", peer],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if connect_result.returncode == 0:
                        connected_peers.append(peer)
                        logger.info(f"Connected to peer {peer}")
                except Exception as e:
                    logger.warning(f"Failed to connect to peer {peer}: {e}")

            # If we connected to any peers, try to retrieve the content
            if connected_peers:
                # Try to find providers for the CID
                find_result = subprocess.run(
                    ["ipfs", "dht", "findprovs", cid],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                # Now try to get the content
                get_result = subprocess.run(
                    ["ipfs", "get", cid, "--output=/dev/null"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if get_result.returncode == 0:
                    # Check if content is now in IPFS
                    is_in_ipfs = self._check_already_in_ipfs(cid)

                    if is_in_ipfs:
                        logger.info(f"Successfully retrieved {cid} using peer connections")

                        return {
                            "success": True,
                            "message": "Content retrieved using direct peer connections",
                            "cid": cid,
                            "in_ipfs": True,
                            "method": "peer_connect",
                            "peers_connected": len(connected_peers),
                            "timestamp": time.time()
                        }

                # If we couldn't get the content, but did connect to peers, report partial success
                return {
                    "success": False,
                    "error": "Connected to peers but could not retrieve content",
                    "peers_connected": len(connected_peers)
                }
            else:
                return {
                    "success": False,
                    "error": "Could not connect to any peers"
                }

        except Exception as e:
            logger.error(f"Error during peer-based retrieval for {cid}: {e}")
            return {
                "success": False,
                "error": f"Peer-based retrieval failed: {str(e)}"
            }

    def check_availability(self, cid: str) -> Dict[str, Any]:
        """
        Check if content is available via Lassie without retrieving it.

        Args:
            cid: Content ID to check

        Returns:
            Dict with availability status and detailed information
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Lassie backend is in simulation mode"
            }

        # First check if it's a well-known CID
        well_known = self._check_if_well_known(cid)

        # Check if it's already in IPFS
        if self._check_already_in_ipfs(cid):
            return {
                "success": True,
                "cid": cid,
                "available": True,
                "message": "Content is already in local IPFS node",
                "method": "local_ipfs",
                "well_known": well_known is not None,
                "timestamp": time.time()
            }

        # If in mock mode, simulate availability check
        if self.mock_mode:
            try:
                logger.info(f"Mock Lassie: Checking availability for CID {cid}")

                # For well-known CIDs, always return available
                if well_known:
                    return {
                        "success": True,
                        "mock": True,
                        "cid": cid,
                        "available": True,
                        "message": f"Well-known CID '{well_known}' is available",
                        "method": "mock_lassie",
                        "well_known": True,
                        "timestamp": time.time()
                    }

                # Otherwise, simulate with 70% chance of being available
                is_available = random.random() < 0.7

                return {
                    "success": True,
                    "mock": True,
                    "cid": cid,
                    "available": is_available,
                    "message": "Mock availability check completed",
                    "method": "mock_lassie",
                    "details": "Content is available through mock Lassie" if is_available else "Content not found in mock network",
                    "timestamp": time.time()
                }

            except Exception as e:
                logger.error(f"Error in mock Lassie check_availability: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e)
                }

        try:
            # Use the features detected during initialization to build the command
            cmd = [self.lassie_path, "fetch"]

            # Add dry-run or no-retrieval flag if available
            if self.features.get("dry_run", False):
                cmd.append("--dry-run")
            elif self.features.get("no_retrieval", False):
                cmd.append("--no-retrieval")

            # Add timeout regardless
            if self.features.get("timeout", True):
                cmd.extend(["--timeout", "10"])

            # Add verbose flag if available
            if self.features.get("verbose", False):
                cmd.append("--verbose")

            # Add the CID
            cmd.append(cid)

            logger.info(f"Running availability check with command: {' '.join(cmd)}")

            # Run the availability check
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )

            # Warn if neither dry-run nor no-retrieval is available
            if not self.features.get("dry_run", False) and not self.features.get("no_retrieval", False):
                logger.warning("No dry-run or no-retrieval option available - actual fetch will be performed")

            # Process the result
            if result.returncode == 0:
                # Successfully found availability information
                logger.info(f"Content {cid} appears to be available via Lassie")

                # Combine stdout and stderr for analysis
                output = result.stdout + result.stderr

                # Try to extract more details from the output
                provider_count = output.count("provider")
                connected = "connected" in output.lower()
                block_received = "received block" in output.lower() or "received data" in output.lower()

                return {
                    "success": True,
                    "cid": cid,
                    "available": True,
                    "message": "Content is available for retrieval",
                    "well_known": well_known is not None,
                    "method": "lassie_check",
                    "provider_count": provider_count if provider_count > 0 else None,
                    "connected": connected,
                    "block_received": block_received,
                    "timestamp": time.time()
                }
            else:
                # Failed to find availability - analyze the output
                error_text = result.stderr.lower() if result.stderr else ""
                output_text = result.stdout.lower() if result.stdout else ""

                # Common error patterns that indicate content is not available
                not_available_patterns = [
                    "not found",
                    "not available",
                    "no providers",
                    "could not find",
                    "timeout",
                    "time out",
                    "failed to fetch",
                    "no candidates"
                ]

                # Check if any not-available patterns are in the output
                found_patterns = [pattern for pattern in not_available_patterns
                                 if pattern in error_text or pattern in output_text]

                is_available = len(found_patterns) == 0

                logger.info(f"Content {cid} availability check completed: {'AVAILABLE' if is_available else 'NOT AVAILABLE'}")

                # If it's a well-known CID that should be available, try fallbacks
                if not is_available and well_known and self.use_fallbacks:
                    # Try checking availability through a public gateway
                    gateway_available = self._check_gateway_availability(cid)

                    if gateway_available:
                        return {
                            "success": True,
                            "cid": cid,
                            "available": True,
                            "message": "Content is available through public gateway",
                            "well_known": True,
                            "method": "gateway_check",
                            "lassie_available": False,
                            "gateway_available": True,
                            "timestamp": time.time()
                        }

                # Construct the result for unavailable content
                result_data = {
                    "success": True,  # The check itself succeeded, even if content is unavailable
                    "cid": cid,
                    "available": is_available,
                    "message": "Content availability check completed",
                    "well_known": well_known is not None,
                    "method": "lassie_check",
                    "error_patterns": found_patterns if not is_available else None,
                    "timestamp": time.time()
                }

                # Add the details from stderr or stdout
                if result.stderr:
                    result_data["details"] = result.stderr.strip()
                elif result.stdout:
                    result_data["details"] = result.stdout.strip()

                # If it's not available, add suggestions
                if not is_available:
                    result_data["suggestions"] = [
                        "This CID may not be widely distributed on the network",
                        "Try with a well-known CID to verify your setup (use /api/v0/lassie/well_known_cids endpoint)",
                        "Ensure you have connectivity to the IPFS network"
                    ]

                return result_data

        except Exception as e:
            logger.error(f"Error checking content availability with Lassie: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _check_gateway_availability(self, cid: str) -> bool:
        """
        Check if content is available through public gateways.

        Args:
            cid: Content ID to check

        Returns:
            bool: True if available through any gateway, False otherwise
        """
        logger.info(f"Checking gateway availability for CID {cid}")

        # Try each gateway until one works
        for gateway in PUBLIC_GATEWAYS:
            try:
                url = f"{gateway}{cid}"
                logger.info(f"Checking gateway: {url}")

                # Just check the headers to minimize data transfer
                response = requests.head(url, timeout=10)

                if response.status_code == 200:
                    logger.info(f"Content {cid} is available through gateway {gateway}")
                    return True
            except Exception as e:
                logger.warning(f"Failed to check gateway {gateway}: {e}")
                continue

        logger.info(f"Content {cid} is not available through any gateway")
        return False

    def get_well_known_cids(self) -> Dict[str, Any]:
        """
        Get the list of well-known CIDs that can be used for testing.

        Returns:
            Dict with well-known CIDs information
        """
        result = {
            "success": True,
            "count": len(WELL_KNOWN_CIDS),
            "cids": {},
            "timestamp": time.time()
        }

        # Add all well-known CIDs with descriptions
        for name, cid in WELL_KNOWN_CIDS.items():
            # Check if this CID is in the local IPFS node
            is_local = self._check_already_in_ipfs(cid)

            result["cids"][name] = {
                "cid": cid,
                "in_local_ipfs": is_local
            }

        # Add usage instructions
        result["usage"] = {
            "description": "These well-known CIDs can be used for testing Lassie retrieval",
            "example": f"curl -X POST -F cid={WELL_KNOWN_CIDS['hello_world']} http://localhost:9997/api/v0/lassie/to_ipfs"
        }

        return result
