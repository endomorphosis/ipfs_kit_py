"""
Storacha API Connection Manager

This module provides improved connection handling for the Storacha API,
implementing robust error handling, retry logic, and automatic endpoint failover.
"""

import time
import logging
import requests
import socket
import random
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse

# Configure logging
logger = logging.getLogger(__name__)


class StorachaConnectionManager:
    """
    Connection manager for Storacha API with enhanced reliability features.

    Provides robust connection handling with:
    - Multiple endpoint support with automatic failover
    - Exponential backoff for retries
    - Health checking and endpoint validation
    - Connection pooling via requests.Session
    - Detailed connection status tracking
    """
    # Default endpoints to try in order of preference
    DEFAULT_ENDPOINTS = [
        "https://up.storacha.network/bridge",  # Primary endpoint
        "https://api.web3.storage",  # Legacy endpoint
        "https://api.storacha.io",  # Alternative endpoint
        "https://up.web3.storage/bridge",  # Alternative bridge endpoint
    ]

    def __init__(
        self
        api_key: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        endpoints: Optional[List[str]] = None,
        max_retries: int = 3,
        timeout: int = 30,
        validate_endpoints: bool = True,
    ):
        """
        Initialize the Storacha connection manager.

        Args:
            api_key: Storacha API key
            api_endpoint: Primary API endpoint to use
            endpoints: List of fallback endpoints to try
            max_retries: Maximum number of retry attempts per endpoint
            timeout: Request timeout in seconds
            validate_endpoints: Whether to validate endpoints on initialization
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

        # Setup endpoints list
        self.endpoints = []

        # Add primary endpoint if specified
        if api_endpoint:
            self.endpoints.append(api_endpoint)

        # Add provided endpoints list
        if endpoints:
            for endpoint in endpoints:
                if endpoint not in self.endpoints:
                    self.endpoints.append(endpoint)

        # Add default endpoints if we still need more
        if not self.endpoints:
            self.endpoints = self.DEFAULT_ENDPOINTS.copy()
        elif len(self.endpoints) < 2:
            # Add some defaults as fallbacks if only one was specified
            for endpoint in self.DEFAULT_ENDPOINTS:
                if endpoint not in self.endpoints:
                    self.endpoints.append(endpoint)

        # Initialize connection state
        self.working_endpoint = None
        self.last_working_time = 0
        self.endpoint_health = {
            endpoint: {"healthy": None, "last_checked": 0, "failures": 0}
            for endpoint in self.endpoints
        }

        # Create session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

        # Validate endpoints if requested
        if validate_endpoints:
            self._validate_endpoints()

    def _validate_endpoints(self) -> None:
        """
        Validate all endpoints and establish a preferred working endpoint.
        """
        logger.info(f"Validating {len(self.endpoints)} Storacha endpoints")

        for endpoint in self.endpoints:
            try:
                # Verify DNS resolution
                url_parts = urlparse(endpoint)
                if not self._check_dns_resolution(url_parts.netloc):
                    logger.warning(f"DNS resolution failed for {endpoint}")
                    self.endpoint_health[endpoint]["healthy"] = False
                    self.endpoint_health[endpoint]["last_checked"] = time.time()
                    self.endpoint_health[endpoint]["failures"] += 1
                    continue

                # Try a simple GET request to validate endpoint
                response = self.session.get(f"{endpoint}/health", timeout=self.timeout)

                if response.status_code == 200:
                    logger.info(f"Validated Storacha endpoint: {endpoint}")
                    self.working_endpoint = endpoint
                    self.last_working_time = time.time()
                    self.endpoint_health[endpoint]["healthy"] = True
                    self.endpoint_health[endpoint]["last_checked"] = time.time()
                    # Once we find a working endpoint, we can stop checking others
                    break
                else:
                    logger.warning(
                        f"Endpoint {endpoint} returned status code {response.status_code}"
                    )
                    self.endpoint_health[endpoint]["healthy"] = False
                    self.endpoint_health[endpoint]["last_checked"] = time.time()
                    self.endpoint_health[endpoint]["failures"] += 1

            except (requests.RequestException, socket.gaierror) as e:
                logger.warning(f"Error validating endpoint {endpoint}: {e}")
                self.endpoint_health[endpoint]["healthy"] = False
                self.endpoint_health[endpoint]["last_checked"] = time.time()
                self.endpoint_health[endpoint]["failures"] += 1

        # If no working endpoint found, but we never actually checked due to DNS issues
        if not self.working_endpoint:
            logger.warning("No working Storacha endpoints found during validation")

        # Log overall status
        healthy_count = sum(1 for status in self.endpoint_health.values() if status["healthy"])
        logger.info(
            f"Endpoint validation complete. {healthy_count}/{len(self.endpoints)} endpoints healthy"
        )

    def _check_dns_resolution(self, hostname: str) -> bool:
        """
        Check if a hostname can be resolved via DNS.

        Args:
            hostname: Hostname to check

        Returns:
            True if resolution succeeded, False otherwise
        """
        try:
            # Handle cases where hostname includes port
            if ":" in hostname:
                hostname = hostname.split(":")[0]

            socket.gethostbyname(hostname)
            return True
        except socket.gaierror as e:
            logger.warning(f"DNS resolution failed for {hostname}: {e}")
            return False

    def _get_endpoint(self) -> str:
        """
        Get the current preferred endpoint to use.

        Returns:
            API endpoint URL
        """
        # If we have a working endpoint that was validated recently, use it
        if self.working_endpoint and (time.time() - self.last_working_time) < 300:  # 5 minutes
            return self.working_endpoint

        # If our working endpoint is stale or we don't have one,
        # re-validate endpoints occasionally
        if not self.working_endpoint or (time.time() - self.last_working_time) > 300:
            self._validate_endpoints()
            if self.working_endpoint:
                return self.working_endpoint

        # If we still don't have a working endpoint, try the first one
        # or a random one if we've had failures
        if not self.working_endpoint:
            if all(status["failures"] > 0 for status in self.endpoint_health.values()):
                # If all endpoints have failed, choose one with the fewest failures
                min_failures = min(status["failures"] for status in self.endpoint_health.values())
                candidates = [
                    ep
                    for ep, status in self.endpoint_health.items()
                    if status["failures"] == min_failures
                ]
                return random.choice(candidates)
            else:
                # Use the first endpoint that hasn't failed yet
                for endpoint, status in self.endpoint_health.items():
                    if status["failures"] == 0:
                        return endpoint

                # Fallback to first endpoint
                return self.endpoints[0]

        # Final fallback to first endpoint
        return self.endpoints[0]

    def _retry_request(
        self, method: str, endpoint: str, path: str, **kwargs
    ) -> Tuple[requests.Response, str]:
        """
        Send a request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            path: API path (without leading slash)
            **kwargs: Additional arguments to pass to requests

        Returns:
            Tuple of (Response, endpoint used)

        Raises:
            requests.RequestException: If all retries fail
        """
        # Ensure we have a timeout
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        # Initialize for retry loop
        retry_count = 0
        last_exception = None
        current_endpoint = endpoint

        while retry_count <= self.max_retries:
            try:
                # Construct URL
                url = f"{current_endpoint}/{path.lstrip('/')}"

                # Send request
                method_func = getattr(self.session, method.lower())
                response = method_func(url, **kwargs)

                # Update endpoint health on success
                self.endpoint_health[current_endpoint]["healthy"] = True
                self.endpoint_health[current_endpoint]["last_checked"] = time.time()

                # Update working endpoint
                self.working_endpoint = current_endpoint
                self.last_working_time = time.time()

                # Return successful response
                return response, current_endpoint

            except (requests.RequestException, socket.gaierror) as e:
                last_exception = e
                logger.warning(
                    f"Request to {current_endpoint} failed (attempt {retry_count + 1}/{self.max_retries + 1}): {e}"
                )

                # Mark endpoint as unhealthy
                self.endpoint_health[current_endpoint]["healthy"] = False
                self.endpoint_health[current_endpoint]["last_checked"] = time.time()
                self.endpoint_health[current_endpoint]["failures"] += 1

                # If this was the current working endpoint, clear it
                if self.working_endpoint == current_endpoint:
                    self.working_endpoint = None

                # Try next endpoint before incrementing retry count
                if retry_count < self.max_retries:
                    # Choose a different endpoint for next retry
                    candidates = [ep for ep in self.endpoints if ep != current_endpoint]
                    if candidates:
                        # Prefer endpoints with fewer failures
                        candidates.sort(key=lambda ep: self.endpoint_health[ep]["failures"])
                        current_endpoint = candidates[0]
                        logger.info(f"Switching to alternative endpoint: {current_endpoint}")

                    # Add exponential backoff delay
                    backoff_time = 0.1 * (2**retry_count)  # 0.1, 0.2, 0.4, 0.8, ...
                    logger.info(f"Retrying in {backoff_time:.2f} seconds...")
                    time.sleep(backoff_time)

                retry_count += 1

        # If we've exhausted all retries, raise the last exception
        logger.error(f"All retry attempts failed for {path}")
        raise last_exception or requests.RequestException("All retry attempts failed")

    def send_request(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        Send a request to the Storacha API with automatic retries and endpoint failover.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (without leading slash)
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object

        Raises:
            requests.RequestException: If all retries fail
        """
        endpoint = self._get_endpoint()
        response, used_endpoint = self._retry_request(method, endpoint, path, **kwargs)

        # If we used a different endpoint than originally selected, update our preference
        if used_endpoint != endpoint:
            self.working_endpoint = used_endpoint
            self.last_working_time = time.time()

        return response

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current connection status.

        Returns:
            Status information dictionary
        """
        return {
            "working_endpoint": self.working_endpoint,
            "last_working_time": self.last_working_time,
            "endpoints": [
                {
                    "url": endpoint
                    "healthy": status["healthy"],
                    "last_checked": status["last_checked"],
                    "failures": status["failures"],
                }
                for endpoint, status in self.endpoint_health.items()
            ],
            "connection_pooling_enabled": True
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "authenticated": bool(self.api_key),
        }
