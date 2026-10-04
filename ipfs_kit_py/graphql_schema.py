"""
GraphQL schema for IPFS Kit.

This module defines the GraphQL schema and resolvers for the IPFS Kit API,
enabling flexible client-side querying capabilities.

Key features:
1. Unified GraphQL schema for all IPFS Kit operations
2. Type-safe queries with introspection
3. Efficient data fetching with field selection
4. Complex nested queries and relationships
5. Mutations for content management operations
6. Subscriptions for real-time updates (if supported)
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union

try:
    # Import GraphQL libraries
    import graphene
    from graphene import ID, Boolean, Field, Float, Int
    from graphene import List as GrapheneList
    from graphene import Mutation, ObjectType, Schema, String

    GRAPHQL_AVAILABLE = True
except ImportError:
    # Create stub types to avoid errors when GraphQL is not available
    GRAPHQL_AVAILABLE = False

    class ObjectType:
        pass

    class Mutation:
        pass

    class Field:
        pass

    class ID:
        pass

    class String:
        pass

    class Int:
        pass

    class Float:
        pass

    class Boolean:
        pass

    class GrapheneList:
        pass

    class Schema:
        pass


# Initialize logger
logger = logging.getLogger(__name__)

if GRAPHQL_AVAILABLE:
    # Define GraphQL Types

    class IPFSMetadata(ObjectType):
        """Metadata for IPFS content."""

        size = Int(description="Size of the content in bytes")
        block_count = Int(description="Number of blocks in the content")
        last_modified = String(description="Last modified timestamp")
        content_type = String(description="Content type (MIME type)")

    class PinInfo(ObjectType):
        """Information about a pinned CID."""

        type = String(description="Type of pin (recursive, direct, indirect)")
        pinned_at = Float(description="Timestamp when the content was pinned")

    class IPFSContent(ObjectType):
        """Representation of IPFS content."""

        cid = ID(description="Content identifier (CID)")
        name = String(description="Name or path of the content")
        is_directory = Boolean(description="Whether the content is a directory")
        size = Int(description="Size of the content in bytes")
        pinned = Boolean(description="Whether the content is pinned locally")
        pin_info = Field(PinInfo, description="Detailed pin information")
        metadata = Field(IPFSMetadata, description="Metadata about the content")

    class DirectoryItem(ObjectType):
        """An item in a directory listing."""

        name = String(description="Name of the item")
        cid = ID(description="Content identifier (CID)")
        size = Int(description="Size in bytes")
        is_directory = Boolean(description="Whether the item is a directory")
        path = String(description="Full path to the item")

    class PeerInfo(ObjectType):
        """Information about a connected peer."""

        peer_id = ID(description="Peer ID")
        address = String(description="Multiaddress of the peer")
        direction = String(description="Connection direction (inbound/outbound)")
        latency = String(description="Connection latency")

    class ClusterPeerInfo(ObjectType):
        """Information about a cluster peer."""

        peer_id = ID(description="Peer ID")
        addresses = GrapheneList(String, description="Multiaddresses of the peer")
        name = String(description="Name of the peer")
        version = String(description="Version of the peer software")

    class ClusterPinStatus(ObjectType):
        """Status of a pin in the cluster."""

        cid = ID(description="Content identifier (CID)")
        status = String(description="Status of the pin (pinned, pinning, pin_error, unpinned)")
        timestamp = Float(description="Timestamp of the status update")
        peer_id = ID(description="Peer ID responsible for this status")
        error = String(description="Error message if status is pin_error")

    class IPNSInfo(ObjectType):
        """Information about an IPNS name."""

        name = ID(description="IPNS name")
        value = String(description="IPFS path that the name points to")
        sequence = Int(description="Sequence number")
        validity = String(description="Validity duration")

    class KeyInfo(ObjectType):
        """Information about a key."""

        name = String(description="Name of the key")
        id = ID(description="ID of the key")

    class AIModel(ObjectType):
        """Information about an AI model."""

        name = String(description="Name of the model")
        version = String(description="Version of the model")
        framework = String(description="Framework used (e.g., 'pytorch', 'tensorflow')")
        cid = ID(description="Content identifier (CID)")
        description = String(description="Description of the model")
        tags = GrapheneList(String, description="Tags for the model")

    class AIDataset(ObjectType):
        """Information about an AI dataset."""

        name = String(description="Name of the dataset")
        version = String(description="Version of the dataset")
        format = String(description="Format of the dataset")
        cid = ID(description="Content identifier (CID)")
        description = String(description="Description of the dataset")
        tags = GrapheneList(String, description="Tags for the dataset")

    # Query Root
    class Query(ObjectType):
        """Root query type for IPFS operations."""

        # Content operations
        content = Field(
            IPFSContent,
            cid=String(required=True, description="Content identifier (CID)"),
            description="Get information about content by CID",
        )

        directory = GrapheneList(
            DirectoryItem,
            path=String(required=True, description="IPFS path or CID to list"),
            description="List directory contents",
        )

        # Pin operations
        pins = GrapheneList(
            IPFSContent,
            type=String(description="Type of pins to list (recursive, direct, indirect, all)"),
            description="List pinned content",
        )

        # Network operations
        peers = GrapheneList(PeerInfo, description="List connected peers")

        # Cluster operations
        cluster_peers = GrapheneList(ClusterPeerInfo, description="List cluster peers")

        cluster_pins = GrapheneList(ClusterPinStatus, description="List pins in the cluster")

        cluster_status = Field(
            ClusterPinStatus,
            cid=String(required=True, description="Content identifier (CID)"),
            description="Get cluster status for a CID",
        )

        # IPNS operations
        ipns_names = GrapheneList(IPNSInfo, description="List all IPNS names")

        resolve_ipns = Field(
            String,
            name=String(required=True, description="IPNS name to resolve"),
            description="Resolve an IPNS name to an IPFS path",
        )

        # Key operations
        keys = GrapheneList(KeyInfo, description="List all keys")

        # AI/ML operations
        ai_models = GrapheneList(
            AIModel,
            framework=String(description="Filter by framework"),
            tags=String(description="Filter by comma-separated tags"),
            query=String(description="Free text search"),
            description="List AI models",
        )

        ai_datasets = GrapheneList(
            AIDataset,
            format=String(description="Filter by format"),
            tags=String(description="Filter by comma-separated tags"),
            query=String(description="Free text search"),
            description="List AI datasets",
        )

        # System operations
        version = String(description="Get IPFS version information")

        # Resolver methods
        def resolve_content(self, info, cid):
            """Resolve content by CID."""
            api = info.context["api"]
            try:
                # Get content info
                result = api.kit.ipfs_object_stat(cid)

                # Get pin info
                pin_result = api.kit.ipfs_pin_ls(cid, type="direct")
                pinned = False
                pin_info = None

                if "Keys" in pin_result and cid in pin_result["Keys"]:
                    pinned = True
                    pin_type = pin_result["Keys"][cid]["Type"]
                    pin_info = PinInfo(
                        type=pin_type, pinned_at=time.time()  # IPFS doesn't provide pinning time
                    )

                # Get metadata
                metadata = IPFSMetadata(
                    size=result.get("CumulativeSize", 0),
                    block_count=result.get("NumLinks", 0),
                    last_modified=None,  # IPFS doesn't store this
                    content_type=None,  # Would need to be determined elsewhere
                )

                return IPFSContent(
                    cid=cid,
                    name=None,  # Would need path context
                    is_directory=result.get("NumLinks", 0) > 0,
                    size=result.get("CumulativeSize", 0),
                    pinned=pinned,
                    pin_info=pin_info,
                    metadata=metadata,
                )
            except Exception as e:
                logger.error(f"Error resolving content {cid}: {str(e)}")
                return None

        def resolve_directory(self, info, path):
            """Resolve directory contents."""
            api = info.context["api"]
            try:
                result = api.kit.ipfs_ls(path)

                items = []
                if "Objects" in result and len(result["Objects"]) > 0:
                    for item in result["Objects"][0].get("Links", []):
                        items.append(
                            DirectoryItem(
                                name=item.get("Name", ""),
                                cid=item.get("Hash", ""),
                                size=item.get("Size", 0),
                                is_directory=item.get("Type", "") == "dir",
                                path=f"{path}/{item.get('Name', '')}",
                            )
                        )

                return items
            except Exception as e:
                logger.error(f"Error listing directory {path}: {str(e)}")
                return []

        def resolve_pins(self, info, type="all"):
            """Resolve list of pinned content."""
            api = info.context["api"]
            try:
                result = api.kit.ipfs_pin_ls(type=type)

                pins = []
                if "Keys" in result:
                    for cid, pin_data in result["Keys"].items():
                        pin_type = pin_data.get("Type", "recursive")
                        pin_info = PinInfo(
                            type=pin_type,
                            pinned_at=time.time(),  # IPFS doesn't provide pinning time
                        )

                        pins.append(
                            IPFSContent(
                                cid=cid,
                                name=None,  # Would need additional context
                                is_directory=False,  # Would need additional stat call
                                size=0,  # Would need additional stat call
                                pinned=True,
                                pin_info=pin_info,
                                metadata=None,  # Would need additional stat call
                            )
                        )

                return pins
            except Exception as e:
                logger.error(f"Error listing pins: {str(e)}")
                return []

        def resolve_peers(self, info):
            """Resolve list of connected peers."""
            api = info.context["api"]
            try:
                result = api.kit.ipfs_swarm_peers()

                peers = []
                if "Peers" in result:
                    for peer_data in result["Peers"]:
                        peers.append(
                            PeerInfo(
                                peer_id=peer_data.get("Peer", ""),
                                address=peer_data.get("Addr", ""),
                                direction=None,  # Not in standard output
                                latency=None,  # Not in standard output
                            )
                        )

                return peers
            except Exception as e:
                logger.error(f"Error listing peers: {str(e)}")
                return []

        def resolve_cluster_peers(self, info):
            """Resolve list of cluster peers."""
            api = info.context["api"]
            try:
                result = api.kit.ipfs_cluster_peers()

                peers = []
                if "cluster_peers" in result and isinstance(result["cluster_peers"], list):
                    for peer_data in result["cluster_peers"]:
                        if isinstance(peer_data, dict):
                            peers.append(
                                ClusterPeerInfo(
                                    peer_id=peer_data.get("id", ""),
                                    addresses=peer_data.get("addresses", []),
                                    name=peer_data.get("peername", ""),
                                    version=peer_data.get("version", ""),
                                )
                            )

                return peers
            except Exception as e:
                logger.error(f"Error listing cluster peers: {str(e)}")
                return []

        def resolve_cluster_pins(self, info):
            """Resolve list of pins in the cluster."""
            api = info.context["api"]
            try:
                result = api.kit.ipfs_cluster_status_all()

                pins = []
                # The structure of the result depends on the IPFS Cluster version
                # This handles both the old and new formats
                if isinstance(result, dict) and "pins" in result:
                    pin_list = result["pins"]
                    for pin_data in pin_list:
                        cid = pin_data.get("cid", "")
                        status = pin_data.get("status", "unknown")

                        pins.append(
                            ClusterPinStatus(
                                cid=cid,
                                status=status,
                                timestamp=time.time(),
                                peer_id=None,  # Simplified output
                                error=None,  # Simplified output
                            )
                        )

                return pins
            except Exception as e:
                logger.error(f"Error listing cluster pins: {str(e)}")
                return []

        def resolve_cluster_status(self, info, cid):
            """Resolve cluster status for a CID."""
            api = info.context["api"]
            try:
                result = api.kit.ipfs_cluster_status(cid)

                status = "unknown"
                error = None
                peer_id = None

                # Extract status information from the result
                if "status" in result:
                    status = result["status"]

                return ClusterPinStatus(
                    cid=cid, status=status, timestamp=time.time(), peer_id=peer_id, error=error
                )
            except Exception as e:
                logger.error(f"Error getting cluster status for {cid}: {str(e)}")
                return None

        def resolve_ipns_names(self, info):
            """Resolve list of IPNS names."""
            api = info.context["api"]
            try:
                result = api.kit.ipfs_key_list()

                names = []
                if "Keys" in result:
                    for name, key_id in result["Keys"].items():
                        names.append(
                            IPNSInfo(
                                name=name,
                                value=f"/ipns/{key_id}",
                                sequence=0,  # Not available in this context
                                validity="24h",  # Default value
                            )
                        )

                return names
            except Exception as e:
                logger.error(f"Error listing IPNS names: {str(e)}")
                return []

        def resolve_resolve_ipns(self, info, name):
            """Resolve an IPNS name to an IPFS path."""
            api = info.context["api"]
            try:
                result = api.kit.ipfs_name_resolve(name)

                if "Path" in result:
                    return result["Path"]
                return None
            except Exception as e:
                logger.error(f"Error resolving IPNS name {name}: {str(e)}")
                return None

        def resolve_keys(self, info):
            """Resolve list of keys."""
            api = info.context["api"]
            try:
                result = api.kit.ipfs_key_list()

                keys = []
                if "Keys" in result:
                    for name, key_id in result["Keys"].items():
                        keys.append(KeyInfo(name=name, id=key_id))

                return keys
            except Exception as e:
                logger.error(f"Error listing keys: {str(e)}")
                return []

        def resolve_ai_models(self, info, framework=None, tags=None, query=None):
            """Resolve list of AI models."""
            api = info.context["api"]
            try:
                # Check if AI/ML integration is available
                if not hasattr(api, "ai_model_list"):
                    return []

                result = api.ai_model_list()

                models = []
                if "models" in result:
                    model_dict = result["models"]

                    for model_name, versions in model_dict.items():
                        # Get the most recent version
                        if versions:
                            latest = versions[0]  # Assuming sorted by version

                            # Apply filters if specified
                            if framework and latest.get("framework") != framework:
                                continue

                            if tags:
                                tag_list = tags.split(",")
                                model_tags = latest.get("metadata", {}).get("tags", [])
                                if not all(tag in model_tags for tag in tag_list):
                                    continue

                            if query:
                                metadata = latest.get("metadata", {})
                                search_text = (
                                    f"{model_name} {metadata.get('description', '')} "
                                    f"{' '.join(metadata.get('tags', []))}"
                                ).lower()

                                if query.lower() not in search_text:
                                    continue

                            # Add model to results
                            models.append(
                                AIModel(
                                    name=model_name,
                                    version=latest.get("version", "1.0.0"),
                                    framework=latest.get("framework"),
                                    cid=latest.get("cid"),
                                    description=latest.get("metadata", {}).get("description"),
                                    tags=latest.get("metadata", {}).get("tags", []),
                                )
                            )

                return models
            except Exception as e:
                logger.error(f"Error listing AI models: {str(e)}")
                return []

        def resolve_ai_datasets(self, info, format=None, tags=None, query=None):
            """Resolve list of AI datasets."""
            api = info.context["api"]
            try:
                # Check if AI/ML integration is available
                if not hasattr(api, "ai_dataset_list"):
                    return []

                result = api.ai_dataset_list()

                datasets = []
                if "datasets" in result:
                    dataset_dict = result["datasets"]

                    for dataset_name, versions in dataset_dict.items():
                        # Get the most recent version
                        if versions:
                            latest = versions[0]  # Assuming sorted by version

                            # Apply filters if specified
                            if format and latest.get("format") != format:
                                continue

                            if tags:
                                tag_list = tags.split(",")
                                dataset_tags = latest.get("metadata", {}).get("tags", [])
                                if not all(tag in dataset_tags for tag in tag_list):
                                    continue

                            if query:
                                metadata = latest.get("metadata", {})
                                search_text = (
                                    f"{dataset_name} {metadata.get('description', '')} "
                                    f"{' '.join(metadata.get('tags', []))}"
                                ).lower()

                                if query.lower() not in search_text:
                                    continue

                            # Add dataset to results
                            datasets.append(
                                AIDataset(
                                    name=dataset_name,
                                    version=latest.get("version", "1.0.0"),
                                    format=latest.get("format"),
                                    cid=latest.get("cid"),
                                    description=latest.get("metadata", {}).get("description"),
                                    tags=latest.get("metadata", {}).get("tags", []),
                                )
                            )

                return datasets
            except Exception as e:
                logger.error(f"Error listing AI datasets: {str(e)}")
                return []

        def resolve_version(self, info):
            """Resolve IPFS version information."""
            api = info.context["api"]
            try:
                result = api.kit.ipfs_version()

                if "Version" in result:
                    return result["Version"]
                return None
            except Exception as e:
                logger.error(f"Error getting IPFS version: {str(e)}")
                return None

    # Mutation Root
    class AddContentMutation(Mutation):
        """Mutation to add content to IPFS."""

        class Arguments:
            content = String(
                required=True, description="Content to add (base64 encoded for binary data)"
            )
            filename = String(description="Filename for the content")
            pin = Boolean(description="Whether to pin the content")

        # Return fields
        success = Boolean(description="Whether the operation was successful")
        cid = String(description="Content identifier (CID) of the added content")
        size = Int(description="Size of the added content in bytes")

        def mutate(self, info, content, filename=None, pin=True):
            """Add content to IPFS."""
            api = info.context["api"]
            try:
                # Decode content if needed
                try:
                    decoded_content = base64.b64decode(content)
                except Exception:
                    # If not base64, use as is
                    decoded_content = content.encode("utf-8")

                # Add to IPFS
                result = api.add(decoded_content, pin=pin)

                if "Hash" in result:
                    return AddContentMutation(
                        success=True,
                        cid=result["Hash"],
                        size=result.get("Size", len(decoded_content)),
                    )
                elif "cid" in result:
                    return AddContentMutation(
                        success=True,
                        cid=result["cid"],
                        size=result.get("size", len(decoded_content)),
                    )
                else:
                    return AddContentMutation(success=False, cid=None, size=None)
            except Exception as e:
                logger.error(f"Error adding content: {str(e)}")
                return AddContentMutation(success=False, cid=None, size=None)

    class PinContentMutation(Mutation):
        """Mutation to pin content in IPFS."""

        class Arguments:
            cid = String(required=True, description="Content identifier (CID) to pin")
            recursive = Boolean(description="Whether to pin recursively")

        # Return fields
        success = Boolean(description="Whether the operation was successful")
        cid = String(description="Content identifier (CID) that was pinned")

        def mutate(self, info, cid, recursive=True):
            """Pin content in IPFS."""
            api = info.context["api"]
            try:
                # Pin content
                result = api.pin(cid, recursive=recursive)

                if isinstance(result, dict) and result.get("success", False):
                    return PinContentMutation(success=True, cid=cid)
                else:
                    return PinContentMutation(success=True, cid=cid)
            except Exception as e:
                logger.error(f"Error pinning content {cid}: {str(e)}")
                return PinContentMutation(success=False, cid=cid)

    class UnpinContentMutation(Mutation):
        """Mutation to unpin content in IPFS."""

        class Arguments:
            cid = String(required=True, description="Content identifier (CID) to unpin")
            recursive = Boolean(description="Whether to unpin recursively")

        # Return fields
        success = Boolean(description="Whether the operation was successful")
        cid = String(description="Content identifier (CID) that was unpinned")

        def mutate(self, info, cid, recursive=True):
            """Unpin content in IPFS."""
            api = info.context["api"]
            try:
                # Unpin content
                result = api.unpin(cid, recursive=recursive)

                if isinstance(result, dict) and result.get("success", False):
                    return UnpinContentMutation(success=True, cid=cid)
                else:
                    return UnpinContentMutation(success=True, cid=cid)
            except Exception as e:
                logger.error(f"Error unpinning content {cid}: {str(e)}")
                return UnpinContentMutation(success=False, cid=cid)

    class PublishIPNSMutation(Mutation):
        """Mutation to publish a name to IPNS."""

        class Arguments:
            cid = String(required=True, description="Content identifier (CID) to publish")
            key = String(description="Key name to use")
            lifetime = String(description="Lifetime of the record")
            ttl = String(description="Time-to-live of the record")

        # Return fields
        success = Boolean(description="Whether the operation was successful")
        name = String(description="IPNS name")
        value = String(description="IPFS path that the name points to")

        def mutate(self, info, cid, key="self", lifetime="24h", ttl="1h"):
            """Publish a name to IPNS."""
            api = info.context["api"]
            try:
                # Publish to IPNS
                result = api.publish(cid, key=key, lifetime=lifetime, ttl=ttl)

                if "Name" in result:
                    return PublishIPNSMutation(
                        success=True, name=result["Name"], value=result.get("Value", f"/ipfs/{cid}")
                    )
                elif "name" in result:
                    return PublishIPNSMutation(
                        success=True, name=result["name"], value=result.get("value", f"/ipfs/{cid}")
                    )
                else:
                    return PublishIPNSMutation(success=False, name=None, value=None)
            except Exception as e:
                logger.error(f"Error publishing IPNS name for {cid}: {str(e)}")
                return PublishIPNSMutation(success=False, name=None, value=None)

    class GenerateKeyMutation(Mutation):
        """Mutation to generate a new key."""

        class Arguments:
            name = String(required=True, description="Name for the key")
            type = String(description="Type of key to generate")
            size = Int(description="Size of the key in bits")

        # Return fields
        success = Boolean(description="Whether the operation was successful")
        name = String(description="Name of the generated key")
        id = String(description="ID of the generated key")

        def mutate(self, info, name, type="rsa", size=2048):
            """Generate a new key."""
            api = info.context["api"]
            try:
                # Generate key
                result = api.kit.ipfs_key_gen(name, type=type, size=size)

                if "Name" in result:
                    return GenerateKeyMutation(
                        success=True, name=result["Name"], id=result.get("Id", "")
                    )
                elif "name" in result:
                    return GenerateKeyMutation(
                        success=True, name=result["name"], id=result.get("id", "")
                    )
                else:
                    return GenerateKeyMutation(success=False, name=None, id=None)
            except Exception as e:
                logger.error(f"Error generating key {name}: {str(e)}")
                return GenerateKeyMutation(success=False, name=None, id=None)

    class ClusterPinMutation(Mutation):
        """Mutation to pin content across the IPFS cluster."""

        class Arguments:
            cid = String(required=True, description="Content identifier (CID) to pin")
            replication_factor = Int(description="Replication factor (-1 for all nodes)")
            name = String(description="Name for the pinned content")

        # Return fields
        success = Boolean(description="Whether the operation was successful")
        cid = String(description="Content identifier (CID) that was pinned")

        def mutate(self, info, cid, replication_factor=-1, name=None):
            """Pin content across the IPFS cluster."""
            api = info.context["api"]
            try:
                # Check if cluster operations are available
                if api.config.get("role") == "leecher":
                    return ClusterPinMutation(success=False, cid=cid)

                # Pin content to cluster
                try:
                    if hasattr(api, "cluster_pin"):
                        result = api.cluster_pin(
                            cid, replication_factor=replication_factor, name=name
                        )
                    elif hasattr(api, "cluster_pin_add"):
                        result = api.cluster_pin_add(
                            cid, replication_factor=replication_factor, name=name
                        )
                    else:
                        return ClusterPinMutation(success=False, cid=cid)
                except Exception as e:
                    logger.warning(f"Error pinning to cluster: {str(e)}")
                    return ClusterPinMutation(success=False, cid=cid)

                return ClusterPinMutation(success=True, cid=cid)
            except Exception as e:
                logger.error(f"Error pinning to cluster: {str(e)}")
                return ClusterPinMutation(success=False, cid=cid)

    class Mutation(ObjectType):
        """Root mutation type for IPFS operations."""

        add_content = AddContentMutation.Field(description="Add content to IPFS")
        pin_content = PinContentMutation.Field(description="Pin content in IPFS")
        unpin_content = UnpinContentMutation.Field(description="Unpin content in IPFS")
        publish_ipns = PublishIPNSMutation.Field(description="Publish a name to IPNS")
        generate_key = GenerateKeyMutation.Field(description="Generate a new key")
        cluster_pin = ClusterPinMutation.Field(description="Pin content across the IPFS cluster")

    # Create schema
    schema = Schema(query=Query, mutation=Mutation)

    # Helper function to execute GraphQL queries
    def execute_graphql(query, variables=None, context=None):
        """
        Execute a GraphQL query against the IPFS Kit schema.

        Args:
            query: GraphQL query string
            variables: Query variables (optional)
            context: Execution context (optional)

        Returns:
            GraphQL execution result
        """
        if not GRAPHQL_AVAILABLE:
            return {"errors": [{"message": "GraphQL not available"}]}

        result = schema.execute(query, variable_values=variables, context=context)

        if result.errors:
            errors = [str(error) for error in result.errors]
            return {"errors": errors}

        return {"data": result.data}

else:
    # Create a stub schema implementation for when GraphQL is not available
    schema = None

    def execute_graphql(query, variables=None, context=None):
        """
        Stub implementation when GraphQL is not available.

        Args:
            query: GraphQL query string
            variables: Query variables (optional)
            context: Execution context (optional)

        Returns:
            Error message
        """
        return {
            "errors": [
                {
                    "message": "GraphQL is not available. Please install graphene with 'pip install graphene'."
                }
            ]
        }


def check_graphql_availability():
    """Check if GraphQL is available and return status."""
    return {
        "available": GRAPHQL_AVAILABLE,
        "library": "graphene" if GRAPHQL_AVAILABLE else None,
        "schema": schema is not None,
    }
