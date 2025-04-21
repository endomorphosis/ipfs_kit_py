"""
HuggingFace storage model implementation for IPFS Kit.

This module provides integration with the HuggingFace Hub for storing and retrieving data.
"""

import logging
from typing import Dict, List, Any, Optional, Union

# Configure logger
logger = logging.getLogger(__name__)

class HuggingFaceModel:
    """HuggingFace storage model implementation."""
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize the HuggingFace model with optional API token.
        
        Args:
            api_token: Optional API token for HuggingFace Hub
        """
        self.api_token = api_token
        self.is_available = self._check_availability()
        
    def _check_availability(self) -> bool:
        """Check if HuggingFace Hub is available."""
        try:
            import huggingface_hub
            return True
        except ImportError:
            logger.warning("HuggingFace Hub not available. Install with: pip install huggingface_hub")
            return False
    
    def upload_file(self, file_path: str, repo_id: str) -> Dict[str, Any]:
        """
        Upload a file to HuggingFace Hub.
        
        Args:
            file_path: Path to the file to upload
            repo_id: Target repository ID
            
        Returns:
            Response dict with upload details
        """
        if not self.is_available:
            return {"success": False, "error": "HuggingFace Hub not available"}
        
        try:
            import huggingface_hub
            result = huggingface_hub.upload_file(
                path_or_fileobj=file_path,
                path_in_repo=file_path.split("/")[-1],
                repo_id=repo_id,
                token=self.api_token
            )
            return {"success": True, "url": result}
        except Exception as e:
            logger.error(f"Error uploading file to HuggingFace Hub: {str(e)}")
            return {"success": False, "error": str(e)}