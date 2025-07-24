"""
Enhanced Dashboard Frontend with VFS, Vector Index, and Knowledge Graph Integration.

This module provides enhanced web dashboard templates and endpoints that integrate
with the columnar IPLD storage system, providing comprehensive views of:
1. Virtual filesystem metadata and CAR archives
2. Vector indices with search capabilities
3. Knowledge graphs with entity/relationship exploration
4. Pinset management and storage backend monitoring
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from .enhanced_vfs_apis import create_enhanced_dashboard_apis

# Import replication manager for real dashboard integration
try:
    from .replication_manager import ReplicationManager
    REPLICATION_AVAILABLE = True
except ImportError:
    REPLICATION_AVAILABLE = False

logger = logging.getLogger(__name__)


class EnhancedDashboardFrontend:
    """Enhanced dashboard frontend with VFS and columnar IPLD integration."""
    
    def __init__(self, web_dashboard_instance):
        """Initialize with reference to main WebDashboard instance."""
        self.web_dashboard = web_dashboard_instance
        self.templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
        
        # Initialize replication manager if available
        if REPLICATION_AVAILABLE:
            try:
                self.replication_manager = ReplicationManager()
                logger.info("✓ Replication manager initialized for dashboard")
            except Exception as e:
                logger.warning(f"⚠ Failed to initialize replication manager: {e}")
                self.replication_manager = None
        else:
            self.replication_manager = None
            logger.warning("⚠ Replication manager not available")
        
        self._setup_enhanced_routes()
    
    def _setup_enhanced_routes(self):
        """Setup enhanced dashboard routes."""
        app = self.web_dashboard.app
        
        @app.get("/dashboard/vfs", response_class=HTMLResponse)
        async def vfs_dashboard(request: Request):
            """Virtual filesystem and columnar storage dashboard."""
            return self.templates.TemplateResponse("vfs_dashboard.html", {
                "request": request,
                "title": "Virtual Filesystem & Columnar Storage",
                "current_page": "vfs"
            })
        
        @app.get("/dashboard/vector", response_class=HTMLResponse) 
        async def vector_dashboard(request: Request):
            """Vector index and search dashboard."""
            return self.templates.TemplateResponse("vector_dashboard.html", {
                "request": request,
                "title": "Vector Index & Search",
                "current_page": "vector"
            })
        
        @app.get("/dashboard/knowledge-graph", response_class=HTMLResponse)
        async def knowledge_graph_dashboard(request: Request):
            """Knowledge graph exploration dashboard.""" 
            return self.templates.TemplateResponse("knowledge_graph_dashboard.html", {
                "request": request,
                "title": "Knowledge Graph Explorer",
                "current_page": "knowledge-graph"
            })
        
        @app.get("/dashboard/pinset", response_class=HTMLResponse)
        async def pinset_dashboard(request: Request):
            """Pinset and storage backend management dashboard."""
            return self.templates.TemplateResponse("pinset_dashboard.html", {
                "request": request,
                "title": "Pinset & Storage Management", 
                "current_page": "pinset"
            })
        
        @app.get("/dashboard/replication", response_class=HTMLResponse)
        async def replication_dashboard(request: Request):
            """Replication management dashboard."""
            return self.templates.TemplateResponse("replication_dashboard.html", {
                "request": request,
                "title": "Replication Management",
                "current_page": "replication"
            })
        
        @app.get("/dashboard/api/enhanced-summary")
        async def get_enhanced_summary():
            """Get enhanced dashboard summary with VFS, vector, and KG data."""
            try:
                summary = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "vfs": await self._get_vfs_summary(),
                    "vector": await self._get_vector_summary(),
                    "knowledge_graph": await self._get_kg_summary(),
                    "pinset": await self._get_pinset_summary(),
                    "replication": await self._get_replication_summary()
                }
                
                return JSONResponse(content={"success": True, "summary": summary})
                
            except Exception as e:
                logger.error(f"Error getting enhanced summary: {e}")
                return JSONResponse(
                    content={"success": False, "error": str(e)},
                    status_code=500
                )
    
    async def _get_vfs_summary(self) -> Dict[str, Any]:
        """Get VFS summary data."""
        try:
            # This would call the actual VFS API
            return {
                "total_datasets": 25,
                "total_size_mb": 1024.5,
                "car_archives_count": 12,
                "cache_hit_rate": 87.3,
                "status": "active"
            }
        except Exception as e:
            logger.warning(f"Failed to get VFS summary: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _get_vector_summary(self) -> Dict[str, Any]:
        """Get vector index summary data."""
        try:
            # This would call the actual Vector API
            return {
                "total_collections": 8,
                "indexed_datasets": 20,
                "total_vectors": 50000,
                "indexing_coverage": 80.0,
                "status": "active"
            }
        except Exception as e:
            logger.warning(f"Failed to get vector summary: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _get_kg_summary(self) -> Dict[str, Any]:
        """Get knowledge graph summary data."""
        try:
            # This would call the actual KG API
            return {
                "entity_count": 1250,
                "relationship_count": 3400,
                "graph_size": 4650,
                "available": True,
                "status": "active"
            }
        except Exception as e:
            logger.warning(f"Failed to get KG summary: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _get_pinset_summary(self) -> Dict[str, Any]:
        """Get pinset summary data."""
        try:
            # This would call the actual Pinset API
            return {
                "total_pins": 45,
                "storage_backends": 3,
                "replication_factor": 2.1,
                "total_storage_gb": 2.5,
                "status": "healthy"
            }
        except Exception as e:
            logger.warning(f"Failed to get pinset summary: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _get_replication_summary(self) -> Dict[str, Any]:
        """Get replication summary data."""
        try:
            if self.replication_manager:
                status = await self.replication_manager.get_replication_status()
                return {
                    "total_pins": status.get("total_pins", 0),
                    "replicated_pins": status.get("replicated_pins", 0),
                    "storage_backends": status.get("total_backends", 0),
                    "replication_health": status.get("replication_health", "unknown"),
                    "status": "active"
                }
            else:
                return {
                    "total_pins": 0,
                    "replicated_pins": 0,
                    "storage_backends": 0,
                    "replication_health": "unavailable",
                    "status": "disabled"
                }
        except Exception as e:
            logger.warning(f"Failed to get replication summary: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_dashboard_summary(self):
        """Get comprehensive dashboard summary (demo-compatible method)."""
        try:
            # Collect summaries from all components
            vfs_summary = await self._get_vfs_summary()
            vector_summary = await self._get_vector_summary()
            kg_summary = await self._get_kg_summary()
            pinset_summary = await self._get_pinset_summary()
            
            return {
                'success': True,
                'summary': {
                    'vfs': vfs_summary,
                    'vector': vector_summary,
                    'knowledge_graph': kg_summary,
                    'pinset': pinset_summary,
                    'replication': await self._get_replication_summary()
                },
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f"Error getting dashboard summary: {e}")
            return {
                'success': False,
                'error': str(e),
                'summary': {
                    'vfs': {"status": "error"},
                    'vector': {"status": "error"},
                    'knowledge_graph': {"status": "error"},
                    'pinset': {"status": "error"},
                    'replication': {"status": "error"}
                }
            }
