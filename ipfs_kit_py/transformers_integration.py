"""Transformers integration.

Historically, this module relied on the separate `ipfs_transformers_py` project.
That approach is now deprecated in favor of `ipfs_accelerate_py.auto_patch_transformers`,
which monkeypatches HuggingFace `transformers` to add IPFS helper methods.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Check if transformers is available
_transformers_available = False
AutoModel = None

try:
    from transformers import AutoModel as _HFAutoModel

    AutoModel = _HFAutoModel
    _transformers_available = True
except Exception:
    _transformers_available = False


def _try_apply_transformers_patches() -> None:
    """Best-effort: patch `transformers` with IPFS helper methods."""
    if not _transformers_available:
        return
    try:
        from ipfs_accelerate_py import auto_patch_transformers

        if auto_patch_transformers is not None:
            auto_patch_transformers.apply()
    except Exception:
        return


class TransformersIntegration:
    """Bridge class to provide ipfs_transformers functionality."""

    def __init__(self, api=None):
        """Initialize the transformers integration.

        Args:
            api: Optional IPFSSimpleAPI instance for sharing connections
        """
        self.api = api
        if not _transformers_available:
            logger.debug("transformers not available. Install with: pip install ipfs_kit_py[transformers]")

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
                "transformers is not available. Install with: pip install ipfs_kit_py[transformers]"
            )

        _try_apply_transformers_patches()
        if AutoModel is not None and hasattr(AutoModel, "from_auto_download"):
            return AutoModel.from_auto_download(model_name=model_name, s3cfg=s3cfg, **kwargs)

        # Fallback to standard HF behavior.
        if AutoModel is None:
            raise ImportError("transformers AutoModel unavailable")
        return AutoModel.from_pretrained(model_name, **kwargs)

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
                "transformers is not available. Install with: pip install ipfs_kit_py[transformers]"
            )

        _try_apply_transformers_patches()
        if AutoModel is not None and hasattr(AutoModel, "from_ipfs"):
            return AutoModel.from_ipfs(cid, **kwargs)

        raise NotImplementedError(
            "AutoModel.from_ipfs is not available. Install/enable ipfs_accelerate_py auto patching."
        )
