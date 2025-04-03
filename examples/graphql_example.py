#!/usr/bin/env python3
"""
Example demonstrating how to use the IPFS Kit GraphQL API.

This example shows:
1. How to construct and send GraphQL queries
2. Different query types (queries, mutations)
3. Working with variables
4. Batch operations
5. Complex nested queries
6. Error handling
7. AI/ML integration via GraphQL
8. IPFS Cluster operations
9. Directory listing and navigation
10. IPNS name operations
11. Key management
"""

import argparse
import base64
import json
import os
import requests
import sys
import time
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports when running as a script
if __name__ == "__main__":
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, parent_dir)

# Try to import GraphQL libraries - they're not required for client usage
try:
    import graphene
    HAS_GRAPHQL_LIBS = True
except ImportError:
    HAS_GRAPHQL_LIBS = False
    print("Note: GraphQL libraries (graphene) not found. This is fine for client usage.")


class GraphQLClient:
    """GraphQL client for interacting with the IPFS Kit GraphQL API."""
    
    def __init__(self, url="http://localhost:8000/graphql"):
        """Initialize with GraphQL endpoint URL."""
        self.url = url
        
    def execute_query(self, query, variables=None):
        """Execute a GraphQL query/mutation with optional variables."""
        # Prepare payload
        payload = {
            "query": query,
            "variables": variables if variables else {}
        }
        
        # Send request
        headers = {"Content-Type": "application/json"}
        response = requests.post(self.url, json=payload, headers=headers)
        
        # Handle response
        if response.status_code != 200:
            raise Exception(f"GraphQL query failed with status code: {response.status_code}")
            
        result = response.json()
        if "errors" in result:
            error_messages = [error.get("message", "Unknown error") for error in result["errors"]]
            raise Exception(f"GraphQL query execution error: {'; '.join(error_messages)}")
            
        return result["data"]
    
    def explore_schema(self):
        """Fetch the schema for exploration."""
        # This uses the introspection query to get schema details
        introspection_query = """
        query IntrospectionQuery {
          __schema {
            queryType {
              name
              fields {
                name
                description
                args {
                  name
                  description
                  type {
                    name
                    kind
                    ofType {
                      name
                      kind
                    }
                  }
                }
                type {
                  name
                  kind
                }
              }
            }
            mutationType {
              name
              fields {
                name
                description
              }
            }
            types {
              name
              kind
              description
              fields {
                name
                description
              }
            }
          }
        }
        """
        return self.execute_query(introspection_query)
    
    def batch_query(self, operations):
        """Execute multiple GraphQL operations in one request.
        
        Args:
            operations: List of dicts with 'query' and optional 'variables'
        
        Returns:
            List of results corresponding to each operation
        """
        # Build batch payload
        payload = [
            {
                "query": op["query"],
                "variables": op.get("variables", {})
            }
            for op in operations
        ]
        
        # Send batch request
        headers = {"Content-Type": "application/json"}
        response = requests.post(self.url, json=payload, headers=headers)
        
        # Handle response
        if response.status_code != 200:
            raise Exception(f"GraphQL batch query failed with status code: {response.status_code}")
            
        results = response.json()
        
        # Check for errors in any of the operations
        for i, result in enumerate(results):
            if "errors" in result:
                error_messages = [error.get("message", "Unknown error") for error in result["errors"]]
                print(f"Warning: Operation {i} had errors: {'; '.join(error_messages)}")
        
        # Return data from each operation
        return [result.get("data") for result in results]


def example_query_content_info(client):
    """Example: Query content information by CID."""
    print("\n=== Example: Query Content Information ===")
    
    # Define a query to get content info
    query = """
    query GetContentInfo($cid: String!) {
      content(cid: $cid) {
        cid
        size
        isDirectory
        pinned
        metadata {
          size
          blockCount
        }
      }
    }
    """
    
    # Choose a CID to query - this should exist in your IPFS node
    # If it doesn't, you can add content first using the add_content mutation
    # For this example, we'll use a well-known IPFS hash (the IPFS logo)
    variables = {
        "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
    }
    
    try:
        # Execute the query
        result = client.execute_query(query, variables)
        print("Query Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")


def example_list_directory(client):
    """Example: List directory contents."""
    print("\n=== Example: List Directory Contents ===")
    
    # Define a query to list directory
    query = """
    query ListDirectory($path: String!) {
      directory(path: $path) {
        name
        cid
        size
        isDirectory
        path
      }
    }
    """
    
    # Use a known directory CID - the IPFS examples directory is a good choice
    variables = {
        "path": "/ipfs/QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
    }
    
    try:
        # Execute the query
        result = client.execute_query(query, variables)
        print("Directory Contents:")
        
        if "directory" in result and result["directory"]:
            # Print formatted directory listing
            print(f"{'Name':<20} {'Type':<10} {'Size':<10} {'CID':<46}")
            print("-" * 86)
            
            for item in result["directory"]:
                item_type = "Directory" if item.get("isDirectory") else "File"
                print(f"{item.get('name', ''):<20} {item_type:<10} {item.get('size', 0):<10} {item.get('cid', '')}")
                
            print(f"\nTotal items: {len(result['directory'])}")
        else:
            print("No directory items found or path is not a directory")
    except Exception as e:
        print(f"Error: {e}")


def example_list_pinned_content(client):
    """Example: List all pinned content."""
    print("\n=== Example: List Pinned Content ===")
    
    # Define a query to list pins
    query = """
    query {
      pins {
        cid
        pinInfo {
          type
        }
      }
    }
    """
    
    try:
        # Execute the query
        result = client.execute_query(query)
        print("Query Result:")
        print(json.dumps(result, indent=2))
        
        # Print count of pins
        if "pins" in result:
            print(f"\nFound {len(result['pins'])} pinned items")
    except Exception as e:
        print(f"Error: {e}")


def example_list_peers(client):
    """Example: List connected peers."""
    print("\n=== Example: List Connected Peers ===")
    
    # Define a query to list peers
    query = """
    query {
      peers {
        peerId
        address
      }
    }
    """
    
    try:
        # Execute the query
        result = client.execute_query(query)
        print("Query Result:")
        print(json.dumps(result, indent=2))
        
        # Print count of peers
        if "peers" in result:
            print(f"\nConnected to {len(result['peers'])} peers")
    except Exception as e:
        print(f"Error: {e}")


def example_add_content(client):
    """Example: Add content to IPFS."""
    print("\n=== Example: Add Content to IPFS ===")
    
    # Define a mutation to add content
    mutation = """
    mutation AddContent($content: String!, $pin: Boolean) {
      addContent(content: $content, pin: $pin) {
        success
        cid
        size
      }
    }
    """
    
    # Content to add (base64 encoded for binary data)
    # For this example, we'll use simple text content
    content = "Hello from IPFS Kit GraphQL API!"
    content_base64 = base64.b64encode(content.encode()).decode()
    
    variables = {
        "content": content_base64,
        "pin": True
    }
    
    try:
        # Execute the mutation
        result = client.execute_query(mutation, variables)
        print("Mutation Result:")
        print(json.dumps(result, indent=2))
        
        # Return the CID for use in other examples
        if "addContent" in result and result["addContent"]["success"]:
            print(f"\nContent added with CID: {result['addContent']['cid']}")
            return result["addContent"]["cid"]
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def example_pin_content(client, cid):
    """Example: Pin content in IPFS."""
    print("\n=== Example: Pin Content ===")
    
    if not cid:
        print("No CID provided, skipping pin example")
        return
    
    # Define a mutation to pin content
    mutation = """
    mutation PinContent($cid: String!, $recursive: Boolean) {
      pinContent(cid: $cid, recursive: $recursive) {
        success
        cid
      }
    }
    """
    
    variables = {
        "cid": cid,
        "recursive": True
    }
    
    try:
        # Execute the mutation
        result = client.execute_query(mutation, variables)
        print("Mutation Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")


def example_unpin_content(client, cid):
    """Example: Unpin content from IPFS."""
    print("\n=== Example: Unpin Content ===")
    
    if not cid:
        print("No CID provided, skipping unpin example")
        return
    
    # Define a mutation to unpin content
    mutation = """
    mutation UnpinContent($cid: String!, $recursive: Boolean) {
      unpinContent(cid: $cid, recursive: $recursive) {
        success
        cid
      }
    }
    """
    
    variables = {
        "cid": cid,
        "recursive": True
    }
    
    try:
        # Execute the mutation
        result = client.execute_query(mutation, variables)
        print("Mutation Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")


def example_ipns_operations(client, cid):
    """Example: IPNS name operations."""
    print("\n=== Example: IPNS Operations ===")
    
    if not cid:
        print("No CID provided, skipping IPNS examples")
        return
    
    # 1. First, list existing IPNS names
    query_ipns = """
    query {
      ipnsNames {
        name
        value
        sequence
        validity
      }
    }
    """
    
    try:
        print("1. Listing existing IPNS names:")
        result = client.execute_query(query_ipns)
        if "ipnsNames" in result:
            for name_info in result["ipnsNames"]:
                print(f"  Name: {name_info.get('name')}, Points to: {name_info.get('value')}")
    except Exception as e:
        print(f"Error listing IPNS names: {e}")
    
    # 2. Publish new IPNS name
    mutation_publish = """
    mutation PublishName($cid: String!, $key: String, $lifetime: String) {
      publishIpns(cid: $cid, key: $key, lifetime: $lifetime) {
        success
        name
        value
      }
    }
    """
    
    variables_publish = {
        "cid": cid,
        "key": "self",  # Use default key
        "lifetime": "24h"  # 24-hour lifetime
    }
    
    try:
        print("\n2. Publishing IPNS name:")
        result = client.execute_query(mutation_publish, variables_publish)
        if "publishIpns" in result and result["publishIpns"]["success"]:
            ipns_name = result["publishIpns"]["name"]
            print(f"  Published name: {ipns_name}")
            print(f"  Points to: {result['publishIpns']['value']}")
            
            # 3. Resolve the name
            query_resolve = """
            query ResolveIPNS($name: String!) {
              resolveIpns(name: $name)
            }
            """
            
            variables_resolve = {
                "name": ipns_name
            }
            
            print("\n3. Resolving IPNS name:")
            resolve_result = client.execute_query(query_resolve, variables_resolve)
            if "resolveIpns" in resolve_result:
                print(f"  {ipns_name} resolves to: {resolve_result['resolveIpns']}")
        else:
            print("  Failed to publish IPNS name")
    except Exception as e:
        print(f"Error with IPNS operations: {e}")


def example_key_management(client):
    """Example: Key management operations."""
    print("\n=== Example: Key Management ===")
    
    # 1. List existing keys
    query_keys = """
    query {
      keys {
        name
        id
      }
    }
    """
    
    try:
        print("1. Listing existing keys:")
        result = client.execute_query(query_keys)
        if "keys" in result:
            for key in result["keys"]:
                print(f"  {key.get('name')}: {key.get('id')}")
    except Exception as e:
        print(f"Error listing keys: {e}")
    
    # 2. Generate a new key
    # Use a timestamp to ensure unique key name
    key_name = f"example-key-{int(time.time())}"
    
    mutation_generate = """
    mutation GenerateKey($name: String!, $type: String, $size: Int) {
      generateKey(name: $name, type: $type, size: $size) {
        success
        name
        id
      }
    }
    """
    
    variables_generate = {
        "name": key_name,
        "type": "ed25519",  # Faster to generate than RSA
        "size": 0  # Not used for ed25519
    }
    
    try:
        print(f"\n2. Generating new key '{key_name}':")
        result = client.execute_query(mutation_generate, variables_generate)
        if "generateKey" in result and result["generateKey"]["success"]:
            print(f"  Generated key: {result['generateKey']['name']}")
            print(f"  Key ID: {result['generateKey']['id']}")
        else:
            print("  Failed to generate key")
    except Exception as e:
        print(f"Error generating key: {e}")


def example_cluster_operations(client, cid):
    """Example: IPFS Cluster operations."""
    print("\n=== Example: IPFS Cluster Operations ===")
    
    # 1. Query cluster peers
    query_peers = """
    query {
      clusterPeers {
        peerId
        name
        addresses
        version
      }
    }
    """
    
    try:
        print("1. Listing cluster peers:")
        result = client.execute_query(query_peers)
        if "clusterPeers" in result:
            for peer in result["clusterPeers"]:
                print(f"  Peer: {peer.get('name', 'unnamed')} ({peer.get('peerId', 'unknown')})")
                print(f"  Version: {peer.get('version', 'unknown')}")
                print(f"  Addresses: {', '.join(peer.get('addresses', []))}")
                print("")
            
            if not result["clusterPeers"]:
                print("  No cluster peers found (cluster may not be configured)")
        else:
            print("  Cluster peer information not available")
    except Exception as e:
        print(f"Error querying cluster peers: {e}")
    
    # 2. Pin content to the cluster
    if cid:
        mutation_cluster_pin = """
        mutation PinToCluster($cid: String!, $replication: Int, $name: String) {
          clusterPin(cid: $cid, replicationFactor: $replication, name: $name) {
            success
            cid
          }
        }
        """
        
        variables_pin = {
            "cid": cid,
            "replication": -1,  # All nodes
            "name": "example-pin"
        }
        
        try:
            print("\n2. Pinning content to cluster:")
            result = client.execute_query(mutation_cluster_pin, variables_pin)
            if "clusterPin" in result and result["clusterPin"]["success"]:
                print(f"  Successfully pinned {cid} to cluster")
                
                # 3. Check pin status
                query_status = """
                query PinStatus($cid: String!) {
                  clusterStatus(cid: $cid) {
                    cid
                    status
                    timestamp
                    peerId
                    error
                  }
                }
                """
                
                variables_status = {
                    "cid": cid
                }
                
                print("\n3. Checking cluster pin status:")
                status_result = client.execute_query(query_status, variables_status)
                if "clusterStatus" in status_result:
                    status = status_result["clusterStatus"]
                    print(f"  CID: {status.get('cid')}")
                    print(f"  Status: {status.get('status')}")
                    if status.get('error'):
                        print(f"  Error: {status.get('error')}")
            else:
                print("  Failed to pin content to cluster")
        except Exception as e:
            print(f"Error with cluster operations: {e}")
    else:
        print("\n2. Skipping cluster pin example (no CID provided)")


def example_ai_ml_integration(client):
    """Example: AI/ML integration via GraphQL."""
    print("\n=== Example: AI/ML Integration ===")
    
    # 1. Query available AI models
    query_models = """
    query {
      aiModels {
        name
        version
        framework
        cid
        description
        tags
      }
    }
    """
    
    try:
        print("1. Querying available AI models:")
        result = client.execute_query(query_models)
        if "aiModels" in result:
            if result["aiModels"]:
                for model in result["aiModels"]:
                    print(f"  Model: {model.get('name')} (v{model.get('version')})")
                    print(f"  Framework: {model.get('framework')}")
                    print(f"  Description: {model.get('description')}")
                    if model.get('tags'):
                        print(f"  Tags: {', '.join(model.get('tags'))}")
                    print(f"  CID: {model.get('cid')}")
                    print("")
            else:
                print("  No AI models found")
        else:
            print("  AI model information not available")
    except Exception as e:
        print(f"Error querying AI models: {e}")
    
    # 2. Query available AI datasets
    query_datasets = """
    query {
      aiDatasets {
        name
        version
        format
        cid
        description
        tags
      }
    }
    """
    
    try:
        print("\n2. Querying available AI datasets:")
        result = client.execute_query(query_datasets)
        if "aiDatasets" in result:
            if result["aiDatasets"]:
                for dataset in result["aiDatasets"]:
                    print(f"  Dataset: {dataset.get('name')} (v{dataset.get('version')})")
                    print(f"  Format: {dataset.get('format')}")
                    print(f"  Description: {dataset.get('description')}")
                    if dataset.get('tags'):
                        print(f"  Tags: {', '.join(dataset.get('tags'))}")
                    print(f"  CID: {dataset.get('cid')}")
                    print("")
            else:
                print("  No AI datasets found")
        else:
            print("  AI dataset information not available")
    except Exception as e:
        print(f"Error querying AI datasets: {e}")


def example_batch_operations(client):
    """Example: Performing batch operations."""
    print("\n=== Example: Batch Operations ===")
    
    # Define multiple operations to execute in a single request
    operations = [
        {
            "query": "query { version }",
            "variables": {}
        },
        {
            "query": """
            query {
              peers {
                peerId
                address
              }
            }
            """,
            "variables": {}
        },
        {
            "query": """
            query {
              keys {
                name
                id
              }
            }
            """,
            "variables": {}
        }
    ]
    
    try:
        # Execute batch query
        print("Executing batch of 3 operations in a single request:")
        results = client.batch_query(operations)
        
        # Process results
        print("\nResults:")
        print("1. Version:", results[0].get("version", "unknown"))
        
        peers = results[1].get("peers", [])
        print(f"2. Peers: {len(peers)} connected")
        
        keys = results[2].get("keys", [])
        print(f"3. Keys: {len(keys)} available")
        if keys:
            key_names = [key.get("name") for key in keys]
            print(f"   Key names: {', '.join(key_names)}")
        
        print("\nBatch operations completed successfully!")
    except Exception as e:
        print(f"Error performing batch operations: {e}")


def example_complex_query(client):
    """Example: Complex query with multiple nested fields."""
    print("\n=== Example: Complex Query ===")
    
    # Define a complex query to get multiple types of data at once
    query = """
    query {
      # Get version info
      version
      
      # Get first 5 pins
      pins {
        cid
        pinInfo {
          type
          pinnedAt
        }
      }
      
      # Get peer info
      peers {
        peerId
        address
      }
      
      # Get keys
      keys {
        name
        id
      }
    }
    """
    
    try:
        # Execute the query
        result = client.execute_query(query)
        print("Query Result (summarized):")
        
        # Print a summary of the results
        if "version" in result:
            print(f"IPFS Version: {result['version']}")
        
        if "pins" in result:
            print(f"Pinned Items: {len(result['pins'])}")
            
        if "peers" in result:
            print(f"Connected Peers: {len(result['peers'])}")
            
        if "keys" in result:
            print(f"Keys: {len(result['keys'])}")
            if result["keys"]:
                print("Key Names:", ", ".join(key["name"] for key in result["keys"]))
    except Exception as e:
        print(f"Error: {e}")


def example_error_handling(client):
    """Example: Handling errors in GraphQL queries."""
    print("\n=== Example: Error Handling ===")
    
    # Define a query with invalid fields to trigger an error
    query = """
    query {
      # This field doesn't exist and will cause an error
      invalidField
      
      # This is a valid field but will still be part of the same request
      version
    }
    """
    
    try:
        # Execute the query
        result = client.execute_query(query)
        print("This line shouldn't be reached due to the error")
    except Exception as e:
        print(f"Caught error: {e}")
        
    # Now try a valid query in a new request
    print("\nNow trying a valid query after the error:")
    query = """
    query {
      version
    }
    """
    
    try:
        # Execute the query
        result = client.execute_query(query)
        print(f"Valid query result: IPFS Version = {result['version']}")
    except Exception as e:
        print(f"Error with valid query: {e}")


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="IPFS Kit GraphQL API Example")
    parser.add_argument("--url", default="http://localhost:8000/graphql", 
                        help="URL of the GraphQL endpoint")
    parser.add_argument("--examples", type=str, 
                        help="Comma-separated list of examples to run (e.g., 'peers,content,pins')")
    parser.add_argument("--all", action="store_true", 
                        help="Run all examples, including cluster and AI/ML examples")
    args = parser.parse_args()
    
    # Create GraphQL client
    client = GraphQLClient(url=args.url)
    
    # Map of available examples
    examples = {
        "content": example_query_content_info,
        "directory": example_list_directory,
        "pins": example_list_pinned_content,
        "peers": example_list_peers,
        "add": example_add_content,
        "pin": lambda c: example_pin_content(c, None),  # Will be updated if add example runs
        "unpin": lambda c: example_unpin_content(c, None),  # Will be updated if add example runs
        "ipns": lambda c: example_ipns_operations(c, None),  # Will be updated if add example runs
        "keys": example_key_management,
        "cluster": lambda c: example_cluster_operations(c, None),  # Will be updated if add example runs
        "ai": example_ai_ml_integration,
        "batch": example_batch_operations,
        "complex": example_complex_query,
        "error": example_error_handling
    }
    
    try:
        # Test connection and capabilities
        print("Testing connection to GraphQL endpoint...")
        schema_info = client.explore_schema()
        print(f"GraphQL schema available with {len(schema_info['__schema']['types'])} types")
        
        # Add a small content item to use in examples
        print("\nAdding a small content item to use in examples...")
        added_cid = example_add_content(client)
        
        # Update examples that need a CID
        if added_cid:
            examples["pin"] = lambda c: example_pin_content(c, added_cid)
            examples["unpin"] = lambda c: example_unpin_content(c, added_cid)
            examples["ipns"] = lambda c: example_ipns_operations(c, added_cid)
            examples["cluster"] = lambda c: example_cluster_operations(c, added_cid)
        
        # Determine which examples to run
        examples_to_run = []
        if args.examples:
            # Run specific examples
            requested = args.examples.split(",")
            examples_to_run = [ex.strip() for ex in requested if ex.strip() in examples]
            if not examples_to_run:
                print(f"No valid examples specified. Available examples: {', '.join(examples.keys())}")
        elif args.all:
            # Run all examples
            examples_to_run = list(examples.keys())
        else:
            # Run basic examples only
            examples_to_run = ["content", "directory", "pins", "peers", "add", "pin", "complex", "error"]
        
        # Run selected examples
        for example_name in examples_to_run:
            examples[example_name](client)
        
        print("\nAll examples completed successfully!")
        
    except Exception as e:
        print(f"Error connecting to GraphQL API: {e}")
        print("\nPossible causes:")
        print("1. The IPFS Kit API server isn't running")
        print("2. GraphQL support isn't enabled or properly configured")
        print("3. The API URL is incorrect")
        print("4. Network issues")
        
        print("\nTo start the API server with GraphQL support:")
        print("1. Ensure graphene is installed: pip install graphene")
        print("2. Start the server: python -m ipfs_kit_py.api")
        print("3. Access GraphQL Playground at: http://localhost:8000/graphql/playground")
        
        print("\nAvailable examples:")
        for name in examples.keys():
            print(f"  - {name}")
        print("\nRun with specific examples: python graphql_example.py --examples=content,pins,peers")
        print("Run all examples: python graphql_example.py --all")


if __name__ == "__main__":
    main()