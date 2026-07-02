"""Gemini CLI wrapper for LLM router."""

from __future__ import annotations

import subprocess
from typing import Any, List, Optional


class GeminiCLI:
    """Python wrapper for Gemini CLI operations."""
    
    def __init__(self, use_accelerate: bool = False):
        """Initialize Gemini CLI wrapper.
        
        Args:
            use_accelerate: Whether to use IPFS accelerate features
        """
        self.use_accelerate = use_accelerate
    
    def execute(
        self,
        args: List[str],
        capture_output: bool = True,
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """Execute a Gemini CLI command.
        
        Args:
            args: List of command arguments
            capture_output: Whether to capture stdout/stderr
            timeout: Command timeout in seconds
        
        Returns:
            Completed process result
        """
        cmd = ["npx", "@google/gemini-cli"] + args
        
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            check=False
        )
        
        return result
