#!/usr/bin/env python3
"""Audit Iroh wheel/sdist contents and reproducibility.

The verifier intentionally uses only the standard library so release jobs can
run it before installing the project or any optional Iroh dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence


class DistributionAuditError(RuntimeError):
    """A built distribution violates the Iroh packaging contract."""


@dataclass(frozen=True)
class ArchiveEntry:
    path: str
    data: bytes
    mode: int


REQUIRED_PACKAGE_FILES = frozenset(
    {
        "ipfs_kit_py/install_iroh.py",
        "ipfs_kit_py/iroh_install_cli.py",
        "ipfs_kit_py/iroh_fsspec.py",
        "ipfs_kit_py/iroh_vfs.py",
        "ipfs_kit_py/iroh/__init__.py",
        "ipfs_kit_py/iroh/client.py",
        "ipfs_kit_py/iroh/multinode.py",
        "ipfs_kit_py/iroh/release.py",
        "ipfs_kit_py/iroh/service.py",
        "ipfs_kit_py/resources/iroh-releases.json",
        "ipfs_kit_py/resources/iroh-releases.schema.json",
        "ipfs_kit_py/resources/iroh-backend-config.schema.json",
        "ipfs_kit_py/resources/iroh-manifest.schema.json",
        "ipfs_kit_py/resources/iroh-interoperability-evidence.json",
        "ipfs_kit_py/resources/iroh-interoperability-evidence.schema.json",
        "ipfs_kit_py/resources/iroh-release-readiness.json",
        "ipfs_kit_py/resources/iroh-release-readiness.schema.json",
        "ipfs_kit_py/resources/iroh-release-receipts.json",
        "ipfs_kit_py/resources/iroh-release-receipts.schema.json",
    }
)
REQUIRED_FSSPEC_ENTRY_POINTS = {
    "iroh": "ipfs_kit_py.iroh_fsspec:IrohFileSystem",
    "iroh+blob": "ipfs_kit_py.iroh_fsspec:IrohFileSystem",
}
REQUIRED_CONSOLE_SCRIPTS = {
    "ipfs-kit-iroh": "ipfs_kit_py.iroh_install_cli:main",
    "ipfs-kit-iroh-diagnostics": "ipfs_kit_py.iroh.diagnostics_cli:main",
    "ipfs-kit-iroh-manifest": "ipfs_kit_py.iroh.manifest_cli:main",
    "ipfs-kit-iroh-interop": "ipfs_kit_py.iroh.multinode:main",
}
_SDIST_ROOT = re.compile(r"^ipfs_kit_py-[^/]+/")


def _canonical_path(path: str, *, strip_sdist_root: bool) -> str:
    value = _SDIST_ROOT.sub("", path, count=1) if strip_sdist_root else path
    return value.rstrip("/")


def _validate_member_path(path: str) -> None:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or "\\" in path:
        raise DistributionAuditError(f"unsafe archive member path: {path!r}")


def read_archive(path: Path) -> dict[str, ArchiveEntry]:
    """Read regular files from a wheel or gzip sdist with normalized paths."""

    result: dict[str, ArchiveEntry] = {}
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                _validate_member_path(info.filename)
                canonical = _canonical_path(info.filename, strip_sdist_root=False)
                result[canonical] = ArchiveEntry(
                    canonical,
                    archive.read(info),
                    (info.external_attr >> 16) & 0o777,
                )
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                _validate_member_path(member.name)
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:  # pragma: no cover - guarded by isfile
                    raise DistributionAuditError(f"unable to read archive member {member.name}")
                canonical = _canonical_path(member.name, strip_sdist_root=True)
                result[canonical] = ArchiveEntry(canonical, extracted.read(), member.mode & 0o777)
    else:
        raise DistributionAuditError(f"unsupported distribution artifact: {path}")
    if not result:
        raise DistributionAuditError(f"distribution is empty: {path}")
    return result


def _metadata_entry(entries: Mapping[str, ArchiveEntry], suffix: str) -> ArchiveEntry:
    if suffix == "PKG-INFO" and suffix in entries:
        return entries[suffix]
    matches = [entry for name, entry in entries.items() if name.endswith(suffix)]
    if len(matches) != 1:
        raise DistributionAuditError(f"expected exactly one {suffix}, found {len(matches)}")
    return matches[0]


def _parse_entry_points(data: bytes) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    selected: dict[str, str] | None = None
    for raw_line in data.decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            selected = sections.setdefault(line[1:-1], {})
            continue
        if selected is None or "=" not in line:
            raise DistributionAuditError("malformed entry_points.txt")
        key, value = line.split("=", 1)
        selected[key.strip()] = value.strip()
    return sections


def _audit_forbidden_files(entries: Mapping[str, ArchiveEntry]) -> None:
    for path in entries:
        pure = PurePosixPath(path)
        lowered = path.lower()
        if "__pycache__" in pure.parts or pure.suffix in {".pyc", ".pyo"}:
            raise DistributionAuditError(f"Python cache leaked into distribution: {path}")
        if len(pure.parts) >= 2 and pure.parts[:2] == ("ipfs_kit_py", "bin"):
            raise DistributionAuditError(f"runtime binary leaked into distribution: {path}")
        if "ipfs-kit-iroh-sidecar" in lowered:
            raise DistributionAuditError(f"Iroh sidecar leaked into distribution: {path}")
        if lowered.endswith((".receipt.json", ".key", ".pem")):
            raise DistributionAuditError(f"runtime credential/receipt leaked into distribution: {path}")


def normalized_digest(entries: Mapping[str, ArchiveEntry]) -> str:
    """Hash logical archive contents independent of container timestamps."""

    digest = hashlib.sha256()
    for path in sorted(entries):
        entry = entries[path]
        digest.update(path.encode("utf-8") + b"\0")
        digest.update(f"{entry.mode:o}".encode("ascii") + b"\0")
        digest.update(hashlib.sha256(entry.data).digest())
    return digest.hexdigest()


def audit_distribution(path: Path) -> dict[str, object]:
    path = path.resolve()
    entries = read_archive(path)
    _audit_forbidden_files(entries)
    missing = sorted(REQUIRED_PACKAGE_FILES.difference(entries))
    if missing:
        raise DistributionAuditError(f"{path.name} omits required Iroh files: {missing}")

    metadata = _metadata_entry(entries, ".dist-info/METADATA" if path.suffix == ".whl" else "PKG-INFO")
    metadata_text = metadata.data.decode("utf-8")
    for extra in ("iroh", "fsspec"):
        if f"Provides-Extra: {extra}" not in metadata_text:
            raise DistributionAuditError(f"{path.name} does not advertise the {extra!r} extra")
    if "Requires-Dist: blake3" not in metadata_text or 'extra == "iroh"' not in metadata_text:
        raise DistributionAuditError("Iroh extra is missing its conditional blake3 dependency")
    if "Requires-Dist: duckdb" not in metadata_text:
        raise DistributionAuditError("Iroh extra is missing its conditional duckdb dependency")
    if "Requires-Dist: fsspec" not in metadata_text or 'extra == "fsspec"' not in metadata_text:
        raise DistributionAuditError("external fsspec is not represented as an optional dependency")

    if path.suffix == ".whl":
        points = _parse_entry_points(_metadata_entry(entries, ".dist-info/entry_points.txt").data)
        if points.get("fsspec.specs") != REQUIRED_FSSPEC_ENTRY_POINTS:
            raise DistributionAuditError("wheel fsspec entry points do not match the frozen contract")
        scripts = points.get("console_scripts", {})
        for name, target in REQUIRED_CONSOLE_SCRIPTS.items():
            if scripts.get(name) != target:
                raise DistributionAuditError(f"wheel console script {name!r} is missing or incorrect")

    raw_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "artifact": path.name,
        "bytes": path.stat().st_size,
        "files": len(entries),
        "sha256": raw_digest,
        "normalized_sha256": normalized_digest(entries),
        "kind": "wheel" if path.suffix == ".whl" else "sdist",
    }


def compare_builds(first: Iterable[Path], second: Iterable[Path]) -> list[dict[str, object]]:
    """Require two builds to have identical logical wheel and sdist contents."""

    by_kind: list[dict[str, dict[str, object]]] = []
    for paths in (first, second):
        audited: dict[str, dict[str, object]] = {}
        for path in paths:
            report = audit_distribution(path)
            kind = str(report["kind"])
            if kind in audited:
                raise DistributionAuditError(f"more than one {kind} artifact in a build")
            audited[kind] = report
        if set(audited) != {"wheel", "sdist"}:
            raise DistributionAuditError("each build must contain exactly one wheel and one sdist")
        by_kind.append(audited)

    comparison: list[dict[str, object]] = []
    for kind in ("wheel", "sdist"):
        left, right = by_kind[0][kind], by_kind[1][kind]
        if left["normalized_sha256"] != right["normalized_sha256"]:
            raise DistributionAuditError(f"repeated {kind} builds have different logical contents")
        comparison.append(
            {
                "kind": kind,
                "normalized_sha256": left["normalized_sha256"],
                "byte_reproducible": left["sha256"] == right["sha256"],
            }
        )
    return comparison


def _artifacts(directory: Path) -> list[Path]:
    return sorted([*directory.glob("*.whl"), *directory.glob("*.tar.gz")])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="*", type=Path, help="wheel/sdist artifacts to audit")
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("BUILD_A", "BUILD_B"),
        type=Path,
        help="audit and compare two directories containing a wheel and sdist",
    )
    parser.add_argument("--report", type=Path, help="write the JSON audit report here")
    args = parser.parse_args(argv)
    try:
        if args.compare:
            reports: object = {
                "schema_version": 1,
                "task_id": "IROH-026",
                "status": "passed",
                "builds": [
                    [audit_distribution(path) for path in _artifacts(directory)]
                    for directory in args.compare
                ],
                "reproducibility": compare_builds(
                    _artifacts(args.compare[0]), _artifacts(args.compare[1])
                ),
            }
        else:
            if not args.artifacts:
                parser.error("provide artifacts or --compare BUILD_A BUILD_B")
            reports = {
                "schema_version": 1,
                "task_id": "IROH-026",
                "status": "passed",
                "artifacts": [audit_distribution(path) for path in args.artifacts],
            }
        encoded = json.dumps(reports, indent=2, sort_keys=True) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0
    except (DistributionAuditError, OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"Iroh distribution audit failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
