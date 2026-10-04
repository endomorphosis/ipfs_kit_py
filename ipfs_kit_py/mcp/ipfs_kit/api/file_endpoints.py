"""
File management API endpoints for the MCP server.
Provides file upload, download, and directory management capabilities.
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
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
    
    def _normalize_and_validate_path(self, path: str) -> Path:
        """
        Normalize a path and ensure it stays within the storage directory.
        
        Args:
            path: The input path (can be absolute or relative)
            
        Returns:
            Normalized Path object within storage_path
            
        Raises:
            ValueError: If path tries to escape storage directory
        """
        # Normalize path - treat "/" as empty path, strip leading slashes
        if path == "/" or not path:
            normalized_path = ""
        else:
            normalized_path = path.strip("/")
        
        # Build target path
        target_path = self.storage_path / normalized_path if normalized_path else self.storage_path
        
        # Resolve and validate the path stays within storage_path
        try:
            target_path = target_path.resolve()
            storage_path_resolved = self.storage_path.resolve()
            
            if not str(target_path).startswith(str(storage_path_resolved)):
                raise ValueError(f"Access denied: path '{path}' outside allowed directory")
                
            return target_path
        except Exception as e:
            raise ValueError(f"Invalid path '{path}': {e}")
        
    def _setup_routes(self):
        """Setup all file management routes."""
        
        @self.router.get("/")
        async def list_files(path: str = "") -> Dict[str, Any]:
            """List files and directories in the specified path."""
            try:
                target_path = self._normalize_and_validate_path(path)
                
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
                
            except ValueError as e:
                # Path validation error
                logger.warning(f"Path validation error for '{path}': {e}")
                return {"success": False, "error": str(e)}
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
            target_path = self._normalize_and_validate_path(path)
            
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
            
        except ValueError as e:
            # Path validation error
            logger.warning(f"Path validation error for '{path}': {e}")
            return {"success": False, "error": str(e)}
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

    async def rename_file_direct(self, old_path: str, new_name: str) -> Dict[str, Any]:
        """Direct method to rename a file or directory."""
        try:
            old_full_path = self.storage_path / old_path
            if not old_full_path.exists():
                return {"success": False, "error": "File or directory not found"}

            new_full_path = old_full_path.parent / new_name
            old_full_path.rename(new_full_path)

            logger.info(f"Renamed: {old_full_path} to {new_full_path}")
            return {"success": True, "message": "Renamed successfully"}
        except Exception as e:
            logger.error(f"Error renaming file: {e}")
            return {"success": False, "error": str(e)}

    async def move_file_direct(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Direct method to move a file or directory."""
        try:
            source_full_path = self.storage_path / source_path
            if not source_full_path.exists():
                return {"success": False, "error": "Source file or directory not found"}

            target_full_path = self.storage_path / target_path
            target_full_path.parent.mkdir(parents=True, exist_ok=True) # Ensure target directory exists

            shutil.move(str(source_full_path), str(target_full_path))

            logger.info(f"Moved: {source_full_path} to {target_full_path}")
            return {"success": True, "message": "Moved successfully"}
        except Exception as e:
            logger.error(f"Error moving file: {e}")
            return {"success": False, "error": str(e)}
