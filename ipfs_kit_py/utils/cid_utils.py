"""CID utilities for content-addressed caching."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def cid_for_obj(obj: Any, base: str = "base32") -> str:
    """Generate a CID (Content Identifier) for an object.
    
    Args:
        obj: The object to generate a CID for
        base: The base encoding to use (default: base32)
    
    Returns:
        A CID string
    """
    # Serialize object to JSON
    try:
        payload = json.dumps(obj, sort_keys=True, default=repr, ensure_ascii=False)
    except Exception:
        payload = repr(obj)
    
    # Generate SHA-256 hash
    hash_bytes = hashlib.sha256(payload.encode("utf-8")).digest()
    
    # Convert to base32 or base58 encoding
    if base == "base32":
        # Simple base32 encoding
        import base64
        encoded = base64.b32encode(hash_bytes).decode("ascii").rstrip("=").lower()
        return f"b{encoded}"
    elif base == "base58":
        # Base58 encoding (Bitcoin-style)
        try:
            import base58
            encoded = base58.b58encode(hash_bytes).decode("ascii")
            return f"z{encoded}"
        except ImportError:
            # Fallback to hex if base58 not available
            return f"f{hash_bytes.hex()}"
    else:
        # Default to hex
        return f"f{hash_bytes.hex()}"
