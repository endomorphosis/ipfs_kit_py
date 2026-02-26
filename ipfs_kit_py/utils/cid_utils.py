"""CID (Content Identifier) utilities for cache keys.

Uses the existing ipfs_multiformats implementation to generate proper CIDv1.
"""

from __future__ import annotations

import json
import hashlib
from typing import Any


def cid_for_obj(obj: Any, base: str = "base32") -> str:
    """Generate a CIDv1 (Content Identifier) for an object using ipfs_multiformats.
    
    Args:
        obj: The object to generate a CID for
        base: The base encoding to use (default: base32)
    
    Returns:
        A CIDv1 string using sha2-256 multihash
    """
    try:
        from ipfs_kit_py.ipfs_multiformats import create_cid_from_bytes
        
        # Serialize object to JSON deterministically
        try:
            payload = json.dumps(obj, sort_keys=True, default=repr, ensure_ascii=False)
        except Exception:
            payload = repr(obj)
        
        # Convert to bytes
        data_bytes = payload.encode("utf-8")
        
        # Use the existing CID implementation
        # This creates a proper CIDv1 with raw codec and sha2-256
        cid = create_cid_from_bytes(data_bytes)
        
        # Return the CID string (already base32 encoded by default)
        return str(cid)
    except ImportError:
        # Fallback to simple hash if ipfs_multiformats not available
        # This is just a content hash, not a real CID
        try:
            payload = json.dumps(obj, sort_keys=True, default=repr, ensure_ascii=False)
        except Exception:
            payload = repr(obj)
        
        hash_bytes = hashlib.sha256(payload.encode("utf-8")).digest()
        
        if base == "base32":
            import base64
            encoded = base64.b32encode(hash_bytes).decode("ascii").rstrip("=").lower()
            return f"b{encoded}"
        elif base == "base58":
            # Simple base58 encoding (not proper multibase)
            import base64
            encoded = base64.b32encode(hash_bytes).decode("ascii").rstrip("=").lower()
            return f"z{encoded}"
        else:
            return hash_bytes.hex()
