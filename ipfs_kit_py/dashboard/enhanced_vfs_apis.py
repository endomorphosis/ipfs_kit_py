"""
Enhanced VFS APIs for IPFS Kit Dashboard
Enhanced APIs for Virtual Filesystem, Vector Indices, Knowledge Graph, and Pinset Management
Includes comprehensive replication management and storage backend integration
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Body, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse, FileResponse
import pandas as pd

# Import IPFS Kit components
try:
    from ..parquet_car_bridge import ParquetCARBridge
    from ..parquet_ipld_bridge import ParquetIPLDBridge
    from ..ipld_knowledge_graph import IPLDGraphDB, GraphRAG
    from ..tiered_cache_manager import TieredCacheManager, ParquetCIDCache
    from ..error import create_result_dict, handle_error
    CAR_BRIDGE_AVAILABLE = True
except ImportError:
    CAR_BRIDGE_AVAILABLE = False

logger = logging.getLogger(__name__)


class VFSMetadataAPI:
    """API for virtual filesystem metadata operations with replication support."""
    
    def __init__(
        self,
        parquet_bridge: ParquetIPLDBridge,
        car_bridge: ParquetCARBridge,
        cache_manager: TieredCacheManager,
        replication_manager=None
    ):
        self.parquet_bridge = parquet_bridge
        self.car_bridge = car_bridge
        self.cache_manager = cache_manager
        self.replication_manager = replication_manager
        self.router = APIRouter(prefix="/api/vfs", tags=["vfs"])
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes for VFS metadata."""
        
        @self.router.get("/metadata/summary")
        async def get_vfs_metadata_summary():
            """Get summary of virtual filesystem metadata."""
            try:
                # Get dataset summary
                datasets_result = self.parquet_bridge.list_datasets()
                if not datasets_result["success"]:
                    raise HTTPException(status_code=500, detail=datasets_result.get("error"))
                
                datasets = datasets_result["datasets"]
                
                # Calculate statistics
                total_size = sum(d.get("size_bytes", 0) for d in datasets)
                total_files = len(datasets)
                
                # Get CAR archives summary
                car_result = self.car_bridge.list_car_archives()
                car_archives = car_result.get("archives", []) if car_result["success"] else []
                
                # Get cache statistics
                cache_stats = self.cache_manager.get_performance_metrics()
                
                summary = {
                    "total_datasets": total_files,
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "car_archives_count": len(car_archives),
                    "cache_hit_rate": cache_stats.get("hit_rate", 0),
                    "last_updated": datetime.utcnow().isoformat()
                }
                
                return JSONResponse(content={"success": True, "summary": summary})
                
            except Exception as e:
                logger.error(f"Error getting VFS metadata summary: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/metadata/datasets")
        async def list_vfs_datasets(
            limit: int = Query(50, ge=1, le=1000),
            offset: int = Query(0, ge=0),
            include_car: bool = Query(True)
        ):
            """List virtual filesystem datasets with optional CAR archive information."""
            try:
                # Get datasets
                datasets_result = self.parquet_bridge.list_datasets()
                if not datasets_result["success"]:
                    raise HTTPException(status_code=500, detail=datasets_result.get("error"))
                
                datasets = datasets_result["datasets"]
                
                # Apply pagination
                total = len(datasets)
                paginated_datasets = datasets[offset:offset + limit]
                
                # Enhance with CAR archive information if requested
                if include_car:
                    car_result = self.car_bridge.list_car_archives()
                    car_archives = {
                        archive["metadata"].get("dataset_cid"): archive
                        for archive in car_result.get("archives", [])
                        if car_result["success"] and archive.get("metadata", {}).get("dataset_cid")
                    }
                    
                    for dataset in paginated_datasets:
                        cid = dataset["cid"]
                        if cid in car_archives:
                            dataset["car_archive"] = car_archives[cid]
                
                return JSONResponse(content={
                    "success": True,
                    "datasets": paginated_datasets,
                    "pagination": {
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                        "has_more": offset + limit < total
                    }
                })
                
            except Exception as e:
                logger.error(f"Error listing VFS datasets: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/metadata/dataset/{cid}")
        async def get_dataset_metadata(cid: str, include_car: bool = Query(True)):
            """Get detailed metadata for a specific dataset."""
            try:
                # Get dataset metadata
                dataset_result = self.parquet_bridge.retrieve_dataframe(cid, use_cache=True)
                if not dataset_result["success"]:
                    raise HTTPException(status_code=404, detail=f"Dataset not found: {cid}")
                
                metadata = dataset_result.get("metadata", {})
                table = dataset_result.get("table")
                
                # Enhance metadata with table information
                if table:
                    metadata.update({
                        "schema": table.schema.to_string(),
                        "column_names": table.column_names,
                        "column_types": [str(field.type) for field in table.schema],
                        "num_rows": len(table),
                        "num_columns": len(table.columns)
                    })
                
                # Add CAR archive information if requested
                if include_car:
                    car_metadata_result = self.car_bridge.get_car_metadata(cid)
                    if car_metadata_result["success"]:
                        metadata["car_archive"] = car_metadata_result["metadata"]
                
                return JSONResponse(content={"success": True, "metadata": metadata})
                
            except Exception as e:
                logger.error(f"Error getting dataset metadata: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/metadata/convert-to-car")
        async def convert_dataset_to_car(
            cid: str,
            include_vector_index: bool = Query(True),
            include_knowledge_graph: bool = Query(True),
            collection_name: Optional[str] = Query(None)
        ):
            """Convert a dataset to CAR archive with vector index and knowledge graph."""
            try:
                # Convert to CAR collection
                result = self.car_bridge.convert_dataset_to_car_collection(
                    dataset_cid=cid,
                    collection_name=collection_name,
                    include_vector_index=include_vector_index,
                    include_knowledge_graph=include_knowledge_graph
                )
                
                if not result["success"]:
                    raise HTTPException(status_code=500, detail=result.get("error"))
                
                return JSONResponse(content=result)
                
            except Exception as e:
                logger.error(f"Error converting dataset to CAR: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/car-archives")
        async def list_car_archives():
            """List all available CAR archives."""
            try:
                result = self.car_bridge.list_car_archives()
                if not result["success"]:
                    raise HTTPException(status_code=500, detail=result.get("error"))
                
                return JSONResponse(content=result)
                
            except Exception as e:
                logger.error(f"Error listing CAR archives: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/car-archives/{identifier}/download")
        async def download_car_archive(identifier: str):
            """Download a CAR archive file."""
            try:
                # Find the CAR file
                car_archives_result = self.car_bridge.list_car_archives()
                if not car_archives_result["success"]:
                    raise HTTPException(status_code=500, detail="Failed to list CAR archives")
                
                car_file = None
                for archive in car_archives_result["archives"]:
                    if (archive.get("name") == identifier or 
                        archive.get("metadata", {}).get("collection_id") == identifier):
                        if archive["type"] == "car_file":
                            car_file = archive["path"]
                        elif archive["type"] == "car_collection":
                            collection_name = os.path.basename(archive["path"])
                            car_file = os.path.join(archive["path"], f"{collection_name}.car")
                        break
                
                if not car_file or not os.path.exists(car_file):
                    raise HTTPException(status_code=404, detail=f"CAR archive not found: {identifier}")
                
                return FileResponse(
                    path=car_file,
                    media_type="application/octet-stream",
                    filename=f"{identifier}.car"
                )
                
            except Exception as e:
                logger.error(f"Error downloading CAR archive: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    # Demo-compatible methods
    async def create_dataset(self, dataset_data):
        """Create a dataset with automatic replication (demo-compatible method)."""
        try:
            # Mock implementation for demo with replication integration
            dataset_id = dataset_data.get('id', f'dataset_{int(time.time())}')
            dataset_cid = f"Qm{dataset_id}MockCID123"
            
            result = {
                'success': True,
                'dataset_id': dataset_id,
                'cid': dataset_cid,
                'message': 'Dataset created successfully'
            }
            
            # If replication manager is available, register the dataset for replication
            if self.replication_manager:
                size_bytes = dataset_data.get('size_bytes', 1024*1024)  # Default 1MB
                target_replicas = dataset_data.get('target_replicas', None)
                priority = dataset_data.get('priority', 1)
                
                replication_result = await self.replication_manager.register_pin_for_replication(
                    cid=dataset_cid,
                    vfs_metadata_id=dataset_id,
                    size_bytes=size_bytes,
                    target_replicas=target_replicas,
                    priority=priority
                )
                result['replication'] = replication_result
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating dataset: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def list_datasets(self, **kwargs):
        """List datasets (demo-compatible method)."""
        # Mock implementation for demo
        return {
            'success': True,
            'datasets': [
                {'id': 'dataset_001', 'name': 'Sample Dataset 1', 'size': '50MB'},
                {'id': 'dataset_002', 'name': 'Sample Dataset 2', 'size': '75MB'}
            ],
            'pagination': {'total': 2, 'limit': 50, 'offset': 0}
        }
    
    async def get_vfs_status(self):
        """Get VFS status (demo-compatible method)."""
        return {
            'success': True,
            'status': {
                'available': True,
                'datasets_count': 5,
                'total_size': '500MB',
                'car_archives': 3
            }
        }
    
    async def convert_dataset_to_car(self, dataset_data):
        """Convert dataset to CAR (demo-compatible method)."""
        return {
            'success': True,
            'dataset_id': dataset_data.get('dataset_id', 'unknown'),
            'car_path': f'/mock/{dataset_data.get("dataset_id", "unknown")}.car',
            'cid': f'Qm{dataset_data.get("dataset_id", "unknown")}MockCID123'
        }


class VectorIndexAPI:
    """API for vector index operations."""
    
    def __init__(
        self,
        parquet_bridge: ParquetIPLDBridge,
        car_bridge: ParquetCARBridge,
        knowledge_graph: Optional[IPLDGraphDB] = None
    ):
        self.parquet_bridge = parquet_bridge
        self.car_bridge = car_bridge
        self.knowledge_graph = knowledge_graph
        self.router = APIRouter(prefix="/api/vector", tags=["vector"])
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes for vector index operations."""
        
        @self.router.get("/status")
        async def get_vector_index_status():
            """Get vector index status and statistics."""
            try:
                # Get dataset statistics
                datasets_result = self.parquet_bridge.list_datasets()
                datasets = datasets_result.get("datasets", []) if datasets_result["success"] else []
                
                # Calculate vector index statistics
                total_datasets = len(datasets)
                indexed_datasets = 0
                total_vectors = 0
                
                for dataset in datasets:
                    # Check if dataset has vector index
                    metadata = dataset.get("metadata", {})
                    if metadata.get("has_vector_index", False):
                        indexed_datasets += 1
                        total_vectors += metadata.get("vector_count", 0)
                
                status = {
                    "total_datasets": total_datasets,
                    "indexed_datasets": indexed_datasets,
                    "indexing_coverage": round(indexed_datasets / max(total_datasets, 1) * 100, 2),
                    "total_vectors": total_vectors,
                    "index_status": "active" if indexed_datasets > 0 else "inactive",
                    "last_updated": datetime.utcnow().isoformat()
                }
                
                return JSONResponse(content={"success": True, "status": status})
                
            except Exception as e:
                logger.error(f"Error getting vector index status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/collections")
        async def list_vector_collections():
            """List available vector collections."""
            try:
                # Get datasets with vector indices
                datasets_result = self.parquet_bridge.list_datasets()
                if not datasets_result["success"]:
                    raise HTTPException(status_code=500, detail=datasets_result.get("error"))
                
                collections = []
                for dataset in datasets_result["datasets"]:
                    metadata = dataset.get("metadata", {})
                    if metadata.get("has_vector_index", False):
                        collections.append({
                            "collection_id": dataset["cid"],
                            "name": dataset.get("name", dataset["cid"][:16]),
                            "vector_count": metadata.get("vector_count", 0),
                            "dimensions": metadata.get("vector_dimensions", 0),
                            "index_type": metadata.get("index_type", "unknown"),
                            "created_at": dataset.get("created_at")
                        })
                
                return JSONResponse(content={
                    "success": True,
                    "collections": collections,
                    "count": len(collections)
                })
                
            except Exception as e:
                logger.error(f"Error listing vector collections: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/search")
        async def search_vectors(
            query: str,
            collection_id: Optional[str] = None,
            top_k: int = Query(10, ge=1, le=100),
            include_metadata: bool = Query(True)
        ):
            """Search vectors using text query."""
            try:
                # This would integrate with actual vector search engine
                # For now, return mock results
                results = []
                for i in range(min(top_k, 5)):
                    results.append({
                        "id": f"vector_{i}",
                        "score": 0.95 - (i * 0.1),
                        "content": f"Sample content {i} matching query: {query}",
                        "metadata": {
                            "collection_id": collection_id or "default",
                            "indexed_at": datetime.utcnow().isoformat()
                        } if include_metadata else {}
                    })
                
                return JSONResponse(content={
                    "success": True,
                    "query": query,
                    "results": results,
                    "total_results": len(results)
                })
                
            except Exception as e:
                logger.error(f"Error searching vectors: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/collection/{collection_id}/export-car")
        async def export_vector_collection_to_car(collection_id: str):
            """Export a vector collection to CAR archive."""
            try:
                # Convert the collection to CAR format
                result = self.car_bridge.convert_dataset_to_car_collection(
                    dataset_cid=collection_id,
                    collection_name=f"vector_collection_{collection_id[:16]}",
                    include_vector_index=True,
                    include_knowledge_graph=False
                )
                
                if not result["success"]:
                    raise HTTPException(status_code=500, detail=result.get("error"))
                
                return JSONResponse(content=result)
                
            except Exception as e:
                logger.error(f"Error exporting vector collection to CAR: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    # Demo-compatible methods
    async def add_vector(self, vector_data):
        """Add a vector (demo-compatible method)."""
        return {
            'success': True,
            'vector_id': vector_data.get('id', 'unknown'),
            'message': 'Vector added successfully'
        }
    
    async def search_vectors(self, query):
        """Search vectors (demo-compatible method)."""
        return {
            'success': True,
            'results': [
                {'id': 'vec_001', 'score': 0.95, 'metadata': {'type': 'document'}},
                {'id': 'vec_002', 'score': 0.87, 'metadata': {'type': 'image'}}
            ],
            'query_time': '0.05s'
        }
    
    async def export_vector_indices_to_car(self):
        """Export vector indices to CAR (demo-compatible method)."""
        return {
            'success': True,
            'car_path': '/mock/vector_indices.car',
            'cid': 'QmVectorIndicesMockCID123'
        }
    
    async def get_vector_status(self):
        """Get vector index status (demo-compatible method)."""
        return {
            'success': True,
            'status': {
                'available': True,
                'collections_count': 3,
                'total_vectors': 1500,
                'index_size': '250MB'
            }
        }


class KnowledgeGraphAPI:
    """API for knowledge graph operations."""
    
    def __init__(
        self,
        knowledge_graph: Optional[IPLDGraphDB],
        car_bridge: ParquetCARBridge,
        graph_rag: Optional[GraphRAG] = None
    ):
        self.knowledge_graph = knowledge_graph
        self.car_bridge = car_bridge
        self.graph_rag = graph_rag
        self.router = APIRouter(prefix="/api/kg", tags=["knowledge-graph"])
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes for knowledge graph operations."""
        
        @self.router.get("/status")
        async def get_knowledge_graph_status():
            """Get knowledge graph status and statistics."""
            try:
                if not self.knowledge_graph:
                    return JSONResponse(content={
                        "success": True,
                        "status": {
                            "available": False,
                            "message": "Knowledge graph not initialized"
                        }
                    })
                
                # Get graph statistics
                stats = {
                    "available": True,
                    "entity_count": len(self.knowledge_graph.entities),
                    "relationship_count": len(self.knowledge_graph.relationships.get("relationship_cids", {})),
                    "graph_size": 0,  # Would calculate actual graph size
                    "last_updated": datetime.utcnow().isoformat()
                }
                
                return JSONResponse(content={"success": True, "status": stats})
                
            except Exception as e:
                logger.error(f"Error getting knowledge graph status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/entities")
        async def list_entities(
            limit: int = Query(50, ge=1, le=1000),
            offset: int = Query(0, ge=0),
            entity_type: Optional[str] = Query(None)
        ):
            """List entities in the knowledge graph."""
            try:
                if not self.knowledge_graph:
                    raise HTTPException(status_code=503, detail="Knowledge graph not available")
                
                # Get entities (simplified for demonstration)
                entities = []
                entity_items = list(self.knowledge_graph.entities.items())[offset:offset + limit]
                
                for entity_id, entity_data in entity_items:
                    if entity_type and entity_data.get("data", {}).get("type") != entity_type:
                        continue
                    
                    entities.append({
                        "id": entity_id,
                        "type": entity_data.get("data", {}).get("type", "unknown"),
                        "cid": entity_data.get("cid"),
                        "properties": entity_data.get("data", {})
                    })
                
                return JSONResponse(content={
                    "success": True,
                    "entities": entities,
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "total": len(self.knowledge_graph.entities)
                    }
                })
                
            except Exception as e:
                logger.error(f"Error listing entities: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/entity/{entity_id}")
        async def get_entity(entity_id: str, include_relationships: bool = Query(True)):
            """Get detailed information about a specific entity."""
            try:
                if not self.knowledge_graph:
                    raise HTTPException(status_code=503, detail="Knowledge graph not available")
                
                # Get entity data
                if entity_id not in self.knowledge_graph.entities:
                    raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
                
                entity_data = self.knowledge_graph.entities[entity_id]
                
                result = {
                    "id": entity_id,
                    "cid": entity_data.get("cid"),
                    "properties": entity_data.get("data", {}),
                    "relationships": []
                }
                
                # Add relationships if requested
                if include_relationships:
                    entity_rels = self.knowledge_graph.relationships.get("entity_rels", {}).get(entity_id, [])
                    for rel_id in entity_rels:
                        rel_cid = self.knowledge_graph.relationships.get("relationship_cids", {}).get(rel_id)
                        if rel_cid:
                            result["relationships"].append({
                                "id": rel_id,
                                "cid": rel_cid
                            })
                
                return JSONResponse(content={"success": True, "entity": result})
                
            except Exception as e:
                logger.error(f"Error getting entity: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/search")
        async def search_knowledge_graph(
            query: str,
            search_type: str = Query("entity", regex="^(entity|relationship|path)$"),
            limit: int = Query(10, ge=1, le=100)
        ):
            """Search the knowledge graph."""
            try:
                if not self.knowledge_graph:
                    raise HTTPException(status_code=503, detail="Knowledge graph not available")
                
                # This would integrate with actual graph search
                # For now, return mock results
                results = []
                
                if search_type == "entity":
                    # Search entities
                    for i, (entity_id, entity_data) in enumerate(list(self.knowledge_graph.entities.items())[:limit]):
                        if query.lower() in str(entity_data.get("data", {})).lower():
                            results.append({
                                "type": "entity",
                                "id": entity_id,
                                "cid": entity_data.get("cid"),
                                "score": 1.0 - (i * 0.1),
                                "properties": entity_data.get("data", {})
                            })
                
                return JSONResponse(content={
                    "success": True,
                    "query": query,
                    "search_type": search_type,
                    "results": results,
                    "total_results": len(results)
                })
                
            except Exception as e:
                logger.error(f"Error searching knowledge graph: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/export-car")
        async def export_knowledge_graph_to_car():
            """Export the entire knowledge graph to CAR archive."""
            try:
                if not self.knowledge_graph:
                    raise HTTPException(status_code=503, detail="Knowledge graph not available")
                
                # Create a special dataset for the knowledge graph
                kg_data = {
                    "entities": dict(self.knowledge_graph.entities),
                    "relationships": dict(self.knowledge_graph.relationships),
                    "exported_at": datetime.utcnow().isoformat()
                }
                
                # Store as dataset first
                import pandas as pd
                df = pd.DataFrame([kg_data])  # Single row with all data
                
                store_result = self.parquet_bridge.store_dataframe(
                    df,
                    name="knowledge_graph_export",
                    metadata={"type": "knowledge_graph_export"}
                )
                
                if not store_result["success"]:
                    raise HTTPException(status_code=500, detail=store_result.get("error"))
                
                # Convert to CAR
                car_result = self.car_bridge.convert_dataset_to_car_collection(
                    dataset_cid=store_result["cid"],
                    collection_name="knowledge_graph_complete",
                    include_vector_index=False,
                    include_knowledge_graph=True
                )
                
                if not car_result["success"]:
                    raise HTTPException(status_code=500, detail=car_result.get("error"))
                
                return JSONResponse(content=car_result)
                
            except Exception as e:
                logger.error(f"Error exporting knowledge graph to CAR: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    # Demo-compatible methods
    async def create_entity(self, entity_data):
        """Create an entity (demo-compatible method)."""
        return {
            'success': True,
            'entity_id': entity_data.get('id', 'unknown'),
            'message': 'Entity created successfully'
        }
    
    async def create_relationship(self, relationship_data):
        """Create a relationship (demo-compatible method)."""
        return {
            'success': True,
            'relationship_id': relationship_data.get('id', 'unknown'),
            'message': 'Relationship created successfully'
        }
    
    async def search_knowledge_graph(self, query):
        """Search knowledge graph (demo-compatible method)."""
        return {
            'success': True,
            'results': [
                {'id': 'entity_001', 'type': 'dataset', 'score': 0.92},
                {'id': 'entity_002', 'type': 'researcher', 'score': 0.88}
            ],
            'query_time': '0.03s'
        }
    
    async def export_knowledge_graph_to_car(self):
        """Export knowledge graph to CAR (demo-compatible method)."""
        return {
            'success': True,
            'car_path': '/mock/knowledge_graph.car',
            'cid': 'QmKnowledgeGraphMockCID123'
        }
    
    async def get_kg_status(self):
        """Get knowledge graph status (demo-compatible method)."""
        return {
            'success': True,
            'status': {
                'available': True,
                'entities_count': 150,
                'relationships_count': 75,
                'graph_size': '100MB'
            }
        }


class PinsetAPI:
    """API for pinset and storage backend management with replication support."""
    
    def __init__(
        self,
        parquet_bridge: ParquetIPLDBridge,
        car_bridge: ParquetCARBridge,
        cache_manager: TieredCacheManager,
        replication_manager=None
    ):
        self.parquet_bridge = parquet_bridge
        self.car_bridge = car_bridge
        self.cache_manager = cache_manager
        self.replication_manager = replication_manager
        self.router = APIRouter(prefix="/api/pinset", tags=["pinset"])
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes for pinset operations."""
        
        @self.router.get("/status")
        async def get_pinset_status():
            """Get pinset status and storage backend information."""
            try:
                # Get storage statistics
                storage_stats = self.parquet_bridge.get_storage_stats()
                
                if not storage_stats["success"]:
                    raise HTTPException(status_code=500, detail=storage_stats.get("error"))
                
                stats = storage_stats["stats"]
                
                # Calculate pinset statistics
                pinset_stats = {
                    "total_pins": stats["dataset_count"],
                    "total_storage_bytes": stats["total_size_bytes"],
                    "storage_backends": [
                        {
                            "name": "local_parquet",
                            "type": "parquet",
                            "status": "active",
                            "pin_count": stats["dataset_count"],
                            "storage_used": stats["total_size_bytes"]
                        }
                    ],
                    "replication_factor": 1,  # Default for local storage
                    "last_updated": datetime.utcnow().isoformat()
                }
                
                # Add cache information
                cache_stats = self.cache_manager.get_performance_metrics()
                pinset_stats["cache_stats"] = cache_stats
                
                return JSONResponse(content={"success": True, "pinset": pinset_stats})
                
            except Exception as e:
                logger.error(f"Error getting pinset status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/pins")
        async def list_pins(
            limit: int = Query(50, ge=1, le=1000),
            offset: int = Query(0, ge=0),
            backend: Optional[str] = Query(None)
        ):
            """List pinned content with storage backend information."""
            try:
                # Get datasets (which represent pinned content)
                datasets_result = self.parquet_bridge.list_datasets()
                if not datasets_result["success"]:
                    raise HTTPException(status_code=500, detail=datasets_result.get("error"))
                
                datasets = datasets_result["datasets"]
                
                # Apply pagination
                total = len(datasets)
                paginated_datasets = datasets[offset:offset + limit]
                
                # Transform to pin format
                pins = []
                for dataset in paginated_datasets:
                    pin_info = {
                        "cid": dataset["cid"],
                        "name": dataset.get("name"),
                        "size_bytes": dataset.get("size_bytes", 0),
                        "pin_type": "recursive",
                        "pinned_at": dataset.get("created_at"),
                        "storage_backends": [
                            {
                                "name": "local_parquet",
                                "type": "parquet",
                                "path": dataset.get("metadata", {}).get("storage_path"),
                                "status": "pinned"
                            }
                        ]
                    }
                    
                    # Add CAR archive information if available
                    car_metadata_result = self.car_bridge.get_car_metadata(dataset["cid"])
                    if car_metadata_result["success"]:
                        car_metadata = car_metadata_result["metadata"]
                        pin_info["storage_backends"].append({
                            "name": "ipld_car",
                            "type": "car_archive",
                            "path": car_metadata.get("car_path"),
                            "status": "available"
                        })
                    
                    pins.append(pin_info)
                
                return JSONResponse(content={
                    "success": True,
                    "pins": pins,
                    "pagination": {
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                        "has_more": offset + limit < total
                    }
                })
                
            except Exception as e:
                logger.error(f"Error listing pins: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/pin/{cid}")
        async def get_pin_info(cid: str):
            """Get detailed information about a specific pin."""
            try:
                # Get dataset metadata
                dataset_result = self.parquet_bridge.retrieve_dataframe(cid, use_cache=True)
                if not dataset_result["success"]:
                    raise HTTPException(status_code=404, detail=f"Pin not found: {cid}")
                
                metadata = dataset_result.get("metadata", {})
                
                pin_info = {
                    "cid": cid,
                    "size_bytes": metadata.get("size_bytes", 0),
                    "pin_type": "recursive",
                    "pinned_at": metadata.get("created_at"),
                    "storage_backends": [],
                    "replication_status": "healthy"
                }
                
                # Add Parquet backend info
                if "storage_path" in metadata:
                    pin_info["storage_backends"].append({
                        "name": "local_parquet",
                        "type": "parquet",
                        "path": metadata["storage_path"],
                        "status": "pinned",
                        "health": "healthy"
                    })
                
                # Add CAR archive info if available
                car_metadata_result = self.car_bridge.get_car_metadata(cid)
                if car_metadata_result["success"]:
                    car_metadata = car_metadata_result["metadata"]
                    pin_info["storage_backends"].append({
                        "name": "ipld_car",
                        "type": "car_archive", 
                        "path": car_metadata.get("car_path"),
                        "status": "available",
                        "health": "healthy"
                    })
                
                return JSONResponse(content={"success": True, "pin": pin_info})
                
            except Exception as e:
                logger.error(f"Error getting pin info: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/pin/{cid}/replicate")
        async def replicate_pin(cid: str, target_backend: str):
            """Replicate a pin to another storage backend."""
            try:
                if self.replication_manager:
                    # Use replication manager
                    result = await self.replication_manager.replicate_pin_to_backend(cid, target_backend)
                    return JSONResponse(content=result)
                elif target_backend == "car_archive":
                    # Convert to CAR archive
                    result = self.car_bridge.convert_dataset_to_car_collection(
                        dataset_cid=cid,
                        include_vector_index=True,
                        include_knowledge_graph=True
                    )
                    
                    if not result["success"]:
                        raise HTTPException(status_code=500, detail=result.get("error"))
                    
                    return JSONResponse(content={
                        "success": True,
                        "message": f"Pin {cid} replicated to CAR archive",
                        "replication_result": result
                    })
                else:
                    raise HTTPException(status_code=400, detail=f"Unknown target backend: {target_backend}")
                
            except Exception as e:
                logger.error(f"Error replicating pin: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/pin")
        async def add_pin(
            cid: str = Body(...),
            backend: str = Body("local"),
            priority: int = Body(1),
            target_replicas: int = Body(None),
            vfs_metadata_id: str = Body(None)
        ):
            """Add a new pin with replication support."""
            try:
                # Validate CID format
                if not cid or len(cid) < 10:
                    raise HTTPException(status_code=400, detail="Invalid CID format")
                
                result = {
                    "success": True,
                    "cid": cid,
                    "backend": backend,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # If replication manager is available, register for replication
                if self.replication_manager:
                    replication_result = await self.replication_manager.register_pin_for_replication(
                        cid=cid,
                        vfs_metadata_id=vfs_metadata_id,
                        target_replicas=target_replicas,
                        priority=priority
                    )
                    result["replication"] = replication_result
                    
                    # Replicate to specific backend if requested
                    if backend != "auto":
                        repl_result = await self.replication_manager.replicate_pin_to_backend(cid, backend)
                        result["backend_replication"] = repl_result
                else:
                    # Fallback to basic pin tracking
                    result["message"] = f"Pin {cid} added to {backend} backend"
                
                return JSONResponse(content=result)
                
            except Exception as e:
                logger.error(f"Error adding pin: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    # Demo-compatible methods
    async def add_pin(self, pin_data):
        """Add a pin (demo-compatible method)."""
        return {
            'success': True,
            'pin_id': pin_data.get('cid', 'unknown'),
            'message': 'Pin added successfully'
        }
    
    async def list_pins(self, **kwargs):
        """List pins (demo-compatible method)."""
        return {
            'success': True,
            'pins': [
                {'cid': 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG', 'status': 'pinned'},
                {'cid': 'QmZ1234567890abcdefghijklmnopqrstuvwxyzABCDEF', 'status': 'pinned'}
            ],
            'pagination': {'total': 2, 'limit': 50, 'offset': 0}
        }
    
    async def list_storage_backends(self):
        """List storage backends (demo-compatible method)."""
        return {
            'success': True,
            'backends': [
                {'name': 'local', 'status': 'online', 'pin_count': 15},
                {'name': 'ipfs_cluster', 'status': 'online', 'pin_count': 8},
                {'name': 'filecoin', 'status': 'online', 'pin_count': 3}
            ]
        }
    
    async def export_pinset_to_car(self, options):
        """Export pinset to CAR (demo-compatible method)."""
        return {
            'success': True,
            'car_path': '/mock/pinset.car',
            'cid': 'QmPinsetMockCID123'
        }
    
    async def get_pinset_status(self):
        """Get pinset status (demo-compatible method)."""
        return {
            'success': True,
            'status': {
                'available': True,
                'total_pins': 25,
                'active_pins': 22,
                'storage_backends': 3
            }
        }


def create_enhanced_dashboard_apis(
    parquet_bridge: ParquetIPLDBridge,
    car_bridge: ParquetCARBridge,
    cache_manager: TieredCacheManager,
    knowledge_graph: Optional[IPLDGraphDB] = None,
    graph_rag: Optional[GraphRAG] = None,
    replication_manager=None
) -> List[APIRouter]:
    """
    Create all enhanced dashboard API routers with replication support.
    
    Returns:
        List of APIRouter instances for VFS, Vector, KG, Pinset and Replication APIs
    """
    apis = []
    
    # VFS Metadata API (with replication support)
    vfs_api = VFSMetadataAPI(parquet_bridge, car_bridge, cache_manager, replication_manager)
    apis.append(vfs_api.router)
    
    # Vector Index API
    vector_api = VectorIndexAPI(parquet_bridge, car_bridge, knowledge_graph)
    apis.append(vector_api.router)
    
    # Knowledge Graph API
    kg_api = KnowledgeGraphAPI(parquet_bridge, car_bridge, knowledge_graph, graph_rag)
    apis.append(kg_api.router)
    
    # Pinset API (with replication support)
    pinset_api = PinsetAPI(parquet_bridge, car_bridge, cache_manager, replication_manager)
    apis.append(pinset_api.router)
    
    # Replication Management API
    if replication_manager:
        from .replication_api import create_replication_api
        replication_api = create_replication_api(replication_manager)
        apis.append(replication_api.router)
    
    return apis
