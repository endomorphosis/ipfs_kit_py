"""
Lassie Model for MCP Server.

This module provides the business logic for Lassie operations in the MCP server.
It relies on the lassie_kit module for underlying functionality.
"""

import logging
import os
import tempfile
import time
from typing import Dict, List, Optional, Any
from ipfs_kit_py.mcp.models.storage import BaseStorageModel

# Configure logger
logger = logging.getLogger(__name__)


class LassieModel(BaseStorageModel):
    """Model for Lassie operations."""
    def __init__(
        self,
        lassie_kit_instance = None,
        ipfs_model = None,
        cache_manager = None,
        credential_manager = None
    ):
        """Initialize Lassie model with dependencies.

        Args:
            lassie_kit_instance: lassie_kit instance for Lassie operations
            ipfs_model: IPFS model for IPFS operations
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
        """
        super().__init__(lassie_kit_instance, cache_manager, credential_manager)

        # Store the lassie_kit instance
        self.lassie_kit = lassie_kit_instance

        # Store the IPFS model for cross-backend operations
        self.ipfs_model = ipfs_model

        # Initialize stats tracking
        self.stats = {
            "successful_operations": 0,
            "failed_operations": 0,
            "bytes_transferred": 0,
            "operations": {},
        }

        logger.info("Lassie Model initialized")

    def check_connection(self) -> Dict[str, Any]:
        """Check connection to the Lassie API.

        Returns:
            Result dictionary with connection status
        """
        start_time = time.time()
        result = self._create_result_dict("check_connection")

        try:
            # Use lassie_kit to check if Lassie is installed
            if self.lassie_kit:
                check_result = self.lassie_kit.check_lassie_installed()

                if check_result.get("success", False) and check_result.get("installed", False):
                    result["success"] = True
                    result["connected"] = True
                    result["version"] = check_result.get("version", "unknown")

                    # Check if this is a simulated result
                    if check_result.get("simulated", False):
                        result["simulated"] = True
                else:
                    result["error"] = check_result.get("error", "Lassie not installed or not working properly")
                    result["error_type"] = "ConnectionError"
            else:
                result["error"] = "Lassie kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about Lassie operations.

        Returns:
            Dictionary containing statistics about Lassie operations
        """
        # Check if Lassie kit has a simulation_mode attribute
        simulation_mode = getattr(self.lassie_kit, "simulation_mode", False)

        # Create statistics result
        stats = {
            "successful_operations": self.stats.get("successful_operations", 0),
            "failed_operations": self.stats.get("failed_operations", 0),
            "bytes_transferred": self.stats.get("bytes_transferred", 0),
            "simulation_mode": simulation_mode,
            "operations": {},
        }

        # Add operation-specific stats
        for operation, count in self.stats.get("operations", {}).items():
            stats["operations"][operation] = count

        return stats

    def fetch_cid(
        self,
        cid: str,
        output_file: Optional[str] = None,
        path: Optional[str] = None,
        block_limit: Optional[int] = None,
        protocols: Optional[List[str]] = None,
        providers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Fetch content by CID from Filecoin/IPFS networks using Lassie.

        Args:
            cid: The CID to fetch
            output_file: Path to write the CAR file to
            path: Optional IPLD path to traverse within the DAG
            block_limit: Maximum number of blocks to retrieve (0 = infinite)
            protocols: List of protocols to use (bitswap, graphsync, http)
            providers: List of provider multiaddrs to use

        Returns:
            Result dictionary with operation results
        """
        start_time = time.time()
        result = self._create_result_dict("fetch_cid")

        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lassie_kit to fetch content
            if self.lassie_kit:
                fetch_result = self.lassie_kit.fetch_cid(
                    cid=cid,
                    output_file=output_file,
                    path=path,
                    block_limit=block_limit,
                    protocols=protocols,
                    providers=providers
                )

                if fetch_result.get("success", False):
                    result["success"] = True
                    result["cid"] = cid

                    # Copy relevant fields
                    if "output_file" in fetch_result:
                        result["output_file"] = fetch_result["output_file"]
                        result["file_size"] = fetch_result.get("file_size", 0)
                    elif "content" in fetch_result:
                        result["content_length"] = fetch_result.get("content_length", 0)

                    # If we have content and no output file, include the content
                    if "content" in fetch_result:
                        result["content"] = fetch_result["content"]
                else:
                    result["error"] = fetch_result.get("error", "Failed to fetch CID")
                    result["error_type"] = fetch_result.get("error_type", "FetchError")
            else:
                result["error"] = "Lassie kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            if result["success"] and result.get("file_size"):
                self._update_stats(result, result["file_size"])
            elif result["success"] and result.get("content_length"):
                self._update_stats(result, result["content_length"])
            else:
                self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def extract_car(self, car_file: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Extract content from a CAR file.

        Args:
            car_file: Path to the CAR file
            output_dir: Directory to extract content to

        Returns:
            Result dictionary with extraction results
        """
        start_time = time.time()
        result = self._create_result_dict("extract_car")

        try:
            # Validate inputs
            if not car_file:
                result["error"] = "CAR file path is required"
                result["error_type"] = "ValidationError"
                return result

            if not os.path.exists(car_file):
                result["error"] = f"CAR file not found: {car_file}"
                result["error_type"] = "FileNotFoundError"
                return result

            # Use lassie_kit to extract the CAR file
            if self.lassie_kit:
                extract_result = self.lassie_kit.extract_car(
                    car_file=car_file, output_dir=output_dir
                )

                if extract_result.get("success", False):
                    result["success"] = True
                    result["car_file"] = car_file
                    result["output_dir"] = extract_result.get("output_dir")

                    # Copy the root CID if available
                    if "root_cid" in extract_result:
                        result["root_cid"] = extract_result["root_cid"]
                else:
                    result["error"] = extract_result.get("error", "Failed to extract CAR file")
                    result["error_type"] = extract_result.get("error_type", "ExtractError")
            else:
                result["error"] = "Lassie kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def retrieve_content(
        self, cid: str, output_file: Optional[str] = None, path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve content by CID.

        Args:
            cid: The CID to retrieve
            output_file: Path to write the result to
            path: Optional IPLD path to traverse within the DAG

        Returns:
            Result dictionary with operation results
        """
        start_time = time.time()
        result = self._create_result_dict("retrieve_content")

        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result

            # Use lassie_kit to retrieve content
            if self.lassie_kit:
                retrieve_result = self.lassie_kit.retrieve_content(
                    cid=cid, output_file=output_file, path=path
                )

                if retrieve_result.get("success", False):
                    result["success"] = True
                    result["cid"] = cid

                    # Copy relevant fields
                    if "output_file" in retrieve_result:
                        result["output_file"] = retrieve_result["output_file"]
                        result["file_size"] = retrieve_result.get("file_size", 0)

                    # If we have content, include it
                    if "content" in retrieve_result:
                        result["content"] = retrieve_result["content"]
                else:
                    result["error"] = retrieve_result.get("error", "Failed to retrieve content")
                    result["error_type"] = retrieve_result.get("error_type", "RetrieveError")
            else:
                result["error"] = "Lassie kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            if result["success"] and "file_size" in result:
                self._update_stats(result, result["file_size"])
            else:
                self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def ipfs_to_lassie(
        self, cid: str, output_file: Optional[str] = None, pin: bool = True
    ) -> Dict[str, Any]:
        """Store IPFS content using Lassie.

        Args:
            cid: Content identifier in IPFS
            output_file: Path to write the retrieved content to
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("ipfs_to_lassie")

        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result

            # Only continue if all dependencies are available
            if not self.lassie_kit:
                result["error"] = "Lassie kit not available"
                result["error_type"] = "DependencyError"
                return result

            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result

            # Create a temporary file if output_file is not provided
            temp_file = None
            if not output_file:
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                output_file = temp_file.name
                temp_file.close()

            # Retrieve content from IPFS
            ipfs_result = self.ipfs_model.get_content(cid)

            if not ipfs_result.get("success", False):
                result["error"] = ipfs_result.get("error", "Failed to retrieve content from IPFS")
                result["error_type"] = ipfs_result.get("error_type", "IPFSGetError")
                result["ipfs_result"] = ipfs_result

                # Clean up temporary file if we created one
                if temp_file:
                    os.unlink(temp_file.name)

                return result

            # Write IPFS content to the output file
            content = ipfs_result.get("data")
            if not content:
                result["error"] = "No content retrieved from IPFS"
                result["error_type"] = "ContentMissingError"
                result["ipfs_result"] = ipfs_result

                # Clean up temporary file if we created one
                if temp_file:
                    os.unlink(temp_file.name)

                return result

            with open(output_file, "wb") as f:
                f.write(content)

            # Pin the content if requested
            if pin:
                pin_result = self.ipfs_model.pin_content(cid)
                if not pin_result.get("success", False):
                    logger.warning(f"Failed to pin content {cid}: {pin_result.get('error')}")

            # Set success and copy relevant fields
            result["success"] = True
            result["ipfs_cid"] = cid
            result["output_file"] = output_file
            result["size_bytes"] = len(content)

            # Update statistics
            self._update_stats(result, len(content))

        except Exception as e:
            self._handle_error(result, e)

            # Clean up temporary file if we created one and an error occurred
            if temp_file:
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def lassie_to_ipfs(self, cid: str, pin: bool = True) -> Dict[str, Any]:
        """Retrieve content from Filecoin/IPFS using Lassie and add to IPFS.

        Args:
            cid: The CID to retrieve
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("lassie_to_ipfs")

        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result

            # Only continue if all dependencies are available
            if not self.lassie_kit:
                result["error"] = "Lassie kit not available"
                result["error_type"] = "DependencyError"
                return result

            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result

            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

            # Retrieve content using Lassie
            lassie_result = self.retrieve_content(cid, temp_path)

            if not lassie_result.get("success", False):
                result["error"] = lassie_result.get("error", "Failed to retrieve content from Lassie")
                result["error_type"] = lassie_result.get("error_type", "LassieRetrieveError")
                result["lassie_result"] = lassie_result

                # Clean up temporary file
                os.unlink(temp_path)

                return result

            # Check if the file exists and has content
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                result["error"] = "No content retrieved from Lassie"
                result["error_type"] = "ContentMissingError"
                result["lassie_result"] = lassie_result

                # Clean up temporary file
                os.unlink(temp_path)

                return result

            # Read the file content
            with open(temp_path, "rb") as f:
                content = f.read()

            # Add to IPFS
            ipfs_result = self.ipfs_model.add_content(content)

            # Clean up the temporary file
            os.unlink(temp_path)

            if not ipfs_result.get("success", False):
                result["error"] = ipfs_result.get("error", "Failed to add content to IPFS")
                result["error_type"] = ipfs_result.get("error_type", "IPFSAddError")
                result["ipfs_result"] = ipfs_result
                return result

            ipfs_cid = ipfs_result.get("cid")

            # Pin the content if requested
            if pin and ipfs_cid:
                pin_result = self.ipfs_model.pin_content(ipfs_cid)
                if not pin_result.get("success", False):
                    logger.warning(f"Failed to pin content {ipfs_cid}: {pin_result.get('error')}")

            # Set success and copy relevant fields
            result["success"] = True
            result["lassie_cid"] = cid
            result["ipfs_cid"] = ipfs_cid
            result["size_bytes"] = len(content)

            # Update statistics
            self._update_stats(result, len(content))

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
