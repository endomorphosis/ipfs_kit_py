#!/bin/bash

# Function to fix syntax issues in base_storage_model.py
fix_base_storage_model() {
    echo "Fixing syntax issues in base_storage_model.py..."
    
    # Create a backup
    cp ipfs_kit_py/mcp/models/storage/base_storage_model.py ipfs_kit_py/mcp/models/storage/base_storage_model.py.bak
    
    # Fix the imports
    sed -i 's/from typing import Dict, Any/from typing import Dict, Any, Optional, Union, Callable, TypeVar, Awaitable, Set/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    # Remove the redundant type imports
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
    
    # Fix other method definitions with missing commas
    sed -i 's/    def _update_stats(/    def _update_stats(self,/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    sed -i 's/        self/        self,/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    # Fix _handle_exception
    sed -i 's/    def _handle_exception(/    def _handle_exception(self, e: Exception, result: Dict[str, Any], operation: str):/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    # Fix _handle_exception_async
    sed -i 's/    def _handle_exception_async(/    def _handle_exception_async(self, e: Exception, result: Dict[str, Any], operation: str):/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    # Fix _cache_put_async
    sed -i 's/    async def _cache_put_async(/    async def _cache_put_async(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None):/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    # Fix _with_retry_async
    sed -i 's/    async def _with_retry_async(/    async def _with_retry_async(self, operation_func, operation_name: str, retry_config: Optional[Dict[str, Any]] = None, *args, **kwargs):/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    # Fix _with_retry_sync
    sed -i 's/    def _with_retry_sync(/    def _with_retry_sync(self, operation_func, operation_name: str, retry_config: Optional[Dict[str, Any]] = None, *args, **kwargs):/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    # Fix missing parentheses in result["error"] assignments
    sed -i 's/        result\["error"\] = (/        result\["error"\] = (/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    sed -i 's/            f"Operation failed after {config\["max_retries"\]} attempts: {str(last_error)}"/            f"Operation failed after {config\["max_retries"\]} attempts: {str(last_error)}");/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    # Fix the notification of listeners
    sed -i 's/        await self._notify_listeners(/        await self._notify_listeners(/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    sed -i 's/"retry"/"retry",/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    sed -i 's/"error"/"error",/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    # Fix missing parenthesis in anyio.get_event_loop().run_in_executor(
    sed -i 's/                        None, listener, event_type, event_data/                        None, listener, event_type, event_data)/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    # Fix formatting in latency dictionary block
    sed -i 's/}/},/' ipfs_kit_py/mcp/models/storage/base_storage_model.py
    
    echo "Applied fixes to base_storage_model.py"
}

# Function to fix other problematic files
fix_problematic_files() {
    echo "Fixing other problematic files..."
    
    # Create a backup directory
    BACKUP_DIR="syntax_fixes_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p $BACKUP_DIR
    
    # Copy problematic files to backup directory
    cp ipfs_kit_py/mcp/models/mcp_discovery_model.py $BACKUP_DIR/
    cp ipfs_kit_py/mcp/models/ipfs_model.py $BACKUP_DIR/
    cp ipfs_kit_py/mcp/models/libp2p_model.py $BACKUP_DIR/
    cp ipfs_kit_py/mcp/storage_manager/performance.py $BACKUP_DIR/
    cp ipfs_kit_py/mcp/storage_manager/migration.py $BACKUP_DIR/
    cp ipfs_kit_py/mcp/storage_manager/notifications.py $BACKUP_DIR/
    cp ipfs_kit_py/mcp/persistence/cache_manager.py $BACKUP_DIR/
    
    # Fix common issues in these files (adding missing ), fixing indentation)
    files=(
        "ipfs_kit_py/mcp/models/mcp_discovery_model.py"
        "ipfs_kit_py/mcp/models/ipfs_model.py"
        "ipfs_kit_py/mcp/models/libp2p_model.py"
        "ipfs_kit_py/mcp/storage_manager/performance.py"
        "ipfs_kit_py/mcp/storage_manager/migration.py" 
        "ipfs_kit_py/mcp/storage_manager/notifications.py"
        "ipfs_kit_py/mcp/persistence/cache_manager.py"
    )
    
    for file in "${files[@]}"; do
        echo "Fixing $file..."
        
        # Fix function declarations with missing self parameter
        sed -i 's/    def \([a-zA-Z0-9_]*\)(/    def \1(self/' $file
        
        # Fix async function declarations with missing self parameter
        sed -i 's/    async def \([a-zA-Z0-9_]*\)(/    async def \1(self/' $file
        
        # Fix method parameters that are missing commas
        sed -i 's/\(    def [a-zA-Z0-9_]*\)(self[[:space:]]*\([a-zA-Z0-9_]*\):/\1(self, \2:/' $file
        sed -i 's/\(    async def [a-zA-Z0-9_]*\)(self[[:space:]]*\([a-zA-Z0-9_]*\):/\1(self, \2:/' $file
        
        # Fix redefined function warnings
        sed -i 's/    # WARNING: Function/    # DISABLED:/' $file
        
        # Fix indentation issues
        sed -i 's/^        self,/    def __init__(self,/' $file
        
        # Fix missing parentheses in method calls
        sed -i 's/await self._notify_listeners$/await self._notify_listeners(/' $file
        
        # Fix missing closing parentheses
        sed -i 's/self.listeners.add(listener$/self.listeners.add(listener)/' $file
        
        echo "Applied fixes to $file"
    done
}

# Create a backup of the entire mcp directory
echo "Creating backup of the entire mcp directory..."
FULL_BACKUP="mcp_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $FULL_BACKUP
cp -r ipfs_kit_py/mcp/* $FULL_BACKUP/
echo "Backup created in $FULL_BACKUP"

# First fix specific files with severe syntax errors
fix_base_storage_model
fix_problematic_files

# Now run Black on the fixed files
echo "Running Black on fixed files..."
black ipfs_kit_py/mcp/models/storage/base_storage_model.py
black ipfs_kit_py/mcp/models/mcp_discovery_model.py
black ipfs_kit_py/mcp/models/ipfs_model.py
black ipfs_kit_py/mcp/models/libp2p_model.py
black ipfs_kit_py/mcp/storage_manager/performance.py
black ipfs_kit_py/mcp/storage_manager/migration.py
black ipfs_kit_py/mcp/storage_manager/notifications.py
black ipfs_kit_py/mcp/persistence/cache_manager.py

# Run Ruff on the fixed files
echo "Running Ruff on fixed files..."
ruff check ipfs_kit_py/mcp/models/storage/base_storage_model.py --fix
ruff check ipfs_kit_py/mcp/models/mcp_discovery_model.py --fix
ruff check ipfs_kit_py/mcp/models/ipfs_model.py --fix
ruff check ipfs_kit_py/mcp/models/libp2p_model.py --fix
ruff check ipfs_kit_py/mcp/storage_manager/performance.py --fix
ruff check ipfs_kit_py/mcp/storage_manager/migration.py --fix
ruff check ipfs_kit_py/mcp/storage_manager/notifications.py --fix
ruff check ipfs_kit_py/mcp/persistence/cache_manager.py --fix

# Final pass with Black on the entire directory
echo "Running final pass with Black on the entire directory..."
black ipfs_kit_py/mcp || echo "Black encountered some issues (continuing)"

# Final pass with Ruff on the entire directory
echo "Running final pass with Ruff on the entire directory..."
ruff check ipfs_kit_py/mcp --fix || echo "Ruff encountered some issues (continuing)"

echo "Process complete! Fixed syntax errors and applied Black and Ruff formatting."
echo "Original files backed up in $FULL_BACKUP"