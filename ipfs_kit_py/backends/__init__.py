"""
IPFS Kit Storage Backends

This package contains storage backend implementations for IPFS Kit.
Each backend provides a standardized interface for different storage systems.
"""

from .synapse_storage import SynapseStorage

__all__ = ['SynapseStorage']
