"""Secure installer for the pinned IPFS Kit Iroh sidecar.

The installer is deliberately driven by ``resources/iroh-releases.json``. It
does not discover releases or checksums over the network. An unpublished or
withdrawn bundle, an unknown target, or incomplete provenance therefore fails
closed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import stat
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Callable, Mapping, Sequence


RELEASE_MANIFEST = Path(__file__).with_name("resources") / "iroh-releases.json"
DEFAULT_BIN_DIR = "~/.local/share/ipfs_kit_py/bin"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
MAX_ARCHIVE_MEMBERS = 1024
MAX_EXECUTABLE_SIZE = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


class IrohInstallError(RuntimeError):
    """Base class for an expected, safely reported installation failure."""


class UnsupportedTargetError(IrohInstallError):
    """The host target has no supported release artifact."""


class ReleaseUnavailableError(IrohInstallError):
    """The selected sidecar bundle is not published and installable."""


class DownloadVerificationError(IrohInstallError):
    """An artifact did not match its pinned size or digest."""


class AttestationVerificationError(IrohInstallError):
    """Artifact provenance verification failed."""


class UnsafeArchiveError(IrohInstallError):
    """An archive is malformed or unsafe to extract."""


def _normalise_os(value: str) -> str:
    aliases = {
        "linux": "linux",
        "darwin": "macos",
        "macos": "macos",
        "windows": "windows",
        "win32": "windows",
        "cygwin": "windows",
    }
    return aliases.get(value.strip().lower(), value.strip().lower())


def _normalise_arch(value: str) -> str:
    aliases = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "x64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
        "armv8": "aarch64",
        "armv8l": "aarch64",
    }
    normalized = value.strip().lower().replace("-", "_")
    return aliases.get(normalized, normalized)


def detect_platform(
    *,
    system: str | None = None,
    machine: str | None = None,
    libc: str | None = None,
) -> tuple[str, str, str]:
    """Return the normalized ``(os, architecture, libc)`` host target.

    Optional values make detection deterministic for callers and unit tests.
    Linux libc is intentionally limited to GNU and musl; guessing an unknown
    ABI could install a binary which cannot run.
    """

    os_name = _normalise_os(system if system is not None else platform.system())
    if os_name not in {"linux", "macos", "windows"}:
        raise UnsupportedTargetError(f"unsupported operating system: {os_name or '<unknown>'}")

    architecture = _normalise_arch(machine if machine is not None else platform.machine())
    if architecture not in {"x86_64", "aarch64"}:
        raise UnsupportedTargetError(
            f"unsupported architecture for {os_name}: {architecture or '<unknown>'}"
        )

    if os_name != "linux":
        return os_name, architecture, "none"

    libc_name = (libc if libc is not None else platform.libc_ver()[0]).strip().lower()
    if not libc_name:
        # Python can return an empty libc name on musl systems. Detect the
        # dynamic loader, but do not assume GNU when neither source identifies
        # the ABI.
        try:
            loader_names = [entry.name for entry in Path("/lib").glob("ld-musl-*.so.1")]
        except OSError:
            loader_names = []
        if loader_names:
            libc_name = "musl"

    if libc_name == "musl":
        return os_name, architecture, "musl"
    if libc_name in {"glibc", "gnu", "libc"}:
        return os_name, architecture, "gnu"
    raise UnsupportedTargetError(f"unsupported Linux libc: {libc_name or '<unknown>'}")


def load_release_manifest(
    path: str | os.PathLike[str] = RELEASE_MANIFEST,
) -> dict[str, Any]:
    """Load the pinned release record from disk without network discovery."""

    manifest_path = Path(path)
    try:
        with manifest_path.open("r", encoding="utf-8") as stream:
            release = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseUnavailableError(
            f"cannot load Iroh release manifest {manifest_path}: {exc}"
        ) from exc

    if not isinstance(release, dict) or release.get("schema_version") != 1:
        raise ReleaseUnavailableError("unsupported Iroh release manifest schema")
    return release


def _safe_member_name(name: str) -> PurePosixPath:
    """Validate an archive member name without resolving it on the host."""

    member = PurePosixPath(name.replace("\\", "/"))
    if (
        not name
        or member == PurePosixPath(".")
        or member.is_absolute()
        or (member.parts and member.parts[0].endswith(":"))
        or any(part in {"", ".", ".."} for part in member.parts)
    ):
        raise UnsafeArchiveError(f"unsafe archive member path: {name}")
    return member


def _validate_expansion(uncompressed_size: int, compressed_size: int) -> None:
    """Reject declared archive expansion that is implausible for a binary."""

    if compressed_size <= 0 or uncompressed_size > compressed_size * MAX_COMPRESSION_RATIO:
        raise UnsafeArchiveError("sidecar executable has an unsafe compression ratio")


def _copy_bounded(source: BinaryIO, destination: BinaryIO, expected_size: int) -> None:
    """Copy exactly the declared member size and reject decoder overrun."""

    remaining = expected_size
    while remaining:
        chunk = source.read(min(DOWNLOAD_CHUNK_SIZE, remaining))
        if not chunk:
            raise UnsafeArchiveError("sidecar executable is truncated")
        destination.write(chunk)
        remaining -= len(chunk)
    if source.read(1):
        raise UnsafeArchiveError("sidecar executable exceeds its declared size")


class IrohInstaller:
    """Install a verified Iroh sidecar artifact for the current host."""

    def __init__(
        self,
        resources: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        *,
        release_manifest: Mapping[str, Any] | None = None,
        manifest_path: str | os.PathLike[str] = RELEASE_MANIFEST,
        opener: Callable[..., BinaryIO] | None = None,
        command_runner: Callable[..., Any] | None = None,
    ) -> None:
        self.resources = dict(resources or {})
        self.metadata = dict(metadata or {})
        self.release = (
            dict(release_manifest)
            if release_manifest is not None
            else load_release_manifest(manifest_path)
        )

        configured_bin_dir = self.metadata.get("bin_dir") or os.environ.get("IPFS_KIT_BIN_DIR")
        self.bin_dir = Path(configured_bin_dir or DEFAULT_BIN_DIR).expanduser().resolve()
        self._opener = opener or urllib.request.urlopen
        self._run = command_runner or subprocess.run

    def select_artifact(
        self,
        *,
        system: str | None = None,
        machine: str | None = None,
        libc: str | None = None,
    ) -> dict[str, Any]:
        """Select and validate the pinned artifact for a target."""

        sidecar = self.release.get("sidecar")
        bundle = self.release.get("release_bundle")
        verification = self.release.get("verification")
        if not isinstance(sidecar, Mapping) or not isinstance(bundle, Mapping):
            raise ReleaseUnavailableError("release manifest has no sidecar bundle")
        if not isinstance(verification, Mapping):
            raise ReleaseUnavailableError("release manifest has no verification policy")
        if bundle.get("status") != "supported":
            raise ReleaseUnavailableError("Iroh sidecar release bundle is not supported")
        if sidecar.get("distribution_status") != "published":
            raise ReleaseUnavailableError(
                f"Iroh sidecar {sidecar.get('version', '<unknown>')} is not published"
            )
        if verification.get("fail_closed") is not True:
            raise ReleaseUnavailableError(
                "release manifest does not enable fail-closed verification"
            )

        target = detect_platform(system=system, machine=machine, libc=libc)
        platforms = self.release.get("platforms")
        if not isinstance(platforms, list):
            raise ReleaseUnavailableError("release manifest has no platform matrix")
        matches = [
            item
            for item in platforms
            if isinstance(item, Mapping)
            and (item.get("os"), item.get("arch"), item.get("libc")) == target
        ]
        if len(matches) != 1:
            raise UnsupportedTargetError(f"unsupported Iroh target: {'_'.join(target)}")

        artifact = dict(matches[0])
        if artifact.get("installable") is not True:
            raise ReleaseUnavailableError(
                f"Iroh target {artifact.get('id', '_'.join(target))} is not installable"
            )
        self._validate_artifact_metadata(artifact)
        return artifact

    def _validate_artifact_metadata(self, artifact: Mapping[str, Any]) -> None:
        """Require complete, immutable artifact identity and a trusted URL."""

        url = artifact.get("url")
        digest = artifact.get("checksum_sha256")
        expected_size = artifact.get("size")
        if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size <= 0:
            raise ReleaseUnavailableError("artifact has no valid pinned size")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or digest != digest.lower()
        ):
            raise ReleaseUnavailableError("artifact has no valid pinned SHA-256 digest")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ReleaseUnavailableError("artifact SHA-256 digest is not hexadecimal") from exc
        if not isinstance(url, str) or not url:
            raise ReleaseUnavailableError("artifact has no pinned URL")

        policy = self.release.get("verification", {}).get("sidecar_artifacts", {})
        repository_url = policy.get("release_repository") if isinstance(policy, Mapping) else None
        if not isinstance(repository_url, str):
            raise ReleaseUnavailableError("artifact verification has no release repository")
        repository = urllib.parse.urlsplit(repository_url)
        parsed = urllib.parse.urlsplit(url)
        expected_prefix = repository.path.rstrip("/") + "/releases/download/"
        if (
            repository.scheme != "https"
            or repository.netloc != "github.com"
            or parsed.scheme != "https"
            or parsed.netloc != repository.netloc
            or not parsed.path.startswith(expected_prefix)
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ReleaseUnavailableError("artifact URL is outside the pinned release repository")

        if artifact.get("archive_format") not in {"tar.gz", "zip"}:
            raise ReleaseUnavailableError("unsupported artifact archive format")
        executable = artifact.get("executable")
        if not isinstance(executable, str) or not executable or PurePosixPath(executable).name != executable:
            raise ReleaseUnavailableError("artifact executable name is missing or unsafe")

    def _download(self, artifact: Mapping[str, Any], destination: Path) -> None:
        """Stream an artifact to a new file while enforcing size and digest."""

        expected_size = int(artifact["size"])
        received = 0
        digest = hashlib.sha256()
        try:
            with self._opener(str(artifact["url"]), timeout=60) as response:
                with destination.open("xb") as output:
                    while True:
                        chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                        if not chunk:
                            break
                        if not isinstance(chunk, bytes):
                            raise DownloadVerificationError("Iroh artifact response was not binary")
                        received += len(chunk)
                        if received > expected_size:
                            raise DownloadVerificationError("download exceeds its pinned size")
                        output.write(chunk)
                        digest.update(chunk)
                    output.flush()
                    os.fsync(output.fileno())
        except DownloadVerificationError:
            raise
        except (OSError, ValueError) as exc:
            raise DownloadVerificationError(f"Iroh artifact download failed: {exc}") from exc

        if received != expected_size:
            raise DownloadVerificationError(
                f"truncated Iroh artifact: expected {expected_size} bytes, received {received}"
            )
        if not hmac.compare_digest(digest.hexdigest(), str(artifact["checksum_sha256"]).lower()):
            raise DownloadVerificationError("Iroh artifact SHA-256 mismatch")

    def _verify_attestation(self, archive: Path) -> None:
        """Verify the repository-bound GitHub artifact attestation."""

        try:
            artifact_policy = self.release["verification"]["sidecar_artifacts"]
            policy = artifact_policy["attestation"]
            command_template = policy["verification_command"]
            repository_url = artifact_policy["release_repository"]
        except (KeyError, TypeError) as exc:
            raise AttestationVerificationError("artifact attestation policy is missing") from exc

        if not isinstance(repository_url, str) or not isinstance(policy, Mapping):
            raise AttestationVerificationError("artifact attestation policy is missing")

        repository = urllib.parse.urlsplit(repository_url).path.strip("/")
        expected_command = [
            "gh",
            "attestation",
            "verify",
            "{artifact}",
            "--repo",
            repository,
        ]
        if (
            policy.get("required") is not True
            or policy.get("authority") != "github-artifact-attestations"
            or policy.get("detached_upstream_signatures_available") is not False
            or not isinstance(command_template, list)
            or command_template != expected_command
        ):
            raise AttestationVerificationError(
                "artifact attestation is not required by the release"
            )

        command = [str(archive) if value == "{artifact}" else value for value in command_template]
        try:
            result = self._run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise AttestationVerificationError(
                f"cannot verify artifact attestation: {exc}"
            ) from exc

        if getattr(result, "returncode", 1) != 0:
            detail = str(getattr(result, "stderr", "")).strip()
            message = "artifact attestation verification failed"
            if detail:
                message += f": {detail}"
            raise AttestationVerificationError(message)

    def _extract_executable(
        self,
        archive: Path,
        artifact: Mapping[str, Any],
        output: Path,
    ) -> None:
        """Extract exactly one bounded regular executable into a new file."""

        executable = str(artifact["executable"])
        archive_format = artifact["archive_format"]
        try:
            if archive_format == "tar.gz":
                with tarfile.open(archive, mode="r:gz") as bundle:
                    members = bundle.getmembers()
                    if len(members) > MAX_ARCHIVE_MEMBERS:
                        raise UnsafeArchiveError("archive has too many members")
                    candidates = []
                    for member in members:
                        member_path = _safe_member_name(member.name)
                        if member.issym() or member.islnk():
                            raise UnsafeArchiveError("archive contains a symbolic link")
                        if member_path.name != executable:
                            continue
                        if not member.isfile():
                            raise UnsafeArchiveError(
                                "sidecar archive member is not a regular file"
                            )
                        if member.size <= 0 or member.size > MAX_EXECUTABLE_SIZE:
                            raise UnsafeArchiveError("sidecar executable has an unsafe size")
                        candidates.append(member)
                    if len(candidates) != 1:
                        raise UnsafeArchiveError(
                            "archive must contain exactly one sidecar executable"
                        )
                    source = bundle.extractfile(candidates[0])
                    if source is None:
                        raise UnsafeArchiveError("cannot read sidecar archive member")
                    _validate_expansion(candidates[0].size, archive.stat().st_size)
                    with source, output.open("xb") as destination:
                        _copy_bounded(source, destination, candidates[0].size)
                        destination.flush()
                        os.fsync(destination.fileno())
            elif archive_format == "zip":
                with zipfile.ZipFile(archive, mode="r") as bundle:
                    members = bundle.infolist()
                    if len(members) > MAX_ARCHIVE_MEMBERS:
                        raise UnsafeArchiveError("archive has too many members")
                    candidates = []
                    for member in members:
                        member_path = _safe_member_name(member.filename)
                        unix_mode = (member.external_attr >> 16) & 0xFFFF
                        if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
                            raise UnsafeArchiveError("archive contains a symbolic link")
                        if member_path.name != executable:
                            continue
                        if member.is_dir():
                            raise UnsafeArchiveError(
                                "sidecar archive member is not a regular file"
                            )
                        file_type = stat.S_IFMT(unix_mode)
                        if file_type not in {0, stat.S_IFREG}:
                            raise UnsafeArchiveError(
                                "sidecar archive member is not a regular file"
                            )
                        if member.file_size <= 0 or member.file_size > MAX_EXECUTABLE_SIZE:
                            raise UnsafeArchiveError("sidecar executable has an unsafe size")
                        candidates.append(member)
                    if len(candidates) != 1:
                        raise UnsafeArchiveError(
                            "archive must contain exactly one sidecar executable"
                        )
                    _validate_expansion(candidates[0].file_size, candidates[0].compress_size)
                    with bundle.open(candidates[0], mode="r") as source:
                        with output.open("xb") as destination:
                            _copy_bounded(source, destination, candidates[0].file_size)
                            destination.flush()
                            os.fsync(destination.fileno())
            else:  # Guarded by metadata validation; retained for direct method callers.
                raise UnsafeArchiveError("unsupported artifact archive format")
        except UnsafeArchiveError:
            raise
        except (OSError, tarfile.TarError, zipfile.BadZipFile, EOFError, RuntimeError) as exc:
            raise UnsafeArchiveError(f"invalid Iroh artifact archive: {exc}") from exc

        if not output.is_file() or output.stat().st_size <= 0:
            raise UnsafeArchiveError("extracted sidecar is empty or not a regular file")

    def install(
        self,
        *,
        system: str | None = None,
        machine: str | None = None,
        libc: str | None = None,
    ) -> Path:
        """Download, verify, and atomically install the selected sidecar."""

        artifact = self.select_artifact(system=system, machine=machine, libc=libc)
        try:
            self.bin_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
        except OSError as exc:
            raise IrohInstallError(f"cannot create binary destination: {exc}") from exc
        if not self.bin_dir.is_dir():
            raise IrohInstallError(f"binary destination is not a directory: {self.bin_dir}")

        executable = str(artifact["executable"])
        destination = self.bin_dir / executable
        try:
            with tempfile.TemporaryDirectory(prefix=".iroh-install-", dir=self.bin_dir) as temp:
                staging_dir = Path(temp)
                archive = staging_dir / "artifact"
                staged_binary = staging_dir / executable
                self._download(artifact, archive)
                self._verify_attestation(archive)
                self._extract_executable(archive, artifact, staged_binary)
                try:
                    staged_binary.chmod(0o755)
                except OSError as exc:
                    raise IrohInstallError(
                        f"cannot make Iroh sidecar executable: {exc}"
                    ) from exc
                if not os.access(staged_binary, os.X_OK):
                    raise IrohInstallError("extracted Iroh sidecar is not executable")

                staged_binary.replace(destination)
                self._fsync_directory(self.bin_dir)
        except IrohInstallError:
            raise
        except OSError as exc:
            raise IrohInstallError(f"cannot install Iroh sidecar: {exc}") from exc

        if not destination.is_file() or not os.access(destination, os.X_OK):
            raise IrohInstallError("installed Iroh sidecar is not executable")
        return destination

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        """Persist an atomic rename where directory fsync is supported."""

        descriptor: int | None = None
        try:
            descriptor = os.open(directory, os.O_RDONLY)
            os.fsync(descriptor)
        except OSError:
            # Windows and some filesystems do not allow opening directories.
            pass
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def install_iroh_binary(self, target: str = "") -> Path:
        """Compatibility alias for the managed sidecar installer."""

        del target
        return self.install()

    def install_iroh_daemon(self, target: str = "") -> Path:
        """Compatibility alias for callers using daemon installer naming."""

        del target
        return self.install()


class install_iroh(IrohInstaller):
    """Backward-compatible lowercase installer name used by ipfs_kit_py."""


def main(argv: Sequence[str] | None = None) -> int:
    """Delegate command handling to the explicit lifecycle CLI when present."""

    from .iroh_install_cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI module
    raise SystemExit(main())
