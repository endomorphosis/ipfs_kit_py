"""Artifact-install profile for the kit proof-context persistence provider."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _run(args: list[str], *, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def test_metadata_declares_explicit_ipfs_extra_and_exact_contract_versions() -> None:
    import tomllib

    metadata = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["optional-dependencies"]["proof-context-ipfs"] == []

    import ipfs_kit_py.proof_context as provider

    assert provider.SCHEMA == "ipfs-kit.proof-context.v0.1"
    assert provider.COMPATIBLE_VERSIONS == {
        "proof_context": "0.1",
        "proof_seal_store": "1.0.0",
    }
    assert provider.IPFS_TRANSPORT_EXTRA == "proof-context-ipfs"


def test_cold_import_does_not_load_storage_implementations() -> None:
    code = """
import json
import sys
sys.path.insert(0, __import__('os').environ['PCCE_PACKAGE_TARGET'])
import ipfs_kit_py.proof_context as provider
assert provider.SCHEMA == 'ipfs-kit.proof-context.v0.1'
assert not any(name.startswith('ipfs_kit_py.proof_context.state_store') for name in sys.modules)
assert not any(name.startswith('ipfs_kit_py.proof_seal_store.local_store') for name in sys.modules)
print(json.dumps(provider.COMPATIBLE_VERSIONS, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=PACKAGE_ROOT.parent,
        env={"PCCE_PACKAGE_TARGET": str(PACKAGE_ROOT)},
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {
        "proof_context": "0.1",
        "proof_seal_store": "1.0.0",
    }


def test_wheel_and_sdist_install_without_source_siblings_and_use_local_storage(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    generated_egg_info = PACKAGE_ROOT / "ipfs_kit_py.egg-info"
    egg_info_existed = generated_egg_info.exists()
    _run([sys.executable, "-m", "build", "--outdir", str(dist), str(PACKAGE_ROOT)], cwd=tmp_path)
    # setuptools may leave this generated metadata directory beside the source.
    # It is not part of the source artifact and can make pytest discover stale
    # entry points on a later test run.
    if not egg_info_existed:
        shutil.rmtree(generated_egg_info)

    wheel = next(dist.glob("ipfs_kit_py-*.whl"))
    sdist = next(dist.glob("ipfs_kit_py-*.tar.gz"))
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "ipfs_kit_py/proof_context/__init__.py" in names
        metadata_name = next(name for name in names if name.endswith("METADATA"))
        assert b"Provides-Extra: proof-context-ipfs" in archive.read(metadata_name)
        assert not any(name.startswith("external/ipfs_datasets/") for name in names)
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        assert any(name.endswith("ipfs_kit_py/proof_context/__init__.py") for name in names)
        assert not any("/external/ipfs_datasets/" in name for name in names)

    target = tmp_path / "installed"
    _run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target), str(wheel)],
        cwd=tmp_path,
    )
    root = tmp_path / "store"
    code = """
import os
import sys
sys.path.insert(0, os.environ['PCCE_PACKAGE_TARGET'])
from pathlib import Path
from ipfs_kit_py.proof_context import open_local_store, open_verification_store
from ipfs_kit_py.proof_seal_store.wal import SealTransitionWal

root = Path(os.environ['PCCE_STORE_ROOT'])
state = open_local_store(root)
reference = state.put(b'proof-context-wheel')
assert state.get(reference) == b'proof-context-wheel'
receipts = open_verification_store(root)
receipt = receipts.put_verification_receipt(b'{"status":"verified"}')
assert receipts.get_verification_receipt(receipt) == b'{"status":"verified"}'
SealTransitionWal(root)
assert (root / 'objects').is_dir()
assert (root / 'seal_wal').is_dir()
"""
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PCCE_PACKAGE_TARGET": str(target),
        "PCCE_STORE_ROOT": str(root),
    }
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
