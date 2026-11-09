"""
Storacha API Connection Manager

This module provides improved connection handling for the Storacha API,
implementing robust error handling, retry logic, and automatic endpoint failover.
"""

import time
import logging
import json
import requests
import socket
import random
from typing import Dict, Any, List, Optional, Tuple, Union
from urllib.parse import urlparse
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)


class StorachaApiError(Exception):
    """Exception raised for Storacha API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class StorachaConnectionManager:
    """
    Connection manager for Storacha API with enhanced reliability features.

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
        "https://up.storacha.network/bridge",  # Primary endpoint
        "https://api.web3.storage",  # Legacy endpoint
        "https://api.storacha.network",  # Alternative endpoint
        "https://up.web3.storage/bridge",  # Alternative bridge endpoint
    ]
    
    # Health check endpoints for each API
    HEALTH_CHECK_PATHS = {
        "up.storacha.network": "health",
        "api.web3.storage": "status",
        "api.storacha.network": "health",
        "up.web3.storage": "health"
    }
    
    # Default rate limit parameters
    DEFAULT_RATE_LIMIT = {
        "requests_per_minute": 30,
        "requests_per_hour": 500,
        "max_burst": 10
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        endpoints: Optional[List[str]] = None,
        max_retries: int = 3,
        timeout: int = 30,
        validate_endpoints: bool = True,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_reset_time: int = 300,  # 5 minutes
        rate_limits: Optional[Dict[str, int]] = None
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
            circuit_breaker_threshold: Number of failures before circuit opens
            circuit_breaker_reset_time: Time in seconds before retrying a failed endpoint
            rate_limits: Custom rate limits to use
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_time = circuit_breaker_reset_time
        self.rate_limits = rate_limits or self.DEFAULT_RATE_LIMIT.copy()

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
                "success_count": 0               # Total successful requests
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
            "User-Agent": "StorachaConnectionManager/1.1"
        })
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

                # Determine the appropriate health check path
                hostname = url_parts.netloc.split(':')[0]
                base_hostname = '.'.join(hostname.split('.')[-2:])  # Get domain.tld
                health_path = self.HEALTH_CHECK_PATHS.get(hostname, 
                                                        self.HEALTH_CHECK_PATHS.get(base_hostname, "health"))
                
                # Try a simple GET request to validate endpoint
                start_time = time.time()
                response = self.session.get(f"{endpoint}/{health_path}", timeout=self.timeout)
                end_time = time.time()
                latency = int((end_time - start_time) * 1000)  # Convert to ms

                if response.status_code == 200:
                    logger.info(f"Validated Storacha endpoint: {endpoint} (latency: {latency}ms)")
                    self.working_endpoint = endpoint
                    self.last_working_time = time.time()
                    self._record_endpoint_success(endpoint, latency)
                    # Once we find a working endpoint, we can stop checking others
                    break
                else:
                    logger.warning(
                        f"Endpoint {endpoint} returned status code {response.status_code}"
                    )
                    self._record_endpoint_failure(endpoint)

            except (requests.RequestException, socket.gaierror) as e:
                logger.warning(f"Error validating endpoint {endpoint}: {e}")
                self._record_endpoint_failure(endpoint)

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
    
    def _record_endpoint_success(self, endpoint: str, latency_ms: int) -> None:
        """
        Record a successful request to an endpoint.
        
        Args:
            endpoint: The endpoint that was successful
            latency_ms: Request latency in milliseconds
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
        
        if response.status_code == 429:
            logger.warning("Rate limit exceeded according to response")
            
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
            StorachaApiError: If the API returns an error response
        """
        # Ensure we have a timeout
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        # Initialize for retry loop
        retry_count = 0
        last_exception = None
        current_endpoint = endpoint
        
        # Check rate limiting before making the request
        if self._check_rate_limiting():
            wait_time = max(0, self.rate_limited_until - time.time())
            raise StorachaApiError(
                f"Rate limit exceeded. Retry after {wait_time:.1f} seconds",
                status_code=429
            )

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
                # Construct URL
                url = f"{current_endpoint}/{path.lstrip('/')}"
                
                # Update metrics
                self.total_requests += 1
                self.last_request_time = time.time()

                # Send request
                start_time = time.time()
                method_func = getattr(self.session, method.lower())
                response = method_func(url, **kwargs)
                end_time = time.time()
                latency = int((end_time - start_time) * 1000)  # Convert to ms
                
                # Check for rate limiting
                rate_limited = self._update_rate_limiting(response)
                if rate_limited:
                    logger.warning(f"Rate limited by {current_endpoint}")
                    # This is a special case - we need to wait or try another endpoint
                    if retry_count < self.max_retries:
                        # Try another endpoint
                        alternatives = [ep for ep in self.endpoints if ep != current_endpoint]
                        if alternatives:
                            current_endpoint = random.choice(alternatives)
                            logger.info(f"Rate limited, switching to {current_endpoint}")
                            retry_count += 1
                            continue
                        else:
                            # No alternatives, we have to wait
                            backoff_time = max(1, min(60, 5 * (2**retry_count)))
                            logger.info(f"No alternative endpoints, waiting {backoff_time}s")
                            time.sleep(backoff_time)
                            retry_count += 1
                            continue
                    
                    # We've exhausted retries, have to fail with rate limit error
                    raise StorachaApiError(
                        "Rate limit exceeded on all endpoints",
                        status_code=429,
                        response={"error": "rate_limit_exceeded"}
                    )

                # Handle non-successful response codes
                if response.status_code >= 400:
                    # Try to parse response as JSON
                    try:
                        error_data = response.json()
                    except:
                        error_data = {"error": "Unknown error", "status": response.status_code}
                    
                    error_message = error_data.get("error", "Unknown error")
                    
                    # Decide if this error should trigger a retry
                    if response.status_code in (500, 502, 503, 504) and retry_count < self.max_retries:
                        logger.warning(f"Server error {response.status_code} from {current_endpoint}: {error_message}")
                        self._record_endpoint_failure(current_endpoint)
                        
                        # Try another endpoint or retry after backoff
                        alternatives = [ep for ep in self.endpoints if ep != current_endpoint and not self._is_circuit_open(ep)]
                        if alternatives:
                            current_endpoint = random.choice(alternatives)
                            logger.info(f"Server error, switching to {current_endpoint}")
                        else:
                            # Exponential backoff
                            backoff_time = 0.1 * (2**retry_count)
                            logger.info(f"Retrying in {backoff_time:.2f} seconds...")
                            time.sleep(backoff_time)
                        
                        retry_count += 1
                        continue
                    
                    # Non-retryable error
                    self._record_endpoint_failure(current_endpoint)
                    self.failed_requests += 1
                    self.last_error = error_message
                    
                    raise StorachaApiError(
                        f"API error: {error_message}",
                        status_code=response.status_code,
                        response=error_data
                    )

                # Update endpoint health on success
                self._record_endpoint_success(current_endpoint, latency)
                self.successful_requests += 1

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
                    backoff_time = 0.1 * (2**retry_count)  # 0.1, 0.2, 0.4, 0.8, ...
                    logger.info(f"Retrying in {backoff_time:.2f} seconds...")
                    time.sleep(backoff_time)

                retry_count += 1

        # If we've exhausted all retries, raise the last exception
        logger.error(f"All retry attempts failed for {path}")
        if isinstance(last_exception, StorachaApiError):
            raise last_exception
        raise last_exception or StorachaApiError("All retry attempts failed", status_code=500)

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
            StorachaApiError: If all retries fail or the API returns an error
        """
        endpoint = self._get_endpoint()
        response, used_endpoint = self._retry_request(method, endpoint, path, **kwargs)

        # If we used a different endpoint than originally selected, update our preference
        if used_endpoint != endpoint:
            self.working_endpoint = used_endpoint
            self.last_working_time = time.time()

        return response
    
    def get(self, path: str, **kwargs) -> requests.Response:
        """Convenience method for GET requests."""
        return self.send_request("get", path, **kwargs)
    
    def post(self, path: str, **kwargs) -> requests.Response:
        """Convenience method for POST requests."""
        return self.send_request("post", path, **kwargs)
    
    def put(self, path: str, **kwargs) -> requests.Response:
        """Convenience method for PUT requests."""
        return self.send_request("put", path, **kwargs)
    
    def delete(self, path: str, **kwargs) -> requests.Response:
        """Convenience method for DELETE requests."""
        return self.send_request("delete", path, **kwargs)
    
    def upload_file(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Upload a file to Storacha.
        
        Args:
            file_path: Path to the file to upload
            metadata: Optional metadata for the file
            
        Returns:
            Upload response data
        """
        import os
        
        if not os.path.exists(file_path):
            raise StorachaApiError(f"File not found: {file_path}", status_code=404)
            
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        logger.info(f"Uploading file {file_name} ({file_size} bytes) to Storacha")
        
        with open(file_path, 'rb') as file:
            files = {'file': (file_name, file)}
            
            if metadata:
                # Convert metadata to JSON string
                metadata_json = json.dumps(metadata)
                data = {'metadata': metadata_json}
            else:
                data = None
                
            # Make the request with special handling for files
            response = self.send_request("post", "upload", files=files, data=data)
            
            try:
                result = response.json()
                logger.info(f"Upload successful: {result.get('cid', 'unknown CID')}")
                return result
            except ValueError:
                raise StorachaApiError("Failed to parse upload response", status_code=500)
    
    def pin_by_cid(self, cid: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Pin content by CID.
        
        Args:
            cid: The CID to pin
            name: Optional name for the pin
            
        Returns:
            Pin response data
        """
        data = {"cid": cid}
        if name:
            data["name"] = name
            
        logger.info(f"Pinning CID {cid}")
        response = self.send_request("post", "pins", json=data)
        
        try:
            result = response.json()
            logger.info(f"Pin request successful: {result.get('requestId', 'unknown request ID')}")
            return result
        except ValueError:
            raise StorachaApiError("Failed to parse pin response", status_code=500)
    
    def check_pin_status(self, request_id: str) -> Dict[str, Any]:
        """
        Check the status of a pin request.
        
        Args:
            request_id: The pin request ID
            
        Returns:
            Pin status data
        """
        logger.info(f"Checking pin status for request {request_id}")
        response = self.send_request("get", f"pins/{request_id}")
        
        try:
            result = response.json()
            logger.info(f"Pin status: {result.get('status', 'unknown')}")
            return result
        except ValueError:
            raise StorachaApiError("Failed to parse pin status response", status_code=500)

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
                }
                for endpoint, status in self.endpoint_health.items()
            ],
            "connection_pooling_enabled": True,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "authenticated": bool(self.api_key),
            "circuit_breaker": {
                "threshold": self.circuit_breaker_threshold,
                "reset_time": self.circuit_breaker_reset_time
            }
        }