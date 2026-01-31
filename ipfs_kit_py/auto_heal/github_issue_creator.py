"""
GitHub issue creator for auto-healing with IPFS/P2P caching.
"""

import os
import logging
from typing import Optional
import requests
from .config import AutoHealConfig
from .error_capture import CapturedError

logger = logging.getLogger(__name__)

# Try to import GHCache for caching GitHub API calls
try:
    from ipfs_kit_py.gh_cache import GHCache
    HAS_GH_CACHE = True
except ImportError:
    HAS_GH_CACHE = False
    logger.debug("GHCache not available - GitHub API caching disabled")


class GitHubIssueCreator:
    """Creates GitHub issues from captured errors with optional caching."""
    
    def __init__(self, config: AutoHealConfig, enable_cache: bool = True):
        """
        Initialize GitHub issue creator.
        
        Args:
            config: Auto-heal configuration
            enable_cache: Enable caching for GitHub API calls (default: True)
        """
        self.config = config
        self.api_base = "https://api.github.com"
        self.enable_cache = enable_cache and HAS_GH_CACHE
        
        # Initialize cache if available
        if self.enable_cache:
            try:
                # Enable IPFS/P2P caching based on environment variables
                enable_ipfs = os.environ.get('GH_CACHE_IPFS', '0') == '1'
                enable_p2p = os.environ.get('GH_CACHE_P2P', '0') == '1'
                
                self.cache = GHCache(enable_ipfs=enable_ipfs, enable_p2p=enable_p2p)
                logger.info(f"GitHub API caching enabled (IPFS: {enable_ipfs}, P2P: {enable_p2p})")
            except Exception as e:
                logger.warning(f"Failed to initialize GitHub cache: {e}")
                self.enable_cache = False
                self.cache = None
        else:
            self.cache = None
            if HAS_GH_CACHE:
                logger.info("GitHub API caching available but disabled")
            else:
                logger.debug("GitHub API caching not available")
    
    def create_issue_from_error(self, error: CapturedError) -> Optional[str]:
        """Create a GitHub issue from a captured error."""
        
        if not self.config.is_configured():
            logger.warning("Auto-healing not properly configured")
            return None
        
        # Check for duplicate issues first
        duplicate_url = self.check_duplicate_issue(error)
        if duplicate_url:
            logger.info(f"Duplicate issue found: {duplicate_url}")
            return duplicate_url
        
        # Format issue title
        title = self._format_issue_title(error)
        
        # Format issue body
        body = error.format_for_issue(max_log_lines=self.config.max_log_lines)
        
        # Create the issue
        try:
            issue_url = self._create_github_issue(
                title=title,
                body=body,
                labels=self.config.issue_labels
            )
            
            return issue_url
        except Exception as e:
            logger.error(f"Failed to create GitHub issue: {e}")
            return None
    
    def _format_issue_title(self, error: CapturedError) -> str:
        """Format issue title from error."""
        # Truncate message if too long
        max_msg_length = 80
        msg = error.error_message
        if len(msg) > max_msg_length:
            msg = msg[:max_msg_length] + "..."
        
        return f"[Auto-Heal] {error.error_type}: {msg}"
    
    def _create_github_issue(
        self,
        title: str,
        body: str,
        labels: list[str]
    ) -> Optional[str]:
        """Create a GitHub issue using the GitHub API."""
        
        # Parse repository owner and name
        if '/' not in self.config.github_repo:
            logger.error(f"Invalid repository format: {self.config.github_repo}")
            return None
        
        owner, repo = self.config.github_repo.split('/', 1)
        
        # Prepare API request
        url = f"{self.api_base}/repos/{owner}/{repo}/issues"
        headers = {
            'Authorization': f'token {self.config.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'title': title,
            'body': body,
            'labels': labels,
        }
        
        # Make API request
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201:
            issue_data = response.json()
            issue_url = issue_data.get('html_url')
            logger.info(f"Created GitHub issue: {issue_url}")
            return issue_url
        else:
            logger.error(f"Failed to create issue: {response.status_code} - {response.text}")
            return None
    
    def check_duplicate_issue(self, error: CapturedError) -> Optional[str]:
        """
        Check if a similar issue already exists.
        
        This method uses caching if available to reduce API calls.
        """
        
        if not self.config.is_configured():
            return None
        
        # Parse repository owner and name
        owner, repo = self.config.github_repo.split('/', 1)
        
        # Try using gh CLI with caching if available
        if self.enable_cache and self.cache:
            try:
                # Use gh CLI to search for issues (cached)
                cmd = [
                    'gh', 'issue', 'list',
                    '--repo', self.config.github_repo,
                    '--state', 'open',
                    '--label', ','.join(self.config.issue_labels),
                    '--limit', '10',
                    '--json', 'title,url'
                ]
                
                result = self.cache.run(cmd)
                if result['exit_code'] == 0:
                    import json
                    issues = json.loads(result['stdout'])
                    
                    # Check if any issue has the same error type in the title
                    for issue in issues:
                        if error.error_type in issue.get('title', ''):
                            logger.info(f"Found duplicate issue (cached): {issue.get('url')}")
                            return issue.get('url')
                    
                    return None
            except Exception as e:
                logger.warning(f"Failed to check duplicates with cached gh CLI: {e}, falling back to API")
        
        # Fallback to direct API call (not cached)
        url = f"{self.api_base}/repos/{owner}/{repo}/issues"
        headers = {
            'Authorization': f'token {self.config.github_token}',
            'Accept': 'application/vnd.github.v3+json',
        }
        
        params = {
            'state': 'open',
            'labels': ','.join(self.config.issue_labels),
            'per_page': 10,
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                issues = response.json()
                
                # Check if any issue has the same error type in the title
                for issue in issues:
                    if error.error_type in issue.get('title', ''):
                        return issue.get('html_url')
            
        except Exception as e:
            logger.error(f"Failed to check for duplicate issues: {e}")
        
        return None
    
    def get_cache_stats(self) -> Optional[dict]:
        """Get cache statistics if caching is enabled."""
        if self.enable_cache and self.cache:
            return {
                'enabled': True,
                'ipfs_enabled': self.cache.enable_ipfs,
                'p2p_enabled': self.cache.enable_p2p,
                'stats': self.cache.stats
            }
        return {'enabled': False}
