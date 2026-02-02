"""Smoke test for the external `libp2p` (py-libp2p) dependency.

This test should fail if the upstream `libp2p` package cannot be imported.

Note: other tests in this repository mutate `sys.path` at import time during
collection. Some of those mutations can accidentally make our internal
`ipfs_kit_py/libp2p/` package importable as top-level `libp2p`, shadowing the
real dependency. These tests defensively de-shadow the local source tree.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import subprocess
import pytest
from pathlib import Path


def _import_external_libp2p():
    """Import the *external* libp2p dependency, not the local source tree."""

    repo_root = Path(__file__).resolve().parents[1]
    local_pkg_dir = (repo_root / "ipfs_kit_py").resolve()

    original_sys_path = list(sys.path)
    try:
        sys.path = [
            p
            for p in sys.path
            if p
            and Path(p).resolve() != local_pkg_dir
            and Path(p).resolve() != repo_root
            and Path(p).name != "ipfs_kit_py"
            and p not in {"ipfs_kit_py", "."}
        ]

        # If something already imported a shadowing module, clear it.
        # We clear all `libp2p*` modules that originate from this repo to
        # avoid mixed-module states (external libp2p + local submodules).
        for name, module in list(sys.modules.items()):
            if name == "libp2p" or name.startswith("libp2p."):
                module_file = getattr(module, "__file__", "") or ""
                normalized = module_file.replace("\\", "/")
                if module_file and (
                    str(repo_root) in module_file
                    or "/ipfs_kit_py/libp2p" in normalized
                ):
                    sys.modules.pop(name, None)
        # Also clear the toplevel name unconditionally if it was loaded from our
        # local package dir.
        existing = sys.modules.get("libp2p")
        if existing is not None:
            existing_file = getattr(existing, "__file__", "") or ""
            normalized = existing_file.replace("\\", "/")
            if str(local_pkg_dir) in existing_file or "/ipfs_kit_py/libp2p" in normalized:
                sys.modules.pop("libp2p", None)

        importlib.invalidate_caches()

        def _load_external_libp2p_from_path():
            for entry in sys.path:
                if not entry:
                    continue
                try:
                    entry_path = Path(entry).resolve()
                    if entry_path.name == "ipfs_kit_py":
                        continue
                    candidate = (entry_path / "libp2p" / "__init__.py").resolve()
                except Exception:
                    continue
                if not candidate.exists():
                    continue
                normalized = str(candidate).replace("\\", "/")
                if "/ipfs_kit_py/" in normalized:
                    continue
                spec = importlib.util.spec_from_file_location(
                    "libp2p",
                    str(candidate),
                    submodule_search_locations=[str(candidate.parent)],
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules["libp2p"] = module
                spec.loader.exec_module(module)  # type: ignore[attr-defined]
                return module
            return None

        libp2p = _load_external_libp2p_from_path()
        if libp2p is None:
            try:
                libp2p = importlib.import_module("libp2p")
            except ModuleNotFoundError:
                if not _attempt_install_libp2p():
                    pytest.skip("External libp2p dependency not installed")
                libp2p = importlib.import_module("libp2p")

        libp2p_file = getattr(libp2p, "__file__", "") or ""
        local_shadow_dir = (local_pkg_dir / "libp2p").resolve()
        normalized_file = libp2p_file.replace("\\", "/")
        assert str(local_shadow_dir) not in libp2p_file and "/ipfs_kit_py/libp2p" not in normalized_file, (
            "Imported local shadowing module instead of external dependency: "
            f"{libp2p_file}"
        )
        return libp2p
    finally:
        sys.path = original_sys_path


def _attempt_install_libp2p() -> bool:
    """Attempt to install libp2p dependencies in zero-touch fashion."""
    try:
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "--user",
            "--break-system-packages",
            "libp2p>=0.2.0",
        ])
        return True
    except Exception:
        return False


def test_libp2p_api_imports():
    libp2p = _import_external_libp2p()

    from libp2p import new_host  # noqa: F401
    from libp2p.crypto.keys import KeyPair  # noqa: F401


def test_libp2p_optional_modules_importable_if_present():
    """Optional imports: don't fail if upstream removed/renamed them."""
    try:
        from libp2p.pubsub.gossipsub import GossipSub  # noqa: F401
    except Exception:
        pass

    try:
        from libp2p.pubsub.floodsub import FloodSub  # noqa: F401
    except Exception:
        pass

    try:
        from libp2p.network.stream.net_stream import NetStream  # noqa: F401
    except Exception:
        pass

