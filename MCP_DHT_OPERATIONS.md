# MCP DHT Operations

This document describes the DHT (Distributed Hash Table) operations implemented in the MCP (Model-Controller-Persistence) server.

## Overview

The DHT is a core component of IPFS, used for content routing and peer discovery. It allows nodes to find content and other peers in the IPFS network in a decentralized way. The MCP server implements two primary DHT operations:

1. `dht_findpeer`: Find information about a peer by its peer ID
2. `dht_findprovs`: Find providers (peers that have a specific piece of content) for a content ID (CID)

## API Endpoints

### DHT FindPeer

#### Endpoint: `/ipfs/dht/findpeer`
- **Method**: POST
- **Description**: Find information about a peer using the DHT
- **Request Body**:
  ```json
  {
    "peer_id": "QmPeerID"
  }
  ```
- **Response Body**:
  ```json
  {
    "success": true,
    "operation": "dht_findpeer",
    "operation_id": "dht_findpeer_1234567890",
    "timestamp": 1234567890.123,
    "peer_id": "QmPeerID",
    "responses": [
      {
        "id": "QmFoundPeerID",
        "addrs": [
          "/ip4/127.0.0.1/tcp/4001",
          "/ip6/::1/tcp/4001"
        ]
      }
    ],
    "peers_found": 1,
    "duration_ms": 123.45
  }
  ```

### DHT FindProvs

#### Endpoint: `/ipfs/dht/findprovs`
- **Method**: POST
- **Description**: Find providers for a CID using the DHT
- **Request Body**:
  ```json
  {
    "cid": "QmContentID",
    "num_providers": 5  // Optional
  }
  ```
- **Response Body**:
  ```json
  {
    "success": true,
    "operation": "dht_findprovs",
    "operation_id": "dht_findprovs_1234567890",
    "timestamp": 1234567890.123,
    "cid": "QmContentID",
    "providers": [
      {
        "id": "QmProvider1",
        "addrs": [
          "/ip4/192.168.1.1/tcp/4001",
          "/ip6/2001:db8::1/tcp/4001"
        ]
      },
      {
        "id": "QmProvider2",
        "addrs": [
          "/ip4/192.168.1.2/tcp/4001"
        ]
      }
    ],
    "count": 2,
    "num_providers": 5,
    "duration_ms": 123.45
  }
  ```

## Implementation Details

### Model Layer

The DHT operations are implemented in the IPFS model (`ipfs_model.py`):

- `dht_findpeer`: Calls the IPFS kit's `dht_findpeer` method and formats the response
- `dht_findprovs`: Calls the IPFS kit's `dht_findprovs` method and formats the response

The model methods handle error cases and ensure consistent response formats.

### Controller Layer

The controller (`ipfs_controller.py`) implements API endpoints that call the model methods:

- `dht_findpeer`: Handles the HTTP request, calls the model method, and returns the response
- `dht_findprovs`: Handles the HTTP request, calls the model method, and returns the response

Both methods include proper error handling and logging.

### Request/Response Models

The controller uses Pydantic models for request and response validation:

- `DHTFindPeerRequest`: Contains the peer ID to find
- `DHTFindPeerResponse`: Contains the result of the findpeer operation
- `DHTFindProvsRequest`: Contains the CID to find providers for and an optional num_providers parameter
- `DHTFindProvsResponse`: Contains the result of the findprovs operation

## Error Handling

Both DHT operations use a standardized error handling approach:

1. Exceptions are caught in the model layer
2. Error messages are returned in a standardized format with `success: false`
3. Errors are logged for troubleshooting
4. The controller layer ensures a consistent response format even in error cases

## Testing

The DHT operations are tested in `test_mcp_dht_operations.py`, which includes tests for:

1. Successful findpeer and findprovs operations
2. Empty responses (no peers/providers found)
3. Error cases
4. Parameter variations (e.g., finding providers with num_providers parameter)

The tests use mock objects to simulate the IPFS kit's behavior without requiring an actual IPFS daemon.