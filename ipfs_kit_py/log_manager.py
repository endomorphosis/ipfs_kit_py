import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import datetime

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'
LOGS_PATH = IPFS_KIT_PATH / 'logs'

# Try to import ipfs_datasets integration
try:
    from .ipfs_datasets_integration import get_ipfs_datasets_manager, IPFS_DATASETS_AVAILABLE
except ImportError:
    IPFS_DATASETS_AVAILABLE = False
    def get_ipfs_datasets_manager(*args, **kwargs):
        return None

class LogManager:
    """
    Manages log files with optional ipfs_datasets_py integration for distributed log storage.
    """
    
    def __init__(self, enable_dataset_storage: bool = False, ipfs_client=None):
        """
        Initialize the log manager.
        
        Args:
            enable_dataset_storage: Enable ipfs_datasets_py for distributed log storage
            ipfs_client: Optional IPFS client for dataset storage
        """
        LOGS_PATH.mkdir(exist_ok=True, parents=True)
        
        # Initialize ipfs_datasets integration if requested
        self.enable_dataset_storage = enable_dataset_storage and IPFS_DATASETS_AVAILABLE
        self.datasets_manager = None
        
        if self.enable_dataset_storage:
            try:
                self.datasets_manager = get_ipfs_datasets_manager(
                    ipfs_client=ipfs_client,
                    enable=True
                )
                if not (self.datasets_manager and self.datasets_manager.is_available()):
                    self.enable_dataset_storage = False
            except Exception:
                self.enable_dataset_storage = False

    def get_logs(self, component=None) -> List[str]:
        """Get logs for a specific component or all logs."""
        logs = []
        for log_file in os.listdir(LOGS_PATH):
            if component and component not in log_file:
                continue
            with open(LOGS_PATH / log_file, 'r') as f:
                logs.extend(f.readlines())
        return logs
    
    def store_logs_as_dataset(self, component: Optional[str] = None, 
                             version: Optional[str] = None) -> Dict[str, Any]:
        """
        Store logs as a versioned dataset using ipfs_datasets_py.
        
        Args:
            component: Optional component name to filter logs
            version: Optional version identifier for the log dataset
        
        Returns:
            Dictionary with storage results including CID if distributed
        """
        if not self.enable_dataset_storage:
            return {"success": False, "error": "Dataset storage not enabled"}
        
        try:
            # Create a temporary aggregated log file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
                logs = self.get_logs(component)
                f.writelines(logs)
                temp_path = f.name
            
            # Store as dataset
            metadata = {
                "type": "logs",
                "component": component or "all",
                "timestamp": datetime.datetime.now().isoformat(),
                "log_count": len(logs)
            }
            
            if version:
                metadata["version"] = version
            
            result = self.datasets_manager.store(
                temp_path,
                metadata=metadata
            )
            
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}