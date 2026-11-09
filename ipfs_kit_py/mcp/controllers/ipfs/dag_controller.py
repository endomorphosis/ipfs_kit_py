"""
DAG Controller for the MCP server.

This controller provides an interface to the DAG functionality of IPFS through the MCP API.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Body, Path, Query, Response

# Import the DAG operations
import ipfs_dag_operations

# Configure logger
logger = logging.getLogger(__name__)

class DAGController:
    """
    Controller for DAG operations.

    Handles HTTP requests related to DAG operations and delegates
    the business logic to the DAG operations model.
    """

    def __init__(self, dag_operations=None):
        """
        Initialize the DAG controller.

        Args:
            dag_operations: DAG operations model to use for operations
        """
        self.dag_operations = dag_operations or ipfs_dag_operations.get_instance()
        logger.info("DAG Controller initialized")

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Add DAG route for putting data
        router.add_api_route(
            "/ipfs/dag/put",
            self.put_data,
            methods=["POST"],
            summary="Store data as a DAG node",
            description="Store data as a DAG node in IPFS and return the CID",
        )

        # Add DAG route for getting data
        router.add_api_route(
            "/ipfs/dag/get/{cid}",
            self.get_data,
            methods=["GET"],
            summary="Retrieve a DAG node",
            description="Get a DAG node from IPFS by CID",
        )

        # Add DAG route for getting data with a path
        router.add_api_route(
            "/ipfs/dag/get/{cid}/{path:path}",
            self.get_data_with_path,
            methods=["GET"],
            summary="Retrieve a DAG node with path",
            description="Get a DAG node from IPFS by CID and path within the node",
        )

        # Add DAG route for resolving a path
        router.add_api_route(
            "/ipfs/dag/resolve/{cid_path:path}",
            self.resolve_path,
            methods=["GET"],
            summary="Resolve an IPLD path to its CID",
            description="Resolve an IPLD path to its CID, returning the CID of the object it points to",
        )

        # Add DAG route for getting statistics
        router.add_api_route(
            "/ipfs/dag/stat/{cid}",
            self.get_stats,
            methods=["GET"],
            summary="Get statistics for a DAG node",
            description="Get statistics for a DAG node in IPFS",
        )

        # Add DAG route for importing data
        router.add_api_route(
            "/ipfs/dag/import",
            self.import_data,
            methods=["POST"],
            summary="Import data into the DAG",
            description="Import data into the DAG with support for various formats and options",
        )

        # Add DAG route for exporting data
        router.add_api_route(
            "/ipfs/dag/export/{cid}",
            self.export_data,
            methods=["GET"],
            summary="Export a DAG to a file",
            description="Export a DAG to a CAR file or stream",
        )

        # Add DAG route for creating a tree
        router.add_api_route(
            "/ipfs/dag/tree",
            self.create_tree,
            methods=["POST"],
            summary="Create a tree structure in the DAG",
            description="Create a complex tree structure from nested data in the DAG",
        )

        # Add DAG route for getting a tree
        router.add_api_route(
            "/ipfs/dag/tree/{cid}",
            self.get_tree,
            methods=["GET"],
            summary="Retrieve a complete tree structure from the DAG",
            description="Retrieve a complete tree structure from the DAG by traversing to the specified depth",
        )

        # Add DAG route for updating a node
        router.add_api_route(
            "/ipfs/dag/update",
            self.update_node,
            methods=["POST"],
            summary="Update a DAG node with new values",
            description="Update a DAG node with new values while preserving the rest",
        )

        # Add DAG route for adding a link
        router.add_api_route(
            "/ipfs/dag/add-link",
            self.add_link,
            methods=["POST"],
            summary="Add a link from a parent node to a child node",
            description="Add a link from a parent node to a child node, creating a new parent node with the additional link",
        )

        # Add DAG route for removing a link
        router.add_api_route(
            "/ipfs/dag/remove-link",
            self.remove_link,
            methods=["POST"],
            summary="Remove a link from a parent node",
            description="Remove a link from a parent node, creating a new parent node without the specified link",
        )

        # Add DAG route for metrics
        router.add_api_route(
            "/ipfs/dag/metrics",
            self.get_metrics,
            methods=["GET"],
            summary="Get DAG metrics",
            description="Get performance metrics for DAG operations",
        )

        logger.info("DAG Controller routes registered")

    async def put_data(
        self,
        data: Any = Body(...),
        format_type: str = Body("dag-json"),
        input_encoding: str = Body("json"),
        pin: bool = Body(True),
        hash_alg: str = Body("sha2-256"),
    ) -> Dict[str, Any]:
        """
        Store data as a DAG node.

        Args:
            data: The data to store
            format_type: IPLD format to use
            input_encoding: Encoding of input data
            pin: Whether to pin the node
            hash_alg: Hash algorithm to use

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Putting data in DAG, format: {format_type}, pin: {pin}")
        try:
            result = self.dag_operations.put(
                data=data,
                format_type=format_type,
                input_encoding=input_encoding,
                pin=pin,
                hash_alg=hash_alg,
            )
            return result
        except Exception as e:
            logger.error(f"Error putting data in DAG: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error putting data in DAG: {str(e)}"
            )

    async def get_data(
        self, cid: str, output_format: str = Query("json")
    ) -> Dict[str, Any]:
        """
        Retrieve a DAG node.

        Args:
            cid: The CID of the node to retrieve
            output_format: Output format ('json', 'raw', 'cbor')

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Getting data from DAG with CID: {cid}, format: {output_format}")
        try:
            result = self.dag_operations.get(cid=cid, output_format=output_format)
            return result
        except Exception as e:
            logger.error(f"Error getting data from DAG: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting data from DAG: {str(e)}"
            )

    async def get_data_with_path(
        self, cid: str, path: str, output_format: str = Query("json")
    ) -> Dict[str, Any]:
        """
        Retrieve a DAG node with a path.

        Args:
            cid: The CID of the node to retrieve
            path: Path within the node
            output_format: Output format ('json', 'raw', 'cbor')

        Returns:
            Dictionary with operation results
        """
        logger.debug(
            f"Getting data from DAG with CID: {cid}, path: {path}, format: {output_format}"
        )
        try:
            result = self.dag_operations.get(
                cid=cid, path=path, output_format=output_format
            )
            return result
        except Exception as e:
            logger.error(f"Error getting data from DAG with path: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error getting data from DAG with path: {str(e)}",
            )

    async def resolve_path(self, cid_path: str) -> Dict[str, Any]:
        """
        Resolve an IPLD path to its CID.

        Args:
            cid_path: CID with optional path to resolve

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Resolving DAG path: {cid_path}")
        try:
            result = self.dag_operations.resolve(cid_path=cid_path)
            return result
        except Exception as e:
            logger.error(f"Error resolving DAG path: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error resolving DAG path: {str(e)}"
            )

    async def get_stats(self, cid: str) -> Dict[str, Any]:
        """
        Get statistics for a DAG node.

        Args:
            cid: The CID of the node to get stats for

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Getting stats for DAG node with CID: {cid}")
        try:
            result = self.dag_operations.stat(cid=cid)
            return result
        except Exception as e:
            logger.error(f"Error getting DAG stats: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting DAG stats: {str(e)}"
            )

    async def import_data(
        self,
        data: Any = Body(...),
        pin: bool = Body(True),
        format_type: str = Body("dag-json"),
        hash_alg: str = Body("sha2-256"),
        input_encoding: str = Body("auto"),
    ) -> Dict[str, Any]:
        """
        Import data into the DAG.

        Args:
            data: The data to import
            pin: Whether to pin the imported data
            format_type: IPLD format to use
            hash_alg: Hash algorithm to use
            input_encoding: How to interpret the input

        Returns:
            Dictionary with operation results
        """
        logger.debug(
            f"Importing data into DAG, format: {format_type}, pin: {pin}, encoding: {input_encoding}"
        )
        try:
            result = self.dag_operations.import_data(
                data=data,
                pin=pin,
                format_type=format_type,
                hash_alg=hash_alg,
                input_encoding=input_encoding,
            )
            return result
        except Exception as e:
            logger.error(f"Error importing data into DAG: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error importing data into DAG: {str(e)}"
            )

    async def export_data(self, cid: str, progress: bool = Query(False)) -> Response:
        """
        Export a DAG to a file.

        Args:
            cid: The root CID to export
            progress: Whether to include progress information

        Returns:
            CAR file as a response
        """
        logger.debug(f"Exporting DAG with CID: {cid}")
        try:
            result = self.dag_operations.export_data(cid=cid, output_file=None, progress=progress)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500, detail=f"Error exporting DAG: {result.get('error', 'Unknown error')}"
                )
                
            data = result.get("data")
            if not data:
                raise HTTPException(
                    status_code=500, detail="No data returned from export operation"
                )
                
            # Return the data as a downloadable file
            headers = {
                "Content-Disposition": f'attachment; filename="{cid}.car"',
                "Content-Type": "application/vnd.ipld.car",
            }
            
            return Response(content=data, headers=headers)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error exporting DAG: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error exporting DAG: {str(e)}"
            )

    async def create_tree(
        self,
        data: Dict[str, Any] = Body(...),
        format_type: str = Body("dag-json"),
        pin: bool = Body(True),
    ) -> Dict[str, Any]:
        """
        Create a tree structure in the DAG.

        Args:
            data: The hierarchical data to store
            format_type: IPLD format to use
            pin: Whether to pin the nodes

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Creating tree in DAG, format: {format_type}, pin: {pin}")
        try:
            result = self.dag_operations.create_tree(
                data=data, format_type=format_type, pin=pin
            )
            return result
        except Exception as e:
            logger.error(f"Error creating DAG tree: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating DAG tree: {str(e)}"
            )

    async def get_tree(
        self, cid: str, max_depth: int = Query(-1)
    ) -> Dict[str, Any]:
        """
        Retrieve a complete tree structure from the DAG.

        Args:
            cid: The root CID of the tree
            max_depth: Maximum depth to traverse (-1 for unlimited)

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Getting tree from DAG with CID: {cid}, max_depth: {max_depth}")
        try:
            result = self.dag_operations.get_tree(cid=cid, max_depth=max_depth)
            return result
        except Exception as e:
            logger.error(f"Error getting DAG tree: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting DAG tree: {str(e)}"
            )

    async def update_node(
        self,
        cid: str = Body(...),
        updates: Dict[str, Any] = Body(...),
        format_type: str = Body("dag-json"),
        pin: bool = Body(True),
    ) -> Dict[str, Any]:
        """
        Update a DAG node with new values.

        Args:
            cid: The CID of the node to update
            updates: Dictionary of key-value pairs to update
            format_type: IPLD format to use for the new node
            pin: Whether to pin the new node

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Updating DAG node with CID: {cid}")
        try:
            result = self.dag_operations.update_node(
                cid=cid, updates=updates, format_type=format_type, pin=pin
            )
            return result
        except Exception as e:
            logger.error(f"Error updating DAG node: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error updating DAG node: {str(e)}"
            )

    async def add_link(
        self,
        parent_cid: str = Body(...),
        name: str = Body(...),
        child_cid: str = Body(...),
        format_type: str = Body("dag-json"),
        pin: bool = Body(True),
    ) -> Dict[str, Any]:
        """
        Add a link from a parent node to a child node.

        Args:
            parent_cid: The CID of the parent node
            name: The name for the link
            child_cid: The CID of the child node to link to
            format_type: IPLD format to use for the new parent
            pin: Whether to pin the new parent

        Returns:
            Dictionary with operation results
        """
        logger.debug(
            f"Adding link from parent {parent_cid} to child {child_cid} with name {name}"
        )
        try:
            result = self.dag_operations.add_link(
                parent_cid=parent_cid,
                name=name,
                child_cid=child_cid,
                format_type=format_type,
                pin=pin,
            )
            return result
        except Exception as e:
            logger.error(f"Error adding link to DAG node: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error adding link to DAG node: {str(e)}"
            )

    async def remove_link(
        self,
        parent_cid: str = Body(...),
        name: str = Body(...),
        format_type: str = Body("dag-json"),
        pin: bool = Body(True),
    ) -> Dict[str, Any]:
        """
        Remove a link from a parent node.

        Args:
            parent_cid: The CID of the parent node
            name: The name of the link to remove
            format_type: IPLD format to use for the new parent
            pin: Whether to pin the new parent

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Removing link {name} from parent {parent_cid}")
        try:
            result = self.dag_operations.remove_link(
                parent_cid=parent_cid, name=name, format_type=format_type, pin=pin
            )
            return result
        except Exception as e:
            logger.error(f"Error removing link from DAG node: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error removing link from DAG node: {str(e)}"
            )

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for DAG operations.

        Returns:
            Dictionary with performance metrics
        """
        logger.debug("Getting DAG performance metrics")
        try:
            result = self.dag_operations.get_metrics()
            return result
        except Exception as e:
            logger.error(f"Error getting DAG metrics: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error getting DAG metrics: {str(e)}"
            )
