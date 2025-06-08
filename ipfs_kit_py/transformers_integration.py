"""Integration module for ipfs_transformers_py functionality."""

import importlib.util
import sys
import os
from typing import Any, Dict, Optional, Union

# Check if transformers is available
_transformers_available = False
try:
    # Try importing directly from the installed transformers package
    from transformers import AutoModel
    _transformers_available = True
except ImportError:
    print("Could not import AutoModel from transformers package!!!")


class TransformersIntegration:
    """Bridge class to provide ipfs_transformers functionality."""

    def __init__(self, api=None):
        """Initialize the transformers integration.

        Args:
            api: Optional IPFSSimpleAPI instance for sharing connections
        """
        self.api = api
        if not _transformers_available:
            print("ipfs_transformers not available. Install with: pip install ipfs_kit_py[transformers]")

    def is_available(self) -> bool:
        """Check if transformers integration is available."""
        return _transformers_available

    def from_auto_download(self, model_name: str, s3cfg: Optional[Dict[str, str]] = None, **kwargs: Any) -> Any:
        """Load a model from auto-download.

        Args:
            model_name: Name of the model to download
            s3cfg: Optional S3 configuration for caching
            **kwargs: Additional arguments passed to from_auto_download

        Returns:
            The loaded model or None if not available
        """
        if not _transformers_available:
            raise ImportError(
                "ipfs_transformers is not available. Install with: pip install ipfs_kit_py[transformers]"
            )
        return AutoModel.from_auto_download(model_name=model_name, s3cfg=s3cfg, **kwargs)

    def from_ipfs(self, cid: str, **kwargs: Any) -> Any:
        """Load a model from IPFS.

        Args:
            cid: IPFS CID of the model
            **kwargs: Additional arguments passed to from_ipfs

        Returns:
            The loaded model or None if not available
        """
        if not _transformers_available:
            raise ImportError(
                "ipfs_transformers is not available. Install with: pip install ipfs_kit_py[transformers]"
            )
        return AutoModel.from_ipfs(cid, **kwargs)
