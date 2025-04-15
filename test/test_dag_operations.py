#!/usr/bin/env python3
"""
Test and demonstrate the enhanced DAG operations for IPFS Kit.

This script tests the new DAG operations functionality, including
node creation, retrieval, linking, and tree manipulation. It serves as
both a validation tool and a practical example of how to use the module.
"""

import argparse
import io
import json
import logging
import os
import sys
import tempfile
import time
import uuid
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_dag_operations")

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our modules
from ipfs_connection_pool import IPFSConnectionConfig, get_connection_pool
from ipfs_dag_operations import DAGOperations, IPLDFormat

def pretty_print(data: Any) -> None:
    """Print formatted JSON data."""
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(data)

def test_basic_operations(api_url: str = "http://127.0.0.1:5001/api/v0") -> None:
    """Test basic DAG operations."""
    logger.info("=== Testing Basic DAG Operations ===")
    logger.info(f"Using API URL: {api_url}")
    
    # Initialize connection and DAG operations
    config = IPFSConnectionConfig(base_url=api_url)
    pool = get_connection_pool(config)
    dag_ops = DAGOperations(pool)
    
    # Create a test object
    test_object = {
        "name": "Test Object",
        "created": time.time(),
        "id": uuid.uuid4().hex,
        "data": {
            "value": 42,
            "nested": {
                "array": [1, 2, 3, 4, 5],
                "boolean": True,
                "null": None
            }
        }
    }
    
    # Store the object in DAG
    logger.info("Storing test object in DAG...")
    put_result = dag_ops.put(
        data=test_object,
        format_type=IPLDFormat.DAG_JSON,
        pin=True
    )
    
    if put_result["success"]:
        cid = put_result["cid"]
        logger.info(f"Successfully stored object with CID: {cid}")
    else:
        logger.error(f"Failed to store object: {put_result['error']}")
        return
    
    # Retrieve the object
    logger.info(f"Retrieving object with CID: {cid}")
    get_result = dag_ops.get(cid)
    
    if get_result["success"]:
        retrieved_object = get_result["data"]
        logger.info("Successfully retrieved object:")
        pretty_print(retrieved_object)
        
        # Verify object data
        if retrieved_object["name"] == test_object["name"] and retrieved_object["id"] == test_object["id"]:
            logger.info("✓ Object verification passed")
        else:
            logger.error("✗ Object verification failed - data mismatch")
    else:
        logger.error(f"Failed to retrieve object: {get_result['error']}")
    
    # Resolve a path within the object
    logger.info(f"Resolving path within object: {cid}/data/nested/array")
    resolve_result = dag_ops.resolve(f"{cid}/data/nested/array")
    
    if resolve_result["success"]:
        logger.info(f"Successfully resolved path: {resolve_result['resolved_path']}")
        
        # Get the array using the path
        array_result = dag_ops.get(cid, path="/data/nested/array")
        
        if array_result["success"]:
            array_data = array_result["data"]
            logger.info(f"Retrieved array data: {array_data}")
            
            # Verify array data
            if array_data == test_object["data"]["nested"]["array"]:
                logger.info("✓ Array verification passed")
            else:
                logger.error("✗ Array verification failed - data mismatch")
        else:
            logger.error(f"Failed to retrieve array: {array_result['error']}")
    else:
        logger.error(f"Failed to resolve path: {resolve_result['error']}")
    
    # Get stats for the object
    logger.info(f"Getting stats for object: {cid}")
    stat_result = dag_ops.stat(cid)
    
    if stat_result["success"]:
        logger.info(f"Object size: {stat_result['size']} bytes")
        logger.info(f"Number of blocks: {stat_result['num_blocks']}")
    else:
        logger.error(f"Failed to get stats: {stat_result['error']}")
    
    # Export the object
    logger.info(f"Exporting object: {cid}")
    with tempfile.NamedTemporaryFile(suffix=".car", delete=False) as temp_file:
        export_file = temp_file.name
    
    export_result = dag_ops.export_data(cid, output_file=export_file)
    
    if export_result["success"]:
        logger.info(f"Successfully exported object to: {export_file}")
        
        # Check file size
        export_size = os.path.getsize(export_file)
        logger.info(f"Export file size: {export_size} bytes")
    else:
        logger.error(f"Failed to export object: {export_result['error']}")
    
    # Clean up the temporary file
    try:
        os.unlink(export_file)
    except:
        pass
    
    logger.info("Basic DAG operations test completed")

def test_link_operations(api_url: str = "http://127.0.0.1:5001/api/v0") -> None:
    """Test DAG link operations."""
    logger.info("=== Testing DAG Link Operations ===")
    logger.info(f"Using API URL: {api_url}")
    
    # Initialize connection and DAG operations
    config = IPFSConnectionConfig(base_url=api_url)
    pool = get_connection_pool(config)
    dag_ops = DAGOperations(pool)
    
    # Create a child object
    child_object = {
        "name": "Child Object",
        "created": time.time(),
        "data": [1, 2, 3, 4, 5]
    }
    
    # Store the child object
    logger.info("Storing child object...")
    child_result = dag_ops.put(child_object)
    
    if not child_result["success"]:
        logger.error(f"Failed to store child object: {child_result['error']}")
        return
    
    child_cid = child_result["cid"]
    logger.info(f"Child object CID: {child_cid}")
    
    # Create a parent object
    parent_object = {
        "name": "Parent Object",
        "created": time.time(),
        "children": {}  # Will add link later
    }
    
    # Store the parent object
    logger.info("Storing parent object...")
    parent_result = dag_ops.put(parent_object)
    
    if not parent_result["success"]:
        logger.error(f"Failed to store parent object: {parent_result['error']}")
        return
    
    parent_cid = parent_result["cid"]
    logger.info(f"Parent object CID: {parent_cid}")
    
    # Add a link from parent to child
    logger.info(f"Adding link from parent to child...")
    link_result = dag_ops.add_link(
        parent_cid=parent_cid,
        name="first_child",
        child_cid=child_cid
    )
    
    if link_result["success"]:
        new_parent_cid = link_result["new_parent_cid"]
        logger.info(f"Successfully added link, new parent CID: {new_parent_cid}")
        
        # Retrieve the parent with link
        logger.info(f"Retrieving updated parent...")
        parent_get_result = dag_ops.get(new_parent_cid)
        
        if parent_get_result["success"]:
            updated_parent = parent_get_result["data"]
            logger.info("Updated parent object:")
            pretty_print(updated_parent)
            
            # Verify link exists
            if "first_child" in updated_parent and "/" in updated_parent["first_child"]:
                logger.info("✓ Link verification passed")
                
                # Resolve through the link
                logger.info(f"Resolving through link: {new_parent_cid}/first_child")
                resolve_result = dag_ops.resolve(f"{new_parent_cid}/first_child")
                
                if resolve_result["success"]:
                    resolved_cid = resolve_result["resolved_path"]
                    logger.info(f"Link resolves to: {resolved_cid}")
                    
                    # Verify resolved CID matches child CID
                    if child_cid in resolved_cid:
                        logger.info("✓ Link resolution verification passed")
                    else:
                        logger.error("✗ Link resolution verification failed")
                else:
                    logger.error(f"Failed to resolve link: {resolve_result['error']}")
            else:
                logger.error("✗ Link verification failed - link not found in parent")
        else:
            logger.error(f"Failed to retrieve updated parent: {parent_get_result['error']}")
    else:
        logger.error(f"Failed to add link: {link_result['error']}")
        return
    
    # Create a second child
    second_child = {
        "name": "Second Child",
        "created": time.time(),
        "data": ["a", "b", "c"]
    }
    
    # Store the second child
    logger.info("Storing second child object...")
    second_child_result = dag_ops.put(second_child)
    
    if not second_child_result["success"]:
        logger.error(f"Failed to store second child: {second_child_result['error']}")
        return
    
    second_child_cid = second_child_result["cid"]
    logger.info(f"Second child CID: {second_child_cid}")
    
    # Add second child to parent
    logger.info(f"Adding second child to parent...")
    second_link_result = dag_ops.add_link(
        parent_cid=new_parent_cid,
        name="second_child",
        child_cid=second_child_cid
    )
    
    if second_link_result["success"]:
        final_parent_cid = second_link_result["new_parent_cid"]
        logger.info(f"Successfully added second link, final parent CID: {final_parent_cid}")
        
        # Get the parent with both links
        final_parent_result = dag_ops.get(final_parent_cid)
        
        if final_parent_result["success"]:
            final_parent = final_parent_result["data"]
            logger.info("Final parent object with both links:")
            pretty_print(final_parent)
            
            # Now remove the first link
            logger.info("Removing first link...")
            remove_result = dag_ops.remove_link(
                parent_cid=final_parent_cid,
                name="first_child"
            )
            
            if remove_result["success"]:
                reduced_parent_cid = remove_result["new_parent_cid"]
                logger.info(f"Successfully removed link, new parent CID: {reduced_parent_cid}")
                
                # Get the parent with link removed
                reduced_parent_result = dag_ops.get(reduced_parent_cid)
                
                if reduced_parent_result["success"]:
                    reduced_parent = reduced_parent_result["data"]
                    logger.info("Parent after removing link:")
                    pretty_print(reduced_parent)
                    
                    # Verify first link is gone but second remains
                    if ("first_child" not in reduced_parent and 
                            "second_child" in reduced_parent):
                        logger.info("✓ Link removal verification passed")
                    else:
                        logger.error("✗ Link removal verification failed")
                else:
                    logger.error(f"Failed to get parent after link removal: {reduced_parent_result['error']}")
            else:
                logger.error(f"Failed to remove link: {remove_result['error']}")
        else:
            logger.error(f"Failed to get final parent: {final_parent_result['error']}")
    else:
        logger.error(f"Failed to add second link: {second_link_result['error']}")
    
    logger.info("DAG link operations test completed")

def test_tree_operations(api_url: str = "http://127.0.0.1:5001/api/v0") -> None:
    """Test DAG tree operations."""
    logger.info("=== Testing DAG Tree Operations ===")
    logger.info(f"Using API URL: {api_url}")
    
    # Initialize connection and DAG operations
    config = IPFSConnectionConfig(base_url=api_url)
    pool = get_connection_pool(config)
    dag_ops = DAGOperations(pool)
    
    # Create a complex tree structure
    tree = {
        "name": "Root Node",
        "metadata": {
            "created": time.time(),
            "version": "1.0",
            "id": uuid.uuid4().hex
        },
        "children": [
            {
                "name": "Child 1",
                "type": "folder",
                "items": [
                    {"name": "Item 1.1", "data": "Value 1.1"},
                    {"name": "Item 1.2", "data": "Value 1.2"}
                ]
            },
            {
                "name": "Child 2",
                "type": "document",
                "content": "This is the content of child 2"
            }
        ]
    }
    
    # Create the tree
    logger.info("Creating DAG tree structure...")
    tree_result = dag_ops.create_tree(tree)
    
    if tree_result["success"]:
        tree_cid = tree_result["cid"]
        logger.info(f"Successfully created tree with root CID: {tree_cid}")
        
        # Get the complete tree
        logger.info("Retrieving complete tree structure...")
        get_tree_result = dag_ops.get_tree(tree_cid)
        
        if get_tree_result["success"]:
            retrieved_tree = get_tree_result["data"]
            logger.info("Retrieved tree structure:")
            pretty_print(retrieved_tree)
            
            # Verify tree structure
            if (retrieved_tree["name"] == tree["name"] and 
                    len(retrieved_tree["children"]) == len(tree["children"])):
                logger.info("✓ Tree structure verification passed")
            else:
                logger.error("✗ Tree structure verification failed")
        else:
            logger.error(f"Failed to retrieve tree: {get_tree_result['error']}")
    else:
        logger.error(f"Failed to create tree: {tree_result['error']}")
        return
    
    # Navigate to a specific path in the tree
    logger.info(f"Navigating to first child in tree: {tree_cid}/children/0")
    child_result = dag_ops.get(tree_cid, path="/children/0")
    
    if child_result["success"]:
        first_child = child_result["data"]
        logger.info("First child node:")
        pretty_print(first_child)
        
        # Verify child data
        if first_child["name"] == "Child 1" and first_child["type"] == "folder":
            logger.info("✓ Child navigation verification passed")
        else:
            logger.error("✗ Child navigation verification failed")
    else:
        logger.error(f"Failed to navigate to child: {child_result['error']}")
    
    # Update a node in the tree
    logger.info("Updating root node with new metadata...")
    update_result = dag_ops.update_node(
        cid=tree_cid,
        updates={
            "metadata": {
                "created": time.time(),
                "version": "1.1",
                "id": tree["metadata"]["id"],
                "updated": True
            }
        }
    )
    
    if update_result["success"]:
        updated_cid = update_result["new_cid"]
        logger.info(f"Successfully updated node, new CID: {updated_cid}")
        
        # Get the updated tree
        updated_tree_result = dag_ops.get(updated_cid)
        
        if updated_tree_result["success"]:
            updated_tree = updated_tree_result["data"]
            logger.info("Updated tree:")
            pretty_print(updated_tree["metadata"])
            
            # Verify update
            if (updated_tree["metadata"]["version"] == "1.1" and 
                    updated_tree["metadata"]["updated"] == True):
                logger.info("✓ Update verification passed")
            else:
                logger.error("✗ Update verification failed")
        else:
            logger.error(f"Failed to get updated tree: {updated_tree_result['error']}")
    else:
        logger.error(f"Failed to update node: {update_result['error']}")
    
    logger.info("DAG tree operations test completed")

def test_import_export(api_url: str = "http://127.0.0.1:5001/api/v0") -> None:
    """Test DAG import and export operations."""
    logger.info("=== Testing DAG Import/Export Operations ===")
    logger.info(f"Using API URL: {api_url}")
    
    # Initialize connection and DAG operations
    config = IPFSConnectionConfig(base_url=api_url)
    pool = get_connection_pool(config)
    dag_ops = DAGOperations(pool)
    
    # Create test data
    test_data = {
        "name": "Export Test Object",
        "created": time.time(),
        "data": [
            {"key": "value1", "index": 1},
            {"key": "value2", "index": 2},
            {"key": "value3", "index": 3}
        ],
        "metadata": {
            "description": "Test object for import/export operations",
            "version": "1.0"
        }
    }
    
    # Import data
    logger.info("Importing test data into DAG...")
    import_result = dag_ops.import_data(test_data)
    
    if import_result["success"]:
        logger.info(f"Successfully imported data with CID: {import_result['cid']}")
        cid = import_result["cid"]
    else:
        logger.error(f"Failed to import data: {import_result['error']}")
        return
    
    # Export to file
    with tempfile.NamedTemporaryFile(suffix=".car", delete=False) as temp_file:
        export_file = temp_file.name
    
    logger.info(f"Exporting DAG to file: {export_file}")
    export_result = dag_ops.export_data(cid, output_file=export_file)
    
    if export_result["success"]:
        logger.info(f"Successfully exported DAG to file, size: {os.path.getsize(export_file)} bytes")
        
        # Export to memory
        logger.info("Exporting DAG to memory...")
        memory_export_result = dag_ops.export_data(cid)
        
        if memory_export_result["success"]:
            logger.info(f"Successfully exported DAG to memory, data size: {len(memory_export_result['data'])} bytes")
            
            # Export to stream
            logger.info("Exporting DAG to stream...")
            output_stream = io.BytesIO()
            stream_export_result = dag_ops.export_data(cid, output_file=output_stream)
            
            if stream_export_result["success"]:
                output_stream.seek(0)
                stream_size = len(output_stream.getvalue())
                logger.info(f"Successfully exported DAG to stream, data size: {stream_size} bytes")
                
                # Verify sizes are similar
                file_size = os.path.getsize(export_file)
                memory_size = len(memory_export_result['data'])
                
                if abs(file_size - memory_size) < 100 and abs(file_size - stream_size) < 100:
                    logger.info("✓ Export size verification passed")
                else:
                    logger.error(f"✗ Export size verification failed: file={file_size}, memory={memory_size}, stream={stream_size}")
            else:
                logger.error(f"Failed to export to stream: {stream_export_result['error']}")
        else:
            logger.error(f"Failed to export to memory: {memory_export_result['error']}")
    else:
        logger.error(f"Failed to export to file: {export_result['error']}")
    
    # Clean up
    try:
        os.unlink(export_file)
    except:
        pass
    
    logger.info("DAG import/export operations test completed")

def test_format_variations(api_url: str = "http://127.0.0.1:5001/api/v0") -> None:
    """Test DAG operations with different formats."""
    logger.info("=== Testing DAG Format Variations ===")
    logger.info(f"Using API URL: {api_url}")
    
    # Initialize connection and DAG operations
    config = IPFSConnectionConfig(base_url=api_url)
    pool = get_connection_pool(config)
    dag_ops = DAGOperations(pool)
    
    # Test data to store in different formats
    test_data = {
        "name": "Format Test",
        "value": 42,
        "array": [1, 2, 3],
        "nested": {"key": "value"}
    }
    
    formats = [
        ("DAG-JSON", IPLDFormat.DAG_JSON),
        ("DAG-CBOR", IPLDFormat.DAG_CBOR),
        ("DAG-PB", IPLDFormat.DAG_PB)
    ]
    
    for format_name, format_type in formats:
        logger.info(f"\nTesting with {format_name} format")
        
        # Store data in the format
        put_result = dag_ops.put(test_data, format_type=format_type)
        
        if put_result["success"]:
            cid = put_result["cid"]
            logger.info(f"Successfully stored data with CID: {cid}")
            
            # Retrieve the data
            get_result = dag_ops.get(cid)
            
            if get_result["success"]:
                retrieved_data = get_result["data"]
                logger.info(f"Retrieved data in {format_name} format:")
                pretty_print(retrieved_data)
                
                # Some formats might not preserve all data exactly as is
                # For example, DAG-PB has limitations on structure
                if format_type != IPLDFormat.DAG_PB:
                    if retrieved_data.get("name") == test_data["name"]:
                        logger.info(f"✓ {format_name} verification passed")
                    else:
                        logger.error(f"✗ {format_name} verification failed")
                else:
                    logger.info(f"Note: {format_name} might not preserve all data structure exactly")
            else:
                logger.error(f"Failed to retrieve {format_name} data: {get_result['error']}")
        else:
            logger.error(f"Failed to store {format_name} data: {put_result['error']}")
    
    # Test with raw bytes
    raw_data = b"This is some raw binary data for testing"
    logger.info("\nTesting with RAW format")
    
    raw_result = dag_ops.put(raw_data, format_type=IPLDFormat.RAW)
    
    if raw_result["success"]:
        raw_cid = raw_result["cid"]
        logger.info(f"Successfully stored raw data with CID: {raw_cid}")
        
        # Retrieve raw data
        raw_get_result = dag_ops.get(raw_cid, output_format="raw")
        
        if raw_get_result["success"]:
            retrieved_raw = raw_get_result["data"]
            logger.info(f"Retrieved raw data: {retrieved_raw[:30]}...")
            
            # Verify raw data
            if isinstance(retrieved_raw, bytes) and retrieved_raw == raw_data:
                logger.info("✓ Raw data verification passed")
            else:
                logger.error("✗ Raw data verification failed")
        else:
            logger.error(f"Failed to retrieve raw data: {raw_get_result['error']}")
    else:
        logger.error(f"Failed to store raw data: {raw_result['error']}")
    
    logger.info("DAG format variations test completed")

def main():
    """Main entry point for testing."""
    parser = argparse.ArgumentParser(description="Test DAG operations")
    parser.add_argument("--api", default="http://127.0.0.1:5001/api/v0", help="IPFS API URL")
    parser.add_argument("--test", choices=["basic", "links", "tree", "import-export", "formats", "all"], 
                        default="all", help="Test to run")
    args = parser.parse_args()
    
    logger.info(f"Testing with IPFS API: {args.api}")
    
    if args.test in ["basic", "all"]:
        test_basic_operations(args.api)
    
    if args.test in ["links", "all"]:
        test_link_operations(args.api)
    
    if args.test in ["tree", "all"]:
        test_tree_operations(args.api)
    
    if args.test in ["import-export", "all"]:
        test_import_export(args.api)
    
    if args.test in ["formats", "all"]:
        test_format_variations(args.api)
    
    logger.info("All DAG operations tests completed")

if __name__ == "__main__":
    main()