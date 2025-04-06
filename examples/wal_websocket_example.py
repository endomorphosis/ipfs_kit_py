#!/usr/bin/env python
# examples/wal_websocket_example.py

"""
Example demonstrating the WebSocket interface for real-time WAL monitoring.

This example shows how to use the WebSocket interface to:
1. Connect to the WAL WebSocket API
2. Subscribe to operation updates
3. Subscribe to backend health updates
4. Subscribe to metrics updates
5. Get operation details
6. Process real-time updates

The WebSocket interface provides a more efficient way to monitor WAL operations
compared to polling the REST API, especially for long-running operations.
"""

import asyncio
import json
import logging
import sys
import time
import argparse
from pathlib import Path

# Add parent directory to path to allow importing from ipfs_kit_py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import websockets
except ImportError:
    print("This example requires the websockets package. Install with:")
    print("pip install websockets")
    sys.exit(1)

try:
    from ipfs_kit_py import IPFSSimpleAPI
    from ipfs_kit_py.storage_wal import OperationType, BackendType
except ImportError:
    print("Failed to import ipfs_kit_py. Make sure it's installed or in your PYTHONPATH.")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("wal_websocket_example")

# Variables to track example state
connected = False
subscriptions = {}
operation_ids = []

async def connect_to_websocket(url):
    """Connect to the WAL WebSocket API."""
    global connected
    
    try:
        logger.info(f"Connecting to {url}...")
        websocket = await websockets.connect(url)
        connected = True
        
        # Get welcome message
        welcome = await websocket.recv()
        welcome_data = json.loads(welcome)
        logger.info(f"Connected: {welcome_data.get('message')}")
        
        return websocket
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        connected = False
        return None

async def subscribe(websocket, subscription_type, parameters=None):
    """Subscribe to updates from the WAL WebSocket API."""
    global subscriptions
    
    if not connected:
        logger.error("Not connected to WebSocket")
        return None
    
    if parameters is None:
        parameters = {}
    
    message = {
        "action": "subscribe",
        "subscription_type": subscription_type,
        "parameters": parameters
    }
    
    logger.info(f"Subscribing to {subscription_type} with parameters {parameters}")
    await websocket.send(json.dumps(message))
    
    # Wait for confirmation
    response = await websocket.recv()
    response_data = json.loads(response)
    
    if response_data.get("type") == "subscription_created":
        subscription_id = response_data.get("subscription_id")
        logger.info(f"Subscription created: {subscription_id}")
        subscriptions[subscription_id] = {
            "type": subscription_type,
            "parameters": parameters
        }
        return subscription_id
    elif response_data.get("type") == "error":
        logger.error(f"Subscription failed: {response_data.get('message')}")
        return None
    else:
        logger.warning(f"Unexpected response: {response_data}")
        return None

async def process_messages(websocket):
    """Process messages from the WebSocket."""
    try:
        while connected:
            message = await websocket.recv()
            message_data = json.loads(message)
            
            message_type = message_data.get("type")
            timestamp = message_data.get("timestamp", time.time())
            formatted_time = time.strftime('%H:%M:%S', time.localtime(timestamp))
            
            if message_type == "operation_update":
                operation = message_data.get("operation", {})
                op_id = operation.get("operation_id", "unknown")
                op_status = operation.get("status", "unknown")
                op_type = operation.get("operation_type", "unknown")
                op_backend = operation.get("backend", "unknown")
                
                logger.info(f"[{formatted_time}] Operation update: {op_id} ({op_status}) - {op_type} on {op_backend}")
                
            elif message_type == "health_update":
                health_data = message_data.get("health_data", {})
                logger.info(f"[{formatted_time}] Backend health update:")
                for backend, status in health_data.items():
                    backend_status = status.get("status", "unknown")
                    logger.info(f"  {backend}: {backend_status}")
                    
            elif message_type == "metrics_update":
                metrics = message_data.get("metrics_data", {})
                pending = metrics.get("pending", 0)
                completed = metrics.get("completed", 0)
                failed = metrics.get("failed", 0)
                total = metrics.get("total_operations", 0)
                
                logger.info(f"[{formatted_time}] Metrics update: {pending} pending, {completed} completed, {failed} failed, {total} total")
                
            elif message_type == "operations_list":
                operations = message_data.get("operations", [])
                logger.info(f"[{formatted_time}] Received operations list with {len(operations)} operations")
                
            elif message_type == "error":
                logger.error(f"[{formatted_time}] Error: {message_data.get('message')}")
                
            else:
                logger.debug(f"[{formatted_time}] Received message of type {message_type}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket connection closed")
        global connected
        connected = False
    except Exception as e:
        logger.error(f"Error processing messages: {e}")

async def create_test_operations(api, count=3):
    """Create test operations to monitor."""
    global operation_ids
    
    logger.info(f"Creating {count} test operations...")
    
    for i in range(count):
        # Create a test file
        test_file = f"/tmp/test_file_{i}.txt"
        with open(test_file, "w") as f:
            f.write(f"This is test file {i} for WAL WebSocket example.")
        
        # Add file to IPFS through WAL
        result = api.add(test_file)
        if "operation_id" in result:
            operation_ids.append(result["operation_id"])
            logger.info(f"Created operation {result['operation_id']}")
        else:
            logger.warning(f"Failed to create operation: {result}")
    
    return operation_ids

async def get_operation_details(websocket, operation_id):
    """Get details for a specific operation."""
    if not connected:
        logger.error("Not connected to WebSocket")
        return None
    
    message = {
        "action": "get_operation",
        "operation_id": operation_id
    }
    
    logger.info(f"Getting details for operation {operation_id}")
    await websocket.send(json.dumps(message))
    
    # Wait for response
    response = await websocket.recv()
    response_data = json.loads(response)
    
    if response_data.get("type") == "operation_data":
        operation = response_data.get("operation", {})
        logger.info(f"Operation details: {json.dumps(operation, indent=2)}")
        return operation
    elif response_data.get("type") == "error":
        logger.error(f"Failed to get operation details: {response_data.get('message')}")
        return None
    else:
        logger.warning(f"Unexpected response: {response_data}")
        return None

async def get_health(websocket, backend=None):
    """Get health status for backends."""
    if not connected:
        logger.error("Not connected to WebSocket")
        return None
    
    message = {
        "action": "get_health",
        "backend": backend
    }
    
    logger.info(f"Getting health status" + (f" for {backend}" if backend else ""))
    await websocket.send(json.dumps(message))
    
    # Wait for response
    response = await websocket.recv()
    response_data = json.loads(response)
    
    if response_data.get("type") == "health_data":
        health_data = response_data.get("health_data", {})
        logger.info(f"Health data: {json.dumps(health_data, indent=2)}")
        return health_data
    elif response_data.get("type") == "error":
        logger.error(f"Failed to get health data: {response_data.get('message')}")
        return None
    else:
        logger.warning(f"Unexpected response: {response_data}")
        return None

async def get_metrics(websocket):
    """Get metrics data."""
    if not connected:
        logger.error("Not connected to WebSocket")
        return None
    
    message = {
        "action": "get_metrics"
    }
    
    logger.info("Getting metrics data")
    await websocket.send(json.dumps(message))
    
    # Wait for response
    response = await websocket.recv()
    response_data = json.loads(response)
    
    if response_data.get("type") == "metrics_data":
        metrics_data = response_data.get("metrics_data", {})
        logger.info(f"Metrics data: {json.dumps(metrics_data, indent=2)}")
        return metrics_data
    elif response_data.get("type") == "error":
        logger.error(f"Failed to get metrics data: {response_data.get('message')}")
        return None
    else:
        logger.warning(f"Unexpected response: {response_data}")
        return None

async def unsubscribe(websocket, subscription_id):
    """Unsubscribe from updates."""
    global subscriptions
    
    if not connected:
        logger.error("Not connected to WebSocket")
        return False
    
    message = {
        "action": "unsubscribe",
        "subscription_id": subscription_id
    }
    
    logger.info(f"Unsubscribing from {subscription_id}")
    await websocket.send(json.dumps(message))
    
    # Wait for response
    response = await websocket.recv()
    response_data = json.loads(response)
    
    if response_data.get("type") == "unsubscribe_result":
        success = response_data.get("success", False)
        if success:
            logger.info(f"Successfully unsubscribed from {subscription_id}")
            if subscription_id in subscriptions:
                del subscriptions[subscription_id]
        else:
            logger.error(f"Failed to unsubscribe from {subscription_id}")
        return success
    elif response_data.get("type") == "error":
        logger.error(f"Unsubscribe error: {response_data.get('message')}")
        return False
    else:
        logger.warning(f"Unexpected response: {response_data}")
        return False

async def run_example(host="localhost", port=8000, duration=60):
    """Run the WebSocket example."""
    # Initialize API with WAL enabled
    api = IPFSSimpleAPI(enable_wal=True)
    
    # Create WebSocket URL
    ws_url = f"ws://{host}:{port}/api/v0/wal/ws"
    
    # Connect to WebSocket
    websocket = await connect_to_websocket(ws_url)
    if not websocket:
        logger.error("Failed to connect to WebSocket")
        return
    
    try:
        # Start message processing in background
        message_task = asyncio.create_task(process_messages(websocket))
        
        # Create test operations
        await create_test_operations(api, count=3)
        
        # Subscribe to different types of updates
        await subscribe(websocket, "all_operations")
        await subscribe(websocket, "backend_health")
        await subscribe(websocket, "metrics")
        
        # If we have operation IDs, subscribe to a specific operation
        if operation_ids:
            await subscribe(websocket, "specific_operation", {
                "operation_id": operation_ids[0]
            })
        
        # Get operation details for first operation
        if operation_ids:
            await get_operation_details(websocket, operation_ids[0])
        
        # Get health status
        await get_health(websocket)
        
        # Get metrics
        await get_metrics(websocket)
        
        # Keep the example running for the specified duration
        logger.info(f"Example running for {duration} seconds. Press Ctrl+C to exit...")
        end_time = time.time() + duration
        
        while time.time() < end_time and connected:
            await asyncio.sleep(1)
        
        # Clean up subscriptions
        for subscription_id in list(subscriptions.keys()):
            await unsubscribe(websocket, subscription_id)
        
        # Cancel message processing task
        message_task.cancel()
        try:
            await message_task
        except asyncio.CancelledError:
            pass
        
    except KeyboardInterrupt:
        logger.info("Example interrupted by user")
    except Exception as e:
        logger.error(f"Example error: {e}")
    finally:
        # Close WebSocket connection
        if websocket and connected:
            await websocket.close()
            connected = False
        
        logger.info("Example completed")

def main():
    """Parse arguments and run the example."""
    parser = argparse.ArgumentParser(description="Example of WebSocket interface for WAL monitoring")
    parser.add_argument("--host", default="localhost", help="API server host")
    parser.add_argument("--port", type=int, default=8000, help="API server port")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds to run the example")
    
    args = parser.parse_args()
    
    asyncio.run(run_example(args.host, args.port, args.duration))

if __name__ == "__main__":
    main()