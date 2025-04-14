"""
S3 API Connection Manager

This module provides improved connection handling for S3-compatible storage services,
implementing robust error handling, retry logic, and automatic endpoint failover.
"""

import time
import logging
import boto3
import botocore.exceptions
import requests
import socket
import random
import json
import os
from typing import Dict, Any, List, Optional, Tuple, Union, BinaryIO
from urllib.parse import urlparse
from datetime import datetime, timedelta
from botocore.client import Config

# Configure logging
logger = logging.getLogger(__name__)


class S3ApiError(Exception):
    """Exception raised for S3 API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 operation: Optional[str] = None, error_code: Optional[str] = None,
                 request_id: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.operation = operation
        self.error_code = error_code
        self.request_id = request_id
        super().__init__(self.message)


class S3ConnectionManager:
    """
    Connection manager for S3-compatible APIs with enhanced reliability features.

    Provides robust connection handling with:
    - Multiple endpoint support with automatic failover
    - Exponential backoff for retries
    - Health checking and endpoint validation
    - Detailed connection status tracking
    - Rate limiting detection and handling
    - Circuit breaker pattern for failing endpoints
    
    Compatible with:
    - Amazon S3
    - MinIO
    - Ceph/RadosGW
    - Wasabi
    - Backblaze B2
    - Other S3-compatible services
    """
    # Default endpoints to try in order of preference
    DEFAULT_ENDPOINTS = [
        "https://s3.amazonaws.com",        # AWS
        "https://s3.us-east-1.amazonaws.com",  # AWS us-east-1
        "https://s3.us-west-2.amazonaws.com"   # AWS us-west-2
    ]
    
    # Default rate limit parameters
    DEFAULT_RATE_LIMIT = {
        "requests_per_minute": 300,  # S3 has higher limits
        "requests_per_hour": 5000,
        "max_burst": 100
    }

    def __init__(
        self,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: str = "us-east-1",
        endpoint_url: Optional[str] = None,
        endpoints: Optional[List[Dict[str, Any]]] = None,
        max_retries: int = 3,
        timeout: int = 30,
        validate_endpoints: bool = True,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_reset_time: int = 300,  # 5 minutes
        rate_limits: Optional[Dict[str, int]] = None,
        default_bucket: Optional[str] = None,
        signature_version: str = 's3v4'
    ):
        """
        Initialize the S3 connection manager.

        Args:
            access_key: AWS access key or equivalent
            secret_key: AWS secret key or equivalent
            region: AWS region or equivalent
            endpoint_url: Primary endpoint URL
            endpoints: List of endpoint configurations to try
                Example: [
                    {
                        "url": "https://s3.amazonaws.com",
                        "region": "us-east-1",
                        "name": "AWS S3"
                    }
                ]
            max_retries: Maximum number of retry attempts per endpoint
            timeout: Request timeout in seconds
            validate_endpoints: Whether to validate endpoints on initialization
            circuit_breaker_threshold: Number of failures before circuit opens
            circuit_breaker_reset_time: Time in seconds before retrying a failed endpoint
            rate_limits: Custom rate limits to use
            default_bucket: Default bucket to use if not specified in operations
            signature_version: S3 signature version to use
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.default_region = region
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_time = circuit_breaker_reset_time
        self.rate_limits = rate_limits or self.DEFAULT_RATE_LIMIT.copy()
        self.default_bucket = default_bucket
        self.signature_version = signature_version

        # Setup endpoints list
        self.endpoint_configs = []

        # Add primary endpoint if specified
        if endpoint_url:
            self.endpoint_configs.append({
                "url": endpoint_url,
                "region": region,
                "name": "Primary Endpoint"
            })

        # Add provided endpoint configs
        if endpoints:
            for endpoint in endpoints:
                # Make sure the endpoint has the required fields
                if "url" not in endpoint:
                    logger.warning(f"Skipping endpoint without URL: {endpoint}")
                    continue
                
                # Add region if not specified
                if "region" not in endpoint:
                    endpoint["region"] = region
                
                # Add name if not specified
                if "name" not in endpoint:
                    endpoint["name"] = f"Custom Endpoint ({endpoint['url']})"
                
                self.endpoint_configs.append(endpoint)

        # Add default endpoints if we need more
        if not self.endpoint_configs:
            for url in self.DEFAULT_ENDPOINTS:
                self.endpoint_configs.append({
                    "url": url,
                    "region": region,
                    "name": f"Default ({url})"
                })

        # For easy lookup, create a list of just the URLs
        self.endpoints = [config["url"] for config in self.endpoint_configs]

        # Initialize connection state
        self.working_endpoint = None
        self.working_client = None
        self.last_working_time = 0
        self.endpoint_health = {
            endpoint["url"]: {
                "healthy": None,                 # Current health status
                "last_checked": 0,               # Timestamp of last health check
                "failures": 0,                   # Consecutive failures
                "total_failures": 0,             # Total lifetime failures
                "circuit_open": False,           # Circuit breaker status
                "circuit_open_until": 0,         # When to try the endpoint again
                "success_rate": 100.0,           # Success percentage
                "avg_response_time": 0,          # Average response time in ms
                "last_latency": 0,               # Last response time in ms
                "requests_count": 0,             # Total requests made
                "success_count": 0,              # Total successful requests
                "region": endpoint["region"],    # Region for this endpoint
                "name": endpoint["name"]         # Friendly name
            }
            for endpoint in self.endpoint_configs
        }
        
        # Cache for boto3 clients (one per endpoint)
        self.clients = {}
        
        # Rate limiting tracking
        self.request_timestamps = []  # List of recent request timestamps
        self.rate_limited_until = 0   # Timestamp when rate limiting expires
        
        # Request metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.last_request_time = 0
        self.last_error = None

        # Validate endpoints if requested
        if validate_endpoints:
            self._validate_endpoints()

    def _get_client_for_endpoint(self, endpoint_url: str) -> boto3.client:
        """
        Get or create a boto3 S3 client for the specified endpoint.
        
        Args:
            endpoint_url: The endpoint URL
            
        Returns:
            boto3 S3 client
        """
        # Check if we already have a client for this endpoint
        if endpoint_url in self.clients:
            return self.clients[endpoint_url]
        
        # Find the endpoint config for this URL
        endpoint_config = next(
            (config for config in self.endpoint_configs if config["url"] == endpoint_url),
            {"url": endpoint_url, "region": self.default_region}
        )
        
        # Create a new client
        client = boto3.client(
            's3',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=endpoint_config["region"],
            endpoint_url=endpoint_url,
            config=Config(
                signature_version=self.signature_version,
                connect_timeout=self.timeout,
                read_timeout=self.timeout,
                retries={'max_attempts': 0}  # We handle retries ourselves
            )
        )
        
        # Cache the client
        self.clients[endpoint_url] = client
        
        return client

    def _validate_endpoints(self) -> None:
        """
        Validate all endpoints and establish a preferred working endpoint.
        """
        logger.info(f"Validating {len(self.endpoints)} S3 endpoints")

        for endpoint in self.endpoints:
            # Skip endpoints with open circuit breakers
            if self._is_circuit_open(endpoint):
                logger.info(f"Skipping endpoint {endpoint} due to open circuit breaker")
                continue
            
            # Find the endpoint config
            endpoint_config = next(
                (config for config in self.endpoint_configs if config["url"] == endpoint),
                {"url": endpoint, "region": self.default_region, "name": "Unknown"}
            )
                
            try:
                # Verify DNS resolution
                url_parts = urlparse(endpoint)
                if not self._check_dns_resolution(url_parts.netloc):
                    logger.warning(f"DNS resolution failed for {endpoint}")
                    self._record_endpoint_failure(endpoint)
                    continue

                # Get client for this endpoint
                client = self._get_client_for_endpoint(endpoint)
                
                # Start timing
                start_time = time.time()
                
                # Try to list buckets as a health check (or use default bucket if specified)
                if self.default_bucket:
                    # Check if default bucket exists
                    try:
                        client.head_bucket(Bucket=self.default_bucket)
                        operation_success = True
                    except botocore.exceptions.ClientError as e:
                        # 404 means the bucket doesn't exist
                        error_code = e.response.get('Error', {}).get('Code', '')
                        if error_code == '404':
                            logger.warning(f"Default bucket '{self.default_bucket}' not found at {endpoint}")
                            operation_success = False
                        else:
                            # Re-raise for other errors
                            raise
                else:
                    # Try to list buckets
                    client.list_buckets()
                    operation_success = True
                
                # Measure latency
                end_time = time.time()
                latency = int((end_time - start_time) * 1000)  # Convert to ms

                if operation_success:
                    logger.info(f"Validated S3 endpoint: {endpoint} (latency: {latency}ms)")
                    self.working_endpoint = endpoint
                    self.working_client = client
                    self.last_working_time = time.time()
                    self._record_endpoint_success(endpoint, latency)
                    
                    # Once we find a working endpoint, we can stop checking others
                    break
                else:
                    logger.warning(f"Endpoint {endpoint} failed basic operations test")
                    self._record_endpoint_failure(endpoint)

            except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError,
                    requests.RequestException, socket.gaierror) as e:
                logger.warning(f"Error validating endpoint {endpoint}: {e}")
                self._record_endpoint_failure(endpoint)

        # If no working endpoint found
        if not self.working_endpoint:
            logger.warning("No working S3 endpoints found during validation")

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
    
    def _detect_rate_limiting(self, exception: Exception) -> bool:
        """
        Detect rate limiting from S3 error responses.
        
        Args:
            exception: The exception to check
            
        Returns:
            True if rate limited, False otherwise
        """
        # Record the request timestamp
        self.request_timestamps.append(datetime.now())
        
        # Check for rate limit indicators
        if isinstance(exception, botocore.exceptions.ClientError):
            error_code = exception.response.get('Error', {}).get('Code', '')
            
            # Common S3 throttling error codes
            if error_code in ('SlowDown', 'RequestLimitExceeded', 'ThrottlingException',
                             'RequestThrottled', 'TooManyRequestsException',
                             'ProvisionedThroughputExceededException'):
                logger.warning(f"Rate limiting detected: {error_code}")
                
                # Set backoff time
                self.rate_limited_until = time.time() + 60  # Default 60 second backoff
                return True
                
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

    def _call_s3_operation(
        self, 
        endpoint: str, 
        operation: str, 
        **kwargs
    ) -> Any:
        """
        Call an S3 operation on a specific endpoint.
        
        Args:
            endpoint: The endpoint to use
            operation: S3 operation (method) name
            **kwargs: Parameters for the operation
            
        Returns:
            Result of the operation
            
        Raises:
            S3ApiError: If there's an error calling the operation
        """
        # Get client for this endpoint
        client = self._get_client_for_endpoint(endpoint)
        
        try:
            # Get the operation method
            s3_operation = getattr(client, operation)
            
            # Time the operation
            start_time = time.time()
            
            # Call the operation
            response = s3_operation(**kwargs)
            
            # Calculate latency
            end_time = time.time()
            latency = int((end_time - start_time) * 1000)  # Convert to ms
            
            # Record success
            self._record_endpoint_success(endpoint, latency)
            
            return response
            
        except botocore.exceptions.ClientError as e:
            # Extract error details
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            status_code = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 500)
            request_id = e.response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
            
            # Record failure
            self._record_endpoint_failure(endpoint)
            
            # Check for rate limiting
            if self._detect_rate_limiting(e):
                # Convert to S3ApiError with rate limiting context
                raise S3ApiError(
                    message=f"Rate limited: {error_message}",
                    status_code=status_code,
                    operation=operation,
                    error_code="RATE_LIMITED",
                    request_id=request_id
                )
                
            # Convert to S3ApiError
            raise S3ApiError(
                message=error_message,
                status_code=status_code,
                operation=operation,
                error_code=error_code,
                request_id=request_id
            )
            
        except botocore.exceptions.BotoCoreError as e:
            # Record failure
            self._record_endpoint_failure(endpoint)
            
            # Convert to S3ApiError
            raise S3ApiError(
                message=str(e),
                operation=operation,
                error_code="BOTO_CORE_ERROR"
            )
            
        except Exception as e:
            # Record failure
            self._record_endpoint_failure(endpoint)
            
            # Convert to S3ApiError
            raise S3ApiError(
                message=f"Unexpected error: {str(e)}",
                operation=operation,
                error_code="UNEXPECTED_ERROR"
            )
        
    def call(self, operation: str, **kwargs) -> Any:
        """
        Call an S3 operation with automatic retries and endpoint failover.
        
        Args:
            operation: S3 operation (method) name
            **kwargs: Parameters for the operation
            
        Returns:
            Result of the operation
            
        Raises:
            S3ApiError: If all retries fail or the API returns an error
        """
        # Check rate limiting
        if self._check_rate_limiting():
            wait_time = max(0, self.rate_limited_until - time.time())
            raise S3ApiError(
                message=f"Rate limit exceeded. Retry after {wait_time:.1f} seconds",
                status_code=429,
                operation=operation,
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
                # Make the call
                response = self._call_s3_operation(current_endpoint, operation, **kwargs)
                
                # Update metrics on success
                self.successful_requests += 1
                
                # Update working endpoint
                self.working_endpoint = current_endpoint
                self.working_client = self._get_client_for_endpoint(current_endpoint)
                self.last_working_time = time.time()
                
                # Return the result
                return response
                
            except S3ApiError as e:
                last_error = e
                logger.warning(
                    f"S3 operation '{operation}' on {current_endpoint} failed (attempt {retry_count + 1}/{self.max_retries + 1}): {e.message}"
                )
                
                # Update metrics
                self.failed_requests += 1
                self.last_error = e.message
                
                # If this was the current working endpoint, clear it
                if self.working_endpoint == current_endpoint:
                    self.working_endpoint = None
                    self.working_client = None
                
                # Decide if we should retry
                # Some error codes should not be retried
                non_retryable = [
                    "AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch",
                    "InvalidToken", "ExpiredToken", "AccountProblem", "AuthFailure",
                    "NoSuchBucket", "NoSuchKey", "NoSuchUpload", "BucketAlreadyExists"
                ]
                
                # For rate limiting, we always try a different endpoint
                if e.error_code == "RATE_LIMITED":
                    # Try another endpoint before incrementing retry count
                    candidates = [ep for ep in self.endpoints if ep != current_endpoint and not self._is_circuit_open(ep)]
                    if candidates:
                        # Prefer endpoints with fewer failures
                        candidates.sort(key=lambda ep: self.endpoint_health[ep]["failures"])
                        current_endpoint = candidates[0]
                        logger.info(f"Rate limited, switching to alternative endpoint: {current_endpoint}")
                        continue
                
                # If error is not retryable, stop trying
                if e.error_code in non_retryable:
                    logger.warning(f"Non-retryable error: {e.error_code}")
                    break
                
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
        logger.error(f"All retry attempts failed for operation '{operation}'")
        if last_error:
            raise last_error
        else:
            raise S3ApiError(
                message=f"All retry attempts failed for operation '{operation}' with unknown error",
                operation=operation,
                error_code="RETRY_EXHAUSTED"
            )
    
    # Convenience methods for common S3 operations
    
    def list_buckets(self) -> List[Dict[str, Any]]:
        """
        List all buckets.
        
        Returns:
            List of bucket information dictionaries
        """
        response = self.call("list_buckets")
        return response.get("Buckets", [])
    
    def list_objects(self, bucket: Optional[str] = None, prefix: str = "", **kwargs) -> Dict[str, Any]:
        """
        List objects in a bucket.
        
        Args:
            bucket: Bucket name (uses default_bucket if not specified)
            prefix: Prefix to filter objects
            **kwargs: Additional parameters for list_objects_v2
            
        Returns:
            Object listing information
        """
        bucket_name = bucket or self.default_bucket
        if not bucket_name:
            raise S3ApiError(
                message="No bucket specified and no default bucket configured",
                operation="list_objects",
                error_code="NO_BUCKET_SPECIFIED"
            )
            
        return self.call("list_objects_v2", Bucket=bucket_name, Prefix=prefix, **kwargs)
    
    def get_object(self, key: str, bucket: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Get an object from a bucket.
        
        Args:
            key: Object key
            bucket: Bucket name (uses default_bucket if not specified)
            **kwargs: Additional parameters for get_object
            
        Returns:
            Object data and metadata
        """
        bucket_name = bucket or self.default_bucket
        if not bucket_name:
            raise S3ApiError(
                message="No bucket specified and no default bucket configured",
                operation="get_object",
                error_code="NO_BUCKET_SPECIFIED"
            )
            
        return self.call("get_object", Bucket=bucket_name, Key=key, **kwargs)
        
    def download_file(self, key: str, file_path: str, bucket: Optional[str] = None, **kwargs) -> None:
        """
        Download an object to a file.
        
        Args:
            key: Object key
            file_path: Local file path to save the object
            bucket: Bucket name (uses default_bucket if not specified)
            **kwargs: Additional parameters for download_file
        """
        bucket_name = bucket or self.default_bucket
        if not bucket_name:
            raise S3ApiError(
                message="No bucket specified and no default bucket configured",
                operation="download_file",
                error_code="NO_BUCKET_SPECIFIED"
            )
            
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
        return self.call("download_file", Bucket=bucket_name, Key=key, Filename=file_path, **kwargs)
    
    def upload_file(self, file_path: str, key: str, bucket: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Upload a file to a bucket.
        
        Args:
            file_path: Local file path to upload
            key: Object key
            bucket: Bucket name (uses default_bucket if not specified)
            **kwargs: Additional parameters for upload_file
            
        Returns:
            Upload response
        """
        bucket_name = bucket or self.default_bucket
        if not bucket_name:
            raise S3ApiError(
                message="No bucket specified and no default bucket configured",
                operation="upload_file",
                error_code="NO_BUCKET_SPECIFIED"
            )
            
        return self.call("upload_file", Filename=file_path, Bucket=bucket_name, Key=key, **kwargs)
    
    def delete_object(self, key: str, bucket: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Delete an object from a bucket.
        
        Args:
            key: Object key
            bucket: Bucket name (uses default_bucket if not specified)
            **kwargs: Additional parameters for delete_object
            
        Returns:
            Delete response
        """
        bucket_name = bucket or self.default_bucket
        if not bucket_name:
            raise S3ApiError(
                message="No bucket specified and no default bucket configured",
                operation="delete_object",
                error_code="NO_BUCKET_SPECIFIED"
            )
            
        return self.call("delete_object", Bucket=bucket_name, Key=key, **kwargs)
    
    def get_object_url(self, key: str, bucket: Optional[str] = None, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for an object.
        
        Args:
            key: Object key
            bucket: Bucket name (uses default_bucket if not specified)
            expires_in: URL expiration time in seconds
            
        Returns:
            Presigned URL
        """
        bucket_name = bucket or self.default_bucket
        if not bucket_name:
            raise S3ApiError(
                message="No bucket specified and no default bucket configured",
                operation="generate_presigned_url",
                error_code="NO_BUCKET_SPECIFIED"
            )
            
        # For generating URLs, we need to use the client directly
        client = self._get_client_for_endpoint(self._get_endpoint())
        
        try:
            url = client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket_name, "Key": key},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            raise S3ApiError(
                message=f"Failed to generate presigned URL: {str(e)}",
                operation="generate_presigned_url",
                error_code="URL_GENERATION_FAILED"
            )
    
    def head_object(self, key: str, bucket: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Get object metadata without downloading the object.
        
        Args:
            key: Object key
            bucket: Bucket name (uses default_bucket if not specified)
            **kwargs: Additional parameters for head_object
            
        Returns:
            Object metadata
        """
        bucket_name = bucket or self.default_bucket
        if not bucket_name:
            raise S3ApiError(
                message="No bucket specified and no default bucket configured",
                operation="head_object",
                error_code="NO_BUCKET_SPECIFIED"
            )
            
        return self.call("head_object", Bucket=bucket_name, Key=key, **kwargs)
    
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
            "default_bucket": self.default_bucket,
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
                    "name": self.endpoint_health[endpoint]["name"],
                    "region": self.endpoint_health[endpoint]["region"],
                    "healthy": self.endpoint_health[endpoint]["healthy"],
                    "last_checked": self.endpoint_health[endpoint]["last_checked"],
                    "failures": self.endpoint_health[endpoint]["failures"],
                    "total_failures": self.endpoint_health[endpoint]["total_failures"],
                    "success_rate": self.endpoint_health[endpoint]["success_rate"],
                    "avg_response_time": self.endpoint_health[endpoint]["avg_response_time"],
                    "last_latency": self.endpoint_health[endpoint]["last_latency"],
                    "circuit_open": self.endpoint_health[endpoint]["circuit_open"],
                    "circuit_open_until": self.endpoint_health[endpoint]["circuit_open_until"],
                }
                for endpoint in self.endpoints
            ],
            "authentication": {
                "has_access_key": bool(self.access_key),
                "has_secret_key": bool(self.secret_key),
                "signature_version": self.signature_version
            },
            "configuration": {
                "max_retries": self.max_retries,
                "timeout": self.timeout,
                "circuit_breaker_threshold": self.circuit_breaker_threshold,
                "circuit_breaker_reset_time": self.circuit_breaker_reset_time
            }
        }