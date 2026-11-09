"""
Example of how to use the MCP error handling system.

This module demonstrates the proper usage of the standardized error handling
system in an MCP controller implementation.
"""

import logging
import json
from typing import Dict, Any, Optional, List

# Import the error handling module
from ipfs_kit_py.mcp.mcp_error_handling import (
    MCPError,
    ValidationError,
    MissingParameterError,
    InvalidParameterError,
    ResourceNotFoundError,
    StorageBackendUnavailableError,
    ContentNotFoundError,
    handle_exception,
    ErrorCategory,
    ErrorSeverity
)

# Configure logging
logger = logging.getLogger("mcp.example")

class ExampleController:
    """Example controller showcasing standardized error handling."""
    
    def __init__(self, storage_backend=None):
        """Initialize the controller."""
        self.storage_backend = storage_backend
    
    def get_content(self, content_id: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get content from storage.
        
        This method demonstrates proper error handling for content retrieval operations.
        
        Args:
            content_id: The ID of the content to retrieve
            options: Optional parameters for the operation
            
        Returns:
            Content data and metadata
            
        Raises:
            MissingParameterError: If content_id is not provided
            InvalidParameterError: If content_id is invalid
            StorageBackendUnavailableError: If the storage backend is unavailable
            ContentNotFoundError: If the content is not found
            MCPError: For other MCP-specific errors
            Exception: For unexpected errors
        """
        try:
            # Input validation
            if not content_id:
                raise MissingParameterError("content_id")
            
            # Validate content ID format
            if not self._is_valid_content_id(content_id):
                raise InvalidParameterError(
                    parameter="content_id",
                    reason="Invalid format (must be valid CID)",
                    suggestion="Please provide a valid content identifier"
                )
            
            # Check if backend is available
            if not self._is_backend_available():
                raise StorageBackendUnavailableError(
                    backend=self._get_backend_name(),
                    suggestion="Please try again later or use a different backend"
                )
            
            # Attempt to retrieve content
            content = self._retrieve_content(content_id, options)
            
            # If content not found
            if not content:
                raise ContentNotFoundError(
                    content_id=content_id,
                    backend=self._get_backend_name(),
                    suggestion="Check if the content exists or try a different backend"
                )
            
            # Return the content
            return {
                "success": True,
                "content_id": content_id,
                "content": content,
                "backend": self._get_backend_name()
            }
            
        except MCPError as e:
            # MCPError exceptions are already properly formatted
            # Just log and re-raise
            logger.error(f"Error retrieving content: {e.message}", exc_info=True)
            raise
            
        except Exception as e:
            # For unexpected errors, wrap in MCPError
            logger.error(f"Unexpected error retrieving content: {str(e)}", exc_info=True)
            raise MCPError(
                message=f"Unexpected error retrieving content: {str(e)}",
                error_code="MCP_CONTENT_RETRIEVAL_ERROR",
                status_code=500,
                category=ErrorCategory.STORAGE,
                severity=ErrorSeverity.ERROR,
                suggestion="Please report this error to the system administrator",
                details={"content_id": content_id},
                original_exception=e
            )
    
    def store_content(self, data: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store content in the backend.
        
        Args:
            data: The content data to store
            metadata: Optional metadata for the content
            
        Returns:
            Storage result with content ID
        """
        try:
            # Input validation
            if data is None:
                raise MissingParameterError("data")
            
            # Check if backend is available
            if not self._is_backend_available():
                raise StorageBackendUnavailableError(
                    backend=self._get_backend_name(),
                    suggestion="Please try again later or use a different backend"
                )
            
            # Store the content
            content_id = self._store_content(data, metadata)
            
            # Return the result
            return {
                "success": True,
                "content_id": content_id,
                "backend": self._get_backend_name()
            }
            
        except MCPError as e:
            logger.error(f"Error storing content: {e.message}", exc_info=True)
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error storing content: {str(e)}", exc_info=True)
            raise MCPError(
                message=f"Unexpected error storing content: {str(e)}",
                error_code="MCP_CONTENT_STORAGE_ERROR",
                status_code=500,
                category=ErrorCategory.STORAGE,
                severity=ErrorSeverity.ERROR,
                original_exception=e
            )
    
    def list_contents(self, 
                     limit: int = 100, 
                     offset: int = 0, 
                     filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List contents from the storage backend.
        
        Args:
            limit: Maximum number of items to return
            offset: Offset for pagination
            filters: Optional filters to apply
            
        Returns:
            List of content IDs and metadata
        """
        try:
            # Input validation
            if limit < 1:
                raise InvalidParameterError(
                    parameter="limit",
                    reason="Must be greater than 0",
                    suggestion="Use a positive integer value"
                )
            
            if offset < 0:
                raise InvalidParameterError(
                    parameter="offset",
                    reason="Cannot be negative",
                    suggestion="Use a non-negative integer value"
                )
            
            # Check if backend is available
            if not self._is_backend_available():
                raise StorageBackendUnavailableError(
                    backend=self._get_backend_name(),
                    suggestion="Please try again later or use a different backend"
                )
            
            # Get the contents
            contents = self._list_contents(limit, offset, filters)
            
            # Return the result
            return {
                "success": True,
                "count": len(contents),
                "total": self._get_total_count(filters),
                "limit": limit,
                "offset": offset,
                "contents": contents,
                "backend": self._get_backend_name()
            }
            
        except MCPError as e:
            logger.error(f"Error listing contents: {e.message}", exc_info=True)
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error listing contents: {str(e)}", exc_info=True)
            raise MCPError(
                message=f"Unexpected error listing contents: {str(e)}",
                error_code="MCP_CONTENT_LISTING_ERROR",
                status_code=500,
                category=ErrorCategory.STORAGE,
                severity=ErrorSeverity.ERROR,
                original_exception=e
            )
    
    # Mock implementation methods
    def _is_valid_content_id(self, content_id: str) -> bool:
        """Validate a content ID."""
        # Mock implementation
        return len(content_id) > 3 and content_id.startswith("Qm")
    
    def _is_backend_available(self) -> bool:
        """Check if the storage backend is available."""
        # Mock implementation
        return self.storage_backend is not None
    
    def _get_backend_name(self) -> str:
        """Get the name of the current storage backend."""
        # Mock implementation
        return getattr(self.storage_backend, "name", "unknown")
    
    def _retrieve_content(self, content_id: str, options: Optional[Dict[str, Any]]) -> Any:
        """Retrieve content from the storage backend."""
        # Mock implementation
        if self.storage_backend and hasattr(self.storage_backend, "data"):
            return self.storage_backend.data.get(content_id)
        return None
    
    def _store_content(self, data: Any, metadata: Optional[Dict[str, Any]]) -> str:
        """Store content in the storage backend."""
        # Mock implementation
        import hashlib
        import random
        import string
        import json
        
        # Generate a mock content ID
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        if isinstance(data, str):
            content_hash = hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]
        else:
            content_hash = hashlib.sha256(str(data).encode('utf-8')).hexdigest()[:16]
        
        content_id = f"Qm{content_hash}{random_suffix}"
        
        # Store in the backend (mock)
        if self.storage_backend and not hasattr(self.storage_backend, "data"):
            self.storage_backend.data = {}
        
        if self.storage_backend:
            self.storage_backend.data[content_id] = {
                "data": data,
                "metadata": metadata
            }
        
        return content_id
    
    def _list_contents(self, 
                      limit: int, 
                      offset: int, 
                      filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """List contents from the storage backend."""
        # Mock implementation
        if not self.storage_backend or not hasattr(self.storage_backend, "data"):
            return []
        
        # Get all content IDs
        all_ids = list(self.storage_backend.data.keys())
        
        # Apply filters (mock implementation)
        if filters:
            # In a real implementation, this would filter based on metadata
            filtered_ids = all_ids
        else:
            filtered_ids = all_ids
        
        # Apply pagination
        paginated_ids = filtered_ids[offset:offset+limit]
        
        # Prepare result
        results = []
        for content_id in paginated_ids:
            item = self.storage_backend.data[content_id]
            results.append({
                "content_id": content_id,
                "metadata": item.get("metadata", {})
            })
        
        return results
    
    def _get_total_count(self, filters: Optional[Dict[str, Any]]) -> int:
        """Get the total count of contents matching the filters."""
        # Mock implementation
        if not self.storage_backend or not hasattr(self.storage_backend, "data"):
            return 0
            
        # In a real implementation, this would count filtered items
        return len(self.storage_backend.data)


# Example usage in a FastAPI or Flask route handler
def api_example():
    """Example of how to use the error handling in an API endpoint."""
    # Create a mock backend
    class MockBackend:
        name = "mock_storage"
        data = {
            "QmTest123": {
                "data": "Test content",
                "metadata": {"name": "Test"}
            }
        }
    
    # Initialize the controller
    controller = ExampleController(storage_backend=MockBackend())
    
    # Example 1: Successful content retrieval
    try:
        result = controller.get_content("QmTest123")
        print("Success:", json.dumps(result, indent=2))
    except MCPError as e:
        error_response, status_code = e.to_response()
        print(f"Error ({status_code}):", json.dumps(error_response, indent=2))
    
    # Example 2: Content not found
    try:
        result = controller.get_content("QmNonExistent")
        print("Success:", json.dumps(result, indent=2))
    except MCPError as e:
        error_response, status_code = e.to_response()
        print(f"Error ({status_code}):", json.dumps(error_response, indent=2))
    
    # Example 3: Invalid content ID
    try:
        result = controller.get_content("invalid")
        print("Success:", json.dumps(result, indent=2))
    except MCPError as e:
        error_response, status_code = e.to_response()
        print(f"Error ({status_code}):", json.dumps(error_response, indent=2))
    
    # Example 4: Backend unavailable
    unavailable_controller = ExampleController(storage_backend=None)
    try:
        result = unavailable_controller.get_content("QmTest123")
        print("Success:", json.dumps(result, indent=2))
    except MCPError as e:
        error_response, status_code = e.to_response()
        print(f"Error ({status_code}):", json.dumps(error_response, indent=2))


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the API example
    api_example()