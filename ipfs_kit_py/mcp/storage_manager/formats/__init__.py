"""
File format handlers for IPFS Kit.

This module provides support for various IPFS/Filecoin file formats
including CAR files and IPLD codecs.
"""

from .car_manager import CARManager

__all__ = ['CARManager']
