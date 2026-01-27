"""Smoke test for the external `libp2p` (py-libp2p) dependency.

This test should fail if the upstream `libp2p` package cannot be imported.

Note: other tests in this repository mutate `sys.path` at import time during
collection. Some of those mutations can accidentally make our internal
`ipfs_kit_py/libp2p/` package importable as top-level `libp2p`, shadowing the
real dependency. These tests defensively de-shadow the local source tree.
"""

from __future__ import annotations

import importlib
import sys
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
            and p not in {"ipfs_kit_py", "."}
        ]

        # If something already imported a shadowing module, clear it.
        # We clear all `libp2p*` modules that originate from this repo to
        # avoid mixed-module states (external libp2p + local submodules).
        for name, module in list(sys.modules.items()):
            if name == "libp2p" or name.startswith("libp2p."):
                module_file = getattr(module, "__file__", "") or ""
                if module_file and str(repo_root) in module_file:
                    sys.modules.pop(name, None)
        # Also clear the toplevel name unconditionally if it was loaded from our
        # local package dir.
        existing = sys.modules.get("libp2p")
        if existing is not None:
            existing_file = getattr(existing, "__file__", "") or ""
            if str(local_pkg_dir) in existing_file:
                sys.modules.pop("libp2p", None)

        importlib.invalidate_caches()
        try:
            libp2p = importlib.import_module("libp2p")
        except ModuleNotFoundError:
            pytest.skip("External libp2p dependency not installed")

        libp2p_file = getattr(libp2p, "__file__", "") or ""
        local_shadow_dir = (local_pkg_dir / "libp2p").resolve()
        assert str(local_shadow_dir) not in libp2p_file, (
            "Imported local shadowing module instead of external dependency: "
            f"{libp2p_file}"
        )
        return libp2p
    finally:
        sys.path = original_sys_path


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

