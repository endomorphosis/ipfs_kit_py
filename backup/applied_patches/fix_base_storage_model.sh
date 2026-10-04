#!/bin/bash
# Script to fix a specific file: base_storage_model.py

echo "Creating backup..."
cp ipfs_kit_py/mcp/models/storage/base_storage_model.py ipfs_kit_py/mcp/models/storage/base_storage_model.py.bak

echo "Fixing base_storage_model.py..."

# Fix the imports first
sed -i 's/from typing import Dict, Any/from typing import Dict, Any, Optional, Union, Callable, TypeVar, Awaitable, Set/' ipfs_kit_py/mcp/models/storage/base_storage_model.py

# Remove redundant type imports
sed -i '/^Any$/d' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i '/^Dict$/d' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i '/^Optional$/d' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i '/^Union$/d' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i '/^Callable$/d' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i '/^TypeVar$/d' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i '/^Awaitable$/d' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i '/^Set$/d' ipfs_kit_py/mcp/models/storage/base_storage_model.py

# Fix the __init__ method
sed -i 's/    def __init__(/    def __init__(self,/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i 's/        self/        self,/' ipfs_kit_py/mcp/models/storage/base_storage_model.py

# Fix other method parameters
sed -i 's/    def _update_stats(/    def _update_stats(self,/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i 's/    def _handle_exception(/    def _handle_exception(self, e: Exception, result: Dict[str, Any], operation: str):/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i 's/    def _handle_exception_async(/    def _handle_exception_async(self, e: Exception, result: Dict[str, Any], operation: str):/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i 's/    async def _cache_put_async(/    async def _cache_put_async(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None):/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i 's/    async def _with_retry_async(/    async def _with_retry_async(self, operation_func, operation_name: str, retry_config: Optional[Dict[str, Any]] = None, *args, **kwargs):/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i 's/    def _with_retry_sync(/    def _with_retry_sync(self, operation_func, operation_name: str, retry_config: Optional[Dict[str, Any]] = None, *args, **kwargs):/' ipfs_kit_py/mcp/models/storage/base_storage_model.py

# Fix missing parentheses
sed -i 's/"retry"/"retry",/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i 's/"error"/"error",/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
sed -i 's/            f"Operation failed after {config\["max_retries"\]} attempts: {str(last_error)}"/            f"Operation failed after {config\["max_retries"\]} attempts: {str(last_error)}");/' ipfs_kit_py/mcp/models/storage/base_storage_model.py

# Fix missing parenthesis in executor call
sed -i 's/                        None, listener, event_type, event_data/                        None, listener, event_type, event_data)/' ipfs_kit_py/mcp/models/storage/base_storage_model.py

# Run black and ruff with minimal output 
echo "Running Black..."
black ipfs_kit_py/mcp/models/storage/base_storage_model.py > /dev/null 2>&1 || echo "Black encountered issues"

echo "Running Ruff..."
ruff check --fix ipfs_kit_py/mcp/models/storage/base_storage_model.py > /dev/null 2>&1 || echo "Ruff encountered issues"

echo "Done with base_storage_model.py"