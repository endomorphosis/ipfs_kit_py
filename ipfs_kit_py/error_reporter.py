"""
Automatic Error Reporter for GitHub Issues.

This module provides functionality to automatically create GitHub issues from
runtime errors in the IPFS Kit Python application. It supports error reporting
from Python runtime, MCP server, and JavaScript dashboard errors.
"""

import os
import sys
import json
import logging
import traceback
from typing import Dict, Any, Optional, List, Tuple
import hashlib
import requests

logger = logging.getLogger(__name__)


class GitHubIssueReporter:
    """
    Reporter for automatically creating GitHub issues from runtime errors.
    
    This class handles the creation of GitHub issues when errors occur during
    runtime, including deduplication, error categorization, and rate limiting.
    """
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        enabled: bool = True,
        auto_labels: Optional[List[str]] = None,
        error_cache_file: Optional[str] = None,
        max_reports_per_hour: int = 10,
    ):
        """
        Initialize the GitHub issue reporter.
        
        Args:
            github_token: GitHub personal access token with repo permissions
            repo_owner: Repository owner (organization or username)
            repo_name: Repository name
            enabled: Whether error reporting is enabled
            auto_labels: Labels to automatically add to created issues
            error_cache_file: Path to cache file for tracking reported errors
            max_reports_per_hour: Maximum number of issues to create per hour
        """
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.repo_owner = repo_owner or os.environ.get("GITHUB_REPO_OWNER", "endomorphosis")
        self.repo_name = repo_name or os.environ.get("GITHUB_REPO_NAME", "ipfs_kit_py")
        self.enabled = enabled and bool(self.github_token)
        self.auto_labels = auto_labels or ["auto-generated", "bug", "error-report"]
        self.error_cache_file = error_cache_file or os.path.join(
            os.path.expanduser("~"), ".ipfs_kit_error_cache.json"
        )
        self.max_reports_per_hour = max_reports_per_hour
        
        # Load error cache
        self.error_cache = self._load_error_cache()
        
        # GitHub API base URL
        self.api_base_url = "https://api.github.com"
        
        if not self.enabled:
            logger.warning(
                "GitHub error reporting is disabled. "
                "Set GITHUB_TOKEN environment variable to enable."
            )
    
    def _load_error_cache(self) -> Dict[str, Any]:
        """Load the error cache from disk."""
        if os.path.exists(self.error_cache_file):
            try:
                with open(self.error_cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load error cache: {e}")
        return {"errors": {}, "hourly_counts": {}}
    
    def _save_error_cache(self) -> None:
        """Save the error cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.error_cache_file), exist_ok=True)
            with open(self.error_cache_file, 'w') as f:
                json.dump(self.error_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save error cache: {e}")
    
    def _get_error_hash(self, error_info: Dict[str, Any]) -> str:
        """
        Generate a unique hash for an error based on its characteristics.
        
        Args:
            error_info: Dictionary containing error information
            
        Returns:
            Hash string for the error
        """
        # Create a canonical representation of the error
        error_signature = f"{error_info.get('error_type', '')}:{error_info.get('error_message', '')}"
        
        # Include the last line of the traceback for more specificity
        traceback_lines = error_info.get('traceback', '').split('\n')
        if traceback_lines:
            error_signature += f":{traceback_lines[-1]}"
        
        return hashlib.sha256(error_signature.encode()).hexdigest()[:16]
    
    def _check_rate_limit(self) -> bool:
        """
        Check if we've exceeded the rate limit for error reports.
        
        Returns:
            True if we can report more errors, False otherwise
        """
        current_hour = datetime.utcnow().strftime("%Y-%m-%d-%H")
        hourly_counts = self.error_cache.get("hourly_counts", {})
        
        # Clean up old hour entries
        hourly_counts = {k: v for k, v in hourly_counts.items() 
                        if k >= datetime.utcnow().strftime("%Y-%m-%d-%H")}
        self.error_cache["hourly_counts"] = hourly_counts
        
        # Check current hour count
        current_count = hourly_counts.get(current_hour, 0)
        return current_count < self.max_reports_per_hour
    
    def _increment_rate_limit(self) -> None:
        """Increment the rate limit counter for the current hour."""
        current_hour = datetime.utcnow().strftime("%Y-%m-%d-%H")
        hourly_counts = self.error_cache.get("hourly_counts", {})
        hourly_counts[current_hour] = hourly_counts.get(current_hour, 0) + 1
        self.error_cache["hourly_counts"] = hourly_counts
    
    def _should_report_error(self, error_hash: str) -> bool:
        """
        Determine if an error should be reported based on deduplication.
        
        Args:
            error_hash: Hash of the error
            
        Returns:
            True if the error should be reported, False otherwise
        """
        errors = self.error_cache.get("errors", {})
        
        if error_hash in errors:
            # Error has been reported before
            last_reported = errors[error_hash].get("last_reported")
            count = errors[error_hash].get("count", 0)
            
            # Update count
            errors[error_hash]["count"] = count + 1
            errors[error_hash]["last_seen"] = datetime.utcnow().isoformat()
            
            # Only report again if it's been more than 24 hours
            if last_reported:
                last_reported_time = datetime.fromisoformat(last_reported)
                hours_since = (datetime.utcnow() - last_reported_time).total_seconds() / 3600
                if hours_since < 24:
                    logger.debug(f"Error {error_hash} reported recently, skipping")
                    return False
        
        return True
    
    def _mark_error_reported(self, error_hash: str, issue_url: str) -> None:
        """
        Mark an error as reported in the cache.
        
        Args:
            error_hash: Hash of the error
            issue_url: URL of the created GitHub issue
        """
        errors = self.error_cache.get("errors", {})
        
        if error_hash not in errors:
            errors[error_hash] = {"count": 1}
        
        errors[error_hash].update({
            "last_reported": datetime.utcnow().isoformat(),
            "issue_url": issue_url,
        })
        
        self.error_cache["errors"] = errors
        self._save_error_cache()
    
    def _create_github_issue(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Create a GitHub issue using the GitHub API.
        
        Args:
            title: Issue title
            body: Issue body (markdown)
            labels: List of labels to add to the issue
            
        Returns:
            URL of the created issue, or None if creation failed
        """
        if not self.enabled:
            logger.warning("GitHub issue reporting is disabled")
            return None
        
        url = f"{self.api_base_url}/repos/{self.repo_owner}/{self.repo_name}/issues"
        
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        data = {
            "title": title,
            "body": body,
            "labels": labels or self.auto_labels,
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            response.raise_for_status()
            
            issue_data = response.json()
            issue_url = issue_data.get("html_url")
            logger.info(f"Created GitHub issue: {issue_url}")
            return issue_url
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create GitHub issue: {e}")
            return None
    
    def _format_error_report(
        self,
        error_info: Dict[str, Any],
        context: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Format an error report for GitHub issue creation.
        
        Args:
            error_info: Dictionary containing error information
            context: Optional context about where the error occurred
            
        Returns:
            Tuple of (title, body) for the GitHub issue
        """
        error_type = error_info.get("error_type", "Unknown Error")
        error_message = error_info.get("error_message", "No message provided")
        
        # Create title
        title = f"[Auto-Report] {error_type}: {error_message[:80]}"
        if len(error_message) > 80:
            title += "..."
        
        # Create body
        body_parts = [
            "## Automatic Error Report",
            "",
            f"**Error Type:** `{error_type}`",
            f"**Error Message:** {error_message}",
            f"**Timestamp:** {error_info.get('timestamp', 'Unknown')}",
            "",
        ]
        
        if context:
            body_parts.extend([
                f"**Context:** {context}",
                "",
            ])
        
        # Add environment information
        if "environment" in error_info:
            env = error_info["environment"]
            body_parts.extend([
                "### Environment",
                f"- **Python Version:** {env.get('python_version', 'Unknown')}",
                f"- **Platform:** {env.get('platform', 'Unknown')}",
                f"- **Component:** {env.get('component', 'Unknown')}",
                "",
            ])
        
        # Add traceback
        if "traceback" in error_info and error_info["traceback"]:
            body_parts.extend([
                "### Traceback",
                "```python",
                error_info["traceback"],
                "```",
                "",
            ])
        
        # Add additional details
        if "details" in error_info and error_info["details"]:
            body_parts.extend([
                "### Additional Details",
                "```json",
                json.dumps(error_info["details"], indent=2),
                "```",
                "",
            ])
        
        body_parts.extend([
            "---",
            "*This issue was automatically generated by the IPFS Kit error reporting system.*",
        ])
        
        return title, "\n".join(body_parts)
    
    def report_error(
        self,
        error: Exception,
        context: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Report an error by creating a GitHub issue.
        
        Args:
            error: The exception that occurred
            context: Optional context about where the error occurred
            additional_info: Additional information to include in the report
            
        Returns:
            URL of the created issue, or None if no issue was created
        """
        if not self.enabled:
            return None
        
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("Error reporting rate limit exceeded, skipping report")
            return None
        
        # Gather error information
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            "traceback": "".join(traceback.format_exception(
                type(error), error, error.__traceback__
            )),
            "environment": {
                "python_version": sys.version,
                "platform": sys.platform,
                "component": context or "Unknown",
            },
            "details": additional_info or {},
        }
        
        # Generate error hash for deduplication
        error_hash = self._get_error_hash(error_info)
        
        # Check if we should report this error
        if not self._should_report_error(error_hash):
            logger.debug(f"Skipping duplicate error report: {error_hash}")
            return None
        
        # Format error report
        title, body = self._format_error_report(error_info, context)
        
        # Create GitHub issue
        issue_url = self._create_github_issue(title, body)
        
        if issue_url:
            # Mark error as reported
            self._mark_error_reported(error_hash, issue_url)
            self._increment_rate_limit()
        
        return issue_url
    
    def report_error_dict(
        self,
        error_info: Dict[str, Any],
        context: Optional[str] = None,
    ) -> Optional[str]:
        """
        Report an error from a dictionary of error information.
        
        This is useful for reporting errors from non-Python sources like
        JavaScript errors from the MCP dashboard.
        
        Args:
            error_info: Dictionary containing error information
            context: Optional context about where the error occurred
            
        Returns:
            URL of the created issue, or None if no issue was created
        """
        if not self.enabled:
            return None
        
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("Error reporting rate limit exceeded, skipping report")
            return None
        
        # Ensure required fields
        if "error_type" not in error_info:
            error_info["error_type"] = "Unknown Error"
        if "error_message" not in error_info:
            error_info["error_message"] = "No message provided"
        if "timestamp" not in error_info:
            error_info["timestamp"] = datetime.utcnow().isoformat()
        
        # Generate error hash for deduplication
        error_hash = self._get_error_hash(error_info)
        
        # Check if we should report this error
        if not self._should_report_error(error_hash):
            logger.debug(f"Skipping duplicate error report: {error_hash}")
            return None
        
        # Format error report
        title, body = self._format_error_report(error_info, context)
        
        # Create GitHub issue
        issue_url = self._create_github_issue(title, body)
        
        if issue_url:
            # Mark error as reported
            self._mark_error_reported(error_hash, issue_url)
            self._increment_rate_limit()
        
        return issue_url


# Global error reporter instance
_global_reporter: Optional[GitHubIssueReporter] = None


def initialize_error_reporter(
    github_token: Optional[str] = None,
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    enabled: bool = True,
    **kwargs
) -> GitHubIssueReporter:
    """
    Initialize the global error reporter instance.
    
    Args:
        github_token: GitHub personal access token
        repo_owner: Repository owner
        repo_name: Repository name
        enabled: Whether to enable error reporting
        **kwargs: Additional arguments to pass to GitHubIssueReporter
        
    Returns:
        The initialized error reporter instance
    """
    global _global_reporter
    _global_reporter = GitHubIssueReporter(
        github_token=github_token,
        repo_owner=repo_owner,
        repo_name=repo_name,
        enabled=enabled,
        **kwargs
    )
    return _global_reporter


def get_error_reporter() -> Optional[GitHubIssueReporter]:
    """
    Get the global error reporter instance.
    
    Returns:
        The global error reporter instance, or None if not initialized
    """
    return _global_reporter


def report_error(
    error: Exception,
    context: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Report an error using the global error reporter.
    
    Args:
        error: The exception that occurred
        context: Optional context about where the error occurred
        additional_info: Additional information to include in the report
        
    Returns:
        URL of the created issue, or None if no issue was created
    """
    reporter = get_error_reporter()
    if reporter:
        return reporter.report_error(error, context, additional_info)
    return None
