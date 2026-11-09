"""
Enhanced DAG Operations Module for IPFS Kit.

This module provides advanced Directed Acyclic Graph (DAG) operations for IPFS,
enabling sophisticated content manipulation and traversal through IPLD
(InterPlanetary Linked Data).

Key features:
- Comprehensive DAG node management (get, put, import, export)
- Multi-format support (dag-pb, dag-cbor, dag-json, raw)
- Path-based traversal through complex data structures
- Efficient patch operations (add-link, rm-link, set-data)
- Structured querying using IPLD selectors
- Bulk operations and batch processing
- Advanced import/export with custom options
"""

import base64
import io
import base64
import io # Added io import
import json
import logging
import tempfile
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, BinaryIO

from ipfs_connection_pool import get_connection_pool # type: ignore

# Set up logging
logger = logging.getLogger("ipfs_dag_operations")

class IPLDFormat(Enum):
    """Supported formats for IPLD data."""
    DAG_PB = "dag-pb"      # Protocol Buffers (default in IPFS)
    DAG_CBOR = "dag-cbor"  # CBOR-based format
    DAG_JSON = "dag-json"  # JSON-based format
    RAW = "raw"            # Raw bytes

class DAGOperations:
    """
    Provides methods for interacting with IPFS Directed Acyclic Graphs (DAGs) using IPLD.

    This class allows manipulation of IPLD data structures stored within IPFS.
    IPLD (InterPlanetary Linked Data) is a data model for decentralized systems,
    enabling traversal across different hash-linked data formats like JSON, CBOR,
    and traditional IPFS objects (dag-pb).

    Key functionalities include:
    - `put`: Storing data (dict, list, bytes) as an IPLD node, returning its CID.
    - `get`: Retrieving data from an IPLD node using its CID and optional path.
    - `resolve`: Resolving an IPLD path (e.g., `<cid>/path/to/data`) to the CID of the
                 target node and any remaining path components.
    - `stat`: Getting statistics (size, number of blocks) about a DAG node.
    - `import_data`: Importing data (including CAR files) into the DAG structure.
    - `export_data`: Exporting a DAG structure as a CAR (Content Addressable aRchive) file.
    - Helper methods for common DAG modifications like adding/removing links.

    It uses an `ipfs_connection_pool` for communication with the IPFS daemon's
    HTTP API (`/api/v0/dag/...`).
    """

    def __init__(self, connection_pool=None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize DAG operations.
        
        Args:
            connection_pool: Optional connection pool to use
            config: Configuration options for DAG operations
        """
        self.config = config or {}
        self.connection_pool = connection_pool or get_connection_pool()
        
        # Default format when not specified
        self.default_format = self.config.get("default_format", IPLDFormat.DAG_JSON)
        if isinstance(self.default_format, IPLDFormat):
            self.default_format = self.default_format.value
        
        # Performance metrics
        self.performance_metrics = {
            "put": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "get": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "resolve": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "stat": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "import": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "export": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
        }
    
    def _update_metrics(self, operation: str, duration: float, success: bool) -> None:
        """
        Update performance metrics for an operation.
        
        Args:
            operation: The operation name
            duration: The operation duration in seconds
            success: Whether the operation was successful
        """
        if operation in self.performance_metrics:
            metrics = self.performance_metrics[operation]
            metrics["count"] += 1
            metrics["total_time"] += duration
            metrics["avg_time"] = metrics["total_time"] / metrics["count"]
            
            # Update success rate using exponential moving average
            alpha = 0.1  # Weight for new observations
            metrics["success_rate"] = (
                (1 - alpha) * metrics["success_rate"] + 
                alpha * (1.0 if success else 0.0)
            )
    
    def put(
        self,
        data: Union[Dict[str, Any], List[Any], str, bytes],
        format_type: Union[IPLDFormat, str] = None,
        input_encoding: str = "json",
        pin: bool = True,
        hash_alg: str = "sha2-256",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store arbitrary data as an IPLD node in IPFS.

        This method takes Python objects (dict, list), strings, or bytes, encodes
        them according to the specified format and input encoding, and stores
        them as a node in the IPFS DAG. It returns the Content Identifier (CID)
        of the newly created node.

        Args:
            data (Union[Dict, List, str, bytes]): The data to be stored.
                - If dict or list, it's typically encoded as dag-json or dag-cbor.
                - If str or bytes, `input_encoding` determines interpretation.
            format_type (Union[IPLDFormat, str], optional): The IPLD codec to use for
                encoding the node. Defaults to `self.default_format` (usually 'dag-json').
                Examples: 'dag-pb', 'dag-cbor', 'dag-json', 'raw'.
            input_encoding (str): Specifies how to interpret the input `data` if it's
                a string or bytes. Common values:
                - 'json': Input is a JSON string.
                - 'raw': Input is raw binary data (will be stored as a 'raw' node
                         or potentially wrapped if format is not 'raw').
                - 'cbor': Input is CBOR encoded bytes.
                Defaults to 'json'.
            pin (bool): If True (default), the newly created DAG node will be pinned
                        to local storage to prevent garbage collection.
            hash_alg (str): The hash algorithm to use for generating the CID.
                            Defaults to 'sha2-256'.
            options (Optional[Dict[str, Any]]): Additional low-level options for the
                                                `dag/put` API endpoint.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
                            On success:
                                {'success': True, 'cid': <CID_string>, 'format': <format_used>,
                                 'pinned': <bool>, 'duration': <float_seconds>}
                            On failure:
                                {'success': False, 'error': <error_message>, ...}

        Example:
            >>> dag_ops = DAGOperations()
            >>> my_data = {'name': 'example', 'value': 123, 'link': {'/': 'Qm...'}}
            >>> result = dag_ops.put(my_data, format_type='dag-cbor', pin=True)
            >>> if result['success']:
            >>>     print(f"Stored data with CID: {result['cid']}")
        """
        options = options or {}
        start_time = time.time()
        
        # Set default format if not specified
        if format_type is None:
            format_type = self.default_format
        
        # Convert enum to string if needed
        if isinstance(format_type, IPLDFormat):
            format_type = format_type.value
        
        # Prepare data based on input type and encoding
        if isinstance(data, (dict, list)):
            # Convert to JSON string
            data_str = json.dumps(data)
            input_enc = "json"
        elif isinstance(data, str):
            data_str = data
            input_enc = input_encoding
        elif isinstance(data, bytes):
            # For bytes, we handle differently based on the encoding
            if input_encoding == "json":
                try:
                    # Try to decode as UTF-8 and validate as JSON
                    data_str = data.decode("utf-8")
                    json.loads(data_str)  # Just to validate
                    input_enc = "json"
                except (UnicodeDecodeError, json.JSONDecodeError):
                    # Fall back to raw
                    data_str = base64.b64encode(data).decode("utf-8")
                    input_enc = "raw"
            else:
                data_str = base64.b64encode(data).decode("utf-8")
                input_enc = "raw"
        else:
            # Unsupported data type
            duration = time.time() - start_time
            self._update_metrics("put", duration, False)
            return {
                "success": False,
                "error": f"Unsupported data type: {type(data)}",
                "duration": duration,
            }
        
        # Create the request parameters
        params = {
            "format": format_type,
            "input-enc": input_enc,
            "pin": "true" if pin else "false",
            "hash": hash_alg,
        }
        
        # Add any other options
        for key, value in options.items():
            if key not in params and value is not None:
                params[key] = str(value)
        
        try:
            # Call the IPFS API
            response = self.connection_pool.post(
                "dag/put",
                data=data_str,
                params=params,
            )
            
            success = response.status_code == 200
            
            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("put", duration, success)
            
            if success:
                try:
                    response_json = response.json()
                    
                    return {
                        "success": True,
                        "cid": response_json.get("Cid", {}).get("/"),
                        "format": format_type,
                        "pinned": pin,
                        "duration": duration,
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid JSON response",
                        "details": response.text,
                        "duration": duration,
                    }
            else:
                return {
                    "success": False,
                    "error": f"Failed to put DAG node: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }
                
        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("put", duration, False)
            
            return {
                "success": False,
                "error": f"Error putting DAG node: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }
    
    def get(
        self,
        cid: str,
        path: str = "",
        output_format: str = "json",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve data from an IPLD node, optionally traversing a path within it.

        Fetches the DAG node identified by `cid` and decodes it. If a `path` is
        provided, it attempts to resolve that path within the decoded node structure.
        The output format can be specified.

        Args:
            cid (str): The Content Identifier (CID) of the root DAG node to retrieve.
            path (str): An optional IPLD path to traverse within the node after retrieval.
                        Paths follow the format `/field1/0/field2`. Defaults to "" (root).
            output_format (str): The desired encoding for the output data.
                                 Common values:
                                 - 'json': Decodes the node (or resolved path value)
                                           and returns it as a Python object (dict/list/primitive).
                                           Handles dag-json, dag-cbor, and attempts dag-pb.
                                 - 'raw': Returns the raw bytes of the node or resolved value.
                                 - 'cbor': Returns the CBOR encoded bytes.
                                 Defaults to 'json'.
            options (Optional[Dict[str, Any]]): Additional low-level options for the
                                                `dag/get` API endpoint.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
                            On success:
                                {'success': True, 'cid': <root_cid>, 'path': <requested_path>,
                                 'data': <retrieved_data>, 'format': <output_format>,
                                 'duration': <float_seconds>}
                                 (Note: `data` type depends on `output_format`)
                            On failure:
                                {'success': False, 'error': <error_message>, ...}

        Example:
            >>> # Get the whole node as JSON
            >>> result = dag_ops.get("bafyreigs...", output_format='json')
            >>> if result['success']:
            >>>     print(result['data'])

            >>> # Get a specific field within the node
            >>> result_field = dag_ops.get("bafyreigs...", path="/name", output_format='json')
            >>> if result_field['success']:
            >>>     print(f"Name: {result_field['data']}")

            >>> # Get raw block data
            >>> result_raw = dag_ops.get("bafk...", output_format='raw')
            >>> if result_raw['success']:
            >>>     print(f"Raw data length: {len(result_raw['data'])}")
        """
        options = options or {}
        start_time = time.time()
        
        # Create the request parameters
        params = {
            "arg": f"{cid}{path}",
            "output-codec": output_format,
        }
        
        try:
            # Call the IPFS API
            response = self.connection_pool.post("dag/get", params=params)
            
            success = response.status_code == 200
            
            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("get", duration, success)
            
            if success:
                # Process response based on output format
                if output_format == "json":
                    try:
                        data = response.json()
                    except json.JSONDecodeError:
                        # Fall back to raw text
                        data = response.text
                else:
                    # For raw/cbor, return the binary data
                    data = response.content
                
                return {
                    "success": True,
                    "cid": cid,
                    "path": path,
                    "data": data,
                    "format": output_format,
                    "duration": duration,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get DAG node: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }
                
        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("get", duration, False)
            
            return {
                "success": False,
                "error": f"Error getting DAG node: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }
    
    def resolve(
        self,
        cid_path: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve an IPLD path to the CID it links to, returning the final CID
        and any remaining path components.

        This is useful for traversing complex DAG structures link by link or
        verifying the structure of linked data.

        Args:
            cid_path (str): An IPLD path string, combining a CID and an optional
                            path within the DAG node (e.g.,
                            "bafyreigs.../users/0/name", "bafk.../content").
            options (Optional[Dict[str, Any]]): Additional low-level options for the
                                                `dag/resolve` API endpoint.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
                            On success:
                                {'success': True, 'cid_path': <original_path>,
                                 'resolved_path': <resolved_CID_string>,
                                 'remainder': <remaining_path_string>,
                                 'duration': <float_seconds>}
                                 (Note: 'resolved_path' is the CID part, 'remainder'
                                  is the part of the path that couldn't be resolved
                                  within the linked blocks, if any).
                            On failure:
                                {'success': False, 'error': <error_message>, ...}

        Example:
            >>> # Resolve a path within a DAG
            >>> result = dag_ops.resolve("bafyreicq.../name")
            >>> if result['success']:
            >>>     print(f"Resolved CID: {result['resolved_path']}")
            >>>     print(f"Remainder Path: {result['remainder']}") # Usually empty if path fully resolves
        """
        options = options or {}
        start_time = time.time()
        
        # Create the request parameters
        params = {
            "arg": cid_path,
        }
        
        try:
            # Call the IPFS API
            response = self.connection_pool.post("dag/resolve", params=params)
            
            success = response.status_code == 200
            
            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("resolve", duration, success)
            
            if success:
                try:
                    response_json = response.json()
                    
                    return {
                        "success": True,
                        "cid_path": cid_path,
                        "resolved_path": response_json.get("Cid", {}).get("/"),
                        "remainder": response_json.get("RemPath", ""),
                        "duration": duration,
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid JSON response",
                        "details": response.text,
                        "duration": duration,
                    }
            else:
                return {
                    "success": False,
                    "error": f"Failed to resolve DAG path: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }
                
        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("resolve", duration, False)
            
            return {
                "success": False,
                "error": f"Error resolving DAG path: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }
    
    def stat(
        self,
        cid: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get statistics about a specific DAG node identified by its CID.

        Provides information like the total size of the node and the number of
        blocks it comprises (including linked blocks within its structure).

        Args:
            cid (str): The Content Identifier (CID) of the DAG node.
            options (Optional[Dict[str, Any]]): Additional low-level options for the
                                                `dag/stat` API endpoint.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
                            On success:
                                {'success': True, 'cid': <cid_string>,
                                 'size': <int_bytes>, 'num_blocks': <int>,
                                 'duration': <float_seconds>, 'details': <raw_api_response>}
                            On failure:
                                {'success': False, 'error': <error_message>, ...}

        Example:
            >>> result = dag_ops.stat("bafyreicq...")
            >>> if result['success']:
            >>>     print(f"DAG Size: {result['size']} bytes")
            >>>     print(f"Number of Blocks: {result['num_blocks']}")
        """
        options = options or {}
        start_time = time.time()
        
        # Create the request parameters
        params = {
            "arg": cid,
        }
        
        try:
            # Call the IPFS API
            response = self.connection_pool.post("dag/stat", params=params)
            
            success = response.status_code == 200
            
            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("stat", duration, success)
            
            if success:
                try:
                    response_json = response.json()
                    
                    return {
                        "success": True,
                        "cid": cid,
                        "size": response_json.get("Size", 0),
                        "num_blocks": response_json.get("NumBlocks", 0),
                        "duration": duration,
                        "details": response_json,
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid JSON response",
                        "details": response.text,
                        "duration": duration,
                    }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get DAG stats: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }
                
        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("stat", duration, False)
            
            return {
                "success": False,
                "error": f"Error getting DAG stats: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }
    
    def import_data(
        self,
        data: Union[Dict[str, Any], List[Any], str, bytes, BinaryIO],
        pin: bool = True,
        format_type: Union[IPLDFormat, str] = None,
        hash_alg: str = "sha2-256",
        input_encoding: str = "auto",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Import data into IPFS as IPLD DAG nodes.

        This method serves as a flexible entry point for adding various data types
        to the IPFS DAG. It automatically handles Python dicts/lists (as JSON),
        strings, bytes, and file-like objects (e.g., open file handles, CAR files).

        - For dicts, lists, strings, and bytes, it typically uses the `dag/put` API endpoint,
          allowing specification of IPLD format, input encoding, pinning, and hashing algorithm.
        - For file-like objects (detected via `isinstance(data, io.IOBase)`), it uses the
          `dag/import` API endpoint, which is suitable for importing CAR files.

        Args:
            data (Union[Dict, List, str, bytes, BinaryIO]): The data to import.
            pin (bool): Whether to pin the resulting root node(s). Defaults to True.
            format_type (Union[IPLDFormat, str], optional): The target IPLD format for `dag/put`.
                                                            Ignored for `dag/import`. Defaults to `self.default_format`.
            hash_alg (str): Hash algorithm for `dag/put`. Ignored for `dag/import`. Defaults to 'sha2-256'.
            input_encoding (str): Encoding for string/byte data for `dag/put`. Use 'auto'
                                  for automatic detection (json or raw). Defaults to 'auto'.
                                  Ignored for `dag/import`.
            options (Optional[Dict[str, Any]]): Additional options. For `dag/import`, can include
                                                `allow_big_block` (bool) and `silent` (bool).
                                                Passed through for `dag/put`.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
                            If `dag/put` was used:
                                {'success': True, 'cid': <CID_string>, ...} or {'success': False, ...}
                            If `dag/import` was used:
                                {'success': True, 'root_cids': [<CID1>, <CID2>...], 'stats': {...}, ...}
                                or {'success': False, ...}

        Example:
            >>> # Import a dictionary as dag-json
            >>> result_dict = dag_ops.import_data({'hello': 'world'})
            >>> print(result_dict.get('cid'))

            >>> # Import a CAR file
            >>> with open('my_dag.car', 'rb') as f:
            >>>     result_car = dag_ops.import_data(f)
            >>> print(result_car.get('root_cids'))
        """
        options = options or {}
        start_time = time.time()
        
        # Set default format if not specified
        if format_type is None:
            format_type = self.default_format
        
        # Convert enum to string if needed
        if isinstance(format_type, IPLDFormat):
            format_type = format_type.value

        # Resolve format_type before potentially calling self.put
        resolved_format_type = format_type if format_type is not None else self.default_format

        # Auto-detect encoding if needed
        if input_encoding == "auto":
            if isinstance(data, (dict, list)):
                input_encoding = "json"
            elif isinstance(data, str):
                try:
                    json.loads(data)
                    input_encoding = "json"
                except json.JSONDecodeError:
                    input_encoding = "raw"
            elif isinstance(data, bytes):
                try:
                    json.loads(data.decode("utf-8"))
                    input_encoding = "json"
                except (UnicodeDecodeError, json.JSONDecodeError):
                    input_encoding = "raw"
            else:
                # For file-like objects, default to raw
                input_encoding = "raw"

        # Handle file-like objects differently using isinstance check
        if isinstance(data, io.IOBase):
            # For file-like objects, we use dag/import
            logger.debug("Importing data from file-like object using dag/import.")
            try:
                # Create parameters for import
                params = {
                    "pin": "true" if pin else "false",
                    "hash": hash_alg,
                    "allow-big-block": "true" if options.get("allow_big_block", False) else "false",
                    "silent": "true" if options.get("silent", False) else "false",
                }
                
                # Call the IPFS API with the file
                response = self.connection_pool.post(
                    "dag/import",
                    files={"file": data},
                    params=params,
                )
                
                success = response.status_code == 200
                
                # Update metrics
                duration = time.time() - start_time
                self._update_metrics("import", duration, success)
                
                if success:
                    try:
                        response_json = response.json()
                        
                        # Extract root CIDs if available
                        root_cids = []
                        for result in response_json.get("Root", {}).get("Cids", []):
                            if "/" in result:
                                root_cids.append(result["/"])
                        
                        return {
                            "success": True,
                            "root_cids": root_cids,
                            "stats": response_json.get("Stats", {}),
                            "pinned": pin,
                            "duration": duration,
                            "details": response_json,
                        }
                    except json.JSONDecodeError:
                        return {
                            "success": False,
                            "error": "Invalid JSON response",
                            "details": response.text,
                            "duration": duration,
                        }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to import DAG: {response.status_code}",
                        "details": response.text,
                        "duration": duration,
                    }
            except Exception as e:
                duration = time.time() - start_time
                self._update_metrics("import", duration, False)
                
                return {
                    "success": False,
                    "error": f"Error importing DAG: {str(e)}",
                    "exception": str(e),
                    "duration": duration,
                }
        else:
            # For other data types, use dag/put with the resolved format type
            logger.debug(f"Importing data using dag/put with format: {resolved_format_type}")
            return self.put( # type: ignore
                data=data,
                format_type=resolved_format_type, # Use resolved format
                input_encoding=input_encoding,
                pin=pin,
                hash_alg=hash_alg,
                options=options,
            )
    
    def export_data(
        self,
        cid: str,
        output_file: Optional[Union[str, BinaryIO]] = None,
        progress: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Export an IPLD DAG rooted at a given CID as a CAR (Content Addressable aRchive) file/stream.

        CAR files are a standard format for bundling IPLD blocks, often used for backups,
        transfers, or offline storage.

        Args:
            cid (str): The root Content Identifier (CID) of the DAG to export.
            output_file (Optional[Union[str, BinaryIO]]): Destination for the CAR data.
                - If a string path is provided, the CAR data will be written to that file.
                - If a file-like object (with a `write` method) is provided, the data
                  will be written to that object.
                - If None (default), the raw CAR data (bytes) will be returned in the
                  result dictionary under the 'data' key.
            progress (bool): If True, includes progress information in the response stream
                             (primarily useful for streaming applications, not fully captured here).
                             Defaults to False.
            options (Optional[Dict[str, Any]]): Additional low-level options for the
                                                `dag/export` API endpoint.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
                            If writing to file:
                                {'success': True, 'cid': <root_cid>, 'output_file': <path>, ...}
                            If writing to stream:
                                {'success': True, 'cid': <root_cid>, ...}
                            If returning data:
                                {'success': True, 'cid': <root_cid>, 'data': <car_bytes>, ...}
                            On failure:
                                {'success': False, 'error': <error_message>, ...}

        Example:
            >>> # Export DAG to a file
            >>> result_file = dag_ops.export_data("bafyreicq...", output_file="my_dag_export.car")
            >>> if result_file['success']:
            >>>     print(f"Exported DAG to {result_file['output_file']}")

            >>> # Get CAR data as bytes
            >>> result_bytes = dag_ops.export_data("bafyreicq...")
            >>> if result_bytes['success']:
            >>>     print(f"Exported CAR data length: {len(result_bytes['data'])}")
        """
        options = options or {}
        start_time = time.time()
        
        # Create the request parameters
        params = {
            "arg": cid,
            "progress": "true" if progress else "false",
        }
        
        try:
            # Determine if we're writing to a file or returning data
            if output_file is not None:
                # If string, it's a file path
                if isinstance(output_file, str):
                    with open(output_file, "wb") as f:
                        response = self.connection_pool.post(
                            "dag/export",
                            params=params,
                            stream=True,
                        )
                        
                        success = response.status_code == 200
                        
                        if success:
                            # Stream response to file
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        else:
                            # Update metrics
                            duration = time.time() - start_time
                            self._update_metrics("export", duration, False)
                            
                            return {
                                "success": False,
                                "error": f"Failed to export DAG: {response.status_code}",
                                "details": response.text,
                                "duration": duration,
                            }
                        
                    # Update metrics
                    duration = time.time() - start_time
                    self._update_metrics("export", duration, True)
                    
                    return {
                        "success": True,
                        "cid": cid,
                        "output_file": output_file,
                        "duration": duration,
                    }
                elif hasattr(output_file, 'write') and callable(output_file.write):
                    # It's a file-like object
                    response = self.connection_pool.post(
                        "dag/export",
                        params=params,
                        stream=True,
                    )
                    
                    success = response.status_code == 200
                    
                    if success:
                        # Stream response to file-like object
                        for chunk in response.iter_content(chunk_size=8192):
                            output_file.write(chunk)
                    else:
                        # Update metrics
                        duration = time.time() - start_time
                        self._update_metrics("export", duration, False)
                        
                        return {
                            "success": False,
                            "error": f"Failed to export DAG: {response.status_code}",
                            "details": response.text,
                            "duration": duration,
                        }
                    
                    # Update metrics
                    duration = time.time() - start_time
                    self._update_metrics("export", duration, True)
                    
                    return {
                        "success": True,
                        "cid": cid,
                        "duration": duration,
                    }
                else:
                    # Invalid output_file parameter
                    duration = time.time() - start_time
                    self._update_metrics("export", duration, False)
                    
                    return {
                        "success": False,
                        "error": f"Invalid output_file parameter: {type(output_file)}",
                        "duration": duration,
                    }
            else:
                # Return the data directly
                response = self.connection_pool.post("dag/export", params=params)
                
                success = response.status_code == 200
                
                # Update metrics
                duration = time.time() - start_time
                self._update_metrics("export", duration, success)
                
                if success:
                    return {
                        "success": True,
                        "cid": cid,
                        "data": response.content,
                        "content_type": response.headers.get("Content-Type", ""),
                        "duration": duration,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to export DAG: {response.status_code}",
                        "details": response.text,
                        "duration": duration,
                    }
                
        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("export", duration, False)
            
            return {
                "success": False,
                "error": f"Error exporting DAG: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }
    
    def create_tree(
        self,
        data: Dict[str, Any],
        format_type: Union[IPLDFormat, str] = None,
        pin: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a tree structure in the DAG.
        
        This helper method builds a complex tree structure from nested data.
        
        Args:
            data: The hierarchical data to store
            format_type: IPLD format to use
            pin: Whether to pin the nodes
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # Use the standard put method for the root
        result = self.put(
            data=data,
            format_type=format_type,
            pin=pin,
            options=options,
        )
        
        duration = time.time() - start_time
        
        if result["success"]:
            result["duration"] = duration
            result["operation"] = "create_tree"
            return result
        else:
            return {
                "success": False,
                "error": f"Failed to create DAG tree: {result['error']}",
                "details": result,
                "duration": duration,
            }
    
    def get_tree(
        self,
        cid: str,
        max_depth: int = -1,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve a complete tree structure from the DAG.
        
        This traverses a DAG structure to the specified depth.
        
        Args:
            cid: The root CID of the tree
            max_depth: Maximum depth to traverse (-1 for unlimited)
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # Function to recursively traverse the DAG
        def traverse_dag(current_cid, current_depth=0):
            if max_depth >= 0 and current_depth > max_depth:
                return None
            
            # Get the node data
            get_result = self.get(current_cid)
            if not get_result["success"]:
                return None
            
            node_data = get_result["data"]
            
            # If not a dict or list, we've reached a leaf
            if not isinstance(node_data, (dict, list)):
                return node_data
            
            # For dictionaries, traverse links
            if isinstance(node_data, dict):
                result = {}
                for key, value in node_data.items():
                    # Check if value is a CID link
                    if isinstance(value, dict) and "/" in value:
                        # Recurse to get linked node
                        linked_cid = value["/"]
                        linked_data = traverse_dag(linked_cid, current_depth + 1)
                        result[key] = linked_data
                    else:
                        result[key] = value
                return result
            
            # For lists, traverse each item
            if isinstance(node_data, list):
                result = []
                for item in node_data:
                    # Check if item is a CID link
                    if isinstance(item, dict) and "/" in item:
                        # Recurse to get linked node
                        linked_cid = item["/"]
                        linked_data = traverse_dag(linked_cid, current_depth + 1)
                        result.append(linked_data)
                    else:
                        result.append(item)
                return result
        
        # Start traversal from root
        tree_data = traverse_dag(cid)
        
        duration = time.time() - start_time
        
        if tree_data is not None:
            return {
                "success": True,
                "cid": cid,
                "data": tree_data,
                "max_depth": max_depth,
                "duration": duration,
            }
        else:
            return {
                "success": False,
                "error": "Failed to traverse DAG tree",
                "cid": cid,
                "duration": duration,
            }
    
    def update_node(
        self,
        cid: str,
        updates: Dict[str, Any],
        format_type: Union[IPLDFormat, str] = None,
        pin: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update a DAG node with new values.
        
        This creates a new node with updated values while preserving the rest.
        
        Args:
            cid: The CID of the node to update
            updates: Dictionary of key-value pairs to update
            format_type: IPLD format to use for the new node
            pin: Whether to pin the new node
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # Get the existing node
        get_result = self.get(cid)
        if not get_result["success"]:
            duration = time.time() - start_time
            return {
                "success": False,
                "error": f"Failed to get original node: {get_result['error']}",
                "details": get_result,
                "duration": duration,
            }
        
        # Ensure the data is a dictionary
        original_data = get_result["data"]
        if not isinstance(original_data, dict):
            duration = time.time() - start_time
            return {
                "success": False,
                "error": "Cannot update non-dictionary node",
                "duration": duration,
            }
        
        # Create a new node with updated values
        new_data = {**original_data, **updates}
        # Resolve format_type before calling put
        resolved_format_type = format_type if format_type is not None else self.default_format

        # Put the updated node
        put_result = self.put( # type: ignore
            data=new_data,
            format_type=resolved_format_type, # Use resolved format
            pin=pin,
            options=options,
        )
        
        duration = time.time() - start_time
        
        if put_result["success"]:
            return {
                "success": True,
                "old_cid": cid,
                "new_cid": put_result["cid"],
                "updated_keys": list(updates.keys()),
                "duration": duration,
            }
        else:
            return {
                "success": False,
                "error": f"Failed to create updated node: {put_result['error']}",
                "details": put_result,
                "duration": duration,
            }
    
    def add_link(
        self,
        parent_cid: str,
        name: str,
        child_cid: str,
        format_type: Union[IPLDFormat, str] = None,
        pin: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a link from a parent node to a child node.
        
        This creates a new parent node with the additional link.
        
        Args:
            parent_cid: The CID of the parent node
            name: The name for the link
            child_cid: The CID of the child node to link to
            format_type: IPLD format to use for the new parent
            pin: Whether to pin the new parent
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # Get the parent node
        get_result = self.get(parent_cid)
        if not get_result["success"]:
            duration = time.time() - start_time
            return {
                "success": False,
                "error": f"Failed to get parent node: {get_result['error']}",
                "details": get_result,
                "duration": duration,
            }
        
        # Ensure the parent data is a dictionary
        parent_data = get_result["data"]
        if not isinstance(parent_data, dict):
            duration = time.time() - start_time
            return {
                "success": False,
                "error": "Parent node must be a dictionary to add links",
                "duration": duration,
            }
        
        # Create CID link format
        child_link = {"/"
        : child_cid}
        
        # Create a new parent with the additional link
        new_parent = {**parent_data, name: child_link}
        # Resolve format_type before calling put
        resolved_format_type = format_type if format_type is not None else self.default_format

        # Put the updated parent
        put_result = self.put( # type: ignore
            data=new_parent,
            format_type=resolved_format_type, # Use resolved format
            pin=pin,
            options=options,
        )
        
        duration = time.time() - start_time
        
        if put_result["success"]:
            return {
                "success": True,
                "parent_cid": parent_cid,
                "new_parent_cid": put_result["cid"],
                "child_cid": child_cid,
                "link_name": name,
                "duration": duration,
            }
        else:
            return {
                "success": False,
                "error": f"Failed to create updated parent: {put_result['error']}",
                "details": put_result,
                "duration": duration,
            }
    
    def remove_link(
        self,
        parent_cid: str,
        name: str,
        format_type: Union[IPLDFormat, str] = None,
        pin: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Remove a link from a parent node.
        
        This creates a new parent node without the specified link.
        
        Args:
            parent_cid: The CID of the parent node
            name: The name of the link to remove
            format_type: IPLD format to use for the new parent
            pin: Whether to pin the new parent
            options: Additional options for the operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # Get the parent node
        get_result = self.get(parent_cid)
        if not get_result["success"]:
            duration = time.time() - start_time
            return {
                "success": False,
                "error": f"Failed to get parent node: {get_result['error']}",
                "details": get_result,
                "duration": duration,
            }
        
        # Ensure the parent data is a dictionary
        parent_data = get_result["data"]
        if not isinstance(parent_data, dict):
            duration = time.time() - start_time
            return {
                "success": False,
                "error": "Parent node must be a dictionary to remove links",
                "duration": duration,
            }
        
        # Check if the link exists
        if name not in parent_data:
            duration = time.time() - start_time
            return {
                "success": False,
                "error": f"Link '{name}' not found in parent node",
                "duration": duration,
            }
        
        # Create a new parent without the link
        new_parent = {k: v for k, v in parent_data.items() if k != name}
        # Resolve format_type before calling put
        resolved_format_type = format_type if format_type is not None else self.default_format

        # Put the updated parent
        put_result = self.put( # type: ignore
            data=new_parent,
            format_type=resolved_format_type, # Use resolved format
            pin=pin,
            options=options,
        )
        
        duration = time.time() - start_time
        
        if put_result["success"]:
            return {
                "success": True,
                "parent_cid": parent_cid,
                "new_parent_cid": put_result["cid"],
                "removed_link": name,
                "duration": duration,
            }
        else:
            return {
                "success": False,
                "error": f"Failed to create updated parent: {put_result['error']}",
                "details": put_result,
                "duration": duration,
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for DAG operations.
        
        Returns:
            Dictionary with performance metrics
        """
        return {
            "success": True,
            "metrics": self.performance_metrics,
        }

# Global instance
_instance = None

def get_instance(connection_pool=None, config=None) -> DAGOperations:
    """Get or create a singleton instance of the DAG operations."""
    global _instance
    if _instance is None:
        _instance = DAGOperations(connection_pool, config)
    return _instance
