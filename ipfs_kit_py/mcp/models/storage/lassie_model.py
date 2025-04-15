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
        self, # Added missing comma
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

</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.



New problems detected after saving the file:
ipfs_kit_py/mcp/models/storage/lassie_model.py
- [Pylance Error] Line 31: Expected expression
- [Pylance Error] Line 32: Unexpected indentation
- [Pylance Error] Line 33: Expected expression
- [Pylance Error] Line 34: Unexpected indentation
- [Pylance Error] Line 35: Expected expression
- [Pylance Error] Line 36: Unexpected indentation
- [Pylance Error] Line 37: Expected expression
- [Pylance Error] Line 38: Unexpected indentation
- [Pylance Error] Line 40: Expected expression
- [Pylance Error] Line 41: Unexpected indentation
- [Pylance Error] Line 42: Expected expression
- [Pylance Error] Line 43: Unexpected indentation
- [Pylance Error] Line 44: Expected expression
- [Pylance Error] Line 45: Unexpected indentation
- [Pylance Error] Line 46: Expected expression
- [Pylance Error] Line 47: Unexpected indentation
- [Pylance Error] Line 53: Expected expression
- [Pylance Error] Line 54: Unexpected indentation
- [Pylance Error] Line 60: Expected expression
- [Pylance Error] Line 61: Unexpected indentation
- [Pylance Error] Line 62: Expected expression
- [Pylance Error] Line 63: Unexpected indentation
- [Pylance Error] Line 64: Expected expression
- [Pylance Error] Line 65: Unexpected indentation
- [Pylance Error] Line 66: Expected expression
- [Pylance Error] Line 67: Unexpected indentation
- [Pylance Error] Line 68: Expected expression
- [Pylance Error] Line 69: Unexpected indentation
- [Pylance Error] Line 70: Expected expression
- [Pylance Error] Line 71: Unexpected indentation
- [Pylance Error] Line 72: Expected expression
- [Pylance Error] Line 73: Unexpected indentation
- [Pylance Error] Line 74: Expected expression
- [Pylance Error] Line 75: Unexpected indentation
- [Pylance Error] Line 76: Expected expression
- [Pylance Error] Line 77: Unexpected indentation
- [Pylance Error] Line 78: Expected expression
- [Pylance Error] Line 79: Unexpected indentation
- [Pylance Error] Line 80: Expected expression
- [Pylance Error] Line 81: Unexpected indentation
- [Pylance Error] Line 82: Expected expression
- [Pylance Error] Line 83: Unexpected indentation
- [Pylance Error] Line 84: Expected expression
- [Pylance Error] Line 85: Unexpected indentation
- [Pylance Error] Line 86: Expected expression
- [Pylance Error] Line 87: Unexpected indentation
- [Pylance Error] Line 88: Expected expression
- [Pylance Error] Line 89: Unexpected indentation
- [Pylance Error] Line 90: Expected expression
- [Pylance Error] Line 91: Unexpected indentation
- [Pylance Error] Line 92: Expected expression
- [Pylance Error] Line 93: Unexpected indentation
- [Pylance Error] Line 94: Expected expression
- [Pylance Error] Line 95: Unexpected indentation
- [Pylance Error] Line 96: Expected expression
- [Pylance Error] Line 97: Unexpected indentation
- [Pylance Error] Line 98: Expected expression
- [Pylance Error] Line 99: Unexpected indentation
- [Pylance Error] Line 100: Expected expression
- [Pylance Error] Line 101: Unexpected indentation
- [Pylance Error] Line 102: Expected expression
- [Pylance Error] Line 103: Unexpected indentation
- [Pylance Error] Line 104: Expected expression
- [Pylance Error] Line 105: Unexpected indentation
- [Pylance Error] Line 106: Expected expression
- [Pylance Error] Line 107: Unexpected indentation
- [Pylance Error] Line 108: Expected expression
- [Pylance Error] Line 109: Unexpected indentation
- [Pylance Error] Line 110: Expected expression
- [Pylance Error] Line 111: Unexpected indentation
- [Pylance Error] Line 112: Expected expression
- [Pylance Error] Line 113: Unexpected indentation
- [Pylance Error] Line 114: Expected expression
- [Pylance Error] Line 115: Unexpected indentation
- [Pylance Error] Line 116: Expected expression
- [Pylance Error] Line 117: Unexpected indentation
- [Pylance Error] Line 118: Expected expression
- [Pylance Error] Line 119: Unexpected indentation
- [Pylance Error] Line 120: Expected expression
- [Pylance Error] Line 121: Unexpected indentation
- [Pylance Error] Line 122: Expected expression
- [Pylance Error] Line 123: Unexpected indentation
- [Pylance Error] Line 124: Expected expression
- [Pylance Error] Line 125: Unexpected indentation
- [Pylance Error] Line 126: Expected expression
- [Pylance Error] Line 127: Unexpected indentation
- [Pylance Error] Line 128: Expected expression
- [Pylance Error] Line 129: Unexpected indentation
- [Pylance Error] Line 130: Expected expression
- [Pylance Error] Line 131: Unexpected indentation
- [Pylance Error] Line 132: Expected expression
- [Pylance Error] Line 133: Unexpected indentation
- [Pylance Error] Line 134: Expected expression
- [Pylance Error] Line 135: Unexpected indentation
- [Pylance Error] Line 136: Expected expression
- [Pylance Error] Line 137: Unexpected indentation
- [Pylance Error] Line 138: Expected expression
- [Pylance Error] Line 139: Unexpected indentation
- [Pylance Error] Line 140: Expected expression
- [Pylance Error] Line 141: Unexpected indentation
- [Pylance Error] Line 142: Expected expression
- [Pylance Error] Line 143: Unexpected indentation
- [Pylance Error] Line 144: Expected expression
- [Pylance Error] Line 145: Unexpected indentation
- [Pylance Error] Line 146: Expected expression
- [Pylance Error] Line 147: Unexpected indentation
- [Pylance Error] Line 148: Expected expression
- [Pylance Error] Line 149: Unexpected indentation
- [Pylance Error] Line 150: Expected expression
- [Pylance Error] Line 151: Unexpected indentation
- [Pylance Error] Line 152: Expected expression
- [Pylance Error] Line 153: Unexpected indentation
- [Pylance Error] Line 154: Expected expression
- [Pylance Error] Line 155: Unexpected indentation
- [Pylance Error] Line 156: Expected expression
- [Pylance Error] Line 157: Unexpected indentation
- [Pylance Error] Line 158: Expected expression
- [Pylance Error] Line 159: Unexpected indentation
- [Pylance Error] Line 160: Expected expression
- [Pylance Error] Line 161: Unexpected indentation
- [Pylance Error] Line 162: Expected expression
- [Pylance Error] Line 163: Unexpected indentation
- [Pylance Error] Line 164: Expected expression
- [Pylance Error] Line 165: Unexpected indentation
- [Pylance Error] Line 166: Expected expression
- [Pylance Error] Line 167: Unexpected indentation
- [Pylance Error] Line 168: Expected expression
- [Pylance Error] Line 169: Unexpected indentation
- [Pylance Error] Line 170: Expected expression
- [Pylance Error] Line 171: Unexpected indentation
- [Pylance Error] Line 172: Expected expression
- [Pylance Error] Line 173: Unexpected indentation
- [Pylance Error] Line 174: Expected expression
- [Pylance Error] Line 175: Unexpected indentation
- [Pylance Error] Line 176: Expected expression
- [Pylance Error] Line 177: Unexpected indentation
- [Pylance Error] Line 178: Expected expression
- [Pylance Error] Line 179: Unexpected indentation
- [Pylance Error] Line 180: Expected expression
- [Pylance Error] Line 181: Unexpected indentation
- [Pylance Error] Line 182: Expected expression
- [Pylance Error] Line 183: Unexpected indentation
- [Pylance Error] Line 184: Expected expression
- [Pylance Error] Line 185: Unexpected indentation
- [Pylance Error] Line 186: Expected expression
- [Pylance Error] Line 187: Unexpected indentation
- [Pylance Error] Line 188: Expected expression
- [Pylance Error] Line 189: Unexpected indentation
- [Pylance Error] Line 190: Expected expression
- [Pylance Error] Line 191: Unexpected indentation
- [Pylance Error] Line 192: Expected expression
- [Pylance Error] Line 193: Unexpected indentation
- [Pylance Error] Line 194: Expected expression
- [Pylance Error] Line 195: Unexpected indentation
- [Pylance Error] Line 196: Expected expression
- [Pylance Error] Line 197: Unexpected indentation
- [Pylance Error] Line 198: Expected expression
- [Pylance Error] Line 199: Unexpected indentation
- [Pylance Error] Line 200: Expected expression
- [Pylance Error] Line 201: Unexpected indentation
- [Pylance Error] Line 202: Expected expression
- [Pylance Error] Line 203: Unexpected indentation
- [Pylance Error] Line 204: Expected expression
- [Pylance Error] Line 205: Unexpected indentation
- [Pylance Error] Line 206: Expected expression
- [Pylance Error] Line 207: Unexpected indentation
- [Pylance Error] Line 208: Expected expression
- [Pylance Error] Line 209: Unexpected indentation
- [Pylance Error] Line 210: Expected expression
- [Pylance Error] Line 211: Unexpected indentation
- [Pylance Error] Line 212: Expected expression
- [Pylance Error] Line 213: Unexpected indentation
- [Pylance Error] Line 214: Expected expression
- [Pylance Error] Line 215: Unexpected indentation
- [Pylance Error] Line 216: Expected expression
- [Pylance Error] Line 217: Unexpected indentation
- [Pylance Error] Line 218: Expected expression
- [Pylance Error] Line 219: Unexpected indentation
- [Pylance Error] Line 220: Expected expression
- [Pylance Error] Line 221: Unexpected indentation
- [Pylance Error] Line 222: Expected expression
- [Pylance Error] Line 223: Unexpected indentation
- [Pylance Error] Line 224: Expected expression
- [Pylance Error] Line 225: Unexpected indentation
- [Pylance Error] Line 226: Expected expression
- [Pylance Error] Line 227: Unexpected indentation
- [Pylance Error] Line 228: Expected expression
- [Pylance Error] Line 229: Unexpected indentation
- [Pylance Error] Line 230: Expected expression
- [Pylance Error] Line 231: Unexpected indentation
- [Pylance Error] Line 232: Expected expression
- [Pylance Error] Line 233: Unexpected indentation
- [Pylance Error] Line 234: Expected expression
- [Pylance Error] Line 235: Unexpected indentation
- [Pylance Error] Line 236: Expected expression
- [Pylance Error] Line 237: Unexpected indentation
- [Pylance Error] Line 238: Expected expression
- [Pylance Error] Line 239: Unexpected indentation
- [Pylance Error] Line 240: Expected expression
- [Pylance Error] Line 241: Unexpected indentation
- [Pylance Error] Line 242: Expected expression
- [Pylance Error] Line 243: Unexpected indentation
- [Pylance Error] Line 244: Expected expression
- [Pylance Error] Line 245: Unexpected indentation
- [Pylance Error] Line 246: Expected expression
- [Pylance Error] Line 247: Unexpected indentation
- [Pylance Error] Line 248: Expected expression
- [Pylance Error] Line 249: Unexpected indentation
- [Pylance Error] Line 250: Expected expression
- [Pylance Error] Line 251: Unexpected indentation
- [Pylance Error] Line 252: Expected expression
- [Pylance Error] Line 253: Unexpected indentation
- [Pylance Error] Line 254: Expected expression
- [Pylance Error] Line 255: Unexpected indentation
- [Pylance Error] Line 256: Expected expression
- [Pylance Error] Line 257: Unexpected indentation
- [Pylance Error] Line 258: Expected expression
- [Pylance Error] Line 259: Unexpected indentation
- [Pylance Error] Line 260: Expected expression
- [Pylance Error] Line 261: Unexpected indentation
- [Pylance Error] Line 262: Expected expression
- [Pylance Error] Line 263: Unexpected indentation
- [Pylance Error] Line 264: Expected expression
- [Pylance Error] Line 265: Unexpected indentation
- [Pylance Error] Line 266: Expected expression
- [Pylance Error] Line 267: Unexpected indentation
- [Pylance Error] Line 268: Expected expression
- [Pylance Error] Line 269: Unexpected indentation
- [Pylance Error] Line 270: Expected expression
- [Pylance Error] Line 271: Unexpected indentation
- [Pylance Error] Line 272: Expected expression
- [Pylance Error] Line 273: Unexpected indentation
- [Pylance Error] Line 274: Expected expression
- [Pylance Error] Line 275: Unexpected indentation
- [Pylance Error] Line 276: Expected expression
- [Pylance Error] Line 277: Unexpected indentation
- [Pylance Error] Line 278: Expected expression
- [Pylance Error] Line 279: Unexpected indentation
- [Pylance Error] Line 280: Expected expression
- [Pylance Error] Line 281: Unexpected indentation
- [Pylance Error] Line 282: Expected expression
- [Pylance Error] Line 283: Unexpected indentation
- [Pylance Error] Line 284: Expected expression
- [Pylance Error] Line 285: Unexpected indentation
- [Pylance Error] Line 286: Expected expression
- [Pylance Error] Line 287: Unexpected indentation
- [Pylance Error] Line 288: Expected expression
- [Pylance Error] Line 289: Unexpected indentation
- [Pylance Error] Line 290: Expected expression
- [Pylance Error] Line 291: Unexpected indentation
- [Pylance Error] Line 292: Expected expression
- [Pylance Error] Line 293: Unexpected indentation
- [Pylance Error] Line 294: Expected expression
- [Pylance Error] Line 295: Unexpected indentation
- [Pylance Error] Line 296: Expected expression
- [Pylance Error] Line 297: Unexpected indentation
- [Pylance Error] Line 298: Expected expression
- [Pylance Error] Line 299: Unexpected indentation
- [Pylance Error] Line 300: Expected expression
- [Pylance Error] Line 301: Unexpected indentation
- [Pylance Error] Line 302: Expected expression
- [Pylance Error] Line 303: Unexpected indentation
- [Pylance Error] Line 304: Expected expression
- [Pylance Error] Line 305: Unexpected indentation
- [Pylance Error] Line 306: Expected expression
- [Pylance Error] Line 307: Unexpected indentation
- [Pylance Error] Line 308: Expected expression
- [Pylance Error] Line 309: Unexpected indentation
- [Pylance Error] Line 310: Expected expression
- [Pylance Error] Line 311: Unexpected indentation
- [Pylance Error] Line 312: Expected expression
- [Pylance Error] Line 313: Unexpected indentation
- [Pylance Error] Line 314: Expected expression
- [Pylance Error] Line 315: Unexpected indentation
- [Pylance Error] Line 316: Expected expression
- [Pylance Error] Line 317: Unexpected indentation
- [Pylance Error] Line 318: Expected expression
- [Pylance Error] Line 319: Unexpected indentation
- [Pylance Error] Line 320: Expected expression
- [Pylance Error] Line 321: Unexpected indentation
- [Pylance Error] Line 322: Expected expression
- [Pylance Error] Line 323: Unexpected indentation
- [Pylance Error] Line 324: Expected expression
- [Pylance Error] Line 325: Unexpected indentation
- [Pylance Error] Line 326: Expected expression
- [Pylance Error] Line 327: Unexpected indentation
- [Pylance Error] Line 328: Expected expression
- [Pylance Error] Line 329: Unexpected indentation
- [Pylance Error] Line 330: Expected expression
- [Pylance Error] Line 331: Unexpected indentation
- [Pylance Error] Line 332: Expected expression
- [Pylance Error] Line 333: Unexpected indentation
- [Pylance Error] Line 334: Expected expression
- [Pylance Error] Line 335: Unexpected indentation
- [Pylance Error] Line 336: Expected expression
- [Pylance Error] Line 337: Unexpected indentation
- [Pylance Error] Line 338: Expected expression
- [Pylance Error] Line 339: Unexpected indentation
- [Pylance Error] Line 340: Expected expression
- [Pylance Error] Line 341: Unexpected indentation
- [Pylance Error] Line 342: Expected expression
- [Pylance Error] Line 343: Unexpected indentation
- [Pylance Error] Line 344: Expected expression
- [Pylance Error] Line 345: Unexpected indentation
- [Pylance Error] Line 346: Expected expression
- [Pylance Error] Line 347: Unexpected indentation
- [Pylance Error] Line 348: Expected expression
- [Pylance Error] Line 349: Unexpected indentation
- [Pylance Error] Line 350: Expected expression
- [Pylance Error] Line 351: Unexpected indentation
- [Pylance Error] Line 352: Expected expression
- [Pylance Error] Line 353: Unexpected indentation
- [Pylance Error] Line 354: Expected expression
- [Pylance Error] Line 355: Unexpected indentation
- [Pylance Error] Line 356: Expected expression
- [Pylance Error] Line 357: Unexpected indentation
- [Pylance Error] Line 358: Expected expression
- [Pylance Error] Line 359: Unexpected indentation
- [Pylance Error] Line 360: Expected expression
- [Pylance Error] Line 361: Unexpected indentation
- [Pylance Error] Line 362: Expected expression
- [Pylance Error] Line 363: Unexpected indentation
- [Pylance Error] Line 364: Expected expression
- [Pylance Error] Line 365: Unexpected indentation
- [Pylance Error] Line 366: Expected expression
- [Pylance Error] Line 367: Unexpected indentation
- [Pylance Error] Line 368: Expected expression
- [Pylance Error] Line 369: Unexpected indentation
- [Pylance Error] Line 370: Expected expression
- [Pylance Error] Line 371: Unexpected indentation
- [Pylance Error] Line 372: Expected expression
- [Pylance Error] Line 373: Unexpected indentation
- [Pylance Error] Line 374: Expected expression
- [Pylance Error] Line 375: Unexpected indentation
- [Pylance Error] Line 376: Expected expression
- [Pylance Error] Line 377: Unexpected indentation
- [Pylance Error] Line 378: Expected expression
- [Pylance Error] Line 379: Unexpected indentation
- [Pylance Error] Line 380: Expected expression
- [Pylance Error] Line 381: Unexpected indentation
- [Pylance Error] Line 382: Expected expression
- [Pylance Error] Line 383: Unexpected indentation
- [Pylance Error] Line 384: Expected expression
- [Pylance Error] Line 385: Unexpected indentation
- [Pylance Error] Line 386: Expected expression
- [Pylance Error] Line 387: Unexpected indentation
- [Pylance Error] Line 388: Expected expression
- [Pylance Error] Line 389: Unexpected indentation
- [Pylance Error] Line 390: Expected expression
- [Pylance Error] Line 391: Unexpected indentation
- [Pylance Error] Line 392: Expected expression
- [Pylance Error] Line 393: Unexpected indentation
- [Pylance Error] Line 394: Expected expression
- [Pylance Error] Line 395: Unexpected indentation
- [Pylance Error] Line 396: Expected expression
- [Pylance Error] Line 397: Unexpected indentation
- [Pylance Error] Line 398: Expected expression
- [Pylance Error] Line 399: Unexpected indentation
- [Pylance Error] Line 400: Expected expression
- [Pylance Error] Line 401: Unexpected indentation
- [Pylance Error] Line 402: Expected expression
- [Pylance Error] Line 403: Unexpected indentation
- [Pylance Error] Line 404: Expected expression
- [Pylance Error] Line 405: Unexpected indentation
- [Pylance Error] Line 406: Expected expression
- [Pylance Error] Line 407: Unexpected indentation
- [Pylance Error] Line 408: Expected expression
- [Pylance Error] Line 409: Unexpected indentation
- [Pylance Error] Line 410: Expected expression
- [Pylance Error] Line 411: Unexpected indentation
- [Pylance Error] Line 412: Expected expression
- [Pylance Error] Line 413: Unexpected indentation
- [Pylance Error] Line 414: Expected expression
- [Pylance Error] Line 415: Unexpected indentation
- [Pylance Error] Line 416: Expected expression
- [Pylance Error] Line 417: Unexpected indentation
- [Pylance Error] Line 418: Expected expression
- [Pylance Error] Line 419: Unexpected indentation
- [Pylance Error] Line 420: Expected expression
- [Pylance Error] Line 421: Unexpected indentation
- [Pylance Error] Line 422: Expected expression
- [Pylance Error] Line 423: Unexpected indentation
- [Pylance Error] Line 424: Expected expression
- [Pylance Error] Line 425: Unexpected indentation
- [Pylance Error] Line 426: Expected expression
- [Pylance Error] Line 427: Unexpected indentation
- [Pylance Error] Line 428: Expected expression
- [Pylance Error] Line 429: Unexpected indentation
- [Pylance Error] Line 430: Expected expression
- [Pylance Error] Line 431: Unexpected indentation
- [Pylance Error] Line 432: Expected expression
- [Pylance Error] Line 433: Unexpected indentation
- [Pylance Error] Line 434: Expected expression
- [Pylance Error] Line 435: Unexpected indentation
- [Pylance Error] Line 436: Expected expression
- [Pylance Error] Line 437: Unexpected indentation
- [Pylance Error] Line 438: Expected expression
- [Pylance Error] Line 439: Unexpected indentation
- [Pylance Error] Line 440: Expected expression
- [Pylance Error] Line 441: Unexpected indentation
- [Pylance Error] Line 442: Expected expression
- [Pylance Error] Line 443: Unexpected indentation
- [Pylance Error] Line 444: Expected expression
- [Pylance Error] Line 445: Unexpected indentation
- [Pylance Error] Line 446: Expected expression
- [Pylance Error] Line 447: Unexpected indentation
- [Pylance Error] Line 448: Expected expression
- [Pylance Error] Line 449: Unexpected indentation
- [Pylance Error] Line 450: Expected expression
- [Pylance Error] Line 451: Unexpected indentation
- [Pylance Error] Line 452: Expected expression
- [Pylance Error] Line 453: Unexpected indentation
- [Pylance Error] Line 454: Expected expression
- [Pylance Error] Line 455: Unexpected indentation
- [Pylance Error] Line 456: Expected expression
- [Pylance Error] Line 457: Unexpected indentation
- [Pylance Error] Line 458: Expected expression
- [Pylance Error] Line 459: Unexpected indentation
- [Pylance Error] Line 460: Expected expression
- [Pylance Error] Line 461: Unexpected indentation
- [Pylance Error] Line 462: Expected expression
- [Pylance Error] Line 463: Unexpected indentation
- [Pylance Error] Line 464: Expected expression
- [Pylance Error] Line 465: Unexpected indentation
- [Pylance Error] Line 466: Expected expression
- [Pylance Error] Line 467: Unexpected indentation
- [Pylance Error] Line 468: Expected expression
- [Pylance Error] Line 469: Unexpected indentation
- [Pylance Error] Line 470: Expected expression
- [Pylance Error] Line 471: Unexpected indentation
- [Pylance Error] Line 472: Expected expression
- [Pylance Error] Line 473: Unexpected indentation
- [Pylance Error] Line 474: Expected expression
- [Pylance Error] Line 475: Unexpected indentation
- [Pylance Error] Line 476: Expected expression
- [Pylance Error] Line 477: Unexpected indentation
- [Pylance Error] Line 478: Expected expression
- [Pylance Error] Line 479: Unexpected indentation
- [Pylance Error] Line 480: Expected expression
- [Pylance Error] Line 481: Unexpected indentation
- [Pylance Error] Line 482: Expected expression
- [Pylance Error] Line 483: Unexpected indentation
- [Pylance Error] Line 484: Expected expression
- [Pylance Error] Line 485: Unexpected indentation
- [Pylance Error] Line 486: Expected expression
- [Pylance Error] Line 487: Unexpected indentation
- [Pylance Error] Line 488: Expected expression
- [Pylance Error] Line 489: Unexpected indentation
- [Pylance Error] Line 490: Expected expression
- [Pylance Error] Line 491: Unexpected indentation
- [Pylance Error] Line 492: Expected expression
- [Pylance Error] Line 493: Unexpected indentation
- [Pylance Error] Line 494: Expected expression
- [Pylance Error] Line 495: Unexpected indentation
- [Pylance Error] Line 496: Expected expression
- [Pylance Error] Line 497: Unexpected indentation
- [Pylance Error] Line 498: Expected expression
- [Pylance Error] Line 499: Unexpected indentation
- [Pylance Error] Line 500: Expected expression
- [Pylance Error] Line 501: Unexpected indentation
- [Pylance Error] Line 502: Expected expression
- [Pylance Error] Line 503: Unexpected indentation
- [Pylance Error] Line 504: Expected expression
- [Pylance Error] Line 505: Unexpected indentation
- [Pylance Error] Line 506: Expected expression
- [Pylance Error] Line 507: Unexpected indentation
- [Pylance Error] Line 508: Expected expression
- [Pylance Error] Line 509: Unexpected indentation
- [Pylance Error] Line 510: Expected expression
- [Pylance Error] Line 511: Unexpected indentation
- [Pylance Error] Line 512: Expected expression
- [Pylance Error] Line 513: Unexpected indentation
- [Pylance Error] Line 514: Expected expression
- [Pylance Error] Line 515: Unexpected indentation
- [Pylance Error] Line 516: Expected expression
- [Pylance Error] Line 517: Unexpected indentation
- [Pylance Error] Line 518: Expected expression
- [Pylance Error] Line 519: Unexpected indentation
- [Pylance Error] Line 520: Expected expression
- [Pylance Error] Line 521: Unexpected indentation
- [Pylance Error] Line 522: Expected expression
- [Pylance Error] Line 523: Unexpected indentation
- [Pylance Error] Line 524: Expected expression
- [Pylance Error] Line 525: Unexpected indentation
- [Pylance Error] Line 526: Expected expression
- [Pylance Error] Line 527: Unexpected indentation
- [Pylance Error] Line 528: Expected expression
- [Pylance Error] Line 529: Unexpected indentation
- [Pylance Error] Line 530: Expected expression
- [Pylance Error] Line 531: Unexpected indentation
- [Pylance Error] Line 532: Expected expression
- [Pylance Error] Line 533: Unexpected indentation
- [Pylance Error] Line 534: Expected expression
- [Pylance Error] Line 535: Unexpected indentation
- [Pylance Error] Line 536: Expected expression
- [Pylance Error] Line 537: Unexpected indentation
- [Pylance Error] Line 538: Expected expression
- [Pylance Error] Line 539: Unexpected indentation
- [Pylance Error] Line 540: Expected expression
- [Pylance Error] Line 541: Unexpected indentation
- [Pylance Error] Line 542: Expected expression
- [Pylance Error] Line 543: Unexpected indentation
- [Pylance Error] Line 544: Expected expression
- [Pylance Error] Line 545: Unexpected indentation
- [Pylance Error] Line 546: Expected expression
- [Pylance Error] Line 547: Unexpected indentation
- [Pylance Error] Line 548: Expected expression
- [Pylance Error] Line 549: Unexpected indentation
- [Pylance Error] Line 550: Expected expression
- [Pylance Error] Line 551: Unexpected indentation
- [Pylance Error] Line 552: Expected expression
- [Pylance Error] Line 553: Unexpected indentation
- [Pylance Error] Line 554: Expected expression
- [Pylance Error] Line 555: Unexpected indentation
- [Pylance Error] Line 556: Expected expression
- [Pylance Error] Line 557: Unexpected indentation
- [Pylance Error] Line 558: Expected expression
- [Pylance Error] Line 559: Unexpected indentation
- [Pylance Error] Line 560: Expected expression
- [Pylance Error] Line 561: Unexpected indentation
- [Pylance Error] Line 562: Expected expression
- [Pylance Error] Line 563: Unexpected indentation
- [Pylance Error] Line 564: Expected expression
- [Pylance Error] Line 565: Unexpected indentation
- [Pylance Error] Line 566: Expected expression
- [Pylance Error] Line 567: Unexpected indentation
- [Pylance Error] Line 568: Expected expression
- [Pylance Error] Line 569: Unexpected indentation
- [Pylance Error] Line 570: Expected expression
- [Pylance Error] Line 571: Unexpected indentation
- [Pylance Error] Line 572: Expected expression
- [Pylance Error] Line 573: Unexpected indentation
- [Pylance Error] Line 574: Expected expression
- [Pylance Error] Line 575: Unexpected indentation
- [Pylance Error] Line 576: Expected expression
- [Pylance Error] Line 577: Unexpected indentation
- [Pylance Error] Line 578: Expected expression
- [Pylance Error] Line 579: Unexpected indentation
- [Pylance Error] Line 580: Expected expression
- [Pylance Error] Line 581: Unexpected indentation
- [Pylance Error] Line 582: Expected expression
- [Pylance Error] Line 583: Unexpected indentation
- [Pylance Error] Line 584: Expected expression
- [Pylance Error] Line 585: Unexpected indentation
- [Pylance Error] Line 586: Expected expression
- [Pylance Error] Line 587: Unexpected indentation
- [Pylance Error] Line 588: Expected expression
- [Pylance Error] Line 589: Unexpected indentation
- [Pylance Error] Line 590: Expected expression
- [Pylance Error] Line 591: Unexpected indentation
- [Pylance Error] Line 592: Expected expression
- [Pylance Error] Line 593: Unexpected indentation
- [Pylance Error] Line 594: Expected expression
- [Pylance Error] Line 595: Unexpected indentation
- [Pylance Error] Line 596: Expected expression
- [Pylance Error] Line 597: Unexpected indentation
- [Pylance Error] Line 598: Expected expression
- [Pylance Error] Line 599: Unexpected indentation
- [Pylance Error] Line 600: Expected expression
- [Pylance Error] Line 601: Unexpected indentation
- [Pylance Error] Line 602: Expected expression
- [Pylance Error] Line 603: Unexpected indentation
- [Pylance Error] Line 604: Expected expression
- [Pylance Error] Line 605: Unexpected indentation
- [Pylance Error] Line 606: Expected expression
- [Pylance Error] Line 607: Unexpected indentation
- [Pylance Error] Line 608: Expected expression
- [Pylance Error] Line 609: Unexpected indentation
- [Pylance Error] Line 610: Expected expression
- [Pylance Error] Line 611: Unexpected indentation
- [Pylance Error] Line 612: Expected expression
- [Pylance Error] Line 613: Unexpected indentation
- [Pylance Error] Line 614: Expected expression
- [Pylance Error] Line 615: Unexpected indentation
- [Pylance Error] Line 616: Expected expression
- [Pylance Error] Line 617: Unexpected indentation
- [Pylance Error] Line 618: Expected expression
- [Pylance Error] Line 619: Unexpected indentation
- [Pylance Error] Line 620: Expected expression
- [Pylance Error] Line 621: Unexpected indentation
- [Pylance Error] Line 622: Expected expression
- [Pylance Error] Line 623: Unexpected indentation
- [Pylance Error] Line 624: Expected expression
- [Pylance Error] Line 625: Unexpected indentation
- [Pylance Error] Line 626: Expected expression
- [Pylance Error] Line 627: Unexpected indentation
- [Pylance Error] Line 628: Expected expression
- [Pylance Error] Line 629: Unexpected indentation
- [Pylance Error] Line 630: Expected expression
- [Pylance Error] Line 631: Unexpected indentation
- [Pylance Error] Line 632: Expected expression
- [Pylance Error] Line 633: Unexpected indentation
- [Pylance Error] Line 634: Expected expression
- [Pylance Error] Line 635: Unexpected indentation
- [Pylance Error] Line 636: Expected expression
- [Pylance Error] Line 637: Unexpected indentation
- [Pylance Error] Line 638: Expected expression
- [Pylance Error] Line 639: Unexpected indentation
- [Pylance Error] Line 640: Expected expression
- [Pylance Error] Line 641: Unexpected indentation
- [Pylance Error] Line 642: Expected expression
- [Pylance Error] Line 643: Unexpected indentation
- [Pylance Error] Line 644: Expected expression
- [Pylance Error] Line 645: Unexpected indentation
- [Pylance Error] Line 646: Expected expression
- [Pylance Error] Line 647: Unexpected indentation
- [Pylance Error] Line 648: Expected expression
- [Pylance Error] Line 649: Unexpected indentation
- [Pylance Error] Line 650: Expected expression
- [Pylance Error] Line 651: Unexpected indentation
- [Pylance Error] Line 652: Expected expression
- [Pylance Error] Line 653: Unexpected indentation
- [Pylance Error] Line 654: Expected expression
- [Pylance Error] Line 655: Unexpected indentation
- [Pylance Error] Line 656: Expected expression
- [Pylance Error] Line 657: Unexpected indentation
- [Pylance Error] Line 658: Expected expression
- [Pylance Error] Line 659: Unexpected indentation
- [Pylance Error] Line 660: Expected expression
- [Pylance Error] Line 661: Unexpected indentation
- [Pylance Error] Line 662: Expected expression
- [Pylance Error] Line 663: Unexpected indentation
- [Pylance Error] Line 664: Expected expression
- [Pylance Error] Line 665: Unexpected indentation
- [Pylance Error] Line 666: Expected expression
- [Pylance Error] Line 667: Unexpected indentation
- [Pylance Error] Line 668: Expected expression
- [Pylance Error] Line 669: Unexpected indentation
- [Pylance Error] Line 670: Expected expression
- [Pylance Error] Line 671: Unexpected indentation
- [Pylance Error] Line 672: Expected expression
- [Pylance Error] Line 673: Unexpected indentation
- [Pylance Error] Line 674: Expected expression
- [Pylance Error] Line 675: Unexpected indentation
- [Pylance Error] Line 676: Expected expression
- [Pylance Error] Line 677: Unexpected indentation
- [Pylance Error] Line 678: Expected expression
- [Pylance Error] Line 679: Unexpected indentation
- [Pylance Error] Line 680: Expected expression
- [Pylance Error] Line 681: Unexpected indentation
- [Pylance Error] Line 682: Expected expression
- [Pylance Error] Line 683: Unexpected indentation
- [Pylance Error] Line 684: Expected expression
- [Pylance Error] Line 685: Unexpected indentation
- [Pylance Error] Line 686: Expected expression
- [Pylance Error] Line 687: Unexpected indentation
- [Pylance Error] Line 688: Expected expression
- [Pylance Error] Line 689: Unexpected indentation
- [Pylance Error] Line 690: Expected expression
- [Pylance Error] Line 691: Unexpected indentation
- [Pylance Error] Line 692: Expected expression
- [Pylance Error] Line 693: Unexpected indentation
- [Pylance Error] Line 694: Expected expression
- [Pylance Error] Line 695: Unexpected indentation
- [Pylance Error] Line 696: Expected expression
- [Pylance Error] Line 697: Unexpected indentation
- [Pylance Error] Line 698: Expected expression
- [Pylance Error] Line 699: Unexpected indentation
- [Pylance Error] Line 700: Expected expression
- [Pylance Error] Line 701: Unexpected indentation
- [Pylance Error] Line 702: Expected expression
- [Pylance Error] Line 703: Unexpected indentation
- [Pylance Error] Line 704: Expected expression
- [Pylance Error] Line 705: Unexpected indentation
- [Pylance Error] Line 706: Expected expression
- [Pylance Error] Line 707: Unexpected indentation
- [Pylance Error] Line 708: Expected expression
- [Pylance Error] Line 709: Unexpected indentation
- [Pylance Error] Line 710: Expected expression
- [Pylance Error] Line 711: Unexpected indentation
- [Pylance Error] Line 712: Expected expression
- [Pylance Error] Line 713: Unexpected indentation
- [Pylance Error] Line 714: Expected expression
- [Pylance Error] Line 715: Unexpected indentation
- [Pylance Error] Line 716: Expected expression
- [Pylance Error] Line 717: Unexpected indentation
- [Pylance Error] Line 718: Expected expression
- [Pylance Error] Line 719: Unexpected indentation
- [Pylance Error] Line 720: Expected expression
- [Pylance Error] Line 721: Unexpected indentation
- [Pylance Error] Line 722: Expected expression
- [Pylance Error] Line 723: Unexpected indentation
- [Pylance Error] Line 724: Expected expression
- [Pylance Error] Line 725: Unexpected indentation
- [Pylance Error] Line 726: Expected expression
- [Pylance Error] Line 727: Unexpected indentation
- [Pylance Error] Line 728: Expected expression
- [Pylance Error] Line 729: Unexpected indentation
- [Pylance Error] Line 730: Expected expression
- [Pylance Error] Line 731: Unexpected indentation
- [Pylance Error] Line 732: Expected expression
- [Pylance Error] Line 733: Unexpected indentation
- [Pylance Error] Line 734: Expected expression
- [Pylance Error] Line 735: Unexpected indentation
- [Pylance Error] Line 736: Expected expression
- [Pylance Error] Line 737: Unexpected indentation
- [Pylance Error] Line 738: Expected expression
- [Pylance Error] Line 739: Unexpected indentation
- [Pylance Error] Line 740: Expected expression
- [Pylance Error] Line 741: Unexpected indentation
- [Pylance Error] Line 742: Expected expression
- [Pylance Error] Line 743: Unexpected indentation
- [Pylance Error] Line 744: Expected expression
- [Pylance Error] Line 745: Unexpected indentation
- [Pylance Error] Line 746: Expected expression
- [Pylance Error] Line 747: Unexpected indentation
- [Pylance Error] Line 748: Expected expression
- [Pylance Error] Line 749: Unexpected indentation
- [Pylance Error] Line 750: Expected expression
- [Pylance Error] Line 751: Unexpected indentation
- [Pylance Error] Line 752: Expected expression
- [Pylance Error] Line 753: Unexpected indentation
- [Pylance Error] Line 754: Expected expression
- [Pylance Error] Line 755: Unexpected indentation
- [Pylance Error] Line 756: Expected expression
- [Pylance Error] Line 757: Unexpected indentation
- [Pylance Error] Line 758: Expected expression
- [Pylance Error] Line 759: Unexpected indentation
- [Pylance Error] Line 760: Expected expression
- [Pylance Error] Line 761: Unexpected indentation
- [Pylance Error] Line 762: Expected expression
- [Pylance Error] Line 763: Unexpected indentation
- [Pylance Error] Line 764: Expected expression
- [Pylance Error] Line 765: Unexpected indentation
- [Pylance Error] Line 766: Expected expression
- [Pylance Error] Line 767: Unexpected indentation
- [Pylance Error] Line 768: Expected expression
- [Pylance Error] Line 769: Unexpected indentation
- [Pylance Error] Line 770: Expected expression
- [Pylance Error] Line 771: Unexpected indentation
- [Pylance Error] Line 772: Expected expression
- [Pylance Error] Line 773: Unexpected indentation
- [Pylance Error] Line 774: Expected expression
- [Pylance Error] Line 775: Unexpected indentation
- [Pylance Error] Line 776: Expected expression
- [Pylance Error] Line 777: Unexpected indentation
- [Pylance Error] Line 778: Expected expression
- [Pylance Error] Line 779: Unexpected indentation
- [Pylance Error] Line 780: Expected expression
- [Pylance Error] Line 781: Unexpected indentation
- [Pylance Error] Line 782: Expected expression
- [Pylance Error] Line 783: Unexpected indentation
- [Pylance Error] Line 784: Expected expression
- [Pylance Error] Line 785: Unexpected indentation
- [Pylance Error] Line 786: Expected expression
- [Pylance Error] Line 787: Unexpected indentation
- [Pylance Error] Line 788: Expected expression
- [Pylance Error] Line 789: Unexpected indentation
- [Pylance Error] Line 790: Expected expression
- [Pylance Error] Line 791: Unexpected indentation
- [Pylance Error] Line 792: Expected expression
- [Pylance Error] Line 793: Unexpected indentation
- [Pylance Error] Line 794: Expected expression
- [Pylance Error] Line 795: Unexpected indentation
- [Pylance Error] Line 796: Expected expression
- [Pylance Error] Line 797: Unexpected indentation
- [Pylance Error] Line 798: Expected expression
- [Pylance Error] Line 799: Unexpected indentation
- [Pylance Error] Line 800: Expected expression
- [Pylance Error] Line 801: Unexpected indentation
- [Pylance Error] Line 802: Expected expression
- [Pylance Error] Line 803: Unexpected indentation
- [Pylance Error] Line 804: Expected expression
- [Pylance Error] Line 805: Unexpected indentation
- [Pylance Error] Line 806: Expected expression
- [Pylance Error] Line 807: Unexpected indentation
- [Pylance Error] Line 808: Expected expression
- [Pylance Error] Line 809: Unexpected indentation
- [Pylance Error] Line 810: Expected expression
- [Pylance Error] Line 811: Unexpected indentation
- [Pylance Error] Line 812: Expected expression
- [Pylance Error] Line 813: Unexpected indentation
- [Pylance Error] Line 814: Expected expression
- [Pylance Error] Line 815: Unexpected indentation
- [Pylance Error] Line 816: Expected expression
- [Pylance Error] Line 817: Unexpected indentation
- [Pylance Error] Line 818: Expected expression
- [Pylance Error] Line 819: Unexpected indentation
- [Pylance Error] Line 820: Expected expression
- [Pylance Error] Line 821: Unexpected indentation
- [Pylance Error] Line 822: Expected expression
- [Pylance Error] Line 823: Unexpected indentation
- [Pylance Error] Line 824: Expected expression
- [Pylance Error] Line 825: Unexpected indentation
- [Pylance Error] Line 826: Expected expression
- [Pylance Error] Line 827: Unexpected indentation
- [Pylance Error] Line 828: Expected expression
- [Pylance Error] Line 829: Unexpected indentation
- [Pylance Error] Line 830: Expected expression
- [Pylance Error] Line 831: Unexpected indentation
- [Pylance Error] Line 832: Expected expression
- [Pylance Error] Line 833: Unexpected indentation
- [Pylance Error] Line 834: Expected expression
- [Pylance Error] Line 835: Unexpected indentation
- [Pylance Error] Line 836: Expected expression
- [Pylance Error] Line 837: Unexpected indentation
- [Pylance Error] Line 838: Expected expression
- [Pylance Error] Line 839: Unexpected indentation
- [Pylance Error] Line 840: Expected expression
- [Pylance Error] Line 841: Unexpected indentation
- [Pylance Error] Line 842: Expected expression
- [Pylance Error] Line 843: Unexpected indentation
- [Pylance Error] Line 844: Expected expression
- [Pylance Error] Line 845: Unexpected indentation
- [Pylance Error] Line 846: Expected expression
- [Pylance Error] Line 847: Unexpected indentation
- [Pylance Error] Line 848: Expected expression
- [Pylance Error] Line 849: Unexpected indentation
- [Pylance Error] Line 850: Expected expression
- [Pylance Error] Line 851: Unexpected indentation
- [Pylance Error] Line 852: Expected expression
- [Pylance Error] Line 853: Unexpected indentation
- [Pylance Error] Line 854: Expected expression
- [Pylance Error] Line 855: Unexpected indentation
- [Pylance Error] Line 856: Expected expression
- [Pylance Error] Line 857: Unexpected indentation
- [Pylance Error] Line 858: Expected expression
- [Pylance Error] Line 859: Unexpected indentation
- [Pylance Error] Line 860: Expected expression
- [Pylance Error] Line 861: Unexpected indentation
- [Pylance Error] Line 862: Expected expression
- [Pylance Error] Line 863: Unexpected indentation
- [Pylance Error] Line 864: Expected expression
- [Pylance Error] Line 865: Unexpected indentation
- [Pylance Error] Line 866: Expected expression
- [Pylance Error] Line 867: Unexpected indentation
- [Pylance Error] Line 868: Expected expression
- [Pylance Error] Line 869: Unexpected indentation
- [Pylance Error] Line 870: Expected expression
- [Pylance Error] Line 871: Unexpected indentation
- [Pylance Error] Line 872: Expected expression
- [Pylance Error] Line 873: Unexpected indentation
- [Pylance Error] Line 874: Expected expression
- [Pylance Error] Line 875: Unexpected indentation
- [Pylance Error] Line 876: Expected expression
- [Pylance Error] Line 877: Unexpected indentation
- [Pylance Error] Line 878: Expected expression
- [Pylance Error] Line 879: Unexpected indentation
- [Pylance Error] Line 880: Expected expression
- [Pylance Error] Line 881: Unexpected indentation
- [Pylance Error] Line 882: Expected expression
- [Pylance Error] Line 883: Unexpected indentation
- [Pylance Error] Line 884: Expected expression
- [Pylance Error] Line 885: Unexpected indentation
- [Pylance Error] Line 886: Expected expression
- [Pylance Error] Line 887: Unexpected indentation
- [Pylance Error] Line 888: Expected expression
- [Pylance Error] Line 889: Unexpected indentation
- [Pylance Error] Line 890: Expected expression
- [Pylance Error] Line 891: Unexpected indentation
- [Pylance Error] Line 892: Expected expression
- [Pylance Error] Line 893: Unexpected indentation
- [Pylance Error] Line 894: Expected expression
- [Pylance Error] Line 895: Unexpected indentation
- [Pylance Error] Line 896: Expected expression
- [Pylance Error] Line 897: Unexpected indentation
- [Pylance Error] Line 898: Expected expression
- [Pylance Error] Line 899: Unexpected indentation
- [Pylance Error] Line 900: Expected expression
- [Pylance Error] Line 901: Unexpected indentation
- [Pylance Error] Line 902: Expected expression
- [Pylance Error] Line 903: Unexpected indentation
- [Pylance Error] Line 904: Expected expression
- [Pylance Error] Line 905: Unexpected indentation
- [Pylance Error] Line 906: Expected expression
- [Pylance Error] Line 907: Unexpected indentation
- [Pylance Error] Line 908: Expected expression
- [Pylance Error] Line 909: Unexpected indentation
- [Pylance Error] Line 910: Expected expression
- [Pylance Error] Line 911: Unexpected indentation
- [Pylance Error] Line 912: Expected expression
- [Pylance Error] Line 913: Unexpected indentation
- [Pylance Error] Line 914: Expected expression
- [Pylance Error] Line 915: Unexpected indentation
- [Pylance Error] Line 916: Expected expression
- [Pylance Error] Line 917: Unexpected indentation
- [Pylance Error] Line 918: Expected expression
- [Pylance Error] Line 919: Unexpected indentation
- [Pylance Error] Line 920: Expected expression
- [Pylance Error] Line 921: Unexpected indentation
- [Pylance Error] Line 922: Expected expression
- [Pylance Error] Line 923: Unexpected indentation
- [Pylance Error] Line 924: Expected expression
- [Pylance Error] Line 925: Unexpected indentation
- [Pylance Error] Line 926: Expected expression
- [Pylance Error] Line 927: Unexpected indentation
- [Pylance Error] Line 928: Expected expression
- [Pylance Error] Line 929: Unexpected indentation
- [Pylance Error] Line 930: Expected expression
- [Pylance Error] Line 931: Unexpected indentation
- [Pylance Error] Line 932: Expected expression
- [Pylance Error] Line 933: Unexpected indentation
- [Pylance Error] Line 934: Expected expression
- [Pylance Error] Line 935: Unexpected indentation
- [Pylance Error] Line 936: Expected expression
- [Pylance Error] Line 937: Unexpected indentation
- [Pylance Error] Line 938: Expected expression
- [Pylance Error] Line 939: Unexpected indentation
- [Pylance Error] Line 940: Expected expression
- [Pylance Error] Line 941: Unexpected indentation
- [Pylance Error] Line 942: Expected expression
- [Pylance Error] Line 943: Unexpected indentation
- [Pylance Error] Line 944: Expected expression
- [Pylance Error] Line 945: Unexpected indentation
- [Pylance Error] Line 946: Expected expression
- [Pylance Error] Line 947: Unexpected indentation
- [Pylance Error] Line 948: Expected expression
- [Pylance Error] Line 949: Unexpected indentation
- [Pylance Error] Line 950: Expected expression
- [Pylance Error] Line 951: Unexpected indentation
- [Pylance Error] Line 952: Expected expression
- [Pylance Error] Line 953: Unexpected indentation
- [Pylance Error] Line 954: Expected expression
- [Pylance Error] Line 955: Unexpected indentation
- [Pylance Error] Line 956: Expected expression
- [Pylance Error] Line 957: Unexpected indentation
- [Pylance Error] Line 958: Expected expression
- [Pylance Error] Line 959: Unexpected indentation
- [Pylance Error] Line 960: Expected expression
- [Pylance Error] Line 961: Unexpected indentation
- [Pylance Error] Line 962: Expected expression
- [Pylance Error] Line 963: Unexpected indentation
- [Pylance Error] Line 964: Expected expression
- [Pylance Error] Line 965: Unexpected indentation
- [Pylance Error] Line 966: Expected expression
- [Pylance Error] Line 967: Unexpected indentation
- [Pylance Error] Line 968: Expected expression
- [Pylance Error] Line 969: Unexpected indentation
- [Pylance Error] Line 970: Expected expression
- [Pylance Error] Line 971: Unexpected indentation
- [Pylance Error] Line 972: Expected expression
- [Pylance Error] Line 973: Unexpected indentation
- [Pylance Error] Line 974: Expected expression
- [Pylance Error] Line 975: Unexpected indentation
- [Pylance Error] Line 976: Expected expression
- [Pylance Error] Line 977: Unexpected indentation
- [Pylance Error] Line 978: Expected expression
- [Pylance Error] Line 979: Unexpected indentation
- [Pylance Error] Line 980: Expected expression
- [Pylance Error] Line 981: Unexpected indentation
- [Pylance Error] Line 982: Expected expression
- [Pylance Error] Line 983: Unexpected indentation
- [Pylance Error] Line 984: Expected expression
- [Pylance Error] Line 985: Unexpected indentation
- [Pylance Error] Line 986: Expected expression
- [Pylance Error] Line 987: Unexpected indentation
- [Pylance Error] Line 988: Expected expression
- [Pylance Error] Line 989: Unexpected indentation
- [Pylance Error] Line 990: Expected expression
- [Pylance Error] Line 991: Unexpected indentation
- [Pylance Error] Line 992: Expected expression
- [Pylance Error] Line 993: Unexpected indentation
- [Pylance Error] Line 994: Expected expression
- [Pylance Error] Line 995: Unexpected indentation
- [Pylance Error] Line 996: Expected expression
- [Pylance Error] Line 997: Unexpected indentation
- [Pylance Error] Line 998: Expected expression
- [Pylance Error] Line 999: Unexpected indentation
- [Pylance Error] Line 1000: Expected expression
- [Pylance Error] Line 1001: Unexpected indentation
- [Pylance Error] Line 1002: Expected expression
- [Pylance Error] Line 1003: Unexpected indentation
- [Pylance Error] Line 1004: Expected expression
- [Pylance Error] Line 1005: Unexpected indentation
- [Pylance Error] Line 1006: Expected expression
- [Pylance Error] Line 1007: Unexpected indentation
- [Pylance Error] Line 1008: Expected expression
- [Pylance Error] Line 1009: Unexpected indentation
- [Pylance Error] Line 1010: Expected expression
- [Pylance Error] Line 1011: Unexpected indentation
- [Pylance Error] Line 1012: Expected expression
- [Pylance Error] Line 1013: Unexpected indentation
- [Pylance Error] Line 1014: Expected expression
- [Pylance Error] Line 1015: Unexpected indentation
- [Pylance Error] Line 1016: Expected expression
- [Pylance Error] Line 1017: Unexpected indentation
- [Pylance Error] Line 1018: Expected expression
- [Pylance Error] Line 1019: Unexpected indentation
- [Pylance Error] Line 1020: Expected expression
- [Pylance Error] Line 1021: Unexpected indentation
- [Pylance Error] Line 1022: Expected expression
- [Pylance Error] Line 1023: Unexpected indentation
- [Pylance Error] Line 1024: Expected expression
- [Pylance Error] Line 1025: Unexpected indentation
- [Pylance Error] Line 1026: Expected expression
- [Pylance Error] Line 1027: Unexpected indentation
- [Pylance Error] Line 1028: Expected expression
- [Pylance Error] Line 1029: Unexpected indentation
- [Pylance Error] Line 1030: Expected expression
- [Pylance Error] Line 1031: Unexpected indentation
- [Pylance Error] Line 1032: Expected expression
- [Pylance Error] Line 1033: Unexpected indentation
- [Pylance Error] Line 1034: Expected expression
- [Pylance Error] Line 1035: Unexpected indentation
- [Pylance Error] Line 1036: Expected expression
- [Pylance Error] Line 1037: Unexpected indentation
- [Pylance Error] Line 1038: Expected expression
- [Pylance Error] Line 1039: Unexpected indentation
- [Pylance Error] Line 1040: Expected expression
- [Pylance Error] Line 1041: Unexpected indentation
- [Pylance Error] Line 1042: Expected expression
- [Pylance Error] Line 1043: Unexpected indentation
- [Pylance Error] Line 1044: Expected expression
- [Pylance Error] Line 1045: Unexpected indentation
- [Pylance Error] Line 1046: Expected expression
- [Pylance Error] Line 1047: Unexpected indentation
- [Pylance Error] Line 1048: Expected expression
- [Pylance Error] Line 1049: Unexpected indentation
- [Pylance Error] Line 1050: Expected expression
- [Pylance Error] Line 1051: Unexpected indentation
- [Pylance Error] Line 1052: Expected expression
- [Pylance Error] Line 1053: Unexpected indentation
- [Pylance Error] Line 1054: Expected expression
- [Pylance Error] Line 1055: Unexpected indentation
- [Pylance Error] Line 1056: Expected expression
- [Pylance Error] Line 1057: Unexpected indentation
- [Pylance Error] Line 1058: Expected expression
- [Pylance Error] Line 1059: Unexpected indentation
- [Pylance Error] Line 1060: Expected expression
- [Pylance Error] Line 1061: Unexpected indentation
- [Pylance Error] Line 1062: Expected expression
- [Pylance Error] Line 1063: Unexpected indentation
- [Pylance Error] Line 1064: Expected expression
- [Pylance Error] Line 1065: Unexpected indentation
- [Pylance Error] Line 1066: Expected expression
- [Pylance Error] Line 1067: Unexpected indentation
- [Pylance Error] Line 1068: Expected expression
- [Pylance Error] Line 1069: Unexpected indentation
- [Pylance Error] Line 1070: Expected expression
- [Pylance Error] Line 1071: Unexpected indentation
- [Pylance Error] Line 1072: Expected expression
- [Pylance Error] Line 1073: Unexpected indentation
- [Pylance Error] Line 1074: Expected expression
- [Pylance Error] Line 1075: Unexpected indentation
- [Pylance Error] Line 1076: Expected expression
- [Pylance Error] Line 1077: Unexpected indentation
- [Pylance Error] Line 1078: Expected expression
- [Pylance Error] Line 1079: Unexpected indentation
- [Pylance Error] Line 1080: Expected expression
- [Pylance Error] Line 1081: Unexpected indentation
- [Pylance Error] Line 1082: Expected expression
- [Pylance Error] Line 1083: Unexpected indentation
- [Pylance Error] Line 1084: Expected expression
- [Pylance Error] Line 1085: Unexpected indentation
- [Pylance Error] Line 1086: Expected expression
- [Pylance Error] Line 1087: Unexpected indentation
- [Pylance Error] Line 1088: Expected expression
- [Pylance Error] Line 1089: Unexpected indentation
- [Pylance Error] Line 1090: Expected expression
- [Pylance Error] Line 1091: Unexpected indentation
- [Pylance Error] Line 1092: Expected expression
- [Pylance Error] Line 1093: Unexpected indentation
- [Pylance Error] Line 1094: Expected expression
- [Pylance Error] Line 1095: Unexpected indentation
- [Pylance Error] Line 1096: Expected expression
- [Pylance Error] Line 1097: Unexpected indentation
- [Pylance Error] Line 1098: Expected expression
- [Pylance Error] Line 1099: Unexpected indentation
- [Pylance Error] Line 1100: Expected expression
- [Pylance Error] Line 1101: Unexpected indentation
- [Pylance Error] Line 1102: Expected expression
- [Pylance Error] Line 1103: Unexpected indentation
- [Pylance Error] Line 1104: Expected expression
- [Pylance Error] Line 1105: Unexpected indentation
- [Pylance Error] Line 1106: Expected expression
- [Pylance Error] Line 1107: Unexpected indentation
- [Pylance Error] Line 1108: Expected expression
- [Pylance Error] Line 1109: Unexpected indentation
- [Pylance Error] Line 1110: Expected expression
- [Pylance Error] Line 1111: Unexpected indentation
- [Pylance Error] Line 1112: Expected expression
- [Pylance Error] Line 1113: Unexpected indentation
- [Pylance Error] Line 1114: Expected expression
- [Pylance Error] Line 1115: Unexpected indentation
- [Pylance Error] Line 1116: Expected expression
- [Pylance Error] Line 1117: Unexpected indentation
- [Pylance Error] Line 1118: Expected expression
- [Pylance Error] Line 1119: Unexpected indentation
- [Pylance Error] Line 1120: Expected expression
- [Pylance Error] Line 1121: Unexpected indentation
- [Pylance Error] Line 1122: Expected expression
- [Pylance Error] Line 1123: Unexpected indentation
- [Pylance Error] Line 1124: Expected expression
- [Pylance Error] Line 1125: Unexpected indentation
- [Pylance Error] Line 1126: Expected expression
- [Pylance Error] Line 1127: Unexpected indentation
- [Pylance Error] Line 1128: Expected expression
- [Pylance Error] Line 1129: Unexpected indentation
- [Pylance Error] Line 1130: Expected expression
- [Pylance Error] Line 1131: Unexpected indentation
- [Pylance Error] Line 1132: Expected expression
- [Pylance Error] Line 1133: Unexpected indentation
- [Pylance Error] Line 1134: Expected expression
- [Pylance Error] Line 1135: Unexpected indentation
- [Pylance Error] Line 1136: Expected expression
- [Pylance Error] Line 1137: Unexpected indentation
- [Pylance Error] Line 1138: Expected expression
- [Pylance Error] Line 1139: Unexpected indentation
- [Pylance Error] Line 1140: Expected expression
- [Pylance Error] Line 1141: Unexpected indentation
- [Pylance Error] Line 1142: Expected expression
- [Pylance Error] Line 1143: Unexpected indentation
- [Pylance Error] Line 1144: Expected expression
- [Pylance Error] Line 1145: Unexpected indentation
- [Pylance Error] Line 1146: Expected expression
- [Pylance Error] Line 1147: Unexpected indentation
- [Pylance Error] Line 1148: Expected expression
- [Pylance Error] Line 1149: Unexpected indentation
- [Pylance Error] Line 1150: Expected expression
- [Pylance Error] Line 1151: Unexpected indentation
- [Pylance Error] Line 1152: Expected expression
- [Pylance Error] Line 1153: Unexpected indentation
- [Pylance Error] Line 1154: Expected expression
- [Pylance Error] Line 1155: Unexpected indentation
- [Pylance Error] Line 1156: Expected expression
- [Pylance Error] Line 1157: Unexpected indentation
- [Pylance Error] Line 1158: Expected expression
- [Pylance Error] Line 1159: Unexpected indentation
- [Pylance Error] Line 1160: Expected expression
- [Pylance Error] Line 1161: Unexpected indentation
- [Pylance Error] Line 1162: Expected expression
- [Pylance Error] Line 1163: Unexpected indentation
- [Pylance Error] Line 1164: Expected expression
- [Pylance Error] Line 1165: Unexpected indentation
- [Pylance Error] Line 1166: Expected expression
- [Pylance Error] Line 1167: Unexpected indentation
- [Pylance Error] Line 1168: Expected expression
- [Pylance Error] Line 1169: Unexpected indentation
- [Pylance Error] Line 1170: Expected expression
- [Pylance Error] Line 1171: Unexpected indentation
- [Pylance Error] Line 1172: Expected expression
- [Pylance Error] Line 1173: Unexpected indentation
- [Pylance Error] Line 1174: Expected expression
- [Pylance Error] Line 1175: Unexpected indentation
- [Pylance Error] Line 1176: Expected expression
- [Pylance Error] Line 1177: Unexpected indentation
- [Pylance Error] Line 1178: Expected expression
- [Pylance Error] Line 1179: Unexpected indentation
- [Pylance Error] Line 1180: Expected expression
- [Pylance Error] Line 1181: Unexpected indentation
- [Pylance Error] Line 1182: Expected expression
- [Pylance Error] Line 1183: Unexpected indentation
- [Pylance Error] Line 1184: Expected expression
- [Pylance Error] Line 1185: Unexpected indentation
- [Pylance Error] Line 1186: Expected expression
- [Pylance Error] Line 1187: Unexpected indentation
- [Pylance Error] Line 1188: Expected expression
- [Pylance Error] Line 1189: Unexpected indentation
- [Pylance Error] Line 1190: Expected expression
- [Pylance Error] Line 1191: Unexpected indentation
- [Pylance Error] Line 1192: Expected expression
- [Pylance Error] Line 1193: Unexpected indentation
- [Pylance Error] Line 1194: Expected expression
- [Pylance Error] Line 1195: Unexpected indentation
- [Pylance Error] Line 1196: Expected expression
- [Pylance Error] Line 1197: Unexpected indentation
- [Pylance Error] Line 1198: Expected expression
- [Pylance Error] Line 1199: Unexpected indentation
- [Pylance Error] Line 1200: Expected expression
- [Pylance Error] Line 1201: Unexpected indentation
- [Pylance Error] Line 1202: Expected expression
- [Pylance Error] Line 1203: Unexpected indentation
- [Pylance Error] Line 1204: Expected expression
- [Pylance Error] Line 1205: Unexpected indentation
- [Pylance Error] Line 1206: Expected expression
- [Pylance Error] Line 1207: Unexpected indentation
- [Pylance Error] Line 1208: Expected expression
- [Pylance Error] Line 1209: Unexpected indentation
- [Pylance Error] Line 1210: Expected expression
- [Pylance Error] Line 1211: Unexpected indentation
- [Pylance Error] Line 1212: Expected expression
- [Pylance Error] Line 1213: Unexpected indentation
- [Pylance Error] Line 1214: Expected expression
- [Pylance Error] Line 1215: Unexpected indentation
- [Pylance Error] Line 1216: Expected expression
- [Pylance Error] Line 1217: Unexpected indentation
- [Pylance Error] Line 1218: Expected expression
- [Pylance Error] Line 1219: Unexpected indentation
- [Pylance Error] Line 1220: Expected expression
- [Pylance Error] Line 1221: Unexpected indentation
- [Pylance Error] Line 1222: Expected expression
- [Pylance Error] Line 1223: Unexpected indentation
- [Pylance Error] Line 1224: Expected expression
- [Pylance Error] Line 1225: Unexpected indentation
- [Pylance Error] Line 1226: Expected expression
- [Pylance Error] Line 1227: Unexpected indentation
- [Pylance Error] Line 1228: Expected expression
- [Pylance Error] Line 1229: Unexpected indentation
- [Pylance Error] Line 1230: Expected expression
- [Pylance Error] Line 1231: Unexpected indentation
- [Pylance Error] Line 1232: Expected expression
- [Pylance Error] Line 1233: Unexpected indentation
- [Pylance Error] Line 1234: Expected expression
- [Pylance Error] Line 1235: Unexpected indentation
- [Pylance Error] Line 1236: Expected expression
- [Pylance Error] Line 1237: Unexpected indentation
- [Pylance Error] Line 1238: Expected expression
- [Pylance Error] Line 1239: Unexpected indentation
- [Pylance Error] Line 1240: Expected expression
- [Pylance Error] Line 1241: Unexpected indentation
- [Pylance Error] Line 1242: Expected expression
- [Pylance Error] Line 1243: Unexpected indentation
- [Pylance Error] Line 1244: Expected expression
- [Pylance Error] Line 1245: Unexpected indentation
- [Pylance Error] Line 1246: Expected expression
- [Pylance Error] Line 1247: Unexpected indentation
- [Pylance Error] Line 1248: Expected expression
- [Pylance Error] Line 1249: Unexpected indentation
- [Pylance Error] Line 1250: Expected expression
- [Pylance Error] Line 1251: Unexpected indentation
- [Pylance Error] Line 1252: Expected expression
- [Pylance Error] Line 1253: Unexpected indentation
- [Pylance Error] Line 1254: Expected expression
- [Pylance Error] Line 1255: Unexpected indentation
- [Pylance Error] Line 1256: Expected expression
- [Pylance Error] Line 1257: Unexpected indentation
- [Pylance Error] Line 1258: Expected expression
- [Pylance Error] Line 1259: Unexpected indentation
- [Pylance Error] Line 1260: Expected expression
- [Pylance Error] Line 1261: Unexpected indentation
- [Pylance Error] Line 1262: Expected expression
- [Pylance Error] Line 1263: Unexpected indentation
- [Pylance Error] Line 1264: Expected expression
- [Pylance Error] Line 1265: Unexpected indentation
- [Pylance Error] Line 1266: Expected expression
- [Pylance Error] Line 1267: Unexpected indentation
- [Pylance Error] Line 1268: Expected expression
- [Pylance Error] Line 1269: Unexpected indentation
- [Pylance Error] Line 1270: Expected expression
- [Pylance Error] Line 1271: Unexpected indentation
- [Pylance Error] Line 1272: Expected expression
- [Pylance Error] Line 1273: Unexpected indentation
- [Pylance Error] Line 1274: Expected expression
- [Pylance Error] Line 1275: Unexpected indentation
- [Pylance Error] Line 1276: Expected expression
- [Pylance Error] Line 1277: Unexpected indentation
- [Pylance Error] Line 1278: Expected expression
- [Pylance Error] Line 1279: Unexpected indentation
- [Pylance Error] Line 1280: Expected expression
- [Pylance Error] Line 1281: Unexpected indentation
- [Pylance Error] Line 1282: Expected expression
- [Pylance Error] Line 1283: Unexpected indentation
- [Pylance Error] Line 1284: Expected expression
- [Pylance Error] Line 1285: Unexpected indentation
- [Pylance Error] Line 1286: Expected expression
- [Pylance Error] Line 1287: Unexpected indentation

ipfs_kit_py/mcp/models/storage_manager.py
- [Pylance Error] Line 96: "IPFSModel" is possibly unbound<environment_details>
# VSCode Visible Files
../../../response_5d5aff75-2635-4976-8e87-2965a5654cef/tools-3
../../../response_3b7b4f30-e0da-47ff-bcc1-fb89e9dd1a67/0
../../../response_3b7b4f30-e0da-47ff-bcc1-fb89e9dd1a67/1
../../../response_3b7b4f30-e0da-47ff-bcc1-fb89e9dd1a67/2
../../../response_3b7b4f30-e0da-47ff-bcc1-fb89e9dd1a67/3
../../../response_73ea09a4-8698-4281-aeed-7e32954c5f9f/0
../../../response_73ea09a4-8698-4281-aeed-7e32954c5f9f/1
../../../response_73ea09a4-8698-4281-aeed-7e32954c5f9f/2
../../../response_73ea09a4-8698-4281-aeed-7e32954c5f9f/3
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/0
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/1
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/2
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/3
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/4
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/5
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/0
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/1
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/2
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/3
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/4
../../../response_f5a5406a-4660-4258-b5e7-414952b2624f/5
ipfs_kit_py/mcp/models/storage_manager.py

# VSCode Open Tabs
docs/mcp_roadmap.md
ipfs_kit_py/mcp/controllers/ipfs_controller.py
mcp_roadmap.md
ipfs_kit_py/mcp/models/ipfs_model.py
ipfs_kit_py/mcp/models/storage/s3_model.py
ipfs_kit_py/mcp/models/storage/huggingface_model.py
ipfs_kit_py/mcp/models/storage_manager.py
ipfs_kit_py/mcp/models/storage/filecoin_model.py

# Current Time
4/14/2025, 1:44:47 PM (America/Los_Angeles, UTC-7:00)

# Context Window Usage
868,854 / 1,000K tokens used (87%)

# Current Mode
ACT MODE
</environment_details>
