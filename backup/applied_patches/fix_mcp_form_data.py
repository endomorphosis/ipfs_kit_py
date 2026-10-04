#!/usr/bin/env python

"""
This script fixes form data handling issues in the MCP server's IPFS controller.
It specifically addresses problems with file upload handling in the handle_add_request
and add_file methods.
"""

import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_ipfs_controller_anyio():
    """Fix the form data handling issues in the MCP IPFS controller (AnyIO version)."""

    file_path = "ipfs_kit_py/mcp/controllers/ipfs_controller_anyio.py"

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False

    with open(file_path, 'r') as f:
        content = f.read()

    # Fix handle_add_request method
    old_handle_add_request = """async def handle_add_request(self, request: Request) -> Dict[str, Any]:
    \"\"\"
    Handle combined add request that supports both JSON and form data.

    This unified endpoint accepts content either as JSON payload or as file upload
    to simplify client integration.

    Args:
        request: The incoming request which may be JSON or form data

    Returns:
        Dictionary with operation results
    \"\"\"
    # Determine request content type
    content_type = request.headers.get("content-type", "")

    # Handle multipart form data (file upload)
    if content_type.startswith("multipart/form-data"):
        # Extract the form data
        form = await request.form()

        # Get uploaded file
        file = form.get("file")
        if not file:
            raise HTTPException(status_code=400, detail="Missing file field in form data")

        # Process the uploaded file
        return await self.add_file(file)

    # Handle application/json
    elif content_type.startswith("application/json"):
        # Parse JSON body
        try:
            data = await request.json()

            # Create ContentRequest instance
            content_request = ContentRequest(
                content=data.get("content", ""),
                filename=data.get("filename")
            )

            # Process the JSON content
            return await self.add_content(content_request)

        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON data")

    # Handle unknown content type
    else:
        # Try to parse as JSON first
        try:
            data = await request.json()

            # Create ContentRequest instance
            content_request = ContentRequest(
                content=data.get("content", ""),
                filename=data.get("filename")
            )

            # Process the JSON content
            return await self.add_content(content_request)

        except:
            # Fall back to form data
            try:
                form = await request.form()
                file = form.get("file")
                if file:
                    # Process the uploaded file
                    return await self.add_file(file)
            except:
                pass

        # If all parsing attempts fail, return error
        raise HTTPException(
            status_code=400,
            detail="Unsupported content type. Use application/json or multipart/form-data"
        )"""

    new_handle_add_request = """async def handle_add_request(
    self,
    request: Request,
    content_request: Optional[ContentRequest] = None,
    file: Optional[UploadFile] = File(None),
    pin: bool = Form(False),
    wrap_with_directory: bool = Form(False)
) -> Dict[str, Any]:
    \"\"\"
    Handle combined add request that supports both JSON and form data.

    This unified endpoint accepts content either as JSON payload or as file upload
    to simplify client integration.

    Args:
        request: The incoming request which may be JSON or form data
        content_request: Optional JSON content request (provided by FastAPI when JSON body is sent)
        file: Optional file upload from form data
        pin: Whether to pin the content (form field)
        wrap_with_directory: Whether to wrap the content in a directory (form field)

    Returns:
        Dictionary with operation results
    \"\"\"
    start_time = time.time()
    operation_id = f"add_{int(start_time * 1000)}"
    logger.debug(f"Handling add request (operation_id={operation_id})")

    try:
        # Check if file is provided directly through dependency injection
        if file:
            logger.debug(f"Processing file upload: {file.filename}")
            content = await file.read()
            result = await anyio.to_thread.run_sync(
                self.ipfs_model.add_content,
                content=content,
                filename=file.filename,
                pin=pin,
                wrap_with_directory=wrap_with_directory
            )
            return result

        # Check if JSON content is provided through dependency injection
        elif content_request:
            logger.debug("Processing JSON content request")
            result = await anyio.to_thread.run_sync(
                self.ipfs_model.add_content,
                content=content_request.content,
                filename=content_request.filename
            )
            return result

        # Content type detection fallback
        content_type = request.headers.get("content-type", "")

        # Handle multipart form data
        if content_type.startswith("multipart/form-data"):
            try:
                form = await request.form()
                uploaded_file = form.get("file")
                if uploaded_file:
                    content = await uploaded_file.read()
                    pin_value = form.get("pin", "false").lower() == "true"
                    wrap_dir_value = form.get("wrap_with_directory", "false").lower() == "true"

                    result = await anyio.to_thread.run_sync(
                        self.ipfs_model.add_content,
                        content=content,
                        filename=uploaded_file.filename,
                        pin=pin_value,
                        wrap_with_directory=wrap_dir_value
                    )
                    return result
                else:
                    raise HTTPException(status_code=400, detail="Missing file field in form data")
            except Exception as e:
                logger.error(f"Error processing form data: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Invalid form data: {str(e)}")

        # Handle JSON content
        elif content_type.startswith("application/json"):
            try:
                body = await request.json()
                content = body.get("content", "")
                filename = body.get("filename")

                result = await anyio.to_thread.run_sync(
                    self.ipfs_model.add_content,
                    content=content,
                    filename=filename
                )
                return result
            except Exception as e:
                logger.error(f"Error processing JSON data: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")

        # Handle unknown content type
        else:
            raise HTTPException(
                status_code=415,
                detail="Unsupported media type. Use application/json or multipart/form-data"
            )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error handling add request: {str(e)}")

        # Return proper error response
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__
        }"""

    # Fix add_file method
    old_add_file = """async def add_file(self, file: UploadFile = File(...)) -> Dict[str, Any]:
    \"\"\"
    Add a file to IPFS.

    Args:
        file: File to upload

    Returns:
        Dictionary with operation results
    \"\"\"
    logger.debug(f"Adding file to IPFS: {file.filename}")

    # Use anyio to read the file
    content = await file.read()

    result = self.ipfs_model.add_content(
        content=content,
        filename=file.filename
    )
    # Ensure the result has the proper Hash and cid fields
    if result.get("success", False) and "Hash" in result and "cid" not in result:
        result["cid"] = result["Hash"]
    return result"""

    new_add_file = """async def add_file(
    self,
    file: UploadFile = File(...),
    pin: bool = Form(False),
    wrap_with_directory: bool = Form(False)
) -> Dict[str, Any]:
    \"\"\"
    Add a file to IPFS.

    Args:
        file: File to upload
        pin: Whether to pin the content
        wrap_with_directory: Whether to wrap the content in a directory

    Returns:
        Dictionary with operation results
    \"\"\"
    logger.debug(f"Adding file to IPFS: {file.filename}")

    try:
        # Use anyio to read the file
        content = await file.read()

        # Use anyio to run model method in thread pool
        result = await anyio.to_thread.run_sync(
            self.ipfs_model.add_content,
            content=content,
            filename=file.filename,
            pin=pin,
            wrap_with_directory=wrap_with_directory
        )

        # Ensure the result has the proper Hash and cid fields
        if result.get("success", False) and "Hash" in result and "cid" not in result:
            result["cid"] = result["Hash"]

        return result
    except Exception as e:
        logger.error(f"Error adding file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error adding file: {str(e)}"
        )"""

    # Replace the methods in the file content
    updated_content = content.replace(old_handle_add_request, new_handle_add_request)
    updated_content = updated_content.replace(old_add_file, new_add_file)

    # Check if any changes were made
    if content == updated_content:
        logger.warning("No changes were made to the file. Make sure the target methods exist with exact patterns.")
        return False

    # Write the updated content back to the file
    with open(file_path, 'w') as f:
        f.write(updated_content)

    logger.info(f"Successfully updated {file_path}")
    return True

if __name__ == "__main__":
    logger.info("Starting to fix form data handling in MCP IPFS controller")
    success = fix_ipfs_controller_anyio()
    if success:
        logger.info("Successfully fixed form data handling issues")
        sys.exit(0)
    else:
        logger.error("Failed to fix form data handling issues")
        sys.exit(1)
