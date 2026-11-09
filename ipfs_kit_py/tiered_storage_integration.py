"""
Tiered Storage Integration Module.

This module integrates the TieredCacheManager with various storage backends:
- S3
- Storacha
- Filecoin
- HuggingFace
- Lassie
- IPFS

It provides a unified interface to move content between storage tiers seamlessly,
leveraging the MCP storage models for backend operations.
"""

import os
import time
import tempfile
import logging
from typing import Dict, List, Optional, Any, Union, Tuple

# Import tiered cache manager
from ipfs_kit_py.tiered_cache_manager import TieredCacheManager

# Import MCP components
from ipfs_kit_py.mcp.models.storage_manager import StorageManager

# Configure logger
logger = logging.getLogger(__name__)


class TieredStorageIntegrator:
    """Integrates TieredCacheManager with backend storage models."""
    
    def __init__(self, cache_manager: TieredCacheManager, storage_manager: StorageManager):
        """Initialize the integrator.
        
        Args:
            cache_manager: TieredCacheManager instance
            storage_manager: StorageManager instance with storage models
        """
        self.cache_manager = cache_manager
        self.storage_manager = storage_manager
        
        # Verify that the cache manager has the tiers configured
        self.tiers_config = self.cache_manager.config.get("tiers", {})
        if not self.tiers_config:
            logger.warning("TieredCacheManager has no tier configuration")
        
        # Map storage backend models to tier names
        self.tier_to_model_map = {
            "s3": "s3",
            "storacha": "storacha",
            "filecoin": "filecoin",
            "huggingface": "huggingface",
            "lassie": "lassie"
        }
        
        # Check which backends are available
        self.available_backends = storage_manager.get_available_backends()
        logger.info(f"Available storage backends: {', '.join([k for k, v in self.available_backends.items() if v])}")
    
    def move_content(self, cid: str, target_tier: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Move content between storage tiers.
        
        This method orchestrates the movement of content between tiers, handling the 
        physical transfer of data as well as metadata updates.
        
        Args:
            cid: Content identifier
            target_tier: Target storage tier
            options: Tier-specific options for the move
            
        Returns:
            Result dictionary with operation status and details
        """
        result = {
            "success": False,
            "operation": "move_content",
            "cid": cid,
            "target_tier": target_tier,
            "timestamp": time.time()
        }
        
        try:
            # Get current tier location
            current_location = self.cache_manager.get_tier_location(cid)
            if not current_location.get("success", False):
                result["error"] = current_location.get("error", f"Content not found: {cid}")
                result["error_type"] = current_location.get("error_type", "ContentNotFoundError")
                return result
            
            current_tier = current_location.get("tier", "unknown")
            result["source_tier"] = current_tier
            
            # Validate target tier
            if target_tier not in self.tiers_config:
                result["error"] = f"Invalid target tier: {target_tier}"
                result["error_type"] = "ValidationError"
                return result
            
            # Handle no-op case (already in target tier)
            if current_tier == target_tier:
                result["success"] = True
                result["message"] = f"Content already in target tier: {target_tier}"
                return result
            
            # For most tier movements, we need to:
            # 1. Retrieve the content from the current tier
            # 2. Store it in the target tier
            # 3. Update the metadata
            
            # Step 1: Retrieve the content from current tier
            # For memory and disk tiers, this is handled by the cache manager
            # For external backends, we need to use the storage model
            
            content = None
            
            if current_tier in ["memory", "disk"]:
                # Get from cache manager
                content = self.cache_manager.get(cid)
                if content is None:
                    result["error"] = f"Failed to retrieve content from {current_tier} tier"
                    result["error_type"] = "RetrievalError"
                    return result
            else:
                # Get from external storage backend
                retrieval_result = self._retrieve_from_backend(cid, current_tier)
                if not retrieval_result.get("success", False):
                    result["error"] = retrieval_result.get("error", f"Failed to retrieve from {current_tier}")
                    result["error_type"] = retrieval_result.get("error_type", "BackendRetrievalError")
                    result["retrieval_result"] = retrieval_result
                    return result
                
                content = retrieval_result.get("content")
            
            # Step 2: Store in target tier
            tier_params = {}
            
            if target_tier in ["memory", "disk"]:
                # For memory and disk tiers, just update the cache
                # No additional parameters needed for local tiers
                pass
            else:
                # Store in external backend
                storage_result = self._store_in_backend(cid, content, target_tier, options)
                if not storage_result.get("success", False):
                    result["error"] = storage_result.get("error", f"Failed to store in {target_tier}")
                    result["error_type"] = storage_result.get("error_type", "BackendStorageError")
                    result["storage_result"] = storage_result
                    return result
                
                # Extract tier-specific parameters for metadata
                tier_params = storage_result.get("tier_params", {})
            
            # Step 3: Update metadata to reflect the new tier location
            move_result = self.cache_manager.move_to_tier(cid, target_tier, tier_params)
            if not move_result.get("success", False):
                result["error"] = move_result.get("error", "Failed to update tier metadata")
                result["error_type"] = move_result.get("error_type", "MetadataUpdateError")
                result["move_result"] = move_result
                return result
            
            # Success!
            result["success"] = True
            result["message"] = f"Content moved from {current_tier} to {target_tier}"
            
            # Add tier-specific details
            if tier_params:
                result["tier_params"] = tier_params
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error moving content to tier {target_tier}: {e}")
        
        return result
    
    def _retrieve_from_backend(self, cid: str, source_tier: str) -> Dict[str, Any]:
        """Retrieve content from a backend storage tier.
        
        Args:
            cid: Content identifier
            source_tier: Source tier name
            
        Returns:
            Result dictionary with content and status
        """
        result = {
            "success": False,
            "operation": "retrieve_from_backend",
            "cid": cid,
            "source_tier": source_tier
        }
        
        try:
            # Get location metadata
            location = self.cache_manager.get_tier_location(cid)
            if not location.get("success", False):
                result["error"] = location.get("error", f"Failed to get location for {cid}")
                result["error_type"] = location.get("error_type", "LocationError")
                return result
            
            # Get the corresponding storage model
            model_name = self.tier_to_model_map.get(source_tier)
            if not model_name:
                result["error"] = f"No storage model mapped for tier: {source_tier}"
                result["error_type"] = "ConfigurationError"
                return result
            
            storage_model = self.storage_manager.get_model(model_name)
            if not storage_model:
                result["error"] = f"Storage model not available: {model_name}"
                result["error_type"] = "BackendUnavailableError"
                return result
            
            # Handle different backends
            if source_tier == "s3":
                # Get S3 parameters from location
                bucket = location.get("bucket")
                key = location.get("key")
                
                if not bucket or not key:
                    result["error"] = "Missing S3 location parameters"
                    result["error_type"] = "ParameterError"
                    return result
                
                # Create temporary file for download
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Download from S3
                download_result = storage_model.download_file(bucket, key, temp_path)
                
                if not download_result.get("success", False):
                    result["error"] = download_result.get("error", "S3 download failed")
                    result["error_type"] = "S3DownloadError"
                    # Clean up temp file
                    os.unlink(temp_path)
                    return result
                
                # Read the content
                with open(temp_path, "rb") as f:
                    content = f.read()
                
                # Clean up
                os.unlink(temp_path)
                
                # Success
                result["success"] = True
                result["content"] = content
                result["size_bytes"] = len(content)
                
            elif source_tier == "storacha":
                # Get Storacha parameters
                space_id = location.get("space_id")
                car_cid = location.get("car_cid")
                
                if not space_id or not car_cid:
                    result["error"] = "Missing Storacha location parameters"
                    result["error_type"] = "ParameterError"
                    return result
                
                # Create temporary file for download
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Download from Storacha
                download_result = storage_model.download_car(car_cid, temp_path)
                
                if not download_result.get("success", False):
                    result["error"] = download_result.get("error", "Storacha download failed")
                    result["error_type"] = "StorachaDownloadError"
                    # Clean up temp file
                    os.unlink(temp_path)
                    return result
                
                # Extract the specific content from the CAR file
                extract_result = storage_model.extract_from_car(temp_path, cid)
                
                # Clean up CAR file
                os.unlink(temp_path)
                
                if not extract_result.get("success", False):
                    result["error"] = extract_result.get("error", "Failed to extract content from CAR")
                    result["error_type"] = "CarExtractionError"
                    return result
                
                # Success
                result["success"] = True
                result["content"] = extract_result.get("content")
                result["size_bytes"] = len(result["content"])
                
            elif source_tier == "huggingface":
                # Get HuggingFace parameters
                repo_id = location.get("repo_id")
                file_path = location.get("file_path")
                
                if not repo_id or not file_path:
                    result["error"] = "Missing HuggingFace location parameters"
                    result["error_type"] = "ParameterError"
                    return result
                
                # Create temporary file for download
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Download from HuggingFace
                download_result = storage_model.download_file(repo_id, file_path, temp_path)
                
                if not download_result.get("success", False):
                    result["error"] = download_result.get("error", "HuggingFace download failed")
                    result["error_type"] = "HuggingFaceDownloadError"
                    # Clean up temp file
                    os.unlink(temp_path)
                    return result
                
                # Read the content
                with open(temp_path, "rb") as f:
                    content = f.read()
                
                # Clean up
                os.unlink(temp_path)
                
                # Success
                result["success"] = True
                result["content"] = content
                result["size_bytes"] = len(content)
                
            elif source_tier == "lassie":
                # For Lassie, we fetch directly by CID
                fetch_result = storage_model.fetch_cid(cid)
                
                if not fetch_result.get("success", False):
                    result["error"] = fetch_result.get("error", "Lassie fetch failed")
                    result["error_type"] = "LassieFetchError"
                    return result
                
                # Success
                result["success"] = True
                result["content"] = fetch_result.get("content")
                result["size_bytes"] = len(result["content"])
                
            elif source_tier == "filecoin":
                # For Filecoin, we retrieve through the filecoin_to_ipfs operation
                retrieve_result = storage_model.filecoin_to_ipfs(cid)
                
                if not retrieve_result.get("success", False):
                    result["error"] = retrieve_result.get("error", "Filecoin retrieval failed")
                    result["error_type"] = "FilecoinRetrievalError"
                    return result
                
                # The content should now be in IPFS, retrieve it
                ipfs_model = self.storage_manager.get_model("ipfs")
                if not ipfs_model:
                    result["error"] = "IPFS model not available for Filecoin retrieval"
                    result["error_type"] = "BackendUnavailableError"
                    return result
                
                # Get the content from IPFS
                ipfs_result = ipfs_model.get_content(cid)
                
                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get("error", "Failed to get content from IPFS after Filecoin retrieval")
                    result["error_type"] = "IPFSGetError"
                    return result
                
                # Success
                result["success"] = True
                result["content"] = ipfs_result.get("data")
                result["size_bytes"] = len(result["content"])
                
            else:
                result["error"] = f"Unsupported source tier: {source_tier}"
                result["error_type"] = "UnsupportedTierError"
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error retrieving from {source_tier}: {e}")
        
        return result
    
    def _store_in_backend(self, cid: str, content: bytes, target_tier: str, 
                         options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store content in a backend storage tier.
        
        Args:
            cid: Content identifier
            content: Content bytes to store
            target_tier: Target tier name
            options: Tier-specific options
            
        Returns:
            Result dictionary with status and tier parameters
        """
        result = {
            "success": False,
            "operation": "store_in_backend",
            "cid": cid,
            "target_tier": target_tier,
            "size_bytes": len(content)
        }
        
        try:
            # Get the corresponding storage model
            model_name = self.tier_to_model_map.get(target_tier)
            if not model_name:
                result["error"] = f"No storage model mapped for tier: {target_tier}"
                result["error_type"] = "ConfigurationError"
                return result
            
            storage_model = self.storage_manager.get_model(model_name)
            if not storage_model:
                result["error"] = f"Storage model not available: {model_name}"
                result["error_type"] = "BackendUnavailableError"
                return result
            
            # Extract options
            options = options or {}
            
            # Handle different backends
            if target_tier == "s3":
                # Get S3 parameters
                bucket = options.get("bucket")
                key = options.get("key", cid)
                
                if not bucket:
                    result["error"] = "Missing required parameter: bucket"
                    result["error_type"] = "ParameterError"
                    return result
                
                # Create temporary file for upload
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name
                
                # Upload to S3
                upload_result = storage_model.upload_file(
                    temp_path, bucket, key, 
                    metadata={"ipfs_cid": cid}
                )
                
                # Clean up temp file
                os.unlink(temp_path)
                
                if not upload_result.get("success", False):
                    result["error"] = upload_result.get("error", "S3 upload failed")
                    result["error_type"] = "S3UploadError"
                    return result
                
                # Success - collect tier parameters for metadata
                result["success"] = True
                result["tier_params"] = {
                    "bucket": bucket,
                    "key": key,
                    "etag": upload_result.get("etag")
                }
                
            elif target_tier == "storacha":
                # Get Storacha parameters
                space_id = options.get("space_id")
                
                if not space_id:
                    result["error"] = "Missing required parameter: space_id"
                    result["error_type"] = "ParameterError"
                    return result
                
                # Create temporary file for upload
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name
                
                # Upload to Storacha
                upload_result = storage_model.upload_file(
                    temp_path, 
                    space_id=space_id,
                    metadata={"ipfs_cid": cid}
                )
                
                # Clean up temp file
                os.unlink(temp_path)
                
                if not upload_result.get("success", False):
                    result["error"] = upload_result.get("error", "Storacha upload failed")
                    result["error_type"] = "StorachaUploadError"
                    return result
                
                # Success - collect tier parameters for metadata
                result["success"] = True
                result["tier_params"] = {
                    "space_id": space_id,
                    "upload_id": upload_result.get("upload_id"),
                    "car_cid": upload_result.get("car_cid")
                }
                
            elif target_tier == "huggingface":
                # Get HuggingFace parameters
                repo_id = options.get("repo_id")
                file_path = options.get("file_path")
                repo_type = options.get("repo_type", "dataset")
                
                if not repo_id or not file_path:
                    result["error"] = "Missing required parameters: repo_id and file_path"
                    result["error_type"] = "ParameterError"
                    return result
                
                # Create temporary file for upload
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name
                
                # Upload to HuggingFace
                upload_result = storage_model.upload_file(
                    temp_path,
                    repo_id=repo_id,
                    path_in_repo=file_path,
                    repo_type=repo_type
                )
                
                # Clean up temp file
                os.unlink(temp_path)
                
                if not upload_result.get("success", False):
                    result["error"] = upload_result.get("error", "HuggingFace upload failed")
                    result["error_type"] = "HuggingFaceUploadError"
                    return result
                
                # Success - collect tier parameters for metadata
                result["success"] = True
                result["tier_params"] = {
                    "repo_id": repo_id,
                    "repo_type": repo_type,
                    "file_path": file_path,
                    "commit_hash": upload_result.get("commit_hash")
                }
                
            elif target_tier == "filecoin":
                # Get Filecoin parameters
                miner = options.get("miner")
                deal_duration = options.get("deal_duration", 518400)  # Default: 180 days
                
                if not miner:
                    result["error"] = "Missing required parameter: miner"
                    result["error_type"] = "ParameterError"
                    return result
                
                # For Filecoin, we need to store in IPFS first, then make a deal
                # Get the IPFS model
                ipfs_model = self.storage_manager.get_model("ipfs")
                if not ipfs_model:
                    result["error"] = "IPFS model not available for Filecoin storage"
                    result["error_type"] = "BackendUnavailableError"
                    return result
                
                # Add to IPFS if not already there
                ipfs_result = ipfs_model.add_content(content)
                
                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get("error", "Failed to add content to IPFS")
                    result["error_type"] = "IPFSAddError"
                    return result
                
                # Now store in Filecoin
                filecoin_result = storage_model.ipfs_to_filecoin(
                    cid,
                    miner,
                    deal_duration=deal_duration
                )
                
                if not filecoin_result.get("success", False):
                    result["error"] = filecoin_result.get("error", "Filecoin storage failed")
                    result["error_type"] = "FilecoinStorageError"
                    return result
                
                # Success - collect tier parameters for metadata
                result["success"] = True
                result["tier_params"] = {
                    "deal_id": filecoin_result.get("deal_id"),
                    "providers": [miner],
                    "deal_duration": deal_duration
                }
                
            else:
                result["error"] = f"Unsupported target tier: {target_tier}"
                result["error_type"] = "UnsupportedTierError"
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error storing in {target_tier}: {e}")
        
        return result
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics for all backends.
        
        Returns:
            Dictionary with storage statistics by tier
        """
        # Get stats from storage manager
        backend_stats = self.storage_manager.get_stats()
        
        # Add local tier stats from cache manager
        cache_stats = self.cache_manager.get_stats()
        
        # Combine into tier-organized structure
        tier_stats = {
            "memory": {
                "items": cache_stats.get("memory_cache", {}).get("count", 0),
                "size_bytes": cache_stats.get("memory_cache", {}).get("current_size", 0),
                "max_size_bytes": cache_stats.get("memory_cache", {}).get("max_size", 0),
                "hit_rate": cache_stats.get("hits", {}).get("memory", 0) / max(1, sum(cache_stats.get("hits", {}).values())),
                "heat_score_avg": None  # Would need additional calculation
            },
            "disk": {
                "items": cache_stats.get("disk_cache", {}).get("count", 0),
                "size_bytes": cache_stats.get("disk_cache", {}).get("current_size", 0),
                "max_size_bytes": cache_stats.get("disk_cache", {}).get("max_size", 0),
                "hit_rate": cache_stats.get("hits", {}).get("disk", 0) / max(1, sum(cache_stats.get("hits", {}).values())),
                "directory": cache_stats.get("disk_cache", {}).get("directory")
            }
        }
        
        # Add external backend stats
        if "s3" in backend_stats:
            s3_stats = backend_stats["s3"].get("operation_stats", {})
            tier_stats["s3"] = {
                "operations": s3_stats.get("total_operations", 0),
                "uploads": s3_stats.get("upload_count", 0),
                "downloads": s3_stats.get("download_count", 0),
                "bytes_uploaded": s3_stats.get("bytes_uploaded", 0),
                "bytes_downloaded": s3_stats.get("bytes_downloaded", 0)
            }
        
        if "storacha" in backend_stats:
            storacha_stats = backend_stats["storacha"].get("operation_stats", {})
            tier_stats["storacha"] = {
                "operations": storacha_stats.get("total_operations", 0),
                "uploads": storacha_stats.get("upload_count", 0),
                "downloads": storacha_stats.get("download_count", 0),
                "bytes_uploaded": storacha_stats.get("bytes_uploaded", 0),
                "bytes_downloaded": storacha_stats.get("bytes_downloaded", 0)
            }
        
        if "filecoin" in backend_stats:
            filecoin_stats = backend_stats["filecoin"].get("operation_stats", {})
            tier_stats["filecoin"] = {
                "operations": filecoin_stats.get("total_operations", 0),
                "deals": filecoin_stats.get("deal_count", 0),
                "retrievals": filecoin_stats.get("retrieval_count", 0),
                "bytes_stored": filecoin_stats.get("bytes_stored", 0),
                "bytes_retrieved": filecoin_stats.get("bytes_retrieved", 0)
            }
        
        if "huggingface" in backend_stats:
            hf_stats = backend_stats["huggingface"].get("operation_stats", {})
            tier_stats["huggingface"] = {
                "operations": hf_stats.get("total_operations", 0),
                "uploads": hf_stats.get("upload_count", 0),
                "downloads": hf_stats.get("download_count", 0),
                "bytes_uploaded": hf_stats.get("bytes_uploaded", 0),
                "bytes_downloaded": hf_stats.get("bytes_downloaded", 0)
            }
        
        if "lassie" in backend_stats:
            lassie_stats = backend_stats["lassie"].get("operation_stats", {})
            tier_stats["lassie"] = {
                "operations": lassie_stats.get("total_operations", 0),
                "fetches": lassie_stats.get("fetch_count", 0),
                "bytes_fetched": lassie_stats.get("bytes_fetched", 0)
            }
        
        # Add aggregate stats
        tier_stats["aggregate"] = {
            "total_operations": backend_stats.get("aggregate", {}).get("total_operations", 0),
            "bytes_uploaded": backend_stats.get("aggregate", {}).get("bytes_uploaded", 0),
            "bytes_downloaded": backend_stats.get("aggregate", {}).get("bytes_downloaded", 0),
            "total_items": cache_stats.get("total_items", 0),
            "cache_hit_rate": cache_stats.get("hit_rate", 0),
            "backend_count": backend_stats.get("aggregate", {}).get("backend_count", 0)
        }
        
        return {
            "success": True,
            "timestamp": time.time(),
            "tier_stats": tier_stats
        }


# Functional style API for simpler usage
def move_content_between_tiers(
    cid: str, 
    target_tier: str, 
    cache_manager: TieredCacheManager,
    storage_manager: StorageManager,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Move content between storage tiers using a functional API.
    
    Args:
        cid: Content identifier
        target_tier: Target storage tier
        cache_manager: TieredCacheManager instance
        storage_manager: StorageManager instance
        options: Tier-specific options
        
    Returns:
        Result dictionary with operation status
    """
    # Create integrator and perform the move
    integrator = TieredStorageIntegrator(cache_manager, storage_manager)
    return integrator.move_content(cid, target_tier, options)