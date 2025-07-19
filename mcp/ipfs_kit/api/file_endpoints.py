"""
File management API endpoints for the MCP server.
Provides file upload, download, and directory management capabilities.
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import asyncio
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class FileInfo(BaseModel):
    name: str
    type: str  # 'file' or 'directory'
    size: int
    modified: str
    path: str

class CreateFolderRequest(BaseModel):
    name: str
    path: Optional[str] = ""

class FileEndpoints:
    """File management API endpoints."""
    
    def __init__(self, storage_path: str = "/tmp/mcp_files"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.router = APIRouter(prefix="/api/files", tags=["files"])
        self._setup_routes()
        
    def _setup_routes(self):
        """Setup all file management routes."""
        
        @self.router.get("/")
        async def list_files(path: str = "") -> Dict[str, Any]:
            """List files and directories in the specified path."""
            try:
                target_path = self.storage_path / path if path else self.storage_path
                
                if not target_path.exists() or not target_path.is_dir():
                    return {"success": False, "error": "Path does not exist"}
                
                files = []
                for item in target_path.iterdir():
                    try:
                        stat = item.stat()
                        files.append({
                            "name": item.name,
                            "type": "directory" if item.is_dir() else "file",
                            "size": stat.st_size if item.is_file() else 0,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "path": str(item.relative_to(self.storage_path))
                        })
                    except Exception as e:
                        logger.warning(f"Error getting info for {item}: {e}")
                        continue
                
                # Sort directories first, then files
                files.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
                
                return {
                    "success": True,
                    "files": files,
                    "current_path": path,
                    "total_count": len(files)
                }
                
            except Exception as e:
                logger.error(f"Error listing files: {e}")
                return {"success": False, "error": str(e)}
        
        @self.router.post("/upload")
        async def upload_file(
            file: UploadFile = File(...),
            path: str = Form("")
        ) -> Dict[str, Any]:
            """Upload a file to the specified path."""
            try:
                # Validate file
                if not file.filename:
                    return {"success": False, "error": "No file provided"}
                
                # Create target directory
                target_dir = self.storage_path / path if path else self.storage_path
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # Save file
                file_path = target_dir / file.filename
                content = await file.read()
                
                with open(file_path, "wb") as f:
                    f.write(content)
                
                logger.info(f"File uploaded: {file_path}")
                
                return {
                    "success": True,
                    "message": f"File '{file.filename}' uploaded successfully",
                    "file_info": {
                        "name": file.filename,
                        "size": len(content),
                        "path": str(file_path.relative_to(self.storage_path))
                    }
                }
                
            except Exception as e:
                logger.error(f"Error uploading file: {e}")
                return {"success": False, "error": str(e)}
        
        @self.router.post("/create_folder")
        async def create_folder(request: CreateFolderRequest) -> Dict[str, Any]:
            """Create a new folder."""
            try:
                # Create target directory
                target_path = self.storage_path / request.path / request.name if request.path else self.storage_path / request.name
                
                if target_path.exists():
                    return {"success": False, "error": "Folder already exists"}
                
                target_path.mkdir(parents=True, exist_ok=True)
                
                logger.info(f"Folder created: {target_path}")
                
                return {
                    "success": True,
                    "message": f"Folder '{request.name}' created successfully",
                    "folder_info": {
                        "name": request.name,
                        "path": str(target_path.relative_to(self.storage_path))
                    }
                }
                
            except Exception as e:
                logger.error(f"Error creating folder: {e}")
                return {"success": False, "error": str(e)}
        
        @self.router.get("/download/{file_path:path}")
        async def download_file(file_path: str):
            """Download a file."""
            try:
                target_file = self.storage_path / file_path
                
                if not target_file.exists() or not target_file.is_file():
                    raise HTTPException(status_code=404, detail="File not found")
                
                return FileResponse(
                    path=target_file,
                    filename=target_file.name,
                    media_type='application/octet-stream'
                )
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error downloading file: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.delete("/{file_path:path}")
        async def delete_file(file_path: str) -> Dict[str, Any]:
            """Delete a file or directory."""
            try:
                target_path = self.storage_path / file_path
                
                if not target_path.exists():
                    return {"success": False, "error": "File or directory not found"}
                
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()
                
                logger.info(f"Deleted: {target_path}")
                
                return {
                    "success": True,
                    "message": f"{'Directory' if target_path.is_dir() else 'File'} deleted successfully"
                }
                
            except Exception as e:
                logger.error(f"Error deleting file: {e}")
                return {"success": False, "error": str(e)}
        
        @self.router.get("/info/{file_path:path}")
        async def get_file_info(file_path: str) -> Dict[str, Any]:
            """Get detailed information about a file or directory."""
            try:
                target_path = self.storage_path / file_path
                
                if not target_path.exists():
                    return {"success": False, "error": "File or directory not found"}
                
                stat = target_path.stat()
                
                info = {
                    "name": target_path.name,
                    "type": "directory" if target_path.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "path": str(target_path.relative_to(self.storage_path)),
                    "permissions": oct(stat.st_mode)[-3:]
                }
                
                if target_path.is_dir():
                    # Count contents for directories
                    try:
                        contents = list(target_path.iterdir())
                        info["contents_count"] = len(contents)
                        info["subdirectories"] = len([x for x in contents if x.is_dir()])
                        info["files"] = len([x for x in contents if x.is_file()])
                    except Exception:
                        info["contents_count"] = 0
                
                return {"success": True, "info": info}
                
            except Exception as e:
                logger.error(f"Error getting file info: {e}")
                return {"success": False, "error": str(e)}

    def get_router(self) -> APIRouter:
        """Get the configured router."""
        return self.router

    # Direct methods for use outside of router
    async def list_files_direct(self, path: str = "") -> Dict[str, Any]:
        """Direct method to list files."""
        try:
            target_path = self.storage_path / path if path else self.storage_path
            
            if not target_path.exists() or not target_path.is_dir():
                return {"success": False, "error": "Path does not exist"}
            
            files = []
            for item in target_path.iterdir():
                try:
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else 0,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "path": str(item.relative_to(self.storage_path))
                    })
                except Exception as e:
                    logger.warning(f"Error getting info for {item}: {e}")
                    continue
            
            # Sort directories first, then files
            files.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
            
            return {
                "success": True,
                "files": files,
                "current_path": path,
                "total_count": len(files)
            }
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return {"success": False, "error": str(e)}

    async def upload_file_direct(self, file: UploadFile, path: str = "") -> Dict[str, Any]:
        """Direct method to upload a file."""
        try:
            # Validate file
            if not file.filename:
                return {"success": False, "error": "No file provided"}
            
            # Create target directory
            target_dir = self.storage_path / path if path else self.storage_path
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file
            file_path = target_dir / file.filename
            content = await file.read()
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            logger.info(f"File uploaded: {file_path}")
            
            return {
                "success": True,
                "message": f"File '{file.filename}' uploaded successfully",
                "file_info": {
                    "name": file.filename,
                    "size": len(content),
                    "path": str(file_path.relative_to(self.storage_path))
                }
            }
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return {"success": False, "error": str(e)}

    async def create_folder_direct(self, name: str, path: str = "") -> Dict[str, Any]:
        """Direct method to create a folder."""
        try:
            # Create target directory
            target_path = self.storage_path / path / name if path else self.storage_path / name
            
            if target_path.exists():
                return {"success": False, "error": "Folder already exists"}
            
            target_path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Folder created: {target_path}")
            
            return {
                "success": True,
                "message": f"Folder '{name}' created successfully",
                "folder_info": {
                    "name": name,
                    "path": str(target_path.relative_to(self.storage_path))
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            return {"success": False, "error": str(e)}

    async def delete_file_direct(self, file_path: str) -> Dict[str, Any]:
        """Direct method to delete a file or directory."""
        try:
            target_path = self.storage_path / file_path
            
            if not target_path.exists():
                return {"success": False, "error": "File or directory not found"}
            
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                target_path.unlink()
            
            logger.info(f"Deleted: {target_path}")
            
            return {
                "success": True,
                "message": f"{'Directory' if target_path.is_dir() else 'File'} deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return {"success": False, "error": str(e)}

    async def download_file_direct(self, file_path: str) -> Dict[str, Any]:
        """Direct method to download a file."""
        try:
            target_file = self.storage_path / file_path
            
            if not target_file.exists() or not target_file.is_file():
                return {"success": False, "error": "File not found"}
            
            return {
                "success": True,
                "path": str(target_file),
                "filename": target_file.name,
                "media_type": 'application/octet-stream'
            }
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return {"success": False, "error": str(e)}
