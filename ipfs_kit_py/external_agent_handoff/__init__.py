"""Package re-export of EAAEF-011 handoff storage."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_OWNED = Path(__file__).resolve().parents[2] / "external_agent_handoff" / "storage.py"
_spec = spec_from_file_location("ipfs_kit_py.external_agent_handoff.storage", _OWNED)
if _spec is None or _spec.loader is None:
    raise ImportError("EAAEF-011 owned storage module is absent")
storage = module_from_spec(_spec)
_spec.loader.exec_module(storage)

EncryptedExportStore = storage.EncryptedExportStore
HandoffStorageError = storage.HandoffStorageError

__all__ = ("EncryptedExportStore", "HandoffStorageError", "storage")
