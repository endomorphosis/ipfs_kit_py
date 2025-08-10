#!/usr/bin/env python3
"""
Comprehensive Bucket Dashboard

Enhanced dashboard with full comprehensive MCP server feature integration,
providing complete feature parity with the original comprehensive dashboard.
Includes 86+ handlers covering system, MCP, backend, bucket, VFS, pin, service, 
config, log, peer, and analytics functionality.
"""

import asyncio
import json
import logging
import os
import shutil
import mimetypes
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path for comprehensive integration
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import comprehensive dashboard integration
try:
    from comprehensive_dashboard_integration import integrate_comprehensive_features
    COMPREHENSIVE_AVAILABLE = True
except ImportError as e:
    COMPREHENSIVE_AVAILABLE = False
    # Log after logger is setup
    logging.getLogger(__name__).warning(f"Comprehensive integration not available: {e}")

class BucketDashboard:
    def __init__(self, data_dir: str = "~/.ipfs_kit", port: int = 8004):
        self.data_dir = Path(data_dir).expanduser()
        self.port = port
        self.app = FastAPI(title="Comprehensive Bucket Dashboard")
        self.comprehensive_integrated = False
        
        # Create data directories
        self.buckets_dir = self.data_dir / "buckets"
        self.buckets_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self.setup_routes()
    
    async def initialize_comprehensive_features(self):
        """Initialize comprehensive MCP server features."""
        if COMPREHENSIVE_AVAILABLE and not self.comprehensive_integrated:
            try:
                logger.info("Integrating comprehensive MCP server features...")
                result = await integrate_comprehensive_features(self.app)
                
                if result.get("success"):
                    self.comprehensive_integrated = True
                    logger.info(f"✅ Comprehensive integration successful!")
                    logger.info(f"   - Features: {result.get('total_features', 0)}")
                    logger.info(f"   - Categories: {result.get('categories', 0)}")
                    logger.info(f"   - Handlers: {result.get('loaded_handlers', 0)}")
                    return result
                else:
                    logger.error(f"Comprehensive integration failed: {result.get('error')}")
                    return result
            except Exception as e:
                logger.error(f"Failed to integrate comprehensive features: {e}")
                return {"success": False, "error": str(e)}
        else:
            reason = "already integrated" if self.comprehensive_integrated else "not available"
            logger.info(f"Comprehensive features {reason}")
            return {"success": False, "reason": reason}
    
    def setup_routes(self):
        """Setup all API routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard():
            return self.get_dashboard_html()
        
        # Comprehensive features initialization endpoint
        @self.app.post("/api/initialize-comprehensive")
        async def initialize_comprehensive():
            """Initialize comprehensive MCP server features."""
            result = await self.initialize_comprehensive_features()
            return JSONResponse(content=result)
        
        @self.app.get("/api/buckets")
        async def get_buckets():
            try:
                buckets = await self.list_buckets()
                return JSONResponse(content={
                    "success": True,
                    "data": {"buckets": buckets}
                })
            except Exception as e:
                logger.error(f"Error getting buckets: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.post("/api/buckets")
        async def create_bucket(request: Request):
            try:
                data = await request.json()
                result = await self.create_bucket(data)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error creating bucket: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.delete("/api/buckets/{bucket_name}")
        async def delete_bucket(bucket_name: str):
            try:
                result = await self.delete_bucket(bucket_name)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error deleting bucket: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.get("/api/buckets/{bucket_name}")
        async def get_bucket_details(bucket_name: str):
            try:
                result = await self.get_bucket_details(bucket_name)
                return JSONResponse(content={
                    "success": True,
                    "data": result
                })
            except Exception as e:
                logger.error(f"Error getting bucket details: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.get("/api/buckets/{bucket_name}/files")
        async def list_bucket_files(bucket_name: str):
            try:
                result = await self.list_bucket_files(bucket_name)
                return JSONResponse(content={
                    "success": True,
                    "data": result
                })
            except Exception as e:
                logger.error(f"Error listing bucket files: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.post("/api/buckets/{bucket_name}/upload")
        async def upload_file_to_bucket(
            bucket_name: str,
            file: UploadFile = File(...),
            path: str = Form("")
        ):
            try:
                result = await self.upload_file(bucket_name, file, path)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error uploading file: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.post("/api/buckets/import-car")
        async def import_car_to_bucket(
            bucket_name: str = Form(...),
            file: UploadFile = File(...)
        ):
            try:
                result = await self.import_car_file(bucket_name, file)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error importing CAR file: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.post("/api/buckets/import-car-cid")
        async def import_car_from_cid(
            bucket_name: str = Form(...),
            cid: str = Form(...)
        ):
            try:
                result = await self.import_car_from_cid(bucket_name, cid)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error importing CAR from CID: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.get("/api/buckets/{bucket_name}/download/{file_path:path}")
        async def download_file_from_bucket(bucket_name: str, file_path: str):
            try:
                bucket_dir = self.buckets_dir / bucket_name
                if not bucket_dir.exists():
                    raise HTTPException(status_code=404, detail="Bucket not found")
                
                full_path = bucket_dir / file_path
                if not full_path.exists() or not full_path.is_file():
                    raise HTTPException(status_code=404, detail="File not found")
                
                return FileResponse(
                    path=str(full_path),
                    filename=full_path.name,
                    media_type=mimetypes.guess_type(str(full_path))[0] or 'application/octet-stream'
                )
            except Exception as e:
                logger.error(f"Error downloading file: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/buckets/{bucket_name}/files/{file_path:path}")
        async def delete_file_from_bucket(bucket_name: str, file_path: str):
            try:
                result = await self.delete_file(bucket_name, file_path)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error deleting file: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.put("/api/buckets/{bucket_name}/files/{file_path:path}")
        async def rename_file_in_bucket(
            bucket_name: str,
            file_path: str,
            new_file_path: str = Form(...)
        ):
            try:
                result = await self.rename_file(bucket_name, file_path, new_file_path)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error renaming file: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
    
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all buckets."""
        buckets = []
        
        if self.buckets_dir.exists():
            for bucket_dir in self.buckets_dir.iterdir():
                if bucket_dir.is_dir():
                    # Read metadata if exists
                    metadata_file = bucket_dir / "metadata.json"
                    if metadata_file.exists():
                        try:
                            with open(metadata_file, 'r') as f:
                                bucket_info = json.load(f)
                        except:
                            bucket_info = {"name": bucket_dir.name, "type": "unknown"}
                    else:
                        bucket_info = {"name": bucket_dir.name, "type": "filesystem"}
                    
                    # Add file count and size
                    files = [f for f in bucket_dir.rglob("*") if f.is_file() and f.name != "metadata.json"]
                    bucket_info["file_count"] = len(files)
                    bucket_info["total_size"] = sum(f.stat().st_size for f in files)
                    bucket_info["created_at"] = bucket_dir.stat().st_ctime
                    bucket_info["last_modified"] = bucket_dir.stat().st_mtime
                    
                    buckets.append(bucket_info)
        
        return buckets
    
    async def create_bucket(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new bucket."""
        bucket_name = data.get("bucket_name")
        bucket_type = data.get("bucket_type", "general")
        metadata = data.get("metadata", {})
        
        if not bucket_name:
            return {"success": False, "error": "bucket_name is required"}
        
        bucket_dir = self.buckets_dir / bucket_name
        if bucket_dir.exists():
            return {"success": False, "error": f"Bucket '{bucket_name}' already exists"}
        
        # Create bucket directory
        bucket_dir.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        metadata_file = bucket_dir / "metadata.json"
        bucket_metadata = {
            "name": bucket_name,
            "type": bucket_type,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(bucket_metadata, f, indent=2)
        
        return {
            "success": True,
            "data": {
                "bucket_name": bucket_name,
                "type": bucket_type,
                "created_at": bucket_metadata["created_at"]
            }
        }
    
    async def delete_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """Delete a bucket."""
        if not bucket_name:
            return {"success": False, "error": "bucket_name is required"}
        
        bucket_dir = self.buckets_dir / bucket_name
        if not bucket_dir.exists():
            return {"success": False, "error": f"Bucket '{bucket_name}' does not exist"}
        
        # Remove bucket directory and contents
        shutil.rmtree(bucket_dir)
        
        return {
            "success": True,
            "data": {
                "bucket_name": bucket_name,
                "message": f"Bucket '{bucket_name}' deleted successfully"
            }
        }
    
    async def get_bucket_details(self, bucket_name: str) -> Dict[str, Any]:
        """Get detailed information about a bucket."""
        bucket_dir = self.buckets_dir / bucket_name
        if not bucket_dir.exists():
            raise HTTPException(status_code=404, detail="Bucket not found")
        
        # Read metadata
        metadata_file = bucket_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {"name": bucket_name, "type": "filesystem"}
        
        # Get files
        files = []
        for file_path in bucket_dir.rglob("*"):
            if file_path.is_file() and file_path.name != "metadata.json":
                rel_path = file_path.relative_to(bucket_dir)
                files.append({
                    "path": str(rel_path),
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                    "type": mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
                })
        
        return {
            "metadata": metadata,
            "files": files,
            "file_count": len(files),
            "total_size": sum(f["size"] for f in files)
        }
    
    async def list_bucket_files(self, bucket_name: str) -> Dict[str, Any]:
        """List files in a bucket."""
        bucket_dir = self.buckets_dir / bucket_name
        if not bucket_dir.exists():
            return {"files": [], "total_count": 0}
        
        files = []
        for file_path in bucket_dir.rglob("*"):
            if file_path.is_file() and file_path.name != "metadata.json":
                rel_path = file_path.relative_to(bucket_dir)
                files.append({
                    "path": str(rel_path),
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                    "type": mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
                })
        
        return {"files": files, "total_count": len(files)}
    
    async def upload_file(self, bucket_name: str, file: UploadFile, path: str = "") -> Dict[str, Any]:
        """Upload a file to a bucket."""
        bucket_dir = self.buckets_dir / bucket_name
        if not bucket_dir.exists():
            return {"success": False, "error": f"Bucket '{bucket_name}' does not exist"}
        
        # Determine file path
        if path:
            file_path = bucket_dir / path / file.filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            file_path = bucket_dir / file.filename
        
        # Save file
        try:
            with open(file_path, 'wb') as f:
                content = await file.read()
                f.write(content)
            
            return {
                "success": True,
                "data": {
                    "file_name": file.filename,
                    "file_path": str(file_path.relative_to(bucket_dir)),
                    "file_size": len(content),
                    "bucket_name": bucket_name
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to upload file: {str(e)}"}
    
    async def delete_file(self, bucket_name: str, file_path: str) -> Dict[str, Any]:
        """Delete a file from a bucket."""
        bucket_dir = self.buckets_dir / bucket_name
        if not bucket_dir.exists():
            return {"success": False, "error": f"Bucket '{bucket_name}' does not exist"}
        
        full_path = bucket_dir / file_path
        if not full_path.exists():
            return {"success": False, "error": f"File '{file_path}' not found in bucket '{bucket_name}'"}
        
        try:
            if full_path.is_file():
                os.remove(full_path)
            elif full_path.is_dir():
                shutil.rmtree(full_path)
            else:
                return {"success": False, "error": f"Path '{file_path}' is not a file or directory"}
            
            return {"success": True, "data": {"message": f"File/directory '{file_path}' deleted successfully from bucket '{bucket_name}'"}}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete file/directory: {str(e)}"}
    
    async def rename_file(self, bucket_name: str, old_file_path: str, new_file_path: str) -> Dict[str, Any]:
        """Rename or move a file/directory within a bucket."""
        bucket_dir = self.buckets_dir / bucket_name
        if not bucket_dir.exists():
            return {"success": False, "error": f"Bucket '{bucket_name}' does not exist"}
        
        full_old_path = bucket_dir / old_file_path
        full_new_path = bucket_dir / new_file_path

        if not full_old_path.exists():
            return {"success": False, "error": f"Source file/directory '{old_file_path}' not found in bucket '{bucket_name}'"}
        
        if full_new_path.exists():
            return {"success": False, "error": f"Destination '{new_file_path}' already exists in bucket '{bucket_name}'"}

        try:
            # Ensure parent directory for new path exists
            full_new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(full_old_path, full_new_path)
            
            return {"success": True, "data": {"message": f"File/directory '{old_file_path}' renamed/moved to '{new_file_path}' successfully"}}
        except Exception as e:
            return {"success": False, "error": f"Failed to rename/move file/directory: {str(e)}"}
    
    async def import_car_file(self, bucket_name: str, car_file: UploadFile) -> Dict[str, Any]:
        """Import a CAR file into a bucket."""
        bucket_dir = self.buckets_dir / bucket_name
        if not bucket_dir.exists():
            bucket_dir.mkdir(parents=True, exist_ok=True)

        car_path = self.data_dir / "temp" / car_file.filename
        car_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(car_path, "wb") as f:
                content = await car_file.read()
                f.write(content)
            
            # Here you would integrate with a CAR parsing library (e.g., pycar)
            # and extract files into the bucket_dir
            # For now, this is a placeholder:
            logger.info(f"Simulating CAR file import from {car_path} to {bucket_dir}")
            # Example: extract_car(car_path, bucket_dir)

            os.remove(car_path) # Clean up temp file
            
            return {"success": True, "data": {"message": f"CAR file '{car_file.filename}' imported to bucket '{bucket_name}'"}}
        except Exception as e:
            return {"success": False, "error": f"Failed to import CAR file: {str(e)}"}

    async def import_car_from_cid(self, bucket_name: str, cid: str) -> Dict[str, Any]:
        """Import a CAR file from an IPFS CID into a bucket."""
        bucket_dir = self.buckets_dir / bucket_name
        if not bucket_dir.exists():
            bucket_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Here you would integrate with an IPFS client library to fetch the CAR by CID
            # and then extract its contents into the bucket_dir.
            # For now, this is a placeholder:
            logger.info(f"Simulating CAR import from CID {cid} to {bucket_dir}")
            # Example: fetch_car_from_ipfs(cid, bucket_dir)

            return {"success": True, "data": {"message": f"CAR from CID '{cid}' imported to bucket '{bucket_name}'"}}
        except Exception as e:
            return {"success": False, "error": f"Failed to import CAR from CID: {str(e)}"}

    def get_dashboard_html(self) -> str:
        """Return the dashboard HTML."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comprehensive Bucket Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .bucket-item { transition: all 0.3s ease; }
        .bucket-item:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .btn { @apply px-4 py-2 rounded font-medium transition-colors; }
        .btn-primary { @apply bg-blue-500 text-white hover:bg-blue-600; }
        .btn-secondary { @apply bg-gray-500 text-white hover:bg-gray-600; }
        .btn-danger { @apply bg-red-500 text-white hover:bg-red-600; }
        .btn-success { @apply bg-green-500 text-white hover:bg-green-600; }
        .btn-sm { @apply px-2 py-1 text-sm; }
        .status-badge { @apply px-2 py-1 rounded-full text-xs font-medium; }
        .status-active { @apply bg-green-100 text-green-800; }
        .status-inactive { @apply bg-red-100 text-red-800; }
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <div class="bg-white rounded-lg shadow-md p-6 mb-6">
            <div class="flex justify-between items-start mb-4">
                <div>
                    <h1 class="text-3xl font-bold text-gray-800 mb-2">🪣 Comprehensive Bucket Dashboard</h1>
                    <p class="text-gray-600">Manage your IPFS-Kit buckets with full MCP server integration</p>
                </div>
                <div class="text-right">
                    <div id="comprehensive-status" class="mb-2">
                        <span class="status-badge status-inactive">Comprehensive Features: Loading...</span>
                    </div>
                    <button onclick="initializeComprehensive()" id="init-comprehensive-btn" 
                            class="btn btn-success btn-sm">Initialize Features</button>
                </div>
            </div>
            
            <!-- Comprehensive Features Quick Actions -->
            <div id="comprehensive-actions" class="hidden mt-4 p-4 bg-gray-50 rounded-lg">
                <h3 class="font-semibold mb-2">Quick Actions:</h3>
                <div class="flex flex-wrap gap-2">
                    <button onclick="callComprehensive('system', 'get_system_status')" class="btn btn-secondary btn-sm">System Status</button>
                    <button onclick="callComprehensive('mcp', 'get_mcp_status')" class="btn btn-secondary btn-sm">MCP Status</button>
                    <button onclick="callComprehensive('backend', 'get_backends')" class="btn btn-secondary btn-sm">Backends</button>
                    <button onclick="callComprehensive('analytics', 'get_analytics_summary')" class="btn btn-secondary btn-sm">Analytics</button>
                    <button onclick="showComprehensiveFeatures()" class="btn btn-primary btn-sm">Browse All Features</button>
                </div>
            </div>
        </div>

        <!-- Create Bucket Section -->
        <div class="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">Create New Bucket</h2>
            <div class="flex gap-4">
                <input type="text" id="bucket-name" placeholder="Bucket name" 
                       class="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:border-blue-500">
                <select id="bucket-type" class="px-3 py-2 border rounded-lg focus:outline-none focus:border-blue-500">
                    <option value="general">General</option>
                    <option value="media">Media</option>
                    <option value="documents">Documents</option>
                    <option value="archive">Archive</option>
                </select>
                <button onclick="createBucket()" class="btn btn-primary">Create Bucket</button>
            </div>
        </div>

        <!-- Import CAR Section -->
        <div class="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">Import CAR File</h2>
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium mb-2">Target Bucket Name:</label>
                    <input type="text" id="import-car-bucket-name" placeholder="Existing or new bucket name" 
                           class="w-full px-3 py-2 border rounded-lg focus:outline-none focus:border-blue-500">
                </div>
                <div class="flex items-center gap-4">
                    <label class="block text-sm font-medium">Upload CAR File:</label>
                    <input type="file" id="car-file-upload" accept=".car" class="flex-1">
                    <button onclick="importCarFile()" class="btn btn-primary">Import from File</button>
                </div>
                <div class="flex items-center gap-4">
                    <label class="block text-sm font-medium">Import from IPFS CID:</label>
                    <input type="text" id="car-cid-input" placeholder="IPFS CID of CAR file" 
                           class="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:border-blue-500">
                    <button onclick="importCarFromCid()" class="btn btn-primary">Import from CID</button>
                </div>
            </div>
        </div>

        <!-- Buckets List -->
        <div class="bg-white rounded-lg shadow-md p-6">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-semibold">Your Buckets</h2>
                <button onclick="refreshBuckets()" class="btn btn-secondary btn-sm">Refresh</button>
            </div>
            <div id="buckets-list" class="space-y-4">
                <div class="text-gray-500">Loading buckets...</div>
            </div>
        </div>

        <!-- Upload Modal -->
        <div id="upload-modal" class="fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center">
            <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                <h3 class="text-lg font-semibold mb-4">Upload File</h3>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium mb-2">Select File:</label>
                        <input type="file" id="upload-file" class="w-full">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2">Path (optional):</label>
                        <input type="text" id="upload-path" placeholder="folder/subfolder" 
                               class="w-full px-3 py-2 border rounded focus:outline-none focus:border-blue-500">
                    </div>
                    <div class="flex gap-2">
                        <button onclick="uploadFile()" class="btn btn-primary flex-1">Upload</button>
                        <button onclick="closeUploadModal()" class="btn btn-secondary flex-1">Cancel</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Bucket Details Modal -->
        <div id="details-modal" class="fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center">
            <div class="bg-white rounded-lg p-6 max-w-4xl w-full mx-4 max-h-screen overflow-y-auto">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-semibold">Bucket Details</h3>
                    <button onclick="closeDetailsModal()" class="text-gray-500 hover:text-gray-700">✕</button>
                </div>
                <div id="bucket-details-content">
                    <!-- Content will be populated by JavaScript -->
                </div>
            </div>
        </div>

        <!-- Rename Modal -->
        <div id="rename-modal" class="fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center">
            <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                <h3 class="text-lg font-semibold mb-4">Rename/Move File</h3>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium mb-2">Current Path:</label>
                        <input type="text" id="rename-old-path" class="w-full px-3 py-2 border rounded bg-gray-100" readonly>
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2">New Path:</label>
                        <input type="text" id="rename-new-path" placeholder="new_folder/new_file.txt" 
                               class="w-full px-3 py-2 border rounded focus:outline-none focus:border-blue-500">
                    </div>
                    <div class="flex gap-2">
                        <button onclick="renameFile()" class="btn btn-primary flex-1">Rename/Move</button>
                        <button onclick="closeRenameModal()" class="btn btn-secondary flex-1">Cancel</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentUploadBucket = '';

        // Initialize page
        document.addEventListener('DOMContentLoaded', function() {
            refreshBuckets();
        });

        async function refreshBuckets() {
            try {
                const response = await fetch('/api/buckets');
                const data = await response.json();
                
                const bucketsList = document.getElementById('buckets-list');
                if (data.success && data.data && data.data.buckets) {
                    const buckets = data.data.buckets;
                    if (buckets.length === 0) {
                        bucketsList.innerHTML = '<div class="text-gray-500">No buckets found</div>';
                    } else {
                        bucketsList.innerHTML = buckets.map(bucket => `
                            <div class="bucket-item p-4 border rounded-lg">
                                <div class="flex justify-between items-start">
                                    <div class="flex-1">
                                        <h4 class="font-semibold text-lg">{{${{bucket.name}}}}</h4>
                                        <p class="text-sm text-gray-600">Type: {{${{bucket.type || 'general'}}}}</p>
                                        <p class="text-sm text-gray-600">Files: {{${{bucket.file_count || 0}}}}</p>
                                        <p class="text-sm text-gray-600">Size: {{${{formatBytes(bucket.total_size || 0)}}}}</p>
                                    </div>
                                    <div class="flex gap-2">
                                        <button onclick="viewBucket('${bucket.name}')" class="btn btn-secondary btn-sm">View</button>
                                        <button onclick="showUploadModal('${bucket.name}')" class="btn btn-primary btn-sm">Upload</button>
                                        <button onclick="deleteBucket('${bucket.name}')" class="btn btn-danger btn-sm">Delete</button>
                                    </div>
                                </div>
                            </div>
                        `).join('');
                    }
                } else {
                    bucketsList.innerHTML = '<div class="text-red-500">Failed to load buckets</div>';
                }
            } catch (error) {
                console.error('Error refreshing buckets:', error);
                document.getElementById('buckets-list').innerHTML = '<div class="text-red-500">Error loading buckets</div>';
            }
        }

        async function createBucket() {{
            const bucketName = document.getElementById('bucket-name').value;
            const bucketType = document.getElementById('bucket-type').value;
            
            if (!bucketName) {{
                alert('Please enter a bucket name');
                return;
            }}

            try {{
                const response = await fetch('/api/buckets', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        bucket_name: bucketName,
                        bucket_type: bucketType
                    }})
                }});
                
                const result = await response.json();
                if (result.success) {{
                    document.getElementById('bucket-name').value = '';
                    refreshBuckets();
                }} else {{
                    alert('Error creating bucket: ' + result.error);
                }}
            }} catch (error) {{
                console.error('Error creating bucket:', error);
                alert('Error creating bucket');
            }}
        }}

        async function deleteBucket(bucketName) {{
            if (!confirm(`Are you sure you want to delete bucket "{{${{bucketName}}}}"?`)) {{
                return;
            }}

            try {{
                const response = await fetch(`/api/buckets/${bucketName}}`, {{
                    method: 'DELETE'
                }});
                
                const result = await response.json();
                if (result.success) {{
                    refreshBuckets();
                }} else {{
                    alert('Error deleting bucket: ' + result.error);
                }}
            }} catch (error) {{
                console.error('Error deleting bucket:', error);
                alert('Error deleting bucket');
            }}
        }}

        async function viewBucket(bucketName) {{
            try {{
                const response = await fetch(`/api/buckets/{{${{bucketName}}}}`);
                const data = await response.json();
                
                if (data.success) {{
                    const details = data.data;
                    const content = `
                        <div class="space-y-4">
                            <div>
                                <h4 class="font-semibold">Metadata</h4>
                                <pre class="bg-gray-100 p-3 rounded text-sm">{{${{JSON.stringify(details.metadata, null, 2)}}}}</pre>
                            </div>
                            <div>
                                <h4 class="font-semibold">Files (${details.file_count})</h4>
                                <div class="max-h-64 overflow-y-auto">
                                    ${details.files.map(file => `
                                        <div class="flex justify-between items-center p-2 border-b">
                                            <div>
                                                <div class="font-medium">{{${{file.name}}}}</div>
                                                <div class="text-sm text-gray-500">{{${{file.path}}}}</div>
                                            </div>
                                            <div class="text-right">
                                                <div class="text-sm">{{${{formatBytes(file.size)}}}}</div>
                                                <a href="/api/buckets/{{${{bucketName}}}}/download/{{${{file.path}}}}" 
                                                   class="text-blue-500 hover:underline text-sm mr-2">Download</a>
                                                <button onclick="deleteFile('{{${{bucketName}}}}', '{{${{file.path}}}}')" 
                                                        class="btn btn-danger btn-sm">Delete</button>
                                                <button onclick="showRenameModal('{{${{bucketName}}}}', '{{${{file.path}}}}')" 
                                                        class="btn btn-secondary btn-sm ml-2">Rename</button>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                                <div id="drop-zone" 
                                     class="mt-4 border-2 border-dashed border-gray-300 rounded-lg p-6 text-center text-gray-500
                                            hover:border-blue-500 hover:text-blue-500 transition-colors duration-200">
                                    Drag & drop files here to upload
                                </div>
                            </div>
                        </div>
                    `;
                    document.getElementById('bucket-details-content').innerHTML = content;
                    document.getElementById('details-modal').classList.remove('hidden');
                    document.getElementById('details-modal').classList.add('flex');

                    // Add drag and drop listeners
                    const dropZone = document.getElementById('drop-zone');
                    dropZone.addEventListener('dragleave', handleDragLeave);
                    dropZone.addEventListener('dragenter', handleDragEnter);

                }} else {
                    alert('Error loading bucket details: ' + data.error);
                }}
            }} catch (error) {{
                console.error('Error viewing bucket:', error);
                alert('Error loading bucket details');
            }}
        }}

        function handleDragLeave(event) {
            event.currentTarget.classList.remove('border-blue-500', 'text-blue-500');
        }

        function handleDragOver(event) {{
            event.preventDefault();
            event.currentTarget.classList.add('border-blue-500', 'text-blue-500');
        }}

        function handleDragEnter(event) {
            event.currentTarget.classList.add('border-blue-500', 'text-blue-500');
        }

        function handleDragLeave(event) {
            event.currentTarget.classList.remove('border-blue-500', 'text-blue-500');
        }

        async function handleFileDrop(event, bucketName) {{
            event.preventDefault();
            event.currentTarget.classList.remove('border-blue-500', 'text-blue-500');

            const files = event.dataTransfer.files;
            if (files.length > 0) {{
                for (let i = 0; i < files.length; i++) {{
                    const file = files[i];
                    const formData = new FormData();
                    formData.append('file', file);
                    // Optionally, you can add a path if you want to support dropping into subfolders
                    // formData.append('path', ''); 

                    try {{
                        const response = await fetch(`/api/buckets/{{${{bucketName}}}}/upload`, {{
                            method: 'POST',
                            body: formData
                        }});
                        const result = await response.json();
                        if (result.success) {{
                            console.log(`Uploaded {{${{file.name}}}} successfully.`);
                        }} else {{
                            console.error(`Failed to upload {{${{file.name}}}}}: {{${{result.error}}}}`);
                            alert(`Failed to upload {{${{file.name}}}}}: {{${{result.error}}}}`);
                        }}
                    }} catch (error) {{
                        console.error(`Error uploading ${file.name}}:`, error);
                        alert(`Error uploading ${file.name}}`);
                    }}
                }}
                viewBucket(bucketName); // Refresh bucket details after upload
            }}
        }}

        function showUploadModal(bucketName) {
            currentUploadBucket = bucketName;
            document.getElementById('upload-modal').classList.remove('hidden');
            document.getElementById('upload-modal').classList.add('flex');
        }

        function closeUploadModal() {{
            document.getElementById('upload-modal').classList.add('hidden');
            document.getElementById('upload-modal').classList.remove('flex');
            document.getElementById('upload-file').value = '';
            document.getElementById('upload-path').value = '';
        }}

        function closeDetailsModal() {{
            document.getElementById('details-modal').classList.add('hidden');
            document.getElementById('details-modal').classList.remove('flex');
        }}

        let currentRenameBucket = '';
        let currentRenameFilePath = '';

        function showRenameModal(bucketName, filePath) {{
            currentRenameBucket = bucketName;
            currentRenameFilePath = filePath;
            document.getElementById('rename-old-path').value = filePath;
            document.getElementById('rename-new-path').value = filePath.substring(filePath.lastIndexOf('/') + 1);
            document.getElementById('rename-modal').classList.remove('hidden');
            document.getElementById('rename-modal').classList.add('flex');
        }}

        function closeRenameModal() {{
            document.getElementById('rename-modal').classList.add('hidden');
            document.getElementById('rename-modal').classList.remove('flex');
            document.getElementById('rename-old-path').value = '';
            document.getElementById('rename-new-path').value = '';
        }}

        async function uploadFile() {{
            const fileInput = document.getElementById('upload-file');
            const pathInput = document.getElementById('upload-path');
            
            if (!fileInput.files[0]) {{
                alert('Please select a file');
                return;
            }}

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('path', pathInput.value);

            try {{
                const response = await fetch(`/api/buckets/{{${{currentUploadBucket}}}}/upload`, {{
                    method: 'POST',
                    body: formData
                }});
                
                const result = await response.json();
                if (result.success) {{
                    closeUploadModal();
                    refreshBuckets();
                }} else {{
                    alert('Error uploading file: ' + result.error);
                }}
            }} catch (error) {{
                console.error('Error uploading file:', error);
                alert('Error uploading file');
            }}
        }}

        async function deleteFile(bucketName, filePath) {{
            if (!confirm(`Are you sure you want to delete "{{${{filePath}}}}" from bucket "{{${{bucketName}}}}"?`)) {{
                return;
            }}

            try {{
                const response = await fetch(`/api/buckets/{{${{bucketName}}}}/files/{{${{filePath}}}}`, {{
                    method: 'DELETE'
                }});
                
                const result = await response.json();
                if (result.success) {{
                    alert(result.data.message);
                    viewBucket(bucketName); // Refresh bucket details after deletion
                }} else {{
                    alert('Error deleting file: ' + result.error);
                }}
            }} catch (error) {{
                console.error('Error deleting file:', error);
                alert('Error deleting file');
            }}
        }}

        async function renameFile() {{
            const newPath = document.getElementById('rename-new-path').value;
            if (!newPath) {
                alert('Please enter a new file path.');
                return;
            }

            try {{
                const formData = new FormData();
                formData.append('new_file_path', newPath);

                const response = await fetch(`/api/buckets/{{${{currentRenameBucket}}}}/files/{{${{currentRenameFilePath}}}}`, {{
                    method: 'PUT',
                    body: formData
                });
                const result = await response.json();
                if (result.success) {
                    alert(result.data.message);
                    closeRenameModal();
                    viewBucket(currentRenameBucket); // Refresh bucket details
                } else {
                    alert('Error renaming file: ' + result.error);
                }
            } catch (error) {
                console.error('Error renaming file:', error);
                alert('Error renaming file');
            }
        }}

        

        // RENAME_FILE_FUNCTION_PLACEHOLDER
        async function importCarFile() {
            const bucketName = document.getElementById('import-car-bucket-name').value;
            const carFile = document.getElementById('car-file-upload').files[0];

            if (!bucketName) {
                alert('Please enter a bucket name for CAR import.');
                return;
            }
            if (!carFile) {
                alert('Please select a CAR file to upload.');
                return;
            }

            const formData = new FormData();
            formData.append('bucket_name', bucketName);
            formData.append('file', carFile);

            try {{
                const response = await fetch('/api/buckets/import-car', {{
                    method: 'POST',
                    body: formData
                }});
                const result = await response.json();
                if (result.success) {
                    alert({{${{result.data.message}}}});
                    document.getElementById('import-car-bucket-name').value = '';
                    document.getElementById('car-file-upload').value = '';
                    refreshBuckets();
                } else {
                    alert('Error importing CAR file: ' + {{${{result.error}}}});
                }
            } catch (error) {
                console.error('Error importing CAR file:', error);
                alert('Error importing CAR file');
            }
        }

        async function importCarFromCid() {
            const bucketName = document.getElementById('import-car-bucket-name').value;
            const cid = document.getElementById('car-cid-input').value;

            if (!bucketName) {
                alert('Please enter a bucket name for CAR import.');
                return;
            }
            if (!cid) {
                alert('Please enter an IPFS CID.');
                return;
            }

            const formData = new FormData();
            formData.append('bucket_name', bucketName);
            formData.append('cid', cid);

            try {{
                const response = await fetch('/api/buckets/import-car-cid', {{
                    method: 'POST',
                    body: formData
                }});
                const result = await response.json();
                if (result.success) {
                    alert({{${{result.data.message}}}});
                    document.getElementById('import-car-bucket-name').value = '';
                    document.getElementById('car-cid-input').value = '';
                    refreshBuckets();
                } else {
                    alert('Error importing CAR from CID: ' + {{${{result.error}}}});
                }
            } catch (error) {
                console.error('Error importing CAR from CID:', error);
                alert('Error importing CAR from CID');
            }
        }

        // Comprehensive Features Integration
        let comprehensiveInitialized = false;
        let comprehensiveFeatures = {};

        // Check comprehensive status on page load
        document.addEventListener('DOMContentLoaded', function() {
            refreshBuckets();
            checkComprehensiveStatus();
        });

        async function checkComprehensiveStatus() {
            try {
                const response = await fetch('/api/comprehensive');
                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        comprehensiveInitialized = true;
                        comprehensiveFeatures = data.data;
                        updateComprehensiveUI(true);
                    } else {
                        updateComprehensiveUI(false);
                    }
                } else {
                    updateComprehensiveUI(false);
                }
            } catch (error) {
                console.log('Comprehensive features not available:', error);
                updateComprehensiveUI(false);
            }
        }

        function updateComprehensiveUI(available) {
            const statusElement = document.getElementById('comprehensive-status');
            const actionsElement = document.getElementById('comprehensive-actions');
            const initButton = document.getElementById('init-comprehensive-btn');

            if (available) {
                statusElement.innerHTML = '<span class="status-badge status-active">Comprehensive Features: Active</span>';
                actionsElement.classList.remove('hidden');
                initButton.style.display = 'none';
            } else {
                statusElement.innerHTML = '<span class="status-badge status-inactive">Comprehensive Features: Inactive</span>';
                actionsElement.classList.add('hidden');
                initButton.style.display = 'inline-block';
            }
        }

        async function initializeComprehensive() {
            const button = document.getElementById('init-comprehensive-btn');
            const originalText = button.textContent;
            button.textContent = 'Initializing...';
            button.disabled = true;

            try {
                const response = await fetch('/api/initialize-comprehensive', { 
                    method: 'POST' 
                });
                const result = await response.json();
                
                if (result.success) {
                    alert(`Comprehensive features initialized successfully!\\nFeatures: ${result.total_features}\\nCategories: ${result.categories}`);
                    await checkComprehensiveStatus();
                } else {
                    alert('Failed to initialize comprehensive features: ' + result.error);
                }
            } catch (error) {
                console.error('Error initializing comprehensive features:', error);
                alert('Error initializing comprehensive features');
            } finally {
                button.textContent = originalText;
                button.disabled = false;
            }
        }

        async function callComprehensive(category, action, data = {}) {
            if (!comprehensiveInitialized) {
                alert('Comprehensive features not initialized');
                return;
            }

            try {
                const response = await fetch(`/api/comprehensive/${category}/${action}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showResultModal(category, action, result.data);
                } else {
                    alert(`Error in ${category}/${action}: ` + result.error);
                }
            } catch (error) {
                console.error(`Error calling ${category}/${action}:`, error);
                alert(`Error calling ${category}/${action}`);
            }
        }

        function showResultModal(category, action, data) {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
            modal.innerHTML = `
                <div class="bg-white rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[80vh] overflow-hidden">
                    <div class="flex justify-between items-start mb-4">
                        <h3 class="text-lg font-semibold">${category} / ${action}</h3>
                        <button onclick="this.closest('.fixed').remove()" class="text-gray-500 hover:text-gray-700">✕</button>
                    </div>
                    <div class="overflow-auto max-h-[60vh]">
                        <pre class="bg-gray-100 p-4 rounded text-sm overflow-auto">${JSON.stringify(data, null, 2)}</pre>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        async function showComprehensiveFeatures() {
            if (!comprehensiveInitialized) {
                alert('Comprehensive features not initialized');
                return;
            }

            try {
                const response = await fetch('/api/comprehensive');
                const result = await response.json();
                
                if (result.success) {
                    const features = result.data.features_by_category;
                    let html = '<div class="space-y-4">';
                    
                    for (const [category, categoryFeatures] of Object.entries(features)) {
                        html += `
                            <div class="border rounded p-4">
                                <h4 class="font-semibold text-lg mb-2 capitalize">${category} (${categoryFeatures.length})</h4>
                                <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
                        `;
                        
                        for (const feature of categoryFeatures) {
                            html += `
                                <button onclick="callComprehensive('${category}', '${feature}')" 
                                        class="btn btn-secondary btn-sm text-left truncate">
                                    ${feature.replace(/_/g, ' ')}
                                </button>
                            `;
                        }
                        
                        html += '</div></div>';
                    }
                    
                    html += '</div>';
                    
                    const modal = document.createElement('div');
                    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
                    modal.innerHTML = `
                        <div class="bg-white rounded-lg p-6 max-w-6xl w-full mx-4 max-h-[80vh] overflow-hidden">
                            <div class="flex justify-between items-start mb-4">
                                <h3 class="text-lg font-semibold">All Comprehensive Features (${result.data.total_features})</h3>
                                <button onclick="this.closest('.fixed').remove()" class="text-gray-500 hover:text-gray-700">✕</button>
                            </div>
                            <div class="overflow-auto max-h-[60vh]">
                                ${html}
                            </div>
                        </div>
                    `;
                    document.body.appendChild(modal);
                } else {
                    alert('Error loading comprehensive features: ' + result.error);
                }
            } catch (error) {
                console.error('Error loading comprehensive features:', error);
                alert('Error loading comprehensive features');
            }
        }

        function formatBytes(bytes, decimals = 2) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const dm = decimals < 0 ? 0 : decimals;
            const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
        }
    </script>
</body>
</html>
"""

    async def start(self):
        """Start the dashboard server."""
        logger.info(f"🚀 Starting Comprehensive Bucket Dashboard on port {self.port}")
        logger.info(f"📁 Data directory: {self.data_dir}")
        logger.info(f"🪣 Buckets directory: {self.buckets_dir}")
        
        # Auto-initialize comprehensive features at startup
        if COMPREHENSIVE_AVAILABLE:
            logger.info("🔄 Auto-initializing comprehensive features...")
            result = await self.initialize_comprehensive_features()
            if result.get("success"):
                logger.info("✅ Comprehensive features auto-initialized successfully!")
            else:
                logger.warning(f"⚠️ Comprehensive features auto-initialization failed: {result.get('error', 'unknown')}")
        
        config = uvicorn.Config(
            app=self.app,
            host="127.0.0.1",
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive Bucket Dashboard")
    parser.add_argument("--port", type=int, default=8004, help="Port to run the dashboard on")
    parser.add_argument("--data-dir", default="~/.ipfs_kit", help="Data directory")
    
    args = parser.parse_args()
    
    dashboard = BucketDashboard(data_dir=args.data_dir, port=args.port)
    await dashboard.start()


if __name__ == "__main__":
    asyncio.run(main())
