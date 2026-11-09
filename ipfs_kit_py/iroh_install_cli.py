"""Explicit lifecycle commands for the managed IPFS Kit Iroh sidecar.

Importing this module is side-effect free.  Network access and filesystem
mutations happen only when :meth:`IrohInstallManager.install`, ``update``, or
``rollback`` is called (or their corresponding CLI command is invoked).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

from .install_iroh import IrohInstallError, IrohInstaller


RECEIPT_FILENAME = ".ipfs-kit-iroh-install.json"
PREVIOUS_BINARY_SUFFIX = ".previous"
PREVIOUS_RECEIPT_SUFFIX = ".previous"
LOCK_FILENAME = ".ipfs-kit-iroh-update.lock"
RECEIPT_SCHEMA_VERSION = 1


class IrohLifecycleError(IrohInstallError):
    """An expected lifecycle refusal or managed-state consistency failure."""


class IrohUpdateLockedError(IrohLifecycleError):
    """Another process currently owns the Iroh lifecycle lock."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise IrohLifecycleError(f"cannot read managed Iroh binary {path}: {exc}") from exc
    return digest.hexdigest()


def _is_prerelease(version: str) -> bool:
    """Recognize common SemVer and PEP 440 prerelease spellings."""

    core = version.strip().lstrip("v")
    return bool(
        re.search(
            r"(?:^|[.\-_+]|(?<=\d))"
            r"(?:a(?:lpha)?|b(?:eta)?|rc|pre(?:view)?|dev)(?=\d|$|[.\-_+])\d*",
            core,
            re.IGNORECASE,
        )
    )


def _version_key(version: str) -> tuple[Any, ...]:
    """Return a SemVer-like comparison key without adding a dependency."""

    normalized = version.strip().lstrip("v")
    match = re.fullmatch(r"(\d+(?:\.\d+)*)(.*)", normalized)
    if match is None:
        parts = re.findall(r"\d+|[A-Za-z]+", normalized)
        return ((), 0, tuple((0, int(p)) if p.isdigit() else (1, p.lower()) for p in parts))

    numbers = [int(part) for part in match.group(1).split(".")]
    while numbers and numbers[-1] == 0:
        numbers.pop()
    suffix = match.group(2).split("+", 1)[0].lstrip(".-_")
    if not suffix:
        # A final release sorts after every prerelease with the same core.
        return (tuple(numbers), 1, ())
    prerelease_order = {
        "dev": 0,
        "a": 1,
        "alpha": 1,
        "b": 2,
        "beta": 2,
        "pre": 3,
        "preview": 3,
        "rc": 4,
    }
    parts = re.findall(r"\d+|[A-Za-z]+", suffix)
    prerelease = tuple(
        (1, int(part))
        if part.isdigit()
        else (0, prerelease_order.get(part.lower(), 5), part.lower())
        for part in parts
    )
    return (tuple(numbers), 0, prerelease)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    """Write a JSON object durably without exposing a partial receipt."""

    try:
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        temporary: Path | None = None
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        IrohInstaller._fsync_directory(path.parent)
    except OSError as exc:
        if temporary is not None:
            with contextlib.suppress(OSError):
                temporary.unlink()
        raise IrohLifecycleError(f"cannot write Iroh install receipt {path}: {exc}") from exc


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read and validate an install receipt, returning ``None`` when absent."""

    if not path.exists():
        return None
    if not path.is_file():
        raise IrohLifecycleError(f"invalid Iroh install receipt {path}: not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IrohLifecycleError(f"invalid Iroh install receipt {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IrohLifecycleError(f"invalid Iroh install receipt {path}: expected an object")

    required_strings = ("version", "source", "digest", "time", "binary", "binary_digest")
    if value.get("schema_version") != RECEIPT_SCHEMA_VERSION or any(
        not isinstance(value.get(field), str) or not value[field] for field in required_strings
    ):
        raise IrohLifecycleError(f"invalid Iroh install receipt {path}: required fields are missing")
    for field in ("digest", "binary_digest"):
        digest = value[field]
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise IrohLifecycleError(f"invalid Iroh install receipt {path}: {field} is not SHA-256")
    try:
        datetime.fromisoformat(value["time"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise IrohLifecycleError(
            f"invalid Iroh install receipt {path}: time is not ISO 8601"
        ) from exc
    return value


class IrohInstallManager:
    """Manage one verified current binary and one retained previous binary."""

    def __init__(
        self,
        installer: IrohInstaller | None = None,
        *,
        bin_dir: str | os.PathLike[str] | None = None,
        clock: Callable[[], datetime] | None = None,
        command_runner: Callable[..., Any] | None = None,
    ) -> None:
        self.installer = installer or IrohInstaller(
            metadata={"bin_dir": str(bin_dir)} if bin_dir is not None else {}
        )
        if bin_dir is not None:
            self.installer.bin_dir = Path(bin_dir).expanduser().resolve()
        self.bin_dir = self.installer.bin_dir

        sidecar = self.installer.release.get("sidecar", {})
        self.binary_name = str(sidecar.get("binary") or "ipfs-kit-iroh-sidecar")
        if os.name == "nt" and not self.binary_name.endswith(".exe"):
            self.binary_name += ".exe"
        self.binary_path = self.bin_dir / self.binary_name
        self.receipt_path = self.bin_dir / RECEIPT_FILENAME
        self.previous_binary_path = self.bin_dir / (self.binary_name + PREVIOUS_BINARY_SUFFIX)
        self.previous_receipt_path = self.bin_dir / (
            RECEIPT_FILENAME + PREVIOUS_RECEIPT_SUFFIX
        )
        self.lock_path = self.bin_dir / LOCK_FILENAME
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._run = command_runner or subprocess.run

    @property
    def available_version(self) -> str:
        sidecar = self.installer.release.get("sidecar")
        if not isinstance(sidecar, Mapping) or not isinstance(sidecar.get("version"), str):
            raise IrohLifecycleError("release manifest has no Iroh sidecar version")
        return str(sidecar["version"])

    def _select_version(self, requested: str | None, allow_prerelease: bool) -> str:
        version = requested or self.available_version
        if version != self.available_version:
            raise IrohLifecycleError(
                f"Iroh version {version} is not in the pinned release manifest "
                f"(available: {self.available_version})"
            )
        if _is_prerelease(version) and not allow_prerelease:
            raise IrohLifecycleError(
                f"Iroh version {version} is a prerelease; pass --allow-prerelease explicitly"
            )
        return version

    @contextlib.contextmanager
    def _lock(self) -> Iterator[None]:
        """Acquire the cross-process lifecycle lock without waiting."""

        try:
            self.bin_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
            stream = self.lock_path.open("a+")
        except OSError as exc:
            raise IrohLifecycleError(f"cannot open Iroh update lock {self.lock_path}: {exc}") from exc
        locked = False
        try:
            try:
                if os.name == "nt":
                    import msvcrt

                    stream.seek(0)
                    if stream.read(1) == "":
                        stream.write("0")
                        stream.flush()
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except (OSError, BlockingIOError) as exc:
                raise IrohUpdateLockedError(
                    f"another Iroh install/update/rollback is in progress ({self.lock_path})"
                ) from exc
            stream.seek(0)
            stream.truncate()
            stream.write(f"pid={os.getpid()}\n")
            stream.flush()
            yield
        finally:
            if locked:
                with contextlib.suppress(OSError):
                    if os.name == "nt":
                        import msvcrt

                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            stream.close()

    def _artifact(self) -> dict[str, Any]:
        return self.installer.select_artifact()

    def _plan(self, operation: str, version: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "operation": operation,
            "dry_run": True,
            "binary": str(self.binary_path),
            "installed": self.binary_path.is_file(),
        }
        if version is not None:
            result["version"] = version
        return result

    def _make_receipt(
        self, version: str, artifact: Mapping[str, Any], binary: Path
    ) -> dict[str, Any]:
        installed_at = self._clock()
        if installed_at.tzinfo is None:
            installed_at = installed_at.replace(tzinfo=timezone.utc)
        return {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "version": version,
            "source": str(artifact["url"]),
            # The supply-chain digest identifies the downloaded archive.
            "digest": str(artifact["checksum_sha256"]).lower(),
            "time": installed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "binary": str(binary.resolve()),
            # The executable digest detects local corruption independently.
            "binary_digest": _sha256(binary),
            "target": str(artifact.get("id", "unknown")),
        }

    @staticmethod
    def _snapshot(paths: Sequence[Path], directory: Path) -> dict[Path, Path | None]:
        """Copy lifecycle files into a private transaction directory."""

        snapshots: dict[Path, Path | None] = {}
        for index, path in enumerate(paths):
            if path.exists():
                if not path.is_file():
                    raise IrohLifecycleError(f"managed Iroh path is not a regular file: {path}")
                snapshot = directory / str(index)
                try:
                    shutil.copy2(path, snapshot)
                except OSError as exc:
                    raise IrohLifecycleError(f"cannot snapshot managed Iroh state: {exc}") from exc
                snapshots[path] = snapshot
            else:
                snapshots[path] = None
        return snapshots

    def _restore(self, snapshots: Mapping[Path, Path | None]) -> None:
        """Restore an exact lifecycle snapshot after a failed transaction."""

        failures: list[str] = []
        for path, snapshot in snapshots.items():
            try:
                if snapshot is None:
                    path.unlink(missing_ok=True)
                else:
                    temporary = path.with_name(path.name + ".restore")
                    shutil.copy2(snapshot, temporary)
                    os.replace(temporary, path)
            except OSError as exc:
                failures.append(f"{path}: {exc}")
        if failures:
            raise IrohLifecycleError(
                "failed to restore Iroh lifecycle transaction: " + "; ".join(failures)
            )

    def _retain_current(self) -> None:
        receipt = _read_json(self.receipt_path)
        if not self.binary_path.is_file() or receipt is None:
            raise IrohLifecycleError("managed Iroh installation is incomplete; refusing update")
        temporary = self.previous_binary_path.with_name(self.previous_binary_path.name + ".tmp")
        try:
            shutil.copy2(self.binary_path, temporary)
            os.replace(temporary, self.previous_binary_path)
            _atomic_json(self.previous_receipt_path, receipt)
        except OSError as exc:
            with contextlib.suppress(OSError):
                temporary.unlink()
            raise IrohLifecycleError(f"cannot retain previous Iroh binary: {exc}") from exc

    def install(
        self,
        *,
        version: str | None = None,
        allow_prerelease: bool = False,
        dry_run: bool = False,
        check: bool = False,
    ) -> dict[str, Any]:
        selected = self._select_version(version, allow_prerelease)
        if self.binary_path.exists() or self.receipt_path.exists():
            raise IrohLifecycleError("Iroh is already installed; use the update command")
        if dry_run:
            artifact = self._artifact()
            plan = self._plan("install", selected)
            plan.update(source=artifact["url"], digest=artifact["checksum_sha256"])
            return plan

        with self._lock():
            if self.binary_path.exists() or self.receipt_path.exists():
                raise IrohLifecycleError("Iroh is already installed; use the update command")
            artifact = self._artifact()
            installed = self.installer.install()
            if installed.resolve() != self.binary_path.resolve():
                with contextlib.suppress(OSError):
                    installed.unlink()
                raise IrohLifecycleError(
                    f"installer returned unexpected Iroh binary path: {installed}"
                )
            receipt = self._make_receipt(selected, artifact, installed)
            try:
                _atomic_json(self.receipt_path, receipt)
            except IrohLifecycleError:
                with contextlib.suppress(OSError):
                    installed.unlink()
                raise
        return self.inspect(check=check)

    def update(
        self,
        *,
        version: str | None = None,
        allow_prerelease: bool = False,
        dry_run: bool = False,
        check: bool = False,
    ) -> dict[str, Any]:
        selected = self._select_version(version, allow_prerelease)
        current = _read_json(self.receipt_path)
        if current is None or not self.binary_path.is_file():
            raise IrohLifecycleError("Iroh is not installed; use the install command")
        if _sha256(self.binary_path) != current["binary_digest"]:
            raise IrohLifecycleError("managed Iroh binary digest does not match its receipt")
        current_version = str(current["version"])
        available = _version_key(selected) > _version_key(current_version)
        if check:
            result = self.inspect(check=True)
            result.update(
                operation="update-check",
                available=available,
                available_version=selected,
            )
            return result
        if not available:
            raise IrohLifecycleError(
                f"refusing non-upgrade from Iroh {current_version} to {selected}"
            )
        if dry_run:
            artifact = self._artifact()
            plan = self._plan("update", selected)
            plan["current_version"] = current_version
            plan.update(source=artifact["url"], digest=artifact["checksum_sha256"])
            return plan

        with self._lock():
            locked_current = _read_json(self.receipt_path)
            if locked_current is None or str(locked_current["version"]) != current_version:
                raise IrohLifecycleError("Iroh installation changed while acquiring update lock")
            if _sha256(self.binary_path) != locked_current["binary_digest"]:
                raise IrohLifecycleError("managed Iroh binary changed while acquiring update lock")
            paths = (
                self.binary_path,
                self.receipt_path,
                self.previous_binary_path,
                self.previous_receipt_path,
            )
            with tempfile.TemporaryDirectory(prefix=".iroh-lifecycle-", dir=self.bin_dir) as temp:
                snapshots = self._snapshot(paths, Path(temp))
                try:
                    self._retain_current()
                    artifact = self._artifact()
                    installed = self.installer.install()
                    if installed.resolve() != self.binary_path.resolve():
                        raise IrohLifecycleError(
                            f"installer returned unexpected Iroh binary path: {installed}"
                        )
                    _atomic_json(
                        self.receipt_path, self._make_receipt(selected, artifact, installed)
                    )
                except Exception as exc:
                    try:
                        self._restore(snapshots)
                    except IrohLifecycleError as restore_exc:
                        raise IrohLifecycleError(f"{exc}; {restore_exc}") from exc
                    raise
        return self.inspect(check=True)

    def inspect(self, *, check: bool = False) -> dict[str, Any]:
        receipt = _read_json(self.receipt_path)
        if receipt is None and not self.binary_path.exists():
            return {
                "installed": False,
                "binary": str(self.binary_path),
                "available_version": self.available_version,
            }
        if receipt is None or not self.binary_path.is_file():
            raise IrohLifecycleError("managed Iroh installation is incomplete")

        result = dict(receipt)
        result["installed"] = True
        result["previous_available"] = (
            self.previous_binary_path.is_file() and self.previous_receipt_path.is_file()
        )
        if check:
            actual = _sha256(self.binary_path)
            if actual != receipt["binary_digest"]:
                raise IrohLifecycleError("managed Iroh binary digest does not match its receipt")
            binary = str(self.binary_path.resolve())
            try:
                completed = self._run(
                    [binary, "--version"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise IrohLifecycleError(f"cannot execute managed Iroh binary: {exc}") from exc
            if getattr(completed, "returncode", 1) != 0:
                detail = str(getattr(completed, "stderr", "") or "").strip()
                raise IrohLifecycleError(
                    "managed Iroh version check failed" + (f": {detail}" if detail else "")
                )
            version_output = str(getattr(completed, "stdout", "") or "").strip()
            if receipt["version"] not in version_output:
                raise IrohLifecycleError(
                    "managed Iroh --version output does not match its install receipt"
                )
            result["healthy"] = True
            result["version_output"] = version_output
        return result

    def rollback(self, *, dry_run: bool = False, check: bool = False) -> dict[str, Any]:
        previous = _read_json(self.previous_receipt_path)
        if previous is None or not self.previous_binary_path.is_file():
            raise IrohLifecycleError("no retained Iroh version is available for rollback")
        if _sha256(self.previous_binary_path) != previous["binary_digest"]:
            raise IrohLifecycleError("retained Iroh binary digest does not match its receipt")
        if dry_run:
            plan = self._plan("rollback", str(previous["version"]))
            plan["current_version"] = (_read_json(self.receipt_path) or {}).get("version")
            return plan

        with self._lock():
            current = _read_json(self.receipt_path)
            previous = _read_json(self.previous_receipt_path)
            if (
                current is None
                or previous is None
                or not self.binary_path.is_file()
                or not self.previous_binary_path.is_file()
            ):
                raise IrohLifecycleError(
                    "managed Iroh installation is incomplete; refusing rollback"
                )
            if _sha256(self.previous_binary_path) != previous["binary_digest"]:
                raise IrohLifecycleError("retained Iroh binary changed while acquiring lock")
            paths = (
                self.binary_path,
                self.receipt_path,
                self.previous_binary_path,
                self.previous_receipt_path,
            )
            with tempfile.TemporaryDirectory(prefix=".iroh-lifecycle-", dir=self.bin_dir) as temp:
                snapshots = self._snapshot(paths, Path(temp))
                swap_binary = self.bin_dir / (self.binary_name + ".rollback-swap")
                try:
                    os.replace(self.binary_path, swap_binary)
                    os.replace(self.previous_binary_path, self.binary_path)
                    os.replace(swap_binary, self.previous_binary_path)
                    _atomic_json(self.receipt_path, previous)
                    _atomic_json(self.previous_receipt_path, current)
                except Exception as exc:
                    with contextlib.suppress(OSError):
                        swap_binary.unlink()
                    try:
                        self._restore(snapshots)
                    except IrohLifecycleError as restore_exc:
                        raise IrohLifecycleError(f"{exc}; {restore_exc}") from exc
                    if isinstance(exc, IrohInstallError):
                        raise
                    raise IrohLifecycleError(f"cannot atomically roll back Iroh: {exc}") from exc
        return self.inspect(check=check)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ipfs-kit-iroh", description=__doc__)
    parser.add_argument("--bin-dir", help="managed directory (defaults to IPFS_KIT_BIN_DIR)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    commands = parser.add_subparsers(dest="command", required=True)

    def common(command: argparse.ArgumentParser) -> None:
        # Also accept global operational options after the subcommand.
        command.add_argument(
            "--bin-dir", default=argparse.SUPPRESS, help="managed installation directory"
        )
        command.add_argument(
            "--json",
            action="store_true",
            default=argparse.SUPPRESS,
            help="emit machine-readable JSON",
        )

    def mutation(name: str, help_text: str, *, version: bool = False) -> None:
        command = commands.add_parser(name, help=help_text)
        common(command)
        if version:
            command.add_argument("--version", help="pinned sidecar version to use")
            command.add_argument(
                "--allow-prerelease",
                action="store_true",
                help="explicitly permit a prerelease",
            )
        command.add_argument("--dry-run", action="store_true", help="describe without changing files")
        command.add_argument("--check", action="store_true", help="verify the resulting state")

    mutation("install", "install the pinned verified sidecar", version=True)
    inspect_parser = commands.add_parser("inspect", help="show the managed installation")
    common(inspect_parser)
    inspect_parser.add_argument(
        "--check", action="store_true", help="verify digest and execute --version"
    )
    mutation("update", "update while retaining the current version", version=True)
    mutation("rollback", "restore the retained previous version")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        manager = IrohInstallManager(bin_dir=args.bin_dir)
        if args.command == "install":
            result = manager.install(
                version=args.version,
                allow_prerelease=args.allow_prerelease,
                dry_run=args.dry_run,
                check=args.check,
            )
        elif args.command == "inspect":
            result = manager.inspect(check=args.check)
        elif args.command == "update":
            result = manager.update(
                version=args.version,
                allow_prerelease=args.allow_prerelease,
                dry_run=args.dry_run,
                check=args.check,
            )
        else:
            result = manager.rollback(dry_run=args.dry_run, check=args.check)
    except IrohInstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # JSON is the stable output contract; --json remains an explicit affordance
    # for scripts and forwards compatibility with possible human formatting.
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
