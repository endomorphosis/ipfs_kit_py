"""
Lassie client for IPFS Kit.
"""

import asyncio
import json
import logging
import subprocess
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LassieClient:
    """A client for interacting with the Lassie retrieval client."""

    def __init__(self, binary_path: str = "lassie", config: Dict[str, Any] = None):
        self.binary_path = binary_path
        self.config = config or {}

    async def health_check(self) -> Dict[str, Any]:
        """Check if the Lassie binary is available and executable."""
        try:
            result = await asyncio.create_subprocess_exec(
                self.binary_path, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                return {
                    "status": "healthy",
                    "binary_available": True,
                    "version": stdout.decode().strip(),
                    "binary_path": self.binary_path
                }
            else:
                return {
                    "status": "unhealthy",
                    "binary_available": False,
                    "error": stderr.decode().strip()
                }
        except FileNotFoundError:
            return {
                "status": "unhealthy",
                "binary_available": False,
                "error": f"Lassie binary not found at '{self.binary_path}'"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "binary_available": False,
                "error": str(e)
            }