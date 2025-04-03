"""
AI/ML Integration for IPFS Kit.

This module provides integration with AI/ML frameworks, enabling:
1. Langchain/LlamaIndex connectors for knowledge graph and content-addressed storage
2. ML model storage and distribution using IPFS content addressing
3. Dataset management for AI workloads with versioning and distribution
4. Distributed training capabilities leveraging the cluster architecture

This implementation focuses on integrating existing AI/ML frameworks with IPFS's
content-addressed storage and distributed architecture, providing seamless interoperability
for machine learning workflows in a decentralized environment.

Key components:
- ModelRegistry: For storing, versioning, and distributing ML models
- DatasetManager: For managing ML datasets with versioning and distribution
- LangchainIntegration: Connectors for Langchain framework
- LlamaIndexIntegration: Connectors for LlamaIndex framework
- DistributedTraining: Infrastructure for distributed model training
"""

import os
import json
import logging
import uuid
import pickle
import time
import queue
import threading
import tempfile  # Added import
from typing import Dict, List, Optional, Any, Tuple, Set, Union, Callable
from pathlib import Path
from unittest.mock import MagicMock # Added import

# Try to import AI/ML dependencies with appropriate fallbacks
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# Check for Langchain availability
try:
    import langchain
    from langchain.schema import Document
    from langchain.vectorstores import VectorStore
    from langchain.embeddings.base import Embeddings
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

# Check for LlamaIndex availability
try:
    import llama_index
    from llama_index.core import Document as LlamaDocument
    from llama_index.core.indices.base import BaseIndex
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False

# Check for machine learning frameworks
try:
    import sklearn
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

# Configure logger
logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Registry for ML models with IPFS-based content addressing.
    
    Provides storage, versioning, and distribution of machine learning models
    using IPFS content addressing for immutability and deduplication.
    """
    
    def __init__(self, ipfs_client, base_path: str = "~/.ipfs_models"):
        """
        Initialize the model registry.
        
        Args:
            ipfs_client: IPFS client instance for storage
            base_path: Local path for model registry metadata
        """
        self.ipfs = ipfs_client
        self.base_path = os.path.expanduser(base_path)
        os.makedirs(self.base_path, exist_ok=True)
        
        # Registry data structure
        self.registry_file = os.path.join(self.base_path, "model_registry.json")
        self.registry = self._load_registry()
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Check available frameworks
        self._check_available_frameworks()
    
    def _check_available_frameworks(self):
        """Log information about available ML frameworks."""
        frameworks = []
        if SKLEARN_AVAILABLE:
            frameworks.append(f"scikit-learn {sklearn.__version__}")
        if TORCH_AVAILABLE:
            frameworks.append(f"PyTorch {torch.__version__}")
        if TF_AVAILABLE:
            frameworks.append(f"TensorFlow {tf.__version__}")
            
        if frameworks:
            logger.info(f"ModelRegistry initialized with frameworks: {', '.join(frameworks)}")
        else:
            logger.warning("No ML frameworks detected. Limited functionality available.")
            logger.info("For full functionality, install scikit-learn, PyTorch, or TensorFlow.")
    
    def _load_registry(self) -> Dict:
        """Load the registry from disk or initialize if not exists."""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Registry file corrupted, initializing new registry")
        
        # Initialize empty registry
        registry = {
            "models": {},
            "updated_at": time.time(),
            "version": "1.0.0"
        }
        
        # Save empty registry
        self._save_registry(registry)
        return registry
    
    def _save_registry(self, registry=None):
        """Save the registry to disk and optionally to IPFS."""
        if registry is None:
            registry = self.registry
            
        # Update timestamp
        registry["updated_at"] = time.time()
        
        # Save to local file
        with open(self.registry_file, 'w') as f:
            json.dump(registry, f, indent=2)
            
        # Optionally, save to IPFS for distributed access
        try:
            result = self.ipfs.dag_put(registry)
            logger.debug(f"Registry saved to IPFS with CID: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to save registry to IPFS: {e}")
            return None
    
    def add_model(self, model, model_name: str, version: str = "1.0.0", 
                 framework: str = None, metadata: Dict = None) -> Dict:
        """
        Add a model to the registry.
        
        Args:
            model: The model object to store
            model_name: Name identifier for the model
            version: Version string (semver recommended)
            framework: ML framework used (e.g., "pytorch", "tensorflow", "sklearn")
            metadata: Additional information about the model
            
        Returns:
            Dict with operation result including CID
        """
        result = {
            "success": False,
            "operation": "add_model",
            "timestamp": time.time()
        }
        
        try:
            # Determine framework if not specified
            if framework is None:
                framework = self._detect_framework(model)
                
            # Prepare metadata
            if metadata is None:
                metadata = {}
                
            model_info = {
                "name": model_name,
                "version": version,
                "framework": framework,
                "added_at": time.time(),
                "metadata": metadata
            }
            
            # Create a temporary directory for model files
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Save model based on framework
                model_files = self._save_model_files(model, framework, tmp_dir)
                model_info["files"] = model_files
                
                # Add metadata file
                metadata_path = os.path.join(tmp_dir, "metadata.json")
                with open(metadata_path, 'w') as f:
                    json.dump(model_info, f, indent=2)
                
                # Add directory to IPFS
                dir_result = self.ipfs.add_directory(tmp_dir)
                
                if not dir_result.get("success", False):
                    raise Exception(f"Failed to add model to IPFS: {dir_result.get('error')}")
                
                model_cid = dir_result.get("Hash") or dir_result.get("cid")
                
                # Update registry
                with self._lock:
                    if model_name not in self.registry["models"]:
                        self.registry["models"][model_name] = {}
                    
                    self.registry["models"][model_name][version] = {
                        "cid": model_cid,
                        "framework": framework,
                        "added_at": time.time(),
                        "metadata": metadata
                    }
                    
                    # Save updated registry
                    registry_cid = self._save_registry()
                
                # Pin the model for persistence
                try:
                    self.ipfs.pin_add(model_cid)
                except Exception as e:
                    logger.warning(f"Failed to pin model {model_name} v{version}: {e}")
                
                result.update({
                    "success": True,
                    "model_name": model_name,
                    "version": version,
                    "framework": framework,
                    "cid": model_cid,
                    "registry_cid": registry_cid
                })
                
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error adding model {model_name}: {e}")
            
        return result
    
    def _detect_framework(self, model) -> str:
        """
        Detect the ML framework used by the model.
        
        Args:
            model: The model object
            
        Returns:
            String identifier for the framework
        """
        # Check for sklearn models
        if SKLEARN_AVAILABLE and hasattr(sklearn, 'base') and isinstance(model, sklearn.base.BaseEstimator):
            return "sklearn"
            
        # Check for PyTorch models
        if TORCH_AVAILABLE and isinstance(model, torch.nn.Module):
            return "pytorch"
            
        # Check for TensorFlow/Keras models
        if TF_AVAILABLE:
            if hasattr(tf, 'keras') and isinstance(model, tf.keras.Model):
                return "tensorflow"
            elif isinstance(model, tf.Module):
                return "tensorflow"
                
        # Handle unknown framework
        logger.warning("Could not detect model framework, using 'unknown'")
        return "unknown"
    
    def _save_model_files(self, model, framework: str, directory: str) -> Dict[str, str]:
        """
        Save model files to a directory based on the framework.
        
        Args:
            model: The model object
            framework: ML framework identifier
            directory: Directory to save files
            
        Returns:
            Dict mapping file types to relative paths
        """
        files = {}
        
        try:
            if framework == "sklearn":
                # Save scikit-learn model with pickle
                model_path = os.path.join(directory, "model.pkl")
                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)
                files["model"] = "model.pkl"
                
            elif framework == "pytorch":
                # Save PyTorch model
                model_path = os.path.join(directory, "model.pt")
                torch.save(model, model_path)
                files["model"] = "model.pt"
                
                # Also save a script version if possible
                try:
                    script_path = os.path.join(directory, "model_script.pt")
                    script_model = torch.jit.script(model)
                    torch.jit.save(script_model, script_path)
                    files["script"] = "model_script.pt"
                except Exception as e:
                    logger.warning(f"Failed to save PyTorch scripted model: {e}")
                
            elif framework == "tensorflow":
                # Save TF model in SavedModel format
                model_dir = os.path.join(directory, "saved_model")
                tf.saved_model.save(model, model_dir)
                files["saved_model"] = "saved_model"
                
                # Try to save as H5 format as well (for Keras models)
                try:
                    h5_path = os.path.join(directory, "model.h5")
                    model.save(h5_path)
                    files["h5"] = "model.h5"
                except Exception as e:
                    logger.debug(f"Failed to save TF model as H5 (likely not a Keras model): {e}")
                    
            else:
                # Generic fallback using pickle
                model_path = os.path.join(directory, "model.pkl")
                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)
                files["model"] = "model.pkl"
                logger.warning(f"Using generic pickle serialization for framework: {framework}")
                
            return files
            
        except Exception as e:
            logger.error(f"Error saving model files for {framework}: {e}")
            raise
    
    def get_model(self, model_name: str, version: str = None) -> Tuple[Any, Dict]:
        """
        Retrieve a model from the registry.
        
        Args:
            model_name: Name of the model to retrieve
            version: Specific version to retrieve (defaults to latest)
            
        Returns:
            Tuple of (model_object, model_metadata)
        """
        # Find the model in registry
        if model_name not in self.registry["models"]:
            raise ValueError(f"Model '{model_name}' not found in registry")
            
        # Get latest version if not specified
        if version is None:
            # Get latest based on semver (simple implementation)
            versions = list(self.registry["models"][model_name].keys())
            if not versions:
                raise ValueError(f"No versions found for model '{model_name}'")
            version = sorted(versions)[-1]
        
        # Get model info
        model_info = self.registry["models"][model_name].get(version)
        if not model_info:
            raise ValueError(f"Version '{version}' not found for model '{model_name}'")
            
        model_cid = model_info["cid"]
        framework = model_info["framework"]
        
        # Create temporary directory for model files
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Get model files from IPFS
            self.ipfs.get(model_cid, tmp_dir)
            model_dir = os.path.join(tmp_dir, model_cid)
            
            # Load metadata
            metadata_path = os.path.join(model_dir, "metadata.json")
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Load model based on framework
            model = self._load_model_files(model_dir, framework, metadata)
            
            return model, metadata
    
    def _load_model_files(self, directory: str, framework: str, metadata: Dict) -> Any:
        """
        Load model from files based on framework.
        
        Args:
            directory: Directory containing model files
            framework: ML framework identifier
            metadata: Model metadata with file information
            
        Returns:
            The loaded model object
        """
        files = metadata.get("files", {})
        
        if framework == "sklearn":
            # Load scikit-learn model
            model_path = os.path.join(directory, files.get("model", "model.pkl"))
            with open(model_path, 'rb') as f:
                return pickle.load(f)
                
        elif framework == "pytorch":
            # Load PyTorch model
            # Try scripted version first if available
            if "script" in files:
                script_path = os.path.join(directory, files["script"])
                return torch.jit.load(script_path)
            
            # Fall back to regular model
            model_path = os.path.join(directory, files.get("model", "model.pt"))
            return torch.load(model_path)
            
        elif framework == "tensorflow":
            # Try SavedModel format first
            if "saved_model" in files:
                model_dir = os.path.join(directory, files["saved_model"])
                return tf.saved_model.load(model_dir)
            
            # Fall back to H5 format
            if "h5" in files:
                h5_path = os.path.join(directory, files["h5"])
                return tf.keras.models.load_model(h5_path)
                
            raise ValueError(f"No compatible TensorFlow model format found in {files}")
            
        else:
            # Generic fallback using pickle
            model_path = os.path.join(directory, files.get("model", "model.pkl"))
            with open(model_path, 'rb') as f:
                return pickle.load(f)
    
    def list_models(self) -> Dict:
        """
        List available models in the registry.
        
        Returns:
            Dict with model information
        """
        result = {
            "success": True,
            "operation": "list_models",
            "models": {},
            "count": 0,
            "timestamp": time.time()
        }
        
        # Convert registry format to simplified listing
        for model_name, versions in self.registry["models"].items():
            result["models"][model_name] = []
            for version, info in versions.items():
                result["models"][model_name].append({
                    "version": version,
                    "framework": info.get("framework", "unknown"),
                    "added_at": info.get("added_at"),
                    "cid": info.get("cid"),
                    "metadata": info.get("metadata", {})
                })
            
            # Sort versions
            result["models"][model_name].sort(key=lambda x: x["version"])
        
        result["count"] = len(result["models"])
        return result


class DatasetManager:
    """
    Manager for AI/ML datasets with versioning and distribution.
    
    Provides tools for storing, versioning, and distributing datasets
    for machine learning workloads, leveraging content addressing for
    efficient sharing and deduplication.
    """
    
    def __init__(self, ipfs_client, base_path: str = "~/.ipfs_datasets"):
        """
        Initialize the dataset manager.
        
        Args:
            ipfs_client: IPFS client instance for storage
            base_path: Local path for dataset registry metadata
        """
        self.ipfs = ipfs_client
        self.base_path = os.path.expanduser(base_path)
        os.makedirs(self.base_path, exist_ok=True)
        
        # Registry data structure
        self.registry_file = os.path.join(self.base_path, "dataset_registry.json")
        self.registry = self._load_registry()
        
        # Lock for thread safety
        self._lock = threading.RLock()
    
    def _load_registry(self) -> Dict:
        """Load the registry from disk or initialize if not exists."""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Dataset registry file corrupted, initializing new registry")
        
        # Initialize empty registry
        registry = {
            "datasets": {},
            "updated_at": time.time(),
            "version": "1.0.0"
        }
        
        # Save empty registry
        self._save_registry(registry)
        return registry

    def _convert_to_json_serializable(self, obj):
        """Recursively convert numpy/pandas types to standard Python types."""
        if isinstance(obj, dict):
            return {k: self._convert_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_serializable(elem) for elem in obj]
        # Check for specific numpy integer types
        elif NUMPY_AVAILABLE and isinstance(obj, (np.int64, np.int32, np.int16, np.int8, np.uint64, np.uint32, np.uint16, np.uint8)):
            return int(obj)
        # Check for specific numpy float types (excluding deprecated np.float_)
        elif NUMPY_AVAILABLE and isinstance(obj, (np.float16, np.float32, np.float64)):
            return float(obj)
        elif NUMPY_AVAILABLE and isinstance(obj, np.ndarray):
            return obj.tolist() # Convert numpy arrays to lists
        elif PANDAS_AVAILABLE and hasattr(obj, 'to_dict'): # Handle pandas Series/DataFrame if needed
             # This might need refinement depending on how pandas objects are stored
             # For now, assume basic types or convert to dict
             try:
                 return obj.to_dict()
             except Exception:
                 return str(obj) # Fallback to string representation
        # Handle MagicMock specifically for testing environments
        elif isinstance(obj, MagicMock):
             # Use repr(obj) for a standard string representation
             return repr(obj) # Represent MagicMock as a string
        # Add checks for other non-serializable types if necessary
        return obj

    def _save_registry(self, registry=None):
        """Save the registry to disk and optionally to IPFS."""
        if registry is None:
            registry = self.registry

        # Update timestamp
        registry["updated_at"] = time.time()

        # Convert registry to be JSON serializable
        serializable_registry = self._convert_to_json_serializable(registry)

        # Save to local file
        try:
            with open(self.registry_file, 'w') as f:
                json.dump(serializable_registry, f, indent=2)
        except TypeError as e:
            logger.error(f"Failed to serialize registry for local save: {e}")
            # Optionally log the problematic part of the registry
            # logger.error(f"Problematic registry data: {serializable_registry}")
            raise # Re-raise the error after logging

        # Optionally, save to IPFS for distributed access
        try:
            # Use the serializable version for dag_put as well
            result = self.ipfs.dag_put(serializable_registry)
            logger.debug(f"Dataset registry saved to IPFS with CID: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to save dataset registry to IPFS: {e}")
            return None
    
    def add_dataset(self, dataset_path: str, dataset_name: str, 
                   version: str = "1.0.0", format: str = None,
                   metadata: Dict = None) -> Dict:
        """
        Add a dataset to the registry.
        
        Args:
            dataset_path: Path to the dataset file or directory
            dataset_name: Name identifier for the dataset
            version: Version string (semver recommended)
            format: Dataset format (e.g., "csv", "parquet", "jsonl", "images")
            metadata: Additional information about the dataset
            
        Returns:
            Dict with operation result including CID
        """
        result = {
            "success": False,
            "operation": "add_dataset",
            "timestamp": time.time()
        }
        
        try:
            # Ensure path exists
            if not os.path.exists(dataset_path):
                raise FileNotFoundError(f"Dataset path not found: {dataset_path}")
                
            # Determine format if not specified
            if format is None:
                format = self._detect_format(dataset_path)
                
            # Prepare metadata
            if metadata is None:
                metadata = {}
                
            dataset_info = {
                "name": dataset_name,
                "version": version,
                "format": format,
                "added_at": time.time(),
                "metadata": metadata
            }
            
            # Create a temporary directory for dataset files
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Create metadata file
                metadata_path = os.path.join(tmp_dir, "metadata.json")
                with open(metadata_path, 'w') as f:
                    json.dump(dataset_info, f, indent=2)
                    
                # Copy dataset to tmp directory
                target_dir = os.path.join(tmp_dir, "data")
                os.makedirs(target_dir, exist_ok=True)
                
                if os.path.isdir(dataset_path):
                    # Copy directory contents
                    import shutil
                    shutil.copytree(dataset_path, target_dir, dirs_exist_ok=True)
                else:
                    # Copy single file
                    import shutil
                    shutil.copy2(dataset_path, target_dir)
                
                dir_result = self.ipfs.add_directory(tmp_dir)
                
                if not dir_result.get("success", False):
                    raise Exception(f"Failed to add dataset to IPFS: {dir_result.get('error')}")
                
                dataset_cid = dir_result.get("Hash") or dir_result.get("cid")
                
                # Generate dataset stats
                stats = self._generate_dataset_stats(dataset_path, format)

                # Ensure stats are JSON serializable (convert numpy types etc.)
                serializable_stats = {}
                for k, v in stats.items():
                    if NUMPY_AVAILABLE:
                        # Check for numpy types only if numpy is available
                        if isinstance(v, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)):
                            serializable_stats[k] = int(v)
                            continue
                        # Check for specific numpy float types (excluding deprecated np.float_)
                        elif isinstance(v, (np.float16, np.float32, np.float64)):
                            serializable_stats[k] = float(v)
                            continue
                        elif isinstance(v, np.ndarray):
                            serializable_stats[k] = v.tolist()
                            continue
                    # Check basic types last
                    if isinstance(v, (list, dict, str, int, float, bool, type(None))):
                         serializable_stats[k] = v # Already serializable
                    else:
                         serializable_stats[k] = str(v) # Fallback to string representation

                # Update registry
                with self._lock:
                    if dataset_name not in self.registry["datasets"]:
                        self.registry["datasets"][dataset_name] = {}
                    
                    self.registry["datasets"][dataset_name][version] = {
                        "cid": dataset_cid,
                        "format": format,
                        "added_at": time.time(),
                        "stats": serializable_stats, # Use the cleaned stats
                        "metadata": metadata
                    }
                    
                    # Save updated registry
                    registry_cid = self._save_registry()
                
                # Pin the dataset for persistence
                try:
                    self.ipfs.pin_add(dataset_cid)
                except Exception as e:
                    logger.warning(f"Failed to pin dataset {dataset_name} v{version}: {e}")
                
                result.update({
                    "success": True,
                    "dataset_name": dataset_name,
                    "version": version,
                    "format": format,
                    "cid": dataset_cid,
                    "registry_cid": registry_cid,
                    "stats": stats
                })
                
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error adding dataset {dataset_name}: {e}")
            
        return result
    
    def _detect_format(self, path: str) -> str:
        """
        Detect the format of a dataset based on its path.
        
        Args:
            path: Path to the dataset file or directory
            
        Returns:
            String identifier for the format
        """
        if os.path.isdir(path):
            # Check for common directory formats
            if any(f.endswith('.jpg') or f.endswith('.jpeg') or f.endswith('.png') 
                  for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))):
                return "images"
                
            if any(f.endswith('.tfrecord') for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))):
                return "tfrecord"
                
            if any(f.endswith('.parquet') for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))):
                return "parquet-directory"
                
            # Default for directories
            return "directory"
        else:
            # Single file detection
            file_ext = os.path.splitext(path)[1].lower()
            
            format_map = {
                '.csv': 'csv',
                '.tsv': 'tsv',
                '.jsonl': 'jsonl',
                '.json': 'json',
                '.parquet': 'parquet',
                '.arrow': 'arrow',
                '.feather': 'feather',
                '.h5': 'hdf5',
                '.hdf5': 'hdf5',
                '.tfrecord': 'tfrecord',
                '.txt': 'text',
            }
            
            return format_map.get(file_ext, 'unknown')
    
    def _generate_dataset_stats(self, path: str, format: str) -> Dict:
        """
        Generate basic statistics for a dataset.
        
        Args:
            path: Path to the dataset file or directory
            format: Dataset format
            
        Returns:
            Dict with dataset statistics
        """
        stats = {
            "size_bytes": 0,
            "num_files": 0,
            "num_rows": None,
            "columns": None
        }
        
        try:
            # Calculate size and file count
            size_bytes = 0
            num_files = 0
            if os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    num_files += len(files)
                    for file in files:
                        try:
                            file_path = os.path.join(root, file)
                            size_bytes += os.path.getsize(file_path)
                        except OSError:
                            logger.warning(f"Could not get size for file: {file_path}")
            else:
                num_files = 1
                try:
                    size_bytes = os.path.getsize(path)
                except OSError:
                     logger.warning(f"Could not get size for file: {path}")

            stats["num_files"] = int(num_files) # Ensure int
            stats["size_bytes"] = int(size_bytes) # Ensure int

            # Format-specific stats
            if format == 'csv' and PANDAS_AVAILABLE: # Check PANDAS_AVAILABLE
                try:
                    import pandas as pd
                    df = pd.read_csv(path, nrows=5) # Read just a few rows for schema
                    # Ensure columns are strings
                    stats["columns"] = [str(col) for col in df.columns.tolist()]
                    # Count rows manually - less prone to mock issues
                    with open(path, 'r') as f_count:
                         row_count = sum(1 for _ in f_count)
                    # Subtract header if file is not empty
                    stats["num_rows"] = int(max(0, row_count -1)) if row_count > 0 else 0 # Ensure int
                except Exception as e:
                    logger.debug(f"Failed to read CSV stats: {e}")

            elif format == 'parquet' and PANDAS_AVAILABLE and NUMPY_AVAILABLE: # Check PANDAS_AVAILABLE and NUMPY
                try:
                    import pandas as pd
                    # Assuming pyarrow is installed for parquet support
                    df = pd.read_parquet(path)
                    # Ensure columns are strings and length is int
                    stats["columns"] = [str(col) for col in df.columns.tolist()]
                    stats["num_rows"] = int(len(df))
                except Exception as e:
                    logger.debug(f"Failed to read Parquet stats: {e}")

            return stats

        except Exception as e:
            # Catch potential errors during stat generation itself
            logger.warning(f"Error generating dataset stats for {path}: {e}")
            # Return the partially filled stats or default stats
            return stats # Return whatever stats were collected so far
    
    def get_dataset(self, dataset_name: str, version: str = None, 
                   output_path: str = None) -> Dict:
        """
        Retrieve a dataset from the registry.
        
        Args:
            dataset_name: Name of the dataset to retrieve
            version: Specific version to retrieve (defaults to latest)
            output_path: Path to save the dataset (if None, a temp directory is used)
            
        Returns:
            Dict with dataset information and local path
        """
        result = {
            "success": False,
            "operation": "get_dataset",
            "timestamp": time.time()
        }
        
        # Create temp dir if output_path not provided
        temp_dir = None
        if output_path is None:
            temp_dir = tempfile.mkdtemp()
            output_path = temp_dir
        
        try:
            # Find the dataset in registry
            if dataset_name not in self.registry["datasets"]:
                raise ValueError(f"Dataset '{dataset_name}' not found in registry")
                
            # Get latest version if not specified
            if version is None:
                # Get latest based on semver (simple implementation)
                versions = list(self.registry["datasets"][dataset_name].keys())
                if not versions:
                    raise ValueError(f"No versions found for dataset '{dataset_name}'")
                version = sorted(versions)[-1]
            
            # Get dataset info
            dataset_info = self.registry["datasets"][dataset_name].get(version)
            if not dataset_info:
                raise ValueError(f"Version '{version}' not found for dataset '{dataset_name}'")
                
            dataset_cid = dataset_info["cid"]
            
            # Get dataset files from IPFS
            get_result = self.ipfs.get(dataset_cid, output_path)
            
            if not get_result.get("success", False):
                raise Exception(f"Failed to get dataset from IPFS: {get_result.get('error')}")
            
            # Construct paths
            dataset_dir = os.path.join(output_path, dataset_cid)
            data_dir = os.path.join(dataset_dir, "data")
            metadata_path = os.path.join(dataset_dir, "metadata.json")
            
            # Load metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            result.update({
                "success": True,
                "dataset_name": dataset_name,
                "version": version,
                "format": dataset_info.get("format"),
                "cid": dataset_cid,
                "local_path": data_dir,
                "metadata": metadata,
                "temp_dir": temp_dir
            })
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error getting dataset {dataset_name}: {e}")
            
            # Clean up temp dir if created and failure occurred
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
                
        return result
    
    def list_datasets(self) -> Dict:
        """
        List available datasets in the registry.
        
        Returns:
            Dict with dataset information
        """
        result = {
            "success": True,
            "operation": "list_datasets",
            "datasets": {},
            "count": 0,
            "timestamp": time.time()
        }
        
        # Convert registry format to simplified listing
        for dataset_name, versions in self.registry["datasets"].items():
            result["datasets"][dataset_name] = []
            for version, info in versions.items():
                result["datasets"][dataset_name].append({
                    "version": version,
                    "format": info.get("format", "unknown"),
                    "added_at": info.get("added_at"),
                    "cid": info.get("cid"),
                    "stats": info.get("stats", {}),
                    "metadata": info.get("metadata", {})
                })
            
            # Sort versions
            result["datasets"][dataset_name].sort(key=lambda x: x["version"])
        
        result["count"] = len(result["datasets"])
        return result


class LangchainIntegration:
    """
    Langchain integration for IPFS-based content and knowledge graphs.
    
    Provides connectors and utilities for integrating Langchain with
    IPFS content addressing and distributed storage capabilities.
    """
    
    def __init__(self, ipfs_client):
        """
        Initialize the Langchain integration.
        
        Args:
            ipfs_client: IPFS client instance
        """
        self.ipfs = ipfs_client
        
        if not LANGCHAIN_AVAILABLE:
            logger.warning("Langchain package not found. Limited functionality available.")
            logger.info("For full functionality, install langchain: pip install langchain")
    
    def check_availability(self) -> Dict:
        """
        Check if Langchain is available and return component status.
        
        Returns:
            Dict with availability information
        """
        result = {
            "langchain_available": LANGCHAIN_AVAILABLE,
            "numpy_available": NUMPY_AVAILABLE
        }
        
        if LANGCHAIN_AVAILABLE:
            result["langchain_version"] = langchain.__version__
            
        return result
    
    def create_ipfs_vectorstore(self, embedding_function: Any = None) -> Optional[Any]:
        """
        Create a Langchain VectorStore backed by IPFS storage.
        
        Args:
            embedding_function: Langchain embedding function to use
            
        Returns:
            VectorStore instance or None if not available
        """
        if not LANGCHAIN_AVAILABLE:
            logger.error("Cannot create vector store: Langchain not available")
            return None
            
        # This is a placeholder implementation - real implementation would
        # create a custom VectorStore that uses IPFS for storage
        class IPFSVectorStore(VectorStore):
            """Custom VectorStore implementation using IPFS for storage."""
            
            def __init__(self, ipfs_client, embedding_function: Embeddings):
                self.ipfs = ipfs_client
                self.embedding_function = embedding_function
                self.index = {}  # Simple in-memory index for this example
                self.cid = None  # IPFS CID for the persisted index
                
            def add_texts(
                self, texts: List[str], metadatas: Optional[List[Dict]] = None, **kwargs
            ) -> List[str]:
                """Add texts to the vectorstore with optional metadata."""
                # Create IDs for the texts
                ids = [str(uuid.uuid4()) for _ in texts]
                
                # Get embeddings
                embeddings = self.embedding_function.embed_documents(texts)
                
                # Store in the index
                for i, (text, embedding, id) in enumerate(zip(texts, embeddings, ids)):
                    metadata = metadatas[i] if metadatas else {}
                    self.index[id] = {
                        "text": text,
                        "embedding": embedding,
                        "metadata": metadata
                    }
                    
                # Persist the index to IPFS
                self._persist_index()
                
                return ids
                
            def similarity_search(
                self, query: str, k: int = 4, **kwargs
            ) -> List[Document]:
                """Search for similar documents using vector similarity."""
                # Get query embedding
                query_embedding = self.embedding_function.embed_query(query)
                
                # Simple L2 distance (not efficient for large datasets)
                distances = {}
                for id, data in self.index.items():
                    doc_embedding = data["embedding"]
                    # Calculate L2 distance (or other metric)
                    distance = sum((a - b) ** 2 for a, b in zip(query_embedding, doc_embedding)) ** 0.5
                    distances[id] = distance
                    
                # Sort by distance and get top k
                sorted_ids = sorted(distances.keys(), key=lambda id: distances[id])[:k]
                
                # Convert to Documents
                return [
                    Document(
                        page_content=self.index[id]["text"],
                        metadata=self.index[id]["metadata"]
                    )
                    for id in sorted_ids
                ]
                
            def _persist_index(self):
                """Persist the index to IPFS."""
                # Serialize the index (this is simplified - real implementation would be more robust)
                serialized = json.dumps({
                    id: {
                        "text": data["text"],
                        "embedding": data["embedding"],
                        "metadata": data["metadata"]
                    }
                    for id, data in self.index.items()
                }, default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x))
                
                # Add to IPFS
                result = self.ipfs.add_str(serialized)
                
                if result.get("success", False):
                    self.cid = result.get("Hash") or result.get("cid")
                    logger.debug(f"Vector store persisted to IPFS with CID: {self.cid}")
                
            @classmethod
            def from_ipfs(cls, ipfs_client, cid: str, embedding_function: Embeddings):
                """Load a vector store from IPFS."""
                # Create instance
                instance = cls(ipfs_client, embedding_function)
                
                # Get serialized index from IPFS
                result = ipfs_client.cat(cid)
                
                if result.get("success", False):
                    content = result.get("content") or result.get("Content")
                    
                    # Deserialize
                    loaded_index = json.loads(content)
                    
                    # Convert to proper format
                    instance.index = {
                        id: {
                            "text": data["text"],
                            "embedding": np.array(data["embedding"]),
                            "metadata": data["metadata"]
                        }
                        for id, data in loaded_index.items()
                    }
                    
                    instance.cid = cid
                    
                return instance
        
        # Create and return the vector store
        return IPFSVectorStore(self.ipfs, embedding_function)
    
    def create_document_loader(self, path_or_cid: str) -> Optional[Any]:
        """
        Create a document loader for IPFS content.
        
        Args:
            path_or_cid: Path or CID to load documents from
            
        Returns:
            Document loader instance or None if not available
        """
        if not LANGCHAIN_AVAILABLE:
            logger.error("Cannot create document loader: Langchain not available")
            return None
            
        # This is a placeholder implementation - real implementation would
        # create a custom document loader for IPFS content
        class IPFSDocumentLoader:
            """Load documents from IPFS."""
            
            def __init__(self, ipfs_client, path_or_cid: str):
                self.ipfs = ipfs_client
                self.path_or_cid = path_or_cid
                
            def load(self) -> List[Document]:
                """Load documents from IPFS."""
                documents = []
                
                # Check if CID or path
                if os.path.exists(self.path_or_cid):
                    # Load from local path
                    # This would use appropriate document loaders based on content type
                    if os.path.isdir(self.path_or_cid):
                        # Directory handling
                        for root, dirs, files in os.walk(self.path_or_cid):
                            for file in files:
                                file_path = os.path.join(root, file)
                                documents.extend(self._load_file(file_path))
                    else:
                        # Single file
                        documents.extend(self._load_file(self.path_or_cid))
                else:
                    # Treat as CID - get from IPFS to temp location
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        result = self.ipfs.get(self.path_or_cid, tmp_dir)
                        
                        if result.get("success", False):
                            content_path = os.path.join(tmp_dir, self.path_or_cid)
                            
                            if os.path.isdir(content_path):
                                # Directory handling
                                for root, dirs, files in os.walk(content_path):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        documents.extend(self._load_file(file_path))
                            else:
                                # Single file
                                documents.extend(self._load_file(content_path))
                                
                return documents
                
            def _load_file(self, file_path: str) -> List[Document]:
                """Load a single file as documents."""
                # This is a simplified implementation
                # Real implementation would use appropriate loaders
                # based on file type (TextLoader, CSVLoader, etc.)
                ext = os.path.splitext(file_path)[1].lower()
                
                try:
                    if ext in ['.txt', '.md', '.py', '.js', '.html', '.css']:
                        # Text file
                        with open(file_path, 'r', encoding='utf-8') as f:
                            text = f.read()
                            
                        return [Document(
                            page_content=text,
                            metadata={"source": file_path}
                        )]
                    elif ext in ['.pdf']:
                        # PDF file - would use PDFLoader in real implementation
                        return [Document(
                            page_content=f"[PDF content from {file_path}]",
                            metadata={"source": file_path}
                        )]
                    elif ext in ['.csv', '.tsv']:
                        # CSV file - would use CSVLoader in real implementation
                        return [Document(
                            page_content=f"[CSV content from {file_path}]",
                            metadata={"source": file_path}
                        )]
                    else:
                        # Unsupported format
                        logger.warning(f"Unsupported file format: {file_path}")
                        return []
                except Exception as e:
                    logger.error(f"Error loading file {file_path}: {e}")
                    return []
        
        # Create and return the document loader
        return IPFSDocumentLoader(self.ipfs, path_or_cid)


class LlamaIndexIntegration:
    """
    LlamaIndex integration for IPFS-based content and knowledge graphs.
    
    Provides connectors and utilities for integrating LlamaIndex with
    IPFS content addressing and distributed storage capabilities.
    """
    
    def __init__(self, ipfs_client):
        """
        Initialize the LlamaIndex integration.
        
        Args:
            ipfs_client: IPFS client instance
        """
        self.ipfs = ipfs_client
        
        if not LLAMA_INDEX_AVAILABLE:
            logger.warning("LlamaIndex package not found. Limited functionality available.")
            logger.info("For full functionality, install llama-index: pip install llama-index")
    
    def check_availability(self) -> Dict:
        """
        Check if LlamaIndex is available and return component status.
        
        Returns:
            Dict with availability information
        """
        result = {
            "llama_index_available": LLAMA_INDEX_AVAILABLE,
            "numpy_available": NUMPY_AVAILABLE
        }
        
        if LLAMA_INDEX_AVAILABLE:
            result["llama_index_version"] = llama_index.__version__
            
        return result
    
    def create_ipfs_document_reader(self, path_or_cid: str) -> Optional[Any]:
        """
        Create a LlamaIndex document reader for IPFS content.
        
        Args:
            path_or_cid: Path or CID to load documents from
            
        Returns:
            Document reader instance or None if not available
        """
        if not LLAMA_INDEX_AVAILABLE:
            logger.error("Cannot create document reader: LlamaIndex not available")
            return None
            
        # This is a placeholder implementation - real implementation would
        # create a custom document reader for IPFS content
        class IPFSReader:
            """Read documents from IPFS for LlamaIndex."""
            
            def __init__(self, ipfs_client, path_or_cid: str):
                self.ipfs = ipfs_client
                self.path_or_cid = path_or_cid
                
            def load_data(self) -> List[Any]:
                """Load documents from IPFS."""
                documents = []
                
                # Check if CID or path
                if os.path.exists(self.path_or_cid):
                    # Load from local path
                    # This would use appropriate document readers based on content type
                    if os.path.isdir(self.path_or_cid):
                        # Directory handling
                        for root, dirs, files in os.walk(self.path_or_cid):
                            for file in files:
                                file_path = os.path.join(root, file)
                                documents.extend(self._load_file(file_path))
                    else:
                        # Single file
                        documents.extend(self._load_file(self.path_or_cid))
                else:
                    # Treat as CID - get from IPFS to temp location
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        result = self.ipfs.get(self.path_or_cid, tmp_dir)
                        
                        if result.get("success", False):
                            content_path = os.path.join(tmp_dir, self.path_or_cid)
                            
                            if os.path.isdir(content_path):
                                # Directory handling
                                for root, dirs, files in os.walk(content_path):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        documents.extend(self._load_file(file_path))
                            else:
                                # Single file
                                documents.extend(self._load_file(content_path))
                                
                return documents
                
            def _load_file(self, file_path: str) -> List[Any]:
                """Load a single file as documents."""
                # This is a simplified implementation
                # Real implementation would use appropriate readers
                # based on file type
                ext = os.path.splitext(file_path)[1].lower()
                
                try:
                    if ext in ['.txt', '.md', '.py', '.js', '.html', '.css']:
                        # Text file
                        with open(file_path, 'r', encoding='utf-8') as f:
                            text = f.read()
                            
                        return [LlamaDocument(
                            text=text,
                            metadata={"source": file_path}
                        )]
                    elif ext in ['.pdf']:
                        # PDF file - would use PDFReader in real implementation
                        return [LlamaDocument(
                            text=f"[PDF content from {file_path}]",
                            metadata={"source": file_path}
                        )]
                    elif ext in ['.csv', '.tsv']:
                        # CSV file - would use CSVReader in real implementation
                        return [LlamaDocument(
                            text=f"[CSV content from {file_path}]",
                            metadata={"source": file_path}
                        )]
                    else:
                        # Unsupported format
                        logger.warning(f"Unsupported file format: {file_path}")
                        return []
                except Exception as e:
                    logger.error(f"Error loading file {file_path}: {e}")
                    return []
        
        # Create and return the document reader
        return IPFSReader(self.ipfs, path_or_cid)
    
    def create_ipfs_storage_context(self) -> Optional[Any]:
        """
        Create a LlamaIndex storage context backed by IPFS.
        
        Returns:
            Storage context instance or None if not available
        """
        if not LLAMA_INDEX_AVAILABLE:
            logger.error("Cannot create storage context: LlamaIndex not available")
            return None
            
        # This is a placeholder implementation - real implementation would
        # create a custom storage context using IPFS
        # Create a simulated implementation
        logger.info("Creating IPFS-backed storage context for LlamaIndex")
        return "IPFS-backed storage context placeholder"


class IPFSDataLoader:
    """
    IPFS-based data loader for ML frameworks.
    
    Provides efficient loading and prefetching of datasets from IPFS content storage,
    with seamless integration into popular machine learning frameworks.
    
    Features:
    - Batch loading with configurable batch size
    - Background prefetching for improved performance
    - Dataset shuffling for training
    - Iterator interface for Python compatibility
    - Framework-specific integrations (PyTorch, TensorFlow, etc.)
    """
    
    def __init__(self, ipfs_client, batch_size=32, shuffle=True, prefetch=2):
        """
        Initialize data loader for machine learning workloads.
        
        Args:
            ipfs_client: IPFS client for content access
            batch_size: Number of samples per batch
            shuffle: Whether to shuffle the dataset
            prefetch: Number of batches to prefetch
        """
        self.ipfs = ipfs_client
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.prefetch = prefetch
        
        # Dataset-related attributes
        self.dataset_cid = None
        self.dataset_metadata = None
        self.sample_cids = []
        self.total_samples = 0
        
        # Prefetching attributes
        self.prefetch_queue = queue.Queue(maxsize=prefetch)
        self.prefetch_threads = []
        self.stop_prefetch = threading.Event()
        
    def load_dataset(self, dataset_cid):
        """
        Load dataset metadata from IPFS.
        
        Args:
            dataset_cid: Content identifier for the dataset
            
        Returns:
            Boolean indicating success or failure
        """
        result = {
            "success": False,
            "operation": "load_dataset",
            "timestamp": time.time()
        }
        
        try:
            self.dataset_cid = dataset_cid
            
            # Fetch dataset metadata
            metadata_result = self.ipfs.dag_get(dataset_cid)
            
            if not metadata_result.get("success", False):
                raise ValueError(f"Failed to get dataset metadata: {metadata_result.get('error')}")
                
            self.dataset_metadata = metadata_result.get("object")
            
            # Extract sample CIDs
            if "samples" in self.dataset_metadata:
                self.sample_cids = self.dataset_metadata["samples"]
                self.total_samples = len(self.sample_cids)
                logger.info(f"Loaded dataset with {self.total_samples} samples")
            else:
                # Try different formats - dataset may be structured differently
                if "data" in self.dataset_metadata and isinstance(self.dataset_metadata["data"], list):
                    # Dataset contains embedded samples
                    self.sample_cids = None
                    self.embedded_samples = self.dataset_metadata["data"]
                    self.total_samples = len(self.embedded_samples)
                    logger.info(f"Loaded dataset with {self.total_samples} embedded samples")
                else:
                    raise ValueError("Dataset doesn't contain samples list or embedded data")
                    
            # Start prefetching
            self._start_prefetch()
            
            result["success"] = True
            result["total_samples"] = self.total_samples
            result["dataset_cid"] = dataset_cid
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Failed to load dataset {dataset_cid}: {e}")
            
            return result
            
    def _start_prefetch(self):
        """Start prefetching thread."""
        # Stop existing threads if any
        self.stop_prefetch.set()
        for thread in self.prefetch_threads:
            thread.join(timeout=1.0)  # Don't wait forever
            
        # Clear queue and reset stop event
        while not self.prefetch_queue.empty():
            try:
                self.prefetch_queue.get_nowait()
            except queue.Empty:
                break
                
        self.stop_prefetch.clear()
        
        # Start new prefetch thread
        thread = threading.Thread(target=self._prefetch_worker)
        thread.daemon = True
        thread.start()
        self.prefetch_threads = [thread]
        
        logger.debug(f"Started prefetching thread for dataset {self.dataset_cid}")
        
    def _prefetch_worker(self):
        """Prefetch worker that loads batches in background."""
        # Create sample indices
        indices = list(range(self.total_samples))
        
        # Main prefetch loop
        while not self.stop_prefetch.is_set():
            # Shuffle if needed
            if self.shuffle:
                random.shuffle(indices)
                
            # Process in batches
            for i in range(0, self.total_samples, self.batch_size):
                if self.stop_prefetch.is_set():
                    break
                    
                # Get batch indices
                batch_indices = indices[i:i+self.batch_size]
                
                # Load samples
                batch = self._load_batch(batch_indices)
                
                # Add to queue (with timeout to allow stopping)
                try:
                    self.prefetch_queue.put(batch, timeout=1.0)
                except queue.Full:
                    # Skip if queue is full
                    pass
                    
    def _load_batch(self, indices):
        """
        Load a batch of samples by indices.
        
        Args:
            indices: List of sample indices to load
            
        Returns:
            List of loaded samples
        """
        batch = []
        
        for idx in indices:
            if idx >= self.total_samples:
                continue
                
            if self.sample_cids:
                # Load from separate CIDs
                sample_cid = self.sample_cids[idx]
                
                try:
                    # Load sample from IPFS
                    sample_result = self.ipfs.dag_get(sample_cid)
                    
                    if sample_result.get("success", False):
                        sample = sample_result.get("object")
                        batch.append(sample)
                    else:
                        logger.warning(f"Failed to load sample {sample_cid}: {sample_result.get('error')}")
                        
                except Exception as e:
                    logger.warning(f"Error loading sample {sample_cid}: {e}")
            else:
                # Use embedded samples
                batch.append(self.embedded_samples[idx])
                
        return batch
        
    def __iter__(self):
        """Iterator interface for dataset."""
        # Reset if needed
        if self.prefetch_queue.empty() and not self.prefetch_threads:
            self._start_prefetch()
        return self
        
    def __next__(self):
        """Get next batch from dataset."""
        if self.total_samples == 0:
            raise StopIteration
            
        try:
            # Get batch from prefetch queue
            batch = self.prefetch_queue.get(timeout=10.0)
            return batch
        except queue.Empty:
            # If prefetch is too slow or exhausted
            raise StopIteration
            
    def __len__(self):
        """Number of batches in dataset."""
        return (self.total_samples + self.batch_size - 1) // self.batch_size
        
    def to_pytorch(self):
        """
        Convert to PyTorch DataLoader.
        
        Returns:
            PyTorch DataLoader or None if PyTorch not available
        """
        try:
            if not TORCH_AVAILABLE:
                raise ImportError("PyTorch not available")
            import torch
            from torch.utils.data import IterableDataset, DataLoader
            
            # Create wrapper class
            class IPFSIterableDataset(IterableDataset):
                def __init__(self, ipfs_loader):
                    self.ipfs_loader = ipfs_loader
                    
                def __iter__(self):
                    for batch in self.ipfs_loader:
                        for sample in batch:
                            # Convert to tensors based on sample format
                            if "features" in sample and "labels" in sample:
                                features = torch.tensor(sample["features"])
                                labels = torch.tensor(sample["labels"])
                                yield features, labels
                            else:
                                # Just return the whole sample as a dict
                                yield {k: torch.tensor(v) if isinstance(v, list) else v 
                                      for k, v in sample.items()}
                                
            # Create and return DataLoader
            dataset = IPFSIterableDataset(self)
            return DataLoader(
                dataset,
                batch_size=self.batch_size,
                num_workers=0  # Already using our own prefetching
            )
            
        except ImportError as e:
            logger.error(f"PyTorch integration not available: {e}")
            return None
            
    def to_tensorflow(self):
        """
        Convert to TensorFlow Dataset.
        
        Returns:
            TensorFlow Dataset or None if TensorFlow not available
        """
        try:
            if not TF_AVAILABLE:
                raise ImportError("TensorFlow not available")
                
            import tensorflow as tf
            
            def generator():
                for batch in self:
                    for sample in batch:
                        if "features" in sample and "labels" in sample:
                            yield (sample["features"], sample["labels"])
                        else:
                            yield sample
                            
            # Try to determine output shapes
            output_shapes = None
            output_types = None
            
            # Peek at first sample to infer types and shapes
            try:
                first_batch = next(iter(self))
                if first_batch:
                    first_sample = first_batch[0]
                    if "features" in first_sample and "labels" in first_sample:
                        # Supervised learning format
                        features_shape = tf.TensorShape([None] + list(np.array(first_sample["features"]).shape[1:]))
                        labels_shape = tf.TensorShape([None] + list(np.array(first_sample["labels"]).shape[1:]))
                        output_shapes = (features_shape, labels_shape)
                        
                        features_type = tf.float32  # Assume float features
                        labels_type = tf.float32 if isinstance(first_sample["labels"][0], float) else tf.int32
                        output_types = (features_type, labels_type)
            except (StopIteration, IndexError, KeyError):
                logger.debug("Could not automatically determine output shapes and types")
                
            # Create dataset
            dataset = tf.data.Dataset.from_generator(
                generator,
                output_types=output_types,
                output_shapes=output_shapes
            )
            
            # Apply batch sizing
            return dataset.batch(self.batch_size).prefetch(tf.data.experimental.AUTOTUNE)
            
        except ImportError as e:
            logger.error(f"TensorFlow integration not available: {e}")
            return None
            
    def close(self):
        """Clean up resources used by the data loader."""
        # Stop prefetching threads
        self.stop_prefetch.set()
        for thread in self.prefetch_threads:
            thread.join(timeout=1.0)
        self.prefetch_threads = []
        
        # Clear queue
        while not self.prefetch_queue.empty():
            try:
                self.prefetch_queue.get_nowait()
            except queue.Empty:
                break


class DistributedTraining:
    """
    Distributed training infrastructure leveraging IPFS cluster.
    
    Provides tools for distributed model training across worker nodes
    in the IPFS cluster, with model and dataset sharing, parallel
    training, and result aggregation.
    """
    
    def __init__(self, ipfs_client, cluster_manager=None):
        """
        Initialize the distributed training infrastructure.
        
        Args:
            ipfs_client: IPFS client instance
            cluster_manager: ClusterManager instance for task distribution
        """
        self.ipfs = ipfs_client
        self.cluster_manager = cluster_manager
        
        # Internal components
        self.model_registry = ModelRegistry(ipfs_client)
        self.dataset_manager = DatasetManager(ipfs_client)
        
        # Check ML framework availability
        self._check_ml_frameworks()
    
    def _check_ml_frameworks(self):
        """Check and log available ML frameworks."""
        frameworks = []
        if SKLEARN_AVAILABLE:
            frameworks.append(f"scikit-learn {sklearn.__version__}")
        if TORCH_AVAILABLE:
            frameworks.append(f"PyTorch {torch.__version__}")
        if TF_AVAILABLE:
            frameworks.append(f"TensorFlow {tf.__version__}")
            
        if frameworks:
            logger.info(f"DistributedTraining initialized with frameworks: {', '.join(frameworks)}")
        else:
            logger.warning("No ML frameworks detected. Limited training functionality available.")
            logger.info("For full functionality, install scikit-learn, PyTorch, or TensorFlow.")
    
    def prepare_distributed_task(self, model_name: str, dataset_name: str, 
                             training_config: Dict, num_workers: int = None) -> Dict:
        """
        Prepare a distributed training task to be executed across workers.
        
        Args:
            model_name: Name identifier for the model
            dataset_name: Name of the dataset to use for training
            training_config: Configuration for the training process
            num_workers: Number of workers to use (None means all available)
            
        Returns:
            Dict with task preparation information
        """
        result = {
            "success": False,
            "operation": "prepare_distributed_task",
            "timestamp": time.time()
        }
        
        try:
            # Verify cluster manager is available
            if self.cluster_manager is None:
                raise ValueError("Cluster manager is required for distributed training")
                
            # Verify dataset exists
            dataset_info = self.dataset_manager.registry.get("datasets", {}).get(dataset_name)
            if not dataset_info:
                raise ValueError(f"Dataset '{dataset_name}' not found in registry")
                
            # Get latest dataset version
            latest_version = sorted(dataset_info.keys())[-1]
            dataset_cid = dataset_info[latest_version]["cid"]
            
            # Check if model exists (for fine-tuning) or if we're training from scratch
            model_cid = None
            if model_name in self.model_registry.registry.get("models", {}):
                latest_model_version = sorted(self.model_registry.registry["models"][model_name].keys())[-1]
                model_cid = self.model_registry.registry["models"][model_name][latest_model_version]["cid"]
                
            # Create training task configuration
            task_config = {
                "operation": "distributed_training",
                "model_name": model_name,
                "dataset_name": dataset_name,
                "dataset_cid": dataset_cid,
                "model_cid": model_cid,  # May be None for new models
                "training_config": training_config,
                "created_at": time.time(),
                "task_id": str(uuid.uuid4())
            }
            
            # Store task configuration in IPFS
            config_result = self.ipfs.add_json(task_config)
            
            if not config_result.get("success", False):
                raise Exception(f"Failed to store task configuration: {config_result.get('error')}")
                
            task_config_cid = config_result.get("Hash") or config_result.get("cid")
            
            # Create cluster task for distribution
            # This will be distributed to worker nodes by the cluster manager
            if num_workers is None:
                # Get all active workers
                workers = self.cluster_manager.get_active_workers()
                num_workers = len(workers)
            else:
                # Use specified number of workers
                workers = self.cluster_manager.get_active_workers()[:num_workers]
                
            if not workers:
                raise ValueError("No active workers available for distributed training")
                
            # Schedule task for workers
            distribution_result = self.cluster_manager.create_task(
                task_type="distributed_training",
                parameters={
                    "task_config_cid": task_config_cid,
                    "model_name": model_name,
                    "dataset_name": dataset_name
                },
                worker_ids=[worker["id"] for worker in workers]
            )
            
            result.update({
                "success": True,
                "task_id": task_config["task_id"],
                "model_name": model_name,
                "dataset_name": dataset_name,
                "num_workers": num_workers,
                "task_config_cid": task_config_cid,
                "distribution_result": distribution_result
            })
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error preparing distributed task: {e}")
            
        return result
    
    def execute_training_task(self, task_config_cid: str, worker_id: str = None) -> Dict:
        """
        Execute a training task on a worker node.
        
        Args:
            task_config_cid: CID of the task configuration
            worker_id: ID of the worker executing the task
            
        Returns:
            Dict with training results
        """
        result = {
            "success": False,
            "operation": "execute_training_task",
            "timestamp": time.time(),
            "worker_id": worker_id
        }
        
        try:
            # Get task configuration from IPFS
            config_result = self.ipfs.cat(task_config_cid)
            
            if not config_result.get("success", False):
                raise Exception(f"Failed to get task configuration: {config_result.get('error')}")
                
            task_config = json.loads(config_result.get("content"))
            
            # Extract task parameters
            dataset_cid = task_config["dataset_cid"]
            model_cid = task_config.get("model_cid")  # May be None for new models
            training_config = task_config["training_config"]
            
            # Get the dataset
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Get dataset from IPFS
                dataset_result = self.ipfs.get(dataset_cid, tmp_dir)
                
                if not dataset_result.get("success", False):
                    raise Exception(f"Failed to get dataset: {dataset_result.get('error')}")
                    
                dataset_dir = os.path.join(tmp_dir, dataset_cid, "data")
                
                # Get model if it exists (for fine-tuning)
                model = None
                if model_cid:
                    model_result = self.ipfs.get(model_cid, tmp_dir)
                    
                    if not model_result.get("success", False):
                        raise Exception(f"Failed to get model: {model_result.get('error')}")
                        
                    model_dir = os.path.join(tmp_dir, model_cid)
                    
                    # Load model based on framework
                    framework = training_config.get("framework", "unknown")
                    
                    # Simplified implementation of model loading
                    # Real implementation would have proper model loading logic
                    logger.info(f"Loading model from {model_dir} using framework {framework}")
                    
                    # Placeholder for model loading
                    model = f"Loaded model from {model_cid}"
                
                # Train or fine-tune model
                # This is a simplified implementation
                # Real implementation would use proper training logic
                logger.info(f"Training model using dataset in {dataset_dir}")
                
                # Simulate training
                time.sleep(1)  # Simulated training time
                
                # Create a dummy trained model
                trained_model = f"Trained model for {task_config['model_name']}"
                
                # Save model to a new temporary directory
                output_dir = os.path.join(tmp_dir, "output")
                os.makedirs(output_dir, exist_ok=True)
                
                # Placeholder for model saving
                model_path = os.path.join(output_dir, "model.pkl")
                with open(model_path, 'wb') as f:
                    pickle.dump(trained_model, f)
                    
                # Create model metadata
                model_metadata = {
                    "name": task_config["model_name"],
                    "version": "1.0.0" if not model_cid else "1.1.0",  # Simple versioning
                    "framework": training_config.get("framework", "unknown"),
                    "trained_by": worker_id or "worker",
                    "training_config": training_config,
                    "dataset_cid": dataset_cid,
                    "parent_model_cid": model_cid,
                    "task_id": task_config["task_id"],
                    "performance_metrics": {
                        "accuracy": 0.95,  # Simulated metrics
                        "loss": 0.05
                    }
                }
                
                # Add to IPFS
                dir_result = self.ipfs.add_directory(output_dir)
                
                if not dir_result.get("success", False):
                    raise Exception(f"Failed to add model to IPFS: {dir_result.get('error')}")
                    
                model_cid = dir_result.get("Hash") or dir_result.get("cid")
                
                # Return result
                result.update({
                    "success": True,
                    "model_name": task_config["model_name"],
                    "model_cid": model_cid,
                    "task_id": task_config["task_id"],
                    "dataset_cid": dataset_cid,
                    "metrics": model_metadata["performance_metrics"]
                })
                
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error executing training task: {e}")
            
        return result
    
    def aggregate_training_results(self, task_id: str) -> Dict:
        """
        Aggregate results from multiple workers for a distributed training task.
        
        Args:
            task_id: ID of the distributed task
            
        Returns:
            Dict with aggregated results
        """
        result = {
            "success": False,
            "operation": "aggregate_training_results",
            "timestamp": time.time(),
            "task_id": task_id
        }
        
        try:
            # Verify cluster manager is available
            if self.cluster_manager is None:
                raise ValueError("Cluster manager is required for result aggregation")
                
            # Get task results from cluster manager
            task_results = self.cluster_manager.get_task_results(task_id)
            
            if not task_results or not task_results.get("results"):
                raise ValueError(f"No results found for task {task_id}")
                
            # Extract worker results
            worker_results = task_results.get("results", [])
            
            # Check if we have a valid result format
            if not all(["model_cid" in res for res in worker_results]):
                raise ValueError("Invalid result format from workers")
                
            # Extract model CIDs and metrics
            model_cids = [res["model_cid"] for res in worker_results]
            metrics = [res.get("metrics", {}) for res in worker_results]
            
            # Simple aggregation - pick the best model based on metrics
            # In a real implementation, this might do model averaging or other techniques
            best_idx = 0
            best_metric = metrics[0].get("accuracy", 0)
            
            for i, metric in enumerate(metrics[1:], 1):
                if metric.get("accuracy", 0) > best_metric:
                    best_idx = i
                    best_metric = metric.get("accuracy", 0)
            
            best_model_cid = model_cids[best_idx]
            model_name = worker_results[0]["model_name"]
            
            # Register the best model in the model registry
            model_registry_result = self._register_aggregate_model(
                model_name, 
                best_model_cid,
                {
                    "task_id": task_id,
                    "worker_results": worker_results,
                    "aggregation_method": "best_accuracy",
                    "selected_worker_idx": best_idx
                }
            )
            
            result.update({
                "success": True,
                "model_name": model_name,
                "best_model_cid": best_model_cid,
                "num_workers": len(worker_results),
                "worker_metrics": metrics,
                "registry_result": model_registry_result
            })
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error aggregating training results: {e}")
            
        return result
    
    def _register_aggregate_model(self, model_name: str, model_cid: str, metadata: Dict) -> Dict:
        """
        Register the aggregated model in the model registry.
        
        Args:
            model_name: Name of the model
            model_cid: CID of the selected model
            metadata: Additional metadata about the aggregation
            
        Returns:
            Dict with registration result
        """
        # Simplified implementation
        with self.model_registry._lock:
            if model_name not in self.model_registry.registry["models"]:
                self.model_registry.registry["models"][model_name] = {}
                
            versions = self.model_registry.registry["models"][model_name].keys()
            next_version = "1.0.0" if not versions else f"1.{int(sorted(versions)[-1].split('.')[-1]) + 1}.0"
            
            self.model_registry.registry["models"][model_name][next_version] = {
                "cid": model_cid,
                "framework": metadata.get("framework", "unknown"),
                "added_at": time.time(),
                "metadata": {
                    "aggregated": True,
                    "task_id": metadata["task_id"],
                    "num_workers": len(metadata["worker_results"]),
                    "aggregation_method": metadata["aggregation_method"]
                }
            }
            
            # Save updated registry
            registry_cid = self.model_registry._save_registry()
            
            return {
                "success": True,
                "model_name": model_name,
                "version": next_version,
                "cid": model_cid,
                "registry_cid": registry_cid
            }
