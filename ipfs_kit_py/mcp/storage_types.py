"""Storage Types Module

This module defines storage backend types and related enumerations.
"""

from enum import Enum, auto
from typing import Dict, Any, Optional, List, Union


class StorageBackendType(str, Enum):
    """Enumeration of supported storage backend types."""
    IPFS = "ipfs"
    FILECOIN = "filecoin"
    S3 = "s3"
    HUGGINGFACE = "huggingface"
    STORACHA = "storacha"
    LASSIE = "lassie"
    LOCAL = "local"
    MEM = "memory"
    CUSTOM = "custom"


class StorageOperation(str, Enum):
    """Enumeration of storage operations."""
    ADD = "add"
    GET = "get"
    PIN = "pin"
    LS = "ls"
    CAT = "cat"
    REMOVE = "remove"
    STAT = "stat"
    DEALS = "deals"
    PUBLISH = "publish"
    RESOLVE = "resolve"


class StorageStatus(str, Enum):
    """Enumeration of storage operation statuses."""
    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    PINNED = "pinned"
    UNPINNED = "unpinned"
    PUBLISHED = "published"
    RESOLVED = "resolved"