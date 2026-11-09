"""
IPFS metadata manager for MCP.

This module implements enhanced metadata handling for IPFS content,
addressing the metadata integration requirements in the MCP roadmap.
"""

import logging
import json
import time
import tempfile
from typing import Dict, Any, Optional, List, Union

# Configure logger
logger = logging.getLogger(__name__)

class IPFSMetadataManager:
    """
    Manages metadata storage and retrieval for IPFS content.
    
    This class implements the enhanced metadata integration mentioned in the roadmap,
    providing a robust way to associate, store, and retrieve metadata for IPFS content.
    """
    
    def __init__(self, ipfs_client):
        """
        Initialize the metadata manager.
        
        Args:
            ipfs_client: IPFS client instance
        """
        self.ipfs = ipfs_client
        self._ensure_metadata_dir()
    
    def _ensure_metadata_dir(self):
        """Ensure the metadata directory exists in MFS."""
        try:
            self.ipfs._call_api('files/mkdir', params={
                'arg': '/metadata',
                'parents': 'true'
            })
            logger.info("Ensured /metadata directory exists in IPFS MFS")
        except Exception as e:
            logger.warning(f"Failed to create metadata directory: {e}")
    
    def store_metadata(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store metadata for a content item.
        
        Args:
            cid: Content identifier
            metadata: Metadata to store
            
        Returns:
            Dict with operation result
        """
        if not metadata:
            return {"success": False, "error": "No metadata provided"}
        
        try:
            # Add timestamp if not present
            if 'timestamp' not in metadata:
                metadata['timestamp'] = time.time()
            
            # Add content reference
            metadata['cid'] = cid
            
            # Serialize to JSON
            metadata_json = json.dumps(metadata)
            metadata_path = f"/metadata/{cid}.json"
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile() as temp:
                temp.write(metadata_json.encode('utf-8'))
                temp.flush()
                
                # Write to MFS
                with open(temp.name, 'rb') as f:
                    files = {'file': f}
                    params = {'arg': metadata_path, 'create': 'true', 'parents': 'true'}
                    result = self.ipfs._call_api('files/write', params=params, files=files)
                
                if not result.get('success'):
                    return result
            
            # Get CID of the metadata file
            stat_result = self.ipfs._call_api('files/stat', params={'arg': metadata_path})
            if not stat_result.get('success'):
                return stat_result
            
            metadata_cid = stat_result.get('Hash')
            
            return {
                "success": True,
                "cid": cid,
                "metadata_cid": metadata_cid,
                "metadata_path": metadata_path
            }
            
        except Exception as e:
            logger.error(f"Error storing metadata for {cid}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "MetadataStoreError"
            }
    
    def get_metadata(self, cid: str) -> Dict[str, Any]:
        """
        Retrieve metadata for a content item.
        
        Args:
            cid: Content identifier
            
        Returns:
            Dict with operation result including metadata
        """
        try:
            metadata_path = f"/metadata/{cid}.json"
            
            # Check if metadata file exists
            try:
                stat_result = self.ipfs._call_api('files/stat', params={'arg': metadata_path})
                if not stat_result.get('success'):
                    return {
                        "success": False,
                        "error": f"Metadata not found for {cid}",
                        "error_type": "MetadataNotFound"
                    }
            except Exception:
                return {
                    "success": False,
                    "error": f"Metadata not found for {cid}",
                    "error_type": "MetadataNotFound"
                }
            
            # Read metadata file
            read_result = self.ipfs._call_api('files/read', params={'arg': metadata_path})
            if not read_result.get('success'):
                return read_result
            
            metadata_content = read_result.get('data')
            if isinstance(metadata_content, bytes):
                metadata_content = metadata_content.decode('utf-8')
            
            # Parse JSON
            try:
                metadata = json.loads(metadata_content)
                return {
                    "success": True,
                    "cid": cid,
                    "metadata": metadata
                }
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Invalid metadata format: {e}",
                    "error_type": "MetadataParseError"
                }
            
        except Exception as e:
            logger.error(f"Error retrieving metadata for {cid}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "MetadataRetrieveError"
            }
    
    def update_metadata(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update metadata for a content item.
        
        Args:
            cid: Content identifier
            metadata: New metadata (will be merged with existing)
            
        Returns:
            Dict with operation result
        """
        try:
            # Get existing metadata
            existing_result = self.get_metadata(cid)
            
            if existing_result.get('success'):
                # Merge existing with new metadata
                existing_metadata = existing_result.get('metadata', {})
                merged_metadata = {**existing_metadata, **metadata}
                
                # Update timestamp
                merged_metadata['updated_at'] = time.time()
                
                # Store merged metadata
                return self.store_metadata(cid, merged_metadata)
            else:
                # No existing metadata, create new
                metadata['created_at'] = time.time()
                return self.store_metadata(cid, metadata)
            
        except Exception as e:
            logger.error(f"Error updating metadata for {cid}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "MetadataUpdateError"
            }
    
    def list_metadata(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        List available metadata entries.
        
        Args:
            prefix: Optional CID prefix to filter by
            
        Returns:
            Dict with operation result including list of metadata entries
        """
        try:
            # List files in metadata directory
            ls_result = self.ipfs._call_api('files/ls', params={'arg': '/metadata', 'long': 'true'})
            if not ls_result.get('success'):
                return ls_result
            
            entries = []
            files = ls_result.get('Entries', [])
            
            for file_entry in files:
                if not file_entry.get('Name', '').endswith('.json'):
                    continue
                
                cid = file_entry.get('Name', '').replace('.json', '')
                
                if prefix and not cid.startswith(prefix):
                    continue
                
                entries.append({
                    "cid": cid,
                    "size": file_entry.get('Size', 0),
                    "metadata_cid": file_entry.get('Hash')
                })
            
            return {
                "success": True,
                "entries": entries,
                "count": len(entries)
            }
            
        except Exception as e:
            logger.error(f"Error listing metadata: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "MetadataListError"
            }
    
    def delete_metadata(self, cid: str) -> Dict[str, Any]:
        """
        Delete metadata for a content item.
        
        Args:
            cid: Content identifier
            
        Returns:
            Dict with operation result
        """
        try:
            metadata_path = f"/metadata/{cid}.json"
            
            # Check if file exists
            try:
                self.ipfs._call_api('files/stat', params={'arg': metadata_path})
            except Exception:
                return {
                    "success": False,
                    "error": f"Metadata not found for {cid}",
                    "error_type": "MetadataNotFound"
                }
            
            # Delete the file
            result = self.ipfs._call_api('files/rm', params={'arg': metadata_path})
            if result.get('success'):
                return {
                    "success": True,
                    "cid": cid,
                    "message": f"Metadata deleted for {cid}"
                }
            else:
                return result
            
        except Exception as e:
            logger.error(f"Error deleting metadata for {cid}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "MetadataDeleteError"
            }
