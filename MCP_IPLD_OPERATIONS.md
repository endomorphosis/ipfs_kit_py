# MCP IPLD Operations Implementation

This document provides a summary of the IPLD operations implemented in the MCP (Model-Controller-Persistence) server.

## Overview

IPLD (InterPlanetary Linked Data) is a data model for content-addressed data. The MCP server implements two key IPLD components:

1. **DAG Operations**: Higher-level operations for working with IPLD data structures
2. **Block Operations**: Lower-level operations for working with raw blocks

## DAG Operations

### Model Methods

The following methods have been implemented in `IPFSModel`:

- `dag_put(obj, format="json", pin=True)`: Adds a DAG node to IPFS
  - Parameters:
    - `obj`: Object to add as a DAG node
    - `format`: Format to use (json or cbor)
    - `pin`: Whether to pin the added node
  - Returns: Dictionary with operation result including CID

- `dag_get(cid, path=None)`: Gets a DAG node from IPFS
  - Parameters:
    - `cid`: CID of the DAG node to get
    - `path`: Optional path within the DAG node
  - Returns: Dictionary with operation result including the object

- `dag_resolve(path)`: Resolves a path through the DAG
  - Parameters:
    - `path`: DAG path to resolve
  - Returns: Dictionary with operation result including resolved CID and remainder path

### Controller Endpoints

The following endpoints have been implemented in `IPFSController`:

- `POST /ipfs/dag/put`: Adds a DAG node to IPFS
  - Request body: `DAGPutRequest` with object, format, and pin parameters
  - Response: `DAGPutResponse` with operation result including CID

- `GET /ipfs/dag/get/{cid}`: Gets a DAG node from IPFS
  - Path parameters: `cid` (CID of the DAG node)
  - Query parameters: `path` (Optional path within the DAG node)
  - Response: `DAGGetResponse` with operation result including the object

- `GET /ipfs/dag/resolve/{path:path}`: Resolves a path through the DAG
  - Path parameters: `path` (DAG path to resolve)
  - Response: `DAGResolveResponse` with operation result including resolved CID and remainder path

## Block Operations

### Model Methods

The following methods have been implemented in `IPFSModel`:

- `block_put(data, format="dag-pb")`: Adds a raw block to IPFS
  - Parameters:
    - `data`: Raw block data to add
    - `format`: Format to use (dag-pb, raw, etc.)
  - Returns: Dictionary with operation result including CID

- `block_get(cid)`: Gets a raw block from IPFS
  - Parameters:
    - `cid`: CID of the block to get
  - Returns: Dictionary with operation result including the block data

- `block_stat(cid)`: Gets stats about a block
  - Parameters:
    - `cid`: CID of the block
  - Returns: Dictionary with operation result including block stats

### Controller Endpoints

The following endpoints have been implemented in `IPFSController`:

- `POST /ipfs/block/put`: Adds a raw block to IPFS
  - Request body: `BlockPutRequest` with data (base64 encoded) and format parameters
  - Response: `BlockPutResponse` with operation result including CID

- `GET /ipfs/block/get/{cid}`: Gets a raw block from IPFS
  - Path parameters: `cid` (CID of the block)
  - Response: Raw block data as a `Response`

- `GET /ipfs/block/stat/{cid}`: Gets stats about a block
  - Path parameters: `cid` (CID of the block)
  - Response: `BlockStatResponse` with operation result including block stats

## Testing

Comprehensive tests have been implemented for both DAG and Block operations:

1. **DAG Operations**:
   - `test_mcp_dag_operations.py`: Tests for dag_put, dag_get, and dag_resolve

2. **Block Operations**:
   - `test_mcp_block_operations.py`: Tests for block_put, block_get, and block_stat

The tests cover success cases, parameter variations, and error handling for each operation.

## Usage Examples

### DAG Operations

```python
# Adding a DAG node
node = {
    "name": "test-node",
    "values": [1, 2, 3],
    "links": [
        {"name": "child1", "cid": "QmChildCid1"},
        {"name": "child2", "cid": "QmChildCid2"}
    ]
}
result = ipfs_model.dag_put(node)
cid = result["cid"]

# Getting a DAG node
result = ipfs_model.dag_get(cid)
node = result["object"]

# Resolving a path
result = ipfs_model.dag_resolve(f"{cid}/links/0/cid")
child_cid = result["cid"]
```

### Block Operations

```python
# Adding a block
import os
data = os.urandom(1024)  # Random 1KB block
result = ipfs_model.block_put(data, format="raw")
cid = result["cid"]

# Getting a block
result = ipfs_model.block_get(cid)
data = result["data"]

# Getting block stats
result = ipfs_model.block_stat(cid)
size = result["size"]
```

## API Responses

All API responses follow a standardized format with the following fields:

- `success`: Boolean indicating success or failure
- `operation_id`: Unique identifier for the operation
- `duration_ms`: Duration of the operation in milliseconds
- `operation`: Name of the operation
- `timestamp`: Timestamp of the operation
- Additional operation-specific fields

## Implementation Notes

- Both DAG and Block operations handle bytes and dictionary responses from the underlying IPFS implementation
- Error handling is standardized across all operations
- Statistics are collected for monitoring and debugging
- The implementation supports both JSON and CBOR formats for DAG operations
- Block operations support various formats including dag-pb and raw