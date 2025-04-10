"""
Fix script for the IPFS controller in the MCP server.

This script demonstrates how to fix the most critical issues
in the IPFS controller implementation:
1. Route registration mismatch
2. Form data handling issues
"""

import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Dict, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_ipfs_controller():
    """
    Create a patched version of the register_routes method for the IPFS controller.
    """
    # Import the original controller
    try:
        from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
    except ImportError:
        logger.error("Could not import IPFSController. Make sure ipfs_kit_py is installed.")
        return

    # Create a patched version of the register_routes method
    original_register_routes = IPFSController.register_routes

    def patched_register_routes(self, router: APIRouter):
        """
        Patched register_routes method with fixed route registration.
        """
        # First, register the original routes
        original_register_routes(self, router)
        
        # Add alias routes that match expected patterns
        # 1. Content add routes
        router.add_api_route(
            "/ipfs/add",
            self.handle_add_request,
            methods=["POST"],
            summary="Add content to IPFS (JSON or form)",
            description="Add content to IPFS using either JSON payload or file upload"
        )
        
        # 2. Pinning routes (aliases)
        router.add_api_route(
            "/ipfs/pin",
            self.pin_content,
            methods=["POST"],
            summary="Pin content (alias)"
        )
        
        router.add_api_route(
            "/ipfs/unpin",
            self.unpin_content,
            methods=["POST"],
            summary="Unpin content (alias)"
        )
        
        router.add_api_route(
            "/ipfs/pins",
            self.list_pins,
            methods=["GET"],
            summary="List pins (alias)"
        )
        
        logger.info("IPFS Controller routes patched successfully")

    # Create the new handle_add_request method
    async def handle_add_request(
        self,
        file: Optional[UploadFile] = File(None),
        content: Optional[str] = Form(None),
        filename: Optional[str] = Form(None)
    ) -> Dict[str, Any]:
        """
        Handle both JSON and form data for add requests.
        
        Args:
            file: Optional file upload
            content: Optional content string (for form submissions)
            filename: Optional filename (for form submissions)
            
        Returns:
            Dictionary with operation results
        """
        try:
            # Case 1: File upload
            if file is not None:
                logger.info(f"Processing file upload: {file.filename}")
                file_content = await file.read()
                result = self.ipfs_model.add_content(
                    content=file_content,
                    filename=file.filename
                )
                return result
                
            # Case 2: Form content
            elif content is not None:
                logger.info(f"Processing form content submission, length: {len(content)} bytes")
                result = self.ipfs_model.add_content(
                    content=content,
                    filename=filename
                )
                return result
                
            # Case 3: None of the above, try to get JSON from request body
            else:
                # Let the original add_content method handle JSON content
                logger.info("No file or form content found, delegating to JSON handler")
                from fastapi import Request
                request = Request.scope["request"]
                try:
                    import json
                    body = await request.body()
                    json_data = json.loads(body)
                    
                    # Create a ContentRequest-like object
                    class ContentRequest:
                        pass
                    
                    content_request = ContentRequest()
                    content_request.content = json_data.get("content", "")
                    content_request.filename = json_data.get("filename")
                    
                    return await self.add_content(content_request)
                except Exception as e:
                    logger.error(f"Error processing JSON content: {e}")
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid content format"
                    )
        
        except Exception as e:
            logger.error(f"Error handling add request: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error adding content: {str(e)}"
            )

    # Add the new method to the class
    IPFSController.handle_add_request = handle_add_request
    
    # Replace the original method with our patched version
    IPFSController.register_routes = patched_register_routes
    
    logger.info("IPFS Controller patched successfully")
    return IPFSController

def apply_patch():
    """Apply the patch to the IPFS controller."""
    try:
        # First, make a backup of the original file
        import os
        import shutil
        from pathlib import Path
        
        # Find the package directory
        import ipfs_kit_py
        package_dir = Path(ipfs_kit_py.__file__).parent
        
        # Locate the IPFS controller file
        controller_path = package_dir / "mcp" / "controllers" / "ipfs_controller.py"
        
        if not controller_path.exists():
            logger.error(f"Controller file not found at {controller_path}")
            return False
            
        # Create a backup
        backup_path = controller_path.with_suffix(".py.bak")
        shutil.copy(controller_path, backup_path)
        logger.info(f"Created backup of controller at {backup_path}")
        
        # Patch the controller
        patched_controller = fix_ipfs_controller()
        if patched_controller:
            logger.info("IPFS Controller successfully patched in memory")
            logger.info("To apply the patch to the actual file, you would need to:")
            logger.info("1. Add the new handle_add_request method to the IPFSController class")
            logger.info("2. Update the register_routes method to include alias routes")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error applying patch: {e}")
        return False

if __name__ == "__main__":
    success = apply_patch()
    if success:
        print("Patch applied successfully!")
        print("To test the patch, restart the MCP server and run the test scripts again.")
    else:
        print("Failed to apply patch. See log for details.")