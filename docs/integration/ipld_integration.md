# IPLD Integration

This document provides a comprehensive guide to the IPLD (InterPlanetary Linked Data) integration in IPFS Kit.

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Python IPLD Libraries](#python-ipld-libraries)
  - [py-ipld-car](#py-ipld-car)
  - [py-ipld-dag-pb](#py-ipld-dag-pb)
  - [py-ipld-unixfs](#py-ipld-unixfs)
- [IPLD Components](#ipld-components)
  - [CAR (Content Addressable aRchive)](#car-content-addressable-archive)
  - [DAG-PB (Directed Acyclic Graph - ProtoBuf)](#dag-pb-directed-acyclic-graph---protobuf)
  - [UnixFS](#unixfs)
- [Using IPLD with IPFS Kit](#using-ipld-with-ipfs-kit)
  - [Initialization](#initialization)
  - [Working with CAR Files](#working-with-car-files)
  - [Working with DAG-PB Nodes](#working-with-dag-pb-nodes)
  - [Working with UnixFS](#working-with-unixfs)
- [API Reference](#api-reference)
- [Error Handling](#error-handling)
- [Advanced Usage](#advanced-usage)
- [Examples](#examples)

## Overview

IPLD, or InterPlanetary Linked Data, is the data model of IPFS. It defines how to represent and link data structures in content-addressed systems. IPLD provides the foundation for working with IPFS data at a lower level than standard file operations.

The IPLD integration in IPFS Kit provides access to three key components:

1. **CAR (Content Addressable aRchive)** - A file format for storing IPLD blocks and their links in a single file
2. **DAG-PB (Directed Acyclic Graph - ProtoBuf)** - The default format for representing DAGs in IPFS
3. **UnixFS** - A format for representing files and directories in IPFS

IPFS Kit includes full Python implementations of these IPLD components through the py-ipld-car, py-ipld-dag-pb, and py-ipld-unixfs libraries, enabling low-level operations with IPFS data structures directly in Python.

## Python IPLD Libraries

### py-ipld-car

A Python implementation of the Content Addressable aRchive (CAR) format specification. This library enables reading and writing CAR files, which are containers for IPLD blocks and their links.

Key features:
- Encode IPLD blocks and root CIDs into CAR files
- Decode CAR files to extract roots and blocks
- Validate CAR file format

### py-ipld-dag-pb

A Python implementation of the DAG-PB (Directed Acyclic Graph - ProtoBuf) specification. DAG-PB is the default format for representing linked data in IPFS.

Key features:
- Create and manipulate DAG-PB nodes
- Encode and decode DAG-PB nodes
- Work with links between nodes
- Data model preparation utilities

### py-ipld-unixfs

A Python implementation of the UnixFS specification, which provides a file and directory format on top of IPLD for IPFS.

Key features:
- File chunking algorithms (fixed-size, rabin)
- Incremental and resumable writes
- Memory-efficient processing
- Direct control over chunking strategies

## Installation

To use the IPLD functionality in IPFS Kit, you need to install the optional IPLD dependencies:

```bash
pip install ipfs_kit_py[ipld]
```

This will install the following packages:
- `py-ipld-car` - For working with CAR files
- `py-ipld-dag-pb` - For working with DAG-PB nodes
- `py-ipld-unixfs` - For working with UnixFS data

## IPLD Components

### CAR (Content Addressable aRchive)

CAR files are a format for storing and transferring IPLD data. They contain a collection of blocks (chunks of content) alongside their content identifiers (CIDs), creating a self-contained package of content-addressed data.

Key operations:
- Create CAR files from blocks and root CIDs
- Extract blocks and roots from CAR files
- Add CAR files to IPFS

### DAG-PB (Directed Acyclic Graph - ProtoBuf)

DAG-PB is the default format for representing DAGs in IPFS. It's a Protocol Buffers-based serialization format that allows for compact representation of linked data structures.

Key operations:
- Create DAG-PB nodes
- Link nodes together to form DAGs
- Serialize and deserialize DAG-PB nodes

### UnixFS

UnixFS is a format built on top of IPLD that represents files and directories in a way similar to Unix filesystems. It provides familiar file operations for content-addressed data.

Key operations:
- Chunk files into blocks for efficient storage and transfer
- Assemble files from blocks
- Navigate directory structures

## Using IPLD with IPFS Kit

### Initialization

The IPLD functionality is implemented as an extension to the main `ipfs_kit` class. To use it, you need to enable it during initialization:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize with IPLD extension enabled
kit = ipfs_kit(metadata={"enable_ipld": True})

# Check if IPLD components are available
print("CAR functionality available:", kit.ipld_extension.car_handler.available)
print("DAG-PB functionality available:", kit.ipld_extension.dag_pb_handler.available)
print("UnixFS functionality available:", kit.ipld_extension.unixfs_handler.available)
```

### Working with CAR Files

CAR files allow you to package and transfer IPLD data in a self-contained format.

```python
# Create a CAR file from content
result = kit.create_car(
    roots=["QmXg9Pp2ytZ14xgmQjYEiHjVjMFXzCVVEcRTWJBmLgR39V"], 
    output_path="example.car"
)

# Extract a CAR file
extract_result = kit.extract_car("example.car", output_dir="/tmp/extracted")

# Add a CAR file to IPFS
import_result = kit.add_car_to_ipfs("example.car")
```

### Working with DAG-PB Nodes

DAG-PB nodes are the building blocks of IPLD graphs in IPFS.

```python
# Create a DAG-PB node with links
node_result = kit.create_dag_node(
    data=b"Hello, IPLD!",
    links=[
        {
            "Name": "child", 
            "Hash": "QmChildCID", 
            "Tsize": 123
        }
    ]
)

# The result contains the serialized node and its CID
node_cid = node_result["cid"]
node_data = node_result["node_bytes"]
```

### Working with UnixFS

UnixFS provides file and directory abstractions over IPLD data.

```python
# Chunk a file using UnixFS chunker
chunk_result = kit.chunk_file(
    file_path="large_file.dat",
    strategy="size-1048576",  # 1MB chunks
    output_dir="/tmp/chunks"
)

# The result contains the root CID and chunking info
root_cid = chunk_result["root_cid"]
chunks = chunk_result["chunks"]
```

## API Reference

### CAR Operations

#### `create_car(roots, blocks=None, output_path=None)`

Creates a CAR file from the specified roots and optional blocks.

Parameters:
- `roots`: List of CIDs for the root blocks
- `blocks`: Optional dict mapping CIDs to block data
- `output_path`: Path to save the CAR file

Returns:
- Dictionary with operation results including `success`, `car_file_path`, and `size`

#### `extract_car(car_path, output_dir=None)`

Extracts the contents of a CAR file.

Parameters:
- `car_path`: Path to the CAR file
- `output_dir`: Directory to extract blocks to

Returns:
- Dictionary with operation results including `success`, `roots`, `blocks_count`

#### `add_car_to_ipfs(car_path)`

Imports a CAR file into IPFS.

Parameters:
- `car_path`: Path to the CAR file

Returns:
- Dictionary with operation results including `success`, `root_cid`, `imported_blocks`

### DAG-PB Operations

#### `create_dag_node(data=None, links=None)`

Creates a DAG-PB node with the specified data and links.

Parameters:
- `data`: Binary data to store in the node
- `links`: List of links to other nodes in the format `[{"Name": name, "Hash": cid, "Tsize": size}, ...]`

Returns:
- Dictionary with operation results including `success`, `cid`, `node_bytes`

### UnixFS Operations

#### `chunk_file(file_path, strategy="size-262144", output_dir=None)`

Chunks a file using UnixFS chunking strategies.

Parameters:
- `file_path`: Path to the file to chunk
- `strategy`: Chunking strategy, one of:
  - `size-N`: Fixed-size chunking with chunks of N bytes
  - `rabin`: Rabin fingerprint chunking
- `output_dir`: Directory to save chunk files to

Returns:
- Dictionary with operation results including `success`, `root_cid`, `chunks`

## Error Handling

All IPLD operations follow the standard IPFS Kit error handling pattern, returning a result dictionary with:

- `success`: Boolean indicating operation success
- `operation`: The name of the operation
- `timestamp`: When the operation was performed
- `error`: Error message if operation failed
- `error_type`: Type of error encountered

Example error handling:

```python
result = kit.create_car(roots=["QmInvalidCID"], output_path="example.car")
if not result["success"]:
    print(f"Operation failed: {result['error']}")
    print(f"Error type: {result['error_type']}")
```

## Advanced Usage

### Combining IPLD Operations

You can combine IPLD operations to build more complex workflows:

```python
# Create a series of DAG-PB nodes and link them together
node1_result = kit.create_dag_node(data=b"Node 1 data")
node1_cid = node1_result["cid"]

node2_result = kit.create_dag_node(data=b"Node 2 data")
node2_cid = node2_result["cid"]

# Create a parent node that links to both children
parent_node_result = kit.create_dag_node(
    data=b"Parent node data",
    links=[
        {"Name": "child1", "Hash": node1_cid, "Tsize": len(node1_result["node_bytes"])},
        {"Name": "child2", "Hash": node2_cid, "Tsize": len(node2_result["node_bytes"])}
    ]
)
parent_cid = parent_node_result["cid"]

# Export the entire DAG to a CAR file
car_result = kit.create_car(
    roots=[parent_cid],
    output_path="dag_export.car"
)

# Import to another IPFS node
import_result = kit.add_car_to_ipfs("dag_export.car")
```

### Integration with Other Features

IPLD can be integrated with other IPFS Kit features:

```python
# Create a knowledge graph using IPLD
from ipfs_kit_py.ipld_knowledge_graph import IPLDKnowledgeGraph

# Initialize graph with IPFS Kit
graph = IPLDKnowledgeGraph(kit)

# Add entities and relationships
entity1_id = graph.add_entity("entity1", {"name": "Entity 1", "type": "Person"})
entity2_id = graph.add_entity("entity2", {"name": "Entity 2", "type": "Document"})

# Create relationship
rel_id = graph.add_relationship(entity1_id, entity2_id, "AUTHORED")

# Export graph to CAR file
export_result = graph.export_to_car("knowledge_graph.car")
```

## Examples

### Example 1: Creating and Using a CAR File

This example demonstrates creating a CAR file from existing IPFS content and then importing it into another node:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize source node with IPLD
source_kit = ipfs_kit(metadata={"enable_ipld": True})

# Add some content to IPFS
content_result = source_kit.ipfs_add("Hello, IPFS and IPLD!")
content_cid = content_result["Hash"]

# Create a CAR file with this content
car_result = source_kit.create_car(
    roots=[content_cid],
    output_path="transfer.car"
)

if car_result["success"]:
    print(f"Created CAR file: {car_result['car_file_path']}")
    print(f"CAR file size: {car_result['size']} bytes")

    # Initialize destination node with IPLD
    dest_kit = ipfs_kit(metadata={"enable_ipld": True})
    
    # Import the CAR file
    import_result = dest_kit.add_car_to_ipfs("transfer.car")
    
    if import_result["success"]:
        print(f"Successfully imported CAR file")
        print(f"Root CID: {import_result['root_cid']}")
        print(f"Imported {import_result['imported_blocks']} blocks")
        
        # Verify content can be retrieved
        get_result = dest_kit.ipfs_cat(content_cid)
        if get_result["success"]:
            print(f"Retrieved content: {get_result['data']}")
else:
    print(f"Failed to create CAR file: {car_result['error']}")
```

### Example 2: Building a Custom DAG Structure

This example shows how to build a custom DAG structure using DAG-PB nodes:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize IPFS Kit with IPLD
kit = ipfs_kit(metadata={"enable_ipld": True})

# Create leaf nodes
leaf1_result = kit.create_dag_node(data=b"Leaf node 1 data")
leaf1_cid = leaf1_result["cid"]

leaf2_result = kit.create_dag_node(data=b"Leaf node 2 data")
leaf2_cid = leaf2_result["cid"]

leaf3_result = kit.create_dag_node(data=b"Leaf node 3 data")
leaf3_cid = leaf3_result["cid"]

# Create intermediate nodes linking to leaves
branch1_result = kit.create_dag_node(
    data=b"Branch 1 data",
    links=[
        {"Name": "leaf1", "Hash": leaf1_cid, "Tsize": len(leaf1_result["node_bytes"])},
        {"Name": "leaf2", "Hash": leaf2_cid, "Tsize": len(leaf2_result["node_bytes"])}
    ]
)
branch1_cid = branch1_result["cid"]

# Create root node linking to branch and remaining leaf
root_result = kit.create_dag_node(
    data=b"Root node data",
    links=[
        {"Name": "branch1", "Hash": branch1_cid, "Tsize": len(branch1_result["node_bytes"])},
        {"Name": "leaf3", "Hash": leaf3_cid, "Tsize": len(leaf3_result["node_bytes"])}
    ]
)
root_cid = root_result["cid"]

print(f"Created DAG with root CID: {root_cid}")

# Export the entire DAG to a CAR file
car_result = kit.create_car(
    roots=[root_cid],
    output_path="custom_dag.car"
)

if car_result["success"]:
    print(f"Exported DAG to CAR file: {car_result['car_file_path']}")
```

### Example 3: Chunking a Large File with UnixFS

This example demonstrates how to chunk a large file using UnixFS:

```python
import os
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize IPFS Kit with IPLD
kit = ipfs_kit(metadata={"enable_ipld": True})

# Create a test file (100MB of random data)
test_file = "/tmp/large_test_file.bin"
with open(test_file, "wb") as f:
    f.write(os.urandom(100 * 1024 * 1024))

# Chunk the file using fixed-size chunking (1MB chunks)
chunk_result = kit.chunk_file(
    file_path=test_file,
    strategy="size-1048576",  # 1MB chunks
    output_dir="/tmp/chunks"
)

if chunk_result["success"]:
    print(f"Successfully chunked file")
    print(f"Root CID: {chunk_result['root_cid']}")
    print(f"Number of chunks: {len(chunk_result['chunks'])}")
    print(f"Average chunk size: {sum(c['size'] for c in chunk_result['chunks']) / len(chunk_result['chunks'])} bytes")
    
    # Add the chunked file to IPFS
    add_result = kit.ipfs_add(test_file)
    
    if add_result["success"]:
        print(f"Added file to IPFS with CID: {add_result['Hash']}")
        print(f"Verify the CIDs match: {add_result['Hash'] == chunk_result['root_cid']}")
else:
    print(f"Failed to chunk file: {chunk_result['error']}")
```

These examples demonstrate the key functionality of the IPLD integration in IPFS Kit. By combining these operations, you can build powerful applications that leverage the full capabilities of IPFS's content-addressed data model.