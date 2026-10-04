"""
Filecoin API Connection Manager

This module provides improved connection handling for Filecoin API interactions,
implementing robust error handling, retry logic, and automatic endpoint failover.
"""

import time
import logging
import requests
import socket
import random
import json
import os
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from urllib.parse import urlparse
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)


class FilecoinApiError(Exception):
    """Exception raised for Filecoin API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response: Optional[Dict[str, Any]] = None, error_code: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        self.error_code = error_code
        super().__init__(self.message)


class FilecoinConnectionManager:
    """
    Connection manager for Filecoin API with enhanced reliability features.

    Provides robust connection handling with:
    - Multiple endpoint support with automatic failover
    - Exponential backoff for retries
    - Health checking and endpoint validation
    - Connection pooling via requests.Session
    - Detailed connection status tracking
    - Rate limiting detection and handling
    - Circuit breaker pattern for failing endpoints
    """
    # Default endpoints to try in order of preference
    DEFAULT_ENDPOINTS = [
        "https://api.node.glif.io/rpc/v0",      # Glif mainnet node (primary)
        "https://filecoin.infura.io/v3/public", # Infura public node
        "https://lotus.miner.report/rpc/v0",    # Lotus Miner Report API
        "https://api.chain.love/rpc/v0"         # Chain Love API
    ]
    
    # Default rate limit parameters
    DEFAULT_RATE_LIMIT = {
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "max_burst": 20
    }

    def __init__(
        self,
        token: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        endpoints: Optional[List[str]] = None,
        max_retries: int = 3,
        timeout: int = 30,
        validate_endpoints: bool = True,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_reset_time: int = 300,  # 5 minutes
        rate_limits: Optional[Dict[str, int]] = None,
        node_version_threshold: str = "1.15.0"  # Minimum acceptable Lotus version
    ):
        """
        Initialize the Filecoin connection manager.

        Args:
            token: Filecoin API token
            api_endpoint: Primary API endpoint to use
            endpoints: List of fallback endpoints to try
            max_retries: Maximum number of retry attempts per endpoint
            timeout: Request timeout in seconds
            validate_endpoints: Whether to validate endpoints on initialization
            circuit_breaker_threshold: Number of failures before circuit opens
            circuit_breaker_reset_time: Time in seconds before retrying a failed endpoint
            rate_limits: Custom rate limits to use
            node_version_threshold: Minimum acceptable Lotus version
        """
        self.token = token
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_time = circuit_breaker_reset_time
        self.rate_limits = rate_limits or self.DEFAULT_RATE_LIMIT.copy()
        self.node_version_threshold = node_version_threshold
        self.request_id = 0  # For JSON-RPC requests

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
            endpoint: {
                "healthy": None,                 # Current health status
                "last_checked": 0,               # Timestamp of last health check
                "failures": 0,                   # Consecutive failures
                "total_failures": 0,             # Total lifetime failures
                "circuit_open": False,           # Circuit breaker status
                "circuit_open_until": 0,         # When to try the endpoint again
                "success_rate": 100.0,           # Success percentage
                "avg_response_time": 0,          # Average response time in ms
                "last_latency": 0,               # Last response time in ms
                "requests_count": 0,             # Total requests made to this endpoint
                "success_count": 0,              # Total successful requests
                "version": None,                 # Lotus version if known
                "height": None                   # Chain height if known
            }
            for endpoint in self.endpoints
        }
        
        # Rate limiting tracking
        self.request_timestamps = []  # List of recent request timestamps
        self.rate_limited_until = 0   # Timestamp when rate limiting expires
        
        # Request metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.last_request_time = 0
        self.last_error = None

        # Create session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "FilecoinConnectionManager/1.0"
        })
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})

        # Chain stats
        self.chain_height = None
        self.last_chain_height_update = 0
        self.current_base_fee = None
        self.last_base_fee_update = 0

        # Validate endpoints if requested
        if validate_endpoints:
            self._validate_endpoints()

    def _validate_endpoints(self) -> None:
        """
        Validate all endpoints and establish a preferred working endpoint.
        """
        logger.info(f"Validating {len(self.endpoints)} Filecoin endpoints")

        for endpoint in self.endpoints:
            # Skip endpoints with open circuit breakers
            if self._is_circuit_open(endpoint):
                logger.info(f"Skipping endpoint {endpoint} due to open circuit breaker")
                continue
                
            try:
                # Verify DNS resolution
                url_parts = urlparse(endpoint)
                if not self._check_dns_resolution(url_parts.netloc):
                    logger.warning(f"DNS resolution failed for {endpoint}")
                    self._record_endpoint_failure(endpoint)
                    continue

                # Try a simple health check request
                start_time = time.time()
                
                # Create JSON-RPC request to get node version
                response = self._make_jsonrpc_request(
                    endpoint, 
                    "Filecoin.Version", 
                    [],
                    timeout=self.timeout
                )
                
                end_time = time.time()
                latency = int((end_time - start_time) * 1000)  # Convert to ms

                # Check if request was successful
                if "result" in response:
                    version = response["result"].get("Version", "unknown")
                    
                    # Extract version numbers for comparison
                    version_numbers = self._parse_version(version)
                    threshold_numbers = self._parse_version(self.node_version_threshold)
                    
                    if version_numbers < threshold_numbers:
                        logger.warning(
                            f"Endpoint {endpoint} has version {version} which is below " +
                            f"the minimum threshold {self.node_version_threshold}"
                        )
                        self._record_endpoint_warning(endpoint, latency, version=version)
                    else:
                        logger.info(f"Validated Filecoin endpoint: {endpoint} (latency: {latency}ms, version: {version})")
                        self.working_endpoint = endpoint
                        self.last_working_time = time.time()
                        self._record_endpoint_success(endpoint, latency, version=version)
                        
                        # Get additional endpoint information (chain height)
                        try:
                            height_response = self._make_jsonrpc_request(
                                endpoint, 
                                "Filecoin.ChainHead", 
                                [],
                                timeout=self.timeout
                            )
                            
                            if "result" in height_response:
                                height = height_response["result"].get("Height", 0)
                                if isinstance(height, int) and height > 0:
                                    self.endpoint_health[endpoint]["height"] = height
                                    self.chain_height = height
                                    self.last_chain_height_update = time.time()
                        except Exception as e:
                            # Non-critical error, just log and continue
                            logger.warning(f"Failed to get chain height from {endpoint}: {e}")
                        
                        # Once we find a working endpoint, we can stop checking others
                        break
                else:
                    error_info = response.get("error", {})
                    error_msg = error_info.get("message", "Unknown error")
                    logger.warning(
                        f"Endpoint {endpoint} returned error: {error_msg}"
                    )
                    self._record_endpoint_failure(endpoint)

            except (requests.RequestException, socket.gaierror, FilecoinApiError) as e:
                logger.warning(f"Error validating endpoint {endpoint}: {e}")
                self._record_endpoint_failure(endpoint)

        # If no working endpoint found, but we never actually checked due to DNS issues
        if not self.working_endpoint:
            logger.warning("No working Filecoin endpoints found during validation")

        # Log overall status
        healthy_count = sum(1 for status in self.endpoint_health.values() if status["healthy"])
        logger.info(
            f"Endpoint validation complete. {healthy_count}/{len(self.endpoints)} endpoints healthy"
        )
    
    def _parse_version(self, version_str: str) -> tuple:
        """
        Parse a version string into a tuple for comparison.
        
        Args:
            version_str: Version string (e.g., "1.15.0")
            
        Returns:
            Tuple of version components (e.g., (1, 15, 0))
        """
        # Extract only the numeric part if there's a prefix or suffix
        import re
        match = re.search(r'(\d+\.\d+\.\d+)', version_str)
        if match:
            version_str = match.group(1)
            
        # Split by dot and convert to integers
        parts = []
        for part in version_str.split('.'):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        
        # Ensure we have at least 3 components
        while len(parts) < 3:
            parts.append(0)
            
        return tuple(parts)

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
    
    def _is_circuit_open(self, endpoint: str) -> bool:
        """
        Check if the circuit breaker is open for an endpoint.
        
        Args:
            endpoint: The endpoint to check
            
        Returns:
            True if circuit breaker is open, False otherwise
        """
        status = self.endpoint_health[endpoint]
        if not status["circuit_open"]:
            return False
            
        # Check if it's time to try again
        if time.time() > status["circuit_open_until"]:
            logger.info(f"Circuit breaker timeout elapsed for {endpoint}, resetting")
            status["circuit_open"] = False
            status["failures"] = 0
            return False
            
        return True
    
    def _record_endpoint_success(self, endpoint: str, latency_ms: int, **kwargs) -> None:
        """
        Record a successful request to an endpoint.
        
        Args:
            endpoint: The endpoint that was successful
            latency_ms: Request latency in milliseconds
            **kwargs: Additional stats to record (e.g., version, height)
        """
        status = self.endpoint_health[endpoint]
        
        # Update status
        status["healthy"] = True
        status["last_checked"] = time.time()
        status["failures"] = 0  # Reset consecutive failures
        status["circuit_open"] = False
        status["requests_count"] += 1
        status["success_count"] += 1
        status["last_latency"] = latency_ms
        
        # Update additional stats if provided
        for key, value in kwargs.items():
            if key in status:
                status[key] = value
        
        # Update average latency
        if status["avg_response_time"] == 0:
            status["avg_response_time"] = latency_ms
        else:
            # Weighted average (80% old, 20% new)
            status["avg_response_time"] = (
                0.8 * status["avg_response_time"] + 0.2 * latency_ms
            )
        
        # Update success rate
        if status["requests_count"] > 0:
            status["success_rate"] = (
                status["success_count"] / status["requests_count"] * 100
            )
    
    def _record_endpoint_warning(self, endpoint: str, latency_ms: int, **kwargs) -> None:
        """
        Record a warning for an endpoint (used for version warnings, etc.).
        
        Args:
            endpoint: The endpoint that was successful but with warnings
            latency_ms: Request latency in milliseconds
            **kwargs: Additional stats to record (e.g., version, height)
        """
        status = self.endpoint_health[endpoint]
        
        # Update status - warnings don't count as failures
        status["healthy"] = True  # It's still healthy, just not preferred
        status["last_checked"] = time.time()
        status["requests_count"] += 1
        status["success_count"] += 1
        status["last_latency"] = latency_ms
        
        # Update additional stats if provided
        for key, value in kwargs.items():
            if key in status:
                status[key] = value
        
        # Update average latency
        if status["avg_response_time"] == 0:
            status["avg_response_time"] = latency_ms
        else:
            # Weighted average
            status["avg_response_time"] = (
                0.8 * status["avg_response_time"] + 0.2 * latency_ms
            )
        
        # Update success rate
        if status["requests_count"] > 0:
            status["success_rate"] = (
                status["success_count"] / status["requests_count"] * 100
            )
    
    def _record_endpoint_failure(self, endpoint: str) -> None:
        """
        Record a failed request to an endpoint.
        
        Args:
            endpoint: The endpoint that failed
        """
        status = self.endpoint_health[endpoint]
        
        # Update status
        status["healthy"] = False
        status["last_checked"] = time.time()
        status["failures"] += 1
        status["total_failures"] += 1
        status["requests_count"] += 1
        
        # Update success rate
        if status["requests_count"] > 0:
            status["success_rate"] = (
                status["success_count"] / status["requests_count"] * 100
            )
        
        # Check if we need to open the circuit breaker
        if status["failures"] >= self.circuit_breaker_threshold:
            logger.warning(
                f"Circuit breaker triggered for endpoint {endpoint} after {status['failures']} failures"
            )
            status["circuit_open"] = True
            status["circuit_open_until"] = time.time() + self.circuit_breaker_reset_time

    def _check_rate_limiting(self) -> bool:
        """
        Check if we're currently rate limited.
        
        Returns:
            True if currently rate limited, False otherwise
        """
        # First check if we have an active rate limit period
        current_time = time.time()
        if current_time < self.rate_limited_until:
            wait_time = self.rate_limited_until - current_time
            logger.warning(f"Currently rate limited. Retry after {wait_time:.1f} seconds")
            return True
            
        # Clean up old request timestamps
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        one_hour_ago = now - timedelta(hours=1)
        
        # Keep only timestamps within the last hour
        self.request_timestamps = [ts for ts in self.request_timestamps if ts > one_hour_ago]
        
        # Count requests in the last minute and hour
        requests_last_minute = sum(1 for ts in self.request_timestamps if ts > one_minute_ago)
        requests_last_hour = len(self.request_timestamps)
        
        # Check if we're approaching rate limits
        if requests_last_minute >= self.rate_limits["requests_per_minute"]:
            logger.warning(f"Rate limit approached: {requests_last_minute}/{self.rate_limits['requests_per_minute']} requests in the last minute")
            self.rate_limited_until = current_time + 30  # Wait 30 seconds
            return True
            
        if requests_last_hour >= self.rate_limits["requests_per_hour"]:
            logger.warning(f"Rate limit approached: {requests_last_hour}/{self.rate_limits['requests_per_hour']} requests in the last hour")
            self.rate_limited_until = current_time + 300  # Wait 5 minutes
            return True
            
        return False
    
    def _update_rate_limiting(self, response: requests.Response) -> bool:
        """
        Update rate limiting based on response headers.
        
        Args:
            response: The HTTP response
            
        Returns:
            True if rate limited, False otherwise
        """
        # Record the request timestamp
        self.request_timestamps.append(datetime.now())
        
        # Check for rate limit headers
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        
        # Common status codes for rate limiting
        if response.status_code in (429, 503):
            logger.warning("Rate limit or service overload response received")
            
            if reset:
                try:
                    reset_time = int(reset)
                    self.rate_limited_until = reset_time
                    wait_time = max(0, reset_time - time.time())
                    logger.warning(f"Rate limited. Retry after {wait_time:.1f} seconds")
                except ValueError:
                    # If we can't parse the reset time, use a default wait
                    self.rate_limited_until = time.time() + 60
                    logger.warning("Rate limited. Using default wait time of 60 seconds")
            else:
                # No reset header, use default wait time
                self.rate_limited_until = time.time() + 60
                logger.warning("Rate limited. Using default wait time of 60 seconds")
                
            return True
            
        elif remaining and int(remaining) <= 5:
            # We're getting close to the limit
            logger.warning(f"Approaching rate limit: {remaining} requests remaining")
            
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

        # If we still don't have a working endpoint, use a selection strategy
        # First, filter out endpoints with open circuit breakers
        available_endpoints = [
            ep for ep in self.endpoints 
            if not self._is_circuit_open(ep)
        ]
        
        if not available_endpoints:
            # All endpoints have open circuit breakers. 
            # Choose the one that will reset soonest
            logger.warning("All endpoints have open circuit breakers")
            endpoint = min(
                self.endpoints,
                key=lambda ep: self.endpoint_health[ep]["circuit_open_until"]
            )
            # Force the circuit closed since we have no choice
            self.endpoint_health[endpoint]["circuit_open"] = False
            self.endpoint_health[endpoint]["failures"] = 0
            logger.info(f"Forcing circuit closed for {endpoint} as all endpoints are unavailable")
            return endpoint
        
        # Rank available endpoints by health metrics
        ranked_endpoints = sorted(
            available_endpoints,
            key=lambda ep: (
                -1 if self.endpoint_health[ep]["healthy"] else 0,  # Prefer healthy endpoints
                -self.endpoint_health[ep]["success_rate"],          # Higher success rate
                self.endpoint_health[ep]["avg_response_time"],      # Lower latency
                self.endpoint_health[ep]["failures"],               # Fewer failures
            )
        )
        
        # Return the highest ranked endpoint
        return ranked_endpoints[0]
    
    def _make_jsonrpc_request(
        self, 
        endpoint: str, 
        method: str, 
        params: List[Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make a JSON-RPC request to a specific endpoint.
        
        Args:
            endpoint: The endpoint to send the request to
            method: JSON-RPC method name
            params: Parameters for the method
            **kwargs: Additional arguments for requests
            
        Returns:
            JSON-RPC response dictionary
            
        Raises:
            FilecoinApiError: If there's an API error
            requests.RequestException: For network/connection errors
        """
        # Get a new request ID
        self.request_id += 1
        
        # Build the JSON-RPC request
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.request_id
        }
        
        # Ensure we have a timeout
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout
        
        try:
            # Make the request
            response = self.session.post(
                endpoint,
                json=jsonrpc_request,
                **kwargs
            )
            
            # Check for rate limiting
            self._update_rate_limiting(response)
            
            # Parse the response
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    # Check for JSON-RPC error
                    if "error" in result:
                        error = result["error"]
                        error_msg = error.get("message", "Unknown JSON-RPC error")
                        error_code = error.get("code", -1)
                        
                        # Convert to FilecoinApiError but still return the result
                        # so the caller can handle it
                        logger.warning(f"JSON-RPC error: {error_msg} (code: {error_code})")
                    
                    return result
                except ValueError:
                    raise FilecoinApiError(
                        "Invalid JSON response",
                        status_code=response.status_code,
                        response={"body": response.text[:1000]}  # First 1000 chars
                    )
            else:
                # Non-200 response
                try:
                    error_data = response.json()
                except ValueError:
                    error_data = {"body": response.text[:1000] if response.text else "Empty response"}
                
                raise FilecoinApiError(
                    f"HTTP error: {response.status_code}",
                    status_code=response.status_code,
                    response=error_data
                )
                
        except requests.RequestException as e:
            # Network/connection error
            raise FilecoinApiError(
                f"Request error: {str(e)}",
                error_code="REQUEST_ERROR"
            )
        
    def call(self, method: str, params: List[Any], **kwargs) -> Dict[str, Any]:
        """
        Call a Filecoin JSON-RPC method with automatic retries and endpoint failover.
        
        Args:
            method: JSON-RPC method name
            params: Parameters for the method
            **kwargs: Additional arguments for requests
            
        Returns:
            Result from the JSON-RPC response
            
        Raises:
            FilecoinApiError: If all retries fail or the API returns an error
        """
        # Check rate limiting
        if self._check_rate_limiting():
            wait_time = max(0, self.rate_limited_until - time.time())
            raise FilecoinApiError(
                f"Rate limit exceeded. Retry after {wait_time:.1f} seconds",
                status_code=429,
                error_code="RATE_LIMIT_EXCEEDED"
            )
        
        # Get the best endpoint to use
        endpoint = self._get_endpoint()
        
        # Initialize for retry loop
        retry_count = 0
        last_error = None
        current_endpoint = endpoint
        
        # Update metrics
        self.total_requests += 1
        self.last_request_time = time.time()
        
        while retry_count <= self.max_retries:
            # Check if the current endpoint's circuit breaker is open
            if self._is_circuit_open(current_endpoint):
                logger.info(f"Circuit breaker open for {current_endpoint}, trying another endpoint")
                # Try to find an alternative endpoint
                alternatives = [ep for ep in self.endpoints if ep != current_endpoint and not self._is_circuit_open(ep)]
                if alternatives:
                    # Choose the alternative with best health metrics
                    alternatives.sort(
                        key=lambda ep: (
                            -1 if self.endpoint_health[ep]["healthy"] else 0,
                            -self.endpoint_health[ep]["success_rate"],
                            self.endpoint_health[ep]["avg_response_time"]
                        )
                    )
                    current_endpoint = alternatives[0]
                    logger.info(f"Switching to alternative endpoint: {current_endpoint}")
                else:
                    # All alternatives have open circuit breakers too
                    # Force the one with the fewest failures
                    current_endpoint = min(
                        self.endpoints,
                        key=lambda ep: self.endpoint_health[ep]["failures"]
                    )
                    # Reset its circuit breaker
                    self.endpoint_health[current_endpoint]["circuit_open"] = False
                    self.endpoint_health[current_endpoint]["failures"] = 0
                    logger.info(f"All endpoints have open circuit breakers. Forcing reset for {current_endpoint}")
            
            try:
                start_time = time.time()
                
                # Make the JSON-RPC request
                response = self._make_jsonrpc_request(
                    current_endpoint, 
                    method, 
                    params,
                    **kwargs
                )
                
                end_time = time.time()
                latency = int((end_time - start_time) * 1000)
                
                # Check for JSON-RPC error
                if "error" in response:
                    error = response["error"]
                    error_msg = error.get("message", "Unknown JSON-RPC error")
                    error_code = error.get("code", -1)
                    
                    # Decide if this error should trigger a retry
                    if error_code in (-32603, -32000) and retry_count < self.max_retries:  # Internal error
                        logger.warning(f"JSON-RPC error from {current_endpoint}: {error_msg} (code: {error_code})")
                        self._record_endpoint_failure(current_endpoint)
                        
                        # Try another endpoint or retry after backoff
                        alternatives = [ep for ep in self.endpoints if ep != current_endpoint and not self._is_circuit_open(ep)]
                        if alternatives:
                            current_endpoint = random.choice(alternatives)
                            logger.info(f"JSON-RPC error, switching to {current_endpoint}")
                        else:
                            # Exponential backoff
                            backoff_time = 0.1 * (2**retry_count)
                            logger.info(f"Retrying in {backoff_time:.2f} seconds...")
                            time.sleep(backoff_time)
                        
                        retry_count += 1
                        continue
                    
                    # Non-retryable error - record failure but return the response
                    self._record_endpoint_failure(current_endpoint)
                    self.failed_requests += 1
                    self.last_error = error_msg
                    
                    # Include the error details in the returned JSON-RPC response
                    return response
                
                # Update endpoint health on success
                self._record_endpoint_success(current_endpoint, latency)
                self.successful_requests += 1
                
                # Update working endpoint
                self.working_endpoint = current_endpoint
                self.last_working_time = time.time()
                
                # Extract only the result part for nicer API
                return response
                
            except (requests.RequestException, FilecoinApiError) as e:
                last_error = e
                logger.warning(
                    f"Request to {current_endpoint} failed (attempt {retry_count + 1}/{self.max_retries + 1}): {e}"
                )
                
                # Update metrics
                self.failed_requests += 1
                self.last_error = str(e)
                
                # Mark endpoint as unhealthy
                self._record_endpoint_failure(current_endpoint)
                
                # If this was the current working endpoint, clear it
                if self.working_endpoint == current_endpoint:
                    self.working_endpoint = None
                
                # Try next endpoint before incrementing retry count
                if retry_count < self.max_retries:
                    # Choose a different endpoint for next retry
                    candidates = [ep for ep in self.endpoints if ep != current_endpoint and not self._is_circuit_open(ep)]
                    if candidates:
                        # Prefer endpoints with fewer failures
                        candidates.sort(key=lambda ep: self.endpoint_health[ep]["failures"])
                        current_endpoint = candidates[0]
                        logger.info(f"Switching to alternative endpoint: {current_endpoint}")
                    
                    # Add exponential backoff delay
                    backoff_time = 0.1 * (2**retry_count)
                    logger.info(f"Retrying in {backoff_time:.2f} seconds...")
                    time.sleep(backoff_time)
                
                retry_count += 1
        
        # If we've exhausted all retries, raise the last error
        logger.error(f"All retry attempts failed for method {method}")
        if isinstance(last_error, FilecoinApiError):
            raise last_error
        
        # If we get here without a FilecoinApiError, convert the last error
        if last_error:
            raise FilecoinApiError(
                f"All retry attempts failed: {str(last_error)}",
                error_code="RETRY_EXHAUSTED"
            )
        else:
            raise FilecoinApiError(
                "All retry attempts failed with unknown error",
                error_code="RETRY_EXHAUSTED_UNKNOWN"
            )
    
    def get_chain_head(self) -> Dict[str, Any]:
        """
        Get the current chain head.
        
        Returns:
            Chain head information
        """
        response = self.call("Filecoin.ChainHead", [])
        
        if "result" in response:
            # Update chain stats
            height = response["result"].get("Height")
            if height:
                self.chain_height = height
                self.last_chain_height_update = time.time()
                
            return response["result"]
        else:
            return {}
    
    def get_node_info(self) -> Dict[str, Any]:
        """
        Get information about the node.
        
        Returns:
            Node information including version
        """
        response = self.call("Filecoin.Version", [])
        
        if "result" in response:
            return response["result"]
        else:
            return {}
    
    def get_base_fee(self) -> Optional[str]:
        """
        Get the current base fee.
        
        Returns:
            Base fee as a string, or None if not available
        """
        # Get the chain head first
        head = self.get_chain_head()
        
        if not head or "Blocks" not in head or not head["Blocks"]:
            return None
            
        # Get the base fee from the first block
        parents = head["Blocks"][0].get("Parents", [])
        if not parents:
            return None
            
        # Try to get base fee from parent receipts
        try:
            parent_hash = parents[0].get("/", "")
            if not parent_hash:
                return None
                
            # Get parent receipts for the first parent
            response = self.call("Filecoin.ChainGetParentReceipts", [{"'/": parent_hash}])
            
            if "result" in response and response["result"]:
                # Base fee is usually in the first message's result
                base_fee = response["result"][0].get("BaseFee")
                if base_fee:
                    self.current_base_fee = base_fee
                    self.last_base_fee_update = time.time()
                return base_fee
        except Exception as e:
            logger.warning(f"Error getting base fee: {e}")
            
        return None
    
    def get_miner_info(self, miner_address: str) -> Dict[str, Any]:
        """
        Get information about a miner.
        
        Args:
            miner_address: Miner address (e.g., "f01234")
            
        Returns:
            Miner information
        """
        response = self.call("Filecoin.StateMinerInfo", [miner_address, None])
        
        if "result" in response:
            return response["result"]
        else:
            return {}
    
    def get_message_status(self, cid: str) -> Dict[str, Any]:
        """
        Get the status of a message.
        
        Args:
            cid: Message CID
            
        Returns:
            Message status information
        """
        response = self.call("Filecoin.ChainGetMessage", [{"'/": cid}])
        
        if "result" in response:
            return response["result"]
        else:
            return {}
    
    def estimate_gas(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimate gas for a message.
        
        Args:
            message: Message object
            
        Returns:
            Gas estimation
        """
        response = self.call("Filecoin.GasEstimateMessageGas", [message, None, None])
        
        if "result" in response:
            return response["result"]
        else:
            return {}
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current connection status.

        Returns:
            Status information dictionary
        """
        # Calculate overall success rate
        success_rate = 0
        if self.total_requests > 0:
            success_rate = (self.successful_requests / self.total_requests) * 100

        return {
            "working_endpoint": self.working_endpoint,
            "last_working_time": self.last_working_time,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "last_request_time": self.last_request_time,
            "last_error": self.last_error,
            "rate_limited_until": self.rate_limited_until,
            "rate_limits": self.rate_limits,
            "chain_stats": {
                "height": self.chain_height,
                "last_height_update": self.last_chain_height_update,
                "base_fee": self.current_base_fee,
                "last_base_fee_update": self.last_base_fee_update
            },
            "endpoints": [
                {
                    "url": endpoint,
                    "healthy": status["healthy"],
                    "last_checked": status["last_checked"],
                    "failures": status["failures"],
                    "total_failures": status["total_failures"],
                    "success_rate": status["success_rate"],
                    "avg_response_time": status["avg_response_time"],
                    "last_latency": status["last_latency"],
                    "circuit_open": status["circuit_open"],
                    "circuit_open_until": status["circuit_open_until"],
                    "version": status["version"],
                    "height": status["height"]
                }
                for endpoint, status in self.endpoint_health.items()
            ],
            "connection_pooling_enabled": True,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "authenticated": bool(self.token),
            "circuit_breaker": {
                "threshold": self.circuit_breaker_threshold,
                "reset_time": self.circuit_breaker_reset_time
            }
        }