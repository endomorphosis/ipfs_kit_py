#!/usr/bin/env python3
"""Smoke-test an installed ipfs_kit_py distribution without an Iroh binary."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
from importlib import metadata, resources
from pathlib import Path
from typing import Sequence


def _entry_points(group: str) -> dict[str, str]:
    selected = metadata.entry_points().select(group=group)
    return {point.name: point.value for point in selected}


def run_smoke(*, fsspec_mode: str, iroh_extra: str, bin_dir: Path) -> dict[str, object]:
    """Validate metadata, imports, resource access, and side-effect isolation."""

    os.environ.pop("IPFS_KIT_AUTO_INSTALL_BINARIES", None)
    os.environ["IPFS_KIT_BIN_DIR"] = str(bin_dir)
    before = sorted(str(path.relative_to(bin_dir)) for path in bin_dir.rglob("*")) if bin_dir.exists() else []

    distribution = metadata.distribution("ipfs_kit_py")
    extras = {value for value in distribution.metadata.get_all("Provides-Extra", [])}
    if not {"iroh", "fsspec"}.issubset(extras):
        raise RuntimeError("installed metadata omits the iroh or fsspec extra")

    external_fsspec = importlib.util.find_spec("fsspec") is not None
    if fsspec_mode == "external" and not external_fsspec:
        raise RuntimeError("external fsspec lane did not install fsspec")
    if fsspec_mode == "vendored" and external_fsspec:
        raise RuntimeError("vendored fsspec lane unexpectedly contains external fsspec")

    import ipfs_kit_py

    optional_modules = {
        name: importlib.util.find_spec(name) is not None for name in ("blake3", "duckdb")
    }
    expected_optional = all(optional_modules.values()) if iroh_extra == "present" else not any(
        optional_modules.values()
    )
    if not expected_optional:
        raise RuntimeError("installed environment does not match the requested Iroh extra mode")
    if iroh_extra == "present":
        from ipfs_kit_py.iroh import IrohUnavailableError
        from ipfs_kit_py.iroh_fsspec import IrohFileSystem, USING_VENDORED_FSSPEC

        if USING_VENDORED_FSSPEC != (fsspec_mode == "vendored"):
            raise RuntimeError("Iroh filesystem selected the wrong fsspec implementation")
        filesystem = IrohFileSystem()
        if filesystem.client is not None:
            raise RuntimeError("constructing IrohFileSystem unexpectedly created a runtime client")
        if not issubclass(IrohUnavailableError, Exception):  # pragma: no cover - defensive
            raise RuntimeError("Iroh typed errors are unavailable")

    package_root = resources.files("ipfs_kit_py")
    for resource_name in (
        "iroh-releases.json",
        "iroh-releases.schema.json",
        "iroh-backend-config.schema.json",
        "iroh-manifest.schema.json",
        "iroh-interoperability-evidence.json",
        "iroh-interoperability-evidence.schema.json",
    ):
        candidate = package_root.joinpath("resources", resource_name)
        if not candidate.is_file():
            raise RuntimeError(f"installed distribution omits {resource_name}")
        json.loads(candidate.read_text(encoding="utf-8"))

    expected_specs = {
        "iroh": "ipfs_kit_py.iroh_fsspec:IrohFileSystem",
        "iroh+blob": "ipfs_kit_py.iroh_fsspec:IrohFileSystem",
    }
    specs = _entry_points("fsspec.specs")
    for name, target in expected_specs.items():
        if specs.get(name) != target:
            raise RuntimeError(f"installed fsspec entry point {name!r} is incorrect")

    expected_scripts = {
        "ipfs-kit-iroh",
        "ipfs-kit-iroh-diagnostics",
        "ipfs-kit-iroh-manifest",
        "ipfs-kit-iroh-interop",
    }
    if not expected_scripts.issubset(_entry_points("console_scripts")):
        raise RuntimeError("installed distribution omits an Iroh console script")

    if shutil.which("ipfs-kit-iroh-sidecar") or shutil.which("ipfs-kit-iroh-sidecar.exe"):
        raise RuntimeError("minimal install unexpectedly exposes an Iroh sidecar")
    after = sorted(str(path.relative_to(bin_dir)) for path in bin_dir.rglob("*")) if bin_dir.exists() else []
    if after != before:
        raise RuntimeError("ordinary package import created binary runtime state")

    return {
        "schema_version": 1,
        "task_id": "IROH-026",
        "status": "passed",
        "distribution_version": distribution.version,
        "fsspec_mode": fsspec_mode,
        "external_fsspec": external_fsspec,
        "iroh_extra": iroh_extra,
        "optional_modules": optional_modules,
        "iroh_binary": "absent",
        "package": str(Path(ipfs_kit_py.__file__).resolve()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fsspec", choices=("external", "vendored"), required=True)
    parser.add_argument("--iroh-extra", choices=("present", "absent"), required=True)
    parser.add_argument("--bin-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_smoke(
            fsspec_mode=args.fsspec,
            iroh_extra=args.iroh_extra,
            bin_dir=args.bin_dir.resolve(),
        )
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0
    except Exception as exc:
        print(f"Iroh install smoke failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
