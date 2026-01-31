"""
GitHub issue creator for auto-healing.
"""

import logging
from typing import Optional
import requests
from .config import AutoHealConfig
from .error_capture import CapturedError

logger = logging.getLogger(__name__)


class GitHubIssueCreator:
    """Creates GitHub issues from captured errors."""
    
    def __init__(self, config: AutoHealConfig):
        """Initialize GitHub issue creator."""
        self.config = config
        self.api_base = "https://api.github.com"
    
    def create_issue_from_error(self, error: CapturedError) -> Optional[str]:
        """Create a GitHub issue from a captured error."""
        
        if not self.config.is_configured():
            logger.warning("Auto-healing not properly configured")
            return None
        
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
        """Check if a similar issue already exists."""
        
        if not self.config.is_configured():
            return None
        
        # Parse repository owner and name
        owner, repo = self.config.github_repo.split('/', 1)
        
        # Search for existing issues with the same error type
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
