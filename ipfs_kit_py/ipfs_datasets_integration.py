"""
IPFS Datasets Integration Module

This module provides integration with ipfs_datasets_py for distributed dataset
manipulation services. It enables local-first and decentralized filesystem operations
with proper fallback support for CI/CD environments where the package may not be available.

Key Features:
1. Dataset storage and retrieval via IPFS
2. Content-addressed versioning
3. Distributed dataset loading
4. Filesystem metadata management (event logs, provenance logs)
5. Graceful degradation when ipfs_datasets_py is not available

Usage:
    from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager
    
    manager = get_ipfs_datasets_manager(enable=True)
    if manager.is_available():
        # Use distributed dataset features
        cid = manager.store_dataset(data, metadata)
    else:
        # Fall back to local operations
        pass
"""

import logging
import os
import sys
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import json
import datetime
import importlib.util
import csv
import hashlib
import tempfile
import threading
import uuid
from contextlib import contextmanager

try:
    import fcntl
except Exception:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

# Configure logging
logger = logging.getLogger(__name__)

# Try to import ipfs_datasets_py with fallback.
#
# NOTE: The published `ipfs_datasets_py` package does not necessarily expose a
# `DatasetManager` symbol. We treat the dependency as available if the package
# itself imports, and keep our own manager abstraction (`IPFSDatasetsManager`).
IPFS_DATASETS_AVAILABLE = False
IPFSDatasetManager = None
_ipfs_datasets_py = None

def _should_skip_datasets_import() -> bool:
    if os.environ.get("IPFS_KIT_FAST_INIT") == "1":
        return True
    if os.environ.get("IPFS_KIT_SKIP_DATASETS") == "1":
        return True
    # Historically, this module skipped importing `ipfs_datasets_py` under pytest
    # to keep optional dependencies from affecting unit test runs.
    #
    # For this repository, we *do* want tests to exercise the integration when
    # the dependency is present. If you need the old behavior, set:
    #   IPFS_KIT_SKIP_DATASETS_IN_PYTEST=1
    if os.environ.get("IPFS_KIT_SKIP_DATASETS_IN_PYTEST") == "1":
        pytest_env_markers = (
            "PYTEST_CURRENT_TEST",
            "PYTEST_ADDOPTS",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
            "PYTEST_VERSION",
            "PYTEST_XDIST_WORKER",
        )
        if any(os.environ.get(key) for key in pytest_env_markers):
            return True
    argv = sys.argv or []
    if any(flag in argv for flag in ("-h", "--help")):
        return True
    return False

def _ensure_ipfs_datasets_loaded() -> None:
    global IPFS_DATASETS_AVAILABLE, IPFSDatasetManager, _ipfs_datasets_py
    if _ipfs_datasets_py is not None or IPFS_DATASETS_AVAILABLE:
        return
    if _should_skip_datasets_import():
        IPFS_DATASETS_AVAILABLE = False
        return
    try:
        spec = importlib.util.find_spec("ipfs_datasets_py")
        if spec is None:
            IPFS_DATASETS_AVAILABLE = False
            IPFSDatasetManager = None
            logger.info("ipfs_datasets_py not available - using fallback implementations")
            return

        # Mark available without importing, to avoid heavy side effects at import time.
        IPFS_DATASETS_AVAILABLE = True
        IPFSDatasetManager = None
        _ipfs_datasets_py = None
        logger.info("ipfs_datasets_py is available for dataset operations")
    except Exception:
        IPFS_DATASETS_AVAILABLE = False
        IPFSDatasetManager = None
        logger.info("ipfs_datasets_py not available - using fallback implementations")


# Populate the availability flag at import time so that code paths that only
# read `IPFS_DATASETS_AVAILABLE` (without calling into the manager) still behave
# correctly in environments where `ipfs_datasets_py` is installed.
_ensure_ipfs_datasets_loaded()


class DatasetIPFSBackend:
    """
    Adapter class that bridges ipfs_kit_py's DatasetManager with ipfs_datasets_py.
    
    This class provides a unified interface for distributed dataset operations,
    handling IPFS storage, retrieval, and metadata management. When ipfs_datasets_py
    is not available, it provides mock implementations to ensure the system continues
    to function in a degraded mode.
    """
    
    def __init__(self, ipfs_client=None, base_path: str = "~/.ipfs_datasets", 
                 enable_distributed: bool = True):
        """
        Initialize the IPFS dataset backend.
        
        Args:
            ipfs_client: Optional IPFS client instance from ipfs_kit
            base_path: Base directory for local dataset storage
            enable_distributed: Enable distributed operations (requires ipfs_datasets_py)
        """
        _ensure_ipfs_datasets_loaded()
        self.ipfs_client = ipfs_client
        self.base_path = Path(os.path.expanduser(base_path))
        self.enable_distributed = enable_distributed and IPFS_DATASETS_AVAILABLE
        self.backend = None
        
        # Initialize backend if available
        if self.enable_distributed and IPFSDatasetManager:
            try:
                self.backend = IPFSDatasetManager(
                    ipfs_client=ipfs_client,
                    base_path=str(self.base_path)
                )
                logger.info(f"Initialized IPFS dataset backend at {self.base_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize IPFS dataset backend: {e}")
                self.backend = None
                self.enable_distributed = False
        
        # Ensure base path exists for local fallback
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _is_cid(identifier: str) -> bool:
        """
        Check if the identifier looks like an IPFS CID.
        
        Supports common CID formats:
        - CIDv0: Starts with 'Qm'
        - CIDv1: Starts with 'b' (base32), 'z' (base58btc), 'f' (base32), 'u' (base64url)
        
        Args:
            identifier: String to check
        
        Returns:
            True if identifier appears to be a CID
        """
        return identifier.startswith(('Qm', 'b', 'z', 'f', 'u'))
    
    def is_available(self) -> bool:
        """Check if distributed operations are available."""
        return self.enable_distributed and self.backend is not None
    
    def store_dataset(self, dataset_path: Union[str, Path], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Store a dataset in IPFS and return metadata including CID.
        
        Args:
            dataset_path: Path to the dataset file or directory
            metadata: Optional metadata to attach to the dataset
        
        Returns:
            Dictionary containing:
                - success: bool indicating if operation succeeded
                - cid: Content identifier (if distributed mode enabled)
                - local_path: Path to local storage
                - metadata: Associated metadata including provenance info
                - error: Error message if operation failed
        """
        try:
            dataset_path = Path(dataset_path)
            
            if not dataset_path.exists():
                return {
                    "success": False,
                    "error": f"Dataset file or directory does not exist: {dataset_path}"
                }
            
            # Add event log metadata
            if metadata is None:
                metadata = {}
            
            metadata["stored_at"] = datetime.datetime.now().isoformat()
            metadata["original_path"] = str(dataset_path)
            
            # Try distributed storage if available
            if self.is_available():
                try:
                    result = self.backend.store(
                        path=str(dataset_path),
                        metadata=metadata
                    )
                    logger.info(f"Stored dataset in IPFS with CID: {result.get('cid')}")
                    return {
                        "success": True,
                        "cid": result.get("cid"),
                        "local_path": str(dataset_path),
                        "metadata": metadata,
                        "distributed": True
                    }
                except Exception as e:
                    logger.warning(f"Distributed storage failed, falling back to local: {e}")
            
            # Fallback to local storage
            logger.info(f"Using local storage for dataset at {dataset_path}")
            return {
                "success": True,
                "local_path": str(dataset_path),
                "metadata": metadata,
                "distributed": False
            }
            
        except Exception as e:
            logger.error(f"Error storing dataset: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def load_dataset(self, identifier: str, target_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Load a dataset from IPFS using its CID or from local storage using a path.
        
        Args:
            identifier: CID for IPFS retrieval or path for local retrieval
            target_path: Optional target path for downloaded content
        
        Returns:
            Dictionary containing:
                - success: bool indicating if operation succeeded
                - path: Path where dataset is available
                - metadata: Associated metadata
                - error: Error message if operation failed
        """
        try:
            # Check if identifier looks like a CID
            is_cid = self._is_cid(identifier)
            
            if is_cid and self.is_available():
                try:
                    result = self.backend.load(
                        cid=identifier,
                        target_path=str(target_path) if target_path else None
                    )
                    logger.info(f"Loaded dataset from IPFS CID: {identifier}")
                    return {
                        "success": True,
                        "path": result.get("path"),
                        "metadata": result.get("metadata", {}),
                        "distributed": True
                    }
                except Exception as e:
                    logger.warning(f"Failed to load from IPFS: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to load from IPFS: {str(e)}"
                    }
            else:
                # Local path
                dataset_path = Path(identifier)
                if not dataset_path.exists():
                    return {
                        "success": False,
                        "error": f"Local dataset not found: {identifier}"
                    }
                
                logger.info(f"Loading dataset from local path: {dataset_path}")
                return {
                    "success": True,
                    "path": str(dataset_path),
                    "metadata": {},
                    "distributed": False
                }
                
        except Exception as e:
            logger.error(f"Error loading dataset: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def version_dataset(self, dataset_id: str, version: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new version of a dataset with provenance tracking.
        
        Args:
            dataset_id: Identifier for the dataset
            version: Version string (e.g., "1.0.0")
            metadata: Optional metadata including provenance info
        
        Returns:
            Dictionary with version information and CID if distributed
        """
        try:
            if metadata is None:
                metadata = {}
            
            # Add provenance metadata
            metadata["version"] = version
            metadata["versioned_at"] = datetime.datetime.now().isoformat()
            metadata["dataset_id"] = dataset_id
            
            if self.is_available():
                try:
                    result = self.backend.version(
                        dataset_id=dataset_id,
                        version=version,
                        metadata=metadata
                    )
                    logger.info(f"Created dataset version {version} with CID: {result.get('cid')}")
                    return {
                        "success": True,
                        "version": version,
                        "cid": result.get("cid"),
                        "metadata": metadata,
                        "distributed": True
                    }
                except Exception as e:
                    logger.warning(f"Distributed versioning failed: {e}")
            
            # Fallback: just return metadata
            logger.info(f"Created local dataset version {version}")
            return {
                "success": True,
                "version": version,
                "metadata": metadata,
                "distributed": False
            }
            
        except Exception as e:
            logger.error(f"Error versioning dataset: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_metadata(self, identifier: str) -> Dict[str, Any]:
        """
        Retrieve metadata for a dataset by CID or local path.
        
        Args:
            identifier: CID or local path of the dataset
        
        Returns:
            Dictionary containing metadata or error
        """
        try:
            is_cid = self._is_cid(identifier)
            
            if is_cid and self.is_available():
                try:
                    result = self.backend.get_metadata(cid=identifier)
                    return {
                        "success": True,
                        "metadata": result,
                        "distributed": True
                    }
                except Exception as e:
                    logger.warning(f"Failed to get metadata from IPFS: {e}")
            
            # Try local metadata file
            metadata_path = Path(identifier).with_suffix('.metadata.json')
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                return {
                    "success": True,
                    "metadata": metadata,
                    "distributed": False
                }
            
            return {
                "success": False,
                "error": "Metadata not found"
            }
            
        except Exception as e:
            logger.error(f"Error retrieving metadata: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class IPFSDatasetsManager:
    """
    High-level manager for IPFS datasets integration.
    
    This class provides a simplified interface for working with distributed datasets,
    handling both IPFS operations and local fallbacks automatically.
    """
    
    def __init__(self, ipfs_client=None, enable: bool = True):
        """
        Initialize the IPFS datasets manager.
        
        Args:
            ipfs_client: Optional IPFS client instance
            enable: Enable distributed operations (requires ipfs_datasets_py)
        """
        self.backend = DatasetIPFSBackend(
            ipfs_client=ipfs_client,
            enable_distributed=enable
        )
        self.event_log = []
        self.provenance_log = []
        self.metadata_index_path = self.backend.base_path / "metadata_index.json"
        self.metadata_index_lock_path = self.backend.base_path / "metadata_index.lock"
        self.metadata_index: Dict[str, Dict[str, Any]] = {}
        self._index_lock = threading.RLock()
        self._metrics: Dict[str, int] = {
            "index_refresh": 0,
            "index_remove": 0,
            "index_list": 0,
            "accelerate_enrichment": 0,
            "accelerate_cache_hits": 0,
            "index_errors": 0,
        }
        self._accelerate_module: Optional[Any] = None
        self._accelerate_checked = False
        self._accelerate_timeout_sec = float(os.environ.get("IPFS_KIT_ACCELERATE_TIMEOUT_SEC", "1.5"))
        self._accelerate_embedding_cache: Dict[str, Any] = {}
        self._accelerate_models_cache: Optional[Any] = None
        self._accelerate_embedding_cache_max = int(os.environ.get("IPFS_KIT_ACCELERATE_EMBED_CACHE_MAX", "256"))
        self._load_metadata_index()

    @contextmanager
    def _index_file_lock(self):
        """Acquire process-safe lock for metadata index operations."""
        self.metadata_index_lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_index_lock_path, "a+", encoding="utf-8") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            elif msvcrt is not None:
                # Windows fallback: lock first byte for exclusive access.
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                elif msvcrt is not None:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)

    def _read_index_from_disk_unlocked(self) -> Dict[str, Dict[str, Any]]:
        if not self.metadata_index_path.exists():
            return {}
        try:
            with open(self.metadata_index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            self._metrics["index_errors"] += 1
            logger.warning(f"Failed to parse metadata index; recovering to empty index: {e}")
        return {}

    def _write_index_to_disk_unlocked(self, data: Dict[str, Dict[str, Any]]) -> None:
        self.metadata_index_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self.metadata_index_path.parent),
            prefix="metadata_index_",
            suffix=".tmp",
            delete=False,
        ) as f:
            tmp_path = Path(f.name)
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, self.metadata_index_path)
    
    def is_available(self) -> bool:
        """Check if distributed dataset operations are available."""
        return self.backend.is_available()

    def _load_metadata_index(self) -> None:
        loaded: Dict[str, Dict[str, Any]] = {}
        try:
            with self._index_file_lock():
                loaded = self._read_index_from_disk_unlocked()
        except Exception as e:
            logger.warning(f"Failed to load metadata index: {e}")
            loaded = {}

        with self._index_lock:
            self.metadata_index = loaded

    def _save_metadata_index(self) -> None:
        try:
            with self._index_lock:
                snapshot = dict(self.metadata_index)
            with self._index_file_lock():
                self._write_index_to_disk_unlocked(snapshot)
        except Exception as e:
            self._metrics["index_errors"] += 1
            logger.warning(f"Failed to save metadata index: {e}")
            try:
                if "tmp_path" in locals() and tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    def _index_key(self, *, path: Optional[Union[str, Path]] = None, cid: Optional[str] = None) -> str:
        if cid:
            return f"cid:{cid}"
        if path is None:
            return "unknown"
        return f"path:{Path(path).expanduser().resolve()}"

    def _safe_file_hash(self, file_path: Path, max_bytes: int = 1024 * 1024) -> Optional[str]:
        try:
            h = hashlib.sha256()
            with open(file_path, "rb") as f:
                h.update(f.read(max_bytes))
            return h.hexdigest()
        except Exception:
            return None

    def _first_data_file(self, dataset_path: Path) -> Optional[Path]:
        if dataset_path.is_file():
            return dataset_path
        if not dataset_path.is_dir():
            return None
        candidates: List[Path] = []
        for ext in ("*.csv", "*.json", "*.jsonl", "*.parquet", "*.txt"):
            candidates.extend(sorted(dataset_path.rglob(ext)))
        return candidates[0] if candidates else None

    def _infer_schema(self, dataset_path: Path) -> Dict[str, Any]:
        data_file = self._first_data_file(dataset_path)
        if data_file is None:
            return {"fields": [], "source": "none"}

        suffix = data_file.suffix.lower()
        try:
            if suffix == ".csv":
                with open(data_file, "r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    fields = list(reader.fieldnames or [])
                return {"fields": fields, "source": "csv_header", "sample_file": str(data_file)}

            if suffix == ".json":
                with open(data_file, "r", encoding="utf-8") as f:
                    parsed = json.load(f)
                if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                    fields = sorted(list(parsed[0].keys()))
                    return {"fields": fields, "source": "json_array_object", "sample_file": str(data_file)}
                if isinstance(parsed, dict):
                    fields = sorted(list(parsed.keys()))
                    return {"fields": fields, "source": "json_object", "sample_file": str(data_file)}

            if suffix == ".jsonl":
                with open(data_file, "r", encoding="utf-8") as f:
                    first = f.readline().strip()
                if first:
                    parsed = json.loads(first)
                    if isinstance(parsed, dict):
                        return {
                            "fields": sorted(list(parsed.keys())),
                            "source": "jsonl_first_row",
                            "sample_file": str(data_file),
                        }

            # Keep parquet lightweight here: avoid hard dependency on pandas/pyarrow.
            if suffix == ".parquet":
                return {"fields": [], "source": "parquet_unparsed", "sample_file": str(data_file)}

            return {"fields": [], "source": "unstructured", "sample_file": str(data_file)}
        except Exception:
            return {"fields": [], "source": "inference_error", "sample_file": str(data_file)}

    def _infer_splits(self, dataset_path: Path) -> List[str]:
        split_tokens = {"train", "test", "validation", "val", "dev"}
        found: List[str] = []

        for part in dataset_path.parts:
            p = part.lower()
            if p in split_tokens and p not in found:
                found.append(p)

        if dataset_path.is_dir():
            try:
                for child in dataset_path.iterdir():
                    name = child.name.lower()
                    if name in split_tokens and name not in found:
                        found.append(name)
            except Exception:
                pass

        return found

    def _infer_provenance(self, dataset_path: Path, cid: Optional[str] = None) -> Dict[str, Any]:
        provenance: Dict[str, Any] = {
            "source_path": str(dataset_path),
            "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        if cid:
            provenance["cid"] = cid

        try:
            stat = dataset_path.stat()
            provenance["size_bytes"] = stat.st_size
            provenance["mtime"] = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).isoformat()
        except Exception:
            pass

        data_file = self._first_data_file(dataset_path)
        if data_file is not None:
            file_hash = self._safe_file_hash(data_file)
            if file_hash:
                provenance["sample_file_sha256"] = file_hash
                provenance["sample_file"] = str(data_file)

        return provenance

    def _get_accelerate_module(self) -> Optional[Any]:
        if self._accelerate_checked:
            return self._accelerate_module
        self._accelerate_checked = True
        try:
            from ipfs_kit_py import get_ipfs_accelerate

            self._accelerate_module = get_ipfs_accelerate()
        except Exception:
            self._accelerate_module = None
        return self._accelerate_module

    def _call_with_timeout(self, func: Any, *args: Any) -> Tuple[bool, Any]:
        done = threading.Event()
        state: Dict[str, Any] = {}

        def _runner() -> None:
            try:
                state["result"] = func(*args)
            except Exception as exc:
                state["error"] = exc
            finally:
                done.set()

        worker = threading.Thread(target=_runner, daemon=True)
        worker.start()

        if not done.wait(self._accelerate_timeout_sec):
            return True, None

        if "error" in state:
            raise state["error"]
        return False, state.get("result")

    def _accelerate_enrich_index(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        accelerate = self._get_accelerate_module()
        if accelerate is None:
            return {"attempted": False, "reason": "accelerate_unavailable"}

        try:
            enrichment: Dict[str, Any] = {}

            if hasattr(accelerate, "discover_embedding_models") and callable(accelerate.discover_embedding_models):
                if self._accelerate_models_cache is not None:
                    models = self._accelerate_models_cache
                    self._metrics["accelerate_cache_hits"] += 1
                else:
                    timed_out, models = self._call_with_timeout(accelerate.discover_embedding_models)
                    if timed_out:
                        return {
                            "attempted": True,
                            "success": False,
                            "reason": "accelerate_timeout",
                            "mode": "discover_embedding_models",
                            "timeout_seconds": self._accelerate_timeout_sec,
                        }
                    self._accelerate_models_cache = models
                enrichment["discovered_models"] = models
            elif hasattr(accelerate, "search_models") and callable(accelerate.search_models):
                if self._accelerate_models_cache is not None:
                    models = self._accelerate_models_cache
                    self._metrics["accelerate_cache_hits"] += 1
                else:
                    timed_out, models = self._call_with_timeout(accelerate.search_models, "embedding")
                    if timed_out:
                        return {
                            "attempted": True,
                            "success": False,
                            "reason": "accelerate_timeout",
                            "mode": "search_models",
                            "timeout_seconds": self._accelerate_timeout_sec,
                        }
                    self._accelerate_models_cache = models
                enrichment["discovered_models"] = models

            embed_text = entry.get("dataset_summary") or entry.get("path")
            if hasattr(accelerate, "create_embedding") and callable(accelerate.create_embedding) and embed_text:
                cache_key = hashlib.sha256(str(embed_text).encode("utf-8")).hexdigest()
                if cache_key in self._accelerate_embedding_cache:
                    vector = self._accelerate_embedding_cache[cache_key]
                    self._metrics["accelerate_cache_hits"] += 1
                    enrichment["embedding_cache_hit"] = True
                else:
                    timed_out, vector = self._call_with_timeout(accelerate.create_embedding, str(embed_text))
                    if timed_out:
                        return {
                            "attempted": True,
                            "success": False,
                            "reason": "accelerate_timeout",
                            "mode": "create_embedding",
                            "timeout_seconds": self._accelerate_timeout_sec,
                        }
                    if len(self._accelerate_embedding_cache) >= self._accelerate_embedding_cache_max:
                        # Pop first inserted item to keep cache bounded.
                        oldest_key = next(iter(self._accelerate_embedding_cache.keys()))
                        self._accelerate_embedding_cache.pop(oldest_key, None)
                    self._accelerate_embedding_cache[cache_key] = vector
                if isinstance(vector, list):
                    enrichment["embedding_dim"] = len(vector)
                enrichment["embedding_preview"] = vector[:8] if isinstance(vector, list) else None

            if enrichment:
                entry["accelerate"] = enrichment
                self._metrics["accelerate_enrichment"] += 1
                return {"attempted": True, "success": True}
            return {"attempted": True, "success": False, "reason": "no_supported_capabilities"}
        except Exception as e:
            self._metrics["index_errors"] += 1
            return {"attempted": True, "success": False, "reason": str(e)}

    def _build_index_entry(
        self,
        *,
        path: Optional[Union[str, Path]],
        cid: Optional[str],
        operation: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = dict(metadata or {})
        operation_id = str(metadata.get("operation_id") or f"idxop-{uuid.uuid4().hex}")
        source_operation_id = metadata.get("source_operation_id")
        source_cid = metadata.get("source_cid")
        dataset_path = Path(path).expanduser() if path else None
        inferred_schema: Dict[str, Any] = {"fields": [], "source": "none"}
        inferred_splits: List[str] = []
        inferred_provenance: Dict[str, Any] = {}

        if dataset_path and dataset_path.exists():
            inferred_schema = self._infer_schema(dataset_path)
            inferred_splits = self._infer_splits(dataset_path)
            inferred_provenance = self._infer_provenance(dataset_path, cid=cid)

        entry = {
            "schema_version": "2",
            "id": self._index_key(path=path, cid=cid),
            "path": str(dataset_path) if dataset_path else metadata.get("path"),
            "cid": cid,
            "operation": operation,
            "operation_id": operation_id,
            "source_operation_id": source_operation_id,
            "source_cid": source_cid,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "schema": inferred_schema,
            "splits": inferred_splits,
            "provenance": inferred_provenance,
            "metadata": metadata,
            "lineage": {
                "schema_version": "2",
                "operation_id": operation_id,
                "source_operation_id": source_operation_id,
                "cid": cid,
                "source_cid": source_cid,
            },
            "dataset_summary": metadata.get("dataset_summary") or metadata.get("description"),
        }
        accelerate_status = self._accelerate_enrich_index(entry)
        if isinstance(accelerate_status, dict):
            entry["accelerate_status"] = accelerate_status
        return entry

    def refresh_metadata_index(
        self,
        *,
        path: Optional[Union[str, Path]] = None,
        cid: Optional[str] = None,
        operation: str = "refresh",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            entry = self._build_index_entry(path=path, cid=cid, operation=operation, metadata=metadata)
            with self._index_file_lock():
                disk_index = self._read_index_from_disk_unlocked()
                disk_index[entry["id"]] = entry
                self._write_index_to_disk_unlocked(disk_index)
                with self._index_lock:
                    self.metadata_index = dict(disk_index)
            self._metrics["index_refresh"] += 1
            return {"success": True, "entry": entry}
        except Exception as e:
            self._metrics["index_errors"] += 1
            return {"success": False, "error": str(e)}

    def update_metadata_index(self, *, path: Optional[Union[str, Path]] = None, operation: str = "update", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Compatibility alias used by existing wrappers."""
        return self.refresh_metadata_index(path=path, operation=operation, metadata=metadata)

    def record_ipfs_operation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Compatibility hook for VFS and bridge notifiers."""
        operation = str(payload.get("operation") or "operation")
        path = payload.get("path")
        cid = payload.get("cid")

        if operation in {"remove", "delete", "rmdir", "unmount"}:
            return self.remove_from_metadata_index(path=path, cid=cid)

        return self.refresh_metadata_index(path=path, cid=cid, operation=operation, metadata=payload)

    def remove_from_metadata_index(
        self,
        *,
        path: Optional[Union[str, Path]] = None,
        cid: Optional[str] = None,
    ) -> Dict[str, Any]:
        key = self._index_key(path=path, cid=cid)
        removed = None
        with self._index_file_lock():
            disk_index = self._read_index_from_disk_unlocked()
            removed = disk_index.pop(key, None)
            self._write_index_to_disk_unlocked(disk_index)
            with self._index_lock:
                self.metadata_index = dict(disk_index)
        self._metrics["index_remove"] += 1
        return {
            "success": True,
            "removed": removed is not None,
            "id": key,
            "removed_entry": removed,
            "removed_operation_id": removed.get("operation_id") if isinstance(removed, dict) else None,
        }

    def list_metadata_index(self) -> Dict[str, Any]:
        self._metrics["index_list"] += 1
        with self._index_lock:
            ordered_items = [self.metadata_index[k] for k in sorted(self.metadata_index.keys())]
        return {
            "success": True,
            "count": len(ordered_items),
            "items": ordered_items,
        }

    def metadata_index_snapshot(self) -> Dict[str, Any]:
        with self._index_lock:
            count = len(self.metadata_index)
        return {
            "count": count,
            "metrics": dict(self._metrics),
        }
    
    def store(self, path: Union[str, Path], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store a dataset with event logging."""
        result = self.backend.store_dataset(path, metadata)
        
        # Log the event
        self.event_log.append({
            "operation": "store",
            "path": str(path),
            "timestamp": datetime.datetime.now().isoformat(),
            "success": result.get("success", False),
            "cid": result.get("cid")
        })

        if result.get("success"):
            self.refresh_metadata_index(
                path=path,
                cid=result.get("cid"),
                operation="store",
                metadata=result.get("metadata") if isinstance(result.get("metadata"), dict) else {},
            )
        
        return result
    
    def load(self, identifier: str, target_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Load a dataset with event logging."""
        result = self.backend.load_dataset(identifier, target_path)
        
        # Log the event
        self.event_log.append({
            "operation": "load",
            "identifier": identifier,
            "timestamp": datetime.datetime.now().isoformat(),
            "success": result.get("success", False)
        })

        if result.get("success"):
            # Refresh index for the resolved local path when available, otherwise identifier.
            resolved_path = result.get("path") or identifier
            self.refresh_metadata_index(
                path=resolved_path,
                operation="load",
                metadata=result.get("metadata") if isinstance(result.get("metadata"), dict) else {},
            )
        
        return result
    
    def version(self, dataset_id: str, version: str, 
                parent_version: Optional[str] = None,
                transformations: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create a versioned dataset with provenance tracking.
        
        Args:
            dataset_id: Dataset identifier
            version: New version string
            parent_version: Optional parent version for lineage tracking
            transformations: Optional list of transformations applied
        
        Returns:
            Result dictionary with version info
        """
        metadata = {
            "provenance": {
                "parent_version": parent_version,
                "transformations": transformations or []
            }
        }
        
        result = self.backend.version_dataset(dataset_id, version, metadata)
        
        # Log provenance
        self.provenance_log.append({
            "dataset_id": dataset_id,
            "version": version,
            "parent_version": parent_version,
            "transformations": transformations or [],
            "timestamp": datetime.datetime.now().isoformat(),
            "cid": result.get("cid")
        })

        if result.get("success"):
            self.refresh_metadata_index(
                path=dataset_id,
                cid=result.get("cid"),
                operation="version",
                metadata=metadata,
            )
        
        return result

    def remove(self, identifier: str) -> Dict[str, Any]:
        """Remove dataset metadata index entry by CID or path."""
        result = self.remove_from_metadata_index(path=identifier, cid=identifier if self.backend._is_cid(identifier) else None)
        self.event_log.append({
            "operation": "remove",
            "identifier": identifier,
            "timestamp": datetime.datetime.now().isoformat(),
            "success": result.get("success", False),
        })
        return result

    def list(self) -> Dict[str, Any]:
        """List datasets from metadata index."""
        result = self.list_metadata_index()
        self.event_log.append({
            "operation": "list",
            "timestamp": datetime.datetime.now().isoformat(),
            "success": result.get("success", False),
            "count": result.get("count", 0),
        })
        return result
    
    def get_event_log(self) -> List[Dict[str, Any]]:
        """Get the event log for all dataset operations."""
        return self.event_log.copy()
    
    def get_provenance_log(self) -> List[Dict[str, Any]]:
        """Get the provenance log showing dataset lineage."""
        return self.provenance_log.copy()


# Singleton instance for easy access
_manager_instance: Optional[IPFSDatasetsManager] = None


def get_ipfs_datasets_manager(ipfs_client=None, enable: bool = True) -> IPFSDatasetsManager:
    """
    Get or create the singleton IPFS datasets manager instance.
    
    Args:
        ipfs_client: Optional IPFS client instance
        enable: Enable distributed operations
    
    Returns:
        IPFSDatasetsManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = IPFSDatasetsManager(ipfs_client=ipfs_client, enable=enable)
    return _manager_instance


def reset_manager():
    """Reset the singleton manager instance (useful for testing)."""
    global _manager_instance
    _manager_instance = None
