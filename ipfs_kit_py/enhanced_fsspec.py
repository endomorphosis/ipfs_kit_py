"""
Enhanced FSSpec implementation with multiple storage backend support.

This module extends the IPFS FSSpec interface to support multiple storage backends
including IPFS, Filecoin (via Lotus), Storacha, and Synapse SDK.
"""

import os
import io
import time
import hashlib
import logging
import anyio
import sniffio
import tempfile
import threading
from functools import partial
from typing import Dict, List, Any, Optional, Union, BinaryIO
from pathlib import Path

# Import fsspec
import fsspec
from fsspec.spec import AbstractFileSystem
from fsspec.callbacks import DEFAULT_CALLBACK

logger = logging.getLogger(__name__)


class _InMemoryStorachaClient:
    """Small Storacha-compatible client for credential-free fsspec mock mode."""

    mock_mode = True
    api_url = "mock://storacha"
    space = "mock-space"

    def __init__(self) -> None:
        self._objects: Dict[str, Dict[str, Any]] = {}

    def w3_up(self, file_path: str, **kwargs) -> Dict[str, Any]:
        with open(file_path, "rb") as f:
            data = f.read()
        digest = hashlib.sha256(data).hexdigest()
        cid = f"bafy{digest[:56]}"
        filename = kwargs.get("filename") or os.path.basename(file_path)
        self._objects[cid] = {
            "cid": cid,
            "name": filename,
            "filename": filename,
            "size": len(data),
            "content": data,
            "created": time.time(),
            "mock": True,
        }
        return {
            "success": True,
            "cid": cid,
            "filename": filename,
            "size": len(data),
            "mock": True,
        }

    def w3_cat(self, cid: str, **kwargs) -> Dict[str, Any]:
        if cid not in self._objects:
            return {"success": False, "cid": cid, "error": "Storacha mock object not found"}
        obj = self._objects[cid]
        return {
            "success": True,
            "cid": cid,
            "content": obj["content"],
            "size": obj["size"],
            "mock": True,
        }

    def w3_list(self, **kwargs) -> Dict[str, Any]:
        uploads = [
            {key: value for key, value in obj.items() if key != "content"}
            for obj in self._objects.values()
        ]
        return {"success": True, "uploads": uploads, "count": len(uploads), "mock": True}

    def w3_remove(self, cid: str, **kwargs) -> Dict[str, Any]:
        self._objects.pop(cid, None)
        return {"success": True, "cid": cid, "removed": True, "mock": True}


def _run_async_from_sync(async_fn, *args, **kwargs):
    """Run an async callable from sync code.

    - If called from an AnyIO worker thread, uses `anyio.from_thread.run`.
    - If called from plain sync code, uses `anyio.run`.
    - If called while an async library is running in this thread, runs the
      call in a dedicated helper thread.
    """
    call = partial(async_fn, *args, **kwargs)

    try:
        return anyio.from_thread.run(call)
    except RuntimeError:
        pass

    try:
        sniffio.current_async_library()
    except sniffio.AsyncLibraryNotFoundError:
        return anyio.run(call)

    result: List[Any] = []
    error: List[BaseException] = []

    def _thread_main() -> None:
        try:
            result.append(anyio.run(call))
        except BaseException as exc:  # noqa: BLE001
            error.append(exc)

    t = threading.Thread(target=_thread_main, daemon=True)
    t.start()
    t.join()
    if error:
        raise error[0]
    return result[0] if result else None


class IPFSFileSystem(AbstractFileSystem):
    """
    Enhanced FSSpec-compatible filesystem supporting multiple storage backends.
    
    Supported backends:
    - ipfs: Direct IPFS client
    - filecoin: Filecoin storage via Lotus
    - storacha: Storacha Web3 storage  
    - synapse: Synapse SDK with PDP verification
    """
    
    protocol = ["ipfs", "filecoin", "storacha", "synapse"]
    default_backend = "ipfs"
    
    def __init__(
        self,
        backend: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        resources: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize the multi-backend filesystem.
        
        Args:
            backend: Storage backend to use ('ipfs', 'filecoin', 'storacha', 'synapse')
            metadata: Backend configuration metadata
            resources: Shared resources dictionary
            **kwargs: Additional arguments for specific backends
        """
        super().__init__(**kwargs)
        
        self.backend = backend or self.default_backend
        self.metadata = metadata or {}
        self.resources = resources or {}
        self._synapse_path_index: Dict[str, Dict[str, Any]] = {}
        self._storacha_path_index: Dict[str, Dict[str, Any]] = {}
        self._storacha_data_index: Dict[str, bytes] = {}
        
        # Initialize backend-specific storage interface
        self._initialize_backend()
        
        logger.info(f"Initialized IPFSFileSystem with {backend} backend")
    
    def _initialize_backend(self):
        """Initialize the specified storage backend."""
        
        if self.backend == "ipfs":
            self._initialize_ipfs_backend()
        elif self.backend == "filecoin":
            self._initialize_filecoin_backend()
        elif self.backend == "storacha":
            self._initialize_storacha_backend()
        elif self.backend == "synapse":
            self._initialize_synapse_backend()
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")
    
    def _initialize_ipfs_backend(self):
        """Initialize IPFS backend."""
        try:
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            
            self.ipfs_client = ipfs_kit(
                resources=self.resources,
                metadata=self.metadata
            )
            logger.info("✓ IPFS backend initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize IPFS backend: {e}")
            raise
    
    def _initialize_filecoin_backend(self):
        """Initialize Filecoin backend."""
        try:
            from ipfs_kit_py.lotus_kit import lotus_kit
            
            self.filecoin_client = lotus_kit(
                resources=self.resources,
                metadata=self.metadata
            )
            logger.info("✓ Filecoin backend initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize Filecoin backend: {e}")
            raise
    
    def _initialize_storacha_backend(self):
        """Initialize Storacha backend."""
        try:
            metadata = dict(self.metadata)
            api_key = metadata.get("api_key") or os.environ.get("STORACHA_API_KEY")
            if not api_key and not metadata.get("require_live", False):
                self.storacha_client = _InMemoryStorachaClient()
                self.storacha_mock_mode = True
                logger.info("✓ Storacha backend initialized in mock mode")
                return
            metadata.setdefault("skip_dependency_check", True)

            from ipfs_kit_py.storacha_kit import storacha_kit

            self.storacha_client = storacha_kit(
                resources=self.resources,
                metadata=metadata
            )
            self.storacha_mock_mode = bool(
                getattr(self.storacha_client, "mock_mode", False)
                or metadata.get("force_mock")
                or metadata.get("mock_mode")
            )
            logger.info("✓ Storacha backend initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize Storacha backend: {e}")
            raise
    
    def _initialize_synapse_backend(self):
        """Initialize Synapse SDK backend."""
        try:
            from ipfs_kit_py.synapse_storage import synapse_storage
            
            self.synapse_storage = synapse_storage(
                resources=self.resources,
                metadata=self.metadata
            )
            logger.info("✓ Synapse SDK backend initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize Synapse backend: {e}")
            raise
    
    @classmethod
    def _protocols(cls) -> List[str]:
        """Return supported protocols as a list."""
        protocol = cls.protocol
        if isinstance(protocol, str):
            return [protocol]
        return list(protocol)

    def _strip_protocol(self, path: str) -> str:
        """Remove protocol prefix from path."""
        for protocol in self._protocols():
            prefix = f"{protocol}://"
            if path.startswith(prefix):
                return path[len(prefix):]
        return path
    
    def _ensure_protocol(self, path: str) -> str:
        """Ensure path has correct protocol prefix."""
        if not any(path.startswith(f"{p}://") for p in self._protocols()):
            return f"{self.backend}://{path}"
        return path

    def _normalize_synapse_path(self, path: str) -> str:
        """Normalize a Synapse path or CommP to the synapse:// namespace."""
        stripped = self._strip_protocol(str(path)).lstrip("/")
        return f"synapse://{stripped}"

    def _synapse_identifier(self, path: str) -> str:
        """Resolve fsspec write aliases to their stored Synapse CommP."""
        normalized = self._normalize_synapse_path(path)
        indexed = self._synapse_path_index.get(normalized)
        if indexed and indexed.get("commp"):
            return indexed["commp"]
        return self._strip_protocol(str(path)).lstrip("/")

    def _synapse_store_result_to_info(
        self,
        result: Dict[str, Any],
        *,
        alias: Optional[str] = None,
        fallback_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert Synapse storage/status dictionaries to fsspec info."""
        commp = result.get("commp") or self._strip_protocol(fallback_name or "")
        canonical = self._normalize_synapse_path(commp) if commp else self._normalize_synapse_path(fallback_name or "")
        provider = (
            result.get("storage_provider")
            or result.get("provider")
            or result.get("provider_address")
            or result.get("current_storage_provider")
        )
        info = {
            "name": canonical,
            "type": "file",
            "size": result.get("size", result.get("data_size", 0)) or 0,
            "commp": commp,
            "exists": result.get("exists", result.get("success", True)),
            "provider": provider,
            "storage_provider": provider,
            "proof_set_id": result.get("proof_set_id"),
            "proof_set_last_proven": result.get("proof_set_last_proven"),
            "proof_set_next_proof_due": result.get("proof_set_next_proof_due"),
            "in_challenge_window": result.get("in_challenge_window", False),
        }
        filename = result.get("filename")
        if filename:
            info["filename"] = filename
        if alias and alias != canonical:
            info["alias"] = alias
        return info

    def _record_synapse_write(self, requested_path: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Remember the CommP returned for a path written through this filesystem."""
        if not result.get("success", False):
            raise IOError(f"Failed to upload to Synapse: {result.get('error', 'Unknown error')}")
        alias = self._normalize_synapse_path(requested_path)
        info = self._synapse_store_result_to_info(result, alias=alias, fallback_name=requested_path)
        self._synapse_path_index[alias] = info
        if info.get("commp"):
            self._synapse_path_index[self._normalize_synapse_path(info["commp"])] = info
        return info

    def _normalize_storacha_path(self, path: str) -> str:
        """Normalize a Storacha path or CID to the storacha:// namespace."""
        stripped = self._strip_protocol(str(path)).lstrip("/")
        return f"storacha://{stripped}"

    def _storacha_identifier(self, path: str) -> str:
        """Resolve fsspec write aliases to their stored Storacha CID."""
        normalized = self._normalize_storacha_path(path)
        indexed = self._storacha_path_index.get(normalized)
        if indexed and indexed.get("cid"):
            return indexed["cid"]
        return self._strip_protocol(str(path)).lstrip("/")

    def _storacha_result_to_info(
        self,
        result: Dict[str, Any],
        *,
        alias: Optional[str] = None,
        fallback_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert Storacha upload/list dictionaries to fsspec info."""
        cid = (
            result.get("cid")
            or result.get("root")
            or result.get("root_cid")
            or self._strip_protocol(fallback_name or "")
        )
        canonical = self._normalize_storacha_path(cid) if cid else self._normalize_storacha_path(fallback_name or "")
        size = (
            result.get("size")
            or result.get("size_bytes")
            or result.get("bytes")
            or result.get("content_length")
            or 0
        )
        info = {
            "name": canonical,
            "type": "file",
            "size": size,
            "cid": cid,
            "exists": result.get("exists", result.get("success", True)),
            "mock": bool(result.get("mock", getattr(self, "storacha_mock_mode", False))),
            "backend": "storacha",
        }
        filename = result.get("filename") or result.get("name") or result.get("file_name")
        if filename:
            info["filename"] = filename
        content_type = result.get("type") or result.get("content_type")
        if content_type:
            info["content_type"] = content_type
        created = result.get("created") or result.get("created_at") or result.get("updated_at")
        if created:
            info["created"] = created
        if alias and alias != canonical:
            info["alias"] = alias
        return info

    def _record_storacha_write(
        self,
        requested_path: str,
        result: Dict[str, Any],
        data: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Remember the CID returned for a Storacha path written through this filesystem."""
        if not result.get("success", False):
            raise IOError(f"Failed to upload to Storacha: {result.get('error', 'Unknown error')}")
        alias = self._normalize_storacha_path(requested_path)
        info = self._storacha_result_to_info(result, alias=alias, fallback_name=requested_path)
        self._storacha_path_index[alias] = info
        if info.get("cid"):
            canonical = self._normalize_storacha_path(info["cid"])
            self._storacha_path_index[canonical] = info
            if data is not None:
                self._storacha_data_index[canonical] = bytes(data)
        if data is not None:
            self._storacha_data_index[alias] = bytes(data)
        return info
    
    # Core FSSpec methods
    
    def ls(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """List directory contents."""
        
        if self.backend == "synapse":
            # For Synapse, list stored data
            return self._ls_synapse(path, detail, **kwargs)
        
        elif self.backend == "ipfs":
            return self._ls_ipfs(path, detail, **kwargs)
        
        elif self.backend == "filecoin":
            return self._ls_filecoin(path, detail, **kwargs)
        
        elif self.backend == "storacha":
            return self._ls_storacha(path, detail, **kwargs)
        
        else:
            raise NotImplementedError(f"ls not implemented for {self.backend}")
    
    def _ls_synapse(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """List Synapse stored data."""
        try:
            result = _run_async_from_sync(self.synapse_storage.synapse_list_stored_data, **kwargs)
            
            if not result.get("success", False):
                raise IOError(f"Failed to list Synapse data: {result.get('error', 'Unknown error')}")
            
            items = []
            for item in result.get("items", []):
                commp = item.get("commp", "")
                name = self._normalize_synapse_path(commp)
                
                if detail:
                    info = self._synapse_store_result_to_info(item, fallback_name=commp)
                    info["stored_at"] = item.get("stored_at", "")
                    info["path"] = name
                    items.append(info)
                else:
                    items.append(name)

            known_names = {item["name"] for item in items if detail}
            known_plain = set(items if not detail else [])
            for alias, info in self._synapse_path_index.items():
                if detail:
                    if info["name"] not in known_names and alias not in known_names:
                        indexed_info = dict(info)
                        indexed_info["path"] = indexed_info["name"]
                        items.append(indexed_info)
                        known_names.add(indexed_info["name"])
                        if indexed_info.get("alias"):
                            known_names.add(indexed_info["alias"])
                elif info["name"] not in known_plain:
                    items.append(info["name"])
                    known_plain.add(info["name"])
            
            return items
            
        except Exception as e:
            logger.error(f"Error listing Synapse data: {e}")
            raise
    
    def _ls_ipfs(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """List IPFS directory contents."""
        stripped_path = self._strip_protocol(path)
        
        try:
            result = self.ipfs_client.ipfs_ls_path(stripped_path)
            
            if not result.get("success", False):
                logger.error(f"Failed to list IPFS path {path}: {result.get('error', 'Unknown error')}")
                return []
            
            items = []
            for item in result.get("items", []):
                name = item.get("name", "")
                cid = item.get("hash", "")
                size = item.get("size", 0)
                item_type = "directory" if item.get("type") == 1 else "file"
                
                if detail:
                    items.append({
                        "name": name,
                        "size": size,
                        "type": item_type,
                        "cid": cid,
                        "path": f"ipfs://{cid}"
                    })
                else:
                    items.append(name)
            
            return items
            
        except Exception as e:
            logger.error(f"Error listing IPFS path: {e}")
            return []
    
    def _ls_filecoin(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """List Filecoin storage contents."""
        # Implement Filecoin-specific listing
        logger.warning("Filecoin ls not yet implemented")
        return []
    
    def _ls_storacha(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """List Storacha storage contents."""
        try:
            items: List[Union[Dict[str, Any], str]] = []
            seen = set()

            result = self.storacha_client.w3_list(**kwargs)
            if not result.get("success", False):
                raise IOError(f"Failed to list Storacha uploads: {result.get('error', 'Unknown error')}")

            for upload in result.get("uploads", result.get("items", [])):
                info = self._storacha_result_to_info(upload)
                key = info["name"]
                seen.add(key)
                if detail:
                    info["path"] = key
                    items.append(info)
                else:
                    items.append(key)

            for info in self._storacha_path_index.values():
                key = info["name"]
                alias = info.get("alias")
                if key in seen or alias in seen:
                    continue
                seen.add(key)
                indexed_info = dict(info)
                if detail:
                    indexed_info["path"] = indexed_info["name"]
                    items.append(indexed_info)
                else:
                    items.append(indexed_info["name"])

            return items
        except Exception as e:
            logger.error(f"Error listing Storacha data: {e}")
            raise
    
    def cat_file(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file contents."""
        
        if self.backend == "synapse":
            return self._cat_file_synapse(path, start, end, **kwargs)
        
        elif self.backend == "ipfs":
            return self._cat_file_ipfs(path, start, end, **kwargs)
        
        elif self.backend == "filecoin":
            return self._cat_file_filecoin(path, start, end, **kwargs)
        
        elif self.backend == "storacha":
            return self._cat_file_storacha(path, start, end, **kwargs)
        
        else:
            raise NotImplementedError(f"cat_file not implemented for {self.backend}")
    
    def _cat_file_synapse(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file from Synapse storage."""
        commp = self._synapse_identifier(path)
        
        try:
            data = _run_async_from_sync(self.synapse_storage.synapse_retrieve_data, commp, **kwargs)
            
            # Apply range if specified
            if start is not None or end is not None:
                start = start or 0
                end = end or len(data)
                data = data[start:end]
            
            return data
            
        except Exception as e:
            logger.error(f"Error reading Synapse file: {e}")
            raise

    def pipe_file(self, path: str, value: bytes, mode: str = "overwrite", **kwargs) -> None:
        """Write bytes to a backend path."""
        if self.backend == "storacha":
            if mode not in {"overwrite", "create"}:
                raise ValueError(f"Unsupported Storacha pipe_file mode: {mode}")
            if isinstance(value, str):
                value = value.encode("utf-8")
            if not isinstance(value, (bytes, bytearray)):
                raise TypeError("Storacha pipe_file value must be bytes-like")
            filename = kwargs.pop("filename", os.path.basename(self._strip_protocol(path)) or "data.bin")
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(bytes(value))
                tmp_path = tmp.name
            try:
                result = self.storacha_client.w3_up(tmp_path, filename=filename, **kwargs)
                result.setdefault("filename", filename)
                result.setdefault("size", len(value))
                self._record_storacha_write(path, result, data=bytes(value))
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            return None
        if self.backend != "synapse":
            return super().pipe_file(path, value, mode=mode, **kwargs)
        if mode not in {"overwrite", "create"}:
            raise ValueError(f"Unsupported Synapse pipe_file mode: {mode}")
        if isinstance(value, str):
            value = value.encode("utf-8")
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError("Synapse pipe_file value must be bytes-like")
        filename = kwargs.pop("filename", os.path.basename(self._strip_protocol(path)) or None)
        result = _run_async_from_sync(
            self.synapse_storage.synapse_store_data,
            bytes(value),
            filename=filename,
            **kwargs,
        )
        self._record_synapse_write(path, result)
    
    def _cat_file_ipfs(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file from IPFS."""
        stripped_path = self._strip_protocol(path)
        
        try:
            result = self.ipfs_client.ipfs_cat_data(stripped_path)
            
            if not result.get("success", False):
                raise IOError(f"Failed to read IPFS file: {result.get('error', 'Unknown error')}")
            
            data = result.get("data", b"")
            
            # Apply range if specified
            if start is not None or end is not None:
                start = start or 0
                end = end or len(data)
                data = data[start:end]
            
            return data
            
        except Exception as e:
            logger.error(f"Error reading IPFS file: {e}")
            raise
    
    def _cat_file_filecoin(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file from Filecoin storage."""
        # Implement Filecoin-specific file reading
        logger.warning("Filecoin cat_file not yet implemented")
        raise NotImplementedError("Filecoin cat_file not yet implemented")
    
    def _cat_file_storacha(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file from Storacha storage."""
        identifier = self._storacha_identifier(path)
        normalized = self._normalize_storacha_path(path)
        canonical = self._normalize_storacha_path(identifier)

        if normalized in self._storacha_data_index:
            data = self._storacha_data_index[normalized]
        elif canonical in self._storacha_data_index:
            data = self._storacha_data_index[canonical]
        else:
            result = self.storacha_client.w3_cat(identifier, **kwargs)
            if not result.get("success", False):
                raise IOError(f"Failed to read Storacha file: {result.get('error', 'Unknown error')}")
            data = result.get("content", result.get("data", b""))
            if isinstance(data, str):
                data = data.encode("utf-8")

        if start is not None or end is not None:
            start = start or 0
            end = end or len(data)
            data = data[start:end]

        return bytes(data)
    
    def put_file(self, lpath: str, rpath: str, **kwargs) -> None:
        """Upload a local file to storage."""
        
        if self.backend == "synapse":
            self._put_file_synapse(lpath, rpath, **kwargs)
        
        elif self.backend == "ipfs":
            self._put_file_ipfs(lpath, rpath, **kwargs)
        
        elif self.backend == "filecoin":
            self._put_file_filecoin(lpath, rpath, **kwargs)
        
        elif self.backend == "storacha":
            self._put_file_storacha(lpath, rpath, **kwargs)
        
        else:
            raise NotImplementedError(f"put_file not implemented for {self.backend}")
    
    def _put_file_synapse(self, lpath: str, rpath: str, **kwargs) -> None:
        """Upload file to Synapse storage."""
        try:
            result = _run_async_from_sync(self.synapse_storage.synapse_store_file, lpath, **kwargs)
            
            self._record_synapse_write(rpath, result)
            logger.info(f"File uploaded to Synapse: {result.get('commp', 'unknown CID')}")
            
        except Exception as e:
            logger.error(f"Error uploading to Synapse: {e}")
            raise
    
    def _put_file_ipfs(self, lpath: str, rpath: str, **kwargs) -> None:
        """Upload file to IPFS."""
        try:
            with open(lpath, 'rb') as f:
                data = f.read()
            
            result = self.ipfs_client.ipfs_add_data(data)
            
            if not result.get("success", False):
                raise IOError(f"Failed to upload to IPFS: {result.get('error', 'Unknown error')}")
            
            logger.info(f"File uploaded to IPFS: {result.get('cid', 'unknown CID')}")
            
        except Exception as e:
            logger.error(f"Error uploading to IPFS: {e}")
            raise
    
    def _put_file_filecoin(self, lpath: str, rpath: str, **kwargs) -> None:
        """Upload file to Filecoin storage."""
        # Implement Filecoin-specific file upload
        logger.warning("Filecoin put_file not yet implemented")
        raise NotImplementedError("Filecoin put_file not yet implemented")
    
    def _put_file_storacha(self, lpath: str, rpath: str, **kwargs) -> None:
        """Upload file to Storacha storage."""
        try:
            with open(lpath, "rb") as f:
                data = f.read()
            filename = kwargs.pop("filename", os.path.basename(lpath))
            result = self.storacha_client.w3_up(lpath, filename=filename, **kwargs)
            result.setdefault("filename", filename)
            result.setdefault("size", len(data))
            self._record_storacha_write(rpath, result, data=data)
            logger.info(f"File uploaded to Storacha: {result.get('cid', 'unknown CID')}")
        except Exception as e:
            logger.error(f"Error uploading to Storacha: {e}")
            raise
    
    def get_file(self, rpath: str, lpath: str, **kwargs) -> None:
        """Download a file from storage to local path."""
        
        if self.backend == "synapse":
            self._get_file_synapse(rpath, lpath, **kwargs)
        
        elif self.backend == "ipfs":
            self._get_file_ipfs(rpath, lpath, **kwargs)
        
        elif self.backend == "filecoin":
            self._get_file_filecoin(rpath, lpath, **kwargs)
        
        elif self.backend == "storacha":
            self._get_file_storacha(rpath, lpath, **kwargs)
        
        else:
            raise NotImplementedError(f"get_file not implemented for {self.backend}")
    
    def _get_file_synapse(self, rpath: str, lpath: str, **kwargs) -> None:
        """Download file from Synapse storage."""
        commp = self._synapse_identifier(rpath)
        
        try:
            result = _run_async_from_sync(self.synapse_storage.synapse_retrieve_file, commp, lpath, **kwargs)
            
            if not result.get("success", False):
                raise IOError(f"Failed to download from Synapse: {result.get('error', 'Unknown error')}")
            
            logger.info(f"File downloaded from Synapse to: {lpath}")
            
        except Exception as e:
            logger.error(f"Error downloading from Synapse: {e}")
            raise
    
    def _get_file_ipfs(self, rpath: str, lpath: str, **kwargs) -> None:
        """Download file from IPFS."""
        data = self._cat_file_ipfs(rpath, **kwargs)
        
        # Create directory if needed
        os.makedirs(os.path.dirname(lpath), exist_ok=True)
        
        with open(lpath, 'wb') as f:
            f.write(data)
        
        logger.info(f"File downloaded from IPFS to: {lpath}")
    
    def _get_file_filecoin(self, rpath: str, lpath: str, **kwargs) -> None:
        """Download file from Filecoin storage."""
        # Implement Filecoin-specific file download
        logger.warning("Filecoin get_file not yet implemented")
        raise NotImplementedError("Filecoin get_file not yet implemented")
    
    def _get_file_storacha(self, rpath: str, lpath: str, **kwargs) -> None:
        """Download file from Storacha storage."""
        data = self._cat_file_storacha(rpath, **kwargs)
        directory = os.path.dirname(lpath)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(lpath, "wb") as f:
            f.write(data)
        logger.info(f"File downloaded from Storacha to: {lpath}")
    
    def exists(self, path: str, **kwargs) -> bool:
        """Check if a path exists in storage."""
        
        if self.backend == "synapse":
            return self._exists_synapse(path, **kwargs)
        
        elif self.backend == "ipfs":
            return self._exists_ipfs(path, **kwargs)
        
        elif self.backend == "filecoin":
            return self._exists_filecoin(path, **kwargs)
        
        elif self.backend == "storacha":
            return self._exists_storacha(path, **kwargs)
        
        else:
            return False
    
    def _exists_synapse(self, path: str, **kwargs) -> bool:
        """Check if data exists in Synapse storage."""
        normalized = self._normalize_synapse_path(path)
        if normalized in self._synapse_path_index:
            return True
        commp = self._synapse_identifier(path)
        
        try:
            result = _run_async_from_sync(self.synapse_storage.synapse_get_piece_status, commp, **kwargs)
            
            return result.get("success", False) and result.get("exists", False)
            
        except Exception as e:
            logger.error(f"Error checking Synapse existence: {e}")
            return False
    
    def _exists_ipfs(self, path: str, **kwargs) -> bool:
        """Check if path exists in IPFS."""
        try:
            # Try to get info about the path
            stripped_path = self._strip_protocol(path)
            result = self.ipfs_client.ipfs_object_stat(stripped_path)
            return result.get("success", False)
            
        except Exception as e:
            logger.error(f"Error checking IPFS existence: {e}")
            return False
    
    def _exists_filecoin(self, path: str, **kwargs) -> bool:
        """Check if path exists in Filecoin storage."""
        # Implement Filecoin-specific existence check
        logger.warning("Filecoin exists not yet implemented")
        return False
    
    def _exists_storacha(self, path: str, **kwargs) -> bool:
        """Check if path exists in Storacha storage."""
        normalized = self._normalize_storacha_path(path)
        if normalized in self._storacha_path_index or normalized in self._storacha_data_index:
            return True
        identifier = self._storacha_identifier(path)
        if not identifier:
            return True
        try:
            canonical = self._normalize_storacha_path(identifier)
            return any(
                item["name"] == canonical or item.get("alias") == normalized
                for item in self._ls_storacha("storacha://", detail=True, **kwargs)
            )
        except Exception:
            return False
    
    def info(self, path: str, **kwargs) -> Dict[str, Any]:
        """Get detailed information about a path."""
        
        if self.backend == "synapse":
            return self._info_synapse(path, **kwargs)
        
        elif self.backend == "ipfs":
            return self._info_ipfs(path, **kwargs)
        
        elif self.backend == "filecoin":
            return self._info_filecoin(path, **kwargs)
        
        elif self.backend == "storacha":
            return self._info_storacha(path, **kwargs)
        
        else:
            return {"name": path, "type": "unknown", "size": 0}
    
    def _info_synapse(self, path: str, **kwargs) -> Dict[str, Any]:
        """Get Synapse storage information."""
        normalized = self._normalize_synapse_path(path)
        if normalized in self._synapse_path_index:
            return dict(self._synapse_path_index[normalized])

        commp = self._synapse_identifier(path)
        
        try:
            result = _run_async_from_sync(self.synapse_storage.synapse_get_piece_status, commp, **kwargs)
            
            if result.get("success", False):
                result.setdefault("commp", commp)
                return self._synapse_store_result_to_info(result, fallback_name=commp)
            raise IOError(f"Failed to get Synapse info: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error getting Synapse info: {e}")
            raise
    
    def _info_ipfs(self, path: str, **kwargs) -> Dict[str, Any]:
        """Get IPFS path information."""
        stripped_path = self._strip_protocol(path)
        
        try:
            result = self.ipfs_client.ipfs_object_stat(stripped_path)
            
            if result.get("success", False):
                return {
                    "name": stripped_path,
                    "type": "file" if result.get("Type") == "file" else "directory",
                    "size": result.get("CumulativeSize", 0),
                    "cid": stripped_path,
                    "hash": result.get("Hash", ""),
                    "links": result.get("NumLinks", 0)
                }
            else:
                return {"name": stripped_path, "type": "unknown", "size": 0}
                
        except Exception as e:
            logger.error(f"Error getting IPFS info: {e}")
            return {"name": stripped_path, "type": "unknown", "size": 0}
    
    def _info_filecoin(self, path: str, **kwargs) -> Dict[str, Any]:
        """Get Filecoin storage information."""
        # Implement Filecoin-specific info
        logger.warning("Filecoin info not yet implemented")
        return {"name": path, "type": "unknown", "size": 0}
    
    def _info_storacha(self, path: str, **kwargs) -> Dict[str, Any]:
        """Get Storacha storage information."""
        normalized = self._normalize_storacha_path(path)
        if normalized in self._storacha_path_index:
            return dict(self._storacha_path_index[normalized])

        identifier = self._storacha_identifier(path)
        canonical = self._normalize_storacha_path(identifier)
        if canonical in self._storacha_path_index:
            return dict(self._storacha_path_index[canonical])

        for item in self._ls_storacha("storacha://", detail=True, **kwargs):
            if item["name"] == canonical or item.get("alias") == normalized:
                return dict(item)

        raise FileNotFoundError(path)
    
    # Backend-specific utility methods
    
    def get_backend_status(self) -> Dict[str, Any]:
        """Get status of the current backend."""
        
        if self.backend == "synapse":
            try:
                status = self.synapse_storage.get_status()
            except Exception as e:
                return {"backend": "synapse", "connected": False, "error": str(e)}
            status.setdefault("backend", "synapse")
            status.setdefault(
                "connected",
                bool(status.get("synapse_initialized") and status.get("storage_service_created")),
            )
            return status
        
        elif self.backend == "ipfs":
            # Get IPFS client status
            try:
                result = self.ipfs_client.ipfs_id()
                return {
                    "backend": "ipfs",
                    "connected": result.get("success", False),
                    "peer_id": result.get("ID", ""),
                    "addresses": result.get("Addresses", [])
                }
            except Exception as e:
                return {"backend": "ipfs", "connected": False, "error": str(e)}
        
        elif self.backend == "filecoin":
            # Get Filecoin client status
            return {"backend": "filecoin", "status": "connected"}  # Placeholder
        
        elif self.backend == "storacha":
            # Get Storacha client status
            return {
                "backend": "storacha",
                "connected": True,
                "mock_mode": bool(getattr(self, "storacha_mock_mode", False)),
                "api_url": getattr(self.storacha_client, "api_url", None),
                "space": getattr(self.storacha_client, "space", None),
            }
        
        else:
            return {"backend": self.backend, "status": "unknown"}
    
    def get_backend_config(self) -> Dict[str, Any]:
        """Get configuration for the current backend."""
        
        if self.backend == "synapse":
            return self.synapse_storage.get_configuration()
        
        else:
            return {"backend": self.backend, "metadata": self.metadata}

    def _open(
        self,
        path: str,
        mode: str = "rb",
        block_size=None,
        autocommit: bool = True,
        cache_options=None,
        **kwargs,
    ):
        """Open backend files. Synapse and Storacha currently support binary reads."""
        if self.backend == "synapse":
            if mode != "rb":
                raise NotImplementedError("Synapse fsspec open currently supports only 'rb'")
            return io.BytesIO(self._cat_file_synapse(path, **kwargs))
        if self.backend == "storacha":
            if mode != "rb":
                raise NotImplementedError("Storacha fsspec open currently supports only 'rb'")
            return io.BytesIO(self._cat_file_storacha(path, **kwargs))
        return super()._open(
            path,
            mode=mode,
            block_size=block_size,
            autocommit=autocommit,
            cache_options=cache_options,
            **kwargs,
        )

    def rm_file(self, path: str, **kwargs) -> None:
        """Remove a single backend file."""
        if self.backend != "storacha":
            return super().rm_file(path, **kwargs)

        identifier = self._storacha_identifier(path)
        result = self.storacha_client.w3_remove(identifier, **kwargs)
        if not result.get("success", False):
            raise IOError(f"Failed to delete Storacha file: {result.get('error', 'Unknown error')}")

        normalized = self._normalize_storacha_path(path)
        canonical = self._normalize_storacha_path(identifier)
        for key in {normalized, canonical}:
            self._storacha_path_index.pop(key, None)
            self._storacha_data_index.pop(key, None)
    
    # Hierarchical Storage Management Methods
    # Import methods from hierarchical_storage_methods.py
    
    def _verify_content_integrity(self, cid):
        """
        Verify content integrity across storage tiers.
        
        This method checks that the content stored in different tiers is identical
        and matches the expected hash.
        
        Args:
            cid: Content identifier to verify
            
        Returns:
            Dictionary with verification results
        """
        import hashlib
        import time
        
        result = {
            "success": True,
            "operation": "verify_content_integrity",
            "cid": cid,
            "timestamp": time.time(),
            "verified_tiers": 0,
            "corrupted_tiers": []
        }
        
        # Get tiers that should contain this content
        tiers = self._get_content_tiers(cid)
        if not tiers:
            result["success"] = False
            result["error"] = f"Content {cid} not found in any tier"
            return result
        
        # Get content from first tier as reference
        reference_tier = tiers[0]
        try:
            reference_content = self._get_from_tier(cid, reference_tier)
            reference_hash = hashlib.sha256(reference_content).hexdigest()
        except Exception as e:
            result["success"] = False
            result["error"] = f"Failed to get reference content from {reference_tier}: {str(e)}"
            return result
        
        # Check content in each tier
        result["verified_tiers"] = 1  # Count reference tier
        
        for tier in tiers[1:]:
            try:
                tier_content = self._get_from_tier(cid, tier)
                tier_hash = hashlib.sha256(tier_content).hexdigest()
                
                if tier_hash != reference_hash:
                    # Content mismatch detected
                    result["corrupted_tiers"].append({
                        "tier": tier,
                        "expected_hash": reference_hash,
                        "actual_hash": tier_hash
                    })
                    result["success"] = False
                else:
                    result["verified_tiers"] += 1
                    
            except Exception as e:
                logger.warning(f"Failed to verify content in tier {tier}: {e}")
                # Don't count this as corruption, just a retrieval failure
                result["retrieval_errors"] = result.get("retrieval_errors", [])
                result["retrieval_errors"].append({
                    "tier": tier,
                    "error": str(e)
                })
        
        # Log the verification result
        if result["success"]:
            logger.info(f"Content {cid} integrity verified across {result['verified_tiers']} tiers")
        else:
            logger.warning(f"Content {cid} integrity check failed: {len(result['corrupted_tiers'])} corrupted tiers")
        
        return result
    
    def _get_content_tiers(self, cid):
        """
        Get the tiers that should contain a given content.
        
        Args:
            cid: Content identifier
            
        Returns:
            List of tier names
        """
        # Check each tier to see if it contains the content
        tiers = []
        
        # Check IPFS
        try:
            # Just check if content exists without downloading
            self.info(f"ipfs://{cid}")
            tiers.append("ipfs_local")
        except Exception:
            pass
        
        return tiers
    
    def _get_from_tier(self, cid, tier):
        """
        Get content from a specific storage tier.
        
        Args:
            cid: Content identifier
            tier: Source tier name
            
        Returns:
            Content data if found, None otherwise
        """
        if tier == "ipfs_local":
            # Get from local IPFS
            try:
                return self._open(f"ipfs://{cid}", "rb").read()
            except Exception:
                return None
        
        return None


class _BackendFixedFileSystem(IPFSFileSystem):
    """Base class for protocol-specific fsspec registrations."""

    protocol: str
    default_backend: str

    def __init__(self, *args, backend: Optional[str] = None, **kwargs):
        if backend is not None and backend != self.default_backend:
            raise ValueError(
                f"{self.__class__.__name__} is registered for the "
                f"{self.default_backend!r} backend, got {backend!r}"
            )
        super().__init__(*args, backend=self.default_backend, **kwargs)


class EnhancedIPFSFileSystem(_BackendFixedFileSystem):
    """IPFS protocol filesystem registration."""

    protocol = "ipfs"
    default_backend = "ipfs"


class FilecoinFileSystem(_BackendFixedFileSystem):
    """Filecoin protocol filesystem registration."""

    protocol = "filecoin"
    default_backend = "filecoin"


class StorachaFileSystem(_BackendFixedFileSystem):
    """Storacha protocol filesystem registration."""

    protocol = "storacha"
    default_backend = "storacha"


class SynapseFileSystem(_BackendFixedFileSystem):
    """Synapse protocol filesystem registration."""

    protocol = "synapse"
    default_backend = "synapse"


_PROTOCOL_IMPLEMENTATIONS = {
    "ipfs": EnhancedIPFSFileSystem,
    "filecoin": FilecoinFileSystem,
    "storacha": StorachaFileSystem,
    "synapse": SynapseFileSystem,
}


def register_fsspec_implementations(clobber: bool = True) -> None:
    """Register enhanced fsspec implementations for each storage protocol."""
    for protocol, filesystem_cls in _PROTOCOL_IMPLEMENTATIONS.items():
        try:
            fsspec.register_implementation(protocol, filesystem_cls, clobber=clobber)
        except TypeError:
            fsspec.register_implementation(protocol, filesystem_cls)


# Register the filesystems with clobber=True to handle development reloads.
try:
    register_fsspec_implementations(clobber=True)
except Exception as e:
    logger.warning(f"Failed to register filesystem protocols: {e}")
    try:
        register_fsspec_implementations(clobber=False)
    except Exception as fallback_error:
        logger.warning(f"Failed fallback filesystem protocol registration: {fallback_error}")


# Convenience functions
def create_synapse_filesystem(metadata: Optional[Dict[str, Any]] = None, **kwargs) -> IPFSFileSystem:
    """Create a Synapse SDK filesystem instance."""
    return IPFSFileSystem(backend="synapse", metadata=metadata, **kwargs)


def create_ipfs_filesystem(metadata: Optional[Dict[str, Any]] = None, **kwargs) -> IPFSFileSystem:
    """Create an IPFS filesystem instance."""
    return IPFSFileSystem(backend="ipfs", metadata=metadata, **kwargs)


def create_filecoin_filesystem(metadata: Optional[Dict[str, Any]] = None, **kwargs) -> IPFSFileSystem:
    """Create a Filecoin filesystem instance."""
    return IPFSFileSystem(backend="filecoin", metadata=metadata, **kwargs)


def create_storacha_filesystem(metadata: Optional[Dict[str, Any]] = None, **kwargs) -> IPFSFileSystem:
    """Create a Storacha filesystem instance."""
    return IPFSFileSystem(backend="storacha", metadata=metadata, **kwargs)


if __name__ == "__main__":
    # Example usage
    import tempfile
    
    # Test Synapse backend
    try:
        fs = create_synapse_filesystem(metadata={
            "network": "calibration",
            "auto_approve": True
        })
        
        print(f"Created filesystem with backend: {fs.backend}")
        print(f"Backend status: {fs.get_backend_status()}")
        
        # Test listing (will show stored data in Synapse)
        items = fs.ls("/", detail=True)
        print(f"Found {len(items)} items")
        
    except Exception as e:
        print(f"Error testing Synapse backend: {e}")
    
    # Test IPFS backend
    try:
        fs = create_ipfs_filesystem()
        
        print(f"Created filesystem with backend: {fs.backend}")
        print(f"Backend status: {fs.get_backend_status()}")
        
    except Exception as e:
        print(f"Error testing IPFS backend: {e}")
