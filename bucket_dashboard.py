#!/usr/bin/env python3
"""
Standalone Bucket Dashboard

A simplified dashboard focused specifically on bucket management functionality
without the complex MCP server dependencies.
"""

import asyncio
import json
import logging
import os
import shutil
import mimetypes
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

class BucketDashboard:
    def __init__(self, data_dir: str = "~/.ipfs_kit", port: int = 8004):
        self.data_dir = Path(data_dir).expanduser()
        self.port = port
        self.app = FastAPI(title="Bucket Dashboard")
        
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
    
    def setup_routes(self):
        """Setup all API routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard():
            return self.get_dashboard_html()
        
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
    
    def get_dashboard_html(self) -> str:
        """Return the dashboard HTML."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bucket Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .bucket-item {{ transition: all 0.3s ease; }}
        .bucket-item:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
        .btn {{ @apply px-4 py-2 rounded font-medium transition-colors; }}
        .btn-primary {{ @apply bg-blue-500 text-white hover:bg-blue-600; }}
        .btn-secondary {{ @apply bg-gray-500 text-white hover:bg-gray-600; }}
        .btn-danger {{ @apply bg-red-500 text-white hover:bg-red-600; }}
        .btn-sm {{ @apply px-2 py-1 text-sm; }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <div class="bg-white rounded-lg shadow-md p-6 mb-6">
            <h1 class="text-3xl font-bold text-gray-800 mb-2">🪣 Bucket Dashboard</h1>
            <p class="text-gray-600">Manage your IPFS-Kit buckets</p>
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
    </div>

    <script>
        let currentUploadBucket = '';

        // Initialize page
        document.addEventListener('DOMContentLoaded', function() {{
            refreshBuckets();
        }});

        async function refreshBuckets() {{
            try {{
                const response = await fetch('/api/buckets');
                const data = await response.json();
                
                const bucketsList = document.getElementById('buckets-list');
                if (data.success && data.data && data.data.buckets) {{
                    const buckets = data.data.buckets;
                    if (buckets.length === 0) {{
                        bucketsList.innerHTML = '<div class="text-gray-500">No buckets found</div>';
                    }} else {{
                        bucketsList.innerHTML = buckets.map(bucket => `
                            <div class="bucket-item p-4 border rounded-lg">
                                <div class="flex justify-between items-start">
                                    <div class="flex-1">
                                        <h4 class="font-semibold text-lg">${{bucket.name}}</h4>
                                        <p class="text-sm text-gray-600">Type: ${{bucket.type || 'general'}}</p>
                                        <p class="text-sm text-gray-600">Files: ${{bucket.file_count || 0}}</p>
                                        <p class="text-sm text-gray-600">Size: ${{formatBytes(bucket.total_size || 0)}}</p>
                                    </div>
                                    <div class="flex gap-2">
                                        <button onclick="viewBucket('${{bucket.name}}')" class="btn btn-secondary btn-sm">View</button>
                                        <button onclick="showUploadModal('${{bucket.name}}')" class="btn btn-primary btn-sm">Upload</button>
                                        <button onclick="deleteBucket('${{bucket.name}}')" class="btn btn-danger btn-sm">Delete</button>
                                    </div>
                                </div>
                            </div>
                        `).join('');
                    }}
                }} else {{
                    bucketsList.innerHTML = '<div class="text-red-500">Failed to load buckets</div>';
                }}
            }} catch (error) {{
                console.error('Error refreshing buckets:', error);
                document.getElementById('buckets-list').innerHTML = '<div class="text-red-500">Error loading buckets</div>';
            }}
        }}

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
            if (!confirm(`Are you sure you want to delete bucket "${{bucketName}}"?`)) {{
                return;
            }}

            try {{
                const response = await fetch(`/api/buckets/${{bucketName}}`, {{
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
                const response = await fetch(`/api/buckets/${{bucketName}}`);
                const data = await response.json();
                
                if (data.success) {{
                    const details = data.data;
                    const content = `
                        <div class="space-y-4">
                            <div>
                                <h4 class="font-semibold">Metadata</h4>
                                <pre class="bg-gray-100 p-3 rounded text-sm">${{JSON.stringify(details.metadata, null, 2)}}</pre>
                            </div>
                            <div>
                                <h4 class="font-semibold">Files (${{details.file_count}})</h4>
                                <div class="max-h-64 overflow-y-auto">
                                    ${{details.files.map(file => `
                                        <div class="flex justify-between items-center p-2 border-b">
                                            <div>
                                                <div class="font-medium">${{file.name}}</div>
                                                <div class="text-sm text-gray-500">${{file.path}}</div>
                                            </div>
                                            <div class="text-right">
                                                <div class="text-sm">${{formatBytes(file.size)}}</div>
                                                <a href="/api/buckets/${{bucketName}}/download/${{file.path}}" 
                                                   class="text-blue-500 hover:underline text-sm">Download</a>
                                            </div>
                                        </div>
                                    `).join('')}}
                                </div>
                            </div>
                        </div>
                    `;
                    document.getElementById('bucket-details-content').innerHTML = content;
                    document.getElementById('details-modal').classList.remove('hidden');
                    document.getElementById('details-modal').classList.add('flex');
                }} else {{
                    alert('Error loading bucket details: ' + data.error);
                }}
            }} catch (error) {{
                console.error('Error viewing bucket:', error);
                alert('Error loading bucket details');
            }}
        }}

        function showUploadModal(bucketName) {{
            currentUploadBucket = bucketName;
            document.getElementById('upload-modal').classList.remove('hidden');
            document.getElementById('upload-modal').classList.add('flex');
        }}

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
                const response = await fetch(`/api/buckets/${{currentUploadBucket}}/upload`, {{
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

        function formatBytes(bytes, decimals = 2) {{
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const dm = decimals < 0 ? 0 : decimals;
            const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
        }}
    </script>
</body>
</html>
"""

    async def start(self):
        """Start the dashboard server."""
        logger.info(f"🚀 Starting Bucket Dashboard on port {self.port}")
        logger.info(f"📁 Data directory: {self.data_dir}")
        logger.info(f"🪣 Buckets directory: {self.buckets_dir}")
        
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
    
    parser = argparse.ArgumentParser(description="Bucket Dashboard")
    parser.add_argument("--port", type=int, default=8004, help="Port to run the dashboard on")
    parser.add_argument("--data-dir", default="~/.ipfs_kit", help="Data directory")
    
    args = parser.parse_args()
    
    dashboard = BucketDashboard(data_dir=args.data_dir, port=args.port)
    await dashboard.start()


if __name__ == "__main__":
    asyncio.run(main())
