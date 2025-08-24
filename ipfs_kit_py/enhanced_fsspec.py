"""
Enhanced FSSpec implementation with multiple storage backend support.

This module extends the IPFS FSSpec interface to support multiple storage backends
including IPFS, Filecoin (via Lotus), Storacha, and Synapse SDK.
"""

import os
import time
import logging
import asyncio
import tempfile
from typing import Dict, List, Any, Optional, Union, BinaryIO
from pathlib import Path

# Import fsspec
import fsspec
from fsspec.spec import AbstractFileSystem
from fsspec.callbacks import DEFAULT_CALLBACK

logger = logging.getLogger(__name__)


class IPFSFileSystem(AbstractFileSystem):
    """
    Enhanced FSSpec-compatible filesystem supporting multiple storage backends.
    
    Supported backends:
    - ipfs: Direct IPFS client
    - filecoin: Filecoin storage via Lotus
    - storacha: Storacha Web3 storage  
    - synapse: Synapse SDK with PDP verification
    """
    
    protocol = ["ipfs", "filecoin", "storacha", "synapse"]
    
    def __init__(
        self,
        backend: str = "ipfs",
        metadata: Optional[Dict[str, Any]] = None,
        resources: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize the multi-backend filesystem.
        
        Args:
            backend: Storage backend to use ('ipfs', 'filecoin', 'storacha', 'synapse')
            metadata: Backend configuration metadata
            resources: Shared resources dictionary
            **kwargs: Additional arguments for specific backends
        """
        super().__init__(**kwargs)
        
        self.backend = backend
        self.metadata = metadata or {}
        self.resources = resources or {}
        
        # Initialize backend-specific storage interface
        self._initialize_backend()
        
        logger.info(f"Initialized IPFSFileSystem with {backend} backend")
    
    def _initialize_backend(self):
        """Initialize the specified storage backend."""
        
        if self.backend == "ipfs":
            self._initialize_ipfs_backend()
        elif self.backend == "filecoin":
            self._initialize_filecoin_backend()
        elif self.backend == "storacha":
            self._initialize_storacha_backend()
        elif self.backend == "synapse":
            self._initialize_synapse_backend()
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")
    
    def _initialize_ipfs_backend(self):
        """Initialize IPFS backend."""
        try:
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            
            self.ipfs_client = ipfs_kit(
                resources=self.resources,
                metadata=self.metadata
            )
            logger.info("✓ IPFS backend initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize IPFS backend: {e}")
            raise
    
    def _initialize_filecoin_backend(self):
        """Initialize Filecoin backend."""
        try:
            from ipfs_kit_py.lotus_kit import lotus_kit
            
            self.filecoin_client = lotus_kit(
                resources=self.resources,
                metadata=self.metadata
            )
            logger.info("✓ Filecoin backend initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize Filecoin backend: {e}")
            raise
    
    def _initialize_storacha_backend(self):
        """Initialize Storacha backend."""
        try:
            from ipfs_kit_py.storacha_kit import storacha_kit
            
            self.storacha_client = storacha_kit(
                resources=self.resources,
                metadata=self.metadata
            )
            logger.info("✓ Storacha backend initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize Storacha backend: {e}")
            raise
    
    def _initialize_synapse_backend(self):
        """Initialize Synapse SDK backend."""
        try:
            from ipfs_kit_py.synapse_storage import synapse_storage
            
            self.synapse_storage = synapse_storage(
                resources=self.resources,
                metadata=self.metadata
            )
            logger.info("✓ Synapse SDK backend initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize Synapse backend: {e}")
            raise
    
    def _strip_protocol(self, path: str) -> str:
        """Remove protocol prefix from path."""
        for protocol in self.protocol:
            prefix = f"{protocol}://"
            if path.startswith(prefix):
                return path[len(prefix):]
        return path
    
    def _ensure_protocol(self, path: str) -> str:
        """Ensure path has correct protocol prefix."""
        if not any(path.startswith(f"{p}://") for p in self.protocol):
            return f"{self.backend}://{path}"
        return path
    
    # Core FSSpec methods
    
    def ls(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """List directory contents."""
        
        if self.backend == "synapse":
            # For Synapse, list stored data
            return self._ls_synapse(path, detail, **kwargs)
        
        elif self.backend == "ipfs":
            return self._ls_ipfs(path, detail, **kwargs)
        
        elif self.backend == "filecoin":
            return self._ls_filecoin(path, detail, **kwargs)
        
        elif self.backend == "storacha":
            return self._ls_storacha(path, detail, **kwargs)
        
        else:
            raise NotImplementedError(f"ls not implemented for {self.backend}")
    
    def _ls_synapse(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """List Synapse stored data."""
        try:
            # Use async wrapper
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.synapse_storage.synapse_list_stored_data(**kwargs)
                )
            finally:
                loop.close()
            
            if not result.get("success", False):
                logger.error(f"Failed to list Synapse data: {result.get('error', 'Unknown error')}")
                return []
            
            items = []
            for item in result.get("items", []):
                commp = item.get("commp", "")
                filename = item.get("filename", commp[:12] + "...")
                size = item.get("size", 0)
                stored_at = item.get("stored_at", "")
                
                if detail:
                    items.append({
                        "name": filename,
                        "size": size,
                        "type": "file",
                        "commp": commp,
                        "stored_at": stored_at,
                        "path": f"synapse://{commp}"
                    })
                else:
                    items.append(filename)
            
            return items
            
        except Exception as e:
            logger.error(f"Error listing Synapse data: {e}")
            return []
    
    def _ls_ipfs(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """List IPFS directory contents."""
        stripped_path = self._strip_protocol(path)
        
        try:
            result = self.ipfs_client.ipfs_ls_path(stripped_path)
            
            if not result.get("success", False):
                logger.error(f"Failed to list IPFS path {path}: {result.get('error', 'Unknown error')}")
                return []
            
            items = []
            for item in result.get("items", []):
                name = item.get("name", "")
                cid = item.get("hash", "")
                size = item.get("size", 0)
                item_type = "directory" if item.get("type") == 1 else "file"
                
                if detail:
                    items.append({
                        "name": name,
                        "size": size,
                        "type": item_type,
                        "cid": cid,
                        "path": f"ipfs://{cid}"
                    })
                else:
                    items.append(name)
            
            return items
            
        except Exception as e:
            logger.error(f"Error listing IPFS path: {e}")
            return []
    
    def _ls_filecoin(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """List Filecoin storage contents."""
        # Implement Filecoin-specific listing
        logger.warning("Filecoin ls not yet implemented")
        return []
    
    def _ls_storacha(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """List Storacha storage contents."""
        # Implement Storacha-specific listing
        logger.warning("Storacha ls not yet implemented")
        return []
    
    def cat_file(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file contents."""
        
        if self.backend == "synapse":
            return self._cat_file_synapse(path, start, end, **kwargs)
        
        elif self.backend == "ipfs":
            return self._cat_file_ipfs(path, start, end, **kwargs)
        
        elif self.backend == "filecoin":
            return self._cat_file_filecoin(path, start, end, **kwargs)
        
        elif self.backend == "storacha":
            return self._cat_file_storacha(path, start, end, **kwargs)
        
        else:
            raise NotImplementedError(f"cat_file not implemented for {self.backend}")
    
    def _cat_file_synapse(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file from Synapse storage."""
        commp = self._strip_protocol(path)
        
        try:
            # Use async wrapper
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                data = loop.run_until_complete(
                    self.synapse_storage.synapse_retrieve_data(commp, **kwargs)
                )
            finally:
                loop.close()
            
            # Apply range if specified
            if start is not None or end is not None:
                start = start or 0
                end = end or len(data)
                data = data[start:end]
            
            return data
            
        except Exception as e:
            logger.error(f"Error reading Synapse file: {e}")
            raise
    
    def _cat_file_ipfs(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file from IPFS."""
        stripped_path = self._strip_protocol(path)
        
        try:
            result = self.ipfs_client.ipfs_cat_data(stripped_path)
            
            if not result.get("success", False):
                raise IOError(f"Failed to read IPFS file: {result.get('error', 'Unknown error')}")
            
            data = result.get("data", b"")
            
            # Apply range if specified
            if start is not None or end is not None:
                start = start or 0
                end = end or len(data)
                data = data[start:end]
            
            return data
            
        except Exception as e:
            logger.error(f"Error reading IPFS file: {e}")
            raise
    
    def _cat_file_filecoin(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file from Filecoin storage."""
        # Implement Filecoin-specific file reading
        logger.warning("Filecoin cat_file not yet implemented")
        raise NotImplementedError("Filecoin cat_file not yet implemented")
    
    def _cat_file_storacha(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file from Storacha storage."""
        # Implement Storacha-specific file reading
        logger.warning("Storacha cat_file not yet implemented")
        raise NotImplementedError("Storacha cat_file not yet implemented")
    
    def put_file(self, lpath: str, rpath: str, **kwargs) -> None:
        """Upload a local file to storage."""
        
        if self.backend == "synapse":
            self._put_file_synapse(lpath, rpath, **kwargs)
        
        elif self.backend == "ipfs":
            self._put_file_ipfs(lpath, rpath, **kwargs)
        
        elif self.backend == "filecoin":
            self._put_file_filecoin(lpath, rpath, **kwargs)
        
        elif self.backend == "storacha":
            self._put_file_storacha(lpath, rpath, **kwargs)
        
        else:
            raise NotImplementedError(f"put_file not implemented for {self.backend}")
    
    def _put_file_synapse(self, lpath: str, rpath: str, **kwargs) -> None:
        """Upload file to Synapse storage."""
        try:
            # Use async wrapper
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.synapse_storage.synapse_store_file(lpath, **kwargs)
                )
            finally:
                loop.close()
            
            if not result.get("success", False):
                raise IOError(f"Failed to upload to Synapse: {result.get('error', 'Unknown error')}")
            
            logger.info(f"File uploaded to Synapse: {result.get('commp', 'unknown CID')}")
            
        except Exception as e:
            logger.error(f"Error uploading to Synapse: {e}")
            raise
    
    def _put_file_ipfs(self, lpath: str, rpath: str, **kwargs) -> None:
        """Upload file to IPFS."""
        try:
            with open(lpath, 'rb') as f:
                data = f.read()
            
            result = self.ipfs_client.ipfs_add_data(data)
            
            if not result.get("success", False):
                raise IOError(f"Failed to upload to IPFS: {result.get('error', 'Unknown error')}")
            
            logger.info(f"File uploaded to IPFS: {result.get('cid', 'unknown CID')}")
            
        except Exception as e:
            logger.error(f"Error uploading to IPFS: {e}")
            raise
    
    def _put_file_filecoin(self, lpath: str, rpath: str, **kwargs) -> None:
        """Upload file to Filecoin storage."""
        # Implement Filecoin-specific file upload
        logger.warning("Filecoin put_file not yet implemented")
        raise NotImplementedError("Filecoin put_file not yet implemented")
    
    def _put_file_storacha(self, lpath: str, rpath: str, **kwargs) -> None:
        """Upload file to Storacha storage."""
        # Implement Storacha-specific file upload
        logger.warning("Storacha put_file not yet implemented")
        raise NotImplementedError("Storacha put_file not yet implemented")
    
    def get_file(self, rpath: str, lpath: str, **kwargs) -> None:
        """Download a file from storage to local path."""
        
        if self.backend == "synapse":
            self._get_file_synapse(rpath, lpath, **kwargs)
        
        elif self.backend == "ipfs":
            self._get_file_ipfs(rpath, lpath, **kwargs)
        
        elif self.backend == "filecoin":
            self._get_file_filecoin(rpath, lpath, **kwargs)
        
        elif self.backend == "storacha":
            self._get_file_storacha(rpath, lpath, **kwargs)
        
        else:
            raise NotImplementedError(f"get_file not implemented for {self.backend}")
    
    def _get_file_synapse(self, rpath: str, lpath: str, **kwargs) -> None:
        """Download file from Synapse storage."""
        commp = self._strip_protocol(rpath)
        
        try:
            # Use async wrapper
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.synapse_storage.synapse_retrieve_file(commp, lpath, **kwargs)
                )
            finally:
                loop.close()
            
            if not result.get("success", False):
                raise IOError(f"Failed to download from Synapse: {result.get('error', 'Unknown error')}")
            
            logger.info(f"File downloaded from Synapse to: {lpath}")
            
        except Exception as e:
            logger.error(f"Error downloading from Synapse: {e}")
            raise
    
    def _get_file_ipfs(self, rpath: str, lpath: str, **kwargs) -> None:
        """Download file from IPFS."""
        data = self._cat_file_ipfs(rpath, **kwargs)
        
        # Create directory if needed
        os.makedirs(os.path.dirname(lpath), exist_ok=True)
        
        with open(lpath, 'wb') as f:
            f.write(data)
        
        logger.info(f"File downloaded from IPFS to: {lpath}")
    
    def _get_file_filecoin(self, rpath: str, lpath: str, **kwargs) -> None:
        """Download file from Filecoin storage."""
        # Implement Filecoin-specific file download
        logger.warning("Filecoin get_file not yet implemented")
        raise NotImplementedError("Filecoin get_file not yet implemented")
    
    def _get_file_storacha(self, rpath: str, lpath: str, **kwargs) -> None:
        """Download file from Storacha storage."""
        # Implement Storacha-specific file download
        logger.warning("Storacha get_file not yet implemented")
        raise NotImplementedError("Storacha get_file not yet implemented")
    
    def exists(self, path: str, **kwargs) -> bool:
        """Check if a path exists in storage."""
        
        if self.backend == "synapse":
            return self._exists_synapse(path, **kwargs)
        
        elif self.backend == "ipfs":
            return self._exists_ipfs(path, **kwargs)
        
        elif self.backend == "filecoin":
            return self._exists_filecoin(path, **kwargs)
        
        elif self.backend == "storacha":
            return self._exists_storacha(path, **kwargs)
        
        else:
            return False
    
    def _exists_synapse(self, path: str, **kwargs) -> bool:
        """Check if data exists in Synapse storage."""
        commp = self._strip_protocol(path)
        
        try:
            # Use async wrapper
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.synapse_storage.synapse_get_piece_status(commp, **kwargs)
                )
            finally:
                loop.close()
            
            return result.get("success", False) and result.get("exists", False)
            
        except Exception as e:
            logger.error(f"Error checking Synapse existence: {e}")
            return False
    
    def _exists_ipfs(self, path: str, **kwargs) -> bool:
        """Check if path exists in IPFS."""
        try:
            # Try to get info about the path
            stripped_path = self._strip_protocol(path)
            result = self.ipfs_client.ipfs_object_stat(stripped_path)
            return result.get("success", False)
            
        except Exception as e:
            logger.error(f"Error checking IPFS existence: {e}")
            return False
    
    def _exists_filecoin(self, path: str, **kwargs) -> bool:
        """Check if path exists in Filecoin storage."""
        # Implement Filecoin-specific existence check
        logger.warning("Filecoin exists not yet implemented")
        return False
    
    def _exists_storacha(self, path: str, **kwargs) -> bool:
        """Check if path exists in Storacha storage."""
        # Implement Storacha-specific existence check
        logger.warning("Storacha exists not yet implemented")
        return False
    
    def info(self, path: str, **kwargs) -> Dict[str, Any]:
        """Get detailed information about a path."""
        
        if self.backend == "synapse":
            return self._info_synapse(path, **kwargs)
        
        elif self.backend == "ipfs":
            return self._info_ipfs(path, **kwargs)
        
        elif self.backend == "filecoin":
            return self._info_filecoin(path, **kwargs)
        
        elif self.backend == "storacha":
            return self._info_storacha(path, **kwargs)
        
        else:
            return {"name": path, "type": "unknown", "size": 0}
    
    def _info_synapse(self, path: str, **kwargs) -> Dict[str, Any]:
        """Get Synapse storage information."""
        commp = self._strip_protocol(path)
        
        try:
            # Use async wrapper
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.synapse_storage.synapse_get_piece_status(commp, **kwargs)
                )
            finally:
                loop.close()
            
            if result.get("success", False):
                return {
                    "name": commp,
                    "type": "file",
                    "size": result.get("size", 0),
                    "commp": commp,
                    "exists": result.get("exists", False),
                    "proof_set_last_proven": result.get("proof_set_last_proven"),
                    "proof_set_next_proof_due": result.get("proof_set_next_proof_due"),
                    "in_challenge_window": result.get("in_challenge_window", False)
                }
            else:
                return {"name": commp, "type": "file", "size": 0, "exists": False}
                
        except Exception as e:
            logger.error(f"Error getting Synapse info: {e}")
            return {"name": commp, "type": "file", "size": 0, "exists": False}
    
    def _info_ipfs(self, path: str, **kwargs) -> Dict[str, Any]:
        """Get IPFS path information."""
        stripped_path = self._strip_protocol(path)
        
        try:
            result = self.ipfs_client.ipfs_object_stat(stripped_path)
            
            if result.get("success", False):
                return {
                    "name": stripped_path,
                    "type": "file" if result.get("Type") == "file" else "directory",
                    "size": result.get("CumulativeSize", 0),
                    "cid": stripped_path,
                    "hash": result.get("Hash", ""),
                    "links": result.get("NumLinks", 0)
                }
            else:
                return {"name": stripped_path, "type": "unknown", "size": 0}
                
        except Exception as e:
            logger.error(f"Error getting IPFS info: {e}")
            return {"name": stripped_path, "type": "unknown", "size": 0}
    
    def _info_filecoin(self, path: str, **kwargs) -> Dict[str, Any]:
        """Get Filecoin storage information."""
        # Implement Filecoin-specific info
        logger.warning("Filecoin info not yet implemented")
        return {"name": path, "type": "unknown", "size": 0}
    
    def _info_storacha(self, path: str, **kwargs) -> Dict[str, Any]:
        """Get Storacha storage information."""
        # Implement Storacha-specific info
        logger.warning("Storacha info not yet implemented")
        return {"name": path, "type": "unknown", "size": 0}
    
    # Backend-specific utility methods
    
    def get_backend_status(self) -> Dict[str, Any]:
        """Get status of the current backend."""
        
        if self.backend == "synapse":
            return self.synapse_storage.get_status()
        
        elif self.backend == "ipfs":
            # Get IPFS client status
            try:
                result = self.ipfs_client.ipfs_id()
                return {
                    "backend": "ipfs",
                    "connected": result.get("success", False),
                    "peer_id": result.get("ID", ""),
                    "addresses": result.get("Addresses", [])
                }
            except Exception as e:
                return {"backend": "ipfs", "connected": False, "error": str(e)}
        
        elif self.backend == "filecoin":
            # Get Filecoin client status
            return {"backend": "filecoin", "status": "connected"}  # Placeholder
        
        elif self.backend == "storacha":
            # Get Storacha client status
            return {"backend": "storacha", "status": "connected"}  # Placeholder
        
        else:
            return {"backend": self.backend, "status": "unknown"}
    
    def get_backend_config(self) -> Dict[str, Any]:
        """Get configuration for the current backend."""
        
        if self.backend == "synapse":
            return self.synapse_storage.get_configuration()
        
        else:
            return {"backend": self.backend, "metadata": self.metadata}
    
    # Hierarchical Storage Management Methods
    # Import methods from hierarchical_storage_methods.py
    
    def _verify_content_integrity(self, cid):
        """
        Verify content integrity across storage tiers.
        
        This method checks that the content stored in different tiers is identical
        and matches the expected hash.
        
        Args:
            cid: Content identifier to verify
            
        Returns:
            Dictionary with verification results
        """
        import hashlib
        import time
        
        result = {
            "success": True,
            "operation": "verify_content_integrity",
            "cid": cid,
            "timestamp": time.time(),
            "verified_tiers": 0,
            "corrupted_tiers": []
        }
        
        # Get tiers that should contain this content
        tiers = self._get_content_tiers(cid)
        if not tiers:
            result["success"] = False
            result["error"] = f"Content {cid} not found in any tier"
            return result
        
        # Get content from first tier as reference
        reference_tier = tiers[0]
        try:
            reference_content = self._get_from_tier(cid, reference_tier)
            reference_hash = hashlib.sha256(reference_content).hexdigest()
        except Exception as e:
            result["success"] = False
            result["error"] = f"Failed to get reference content from {reference_tier}: {str(e)}"
            return result
        
        # Check content in each tier
        result["verified_tiers"] = 1  # Count reference tier
        
        for tier in tiers[1:]:
            try:
                tier_content = self._get_from_tier(cid, tier)
                tier_hash = hashlib.sha256(tier_content).hexdigest()
                
                if tier_hash != reference_hash:
                    # Content mismatch detected
                    result["corrupted_tiers"].append({
                        "tier": tier,
                        "expected_hash": reference_hash,
                        "actual_hash": tier_hash
                    })
                    result["success"] = False
                else:
                    result["verified_tiers"] += 1
                    
            except Exception as e:
                logger.warning(f"Failed to verify content in tier {tier}: {e}")
                # Don't count this as corruption, just a retrieval failure
                result["retrieval_errors"] = result.get("retrieval_errors", [])
                result["retrieval_errors"].append({
                    "tier": tier,
                    "error": str(e)
                })
        
        # Log the verification result
        if result["success"]:
            logger.info(f"Content {cid} integrity verified across {result['verified_tiers']} tiers")
        else:
            logger.warning(f"Content {cid} integrity check failed: {len(result['corrupted_tiers'])} corrupted tiers")
        
        return result
    
    def _get_content_tiers(self, cid):
        """
        Get the tiers that should contain a given content.
        
        Args:
            cid: Content identifier
            
        Returns:
            List of tier names
        """
        # Check each tier to see if it contains the content
        tiers = []
        
        # Check IPFS
        try:
            # Just check if content exists without downloading
            self.info(f"ipfs://{cid}")
            tiers.append("ipfs_local")
        except Exception:
            pass
        
        return tiers
    
    def _get_from_tier(self, cid, tier):
        """
        Get content from a specific storage tier.
        
        Args:
            cid: Content identifier
            tier: Source tier name
            
        Returns:
            Content data if found, None otherwise
        """
        if tier == "ipfs_local":
            # Get from local IPFS
            try:
                return self._open(f"ipfs://{cid}", "rb").read()
            except Exception:
                return None
        
        return None


# Register the filesystem with clobber=True to handle development reloads
try:
    fsspec.register_implementation("ipfs", IPFSFileSystem, clobber=True)
    fsspec.register_implementation("filecoin", IPFSFileSystem, clobber=True)
    fsspec.register_implementation("storacha", IPFSFileSystem, clobber=True)
    fsspec.register_implementation("synapse", IPFSFileSystem, clobber=True)
except Exception as e:
    logger.warning(f"Failed to register filesystem protocols: {e}")
    # Fallback without clobber
    for protocol in ["ipfs", "filecoin", "storacha", "synapse"]:
        if protocol not in fsspec.registry.known:
            fsspec.register_implementation(protocol, IPFSFileSystem)


# Convenience functions
def create_synapse_filesystem(metadata: Optional[Dict[str, Any]] = None, **kwargs) -> IPFSFileSystem:
    """Create a Synapse SDK filesystem instance."""
    return IPFSFileSystem(backend="synapse", metadata=metadata, **kwargs)


def create_ipfs_filesystem(metadata: Optional[Dict[str, Any]] = None, **kwargs) -> IPFSFileSystem:
    """Create an IPFS filesystem instance."""
    return IPFSFileSystem(backend="ipfs", metadata=metadata, **kwargs)


def create_filecoin_filesystem(metadata: Optional[Dict[str, Any]] = None, **kwargs) -> IPFSFileSystem:
    """Create a Filecoin filesystem instance."""
    return IPFSFileSystem(backend="filecoin", metadata=metadata, **kwargs)


def create_storacha_filesystem(metadata: Optional[Dict[str, Any]] = None, **kwargs) -> IPFSFileSystem:
    """Create a Storacha filesystem instance."""
    return IPFSFileSystem(backend="storacha", metadata=metadata, **kwargs)


if __name__ == "__main__":
    # Example usage
    import tempfile
    
    # Test Synapse backend
    try:
        fs = create_synapse_filesystem(metadata={
            "network": "calibration",
            "auto_approve": True
        })
        
        print(f"Created filesystem with backend: {fs.backend}")
        print(f"Backend status: {fs.get_backend_status()}")
        
        # Test listing (will show stored data in Synapse)
        items = fs.ls("/", detail=True)
        print(f"Found {len(items)} items")
        
    except Exception as e:
        print(f"Error testing Synapse backend: {e}")
    
    # Test IPFS backend
    try:
        fs = create_ipfs_filesystem()
        
        print(f"Created filesystem with backend: {fs.backend}")
        print(f"Backend status: {fs.get_backend_status()}")
        
    except Exception as e:
        print(f"Error testing IPFS backend: {e}")
