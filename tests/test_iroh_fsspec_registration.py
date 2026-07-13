"""Registration and isolation checks for the Iroh fsspec foundation."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HASH = "a" * 64


def test_packaging_advertises_both_fsspec_protocols() -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]

    specs = project["entry-points"]["fsspec.specs"]
    target = "ipfs_kit_py.iroh_fsspec:IrohFileSystem"
    assert specs == {"iroh": target, "iroh+blob": target}


def test_external_and_vendored_registries_resolve_shared_class() -> None:
    fsspec = pytest.importorskip("fsspec")
    from ipfs_kit_py._vendor import fsspec as vendored
    from ipfs_kit_py.iroh_fsspec import IrohFileSystem

    assert fsspec.get_filesystem_class("iroh") is IrohFileSystem
    assert fsspec.get_filesystem_class("iroh+blob") is IrohFileSystem
    assert vendored.get_filesystem_class("iroh") is IrohFileSystem
    assert vendored.get_filesystem_class("iroh+blob") is IrohFileSystem


def test_url_factory_preserves_protocol_without_starting_a_service() -> None:
    fsspec = pytest.importorskip("fsspec")
    from ipfs_kit_py.iroh_fsspec import IrohBlobFile, IrohFile, IrohFileSystem

    namespace_fs, namespace_path = fsspec.core.url_to_fs(f"iroh://{HASH}/docs/readme.txt")
    blob_fs, blob_path = fsspec.core.url_to_fs(f"iroh+blob://{HASH}")

    assert isinstance(namespace_fs, IrohFileSystem)
    assert isinstance(blob_fs, IrohFileSystem)
    assert namespace_fs.client is None
    assert blob_fs.client is None
    assert namespace_fs._iroh_protocol == "iroh"
    assert blob_fs._iroh_protocol == "iroh+blob"
    assert isinstance(namespace_fs._open(namespace_path), IrohFile)
    assert isinstance(blob_fs._open(blob_path), IrohBlobFile)


def test_import_uses_vendored_fallback_when_external_fsspec_is_isolated() -> None:
    script = r"""
import builtins
import importlib
import sys

import ipfs_kit_py

real_import = builtins.__import__
for loaded in list(sys.modules):
    if loaded == "fsspec" or loaded.startswith("fsspec."):
        del sys.modules[loaded]

def isolated_import(name, *args, **kwargs):
    if name == "fsspec" or name.startswith("fsspec."):
        raise ModuleNotFoundError("external fsspec isolated", name=name)
    return real_import(name, *args, **kwargs)

builtins.__import__ = isolated_import
module = importlib.import_module("ipfs_kit_py.iroh_fsspec")
vendored = importlib.import_module("ipfs_kit_py._vendor.fsspec")
assert module.USING_VENDORED_FSSPEC is True
assert vendored.get_filesystem_class("iroh") is module.IrohFileSystem
assert vendored.get_filesystem_class("iroh+blob") is module.IrohFileSystem
filesystem = vendored.filesystem("iroh+blob")
assert filesystem._iroh_protocol == "iroh+blob"
assert filesystem.client is None
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), value] if (value := env.get("PYTHONPATH")) else [str(ROOT)]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
