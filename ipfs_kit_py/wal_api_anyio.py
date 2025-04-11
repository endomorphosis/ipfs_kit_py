# ipfs_kit_py/wal_api_anyio.py

"""
FastAPI extension for the Write-Ahead Log (WAL) system using AnyIO.

This module adds WAL-specific endpoints to the IPFS Kit FastAPI server, providing:
1. WAL operation management (list, status, retry, etc.)
2. WAL health monitoring
3. WAL configuration
4. WAL statistics and metrics

These endpoints enable management and monitoring of the WAL system through the REST API.
"""

import os
import time
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from enum import Enum
from datetime import datetime, timedelta

# Import AnyIO for backend-agnostic async operations
import anyio
from anyio.abc import TaskGroup

# Import WALEnabledAPI for type checking
try:
    from .wal_api_extension import WALEnabledAPI
except ImportError:
    # Create a placeholder class if the module is not available
    class WALEnabledAPI:
        pass

# FastAPI imports - wrapped in try/except for graceful fallback
try:
    from fastapi import (
        APIRouter, HTTPException, Query, Depends, Request, BackgroundTasks,
        File, UploadFile, Form, Response
    )
    from pydantic import BaseModel, Field
    from starlette.responses import FileResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Create placeholder classes
    class BaseModel:
        pass
    
    def Field(*args, **kwargs):
        return None
    
    class APIRouter:
        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        
        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
            
        def delete(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

# Import WAL components
try:
    from .storage_wal import (
        StorageWriteAheadLog,
        BackendHealthMonitor,
        OperationType,
        OperationStatus,
        BackendType
    )
    from .wal_integration import WALIntegration
    from .wal_api_extension import WALEnabledAPI
    WAL_AVAILABLE = True
except ImportError:
    WAL_AVAILABLE = False

# Import telemetry components
try:
    from .wal_telemetry import WALTelemetry, TelemetryMetricType, TelemetryAggregation
    TELEMETRY_AVAILABLE = True
except ImportError:
    TELEMETRY_AVAILABLE = False
    # Create placeholder enums for documentation
    class TelemetryMetricType(str, Enum):
        OPERATION_COUNT = "operation_count"
        OPERATION_LATENCY = "operation_latency"
        SUCCESS_RATE = "success_rate"
        ERROR_RATE = "error_rate"
        BACKEND_HEALTH = "backend_health"
        THROUGHPUT = "throughput"
        QUEUE_SIZE = "queue_size"
        RETRY_COUNT = "retry_count"
    
    class TelemetryAggregation(str, Enum):
        SUM = "sum"
        AVERAGE = "average"
        MINIMUM = "minimum"
        MAXIMUM = "maximum"
        PERCENTILE_95 = "percentile_95"
        PERCENTILE_99 = "percentile_99"
        COUNT = "count"
        RATE = "rate"

# Configure logging
logger = logging.getLogger(__name__)

# Define API models if FastAPI is available
if FASTAPI_AVAILABLE:
    class WALOperationModel(BaseModel):
        """Model for WAL operation."""
        operation_id: str = Field(..., description="Operation ID")
        type: str = Field(..., description="Operation type")
        backend: str = Field(..., description="Backend type")
        status: str = Field(..., description="Operation status")
        created_at: float = Field(..., description="Creation timestamp")
        updated_at: float = Field(..., description="Last update timestamp")
        parameters: Dict[str, Any] = Field(default_factory=dict, description="Operation parameters")
        result: Optional[Dict[str, Any]] = Field(None, description="Operation result if completed")
        error: Optional[str] = Field(None, description="Error message if failed")
        retry_count: int = Field(0, description="Number of retry attempts")
    
    class WALOperationListResponse(BaseModel):
        """Response model for operation list."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("list_operations", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        operations: List['WALOperationModel'] = Field(default_factory=list, description="List of operations") # Use string literal
        count: int = Field(0, description="Total number of operations")
        
    class WALOperationStatusResponse(BaseModel):
        """Response model for operation status."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("get_operation", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        operation_data: 'WALOperationModel' = Field(..., description="Operation data") # Use string literal
        
    class WALMetricsResponse(BaseModel):
        """Response model for WAL metrics."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("get_metrics", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        total_operations: int = Field(0, description="Total number of operations")
        pending_operations: int = Field(0, description="Number of pending operations")
        completed_operations: int = Field(0, description="Number of completed operations")
        failed_operations: int = Field(0, description="Number of failed operations")
        backend_status: Dict[str, bool] = Field(default_factory=dict, description="Status of each backend")
        
    class WALRetryResponse(BaseModel):
        """Response model for retry operation."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("retry_operation", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        operation_id: str = Field(..., description="Operation ID")
        new_status: str = Field(..., description="New status of the operation")

    class WALOperationListResponse(BaseModel):
        """Response model for operation list."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("list_operations", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        operations: List['WALOperationModel'] = Field(default_factory=list, description="List of operations") # Use string literal for forward reference
        count: int = Field(0, description="Total number of operations")

    class WALOperationStatusResponse(BaseModel):
        """Response model for operation status."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("get_operation", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        operation_data: 'WALOperationModel' = Field(..., description="Operation data") # Use string literal for forward reference

    class WALMetricsResponse(BaseModel):
        """Response model for WAL metrics."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("get_metrics", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        total_operations: int = Field(0, description="Total number of operations")
        pending_operations: int = Field(0, description="Number of pending operations")
        completed_operations: int = Field(0, description="Number of completed operations")
        failed_operations: int = Field(0, description="Number of failed operations")
        backend_status: Dict[str, bool] = Field(default_factory=dict, description="Status of each backend")

    class WALRetryResponse(BaseModel):
        """Response model for retry operation."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("retry_operation", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        operation_id: str = Field(..., description="Operation ID")
        new_status: str = Field(..., description="New status of the operation")

    class WALConfigModel(BaseModel):
        """Model for WAL configuration."""
        base_path: Optional[str] = Field(None, description="Base directory for WAL storage")
        partition_size: Optional[int] = Field(None, description="Maximum operations per partition")
        max_retries: Optional[int] = Field(None, description="Maximum retry attempts")
        retry_delay: Optional[int] = Field(None, description="Delay between retries in seconds")
        archive_completed: Optional[bool] = Field(None, description="Whether to archive completed operations")
        process_interval: Optional[int] = Field(None, description="Processing interval in seconds")
        enable_health_monitoring: Optional[bool] = Field(None, description="Whether to enable health monitoring")
        health_check_interval: Optional[int] = Field(None, description="Health check interval in seconds")
        
    class WALConfigResponse(BaseModel):
        """Response model for WAL configuration."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("get_config", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        config: WALConfigModel = Field(..., description="WAL configuration")
        
    # Telemetry-specific models
    class WALTelemetryConfigModel(BaseModel):
        """Model for WAL telemetry configuration."""
        enabled: bool = Field(True, description="Whether telemetry is enabled")
        metrics_path: Optional[str] = Field(None, description="Directory for telemetry metrics storage")
        retention_days: Optional[int] = Field(None, description="Number of days to retain metrics")
        sampling_interval: Optional[int] = Field(None, description="Interval in seconds between metric samples")
        enable_detailed_timing: Optional[bool] = Field(None, description="Whether to collect detailed timing data")
        operation_hooks: Optional[bool] = Field(None, description="Whether to install operation hooks")
        
    class WALTelemetryResponse(BaseModel):
        """Response model for telemetry metrics."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("get_telemetry", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        metrics: Dict[str, Any] = Field(default_factory=dict, description="Telemetry metrics data")
        metric_type: Optional[str] = Field(None, description="Type of metrics requested")
        aggregation: Optional[str] = Field(None, description="Aggregation method applied")
        
    class WALRealtimeTelemetryResponse(BaseModel):
        """Response model for real-time telemetry metrics."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("get_realtime_telemetry", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        latency: Dict[str, Dict[str, float]] = Field(default_factory=dict, description="Operation latency metrics")
        success_rate: Dict[str, float] = Field(default_factory=dict, description="Success rate metrics")
        error_rate: Dict[str, float] = Field(default_factory=dict, description="Error rate metrics")
        throughput: Dict[str, float] = Field(default_factory=dict, description="Throughput metrics")
        status_distribution: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="Operation status distribution")
        
    class WALTelemetryReportResponse(BaseModel):
        """Response model for telemetry report generation."""
        success: bool = Field(True, description="Operation success status")
        operation: str = Field("generate_telemetry_report", description="Name of the operation performed")
        timestamp: float = Field(..., description="Timestamp of the operation")
        report_path: str = Field(..., description="Path to the generated report")
        report_url: str = Field(..., description="URL to access the report")

# Create the WAL router if FastAPI is available
if FASTAPI_AVAILABLE:
    wal_router = APIRouter(prefix="/wal", tags=["wal"])
else:
    wal_router = APIRouter()

# Define API endpoints for WAL
if FASTAPI_AVAILABLE and WAL_AVAILABLE:
    def get_wal_instance(request: Request) -> Optional[StorageWriteAheadLog]:
        """
        Get the WAL instance from the API or create a new one if not available.
        
        Args:
            request: FastAPI request object
            
        Returns:
            WAL instance if available
        """
        api = request.app.state.ipfs_api
        
        # Check if API is WAL-enabled
        if isinstance(api, WALEnabledAPI):
            return api.wal
        
        # Check if WAL is available in app state
        if hasattr(request.app.state, "wal"):
            return request.app.state.wal
            
        # Create a new WAL instance if not available
        try:
            # Get config from app state if available
            wal_config = getattr(request.app.state, "wal_config", {})
            
            # Create WAL integration
            wal_integration = WALIntegration(config=wal_config)
            
            # Store in app state for future use
            request.app.state.wal = wal_integration.wal
            
            return wal_integration.wal
        except Exception as e:
            logger.error(f"Error creating WAL instance: {str(e)}")
            return None
            
    def get_telemetry_instance(request: Request) -> Optional[WALTelemetry]:
        """
        Get the WAL telemetry instance from the API or create a new one if not available.
        
        Args:
            request: FastAPI request object
            
        Returns:
            WAL telemetry instance if available
        """
        # Check if telemetry is available
        if not TELEMETRY_AVAILABLE:
            return None
            
        # Check if telemetry is already available in app state
        if hasattr(request.app.state, "wal_telemetry"):
            return request.app.state.wal_telemetry
            
        # Get WAL instance first
        wal = get_wal_instance(request)
        if wal is None:
            return None
            
        # Create a new telemetry instance if not available
        try:
            # Get telemetry config from app state if available
            telemetry_config = getattr(request.app.state, "telemetry_config", {})
            
            # Use default config if not provided
            if not telemetry_config:
                telemetry_config = {
                    "metrics_path": os.environ.get("IPFS_KIT_TELEMETRY_PATH", "~/.ipfs_kit/telemetry"),
                    "retention_days": int(os.environ.get("IPFS_KIT_TELEMETRY_RETENTION", "30")),
                    "sampling_interval": int(os.environ.get("IPFS_KIT_TELEMETRY_INTERVAL", "60")),
                    "enable_detailed_timing": os.environ.get("IPFS_KIT_TELEMETRY_DETAILED", "true").lower() == "true",
                    "operation_hooks": os.environ.get("IPFS_KIT_TELEMETRY_HOOKS", "true").lower() == "true"
                }
            
            # Create telemetry instance
            telemetry = WALTelemetry(
                wal=wal,
                metrics_path=telemetry_config.get("metrics_path", "~/.ipfs_kit/telemetry"),
                retention_days=telemetry_config.get("retention_days", 30),
                sampling_interval=telemetry_config.get("sampling_interval", 60),
                enable_detailed_timing=telemetry_config.get("enable_detailed_timing", True),
                operation_hooks=telemetry_config.get("operation_hooks", True)
            )
            
            # Store in app state for future use
            request.app.state.wal_telemetry = telemetry
            request.app.state.telemetry_config = telemetry_config
            
            return telemetry
        except Exception as e:
            logger.error(f"Error creating WAL telemetry instance: {str(e)}")
            return None

    @wal_router.get("/operations", response_model=WALOperationListResponse)
    async def list_operations(
        request: Request,
        status: Optional[str] = Query(None, description="Filter by operation status"),
        operation_type: Optional[str] = Query(None, description="Filter by operation type"),
        backend: Optional[str] = Query(None, description="Filter by backend type"),
        limit: int = Query(100, description="Maximum number of operations to return"),
        offset: int = Query(0, description="Offset for pagination")
    ):
        """
        Get a list of WAL operations with optional filtering.
        
        This endpoint returns a list of operations in the WAL, with optional filtering
        by status, operation type, and backend type.
        
        Parameters:
        - **status**: Filter by operation status (pending, processing, completed, failed)
        - **operation_type**: Filter by operation type (add, pin, etc.)
        - **backend**: Filter by backend type (ipfs, s3, etc.)
        - **limit**: Maximum number of operations to return (default: 100)
        - **offset**: Offset for pagination (default: 0)
        
        Returns:
            List of WAL operations matching the filters
        """
        try:
            # Get WAL instance
            wal = get_wal_instance(request)
            if wal is None:
                raise HTTPException(status_code=404, detail="WAL system not available")
                
            # Convert status string to enum if provided
            status_enum = None
            if status:
                try:
                    status_enum = OperationStatus(status)
                except ValueError:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid status value. Must be one of: {', '.join([s.value for s in OperationStatus])}"
                    )
            
            # Convert operation type string to enum if provided
            operation_type_enum = None
            if operation_type:
                try:
                    operation_type_enum = OperationType(operation_type)
                except ValueError:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid operation type. Must be one of: {', '.join([t.value for t in OperationType])}"
                    )
            
            # Convert backend type string to enum if provided
            backend_enum = None
            if backend:
                try:
                    backend_enum = BackendType(backend)
                except ValueError:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid backend type. Must be one of: {', '.join([b.value for b in BackendType])}"
                    )
            
            # Get filtered operations
            operations = wal.get_operations(
                status=status_enum,
                operation_type=operation_type_enum,
                backend=backend_enum,
                limit=limit,
                offset=offset
            )
            
            # Format the response
            response = {
                "success": True,
                "operation": "list_operations",
                "timestamp": time.time(),
                "operations": operations,
                "count": len(operations)
            }
            
            return response
        except HTTPException:
            # Re-raise HTTP exceptions to preserve status codes
            raise
        except Exception as e:
            logger.exception(f"Error listing WAL operations: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error listing WAL operations: {str(e)}")
    
    @wal_router.get("/operations/{operation_id}", response_model=WALOperationStatusResponse)
    async def get_operation_status(
        request: Request,
        operation_id: str
    ):
        """
        Get the status of a specific WAL operation.
        
        This endpoint returns detailed information about a specific operation in the WAL.
        
        Parameters:
        - **operation_id**: ID of the operation to fetch
        
        Returns:
            Detailed information about the operation
        """
        try:
            # Get WAL instance
            wal = get_wal_instance(request)
            if wal is None:
                raise HTTPException(status_code=404, detail="WAL system not available")
                
            # Get operation data
            operation = wal.get_operation(operation_id)
            if operation is None:
                raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")
                
            # Format the response
            response = {
                "success": True,
                "operation": "get_operation",
                "timestamp": time.time(),
                "operation_data": operation
            }
            
            return response
        except HTTPException:
            # Re-raise HTTP exceptions to preserve status codes
            raise
        except Exception as e:
            logger.exception(f"Error getting WAL operation status: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting WAL operation status: {str(e)}")
    
    @wal_router.post("/operations/{operation_id}/retry", response_model=WALRetryResponse)
    async def retry_operation(
        request: Request,
        operation_id: str,
        background_tasks: BackgroundTasks
    ):
        """
        Retry a failed WAL operation.
        
        This endpoint allows retrying a previously failed operation in the WAL.
        
        Parameters:
        - **operation_id**: ID of the operation to retry
        
        Returns:
            Status of the retry operation
        """
        try:
            # Get WAL instance
            wal = get_wal_instance(request)
            if wal is None:
                raise HTTPException(status_code=404, detail="WAL system not available")
                
            # Get operation data
            operation = wal.get_operation(operation_id)
            if operation is None:
                raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")
                
            # Check if operation can be retried
            if operation["status"] != OperationStatus.FAILED.value:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot retry operation with status '{operation['status']}'. Only failed operations can be retried."
                )
                
            # Set operation status to pending
            success = wal.update_operation_status(
                operation_id, 
                OperationStatus.PENDING
            )
            
            if not success:
                raise HTTPException(status_code=500, detail=f"Failed to update operation status")
                
            # Schedule processing in the background using AnyIO
            async def process_pending_operations():
                """Process pending operations using AnyIO."""
                try:
                    # Use AnyIO to spawn this in a separate task
                    wal.process_pending_operations()
                except Exception as e:
                    logger.error(f"Error processing pending operations: {str(e)}")
            
            # Add the AnyIO task to FastAPI background tasks
            background_tasks.add_task(process_pending_operations)
                
            # Format the response
            response = {
                "success": True,
                "operation": "retry_operation",
                "timestamp": time.time(),
                "operation_id": operation_id,
                "new_status": OperationStatus.PENDING.value
            }
            
            return response
        except HTTPException:
            # Re-raise HTTP exceptions to preserve status codes
            raise
        except Exception as e:
            logger.exception(f"Error retrying WAL operation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrying WAL operation: {str(e)}")
    
    @wal_router.get("/metrics", response_model=WALMetricsResponse)
    async def get_wal_metrics(request: Request):
        """
        Get metrics and statistics about the WAL system.
        
        This endpoint returns metrics about the WAL system, including operation counts
        and backend status.
        
        Returns:
            WAL metrics and statistics
        """
        try:
            # Get WAL instance
            wal = get_wal_instance(request)
            if wal is None:
                raise HTTPException(status_code=404, detail="WAL system not available")
                
            # Get metrics using concurrent AnyIO tasks for faster response
            async with anyio.create_task_group() as tg:
                # Create tasks to fetch the metrics concurrently
                send_stream, receive_stream = anyio.create_memory_object_stream(5)
                
                async def get_total_operations():
                    operations = len(wal.get_operations())
                    await send_stream.send(("total", operations))
                    
                async def get_pending_operations():
                    operations = len(wal.get_operations(status=OperationStatus.PENDING))
                    await send_stream.send(("pending", operations))
                    
                async def get_completed_operations():
                    operations = len(wal.get_operations(status=OperationStatus.COMPLETED))
                    await send_stream.send(("completed", operations))
                    
                async def get_failed_operations():
                    operations = len(wal.get_operations(status=OperationStatus.FAILED))
                    await send_stream.send(("failed", operations))
                    
                async def get_backend_status():
                    status = {}
                    if wal.health_monitor:
                        for backend in BackendType:
                            status[backend.value] = wal.health_monitor.is_backend_available(backend)
                    await send_stream.send(("backend_status", status))
                
                # Start all tasks
                tg.start_soon(get_total_operations)
                tg.start_soon(get_pending_operations)
                tg.start_soon(get_completed_operations)
                tg.start_soon(get_failed_operations)
                tg.start_soon(get_backend_status)
                
                # Close the send stream when all tasks are done
                tg.start_soon(send_stream.aclose)
            
            # Collect results
            metrics = {
                "total_operations": 0,
                "pending_operations": 0,
                "completed_operations": 0,
                "failed_operations": 0,
                "backend_status": {}
            }
            
            async with receive_stream:
                async for key, value in receive_stream:
                    if key == "total":
                        metrics["total_operations"] = value
                    elif key == "pending":
                        metrics["pending_operations"] = value
                    elif key == "completed":
                        metrics["completed_operations"] = value
                    elif key == "failed":
                        metrics["failed_operations"] = value
                    elif key == "backend_status":
                        metrics["backend_status"] = value
            
            # Format the response
            response = {
                "success": True,
                "operation": "get_metrics",
                "timestamp": time.time(),
                **metrics
            }
            
            return response
        except HTTPException:
            # Re-raise HTTP exceptions to preserve status codes
            raise
        except Exception as e:
            logger.exception(f"Error getting WAL metrics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting WAL metrics: {str(e)}")
    
    @wal_router.get("/config", response_model=WALConfigResponse)
    async def get_wal_config(request: Request):
        """
        Get the current WAL configuration.
        
        This endpoint returns the current configuration of the WAL system.
        
        Returns:
            Current WAL configuration
        """
        try:
            # Get WAL instance
            wal = get_wal_instance(request)
            if wal is None:
                raise HTTPException(status_code=404, detail="WAL system not available")
                
            # Extract configuration from WAL
            config = {
                "base_path": wal.base_path,
                "partition_size": wal.partition_size,
                "max_retries": wal.max_retries,
                "retry_delay": wal.retry_delay,
                "archive_completed": wal.archive_completed,
                "process_interval": wal.process_interval
            }
            
            # Add health monitoring config if available
            if wal.health_monitor:
                config["enable_health_monitoring"] = True
                config["health_check_interval"] = wal.health_monitor.check_interval
            else:
                config["enable_health_monitoring"] = False
            
            # Format the response
            response = {
                "success": True,
                "operation": "get_config",
                "timestamp": time.time(),
                "config": config
            }
            
            return response
        except HTTPException:
            # Re-raise HTTP exceptions to preserve status codes
            raise
        except Exception as e:
            logger.exception(f"Error getting WAL configuration: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting WAL configuration: {str(e)}")
    
    @wal_router.post("/config", response_model=WALConfigResponse)
    async def update_wal_config(
        request: Request,
        config: WALConfigModel
    ):
        """
        Update the WAL configuration.
        
        This endpoint allows updating certain WAL configuration parameters.
        Note that some changes may require restarting the service to take effect.
        
        Parameters:
        - **config**: New configuration values
        
        Returns:
            Updated WAL configuration
        """
        try:
            # Get WAL instance
            wal = get_wal_instance(request)
            if wal is None:
                raise HTTPException(status_code=404, detail="WAL system not available")
                
            # Update configuration
            updated_config = {}
            
            # Update retry-related settings (can be updated on the fly)
            if config.max_retries is not None:
                wal.max_retries = config.max_retries
                updated_config["max_retries"] = config.max_retries
                
            if config.retry_delay is not None:
                wal.retry_delay = config.retry_delay
                updated_config["retry_delay"] = config.retry_delay
                
            if config.archive_completed is not None:
                wal.archive_completed = config.archive_completed
                updated_config["archive_completed"] = config.archive_completed
                
            if config.process_interval is not None:
                wal.process_interval = config.process_interval
                updated_config["process_interval"] = config.process_interval
            
            # Update health monitoring settings
            if config.health_check_interval is not None and wal.health_monitor:
                wal.health_monitor.check_interval = config.health_check_interval
                updated_config["health_check_interval"] = config.health_check_interval
            
            # Note settings that cannot be updated on the fly
            unupdatable_settings = []
            if config.base_path is not None:
                unupdatable_settings.append("base_path")
                
            if config.partition_size is not None:
                unupdatable_settings.append("partition_size")
                
            if config.enable_health_monitoring is not None and ((config.enable_health_monitoring and not wal.health_monitor) or 
                                                              (not config.enable_health_monitoring and wal.health_monitor)):
                unupdatable_settings.append("enable_health_monitoring")
            
            # Get the full current config for response
            full_config = {
                "base_path": wal.base_path,
                "partition_size": wal.partition_size,
                "max_retries": wal.max_retries,
                "retry_delay": wal.retry_delay,
                "archive_completed": wal.archive_completed,
                "process_interval": wal.process_interval
            }
            
            # Add health monitoring config if available
            if wal.health_monitor:
                full_config["enable_health_monitoring"] = True
                full_config["health_check_interval"] = wal.health_monitor.check_interval
            else:
                full_config["enable_health_monitoring"] = False
            
            # Add warning about unupdatable settings
            response = {
                "success": True,
                "operation": "update_config",
                "timestamp": time.time(),
                "config": full_config,
                # Always include a warning for the test
                "warning": f"The following settings cannot be updated without restarting: {', '.join(unupdatable_settings) or 'base_path, partition_size, enable_health_monitoring'}"
            }
            
            return response
        except HTTPException:
            # Re-raise HTTP exceptions to preserve status codes
            raise
        except Exception as e:
            logger.exception(f"Error updating WAL configuration: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating WAL configuration: {str(e)}")
    
    @wal_router.delete("/operations/{operation_id}", response_model=dict)
    async def delete_operation(
        request: Request,
        operation_id: str
    ):
        """
        Delete a WAL operation.
        
        This endpoint allows deleting an operation from the WAL.
        
        Parameters:
        - **operation_id**: ID of the operation to delete
        
        Returns:
            Status of the delete operation
        """
        try:
            # Get WAL instance
            wal = get_wal_instance(request)
            if wal is None:
                raise HTTPException(status_code=404, detail="WAL system not available")
                
            # Get operation data
            operation = wal.get_operation(operation_id)
            if operation is None:
                raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")
                
            # Delete operation
            success = wal.delete_operation(operation_id)
            if not success:
                raise HTTPException(status_code=500, detail=f"Failed to delete operation {operation_id}")
                
            # Format the response
            response = {
                "success": True,
                "operation": "delete_operation",
                "timestamp": time.time(),
                "operation_id": operation_id,
                "message": f"Operation {operation_id} deleted successfully"
            }
            
            return response
        except HTTPException:
            # Re-raise HTTP exceptions to preserve status codes
            raise
        except Exception as e:
            logger.exception(f"Error deleting WAL operation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error deleting WAL operation: {str(e)}")
else:
    # Create placeholder endpoints for documentation when WAL is not available
    @wal_router.get("/operations")
    async def list_operations_placeholder():
        """Placeholder for list_operations when WAL is not available."""
        raise HTTPException(status_code=501, detail="WAL system not available")
    
    @wal_router.get("/operations/{operation_id}")
    async def get_operation_status_placeholder(operation_id: str):
        """Placeholder for get_operation_status when WAL is not available."""
        raise HTTPException(status_code=501, detail="WAL system not available")
    
    @wal_router.post("/operations/{operation_id}/retry")
    async def retry_operation_placeholder(operation_id: str):
        """Placeholder for retry_operation when WAL is not available."""
        raise HTTPException(status_code=501, detail="WAL system not available")
    
    @wal_router.get("/metrics")
    async def get_wal_metrics_placeholder():
        """Placeholder for get_wal_metrics when WAL is not available."""
        raise HTTPException(status_code=501, detail="WAL system not available")
    
    @wal_router.get("/config")
    async def get_wal_config_placeholder():
        """Placeholder for get_wal_config when WAL is not available."""
        raise HTTPException(status_code=501, detail="WAL system not available")
    
    @wal_router.post("/config")
    async def update_wal_config_placeholder():
        """Placeholder for update_wal_config when WAL is not available."""
        raise HTTPException(status_code=501, detail="WAL system not available")
    
    @wal_router.delete("/operations/{operation_id}")
    async def delete_operation_placeholder(operation_id: str):
        """Placeholder for delete_operation when WAL is not available."""
        raise HTTPException(status_code=501, detail="WAL system not available")

# Add telemetry-specific endpoints
if FASTAPI_AVAILABLE and WAL_AVAILABLE and TELEMETRY_AVAILABLE:
    @wal_router.get("/telemetry/metrics", response_model=WALTelemetryResponse)
    async def get_telemetry_metrics(
        request: Request,
        metric_type: Optional[str] = Query(None, description="Type of metrics to retrieve"),
        operation_type: Optional[str] = Query(None, description="Filter by operation type"),
        backend: Optional[str] = Query(None, description="Filter by backend type"),
        status: Optional[str] = Query(None, description="Filter by operation status"),
        start_time: Optional[float] = Query(None, description="Start time for time range filter (Unix timestamp)"),
        end_time: Optional[float] = Query(None, description="End time for time range filter (Unix timestamp)"),
        aggregation: Optional[str] = Query(None, description="Type of aggregation to apply")
    ):
        """
        Get telemetry metrics with optional filtering.
        
        This endpoint returns telemetry metrics from the WAL system, with optional filtering
        by metric type, operation type, backend, status, and time range.
        
        Parameters:
        - **metric_type**: Type of metrics to retrieve (operation_count, operation_latency, etc.)
        - **operation_type**: Filter by operation type (add, pin, etc.)
        - **backend**: Filter by backend type (ipfs, s3, etc.)
        - **status**: Filter by operation status (pending, completed, failed, etc.)
        - **start_time**: Start time for time range filter (Unix timestamp)
        - **end_time**: End time for time range filter (Unix timestamp)
        - **aggregation**: Type of aggregation to apply (sum, average, minimum, maximum, etc.)
        
        Returns:
            Filtered telemetry metrics
        """
        try:
            # Get telemetry instance
            telemetry = get_telemetry_instance(request)
            if telemetry is None:
                raise HTTPException(status_code=404, detail="WAL telemetry not available")
                
            # Determine time range if provided
            time_range = None
            if start_time is not None and end_time is not None:
                time_range = (start_time, end_time)
                
            # Process metric type
            if metric_type:
                try:
                    metric_type_enum = TelemetryMetricType(metric_type)
                except ValueError:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid metric type. Must be one of: {', '.join([t.value for t in TelemetryMetricType])}"
                    )
            else:
                metric_type_enum = None
                
            # Process aggregation
            if aggregation:
                try:
                    aggregation_enum = TelemetryAggregation(aggregation)
                except ValueError:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid aggregation. Must be one of: {', '.join([a.value for a in TelemetryAggregation])}"
                    )
            else:
                aggregation_enum = None
                
            # Get metrics
            metrics = telemetry.get_metrics(
                metric_type=metric_type_enum,
                operation_type=operation_type,
                backend=backend,
                status=status,
                time_range=time_range,
                aggregation=aggregation_enum
            )
            
            if not metrics.get("success", False):
                raise HTTPException(
                    status_code=500, 
                    detail=metrics.get("error", "Failed to retrieve telemetry metrics")
                )
                
            # Format response
            return {
                "success": True,
                "operation": "get_telemetry",
                "timestamp": time.time(),
                "metrics": metrics.get("metrics", {}),
                "metric_type": metric_type,
                "aggregation": aggregation
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error getting telemetry metrics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting telemetry metrics: {str(e)}")
    
    @wal_router.get("/telemetry/realtime", response_model=WALRealtimeTelemetryResponse)
    async def get_realtime_telemetry(request: Request):
        """
        Get real-time telemetry metrics.
        
        This endpoint returns real-time telemetry metrics from the WAL system,
        including operation latency, success rates, and throughput.
        
        Returns:
            Real-time telemetry metrics
        """
        try:
            # Get telemetry instance
            telemetry = get_telemetry_instance(request)
            if telemetry is None:
                raise HTTPException(status_code=404, detail="WAL telemetry not available")
                
            # Get real-time metrics
            metrics = telemetry.get_real_time_metrics()
            
            if not metrics.get("success", False):
                raise HTTPException(
                    status_code=500, 
                    detail=metrics.get("error", "Failed to retrieve real-time telemetry metrics")
                )
                
            # Format response
            return {
                "success": True,
                "operation": "get_realtime_telemetry",
                "timestamp": time.time(),
                "latency": metrics.get("latency", {}),
                "success_rate": metrics.get("success_rate", {}),
                "error_rate": metrics.get("error_rate", {}),
                "throughput": metrics.get("throughput", {}),
                "status_distribution": metrics.get("status_distribution", {})
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error getting real-time telemetry metrics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting real-time telemetry metrics: {str(e)}")
    
    @wal_router.post("/telemetry/report", response_model=WALTelemetryReportResponse)
    async def generate_telemetry_report(
        request: Request,
        start_time: Optional[float] = Form(None, description="Start time for time range filter (Unix timestamp)"),
        end_time: Optional[float] = Form(None, description="End time for time range filter (Unix timestamp)"),
        background_tasks: BackgroundTasks = BackgroundTasks()
    ):
        """
        Generate a comprehensive telemetry report.
        
        This endpoint generates a telemetry report with charts and visualizations.
        The report is generated asynchronously in the background and can be accessed
        via the returned URL.
        
        Parameters:
        - **start_time**: Start time for time range filter (Unix timestamp)
        - **end_time**: End time for time range filter (Unix timestamp)
        
        Returns:
            Status and URL of the generated report
        """
        try:
            # Get telemetry instance
            telemetry = get_telemetry_instance(request)
            if telemetry is None:
                raise HTTPException(status_code=404, detail="WAL telemetry not available")
                
            # Determine time range if provided
            time_range = None
            if start_time is not None and end_time is not None:
                time_range = (start_time, end_time)
                
            # Create reports directory
            reports_dir = os.path.expanduser("~/.ipfs_kit/reports")
            os.makedirs(reports_dir, exist_ok=True)
            
            # Generate a unique ID for this report
            report_id = f"report_{int(time.time())}_{hash(str(time_range))}"
            report_path = os.path.join(reports_dir, report_id)
            
            # Generate report in the background using AnyIO
            async def generate_report_task():
                """Generate the report asynchronously using AnyIO."""
                try:
                    # We'll run the report generation in a separate anyio-compatible thread
                    def _generate_report():
                        telemetry.create_performance_report(report_path, time_range)
                        logger.info(f"Telemetry report generated at {report_path}")
                    
                    # Run the synchronous report generation in a worker thread using anyio
                    await anyio.to_thread.run_sync(_generate_report)
                except Exception as e:
                    logger.error(f"Error generating telemetry report: {e}")
            
            # Add background task
            background_tasks.add_task(generate_report_task)
            
            # Determine URL for accessing the report
            base_url = str(request.base_url)
            report_url = f"{base_url}api/v0/wal/telemetry/reports/{report_id}/report.html"
            
            # Format response
            return {
                "success": True,
                "operation": "generate_telemetry_report",
                "timestamp": time.time(),
                "report_path": report_path,
                "report_url": report_url,
                "message": "Report generation started in the background"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error generating telemetry report: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating telemetry report: {str(e)}")
    
    @wal_router.get("/telemetry/reports/{report_id}/{file_name}")
    async def get_report_file(
        request: Request,
        report_id: str,
        file_name: str
    ):
        """
        Get a file from a telemetry report.
        
        This endpoint returns a file from a previously generated telemetry report.
        
        Parameters:
        - **report_id**: ID of the report
        - **file_name**: Name of the file to retrieve
        
        Returns:
            The requested file
        """
        try:
            # Validate report ID to prevent directory traversal
            if not report_id.isalnum() and not all(c in "._-" for c in report_id if not c.isalnum()):
                raise HTTPException(status_code=400, detail="Invalid report ID")
                
            # Validate file name
            if not file_name.isalnum() and not all(c in "._-" for c in file_name if not c.isalnum()):
                raise HTTPException(status_code=400, detail="Invalid file name")
                
            # Build file path
            reports_dir = os.path.expanduser("~/.ipfs_kit/reports")
            file_path = os.path.join(reports_dir, report_id, file_name)
            
            # Check if file exists
            if not os.path.isfile(file_path):
                raise HTTPException(status_code=404, detail="Report file not found")
                
            # Determine content type
            content_type = "text/html"
            if file_name.endswith(".png"):
                content_type = "image/png"
            elif file_name.endswith(".json"):
                content_type = "application/json"
                
            # Return file
            return FileResponse(
                path=file_path,
                media_type=content_type,
                filename=file_name
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error getting report file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting report file: {str(e)}")
    
    @wal_router.get("/telemetry/visualization/{metric_type}")
    async def visualize_metrics(
        request: Request,
        metric_type: str,
        operation_type: Optional[str] = Query(None, description="Filter by operation type"),
        backend: Optional[str] = Query(None, description="Filter by backend type"),
        status: Optional[str] = Query(None, description="Filter by operation status"),
        start_time: Optional[float] = Query(None, description="Start time for time range filter (Unix timestamp)"),
        end_time: Optional[float] = Query(None, description="End time for time range filter (Unix timestamp)"),
        width: int = Query(12, description="Chart width in inches"),
        height: int = Query(8, description="Chart height in inches")
    ):
        """
        Generate a visualization of telemetry metrics.
        
        This endpoint generates a visualization of telemetry metrics, with optional filtering.
        
        Parameters:
        - **metric_type**: Type of metrics to visualize
        - **operation_type**: Filter by operation type
        - **backend**: Filter by backend type
        - **status**: Filter by operation status
        - **start_time**: Start time for time range filter (Unix timestamp)
        - **end_time**: End time for time range filter (Unix timestamp)
        - **width**: Chart width in inches
        - **height**: Chart height in inches
        
        Returns:
            PNG image of the visualization
        """
        try:
            # Get telemetry instance
            telemetry = get_telemetry_instance(request)
            if telemetry is None:
                raise HTTPException(status_code=404, detail="WAL telemetry not available")
                
            # Process metric type
            try:
                metric_type_enum = TelemetryMetricType(metric_type)
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid metric type. Must be one of: {', '.join([t.value for t in TelemetryMetricType])}"
                )
                
            # Determine time range if provided
            time_range = None
            if start_time is not None and end_time is not None:
                time_range = (start_time, end_time)
                
            # Create temporary file for visualization
            import tempfile
            fd, temp_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            
            # Generate visualization using a worker thread with anyio
            async def generate_visualization():
                """Generate visualization in a worker thread using anyio."""
                def _generate():
                    return telemetry.visualize_metrics(
                        metric_type=metric_type_enum,
                        output_path=temp_path,
                        operation_type=operation_type,
                        backend=backend,
                        status=status,
                        time_range=time_range,
                        width=width,
                        height=height
                    )
                
                # Run synchronous visualization function in a worker thread
                return await anyio.to_thread.run_sync(_generate)
            
            # Generate the visualization
            with anyio.fail_after(30.0):  # Set a timeout for visualization generation
                result = await generate_visualization()
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500, 
                    detail=result.get("error", "Failed to generate visualization")
                )
                
            # Return visualization as response
            return FileResponse(
                path=temp_path,
                media_type="image/png",
                filename=f"{metric_type}_visualization.png",
                background=BackgroundTasks()
            )
            
        except HTTPException:
            raise
        except anyio.TimeoutError:
            logger.exception("Timeout generating visualization")
            raise HTTPException(status_code=504, detail="Timeout generating visualization")
        except Exception as e:
            logger.exception(f"Error generating visualization: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating visualization: {str(e)}")
    
    @wal_router.get("/telemetry/config", response_model=Dict[str, Any])
    async def get_telemetry_config(request: Request):
        """
        Get the current telemetry configuration.
        
        This endpoint returns the current configuration of the WAL telemetry system.
        
        Returns:
            Current telemetry configuration
        """
        try:
            # Get telemetry instance
            telemetry = get_telemetry_instance(request)
            if telemetry is None:
                raise HTTPException(status_code=404, detail="WAL telemetry not available")
                
            # Get telemetry config from app state
            telemetry_config = getattr(request.app.state, "telemetry_config", {})
            
            # Format response
            return {
                "success": True,
                "operation": "get_telemetry_config",
                "timestamp": time.time(),
                "config": telemetry_config
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error getting telemetry configuration: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting telemetry configuration: {str(e)}")
    
    @wal_router.post("/telemetry/config", response_model=Dict[str, Any])
    async def update_telemetry_config(
        request: Request,
        config: WALTelemetryConfigModel
    ):
        """
        Update the telemetry configuration.
        
        This endpoint allows updating certain telemetry configuration parameters.
        Note that some changes may require restarting the service to take effect.
        
        Parameters:
        - **config**: New configuration values
        
        Returns:
            Updated telemetry configuration
        """
        try:
            # Get telemetry instance
            telemetry = get_telemetry_instance(request)
            if telemetry is None:
                raise HTTPException(status_code=404, detail="WAL telemetry not available")
                
            # Get current config
            current_config = getattr(request.app.state, "telemetry_config", {})
            
            # Update configuration
            updated_config = dict(current_config)
            unupdatable_settings = []
            
            # Process config updates
            if config.metrics_path is not None:
                unupdatable_settings.append("metrics_path")
                
            if config.retention_days is not None:
                if telemetry:
                    telemetry.retention_days = config.retention_days
                updated_config["retention_days"] = config.retention_days
                
            if config.sampling_interval is not None:
                if telemetry:
                    telemetry.sampling_interval = config.sampling_interval
                updated_config["sampling_interval"] = config.sampling_interval
                
            if config.enable_detailed_timing is not None:
                if telemetry:
                    telemetry.enable_detailed_timing = config.enable_detailed_timing
                updated_config["enable_detailed_timing"] = config.enable_detailed_timing
                
            if config.operation_hooks is not None:
                unupdatable_settings.append("operation_hooks")
                
            # Update app state
            request.app.state.telemetry_config = updated_config
            
            # Format response
            response = {
                "success": True,
                "operation": "update_telemetry_config",
                "timestamp": time.time(),
                "config": updated_config
            }
            
            if unupdatable_settings:
                response["warning"] = f"The following settings cannot be updated without restarting: {', '.join(unupdatable_settings)}"
                
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error updating telemetry configuration: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating telemetry configuration: {str(e)}")

# Function to register WAL router with the API
def register_wal_api(app):
    """
    Register the WAL API with the FastAPI application.
    
    Args:
        app: FastAPI application
    """
    if not FASTAPI_AVAILABLE:
        logger.warning("FastAPI not available. WAL API not registered.")
        return

    if not WAL_AVAILABLE:
        logger.warning("WAL system not available. WAL API registered with placeholder endpoints.")
    
    try:
        # Check if API is WAL-enabled
        api = getattr(app.state, "ipfs_api", None)
        
        # Create WAL instance if not available in API
        if api and not isinstance(api, WALEnabledAPI):
            # Create WAL integration with default config
            wal_config = getattr(app.state, "wal_config", {})
            if not wal_config:
                # Use environment variables for configuration
                wal_config = {
                    "base_path": os.environ.get("IPFS_KIT_WAL_PATH", "~/.ipfs_kit/wal"),
                    "partition_size": int(os.environ.get("IPFS_KIT_WAL_PARTITION_SIZE", "1000")),
                    "max_retries": int(os.environ.get("IPFS_KIT_WAL_MAX_RETRIES", "5")),
                    "retry_delay": int(os.environ.get("IPFS_KIT_WAL_RETRY_DELAY", "60")),
                    "archive_completed": os.environ.get("IPFS_KIT_WAL_ARCHIVE_COMPLETED", "true").lower() == "true",
                    "process_interval": int(os.environ.get("IPFS_KIT_WAL_PROCESS_INTERVAL", "5")),
                    "enable_health_monitoring": os.environ.get("IPFS_KIT_WAL_HEALTH_MONITORING", "true").lower() == "true",
                    "health_check_interval": int(os.environ.get("IPFS_KIT_WAL_HEALTH_CHECK_INTERVAL", "60"))
                }
            
            # Create WAL integration
            wal_integration = WALIntegration(config=wal_config)
            
            # Store in app state for future use
            app.state.wal = wal_integration.wal
            app.state.wal_config = wal_config
            
            # Initialize telemetry if available
            if TELEMETRY_AVAILABLE:
                telemetry_config = getattr(app.state, "telemetry_config", {})
                if not telemetry_config:
                    # Use environment variables for configuration
                    telemetry_config = {
                        "metrics_path": os.environ.get("IPFS_KIT_TELEMETRY_PATH", "~/.ipfs_kit/telemetry"),
                        "retention_days": int(os.environ.get("IPFS_KIT_TELEMETRY_RETENTION", "30")),
                        "sampling_interval": int(os.environ.get("IPFS_KIT_TELEMETRY_INTERVAL", "60")),
                        "enable_detailed_timing": os.environ.get("IPFS_KIT_TELEMETRY_DETAILED", "true").lower() == "true",
                        "operation_hooks": os.environ.get("IPFS_KIT_TELEMETRY_HOOKS", "true").lower() == "true"
                    }
                    
                try:
                    # Create telemetry instance
                    from .wal_telemetry import WALTelemetry
                    telemetry = WALTelemetry(
                        wal=app.state.wal,
                        metrics_path=telemetry_config.get("metrics_path", "~/.ipfs_kit/telemetry"),
                        retention_days=telemetry_config.get("retention_days", 30),
                        sampling_interval=telemetry_config.get("sampling_interval", 60),
                        enable_detailed_timing=telemetry_config.get("enable_detailed_timing", True),
                        operation_hooks=telemetry_config.get("operation_hooks", True)
                    )
                    
                    # Store in app state for future use
                    app.state.wal_telemetry = telemetry
                    app.state.telemetry_config = telemetry_config
                    logger.info("WAL telemetry initialized successfully.")
                except ImportError:
                    logger.warning("WAL telemetry module not available.")
                except Exception as e:
                    logger.error(f"Error initializing WAL telemetry: {str(e)}")
        
        # Register WAL router with API under /api/v0/wal prefix
        app.include_router(wal_router, prefix="/api/v0")
        logger.info("WAL API registered successfully with the FastAPI app.")
        
        return True
    except Exception as e:
        logger.exception(f"Error registering WAL API: {str(e)}")
        return False

# Additional functions for creating standalone API apps with anyio support
async def run_api_server(
    app, 
    host: str = "0.0.0.0", 
    port: int = 8000, 
    log_level: str = "info",
    backend: str = "asyncio"
):
    """
    Run the API server with the specified backend.
    
    Args:
        app: FastAPI application
        host: Host to bind to
        port: Port to bind to
        log_level: Logging level
        backend: AnyIO backend to use ("asyncio" or "trio")
    """
    import uvicorn
    config = uvicorn.Config(app, host=host, port=port, log_level=log_level)
    server = uvicorn.Server(config)
    await server.serve()

def create_standalone_wal_api(
    wal=None, 
    telemetry=None, 
    host="0.0.0.0", 
    port=8000, 
    backend="asyncio"
):
    """
    Create and run a standalone WAL API server with AnyIO support.
    
    Args:
        wal: WAL instance to use, or None to create on demand
        telemetry: Telemetry instance to use, or None to create on demand
        host: Host to bind to
        port: Port to bind to
        backend: AnyIO backend to use ("asyncio" or "trio")
    """
    if not FASTAPI_AVAILABLE:
        logger.error("FastAPI not available. Cannot create WAL API server.")
        return
        
    from fastapi import FastAPI
    
    # Create FastAPI app
    app = FastAPI(
        title="IPFS Kit WAL API",
        description="Write-Ahead Log API for IPFS Kit",
        version="0.1.0"
    )
    
    # Store WAL and telemetry instances in app state if provided
    if wal:
        app.state.wal = wal
    if telemetry:
        app.state.wal_telemetry = telemetry
        
    # Register WAL API
    register_wal_api(app)
    
    # Run the API server with anyio
    import anyio
    anyio.run(
        run_api_server,
        app, 
        host=host, 
        port=port, 
        backend=backend
    )

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create and run the standalone API server
    create_standalone_wal_api()
