"""
Configuration for auto-healing feature.
"""

import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import json


@dataclass
class AutoHealConfig:
    """Configuration for auto-healing feature."""
    
    enabled: bool = False
    github_token: Optional[str] = None
    github_repo: Optional[str] = None
    max_log_lines: int = 100
    include_stack_trace: bool = True
    auto_create_issues: bool = True
    issue_labels: list[str] = None
    
    def __post_init__(self):
        """Initialize default values and load from environment."""
        if self.issue_labels is None:
            self.issue_labels = ['auto-heal', 'cli-error', 'automated-issue']
        
        # Load from environment variables if not set
        if self.github_token is None:
            self.github_token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
        
        if self.github_repo is None:
            self.github_repo = os.environ.get('GITHUB_REPOSITORY')
        
        # Check if auto-healing is enabled via environment
        if os.environ.get('IPFS_KIT_AUTO_HEAL', '').lower() in ('true', '1', 'yes'):
            self.enabled = True
    
    @classmethod
    def from_file(cls, config_path: Optional[Path] = None) -> 'AutoHealConfig':
        """Load configuration from file."""
        if config_path is None:
            config_path = Path.home() / '.ipfs_kit' / 'auto_heal_config.json'
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                    return cls(**config_data)
            except Exception:
                pass
        
        return cls()
    
    def save_to_file(self, config_path: Optional[Path] = None):
        """Save configuration to file."""
        if config_path is None:
            config_path = Path.home() / '.ipfs_kit' / 'auto_heal_config.json'
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump({
                'enabled': self.enabled,
                'github_repo': self.github_repo,
                'max_log_lines': self.max_log_lines,
                'include_stack_trace': self.include_stack_trace,
                'auto_create_issues': self.auto_create_issues,
                'issue_labels': self.issue_labels,
            }, f, indent=2)
    
    def is_configured(self) -> bool:
        """Check if auto-healing is properly configured."""
        return (
            self.enabled and
            self.github_token is not None and
            self.github_repo is not None and
            self.auto_create_issues
        )
