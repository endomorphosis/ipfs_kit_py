"""
IPLD (InterPlanetary Linked Data) utilities for IPFS Kit.

This module integrates the py-ipld libraries into IPFS Kit, providing 
functionality for working with:
- CAR files (Content Addressable aRchives)
- DAG-PB (Protobuf Directed Acyclic Graph format)
- UnixFS (File system representation in IPFS)

These components enable low-level manipulation of IPFS data structures,
providing developers with direct access to IPFS content addressing and
graph-based data models.
"""

import logging
import os
import sys
from typing import Dict, List, Optional, Tuple, Union, Any

from .car import IPLDCarHandler
from .dag_pb import IPLDDagPbHandler 
from .unixfs import IPLDUnixFSHandler

logger = logging.getLogger(__name__)