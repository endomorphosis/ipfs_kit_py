#!/usr/bin/env python3
"""
Standalone Enhanced MCP Dashboard - Minimal version for testing bucket management features

This simplified version runs without full IPFS Kit dependencies to demonstrate
the enhanced bucket management UI and functionality.
"""

import json
import logging
import os
import time
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Web framework imports
from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger(__name__)

class StandaloneEnhancedDashboard:
    """Standalone version of enhanced MCP dashboard for testing."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the standalone enhanced dashboard."""
        if config is None:
            config = {
                'host': '127.0.0.1',
                'port': 8004,
                'data_dir': '~/.ipfs_kit_test',
                'debug': True
            }
        
        self.config = config
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 8004)
        self.data_dir = Path(config.get('data_dir', '~/.ipfs_kit_test')).expanduser()
        self.debug = config.get('debug', True)
        
        # Create data directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "buckets").mkdir(exist_ok=True)
        (self.data_dir / "bucket_configs").mkdir(exist_ok=True)
        (self.data_dir / "bucket_index").mkdir(exist_ok=True)
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="Enhanced MCP Dashboard - Standalone",
            description="Testing enhanced bucket management features",
            version="1.0.0"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Set up routes
        self._setup_routes()
        
        # Create sample data
        self._create_sample_data()
    
    def _setup_routes(self):
        """Set up FastAPI routes."""
        
        # Serve static files
        current_dir = Path(__file__).parent
        dashboard_dir = current_dir / "ipfs_kit_py" / "mcp" / "dashboard"
        
        if not dashboard_dir.exists():
            # Try different path structure
            dashboard_dir = Path("ipfs_kit_py/mcp/dashboard")
        
        if dashboard_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(dashboard_dir / "static")), name="static")
            templates = Jinja2Templates(directory=str(dashboard_dir / "templates"))
        else:
            print(f"Warning: Dashboard directory not found at {dashboard_dir}")
            print("Creating minimal inline templates...")
            templates = None
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Serve the main dashboard."""
            if templates:
                return templates.TemplateResponse(
                    "dashboard.html", 
                    {"request": request, "port": self.port}
                )
            else:
                return HTMLResponse(content="""
                <!DOCTYPE html>
                <html><head><title>Enhanced Dashboard - Static Files Not Found</title></head>
                <body><h1>Enhanced MCP Dashboard</h1>
                <p>Dashboard static files not found. The enhanced features have been implemented but templates are not accessible.</p>
                <p>API endpoints are available at:</p>
                <ul>
                    <li><a href="/api/buckets">/api/buckets</a> - List buckets</li>
                    <li><a href="/api/system/overview">/api/system/overview</a> - System overview</li>
                </ul>
                </body></html>
                """)
        
        # API Routes
        @self.app.get("/api/system/overview")
        async def api_system_overview():
            """Get system overview data."""
            return {
                "status": "running",
                "version": "1.0.0-enhanced",
                "uptime": 3600,
                "counts": {
                    "buckets": len(list((self.data_dir / "buckets").iterdir())),
                    "files": sum(len(list(bucket.rglob('*'))) for bucket in (self.data_dir / "buckets").iterdir() if bucket.is_dir()),
                    "backends": 3
                }
            }
        
        @self.app.get("/api/buckets")
        async def api_buckets():
            """Get buckets data."""
            return await self._get_buckets_data()
        
        @self.app.post("/api/buckets")
        async def api_create_bucket(request: Request):
            """Create a new bucket."""
            try:
                data = await request.json()
                bucket_name = data.get("name") or data.get("bucket_name")
                bucket_type = data.get("backend", data.get("bucket_type", "local"))
                description = data.get("description", "")
                
                if not bucket_name:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Bucket name is required"}
                    )
                
                result = await self._create_bucket(bucket_name, bucket_type, description)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in create_bucket API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to create bucket: {str(e)}"}
                )

        @self.app.delete("/api/buckets/{bucket_name}")
        async def api_delete_bucket(bucket_name: str):
            """Delete a bucket."""
            try:
                result = await self._delete_bucket(bucket_name)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in delete_bucket API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to delete bucket: {str(e)}"}
                )

        @self.app.get("/api/buckets/{bucket_name}")
        async def api_get_bucket_details(bucket_name: str):
            """Get bucket details."""
            try:
                result = await self._get_bucket_details(bucket_name)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in get_bucket_details API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to get bucket details: {str(e)}"}
                )

        @self.app.get("/api/buckets/{bucket_name}/files")
        async def api_get_bucket_files(bucket_name: str):
            """Get list of files in a bucket."""
            try:
                result = await self._get_bucket_files(bucket_name)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in get_bucket_files API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to get bucket files: {str(e)}"}
                )

        @self.app.post("/api/buckets/{bucket_name}/upload")
        async def api_upload_file_to_bucket(bucket_name: str, file: UploadFile = File(...)):
            """Upload a file to a bucket."""
            try:
                result = await self._upload_file_to_bucket(bucket_name, file)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in upload_to_bucket API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to upload file: {str(e)}"}
                )

        @self.app.get("/api/buckets/{bucket_name}/download/{file_path:path}")
        async def api_download_file_from_bucket(bucket_name: str, file_path: str):
            """Download a file from a bucket."""
            try:
                return await self._download_file_from_bucket(bucket_name, file_path)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error in download_file API: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

        @self.app.delete("/api/buckets/{bucket_name}/files/{file_name}")
        async def api_delete_file_from_bucket(bucket_name: str, file_name: str):
            """Delete a file from a bucket."""
            try:
                result = await self._delete_file_from_bucket(bucket_name, file_name)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in delete_file API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to delete file: {str(e)}"}
                )

        @self.app.put("/api/buckets/{bucket_name}/settings")
        async def api_update_bucket_settings(bucket_name: str, request: Request):
            """Update bucket settings."""
            try:
                settings = await request.json()
                result = await self._update_bucket_settings(bucket_name, settings)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in update_bucket_settings API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to update bucket settings: {str(e)}"}
                )

    def _create_sample_data(self):
        """Create sample buckets and files for testing."""
        sample_buckets = [
            {
                "name": "demo-bucket",
                "backend": "local", 
                "description": "Demo bucket with sample files",
                "settings": {
                    "cache_enabled": True,
                    "vector_search": True,
                    "knowledge_graph": False,
                    "storage_quota": 1000
                }
            },
            {
                "name": "test-uploads", 
                "backend": "s3",
                "description": "Test bucket for file uploads",
                "settings": {
                    "cache_enabled": False,
                    "vector_search": False, 
                    "knowledge_graph": True,
                    "storage_quota": 500
                }
            }
        ]
        
        for bucket_data in sample_buckets:
            bucket_path = self.data_dir / "buckets" / bucket_data["name"]
            bucket_path.mkdir(parents=True, exist_ok=True)
            
            # Create sample files
            if bucket_data["name"] == "demo-bucket":
                (bucket_path / "readme.txt").write_text(f"This is a sample file in {bucket_data['name']}")
                (bucket_path / "data.json").write_text('{"sample": "data", "created": "' + datetime.now().isoformat() + '"}')
            
            # Create bucket config
            config_path = self.data_dir / "bucket_configs" / f"{bucket_data['name']}.yaml"
            bucket_config = {
                **bucket_data,
                "created_at": datetime.now().isoformat()
            }
            with open(config_path, 'w') as f:
                yaml.dump(bucket_config, f)

    # Backend implementation methods (simplified versions from main dashboard)
    async def _get_buckets_data(self):
        """Get buckets data with enhanced information."""
        buckets = []
        
        for bucket_dir in (self.data_dir / "buckets").iterdir():
            if bucket_dir.is_dir():
                bucket_name = bucket_dir.name
                
                # Calculate storage usage
                total_size = sum(f.stat().st_size for f in bucket_dir.rglob('*') if f.is_file())
                file_count = len(list(bucket_dir.rglob('*')))
                
                # Load bucket config
                bucket_config_file = self.data_dir / "bucket_configs" / f"{bucket_name}.yaml"
                settings = {}
                backend = "local"
                description = ""
                
                if bucket_config_file.exists():
                    try:
                        with open(bucket_config_file, 'r') as f:
                            config = yaml.safe_load(f) or {}
                            settings = config.get("settings", {})
                            backend = config.get("backend", "local")
                            description = config.get("description", "")
                    except Exception as e:
                        logger.warning(f"Could not load bucket config for {bucket_name}: {e}")
                
                bucket = {
                    "name": bucket_name,
                    "backend": backend,
                    "description": description,
                    "storage_used": total_size,
                    "file_count": file_count,
                    "vector_search": settings.get("vector_search", False),
                    "knowledge_graph": settings.get("knowledge_graph", False),
                    "cache_enabled": settings.get("cache_enabled", False),
                    "settings": settings,
                    "created_at": datetime.now().isoformat()
                }
                buckets.append(bucket)
        
        return {"buckets": buckets}

    async def _create_bucket(self, bucket_name, bucket_type, description):
        """Create bucket with proper directory structure and metadata."""
        try:
            bucket_path = self.data_dir / "buckets" / bucket_name
            if bucket_path.exists():
                return {"success": False, "error": "Bucket already exists"}
                
            bucket_path.mkdir(parents=True)
            
            # Create bucket configuration
            bucket_config = {
                "name": bucket_name,
                "type": bucket_type,
                "backend": bucket_type,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "settings": {
                    "cache_enabled": True,
                    "cache_ttl": 3600,
                    "vector_search": False,
                    "knowledge_graph": False,
                    "public_access": False,
                    "storage_quota": None,
                    "max_files": None,
                    "max_file_size": 500,
                    "retention_days": None
                }
            }
            
            config_path = self.data_dir / "bucket_configs" / f"{bucket_name}.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(bucket_config, f)
            
            return {"success": True, "message": f"Bucket '{bucket_name}' created successfully"}
            
        except Exception as e:
            logger.error(f"Error creating bucket: {e}")
            return {"success": False, "error": str(e)}

    async def _delete_bucket(self, bucket_name):
        """Delete bucket and clean up all associated data."""
        try:
            import shutil
            
            bucket_path = self.data_dir / "buckets" / bucket_name
            if bucket_path.exists():
                shutil.rmtree(bucket_path)
            
            config_path = self.data_dir / "bucket_configs" / f"{bucket_name}.yaml"
            if config_path.exists():
                config_path.unlink()
            
            return {"success": True, "message": f"Bucket '{bucket_name}' deleted successfully"}
            
        except Exception as e:
            logger.error(f"Error deleting bucket: {e}")
            return {"success": False, "error": str(e)}

    async def _get_bucket_details(self, bucket_name):
        """Get detailed bucket information."""
        try:
            bucket_path = self.data_dir / "buckets" / bucket_name
            if not bucket_path.exists():
                return {"success": False, "error": "Bucket not found"}
            
            config_path = self.data_dir / "bucket_configs" / f"{bucket_name}.yaml"
            bucket_info = {"name": bucket_name, "backend": "local"}
            
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
                    bucket_info.update(config)
            
            # Calculate stats
            total_size = sum(f.stat().st_size for f in bucket_path.rglob('*') if f.is_file())
            file_count = len(list(bucket_path.glob('*')))
            
            bucket_info.update({
                "storage_used": total_size,
                "file_count": file_count,
                "last_accessed": datetime.now().isoformat()
            })
            
            return {"success": True, "bucket": bucket_info}
            
        except Exception as e:
            logger.error(f"Error getting bucket details: {e}")
            return {"success": False, "error": str(e)}

    async def _get_bucket_files(self, bucket_name):
        """Get list of files in a bucket."""
        try:
            bucket_path = self.data_dir / "buckets" / bucket_name
            if not bucket_path.exists():
                return {"success": False, "error": "Bucket not found", "files": []}
            
            files = []
            for file_path in bucket_path.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append({
                        "name": file_path.name,
                        "size": stat.st_size,
                        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "path": file_path.name,
                        "type": "file"
                    })
            
            return {"success": True, "files": files}
            
        except Exception as e:
            logger.error(f"Error getting bucket files: {e}")
            return {"success": False, "error": str(e), "files": []}

    async def _upload_file_to_bucket(self, bucket_name, file):
        """Upload file to bucket."""
        try:
            bucket_path = self.data_dir / "buckets" / bucket_name
            if not bucket_path.exists():
                return {"success": False, "error": "Bucket not found"}
            
            content = await file.read()
            file_path = bucket_path / file.filename
            
            with open(file_path, 'wb') as f:
                f.write(content)
            
            return {"success": True, "message": f"File '{file.filename}' uploaded successfully"}
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return {"success": False, "error": str(e)}

    async def _download_file_from_bucket(self, bucket_name, file_path):
        """Download file from bucket."""
        try:
            bucket_path = self.data_dir / "buckets" / bucket_name
            full_file_path = bucket_path / file_path
            
            if not full_file_path.exists():
                raise HTTPException(status_code=404, detail="File not found")
            
            return FileResponse(
                path=str(full_file_path),
                filename=full_file_path.name,
                media_type='application/octet-stream'
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _delete_file_from_bucket(self, bucket_name, file_name):
        """Delete a file from a bucket."""
        try:
            bucket_path = self.data_dir / "buckets" / bucket_name
            file_path = bucket_path / file_name
            
            if not file_path.exists():
                return {"success": False, "error": "File not found"}
            
            file_path.unlink()
            return {"success": True, "message": f"File '{file_name}' deleted successfully"}
            
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return {"success": False, "error": str(e)}

    async def _update_bucket_settings(self, bucket_name, settings):
        """Update bucket settings."""
        try:
            config_path = self.data_dir / "bucket_configs" / f"{bucket_name}.yaml"
            
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {"name": bucket_name, "backend": "local"}
            
            if "settings" not in config:
                config["settings"] = {}
            
            config["settings"].update(settings)
            config["updated_at"] = datetime.now().isoformat()
            
            # Update description if provided
            if "description" in settings:
                config["description"] = settings["description"]
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f)
            
            return {"success": True, "message": "Bucket settings updated successfully"}
            
        except Exception as e:
            logger.error(f"Error updating bucket settings: {e}")
            return {"success": False, "error": str(e)}

    def run(self):
        """Run the standalone dashboard server."""
        print(f"🚀 Starting Enhanced MCP Dashboard (Standalone)")
        print(f"📍 URL: http://{self.host}:{self.port}")
        print(f"💾 Data directory: {self.data_dir}")
        print("=" * 50)
        
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info" if not self.debug else "debug"
        )

def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO)
    
    dashboard = StandaloneEnhancedDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()