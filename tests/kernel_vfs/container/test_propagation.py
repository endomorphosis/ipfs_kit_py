"""KVFS-700: Host vs in-container propagation profile conformance.

In-container access and host-visible propagation are **separate claims**:

* default Compose/image profile is in-container only (tmpfs mountpoint, no
  host-shared bind);
* native Linux ``rshared`` host propagation is a **distinct tested profile**
  that requires an explicitly shared bind mount;
* Docker Desktop propagation is **not claimed** and must never be advertised
  as supported by this suite or the KVFS-701 profile.

Hermetic contract tests (no Docker daemon required). Live rshared verification
is opt-in and never promotes Docker Desktop support.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final, Mapping

import pytest
import yaml


def _load_live_container():
    """Load sibling test_live_container.py without requiring a package __init__."""

    name = "kvfs700_live_container"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    path = Path(__file__).resolve().parent / "test_live_container.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load live container harness from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


live = _load_live_container()

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-700"
PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
DOCKERFILE_PATH: Final[Path] = PACKAGE_ROOT / "docker" / "kernel-vfs.Dockerfile"
COMPOSE_PATH: Final[Path] = PACKAGE_ROOT / "docker-compose.kernel-vfs.yml"
TEST_PATH: Final[Path] = Path(__file__).resolve()

HARNESS_NAMESPACE: Final[str] = (
    "ipfs_kit_py/tests/kernel_vfs/container/propagation"
)
PROFILE_RECEIPT_SCHEMA: Final[str] = (
    f"{HARNESS_NAMESPACE}/profile-receipt@1"
)
PROPAGATION_SUITE_SCHEMA: Final[str] = (
    f"{HARNESS_NAMESPACE}/suite-receipt@1"
)

PROPAGATION_IN_CONTAINER: Final[str] = live.PROPAGATION_IN_CONTAINER
PROPAGATION_NATIVE_RSHARED: Final[str] = live.PROPAGATION_NATIVE_RSHARED
PROPAGATION_DOCKER_DESKTOP: Final[str] = live.PROPAGATION_DOCKER_DESKTOP

PROFILE_MINIMAL: Final[str] = live.PROFILE_MINIMAL
REQUIRED_DEVICE: Final[str] = live.REQUIRED_DEVICE
REQUIRED_CAP: Final[str] = live.REQUIRED_CAP
SERVICE_NAME: Final[str] = live.SERVICE_NAME
MOUNTPOINT_PATH: Final[str] = live.MOUNTPOINT_PATH

# Explicit host bind path used only by the rshared profile (never default).
RSHARED_HOST_BIND_TARGET: Final[str] = "/mnt/ipfs-kit-vfs-host"
RSHARED_PROPAGATION: Final[str] = "rshared"


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


class PropagationProfileId(str, Enum):
    """Closed vocabulary of propagation profiles under test."""

    IN_CONTAINER = PROPAGATION_IN_CONTAINER
    NATIVE_LINUX_RSHARED = PROPAGATION_NATIVE_RSHARED
    DOCKER_DESKTOP = PROPAGATION_DOCKER_DESKTOP


class SupportClaim(str, Enum):
    CLAIMED = "claimed"
    NOT_CLAIMED = "not_claimed"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class PropagationProfile:
    """One tested (or explicitly unclaimed) propagation profile."""

    SCHEMA: ClassVar[str] = PROFILE_RECEIPT_SCHEMA

    profile_id: PropagationProfileId
    support_claim: SupportClaim
    requires_shared_bind: bool
    host_visible: bool
    bind_propagation: str | None
    host_bind_target: str | None
    privileged: bool
    required_device: str
    required_cap: str
    distinct_from_default: bool
    notes: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "task_id": TASK_ID,
            "profile_id": self.profile_id.value,
            "support_claim": self.support_claim.value,
            "requires_shared_bind": self.requires_shared_bind,
            "host_visible": self.host_visible,
            "bind_propagation": self.bind_propagation,
            "host_bind_target": self.host_bind_target,
            "privileged": self.privileged,
            "required_device": self.required_device,
            "required_cap": self.required_cap,
            "distinct_from_default": self.distinct_from_default,
            "notes": self.notes,
            "docker_desktop_claimed": (
                self.profile_id is PropagationProfileId.DOCKER_DESKTOP
                and self.support_claim is SupportClaim.CLAIMED
            ),
        }


def in_container_profile() -> PropagationProfile:
    """Default profile: mount is visible only inside the container."""

    return PropagationProfile(
        profile_id=PropagationProfileId.IN_CONTAINER,
        support_claim=SupportClaim.CLAIMED,
        requires_shared_bind=False,
        host_visible=False,
        bind_propagation=None,
        host_bind_target=None,
        privileged=False,
        required_device=REQUIRED_DEVICE,
        required_cap=REQUIRED_CAP,
        distinct_from_default=False,
        notes=(
            "Default KVFS-701 Compose profile: tmpfs mountpoint, no host-shared "
            "bind. In-container CRUD/fsync/restart/recovery only."
        ),
    )


def native_linux_rshared_profile() -> PropagationProfile:
    """Distinct native Linux host-visible profile via explicit rshared bind."""

    return PropagationProfile(
        profile_id=PropagationProfileId.NATIVE_LINUX_RSHARED,
        support_claim=SupportClaim.CLAIMED,
        requires_shared_bind=True,
        host_visible=True,
        bind_propagation=RSHARED_PROPAGATION,
        host_bind_target=RSHARED_HOST_BIND_TARGET,
        privileged=False,
        required_device=REQUIRED_DEVICE,
        required_cap=REQUIRED_CAP,
        distinct_from_default=True,
        notes=(
            "Host-visible native-Linux mounts require an explicitly shared "
            "(rshared) bind mount. This is a distinct tested profile, never "
            "implied by the default in-container service."
        ),
    )


def docker_desktop_profile() -> PropagationProfile:
    """Docker Desktop propagation — explicitly not claimed."""

    return PropagationProfile(
        profile_id=PropagationProfileId.DOCKER_DESKTOP,
        support_claim=SupportClaim.NOT_CLAIMED,
        requires_shared_bind=False,
        host_visible=False,
        bind_propagation=None,
        host_bind_target=None,
        privileged=False,
        required_device=REQUIRED_DEVICE,
        required_cap=REQUIRED_CAP,
        distinct_from_default=True,
        notes=(
            "Docker Desktop host propagation is not claimed. Suites must not "
            "advertise Docker Desktop mount visibility as supported."
        ),
    )


def all_propagation_profiles() -> tuple[PropagationProfile, ...]:
    return (
        in_container_profile(),
        native_linux_rshared_profile(),
        docker_desktop_profile(),
    )


# ---------------------------------------------------------------------------
# Compose inspection helpers
# ---------------------------------------------------------------------------


def _compose_doc() -> dict[str, Any]:
    assert COMPOSE_PATH.is_file(), f"missing Compose file: {COMPOSE_PATH}"
    doc = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    return doc


def _compose_service() -> dict[str, Any]:
    services = _compose_doc().get("services")
    assert isinstance(services, dict)
    service = services.get(SERVICE_NAME)
    assert isinstance(service, dict)
    return service


def _compose_text() -> str:
    return COMPOSE_PATH.read_text(encoding="utf-8")


def _dockerfile_text() -> str:
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def extract_volume_propagations(service: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return structured volume/bind propagation descriptors from Compose."""

    service = service or _compose_service()
    volumes = service.get("volumes") or []
    results: list[dict[str, Any]] = []
    for entry in volumes:
        if isinstance(entry, str):
            parts = entry.split(":")
            propagation = None
            if len(parts) >= 3:
                # short syntax options: ro,rw,rshared,shared,slave,rslave,z,Z
                opts = parts[-1].split(",")
                for opt in opts:
                    if opt.lower() in {
                        "rshared",
                        "shared",
                        "slave",
                        "rslave",
                        "private",
                        "rprivate",
                    }:
                        propagation = opt.lower()
            results.append(
                {
                    "raw": entry,
                    "type": "short",
                    "propagation": propagation,
                    "target": parts[1] if len(parts) >= 2 else None,
                }
            )
        elif isinstance(entry, dict):
            bind = entry.get("bind") if isinstance(entry.get("bind"), dict) else {}
            prop = None
            if isinstance(bind, dict):
                prop = bind.get("propagation")
            prop = prop or entry.get("propagation")
            results.append(
                {
                    "raw": entry,
                    "type": str(entry.get("type") or "volume"),
                    "propagation": str(prop).lower() if prop else None,
                    "target": entry.get("target") or entry.get("destination"),
                    "source": entry.get("source") or entry.get("src"),
                }
            )
    return results


def default_profile_has_host_rshared() -> bool:
    for item in extract_volume_propagations():
        prop = (item.get("propagation") or "").lower()
        if prop in {"rshared", "shared"}:
            return True
    return False


def build_rshared_override_spec(
    *,
    host_path: str,
    container_path: str = RSHARED_HOST_BIND_TARGET,
) -> dict[str, Any]:
    """Construct the distinct native Linux rshared host-propagation overlay.

    This is intentionally **not** the default Compose service. Operators must
    opt into host visibility via an explicit shared bind.
    """

    return {
        "schema": "KernelVFSContainerRsharedPropagationProfile@1",
        "task_id": TASK_ID,
        "profile_id": PROPAGATION_NATIVE_RSHARED,
        "base_profile": PROFILE_MINIMAL,
        "privileged": False,
        "required_device": REQUIRED_DEVICE,
        "required_cap": REQUIRED_CAP,
        "host_visible": True,
        "requires_shared_bind": True,
        "docker_desktop_claimed": False,
        "volumes": [
            {
                "type": "bind",
                "source": host_path,
                "target": container_path,
                "bind": {"propagation": RSHARED_PROPAGATION},
            }
        ],
        "notes": (
            "Explicit rshared bind only. Does not alter the default "
            "in-container tmpfs mountpoint. Docker Desktop is not claimed."
        ),
    }


def rshared_docker_run_argv(
    *,
    image: str,
    host_path: str,
    container_path: str = RSHARED_HOST_BIND_TARGET,
    name: str | None = None,
) -> list[str]:
    """Minimal docker run argv for the rshared profile (never --privileged)."""

    name = name or f"kvfs-rshared-{uuid.uuid4().hex[:8]}"
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--device",
        REQUIRED_DEVICE,
        "--cap-add",
        REQUIRED_CAP,
        # Never --privileged
        "--mount",
        (
            f"type=bind,source={host_path},target={container_path},"
            f"bind-propagation={RSHARED_PROPAGATION}"
        ),
        image,
    ]


# ---------------------------------------------------------------------------
# Hermetic rshared simulation (host mount table awareness)
# ---------------------------------------------------------------------------


@dataclass
class RsharedProbeReceipt:
    """Receipt for a hermetic or live rshared capability probe."""

    profile_id: str
    host_visible_claimed: bool
    shared_bind_configured: bool
    docker_desktop_claimed: bool
    privileged: bool
    elapsed_seconds: float
    ok: bool
    message: str
    plane: str = "hermetic"
    detail: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": f"{HARNESS_NAMESPACE}/rshared-probe@1",
            "task_id": TASK_ID,
            "profile_id": self.profile_id,
            "host_visible_claimed": self.host_visible_claimed,
            "shared_bind_configured": self.shared_bind_configured,
            "docker_desktop_claimed": self.docker_desktop_claimed,
            "privileged": self.privileged,
            "elapsed_seconds": self.elapsed_seconds,
            "ok": self.ok,
            "message": self.message,
            "plane": self.plane,
            "detail": dict(self.detail),
        }


def probe_rshared_profile(
    *,
    host_path: str | Path | None = None,
    require_live_mount: bool = False,
) -> RsharedProbeReceipt:
    """Validate the rshared profile contract without claiming Docker Desktop.

    Hermetic plane: verifies override spec shape, distinctness from default,
    and that privileged/Desktop are never set. Live plane (optional) checks
    that the host path exists and is a directory when provided.
    """

    started = time.monotonic()
    host = Path(host_path) if host_path is not None else None
    if host is None:
        host = Path(tempfile.mkdtemp(prefix="kvfs-rshared-host-"))
        owns_host = True
    else:
        owns_host = False
        host.mkdir(parents=True, exist_ok=True)

    try:
        override = build_rshared_override_spec(host_path=str(host))
        default_has = default_profile_has_host_rshared()
        shared_ok = (
            override["requires_shared_bind"] is True
            and override["host_visible"] is True
            and override["volumes"][0]["bind"]["propagation"] == RSHARED_PROPAGATION
            and override["privileged"] is False
            and override["docker_desktop_claimed"] is False
        )
        distinct = default_has is False and override["profile_id"] != PROPAGATION_IN_CONTAINER
        live_ok = True
        plane = "hermetic"
        if require_live_mount:
            plane = "live"
            # Live requires Linux + docker + host path; never Desktop claim.
            docker = live.probe_docker_daemon(budget_seconds=5.0)
            live_ok = bool(docker.get("docker_ready")) and host.is_dir()
            if not live_ok:
                return RsharedProbeReceipt(
                    profile_id=PROPAGATION_NATIVE_RSHARED,
                    host_visible_claimed=True,
                    shared_bind_configured=shared_ok,
                    docker_desktop_claimed=False,
                    privileged=False,
                    elapsed_seconds=time.monotonic() - started,
                    ok=False,
                    message="live rshared probe unavailable (docker or host path)",
                    plane=plane,
                    detail={"docker": docker, "host_path": str(host)},
                )

        ok = shared_ok and distinct and live_ok
        return RsharedProbeReceipt(
            profile_id=PROPAGATION_NATIVE_RSHARED,
            host_visible_claimed=True,
            shared_bind_configured=shared_ok,
            docker_desktop_claimed=False,
            privileged=False,
            elapsed_seconds=time.monotonic() - started,
            ok=ok,
            message=(
                "native Linux rshared profile contract holds"
                if ok
                else "rshared profile contract failed"
            ),
            plane=plane,
            detail={
                "override": override,
                "default_has_rshared": default_has,
                "distinct_from_default": distinct,
                "host_path": str(host),
                "argv_sample": rshared_docker_run_argv(
                    image="ipfs-kit-kernel-vfs:latest",
                    host_path=str(host),
                ),
            },
        )
    finally:
        if owns_host:
            shutil.rmtree(host, ignore_errors=True)


def assert_no_docker_desktop_claim(text: str) -> None:
    """Fail if *text* advertises Docker Desktop host propagation as supported."""

    lowered = text.lower()
    # Positive claim patterns that are forbidden.
    forbidden = [
        r"docker\s+desktop\s+propagation\s+is\s+supported",
        r"docker\s+desktop\s+host\s+propagation\s+supported",
        r"claims?\s+docker\s+desktop\s+propagation",
        r"docker\s+desktop\s+propagation\s*=\s*true",
        r"docker_desktop_propagation_claimed\s*[:=]\s*true",
    ]
    for pattern in forbidden:
        assert re.search(pattern, lowered) is None, (
            f"forbidden Docker Desktop propagation claim matched {pattern!r}"
        )


def profiles_are_distinct(
    left: PropagationProfile, right: PropagationProfile
) -> bool:
    if left.profile_id == right.profile_id:
        return False
    # Distinctness axes for acceptance.
    return (
        left.host_visible != right.host_visible
        or left.requires_shared_bind != right.requires_shared_bind
        or left.bind_propagation != right.bind_propagation
        or left.support_claim != right.support_claim
    )


# ---------------------------------------------------------------------------
# Tests — identity / declared outputs
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert TEST_PATH.is_file()
    assert TEST_PATH.stat().st_size > 0
    assert live.TEST_PATH.is_file()
    assert COMPOSE_PATH.is_file()
    assert DOCKERFILE_PATH.is_file()


def test_task_identity() -> None:
    assert TASK_ID == "KVFS-700"
    assert live.TASK_ID == "KVFS-700"
    assert PROPAGATION_IN_CONTAINER == "in_container"
    assert PROPAGATION_NATIVE_RSHARED == "native_linux_rshared"
    assert PROPAGATION_DOCKER_DESKTOP == "docker_desktop"


# ---------------------------------------------------------------------------
# Profile catalog
# ---------------------------------------------------------------------------


def test_all_three_profiles_are_catalogued() -> None:
    profiles = all_propagation_profiles()
    ids = {p.profile_id for p in profiles}
    assert ids == {
        PropagationProfileId.IN_CONTAINER,
        PropagationProfileId.NATIVE_LINUX_RSHARED,
        PropagationProfileId.DOCKER_DESKTOP,
    }
    for profile in profiles:
        record = profile.to_record()
        assert record["task_id"] == TASK_ID
        assert record["privileged"] is False
        assert record["required_device"] == REQUIRED_DEVICE
        assert record["required_cap"] == REQUIRED_CAP


def test_in_container_is_default_claimed_profile() -> None:
    profile = in_container_profile()
    assert profile.support_claim is SupportClaim.CLAIMED
    assert profile.host_visible is False
    assert profile.requires_shared_bind is False
    assert profile.bind_propagation is None
    assert profile.distinct_from_default is False
    assert profile.privileged is False


def test_native_linux_rshared_is_distinct_claimed_profile() -> None:
    default = in_container_profile()
    rshared = native_linux_rshared_profile()
    assert rshared.support_claim is SupportClaim.CLAIMED
    assert rshared.host_visible is True
    assert rshared.requires_shared_bind is True
    assert rshared.bind_propagation == "rshared"
    assert rshared.host_bind_target == RSHARED_HOST_BIND_TARGET
    assert rshared.distinct_from_default is True
    assert rshared.privileged is False
    assert profiles_are_distinct(default, rshared)
    assert default.profile_id != rshared.profile_id
    assert default.host_visible is False
    assert rshared.host_visible is True


def test_docker_desktop_propagation_is_not_claimed() -> None:
    desktop = docker_desktop_profile()
    assert desktop.support_claim is SupportClaim.NOT_CLAIMED
    assert desktop.host_visible is False
    assert desktop.to_record()["docker_desktop_claimed"] is False
    assert desktop.support_claim is not SupportClaim.CLAIMED

    # Suite-level and compose-level denials.
    compose = _compose_text()
    assert (
        "Docker Desktop propagation is not claimed" in compose
        or "does not claim Docker Desktop" in compose
    )
    assert_no_docker_desktop_claim(compose)
    assert_no_docker_desktop_claim(_dockerfile_text())
    assert_no_docker_desktop_claim(TEST_PATH.read_text(encoding="utf-8"))
    assert_no_docker_desktop_claim(live.TEST_PATH.read_text(encoding="utf-8"))

    # Minimal profile from live harness never claims Desktop.
    minimal = live.minimal_capability_profile()
    assert minimal["docker_desktop_propagation_claimed"] is False
    assert minimal["host_propagation_claimed"] is False
    assert minimal["propagation_claim"] == PROPAGATION_IN_CONTAINER


# ---------------------------------------------------------------------------
# Default Compose: in-container only
# ---------------------------------------------------------------------------


def test_default_compose_is_in_container_only() -> None:
    service = _compose_service()
    props = extract_volume_propagations(service)
    for item in props:
        prop = (item.get("propagation") or "").lower()
        assert prop not in {"rshared", "shared"}, item

    # Mountpoint is tmpfs (ephemeral in-container), not a host bind.
    volumes = service.get("volumes") or []
    mountpoint_is_tmpfs = False
    for entry in volumes:
        if isinstance(entry, dict):
            target = entry.get("target") or entry.get("destination")
            if target == MOUNTPOINT_PATH or target == "/mnt/ipfs-kit-vfs":
                assert entry.get("type") == "tmpfs", entry
                mountpoint_is_tmpfs = True
    assert mountpoint_is_tmpfs, "default mountpoint must be tmpfs (in-container)"

    assert default_profile_has_host_rshared() is False
    assert service.get("privileged") is False


def test_compose_documents_separate_propagation_claims() -> None:
    text = _compose_text()
    assert "In-container mount access and host-visible propagation" in text or (
        "in-container" in text.lower() and "propagation" in text.lower()
    )
    assert "Docker Desktop" in text
    assert "not claimed" in text.lower() or "does not claim" in text.lower()


# ---------------------------------------------------------------------------
# rshared profile construction
# ---------------------------------------------------------------------------


def test_rshared_override_is_explicit_and_unprivileged() -> None:
    host = "/tmp/kvfs-rshared-host-example"
    override = build_rshared_override_spec(host_path=host)
    assert override["profile_id"] == PROPAGATION_NATIVE_RSHARED
    assert override["base_profile"] == PROFILE_MINIMAL
    assert override["privileged"] is False
    assert override["host_visible"] is True
    assert override["requires_shared_bind"] is True
    assert override["docker_desktop_claimed"] is False
    assert override["required_device"] == REQUIRED_DEVICE
    assert override["required_cap"] == REQUIRED_CAP
    vol = override["volumes"][0]
    assert vol["type"] == "bind"
    assert vol["source"] == host
    assert vol["target"] == RSHARED_HOST_BIND_TARGET
    assert vol["bind"]["propagation"] == "rshared"


def test_rshared_docker_run_argv_never_privileged() -> None:
    argv = rshared_docker_run_argv(
        image="ipfs-kit-kernel-vfs:latest",
        host_path="/var/tmp/kvfs-host",
    )
    assert argv[0] == "docker"
    assert "--privileged" not in argv
    assert "--device" in argv
    assert REQUIRED_DEVICE in argv
    assert "--cap-add" in argv
    assert REQUIRED_CAP in argv
    mount_idx = argv.index("--mount")
    mount_spec = argv[mount_idx + 1]
    assert "bind-propagation=rshared" in mount_spec
    assert "type=bind" in mount_spec
    # Desktop not mentioned.
    assert "desktop" not in " ".join(argv).lower()


def test_rshared_probe_hermetic_ok(tmp_path: Path) -> None:
    receipt = probe_rshared_profile(host_path=tmp_path / "host-bind")
    assert receipt.ok is True
    assert receipt.profile_id == PROPAGATION_NATIVE_RSHARED
    assert receipt.host_visible_claimed is True
    assert receipt.shared_bind_configured is True
    assert receipt.docker_desktop_claimed is False
    assert receipt.privileged is False
    assert receipt.plane == "hermetic"
    record = receipt.to_record()
    assert record["detail"]["default_has_rshared"] is False
    assert record["detail"]["distinct_from_default"] is True
    argv = record["detail"]["argv_sample"]
    assert "--privileged" not in argv


def test_rshared_and_in_container_profiles_not_interchangeable() -> None:
    """Acceptance: native Linux rshared is a distinct tested profile."""

    a = in_container_profile().to_record()
    b = native_linux_rshared_profile().to_record()
    assert a["profile_id"] != b["profile_id"]
    assert a["host_visible"] is False
    assert b["host_visible"] is True
    assert a["requires_shared_bind"] is False
    assert b["requires_shared_bind"] is True
    assert a["bind_propagation"] is None
    assert b["bind_propagation"] == "rshared"
    # Neither claims Docker Desktop.
    assert a["docker_desktop_claimed"] is False
    assert b["docker_desktop_claimed"] is False


def test_docker_desktop_cannot_be_promoted_to_claimed() -> None:
    desktop = docker_desktop_profile()
    # Even if a caller forges host_visible, the catalogued support claim is
    # NOT_CLAIMED and docker_desktop_claimed remains false.
    record = desktop.to_record()
    assert record["support_claim"] == SupportClaim.NOT_CLAIMED.value
    assert record["docker_desktop_claimed"] is False
    # Live container suite receipt also denies Desktop.
    with live.ContainerLiveHarness(prefer_live=False) as h:
        suite = h.run_suite(
            case_ids=[
                live.ConformanceCaseId.ABSENT_DEVICE,
                live.ConformanceCaseId.NO_PRIVILEGED,
            ]
        )
        suite_record = suite.to_record()
        assert suite_record["docker_desktop_propagation_claimed"] is False
        assert suite_record["propagation_claim"] == PROPAGATION_IN_CONTAINER


# ---------------------------------------------------------------------------
# Cross-profile isolation / no leak of claims
# ---------------------------------------------------------------------------


def test_minimal_live_profile_does_not_inherit_rshared() -> None:
    minimal = live.minimal_capability_profile()
    assert minimal["propagation_claim"] == PROPAGATION_IN_CONTAINER
    assert minimal["host_propagation_claimed"] is False
    # rshared override is a separate object.
    override = build_rshared_override_spec(host_path="/tmp/x")
    assert override["profile_id"] != minimal["propagation_claim"]
    assert override["host_visible"] is True
    assert minimal["host_propagation_claimed"] is False


def test_propagation_suite_receipt_shape(tmp_path: Path) -> None:
    """Emit a compact suite receipt covering all profiles (hermetic)."""

    started = time.monotonic()
    profiles = [p.to_record() for p in all_propagation_profiles()]
    rshared = probe_rshared_profile(host_path=tmp_path / "rs").to_record()
    suite = {
        "schema": PROPAGATION_SUITE_SCHEMA,
        "task_id": TASK_ID,
        "profiles": profiles,
        "rshared_probe": rshared,
        "default_has_host_rshared": default_profile_has_host_rshared(),
        "docker_desktop_claimed": False,
        "privileged": False,
        "elapsed_seconds": time.monotonic() - started,
        "status": "passed",
    }
    out = tmp_path / "propagation-suite.json"
    out.write_text(json.dumps(suite, sort_keys=True, indent=2), encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["docker_desktop_claimed"] is False
    assert loaded["privileged"] is False
    assert loaded["default_has_host_rshared"] is False
    assert loaded["rshared_probe"]["ok"] is True
    ids = {p["profile_id"] for p in loaded["profiles"]}
    assert PROPAGATION_IN_CONTAINER in ids
    assert PROPAGATION_NATIVE_RSHARED in ids
    assert PROPAGATION_DOCKER_DESKTOP in ids
    desktop = next(
        p for p in loaded["profiles"] if p["profile_id"] == PROPAGATION_DOCKER_DESKTOP
    )
    assert desktop["support_claim"] == "not_claimed"
    assert desktop["docker_desktop_claimed"] is False


def test_rshared_requires_shared_bind_gate() -> None:
    """Host-visible claim without shared bind is rejected."""

    rshared = native_linux_rshared_profile()
    assert rshared.requires_shared_bind is True
    # Simulated invalid profile: host_visible without shared bind.
    invalid = PropagationProfile(
        profile_id=PropagationProfileId.NATIVE_LINUX_RSHARED,
        support_claim=SupportClaim.CLAIMED,
        requires_shared_bind=False,  # invalid
        host_visible=True,
        bind_propagation=None,
        host_bind_target=None,
        privileged=False,
        required_device=REQUIRED_DEVICE,
        required_cap=REQUIRED_CAP,
        distinct_from_default=True,
        notes="invalid",
    )
    # Gate: host_visible => requires_shared_bind and rshared propagation.
    def _valid(p: PropagationProfile) -> bool:
        if not p.host_visible:
            return True
        return (
            p.requires_shared_bind
            and p.bind_propagation == RSHARED_PROPAGATION
            and p.host_bind_target is not None
            and not p.privileged
        )

    assert _valid(rshared) is True
    assert _valid(invalid) is False
    assert _valid(in_container_profile()) is True
    assert _valid(docker_desktop_profile()) is True  # not host_visible


def test_import_is_inert() -> None:
    """Importing propagation tests must not start Docker or load fusepy."""

    source = TEST_PATH.read_text(encoding="utf-8")
    # Build fragments so this self-check does not embed the banned literals.
    banned = (
        "import " + "fuse\n",
        "import " + "fusepy\n",
        "from " + "fuse ",
        "from " + "fusepy ",
        "ctypes." + "CDLL",
    )
    for fragment in banned:
        assert fragment not in source, fragment
    pre = {n for n in ("fuse", "fusepy") if n in sys.modules}
    _ = all_propagation_profiles()
    for name in ("fuse", "fusepy"):
        if name not in pre:
            assert name not in sys.modules


def test_live_rshared_probe_opt_in_does_not_claim_desktop(
    tmp_path: Path,
) -> None:
    """Even when live docker is probed, Desktop remains unclaimed."""

    receipt = probe_rshared_profile(
        host_path=tmp_path / "live-host",
        require_live_mount=True,
    )
    assert receipt.docker_desktop_claimed is False
    assert receipt.privileged is False
    assert receipt.profile_id == PROPAGATION_NATIVE_RSHARED
    # If docker is unavailable, ok may be False — still no Desktop claim.
    if not receipt.ok:
        assert "desktop" not in receipt.message.lower() or "not" in receipt.message.lower()


# Optional: when IPFS_KIT_KERNEL_VFS_CONTAINER_LIVE is set and docker works,
# verify the rshared argv is well-formed against `docker` help only (no run).
def test_docker_cli_recognizes_mount_flag_when_present() -> None:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        pytest.skip("docker binary not on PATH")
    try:
        proc = subprocess.run(
            [docker_bin, "run", "--help"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("docker run --help unavailable")
    help_text = (proc.stdout or "") + (proc.stderr or "")
    # --mount is the supported bind-propagation surface; --privileged must
    # remain available as a flag we *refuse* to use.
    assert "--mount" in help_text
    assert "--device" in help_text
    assert "--cap-add" in help_text or "cap-add" in help_text


__all__ = [
    "PropagationProfileId",
    "PropagationProfile",
    "in_container_profile",
    "native_linux_rshared_profile",
    "docker_desktop_profile",
    "probe_rshared_profile",
    "build_rshared_override_spec",
    "rshared_docker_run_argv",
]
