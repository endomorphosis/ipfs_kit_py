#!/usr/bin/env python3
"""
Comprehensive Dashboard Integration

Adds all 86+ comprehensive MCP server features to the bucket dashboard,
bringing full feature parity with the old comprehensive dashboard.
"""

import anyio
import json
import logging
import os
import importlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComprehensiveDashboardIntegration:
    """
    Integrates all 86+ comprehensive handlers into the bucket dashboard.
    Provides feature parity with the old comprehensive dashboard.
    """
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.handlers = {}
        self.handler_categories = {
            'system': [
                'get_system_status', 'get_system_health', 'get_system_metrics',
                'get_detailed_metrics', 'get_metrics_history'
            ],
            'mcp': [
                'get_mcp_status', 'restart_mcp_server', 'list_mcp_tools',
                'call_mcp_tool', 'list_all_mcp_tools', 'mcp_backend_action',
                'mcp_storage_action', 'mcp_daemon_action', 'mcp_vfs_action',
                'get_mcp_config', 'update_mcp_config'
            ],
            'backend': [
                'get_backends', 'get_backend_health', 'sync_backend',
                'get_backend_stats', 'get_all_backend_configs', 'create_backend_config',
                'update_backend_config', 'delete_backend_config', 'test_backend_config',
                'test_backend_connection'
            ],
            'bucket': [
                'get_buckets', 'create_bucket', 'get_bucket_details',
                'delete_bucket', 'list_bucket_files', 'upload_to_bucket',
                'download_from_bucket', 'delete_bucket_file'
            ],
            'vfs': [
                'get_bucket_index', 'create_bucket_index', 'rebuild_bucket_index',
                'get_bucket_index_info', 'get_vfs_structure', 'browse_vfs'
            ],
            'pin': [
                'get_pins', 'add_pin', 'remove_pin', 'sync_pins',
                'get_backend_pins', 'add_backend_pin', 'remove_backend_pin',
                'find_pin_across_backends'
            ],
            'service': [
                'get_services', 'control_service', 'get_service_details'
            ],
            'config': [
                'get_all_configs', 'get_configs_by_type', 'get_specific_config',
                'create_config', 'update_config', 'delete_config', 'validate_config',
                'test_config', 'get_all_service_configs', 'get_service_config',
                'create_service_config', 'update_service_config', 'delete_service_config',
                'get_all_vfs_backend_configs', 'create_vfs_backend_config',
                'get_backend_schemas', 'validate_backend_config', 'get_config_schemas',
                'get_config_schema', 'validate_config_data', 'list_config_files',
                'get_config_file', 'update_config_file', 'delete__config_file',
                'backup_config', 'restore_config', 'get_component_config'
            ],
            'log': [
                'get_logs', 'stream_logs'
            ],
            'peer': [
                'get_peers', 'connect_peer', 'get_peer_stats'
            ],
            'analytics': [
                'get_analytics_summary', 'get_bucket_analytics', 'get_performance_analytics'
            ]
        }
        
    async def load_handlers(self):
        """Load all comprehensive handlers dynamically."""
        logger.info("Loading comprehensive handlers...")
        
        loaded_count = 0
        failed_count = 0
        
        for category, handler_names in self.handler_categories.items():
            self.handlers[category] = {}
            
            for handler_name in handler_names:
                try:
                    # Import handler module
                    module_name = f"mcp_handlers.{handler_name}_handler"
                    module = importlib.import_module(module_name)
                    
                    # Try different handler patterns
                    handler_func = None
                    
                    # Pattern 1: handle_{handler_name} function
                    try:
                        handler_func = getattr(module, f"handle_{handler_name}")
                    except AttributeError:
                        pass
                    
                    # Pattern 2: {HandlerName}Handler class with handle method  
                    if not handler_func:
                        try:
                            class_name = ''.join(word.capitalize() for word in handler_name.split('_')) + 'Handler'
                            handler_class = getattr(module, class_name)
                            # Create instance with default ipfs_kit_dir
                            handler_instance = handler_class(Path("~/.ipfs_kit").expanduser())
                            handler_func = handler_instance.handle
                        except (AttributeError, TypeError):
                            pass
                    
                    # Pattern 3: Generic handle function
                    if not handler_func:
                        try:
                            handler_func = getattr(module, "handle")
                        except AttributeError:
                            pass
                    
                    if handler_func:
                        self.handlers[category][handler_name] = handler_func
                        loaded_count += 1
                    else:
                        logger.warning(f"No handler function found in {module_name}")
                        failed_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to load handler {handler_name}: {e}")
                    failed_count += 1
        
        logger.info(f"Loaded {loaded_count} handlers, {failed_count} failed")
        return loaded_count, failed_count
    
    def setup_comprehensive_routes(self):
        """Setup all comprehensive API routes."""
        
        # Comprehensive API endpoint
        @self.app.post("/api/comprehensive/{category}/{action}")
        async def comprehensive_action(category: str, action: str, request: Request):
            """
            Universal endpoint for all comprehensive features.
            Routes: /api/comprehensive/{category}/{action}
            
            Examples:
            - POST /api/comprehensive/system/get_system_status
            - POST /api/comprehensive/bucket/create_bucket
            - POST /api/comprehensive/mcp/list_mcp_tools
            """
            try:
                # Validate category
                if category not in self.handlers:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False, 
                            "error": f"Unknown category: {category}",
                            "available_categories": list(self.handlers.keys())
                        }
                    )
                
                # Validate action
                if action not in self.handlers[category]:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "error": f"Unknown action: {action}",
                            "available_actions": list(self.handlers[category].keys())
                        }
                    )
                
                # Get handler
                handler = self.handlers[category][action]
                
                # Get request data
                try:
                    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
                except:
                    data = {}
                
                # Call handler
                result = await handler(data)
                
                return JSONResponse(content={
                    "success": True,
                    "data": result,
                    "category": category,
                    "action": action,
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error in comprehensive action {category}/{action}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": str(e),
                        "category": category,
                        "action": action
                    }
                )
        
        # API discovery endpoint
        @self.app.get("/api/comprehensive")
        async def list_comprehensive_features():
            """List all available comprehensive features by category."""
            return JSONResponse(content={
                "success": True,
                "data": {
                    "categories": list(self.handlers.keys()),
                    "features_by_category": {
                        category: list(handlers.keys())
                        for category, handlers in self.handlers.items()
                    },
                    "total_features": sum(len(handlers) for handlers in self.handlers.values()),
                    "description": "Comprehensive MCP server features integrated into bucket dashboard"
                }
            })
        
        # Category-specific endpoints
        @self.app.get("/api/comprehensive/{category}")
        async def list_category_features(category: str):
            """List features available in a specific category."""
            if category not in self.handlers:
                return JSONResponse(
                    status_code=404,
                    content={
                        "success": False,
                        "error": f"Category not found: {category}",
                        "available_categories": list(self.handlers.keys())
                    }
                )
            
            return JSONResponse(content={
                "success": True,
                "data": {
                    "category": category,
                    "features": list(self.handlers[category].keys()),
                    "feature_count": len(self.handlers[category])
                }
            })
        
        # Batch operation endpoint
        @self.app.post("/api/comprehensive/batch")
        async def batch_comprehensive_actions(request: Request):
            """
            Execute multiple comprehensive actions in sequence.
            
            Request format:
            {
                "actions": [
                    {"category": "system", "action": "get_system_status", "data": {}},
                    {"category": "bucket", "action": "get_buckets", "data": {}}
                ]
            }
            """
            try:
                body = await request.json()
                actions = body.get("actions", [])
                
                if not actions:
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "error": "No actions provided"}
                    )
                
                results = []
                for i, action_spec in enumerate(actions):
                    try:
                        category = action_spec.get("category")
                        action = action_spec.get("action")
                        data = action_spec.get("data", {})
                        
                        if not category or not action:
                            results.append({
                                "index": i,
                                "success": False,
                                "error": "Missing category or action"
                            })
                            continue
                        
                        if category not in self.handlers or action not in self.handlers[category]:
                            results.append({
                                "index": i,
                                "success": False,
                                "error": f"Invalid category/action: {category}/{action}"
                            })
                            continue
                        
                        # Execute action
                        handler = self.handlers[category][action]
                        result = await handler(data)
                        
                        results.append({
                            "index": i,
                            "success": True,
                            "data": result,
                            "category": category,
                            "action": action
                        })
                        
                    except Exception as e:
                        results.append({
                            "index": i,
                            "success": False,
                            "error": str(e),
                            "category": action_spec.get("category"),
                            "action": action_spec.get("action")
                        })
                
                return JSONResponse(content={
                    "success": True,
                    "data": {
                        "results": results,
                        "total_actions": len(actions),
                        "successful_actions": sum(1 for r in results if r["success"]),
                        "failed_actions": sum(1 for r in results if not r["success"])
                    }
                })
                
            except Exception as e:
                logger.error(f"Error in batch comprehensive actions: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )

async def integrate_comprehensive_features(app: FastAPI):
    """
    Main integration function to add comprehensive features to dashboard.
    
    Usage:
        app = FastAPI()
        await integrate_comprehensive_features(app)
    """
    logger.info("Starting comprehensive dashboard integration...")
    
    try:
        # Create integration instance
        integration = ComprehensiveDashboardIntegration(app)
        
        # Load all handlers
        loaded_count, failed_count = await integration.load_handlers()
        
        # Setup routes
        integration.setup_comprehensive_routes()
        
        logger.info(f"✅ Comprehensive integration complete!")
        logger.info(f"   - Loaded: {loaded_count} handlers")
        logger.info(f"   - Failed: {failed_count} handlers") 
        logger.info(f"   - Categories: {len(integration.handler_categories)}")
        logger.info(f"   - Routes added: /api/comprehensive/*")
        
        return {
            "success": True,
            "loaded_handlers": loaded_count,
            "failed_handlers": failed_count,
            "categories": len(integration.handler_categories),
            "total_features": sum(len(handlers) for handlers in integration.handler_categories.values())
        }
        
    except Exception as e:
        logger.error(f"Failed to integrate comprehensive features: {e}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    # For testing the integration
    from fastapi import FastAPI
    
    async def test_integration():
        app = FastAPI()
        result = await integrate_comprehensive_features(app)
        print(f"Integration result: {json.dumps(result, indent=2)}")
    
    anyio.run(test_integration)
