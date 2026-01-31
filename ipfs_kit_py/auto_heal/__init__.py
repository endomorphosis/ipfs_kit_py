"""
Auto-healing module for IPFS Kit CLI.

This module provides automatic error capture, GitHub issue creation,
and integration with the auto-healing workflow system.
"""

from .error_capture import ErrorCapture, capture_cli_errors
from .github_issue_creator import GitHubIssueCreator
from .config import AutoHealConfig

__all__ = [
    'ErrorCapture',
    'capture_cli_errors',
    'GitHubIssueCreator',
    'AutoHealConfig',
]
