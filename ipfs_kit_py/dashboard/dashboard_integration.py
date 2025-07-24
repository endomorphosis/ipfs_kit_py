"""
Enhanced Dashboard Integration

Integrates the enhanced VFS, Vector, Knowledge Graph, and Pinset APIs
with the existing WebDashboard infrastructure.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .enhanced_vfs_apis import VFSMetadataAPI, VectorIndexAPI, KnowledgeGraphAPI, PinsetAPI
from .enhanced_frontend import EnhancedDashboardFrontend
from ..parquet_car_bridge import ParquetCARBridge

logger = logging.getLogger(__name__)


class DashboardEnhancementIntegrator:
    """Integrates enhanced columnar IPLD storage capabilities into the existing dashboard."""
    
    def __init__(self, dashboard_instance, ipfs_manager=None, dag_manager=None):
        """Initialize the enhancement integrator.
        
        Args:
            dashboard_instance: The existing WebDashboard instance
            ipfs_manager: IPFS manager instance for storage operations
            dag_manager: DAG manager for IPLD operations
        """
        self.dashboard = dashboard_instance
        self.ipfs_manager = ipfs_manager
        self.dag_manager = dag_manager
        
        # Initialize enhanced components
        self.car_bridge = None
        self.vfs_api = None
        self.vector_api = None
        self.kg_api = None
        self.pinset_api = None
        self.frontend = None
        
        logger.info("Dashboard enhancement integrator initialized")
    
    async def initialize_enhanced_apis(self):
        """Initialize all enhanced API components."""
        try:
            # Initialize Parquet-CAR bridge
            if self.ipfs_manager and self.dag_manager:
                self.car_bridge = ParquetCARBridge(
                    ipfs_manager=self.ipfs_manager,
                    dag_manager=self.dag_manager
                )
                logger.info("Parquet-CAR bridge initialized")
            
            # Initialize enhanced APIs
            self.vfs_api = VFSMetadataAPI(car_bridge=self.car_bridge)
            self.vector_api = VectorIndexAPI(car_bridge=self.car_bridge)
            self.kg_api = KnowledgeGraphAPI(car_bridge=self.car_bridge)
            self.pinset_api = PinsetAPI(car_bridge=self.car_bridge)
            
            # Initialize enhanced frontend
            self.frontend = EnhancedDashboardFrontend(
                vfs_api=self.vfs_api,
                vector_api=self.vector_api,
                kg_api=self.kg_api,
                pinset_api=self.pinset_api
            )
            
            logger.info("Enhanced APIs initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize enhanced APIs: {e}")
            raise
    
    def integrate_enhanced_routes(self):
        """Integrate enhanced routes into the existing dashboard."""
        try:
            # Add enhanced dashboard page routes
            self._add_enhanced_page_routes()
            
            # Add enhanced API routes
            self._add_enhanced_api_routes()
            
            logger.info("Enhanced routes integrated successfully")
            
        except Exception as e:
            logger.error(f"Failed to integrate enhanced routes: {e}")
            raise
    
    def _add_enhanced_page_routes(self):
        """Add enhanced dashboard page routes."""
        from fastapi import Request
        from fastapi.responses import HTMLResponse
        
        # VFS Dashboard
        @self.dashboard.app.get(f"{self.dashboard.config.dashboard_path}/vfs", response_class=HTMLResponse)
        async def enhanced_vfs_dashboard(request: Request):
            """Enhanced Virtual Filesystem dashboard."""
            return self.dashboard.templates.TemplateResponse("vfs_dashboard.html", {
                "request": request,
                "title": "Virtual Filesystem & Columnar Storage",
                "current_page": "vfs"
            })
        
        # Vector Index Dashboard
        @self.dashboard.app.get(f"{self.dashboard.config.dashboard_path}/vector", response_class=HTMLResponse)
        async def enhanced_vector_dashboard(request: Request):
            """Enhanced Vector Index dashboard."""
            return self.dashboard.templates.TemplateResponse("vector_dashboard.html", {
                "request": request,
                "title": "Vector Index Management",
                "current_page": "vector"
            })
        
        # Knowledge Graph Dashboard
        @self.dashboard.app.get(f"{self.dashboard.config.dashboard_path}/knowledge-graph", response_class=HTMLResponse)
        async def enhanced_kg_dashboard(request: Request):
            """Enhanced Knowledge Graph dashboard."""
            return self.dashboard.templates.TemplateResponse("knowledge_graph_dashboard.html", {
                "request": request,
                "title": "Knowledge Graph Explorer",
                "current_page": "knowledge-graph"
            })
        
        # Pinset Management Dashboard
        @self.dashboard.app.get(f"{self.dashboard.config.dashboard_path}/pinset", response_class=HTMLResponse)
        async def enhanced_pinset_dashboard(request: Request):
            """Enhanced Pinset Management dashboard."""
            return self.dashboard.templates.TemplateResponse("pinset_dashboard.html", {
                "request": request,
                "title": "Pinset Management",
                "current_page": "pinset"
            })
        
        logger.info("Enhanced page routes added")
    
    def _add_enhanced_api_routes(self):
        """Add enhanced API routes."""
        
        # VFS API Routes
        if self.vfs_api:
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/vfs/status")
            async def vfs_status():
                return await self.vfs_api.get_vfs_status()
            
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/vfs/datasets")
            async def vfs_datasets(limit: int = 50, offset: int = 0):
                return await self.vfs_api.list_datasets(limit=limit, offset=offset)
            
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/vfs/dataset/{dataset_id}")
            async def vfs_dataset_details(dataset_id: str):
                return await self.vfs_api.get_dataset_details(dataset_id)
            
            @self.dashboard.app.post(f"{self.dashboard.config.api_path}/vfs/convert-to-car")
            async def vfs_convert_to_car(request: Request):
                data = await request.json()
                return await self.vfs_api.convert_dataset_to_car(data)
        
        # Vector API Routes
        if self.vector_api:
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/vector/status")
            async def vector_status():
                return await self.vector_api.get_vector_status()
            
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/vector/collections")
            async def vector_collections():
                return await self.vector_api.list_collections()
            
            @self.dashboard.app.post(f"{self.dashboard.config.api_path}/vector/search")
            async def vector_search(request: Request):
                data = await request.json()
                return await self.vector_api.search_vectors(data)
            
            @self.dashboard.app.post(f"{self.dashboard.config.api_path}/vector/export-car")
            async def vector_export_car():
                return await self.vector_api.export_vector_indices_to_car()
        
        # Knowledge Graph API Routes
        if self.kg_api:
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/kg/status")
            async def kg_status():
                return await self.kg_api.get_kg_status()
            
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/kg/entities")
            async def kg_entities(limit: int = 50, offset: int = 0):
                return await self.kg_api.list_entities(limit=limit, offset=offset)
            
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/kg/entity/{entity_id}")
            async def kg_entity_details(entity_id: str, include_relationships: bool = False):
                return await self.kg_api.get_entity_details(entity_id, include_relationships)
            
            @self.dashboard.app.post(f"{self.dashboard.config.api_path}/kg/search")
            async def kg_search(request: Request):
                data = await request.json()
                return await self.kg_api.search_knowledge_graph(data)
            
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/kg/export-car")
            async def kg_export_car():
                return await self.kg_api.export_knowledge_graph_to_car()
        
        # Pinset API Routes
        if self.pinset_api:
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/pinset/status")
            async def pinset_status():
                return await self.pinset_api.get_pinset_status()
            
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/pinset/backends")
            async def pinset_backends():
                return await self.pinset_api.list_storage_backends()
            
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/pinset/pins")
            async def pinset_pins(limit: int = 50, offset: int = 0, query: str = None, 
                                 status: str = None, backend: str = None):
                filters = {}
                if query: filters['query'] = query
                if status: filters['status'] = status
                if backend: filters['backend'] = backend
                return await self.pinset_api.list_pins(limit=limit, offset=offset, filters=filters)
            
            @self.dashboard.app.get(f"{self.dashboard.config.api_path}/pinset/pin/{cid}")
            async def pinset_pin_details(cid: str):
                return await self.pinset_api.get_pin_details(cid)
            
            @self.dashboard.app.post(f"{self.dashboard.config.api_path}/pinset/pin")
            async def pinset_add_pin(request: Request):
                data = await request.json()
                return await self.pinset_api.add_pin(data)
            
            @self.dashboard.app.post(f"{self.dashboard.config.api_path}/pinset/export-car")
            async def pinset_export_car(request: Request):
                data = await request.json()
                return await self.pinset_api.export_pinset_to_car(data)
        
        logger.info("Enhanced API routes added")
    
    async def get_enhanced_summary_data(self) -> Dict[str, Any]:
        """Get summary data from all enhanced components."""
        summary_data = {}
        
        try:
            # VFS Summary
            if self.vfs_api:
                vfs_status = await self.vfs_api.get_vfs_status()
                if vfs_status.get('success'):
                    summary_data['vfs'] = vfs_status['status']
            
            # Vector Index Summary
            if self.vector_api:
                vector_status = await self.vector_api.get_vector_status()
                if vector_status.get('success'):
                    summary_data['vector'] = vector_status['status']
            
            # Knowledge Graph Summary
            if self.kg_api:
                kg_status = await self.kg_api.get_kg_status()
                if kg_status.get('success'):
                    summary_data['knowledge_graph'] = kg_status['status']
            
            # Pinset Summary
            if self.pinset_api:
                pinset_status = await self.pinset_api.get_pinset_status()
                if pinset_status.get('success'):
                    summary_data['pinset'] = pinset_status['status']
            
            logger.debug("Enhanced summary data collected")
            
        except Exception as e:
            logger.error(f"Error collecting enhanced summary data: {e}")
            summary_data['error'] = str(e)
        
        return summary_data
    
    def validate_integration(self) -> Dict[str, bool]:
        """Validate that all enhanced components are properly integrated."""
        validation_results = {
            'car_bridge_initialized': self.car_bridge is not None,
            'vfs_api_initialized': self.vfs_api is not None,
            'vector_api_initialized': self.vector_api is not None,
            'kg_api_initialized': self.kg_api is not None,
            'pinset_api_initialized': self.pinset_api is not None,
            'frontend_initialized': self.frontend is not None,
        }
        
        validation_results['all_components_ready'] = all(validation_results.values())
        
        logger.info(f"Integration validation: {validation_results}")
        return validation_results


async def enhance_existing_dashboard(dashboard_instance, ipfs_manager=None, dag_manager=None):
    """Enhance an existing dashboard instance with columnar IPLD capabilities.
    
    Args:
        dashboard_instance: The existing WebDashboard instance
        ipfs_manager: Optional IPFS manager instance
        dag_manager: Optional DAG manager instance
    
    Returns:
        DashboardEnhancementIntegrator: The integrator instance
    """
    integrator = DashboardEnhancementIntegrator(
        dashboard_instance=dashboard_instance,
        ipfs_manager=ipfs_manager,
        dag_manager=dag_manager
    )
    
    # Initialize enhanced APIs
    await integrator.initialize_enhanced_apis()
    
    # Integrate enhanced routes
    integrator.integrate_enhanced_routes()
    
    # Validate integration
    validation = integrator.validate_integration()
    
    if validation['all_components_ready']:
        logger.info("Dashboard enhancement completed successfully")
    else:
        logger.warning(f"Dashboard enhancement completed with issues: {validation}")
    
    return integrator
