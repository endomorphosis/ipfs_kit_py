# ipfs_kit_py/wal_telemetry_client_anyio.py

"""
Client for the WAL telemetry API with AnyIO support.

This module provides a client for accessing the WAL telemetry API, providing
programmatic access to telemetry metrics, reports, and visualizations with
support for different async backends through AnyIO.
"""

import os
import time
import json
import logging
import warnings
import webbrowser
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from enum import Enum

import anyio
import httpx
import sniffio

# Configure logging
logger = logging.getLogger(__name__)

# Metric type and aggregation enums
class TelemetryMetricType(str, Enum):
    """Types of metrics collected by the telemetry system."""
    OPERATION_COUNT = "operation_count"
    OPERATION_LATENCY = "operation_latency"
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"
    BACKEND_HEALTH = "backend_health"
    THROUGHPUT = "throughput"
    QUEUE_SIZE = "queue_size"
    RETRY_COUNT = "retry_count"

class TelemetryAggregation(str, Enum):
    """Types of aggregation for telemetry metrics."""
    SUM = "sum"
    AVERAGE = "average"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    PERCENTILE_95 = "percentile_95"
    PERCENTILE_99 = "percentile_99"
    COUNT = "count"
    RATE = "rate"

class WALTelemetryClientAnyIO:
    """
    Client for accessing the WAL telemetry API with AnyIO support.
    
    This class provides methods for retrieving telemetry metrics, generating reports,
    and accessing visualizations from the WAL telemetry API with support for
    different async backends through AnyIO.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None, 
                timeout: int = 30, verify_ssl: bool = True):
        """
        Initialize the WAL telemetry client.
        
        Args:
            base_url: Base URL for the API server
            api_key: Optional API key for authentication
            timeout: Timeout in seconds for API requests
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        # Initialize HTTP client for sync operations
        self.session = None
        
        # Set default headers
        self.headers = {
            "User-Agent": "WALTelemetryClientAnyIO/1.0",
            "Accept": "application/json"
        }
        
        # Add API key to headers if provided
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    @staticmethod
    def get_backend() -> Optional[str]:
        """
        Get the current async backend being used.
        
        Returns:
            String identifying the async library or None if not in async context
        """
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
    
    def _warn_if_async_context(self, method_name: str) -> None:
        """
        Warn if a synchronous method is called from an async context.
        
        Args:
            method_name: Name of the method being called
        """
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
                stacklevel=3
            )
    
    def _ensure_session(self) -> None:
        """Ensure the synchronous HTTP session is initialized."""
        if self.session is None:
            import requests
            self.session = requests.Session()
            self.session.headers.update(self.headers)
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, 
                data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None,
                files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a synchronous request to the API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Form data
            json_data: JSON data
            files: Files to upload
            
        Returns:
            API response as dictionary
            
        Raises:
            ValueError: If the API returns an error
            requests.RequestException: If the request fails
        """
        # Warn if called from async context
        self._warn_if_async_context("_request")
        
        # Ensure session is initialized
        self._ensure_session()
        
        # Build URL
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Make request
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_data,
                files=files,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            # Check for successful response
            response.raise_for_status()
            
            # Parse JSON response if available
            if response.headers.get("Content-Type", "").startswith("application/json"):
                result = response.json()
                
                # Check for API error
                if not result.get("success", False):
                    error_msg = result.get("error", "Unknown API error")
                    raise ValueError(f"API error: {error_msg}")
                
                return result
            else:
                # Return raw response for non-JSON content
                return {
                    "success": True,
                    "content_type": response.headers.get("Content-Type"),
                    "content": response.content,
                    "status_code": response.status_code
                }
            
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            raise
    
    async def _request_async(self, method: str, endpoint: str, 
                           params: Optional[Dict[str, Any]] = None, 
                           data: Optional[Dict[str, Any]] = None, 
                           json_data: Optional[Dict[str, Any]] = None,
                           files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an asynchronous request to the API using AnyIO.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Form data
            json_data: JSON data
            files: Files to upload
            
        Returns:
            API response as dictionary
            
        Raises:
            ValueError: If the API returns an error
            httpx.HTTPError: If the request fails
        """
        # Build URL
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Make async request with httpx
            async with httpx.AsyncClient(
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    files=files
                )
                
                # Check for successful response
                response.raise_for_status()
                
                # Parse JSON response if available
                if response.headers.get("Content-Type", "").startswith("application/json"):
                    result = response.json()
                    
                    # Check for API error
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown API error")
                        raise ValueError(f"API error: {error_msg}")
                    
                    return result
                else:
                    # Return raw response for non-JSON content
                    return {
                        "success": True,
                        "content_type": response.headers.get("Content-Type"),
                        "content": response.content,
                        "status_code": response.status_code
                    }
                
        except Exception as e:
            logger.error(f"Async API request failed: {str(e)}")
            raise
    
    def get_metrics(self, metric_type: Optional[Union[str, TelemetryMetricType]] = None,
                   operation_type: Optional[str] = None, backend: Optional[str] = None,
                   status: Optional[str] = None, time_range: Optional[Tuple[float, float]] = None,
                   aggregation: Optional[Union[str, TelemetryAggregation]] = None) -> Dict[str, Any]:
        """
        Get telemetry metrics with optional filtering.
        
        Args:
            metric_type: Type of metrics to retrieve
            operation_type: Filter by operation type
            backend: Filter by backend type
            status: Filter by operation status
            time_range: Tuple of (start_time, end_time) to filter by
            aggregation: Type of aggregation to apply
            
        Returns:
            Dictionary with telemetry metrics
        """
        # Warn if called from async context
        self._warn_if_async_context("get_metrics")
        
        # Convert enums to strings
        if hasattr(metric_type, 'value'):
            metric_type = metric_type.value
            
        if hasattr(aggregation, 'value'):
            aggregation = aggregation.value
        
        # Prepare params
        params = {}
        if metric_type:
            params["metric_type"] = metric_type
        if operation_type:
            params["operation_type"] = operation_type
        if backend:
            params["backend"] = backend
        if status:
            params["status"] = status
        if time_range:
            params["start_time"] = time_range[0]
            params["end_time"] = time_range[1]
        if aggregation:
            params["aggregation"] = aggregation
        
        # Make request
        result = self._request(
            method="GET",
            endpoint="/api/v0/wal/telemetry/metrics",
            params=params
        )
        
        return result
    
    async def get_metrics_async(self, metric_type: Optional[Union[str, TelemetryMetricType]] = None,
                             operation_type: Optional[str] = None, backend: Optional[str] = None,
                             status: Optional[str] = None, time_range: Optional[Tuple[float, float]] = None,
                             aggregation: Optional[Union[str, TelemetryAggregation]] = None) -> Dict[str, Any]:
        """
        Get telemetry metrics with optional filtering asynchronously.
        
        Args:
            metric_type: Type of metrics to retrieve
            operation_type: Filter by operation type
            backend: Filter by backend type
            status: Filter by operation status
            time_range: Tuple of (start_time, end_time) to filter by
            aggregation: Type of aggregation to apply
            
        Returns:
            Dictionary with telemetry metrics
        """
        # Convert enums to strings
        if hasattr(metric_type, 'value'):
            metric_type = metric_type.value
            
        if hasattr(aggregation, 'value'):
            aggregation = aggregation.value
        
        # Prepare params
        params = {}
        if metric_type:
            params["metric_type"] = metric_type
        if operation_type:
            params["operation_type"] = operation_type
        if backend:
            params["backend"] = backend
        if status:
            params["status"] = status
        if time_range:
            params["start_time"] = time_range[0]
            params["end_time"] = time_range[1]
        if aggregation:
            params["aggregation"] = aggregation
        
        # Make async request
        result = await self._request_async(
            method="GET",
            endpoint="/api/v0/wal/telemetry/metrics",
            params=params
        )
        
        return result
    
    def get_realtime_metrics(self) -> Dict[str, Any]:
        """
        Get real-time telemetry metrics.
        
        Returns:
            Dictionary with real-time telemetry metrics
        """
        # Warn if called from async context
        self._warn_if_async_context("get_realtime_metrics")
        
        return self._request(
            method="GET",
            endpoint="/api/v0/wal/telemetry/realtime"
        )
    
    async def get_realtime_metrics_async(self) -> Dict[str, Any]:
        """
        Get real-time telemetry metrics asynchronously.
        
        Returns:
            Dictionary with real-time telemetry metrics
        """
        return await self._request_async(
            method="GET",
            endpoint="/api/v0/wal/telemetry/realtime"
        )
    
    def generate_report(self, start_time: Optional[float] = None, end_time: Optional[float] = None,
                      open_browser: bool = False) -> Dict[str, Any]:
        """
        Generate a comprehensive telemetry report.
        
        Args:
            start_time: Start time for time range filter (Unix timestamp)
            end_time: End time for time range filter (Unix timestamp)
            open_browser: Whether to open the report in a browser
            
        Returns:
            Dictionary with report information
        """
        # Warn if called from async context
        self._warn_if_async_context("generate_report")
        
        # Set default time range if not provided (last 24 hours)
        if end_time is None:
            end_time = time.time()
            
        if start_time is None:
            start_time = end_time - (24 * 60 * 60)  # 24 hours ago
        
        # Prepare data
        data = {
            "start_time": start_time,
            "end_time": end_time
        }
        
        # Make request
        result = self._request(
            method="POST",
            endpoint="/api/v0/wal/telemetry/report",
            data=data
        )
        
        # Open report in browser if requested
        if open_browser and "report_url" in result:
            try:
                webbrowser.open(result["report_url"])
            except Exception as e:
                logger.warning(f"Failed to open browser: {str(e)}")
        
        return result
    
    async def generate_report_async(self, start_time: Optional[float] = None, 
                                 end_time: Optional[float] = None,
                                 open_browser: bool = False) -> Dict[str, Any]:
        """
        Generate a comprehensive telemetry report asynchronously.
        
        Args:
            start_time: Start time for time range filter (Unix timestamp)
            end_time: End time for time range filter (Unix timestamp)
            open_browser: Whether to open the report in a browser
            
        Returns:
            Dictionary with report information
        """
        # Set default time range if not provided (last 24 hours)
        if end_time is None:
            end_time = time.time()
            
        if start_time is None:
            start_time = end_time - (24 * 60 * 60)  # 24 hours ago
        
        # Prepare data
        data = {
            "start_time": start_time,
            "end_time": end_time
        }
        
        # Make async request
        result = await self._request_async(
            method="POST",
            endpoint="/api/v0/wal/telemetry/report",
            data=data
        )
        
        # Open report in browser if requested (this is sync but acceptable for UI)
        if open_browser and "report_url" in result:
            # Use anyio.to_thread.run_sync to avoid blocking
            try:
                await anyio.to_thread.run_sync(
                    lambda: webbrowser.open(result["report_url"])
                )
            except Exception as e:
                logger.warning(f"Failed to open browser: {str(e)}")
        
        return result
    
    def get_report_file(self, report_id: str, file_name: str, 
                      save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a file from a telemetry report.
        
        Args:
            report_id: ID of the report
            file_name: Name of the file to retrieve
            save_path: Path to save the file (if None, file is not saved)
            
        Returns:
            Dictionary with file content or saved file information
        """
        # Warn if called from async context
        self._warn_if_async_context("get_report_file")
        
        # Make request
        result = self._request(
            method="GET",
            endpoint=f"/api/v0/wal/telemetry/reports/{report_id}/{file_name}"
        )
        
        # Save file if path provided
        if save_path and "content" in result:
            try:
                with open(save_path, "wb") as f:
                    f.write(result["content"])
                
                # Update result
                result["saved_path"] = save_path
                result["saved"] = True
            except Exception as e:
                logger.error(f"Failed to save file: {str(e)}")
                result["saved"] = False
                result["save_error"] = str(e)
        
        return result
    
    async def get_report_file_async(self, report_id: str, file_name: str, 
                                 save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a file from a telemetry report asynchronously.
        
        Args:
            report_id: ID of the report
            file_name: Name of the file to retrieve
            save_path: Path to save the file (if None, file is not saved)
            
        Returns:
            Dictionary with file content or saved file information
        """
        # Make async request
        result = await self._request_async(
            method="GET",
            endpoint=f"/api/v0/wal/telemetry/reports/{report_id}/{file_name}"
        )
        
        # Save file if path provided
        if save_path and "content" in result:
            try:
                async with await anyio.open_file(save_path, "wb") as f:
                    await f.write(result["content"])
                
                # Update result
                result["saved_path"] = save_path
                result["saved"] = True
            except Exception as e:
                logger.error(f"Failed to save file: {str(e)}")
                result["saved"] = False
                result["save_error"] = str(e)
        
        return result
    
    def get_visualization(self, metric_type: Union[str, TelemetryMetricType],
                        operation_type: Optional[str] = None, backend: Optional[str] = None,
                        status: Optional[str] = None, time_range: Optional[Tuple[float, float]] = None,
                        width: int = 12, height: int = 8, save_path: Optional[str] = None,
                        open_browser: bool = False) -> Dict[str, Any]:
        """
        Get a visualization of telemetry metrics.
        
        Args:
            metric_type: Type of metrics to visualize
            operation_type: Filter by operation type
            backend: Filter by backend type
            status: Filter by operation status
            time_range: Tuple of (start_time, end_time) to filter by
            width: Chart width in inches
            height: Chart height in inches
            save_path: Path to save the visualization (if None, visualization is not saved)
            open_browser: Whether to open the visualization in a browser
            
        Returns:
            Dictionary with visualization information
        """
        # Warn if called from async context
        self._warn_if_async_context("get_visualization")
        
        # Convert enum to string
        if hasattr(metric_type, 'value'):
            metric_type = metric_type.value
        
        # Prepare params
        params = {
            "width": width,
            "height": height
        }
        if operation_type:
            params["operation_type"] = operation_type
        if backend:
            params["backend"] = backend
        if status:
            params["status"] = status
        if time_range:
            params["start_time"] = time_range[0]
            params["end_time"] = time_range[1]
            
        # Build URL for browser opening
        browser_url = f"{self.base_url}/api/v0/wal/telemetry/visualization/{metric_type}"
        if params:
            browser_url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        # Open in browser if requested
        if open_browser:
            try:
                webbrowser.open(browser_url)
            except Exception as e:
                logger.warning(f"Failed to open browser: {str(e)}")
            
            return {
                "success": True,
                "operation": "visualize_metrics",
                "url": browser_url,
                "message": "Visualization opened in browser"
            }
        
        # Make request to get image
        result = self._request(
            method="GET",
            endpoint=f"/api/v0/wal/telemetry/visualization/{metric_type}",
            params=params
        )
        
        # Save visualization if path provided
        if save_path and "content" in result:
            try:
                with open(save_path, "wb") as f:
                    f.write(result["content"])
                
                # Update result
                result["saved_path"] = save_path
                result["saved"] = True
            except Exception as e:
                logger.error(f"Failed to save visualization: {str(e)}")
                result["saved"] = False
                result["save_error"] = str(e)
        
        return result
    
    async def get_visualization_async(self, metric_type: Union[str, TelemetryMetricType],
                                   operation_type: Optional[str] = None, backend: Optional[str] = None,
                                   status: Optional[str] = None, time_range: Optional[Tuple[float, float]] = None,
                                   width: int = 12, height: int = 8, save_path: Optional[str] = None,
                                   open_browser: bool = False) -> Dict[str, Any]:
        """
        Get a visualization of telemetry metrics asynchronously.
        
        Args:
            metric_type: Type of metrics to visualize
            operation_type: Filter by operation type
            backend: Filter by backend type
            status: Filter by operation status
            time_range: Tuple of (start_time, end_time) to filter by
            width: Chart width in inches
            height: Chart height in inches
            save_path: Path to save the visualization (if None, visualization is not saved)
            open_browser: Whether to open the visualization in a browser
            
        Returns:
            Dictionary with visualization information
        """
        # Convert enum to string
        if hasattr(metric_type, 'value'):
            metric_type = metric_type.value
        
        # Prepare params
        params = {
            "width": width,
            "height": height
        }
        if operation_type:
            params["operation_type"] = operation_type
        if backend:
            params["backend"] = backend
        if status:
            params["status"] = status
        if time_range:
            params["start_time"] = time_range[0]
            params["end_time"] = time_range[1]
            
        # Build URL for browser opening
        browser_url = f"{self.base_url}/api/v0/wal/telemetry/visualization/{metric_type}"
        if params:
            browser_url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        # Open in browser if requested
        if open_browser:
            # Use anyio.to_thread.run_sync to avoid blocking
            try:
                await anyio.to_thread.run_sync(
                    lambda: webbrowser.open(browser_url)
                )
            except Exception as e:
                logger.warning(f"Failed to open browser: {str(e)}")
            
            return {
                "success": True,
                "operation": "visualize_metrics",
                "url": browser_url,
                "message": "Visualization opened in browser"
            }
        
        # Make async request to get image
        result = await self._request_async(
            method="GET",
            endpoint=f"/api/v0/wal/telemetry/visualization/{metric_type}",
            params=params
        )
        
        # Save visualization if path provided
        if save_path and "content" in result:
            try:
                async with await anyio.open_file(save_path, "wb") as f:
                    await f.write(result["content"])
                
                # Update result
                result["saved_path"] = save_path
                result["saved"] = True
            except Exception as e:
                logger.error(f"Failed to save visualization: {str(e)}")
                result["saved"] = False
                result["save_error"] = str(e)
        
        return result
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the current telemetry configuration.
        
        Returns:
            Dictionary with telemetry configuration
        """
        # Warn if called from async context
        self._warn_if_async_context("get_config")
        
        return self._request(
            method="GET",
            endpoint="/api/v0/wal/telemetry/config"
        )
    
    async def get_config_async(self) -> Dict[str, Any]:
        """
        Get the current telemetry configuration asynchronously.
        
        Returns:
            Dictionary with telemetry configuration
        """
        return await self._request_async(
            method="GET",
            endpoint="/api/v0/wal/telemetry/config"
        )
    
    def update_config(self, enabled: Optional[bool] = None, metrics_path: Optional[str] = None,
                    retention_days: Optional[int] = None, sampling_interval: Optional[int] = None,
                    enable_detailed_timing: Optional[bool] = None,
                    operation_hooks: Optional[bool] = None) -> Dict[str, Any]:
        """
        Update telemetry configuration.
        
        Args:
            enabled: Whether telemetry is enabled
            metrics_path: Directory for telemetry metrics storage
            retention_days: Number of days to retain metrics
            sampling_interval: Interval in seconds between metric samples
            enable_detailed_timing: Whether to collect detailed timing data
            operation_hooks: Whether to install operation hooks
            
        Returns:
            Dictionary with updated configuration
        """
        # Warn if called from async context
        self._warn_if_async_context("update_config")
        
        # Prepare config data
        config = {}
        if enabled is not None:
            config["enabled"] = enabled
        if metrics_path is not None:
            config["metrics_path"] = metrics_path
        if retention_days is not None:
            config["retention_days"] = retention_days
        if sampling_interval is not None:
            config["sampling_interval"] = sampling_interval
        if enable_detailed_timing is not None:
            config["enable_detailed_timing"] = enable_detailed_timing
        if operation_hooks is not None:
            config["operation_hooks"] = operation_hooks
        
        # Make request
        return self._request(
            method="POST",
            endpoint="/api/v0/wal/telemetry/config",
            json_data=config
        )
    
    async def update_config_async(self, enabled: Optional[bool] = None, 
                               metrics_path: Optional[str] = None,
                               retention_days: Optional[int] = None, 
                               sampling_interval: Optional[int] = None,
                               enable_detailed_timing: Optional[bool] = None,
                               operation_hooks: Optional[bool] = None) -> Dict[str, Any]:
        """
        Update telemetry configuration asynchronously.
        
        Args:
            enabled: Whether telemetry is enabled
            metrics_path: Directory for telemetry metrics storage
            retention_days: Number of days to retain metrics
            sampling_interval: Interval in seconds between metric samples
            enable_detailed_timing: Whether to collect detailed timing data
            operation_hooks: Whether to install operation hooks
            
        Returns:
            Dictionary with updated configuration
        """
        # Prepare config data
        config = {}
        if enabled is not None:
            config["enabled"] = enabled
        if metrics_path is not None:
            config["metrics_path"] = metrics_path
        if retention_days is not None:
            config["retention_days"] = retention_days
        if sampling_interval is not None:
            config["sampling_interval"] = sampling_interval
        if enable_detailed_timing is not None:
            config["enable_detailed_timing"] = enable_detailed_timing
        if operation_hooks is not None:
            config["operation_hooks"] = operation_hooks
        
        # Make async request
        return await self._request_async(
            method="POST",
            endpoint="/api/v0/wal/telemetry/config",
            json_data=config
        )
    
    def get_metrics_over_time(self, metric_type: Union[str, TelemetryMetricType],
                            operation_type: Optional[str] = None, backend: Optional[str] = None,
                            status: Optional[str] = None, 
                            start_time: Optional[float] = None,
                            end_time: Optional[float] = None,
                            interval: str = "hour") -> Dict[str, Any]:
        """
        Get metrics over time with specified interval.
        
        This is a convenience method that retrieves metrics for multiple time periods
        and organizes them into a time series.
        
        Args:
            metric_type: Type of metrics to retrieve
            operation_type: Filter by operation type
            backend: Filter by backend type
            status: Filter by operation status
            start_time: Start time (defaults to 24 hours ago)
            end_time: End time (defaults to now)
            interval: Time interval ('hour', 'day', 'week')
            
        Returns:
            Dictionary with time series metrics
        """
        # Warn if called from async context
        self._warn_if_async_context("get_metrics_over_time")
        
        # Set default time range if not provided
        if end_time is None:
            end_time = time.time()
            
        if start_time is None:
            start_time = end_time - (24 * 60 * 60)  # 24 hours ago
        
        # Calculate intervals
        intervals = []
        current_time = start_time
        
        if interval == "hour":
            step = 60 * 60  # 1 hour
        elif interval == "day":
            step = 24 * 60 * 60  # 1 day
        elif interval == "week":
            step = 7 * 24 * 60 * 60  # 1 week
        else:
            raise ValueError(f"Invalid interval: {interval}. Must be 'hour', 'day', or 'week'.")
        
        while current_time < end_time:
            next_time = min(current_time + step, end_time)
            intervals.append((current_time, next_time))
            current_time = next_time
        
        # Get metrics for each interval
        time_series = []
        for interval_start, interval_end in intervals:
            metrics = self.get_metrics(
                metric_type=metric_type,
                operation_type=operation_type,
                backend=backend,
                status=status,
                time_range=(interval_start, interval_end),
                aggregation=TelemetryAggregation.AVERAGE
            )
            
            # Add timestamp to metrics
            interval_data = {
                "start_time": interval_start,
                "end_time": interval_end,
                "timestamp": (interval_start + interval_end) / 2,  # Middle of interval
                "metrics": metrics.get("metrics", {})
            }
            
            time_series.append(interval_data)
        
        return {
            "success": True,
            "operation": "get_metrics_over_time",
            "timestamp": time.time(),
            "metric_type": metric_type,
            "start_time": start_time,
            "end_time": end_time,
            "interval": interval,
            "time_series": time_series
        }
    
    async def get_metrics_over_time_async(self, metric_type: Union[str, TelemetryMetricType],
                                      operation_type: Optional[str] = None, 
                                      backend: Optional[str] = None,
                                      status: Optional[str] = None, 
                                      start_time: Optional[float] = None,
                                      end_time: Optional[float] = None,
                                      interval: str = "hour") -> Dict[str, Any]:
        """
        Get metrics over time with specified interval asynchronously.
        
        This is a convenience method that retrieves metrics for multiple time periods
        and organizes them into a time series.
        
        Args:
            metric_type: Type of metrics to retrieve
            operation_type: Filter by operation type
            backend: Filter by backend type
            status: Filter by operation status
            start_time: Start time (defaults to 24 hours ago)
            end_time: End time (defaults to now)
            interval: Time interval ('hour', 'day', 'week')
            
        Returns:
            Dictionary with time series metrics
        """
        # Set default time range if not provided
        if end_time is None:
            end_time = time.time()
            
        if start_time is None:
            start_time = end_time - (24 * 60 * 60)  # 24 hours ago
        
        # Calculate intervals
        intervals = []
        current_time = start_time
        
        if interval == "hour":
            step = 60 * 60  # 1 hour
        elif interval == "day":
            step = 24 * 60 * 60  # 1 day
        elif interval == "week":
            step = 7 * 24 * 60 * 60  # 1 week
        else:
            raise ValueError(f"Invalid interval: {interval}. Must be 'hour', 'day', or 'week'.")
        
        while current_time < end_time:
            next_time = min(current_time + step, end_time)
            intervals.append((current_time, next_time))
            current_time = next_time
        
        # Get metrics for each interval asynchronously
        time_series = []
        for interval_start, interval_end in intervals:
            metrics = await self.get_metrics_async(
                metric_type=metric_type,
                operation_type=operation_type,
                backend=backend,
                status=status,
                time_range=(interval_start, interval_end),
                aggregation=TelemetryAggregation.AVERAGE
            )
            
            # Add timestamp to metrics
            interval_data = {
                "start_time": interval_start,
                "end_time": interval_end,
                "timestamp": (interval_start + interval_end) / 2,  # Middle of interval
                "metrics": metrics.get("metrics", {})
            }
            
            time_series.append(interval_data)
        
        return {
            "success": True,
            "operation": "get_metrics_over_time",
            "timestamp": time.time(),
            "metric_type": metric_type,
            "start_time": start_time,
            "end_time": end_time,
            "interval": interval,
            "time_series": time_series
        }
    
    def monitor_realtime(self, callback: Callable, interval: int = 5, 
                       duration: Optional[int] = None) -> None:
        """
        Monitor real-time metrics at regular intervals.
        
        Args:
            callback: Function to call with each metrics update
            interval: Interval in seconds between updates
            duration: Total monitoring duration in seconds (None for indefinite)
        """
        # Warn if called from async context
        self._warn_if_async_context("monitor_realtime")
        
        start_time = time.time()
        iteration = 0
        
        try:
            while True:
                # Check if duration exceeded
                if duration is not None and time.time() - start_time >= duration:
                    break
                
                # Get real-time metrics
                metrics = self.get_realtime_metrics()
                
                # Call callback with metrics
                callback(metrics, iteration)
                
                # Increment iteration counter
                iteration += 1
                
                # Wait for next interval
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error during monitoring: {str(e)}")
            raise
    
    async def monitor_realtime_async(self, callback: Callable, interval: int = 5, 
                                  duration: Optional[int] = None) -> None:
        """
        Monitor real-time metrics at regular intervals asynchronously.
        
        Args:
            callback: Function to call with each metrics update
            interval: Interval in seconds between updates
            duration: Total monitoring duration in seconds (None for indefinite)
        """
        start_time = time.time()
        iteration = 0
        
        try:
            while True:
                # Check if duration exceeded
                if duration is not None and time.time() - start_time >= duration:
                    break
                
                # Get real-time metrics asynchronously
                metrics = await self.get_realtime_metrics_async()
                
                # Call callback with metrics (use anyio.to_thread.run_sync if callback is blocking)
                if anyio.iscoroutinefunction(callback):
                    await callback(metrics, iteration)
                else:
                    await anyio.to_thread.run_sync(
                        lambda: callback(metrics, iteration)
                    )
                
                # Increment iteration counter
                iteration += 1
                
                # Wait for next interval asynchronously
                await anyio.sleep(interval)
                
        except Exception as e:
            logger.error(f"Error during async monitoring: {str(e)}")
            raise

# Function to create appropriate client based on context
def get_telemetry_client(base_url: str = "http://localhost:8000", 
                        api_key: Optional[str] = None, 
                        timeout: int = 30, 
                        verify_ssl: bool = True,
                        use_anyio: Optional[bool] = None) -> Union[WALTelemetryClientAnyIO, "WALTelemetryClient"]:
    """
    Create a telemetry client based on the current context.
    
    Args:
        base_url: Base URL for the API server
        api_key: Optional API key for authentication
        timeout: Timeout in seconds for API requests
        verify_ssl: Whether to verify SSL certificates
        use_anyio: Whether to use the AnyIO client (if None, detect automatically)
        
    Returns:
        Telemetry client instance
    """
    if use_anyio is None:
        # Detect if in async context
        try:
            current_async_lib = sniffio.current_async_library()
            use_anyio = True
        except sniffio.AsyncLibraryNotFoundError:
            use_anyio = False
    
    if use_anyio:
        return WALTelemetryClientAnyIO(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            verify_ssl=verify_ssl
        )
    else:
        # Import original client
        from ipfs_kit_py.wal_telemetry_client import WALTelemetryClient
        return WALTelemetryClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            verify_ssl=verify_ssl
        )

# Example usage
if __name__ == "__main__":
    # Enable debug logging
    logging.basicConfig(level=logging.INFO)
    
    # Import asyncio for example
    import anyio
    
    # Example monitor callback
    def print_metrics(metrics, iteration):
        """Print real-time metrics as they arrive."""
        print(f"\n=== Metrics Update #{iteration} ===")
        latency = metrics.get("latency", {})
        success_rate = metrics.get("success_rate", {})
        error_rate = metrics.get("error_rate", {})
        throughput = metrics.get("throughput", {})
        
        print(f"Latency: {latency}")
        print(f"Success Rate: {success_rate}")
        print(f"Error Rate: {error_rate}")
        print(f"Throughput: {throughput}")
    
    # Async example using anyio
    async def async_example():
        # Create client
        client = WALTelemetryClientAnyIO(base_url="http://localhost:8000")
        
        try:
            # Get real-time metrics
            metrics = await client.get_realtime_metrics_async()
            print(f"Real-time metrics: {json.dumps(metrics, indent=2)}")
            
            # Get configuration
            config = await client.get_config_async()
            print(f"Configuration: {json.dumps(config, indent=2)}")
            
            # Demonstration of monitoring (uncomment to run for 10 seconds)
            # Define async callback
            # async def async_callback(metrics, iteration):
            #     print(f"\n=== Async Metrics Update #{iteration} ===")
            #     print(f"Metrics: {metrics}")
            # 
            # await client.monitor_realtime_async(async_callback, interval=2, duration=10)
            
        except Exception as e:
            print(f"Error in async example: {str(e)}")
    
    # Run async example with asyncio
    # anyio.run(async_example())
    
    # Run async example with trio (uncomment to test)
    # import trio
    # trio.run(async_example)