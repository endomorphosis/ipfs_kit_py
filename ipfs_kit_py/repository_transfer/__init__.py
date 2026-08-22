from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
_OWNED = Path(__file__).resolve().parents[2] / "repository_transfer" / "bundle.py"
_spec = spec_from_file_location("ipfs_kit_py.repository_transfer.bundle", _OWNED)
if _spec is None or _spec.loader is None:
    raise ImportError("EAAEF-021 owned bundle module is absent")
bundle = module_from_spec(_spec)
_spec.loader.exec_module(bundle)
admit_transfer = bundle.admit_transfer
TransferError = bundle.TransferError
