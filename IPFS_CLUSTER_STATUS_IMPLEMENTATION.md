# IPFS Cluster Status Implementation

## Overview

This document describes the implementation of the IPFS cluster daemon status functionality within the `ipfs_kit_py` project. The implementation adds support for checking the status of both `ipfs-cluster-service` and `ipfs-cluster-follow` daemons within the MCP (Model-Controller-Persistence) architecture.

## Implementation Components

### 1. Module-Level Status Methods

#### `ipfs_cluster_service_status` in `ipfs_cluster_service.py`

This method checks if the IPFS cluster service daemon is running by using the `ps` command to look for running processes matching the pattern `ipfs-cluster-service daemon`.

```python
def ipfs_cluster_service_status(self, **kwargs):
    """Get the status of the IPFS cluster-service daemon.

    Args:
        **kwargs: Optional arguments
            - correlation_id: ID for tracking related operations
            - timeout: Command timeout in seconds

    Returns:
        Dictionary with operation result information
    """
    # Create standardized result dictionary
    correlation_id = kwargs.get("correlation_id", getattr(self, "correlation_id", str(uuid.uuid4())))
    result = create_result_dict("ipfs_cluster_service_status", correlation_id)

    try:
        # Set timeout for commands
        timeout = kwargs.get("timeout", 30)

        # First check if the process is running
        process_check_cmd = ["ps", "-ef"]
        ps_result = self.run_cluster_service_command(
            process_check_cmd, check=False, timeout=10, correlation_id=correlation_id
        )

        process_running = False
        process_count = 0

        # Process ps output to check for ipfs-cluster-service processes
        if ps_result.get("success", False) and ps_result.get("stdout"):
            for line in ps_result.get("stdout", "").splitlines():
                if "ipfs-cluster-service" in line and "daemon" in line and "grep" not in line:
                    process_running = True
                    process_count += 1

        result["process_running"] = process_running
        result["process_count"] = process_count

        # If process is running, try to get detailed status
        if process_running:
            # Use the ipfs-cluster-service status command
            status_cmd = ["ipfs-cluster-service", "status"]
            status_result = self.run_cluster_service_command(
                status_cmd, check=False, timeout=timeout, correlation_id=correlation_id
            )

            if status_result.get("success", False):
                result["detailed_status"] = status_result.get("stdout", "")
                result["success"] = True
            else:
                # If status command fails, at least we know process is running
                result["detailed_status_error"] = status_result.get("stderr", "")
                result["detailed_status_failed"] = True
                result["success"] = (
                    True  # Service is running even if we can't get detailed status
                )
        else:
            # Check socket file to see if it's stale
            socket_path = os.path.expanduser("~/.ipfs-cluster/api-socket")
            result["socket_exists"] = os.path.exists(socket_path)
            result["success"] = False

        # Log appropriate message
        if result["success"]:
            logger.info(f"IPFS cluster service is running with {process_count} process(es)")
        else:
            logger.warning("IPFS cluster service is not running")

        return result

    except Exception as e:
        logger.exception(f"Unexpected error in ipfs_cluster_service_status: {str(e)}")
        return handle_error(result, e)
```

#### `ipfs_cluster_follow_status` in `ipfs_cluster_follow.py`

This method checks if the IPFS cluster follow daemon is running by using the `ps` command to look for running processes matching the pattern `ipfs-cluster-follow daemon`.

```python
def ipfs_cluster_follow_status(self, **kwargs):
    """Get the status of the IPFS cluster-follow daemon.

    Args:
        **kwargs: Optional arguments
            - correlation_id: ID for tracking related operations
            - timeout: Command timeout in seconds

    Returns:
        Dictionary with operation result information
    """
    # Create standardized result dictionary
    correlation_id = kwargs.get("correlation_id", getattr(self, "correlation_id", str(uuid.uuid4())))
    result = create_result_dict("ipfs_cluster_follow_status", correlation_id)

    try:
        # Set timeout for commands
        timeout = kwargs.get("timeout", 30)

        # First check if the process is running
        process_check_cmd = ["ps", "-ef"]
        ps_result = self.run_cluster_follow_command(
            process_check_cmd, check=False, timeout=10, correlation_id=correlation_id
        )

        process_running = False
        process_count = 0

        # Process ps output to check for ipfs-cluster-follow processes
        if ps_result.get("success", False) and ps_result.get("stdout"):
            for line in ps_result.get("stdout", "").splitlines():
                if "ipfs-cluster-follow" in line and "daemon" in line and "grep" not in line:
                    process_running = True
                    process_count += 1

        result["process_running"] = process_running
        result["process_count"] = process_count

        # If process is running, try to get detailed status
        if process_running:
            # Use the ipfs-cluster-follow status command
            status_cmd = ["ipfs-cluster-follow", "status"]
            status_result = self.run_cluster_follow_command(
                status_cmd, check=False, timeout=timeout, correlation_id=correlation_id
            )

            if status_result.get("success", False):
                result["detailed_status"] = status_result.get("stdout", "")
                result["success"] = True
            else:
                # If status command fails, at least we know process is running
                result["detailed_status_error"] = status_result.get("stderr", "")
                result["detailed_status_failed"] = True
                result["success"] = (
                    True  # Service is running even if we can't get detailed status
                )
        else:
            # Check socket file to see if it's stale
            socket_path = os.path.expanduser("~/.ipfs-cluster/api-socket")
            result["socket_exists"] = os.path.exists(socket_path)
            result["success"] = False

        # Log appropriate message
        if result["success"]:
            logger.info(f"IPFS cluster-follow is running with {process_count} process(es)")
        else:
            logger.warning("IPFS cluster-follow is not running")

        return result

    except Exception as e:
        logger.exception(f"Unexpected error in ipfs_cluster_follow_status: {str(e)}")
        return handle_error(result, e)
```

### 2. Controller Integration

The `check_daemon_status` method in the IPFS controller was modified to handle special cases for cluster daemons:

```python
# Handle daemon type specific checks
if daemon_type in ["ipfs_cluster_service", "ipfs_cluster_follow"]:
    logger.debug(f"Checking cluster daemon status for type: {daemon_type}")
    try:
        # Import the appropriate module based on daemon type
        if daemon_type == "ipfs_cluster_service":
            from ipfs_kit_py.ipfs_cluster_service import ipfs_cluster_service
            cluster_service = ipfs_cluster_service()
            cluster_result = cluster_service.ipfs_cluster_service_status()
        else:  # ipfs_cluster_follow
            from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow
            cluster_follow = ipfs_cluster_follow()
            cluster_result = cluster_follow.ipfs_cluster_follow_status()
        
        # Create a standardized result
        result = {
            "success": cluster_result.get("success", False),
            "operation": f"check_{daemon_type}_status",
            "operation_id": operation_id,
            "overall_status": "running" if cluster_result.get("process_running", False) else "stopped",
            "daemons": {
                daemon_type: {
                    "running": cluster_result.get("process_running", False),
                    "type": daemon_type,
                    "process_count": cluster_result.get("process_count", 0),
                    "details": cluster_result
                }
            }
        }
    except Exception as cluster_error:
        logger.error(f"Error checking {daemon_type} status: {cluster_error}")
        logger.error(traceback.format_exc())
        result = {
            "success": False,
            "operation": f"check_{daemon_type}_status",
            "operation_id": operation_id,
            "overall_status": "error",
            "error": str(cluster_error),
            "error_type": type(cluster_error).__name__,
            "daemons": {
                daemon_type: {
                    "running": False,
                    "type": daemon_type,
                    "error": str(cluster_error)
                }
            }
        }
else:
    # Standard IPFS daemon check
    result = self.ipfs_model.check_daemon_status(daemon_type)
```

This implementation:
1. Identifies when the daemon_type is either "ipfs_cluster_service" or "ipfs_cluster_follow"
2. Imports the appropriate module dynamically 
3. Calls the appropriate status method
4. Formats the response in a standardized way consistent with the existing API

### 3. API Endpoint

The controller's `check_daemon_status` method is exposed via the FastAPI endpoint:

```python
router.add_api_route(
    "/api/v0/ipfs/daemon/status",
    self.check_daemon_status,
    methods=["POST"],
    response_model=DaemonStatusResponse, 
    summary="Check daemon status",
    description="Check status of IPFS daemons with role-based requirements"
)
```

This endpoint accepts a JSON request body with a `daemon_type` field specifying which daemon to check. For example:

```json
{
  "daemon_type": "ipfs_cluster_service"
}
```

And returns a JSON response with the status information:

```json
{
  "success": true,
  "operation": "check_ipfs_cluster_service_status",
  "operation_id": "1744348255000",
  "overall_status": "running",
  "daemons": {
    "ipfs_cluster_service": {
      "running": true,
      "type": "ipfs_cluster_service",
      "process_count": 1,
      "details": {
        "success": true,
        "process_running": true,
        "process_count": 1,
        "detailed_status": "Cluster pins are in sync with the shared state..."
      }
    }
  }
}
```

## Testing

The implementation is verified with multiple levels of testing:

1. **Direct Module Testing**: Tests the module status methods directly
2. **Controller Integration Testing**: Tests the controller's integration with the modules
3. **API Endpoint Testing**: Tests the complete API endpoint via HTTP requests

The comprehensive test script is located at: `/home/barberb/ipfs_kit_py/test_cluster_status_integrated.py`.

## Error Handling

The implementation includes robust error handling at multiple levels:

1. **Module Level**: Uses the standard `handle_error` function to catch and format errors
2. **Controller Level**: Catches any exceptions from the module calls and formats them in a standardized way
3. **API Level**: Uses FastAPI's exception handling for HTTP-specific errors

## Conclusion

This implementation successfully adds support for checking the status of IPFS cluster daemons within the MCP architecture. It follows the project's established patterns for error handling, request processing, and response formatting, while also providing a clean separation of concerns between modules and the controller.

The functionality has been thoroughly tested at different levels of integration and is ready for use in production environments.