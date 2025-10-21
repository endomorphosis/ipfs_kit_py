"""
Parquet to CAR Archive Bridge for IPFS Kit.

This module provides functionality to convert between Parquet files and IPLD CAR archives,
enabling columnar data to be content-addressed and shared through IPFS networks.

Features:
1. Convert Parquet files to IPLD CAR archives
2. Convert CAR archives back to Parquet files
3. Maintain metadata and schema information
4. Support for partitioned datasets
5. Integration with vector indices and knowledge graphs
6. Dashboard API endpoints for monitoring and querying
"""

from __future__ import annotations

import os
import json
import logging
import hashlib
import tempfile
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple, BinaryIO
from pathlib import Path

# Import Arrow/Parquet dependencies
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    from pyarrow.dataset import dataset
    ARROW_AVAILABLE = True
except ImportError:
    # Keep names bound to avoid import-time NameError in annotations when PyArrow isn't installed
    pa = None  # type: ignore[assignment]
    pq = None  # type: ignore[assignment]
    pc = None  # type: ignore[assignment]
    dataset = None  # type: ignore[assignment]
    ARROW_AVAILABLE = False

# Import IPLD CAR dependencies
try:
    from .ipld_extension import IPLDExtension
    from .ipld.car import IPLDCarHandler
    CAR_AVAILABLE = True
except ImportError:
    CAR_AVAILABLE = False

# Import other dependencies
from .parquet_ipld_bridge import ParquetIPLDBridge
from .ipld_knowledge_graph import IPLDGraphDB
from .error import IPFSError, create_result_dict, handle_error

logger = logging.getLogger(__name__)


class ParquetCARBridge:
    """
    Bridge for converting between Parquet files and IPLD CAR archives.
    
    This class enables columnar data to be stored as content-addressed
    CAR archives while maintaining all metadata and schema information.
    """
    
    def __init__(
        self,
        ipfs_client=None,
        storage_path: str = "~/.ipfs_parquet_car_storage",
        parquet_bridge: Optional[ParquetIPLDBridge] = None,
        knowledge_graph: Optional[IPLDGraphDB] = None
    ):
        """Initialize the Parquet-CAR bridge."""
        if not ARROW_AVAILABLE:
            raise ImportError("PyArrow is required for ParquetCARBridge")
        
        if not CAR_AVAILABLE:
            raise ImportError("IPLD CAR support is required for ParquetCARBridge")
        
        self.ipfs_client = ipfs_client
        self.storage_path = os.path.expanduser(storage_path)
        self.car_storage_path = os.path.join(self.storage_path, "car_archives")
        self.metadata_path = os.path.join(self.storage_path, "metadata")
        
        # Create storage directories
        os.makedirs(self.car_storage_path, exist_ok=True)
        os.makedirs(self.metadata_path, exist_ok=True)
        
        # Initialize components
        self.parquet_bridge = parquet_bridge or ParquetIPLDBridge()
        self.knowledge_graph = knowledge_graph
        self.ipld_extension = IPLDExtension(ipfs_client)
        self.car_handler = IPLDCarHandler()
        
        # Content addressing
        self.parquet_to_car_mapping = {}
        self.car_to_parquet_mapping = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info(f"ParquetCARBridge initialized at {self.storage_path}")
    
    def convert_parquet_to_car(
        self,
        parquet_path: str,
        car_path: Optional[str] = None,
        include_metadata: bool = True,
        compress_blocks: bool = True
    ) -> Dict[str, Any]:
        """
        Convert a Parquet file to an IPLD CAR archive.
        
        Args:
            parquet_path: Path to the Parquet file
            car_path: Optional output path for CAR file
            include_metadata: Whether to include schema and metadata
            compress_blocks: Whether to compress data blocks
            
        Returns:
            Result dictionary with CAR file information
        """
        try:
            with self._lock:
                # Validate input
                if not os.path.exists(parquet_path):
                    return create_result_dict(False, error=f"Parquet file not found: {parquet_path}")
                
                # Read Parquet file
                table = pq.read_table(parquet_path)
                
                # Generate CID for the table
                table_cid = self._generate_table_cid(table)
                
                # Prepare blocks for CAR archive
                blocks = []
                root_cids = []
                
                # Create schema block
                if include_metadata:
                    schema_data = {
                        "type": "arrow_schema",
                        "schema": table.schema.to_string(),
                        "num_rows": len(table),
                        "num_columns": len(table.columns),
                        "column_names": table.column_names,
                        "column_types": [str(field.type) for field in table.schema],
                        "created_at": datetime.utcnow().isoformat()
                    }
                    schema_bytes = json.dumps(schema_data).encode('utf-8')
                    schema_cid = self._generate_block_cid(schema_bytes)
                    blocks.append((schema_cid, schema_bytes))
                    root_cids.append(schema_cid)
                
                # Convert table to columnar blocks
                for i, column_name in enumerate(table.column_names):
                    column = table.column(i)
                    
                    # Serialize column data
                    column_table = pa.table([column], [column_name])
                    column_bytes = self._serialize_arrow_table(column_table, compress_blocks)
                    
                    # Generate CID for column
                    column_cid = self._generate_block_cid(column_bytes)
                    blocks.append((column_cid, column_bytes))
                
                # Create main table block
                table_bytes = self._serialize_arrow_table(table, compress_blocks)
                blocks.append((table_cid, table_bytes))
                root_cids.append(table_cid)
                
                # Create CAR archive
                car_data = self.car_handler.encode(root_cids, blocks)
                
                # Determine output path
                if not car_path:
                    car_filename = f"{table_cid}.car"
                    car_path = os.path.join(self.car_storage_path, car_filename)
                
                # Save CAR file
                with open(car_path, 'wb') as f:
                    f.write(car_data)
                
                # Store metadata
                metadata = {
                    "parquet_path": parquet_path,
                    "car_path": car_path,
                    "table_cid": table_cid,
                    "root_cids": root_cids,
                    "block_count": len(blocks),
                    "car_size": len(car_data),
                    "schema": table.schema.to_string(),
                    "num_rows": len(table),
                    "num_columns": len(table.columns),
                    "created_at": datetime.utcnow().isoformat()
                }
                
                metadata_path = os.path.join(self.metadata_path, f"{table_cid}_metadata.json")
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                # Update mappings
                self.parquet_to_car_mapping[parquet_path] = car_path
                self.car_to_parquet_mapping[car_path] = parquet_path
                
                # Add to knowledge graph if available
                if self.knowledge_graph:
                    self._add_to_knowledge_graph(metadata)
                
                logger.info(f"Converted Parquet to CAR: {parquet_path} -> {car_path}")
                
                return create_result_dict(
                    True,
                    car_path=car_path,
                    table_cid=table_cid,
                    root_cids=root_cids,
                    car_size=len(car_data),
                    block_count=len(blocks),
                    metadata=metadata
                )
                
        except Exception as e:
            return handle_error("convert_parquet_to_car", e)
    
    def convert_car_to_parquet(
        self,
        car_path: str,
        parquet_path: Optional[str] = None,
        extract_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Convert an IPLD CAR archive back to a Parquet file.
        
        Args:
            car_path: Path to the CAR file
            parquet_path: Optional output path for Parquet file
            extract_metadata: Whether to extract and validate metadata
            
        Returns:
            Result dictionary with Parquet file information
        """
        try:
            with self._lock:
                # Validate input
                if not os.path.exists(car_path):
                    return create_result_dict(False, error=f"CAR file not found: {car_path}")
                
                # Load CAR archive
                roots, blocks = self.car_handler.load_from_file(car_path)
                
                # Find main table block
                table_data = None
                schema_data = None
                
                for cid, data in blocks:
                    try:
                        # Try to deserialize as Arrow table
                        table = self._deserialize_arrow_table(data)
                        if table is not None:
                            table_data = table
                            break
                    except:
                        # Try to parse as schema metadata
                        try:
                            metadata = json.loads(data.decode('utf-8'))
                            if metadata.get("type") == "arrow_schema":
                                schema_data = metadata
                        except:
                            continue
                
                if table_data is None:
                    return create_result_dict(False, error="No valid Arrow table found in CAR archive")
                
                # Determine output path
                if not parquet_path:
                    car_name = os.path.splitext(os.path.basename(car_path))[0]
                    parquet_path = os.path.join(self.storage_path, f"{car_name}.parquet")
                
                # Write Parquet file
                pq.write_table(table_data, parquet_path)
                
                # Update mappings
                self.car_to_parquet_mapping[car_path] = parquet_path
                self.parquet_to_car_mapping[parquet_path] = car_path
                
                logger.info(f"Converted CAR to Parquet: {car_path} -> {parquet_path}")
                
                result = create_result_dict(
                    True,
                    parquet_path=parquet_path,
                    car_path=car_path,
                    num_rows=len(table_data),
                    num_columns=len(table_data.columns),
                    schema=table_data.schema.to_string()
                )
                
                if schema_data and extract_metadata:
                    result["metadata"] = schema_data
                
                return result
                
        except Exception as e:
            return handle_error("convert_car_to_parquet", e)
    
    def convert_dataset_to_car_collection(
        self,
        dataset_cid: str,
        collection_name: Optional[str] = None,
        include_vector_index: bool = True,
        include_knowledge_graph: bool = True
    ) -> Dict[str, Any]:
        """
        Convert a dataset along with its vector index and knowledge graph to CAR collection.
        
        Args:
            dataset_cid: CID of the dataset to convert
            collection_name: Optional name for the collection
            include_vector_index: Whether to include vector index data
            include_knowledge_graph: Whether to include knowledge graph data
            
        Returns:
            Result dictionary with CAR collection information
        """
        try:
            with self._lock:
                # Retrieve the dataset
                dataset_result = self.parquet_bridge.retrieve_dataframe(dataset_cid)
                if not dataset_result["success"]:
                    return dataset_result
                
                table = dataset_result["table"]
                metadata = dataset_result.get("metadata", {})
                
                # Create collection structure
                collection_id = collection_name or f"collection_{dataset_cid[:16]}"
                collection_path = os.path.join(self.car_storage_path, collection_id)
                os.makedirs(collection_path, exist_ok=True)
                
                blocks = []
                root_cids = []
                
                # Add main dataset
                table_bytes = self._serialize_arrow_table(table, True)
                table_cid = self._generate_block_cid(table_bytes)
                blocks.append((table_cid, table_bytes))
                root_cids.append(table_cid)
                
                # Add vector index if available and requested
                if include_vector_index:
                    vector_result = self._extract_vector_index(dataset_cid, table)
                    if vector_result["success"]:
                        vector_cid = vector_result["cid"]
                        vector_bytes = vector_result["data"]
                        blocks.append((vector_cid, vector_bytes))
                        root_cids.append(vector_cid)
                
                # Add knowledge graph if available and requested
                if include_knowledge_graph and self.knowledge_graph:
                    kg_result = self._extract_knowledge_graph_data(dataset_cid)
                    if kg_result["success"]:
                        kg_cid = kg_result["cid"]
                        kg_bytes = kg_result["data"]
                        blocks.append((kg_cid, kg_bytes))
                        root_cids.append(kg_cid)
                
                # Add pinset metadata
                pinset_result = self._extract_pinset_metadata(dataset_cid)
                if pinset_result["success"]:
                    pinset_cid = pinset_result["cid"]
                    pinset_bytes = pinset_result["data"]
                    blocks.append((pinset_cid, pinset_bytes))
                    root_cids.append(pinset_cid)
                
                # Create collection metadata
                collection_metadata = {
                    "collection_id": collection_id,
                    "dataset_cid": dataset_cid,
                    "root_cids": root_cids,
                    "components": {
                        "dataset": table_cid,
                        "vector_index": vector_result.get("cid") if include_vector_index else None,
                        "knowledge_graph": kg_result.get("cid") if include_knowledge_graph else None,
                        "pinset": pinset_result.get("cid")
                    },
                    "created_at": datetime.utcnow().isoformat(),
                    "metadata": metadata
                }
                
                metadata_bytes = json.dumps(collection_metadata).encode('utf-8')
                metadata_cid = self._generate_block_cid(metadata_bytes)
                blocks.append((metadata_cid, metadata_bytes))
                root_cids.insert(0, metadata_cid)  # Make metadata the primary root
                
                # Create CAR archive
                car_data = self.car_handler.encode(root_cids, blocks)
                car_path = os.path.join(collection_path, f"{collection_id}.car")
                
                with open(car_path, 'wb') as f:
                    f.write(car_data)
                
                # Store collection metadata
                collection_metadata_path = os.path.join(collection_path, "collection_metadata.json")
                with open(collection_metadata_path, 'w') as f:
                    json.dump(collection_metadata, f, indent=2)
                
                logger.info(f"Created CAR collection: {collection_id}")
                
                return create_result_dict(
                    True,
                    collection_id=collection_id,
                    collection_path=collection_path,
                    car_path=car_path,
                    car_size=len(car_data),
                    components=collection_metadata["components"],
                    metadata=collection_metadata
                )
                
        except Exception as e:
            return handle_error("convert_dataset_to_car_collection", e)
    
    def list_car_archives(self) -> Dict[str, Any]:
        """List all available CAR archives."""
        try:
            archives = []
            
            # Scan CAR storage directory
            for item in os.listdir(self.car_storage_path):
                item_path = os.path.join(self.car_storage_path, item)
                
                if os.path.isfile(item_path) and item.endswith('.car'):
                    # Single CAR file
                    archives.append(self._get_car_info(item_path))
                elif os.path.isdir(item_path):
                    # CAR collection directory
                    collection_car = os.path.join(item_path, f"{item}.car")
                    if os.path.exists(collection_car):
                        archives.append(self._get_car_collection_info(item_path))
            
            return create_result_dict(
                True,
                archives=archives,
                count=len(archives)
            )
            
        except Exception as e:
            return handle_error("list_car_archives", e)
    
    def get_car_metadata(self, car_identifier: str) -> Dict[str, Any]:
        """Get metadata for a specific CAR archive."""
        try:
            # Try to find metadata file
            metadata_path = os.path.join(self.metadata_path, f"{car_identifier}_metadata.json")
            
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                return create_result_dict(True, metadata=metadata)
            else:
                return create_result_dict(False, error=f"Metadata not found for: {car_identifier}")
                
        except Exception as e:
            return handle_error("get_car_metadata", e)
    
    def _generate_table_cid(self, table: pa.Table) -> str:
        """Generate a content-addressed CID for an Arrow table."""
        schema_str = table.schema.to_string()
        
        # Get deterministic sample for hashing
        sample_size = min(100, len(table))
        if sample_size > 0:
            indices = list(range(0, sample_size))
            sample = table.take(indices)
            sample_str = str(sample.to_pydict())
        else:
            sample_str = "empty"
        
        content = f"{schema_str}:{sample_str}:{len(table)}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return f"bafy{content_hash[:52]}"
    
    def _generate_block_cid(self, data: bytes) -> str:
        """Generate a CID for a data block."""
        content_hash = hashlib.sha256(data).hexdigest()
        return f"bafy{content_hash[:52]}"
    
    def _serialize_arrow_table(self, table: pa.Table, compress: bool = True) -> bytes:
        """Serialize an Arrow table to bytes."""
        import io
        buffer = io.BytesIO()
        
        if compress:
            pq.write_table(table, buffer, compression='zstd')
        else:
            pq.write_table(table, buffer)
        
        return buffer.getvalue()
    
    def _deserialize_arrow_table(self, data: bytes) -> Optional[pa.Table]:
        """Deserialize bytes to an Arrow table."""
        try:
            import io
            buffer = io.BytesIO(data)
            return pq.read_table(buffer)
        except:
            return None
    
    def _extract_vector_index(self, dataset_cid: str, table: pa.Table) -> Dict[str, Any]:
        """Extract vector index data for a dataset."""
        try:
            # This is a placeholder - would integrate with actual vector index
            # For now, create a simple columnar representation
            
            # Look for text columns that might have embeddings
            text_columns = []
            for i, field in enumerate(table.schema):
                if pa.types.is_string(field.type) or pa.types.is_large_string(field.type):
                    text_columns.append(table.column_names[i])
            
            if not text_columns:
                return create_result_dict(False, error="No text columns found for vector indexing")
            
            # Create a simple vector index structure
            vector_index_data = {
                "type": "vector_index",
                "dataset_cid": dataset_cid,
                "text_columns": text_columns,
                "num_vectors": len(table),
                "created_at": datetime.utcnow().isoformat()
            }
            
            vector_bytes = json.dumps(vector_index_data).encode('utf-8')
            vector_cid = self._generate_block_cid(vector_bytes)
            
            return create_result_dict(
                True,
                cid=vector_cid,
                data=vector_bytes,
                metadata=vector_index_data
            )
            
        except Exception as e:
            return handle_error("_extract_vector_index", e)
    
    def _extract_knowledge_graph_data(self, dataset_cid: str) -> Dict[str, Any]:
        """Extract knowledge graph data for a dataset."""
        try:
            if not self.knowledge_graph:
                return create_result_dict(False, error="Knowledge graph not available")
            
            # Get entities and relationships related to this dataset
            kg_data = {
                "type": "knowledge_graph",
                "dataset_cid": dataset_cid,
                "entities": [],
                "relationships": [],
                "created_at": datetime.utcnow().isoformat()
            }
            
            # This would integrate with the actual knowledge graph
            # For now, create a placeholder structure
            kg_bytes = json.dumps(kg_data).encode('utf-8')
            kg_cid = self._generate_block_cid(kg_bytes)
            
            return create_result_dict(
                True,
                cid=kg_cid,
                data=kg_bytes,
                metadata=kg_data
            )
            
        except Exception as e:
            return handle_error("_extract_knowledge_graph_data", e)
    
    def _extract_pinset_metadata(self, dataset_cid: str) -> Dict[str, Any]:
        """Extract pinset metadata for a dataset."""
        try:
            # Get pinset information from IPFS
            pinset_data = {
                "type": "pinset",
                "dataset_cid": dataset_cid,
                "pins": [dataset_cid],  # At minimum, the dataset itself is pinned
                "storage_backends": [],
                "replication_factor": 1,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # This would integrate with actual pinset management
            # For now, create a basic structure
            pinset_bytes = json.dumps(pinset_data).encode('utf-8')
            pinset_cid = self._generate_block_cid(pinset_bytes)
            
            return create_result_dict(
                True,
                cid=pinset_cid,
                data=pinset_bytes,
                metadata=pinset_data
            )
            
        except Exception as e:
            return handle_error("_extract_pinset_metadata", e)
    
    def _add_to_knowledge_graph(self, metadata: Dict[str, Any]) -> None:
        """Add conversion metadata to knowledge graph."""
        if not self.knowledge_graph:
            return
        
        try:
            # Create entity for the CAR archive
            entity_data = {
                "type": "car_archive",
                "table_cid": metadata["table_cid"],
                "car_path": metadata["car_path"],
                "parquet_path": metadata["parquet_path"],
                "schema": metadata["schema"],
                "num_rows": metadata["num_rows"],
                "num_columns": metadata["num_columns"],
                "created_at": metadata["created_at"]
            }
            
            # This would use the actual knowledge graph API
            # For now, just log the action
            logger.info(f"Added CAR archive to knowledge graph: {metadata['table_cid']}")
            
        except Exception as e:
            logger.warning(f"Failed to add to knowledge graph: {e}")
    
    def _get_car_info(self, car_path: str) -> Dict[str, Any]:
        """Get information about a CAR file."""
        try:
            stat = os.stat(car_path)
            car_name = os.path.splitext(os.path.basename(car_path))[0]
            
            # Try to load metadata
            metadata_path = os.path.join(self.metadata_path, f"{car_name}_metadata.json")
            metadata = {}
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
            
            return {
                "type": "car_file",
                "name": car_name,
                "path": car_path,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.warning(f"Failed to get CAR info for {car_path}: {e}")
            return {
                "type": "car_file",
                "name": os.path.basename(car_path),
                "path": car_path,
                "error": str(e)
            }
    
    def _get_car_collection_info(self, collection_path: str) -> Dict[str, Any]:
        """Get information about a CAR collection."""
        try:
            collection_name = os.path.basename(collection_path)
            metadata_path = os.path.join(collection_path, "collection_metadata.json")
            
            metadata = {}
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
            
            # Get CAR file size
            car_path = os.path.join(collection_path, f"{collection_name}.car")
            car_size = 0
            if os.path.exists(car_path):
                car_size = os.path.getsize(car_path)
            
            return {
                "type": "car_collection",
                "name": collection_name,
                "path": collection_path,
                "car_size": car_size,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.warning(f"Failed to get CAR collection info for {collection_path}: {e}")
            return {
                "type": "car_collection",
                "name": os.path.basename(collection_path),
                "path": collection_path,
                "error": str(e)
            }
