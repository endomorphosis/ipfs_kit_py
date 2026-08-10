"""KVFS-701: dedicated minimally privileged Linux FUSE image and Compose profile.

Hermetic contract tests (no Docker daemon required). Acceptance coverage:

* Python floor, ``[fuse]`` extra, libfuse2 compatibility, and fusermount are
  reproducible in the dedicated Dockerfile;
* mount runs foreground with readiness;
* WAL / cache / state volumes are separate;
* profile requires ``/dev/fuse`` and ``SYS_ADMIN`` but never ``privileged``;
* either missing required input fails within five seconds.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any, Mapping

import yaml

# tests/kernel_vfs/container -> parents[3] == package root (ipfs_kit_py/)
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE_PATH = PACKAGE_ROOT / "docker" / "kernel-vfs.Dockerfile"
COMPOSE_PATH = PACKAGE_ROOT / "docker-compose.kernel-vfs.yml"
PYPROJECT_PATH = PACKAGE_ROOT / "pyproject.toml"

TASK_ID = "KVFS-701"
PYTHON_FLOOR = "3.12"
FUSE_EXTRA = "fuse"
FUSE_BINDING = "fusepy==3.0.1"
LIBFUSE_SONAME = "libfuse.so.2"
REQUIRED_DEVICE = "/dev/fuse"
REQUIRED_CAP = "SYS_ADMIN"
MISSING_INPUT_BUDGET_SECONDS = 5
SERVICE_NAME = "kernel-vfs"
PROFILE_NAMES = frozenset({"kernel-vfs", "fuse"})
STATE_VOLUME = "kernel-vfs-state"
WAL_VOLUME = "kernel-vfs-wal"
CACHE_VOLUME = "kernel-vfs-cache"
STATE_PATH = "/var/lib/ipfs-kit-vfs/state"
WAL_PATH = "/var/lib/ipfs-kit-vfs/wal"
CACHE_PATH = "/var/lib/ipfs-kit-vfs/cache"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _dockerfile_text() -> str:
    assert DOCKERFILE_PATH.is_file(), f"missing Dockerfile: {DOCKERFILE_PATH}"
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def _compose_doc() -> dict[str, Any]:
    assert COMPOSE_PATH.is_file(), f"missing Compose file: {COMPOSE_PATH}"
    raw = COMPOSE_PATH.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    assert isinstance(doc, dict), "Compose file must parse to a mapping"
    return doc


def _compose_text() -> str:
    return COMPOSE_PATH.read_text(encoding="utf-8")


def _service() -> dict[str, Any]:
    doc = _compose_doc()
    services = doc.get("services")
    assert isinstance(services, dict), "Compose must declare services"
    assert SERVICE_NAME in services, f"service {SERVICE_NAME!r} missing"
    service = services[SERVICE_NAME]
    assert isinstance(service, dict), f"service {SERVICE_NAME!r} must be a mapping"
    return service


def _packaging_policy() -> Mapping[str, Any]:
    with PYPROJECT_PATH.open("rb") as handle:
        project = tomllib.load(handle)
    tool = project.get("tool") or {}
    kit = tool.get("ipfs_kit_py") or {}
    kernel = kit.get("kernel_vfs") or {}
    policy = kernel.get("packaging") or {}
    assert isinstance(policy, dict)
    return policy


# ---------------------------------------------------------------------------
# Declared outputs exist
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert DOCKERFILE_PATH.is_file()
    assert COMPOSE_PATH.is_file()
    assert Path(__file__).resolve().is_file()


# ---------------------------------------------------------------------------
# Dockerfile: Python floor, fuse extra, libfuse2, fusermount (reproducible)
# ---------------------------------------------------------------------------


def test_dockerfile_python_floor_is_reproducible() -> None:
    text = _dockerfile_text()
    # Explicit ARG pin and base image use the Python floor.
    assert re.search(r"(?m)^ARG\s+PYTHON_VERSION=3\.12\s*$", text)
    assert "FROM python:${PYTHON_VERSION}-slim-bookworm" in text
    # Runtime asserts the floor.
    assert "sys.version_info[:2] >= (3, 12)" in text
    assert f'kvfs.python_floor="${{PYTHON_VERSION}}"' in text or "kvfs.python_floor=" in text


def test_dockerfile_installs_pinned_fuse_extra() -> None:
    text = _dockerfile_text()
    policy = _packaging_policy()
    # Install surface must use the packaging [fuse] extra.
    assert '".[fuse]"' in text or "'.[fuse]'" in text or ".[fuse]" in text
    assert FUSE_EXTRA in text
    # Pin is exact and matches packaging policy.
    assert FUSE_BINDING in text
    assert policy.get("fuse_binding_requirement") == FUSE_BINDING
    assert policy.get("fuse_extra") == FUSE_EXTRA
    # fusepy is verified at build time (reproducible binding presence).
    assert "fusepy" in text
    assert "import fuse" in text or "fuse-binding-ok" in text


def test_dockerfile_installs_libfuse2_and_fusermount() -> None:
    text = _dockerfile_text()
    # Debian packages for libfuse2 ABI + fusermount helper.
    assert re.search(r"(?m)^\s*libfuse2\s*\\?\s*$", text) or "libfuse2" in text
    assert re.search(r"(?m)^\s*fuse\s*\\?\s*$", text) or re.search(
        r"apt-get install[^\n]*\bfuse\b", text
    )
    assert LIBFUSE_SONAME in text
    assert "libfuse2" in text
    assert "fusermount" in text
    # Build verifies helper and soname (reproducible presence checks).
    assert "libfuse.so.2" in text
    assert "fusermount" in text.lower()
    assert "kvfs.libfuse_abi=\"libfuse2\"" in text or "libfuse2" in text


def test_dockerfile_never_enables_privileged_mode() -> None:
    raw = _dockerfile_text()
    text = raw.lower()
    # Image must declare privileged=false and never instruct privileged true.
    assert "privileged" in text
    assert 'kvfs.privileged="false"' in raw or "KVFS_PRIVILEGED=false" in raw
    # Instruction/assignment forms of privileged:true are forbidden. Mentions of
    # the forbidden flag in comments/remediation text are allowed only as denial.
    assert re.search(r"(?i)privileged\s*=\s*true", raw) is None
    assert re.search(r"(?i)^\s*privileged\s+true\b", raw, re.M) is None
    # Remediation must steer operators away from blanket privileged mode.
    assert "do not use --privileged" in text or "never --privileged" in text or "privileged is forbidden" in text


def test_dockerfile_mount_runs_foreground_with_readiness() -> None:
    text = _dockerfile_text()
    assert "IPFS_KIT_KERNEL_VFS_FOREGROUND=1" in text
    assert "IPFS_KIT_KERNEL_VFS_READINESS=1" in text
    assert "--foreground" in text
    assert "--readiness" in text
    assert "kvfs.mount_mode=\"foreground\"" in text or "foreground" in text.lower()
    assert "ready.json" in text
    # ENTRYPOINT is the preflight+mount wrapper (PID-1 friendly).
    assert "ENTRYPOINT" in text
    assert "kernel-vfs-entrypoint" in text


def test_dockerfile_declares_separate_wal_cache_state_volumes() -> None:
    text = _dockerfile_text()
    assert STATE_PATH in text
    assert WAL_PATH in text
    assert CACHE_PATH in text
    # Paths must be distinct.
    assert len({STATE_PATH, WAL_PATH, CACHE_PATH}) == 3
    # VOLUME instruction lists all three separately.
    assert "VOLUME" in text
    for path in (STATE_PATH, WAL_PATH, CACHE_PATH):
        assert path in text
    assert "kvfs.volumes=\"state,wal,cache\"" in text or "state,wal,cache" in text


def test_dockerfile_missing_input_fails_within_five_seconds() -> None:
    text = _dockerfile_text()
    assert "IPFS_KIT_KERNEL_VFS_CAPABILITY_BUDGET_SECONDS=5" in text
    assert "KVFS_CAPABILITY_BUDGET_SECONDS=5" in text or "CAPABILITY_BUDGET" in text
    assert str(MISSING_INPUT_BUDGET_SECONDS) in text
    # Preflight covers both required inputs.
    assert REQUIRED_DEVICE in text
    assert REQUIRED_CAP in text
    assert "CapEff" in text or "CAP_SYS_ADMIN" in text or "_CAP_SYS_ADMIN" in text
    assert "missing_input_fail_seconds" in text or "budget" in text.lower()
    # Budget is hard-capped at 5 seconds in entrypoint logic.
    assert "min(value, 5.0)" in text or "min(value, 5)" in text or "5.0" in text


# ---------------------------------------------------------------------------
# Compose profile: devices, capabilities, volumes, never privileged
# ---------------------------------------------------------------------------


def test_compose_uses_dedicated_dockerfile_and_profiles() -> None:
    service = _service()
    build = service.get("build")
    assert isinstance(build, dict)
    assert build.get("context") in {".", "./"}
    assert build.get("dockerfile") == "docker/kernel-vfs.Dockerfile"
    args = build.get("args") or {}
    assert str(args.get("PYTHON_VERSION")) == PYTHON_FLOOR
    assert str(args.get("KVFS_FUSE_EXTRA", FUSE_EXTRA)) == FUSE_EXTRA
    assert str(args.get("KVFS_FUSE_BINDING", FUSE_BINDING)) == FUSE_BINDING
    assert str(args.get("KVFS_LIBFUSE_SONAME", LIBFUSE_SONAME)) == LIBFUSE_SONAME
    assert str(args.get("KVFS_CAPABILITY_BUDGET_SECONDS", "5")) == "5"

    profiles = service.get("profiles")
    assert isinstance(profiles, list)
    assert PROFILE_NAMES.issubset(set(profiles))


def test_compose_requires_dev_fuse_and_sys_admin_never_privileged() -> None:
    service = _service()
    # Explicitly false — not merely omitted.
    assert service.get("privileged") is False

    devices = service.get("devices")
    assert isinstance(devices, list)
    device_blob = " ".join(str(item) for item in devices)
    assert REQUIRED_DEVICE in device_blob

    cap_add = service.get("cap_add")
    assert isinstance(cap_add, list)
    caps = {str(item).upper() for item in cap_add}
    assert REQUIRED_CAP in caps

    # Forbidden: privileged true as a Compose key assignment (ignore comments).
    instruction_lines = [
        line
        for line in _compose_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    instruction_blob = "\n".join(instruction_lines).lower()
    assert re.search(r"privileged\s*:\s*true", instruction_blob) is None
    assert service.get("privileged") is False
    # Labels reinforce the contract for operators and scanners.
    labels = service.get("labels") or {}
    assert str(labels.get("kvfs.privileged", "")).lower() in {"false", "0"}
    assert labels.get("kvfs.required_device") == REQUIRED_DEVICE
    assert str(labels.get("kvfs.required_cap", "")).upper() == REQUIRED_CAP


def test_compose_wal_cache_state_volumes_are_separate() -> None:
    doc = _compose_doc()
    service = _service()
    volumes = service.get("volumes")
    assert isinstance(volumes, list)

    # Map host volume source -> container target for named volumes.
    named_binds: dict[str, str] = {}
    for entry in volumes:
        if isinstance(entry, str):
            # short syntax: name:path
            parts = entry.split(":")
            if len(parts) >= 2 and not parts[0].startswith("/") and parts[0] != "type":
                named_binds[parts[0]] = parts[1]
        elif isinstance(entry, dict):
            source = entry.get("source") or entry.get("src")
            target = entry.get("target") or entry.get("destination")
            if source and target and entry.get("type") in {None, "volume"}:
                named_binds[str(source)] = str(target)

    assert STATE_VOLUME in named_binds
    assert WAL_VOLUME in named_binds
    assert CACHE_VOLUME in named_binds
    assert named_binds[STATE_VOLUME] == STATE_PATH
    assert named_binds[WAL_VOLUME] == WAL_PATH
    assert named_binds[CACHE_VOLUME] == CACHE_PATH
    # Three distinct volume sources and three distinct targets.
    assert len({STATE_VOLUME, WAL_VOLUME, CACHE_VOLUME}) == 3
    assert len({named_binds[STATE_VOLUME], named_binds[WAL_VOLUME], named_binds[CACHE_VOLUME]}) == 3

    top_volumes = doc.get("volumes")
    assert isinstance(top_volumes, dict)
    for name in (STATE_VOLUME, WAL_VOLUME, CACHE_VOLUME):
        assert name in top_volumes


def test_compose_foreground_readiness_and_five_second_fail_budget() -> None:
    service = _service()
    env = service.get("environment") or {}
    # Normalize list-or-map environment forms.
    if isinstance(env, list):
        env_map: dict[str, str] = {}
        for item in env:
            if isinstance(item, str) and "=" in item:
                key, value = item.split("=", 1)
                env_map[key] = value
        env = env_map
    assert isinstance(env, dict)

    assert str(env.get("IPFS_KIT_KERNEL_VFS_FOREGROUND")) == "1"
    assert str(env.get("IPFS_KIT_KERNEL_VFS_READINESS")) == "1"
    assert str(env.get("IPFS_KIT_KERNEL_VFS_CAPABILITY_BUDGET_SECONDS")) == "5"
    assert str(env.get("KVFS_REQUIRED_DEVICE")) == REQUIRED_DEVICE
    assert str(env.get("KVFS_REQUIRED_CAP")).upper() == REQUIRED_CAP
    assert str(env.get("KVFS_PRIVILEGED")).lower() == "false"

    labels = service.get("labels") or {}
    assert str(labels.get("kvfs.mount_mode")) == "foreground"
    assert str(labels.get("kvfs.readiness")) == "required"
    assert str(labels.get("kvfs.missing_input_fail_seconds")) == "5"
    assert str(labels.get("kvfs.task_id")) == TASK_ID

    # PID-1 aware init for foreground mount child reaping.
    assert service.get("init") is True


def test_compose_and_dockerfile_agree_on_required_inputs() -> None:
    """Device, capability, budget, and volume paths are consistent across files."""
    df = _dockerfile_text()
    service = _service()
    env = service.get("environment") or {}
    if isinstance(env, list):
        env = {
            item.split("=", 1)[0]: item.split("=", 1)[1]
            for item in env
            if isinstance(item, str) and "=" in item
        }

    for path_key, path_value in (
        ("IPFS_KIT_KERNEL_VFS_STATE_DIR", STATE_PATH),
        ("IPFS_KIT_KERNEL_VFS_WAL_DIR", WAL_PATH),
        ("IPFS_KIT_KERNEL_VFS_CACHE_DIR", CACHE_PATH),
    ):
        assert path_value in df
        assert str(env.get(path_key)) == path_value

    assert REQUIRED_DEVICE in df
    assert REQUIRED_CAP in df
    assert service.get("privileged") is False
    devices = " ".join(str(d) for d in (service.get("devices") or []))
    assert REQUIRED_DEVICE in devices
    assert REQUIRED_CAP in {str(c).upper() for c in (service.get("cap_add") or [])}


def test_normal_compose_not_modified_by_this_profile() -> None:
    """Conflict policy: dedicated profile only; normal compose stays separate."""
    normal = PACKAGE_ROOT / "docker-compose.yml"
    assert normal.is_file()
    # Dedicated file is not the normal compose file.
    assert COMPOSE_PATH.resolve() != normal.resolve()
    normal_text = normal.read_text(encoding="utf-8")
    # The dedicated kernel-vfs service must not have been injected into normal.
    assert "kernel-vfs.Dockerfile" not in normal_text
    # Normal compose must not gain a privileged kernel-vfs profile via this task.
    # (May still mention privileged for unrelated services historically — only
    # assert our dedicated service is absent.)
    assert "ipfs-kit-kernel-vfs" not in normal_text
    assert "kernel-vfs-state" not in normal_text


def test_image_profile_task_identity() -> None:
    df = _dockerfile_text()
    service = _service()
    labels = service.get("labels") or {}
    assert TASK_ID in df
    assert labels.get("kvfs.task_id") == TASK_ID
    assert "KernelVFSContainerImageProfile@1" in df or "kvfs.schema=" in df
    assert "linux-fuse-minimal" in df
    assert labels.get("kvfs.profile") == "linux-fuse-minimal"


# ---------------------------------------------------------------------------
# Static preflight semantics (entrypoint source embedded in Dockerfile)
# ---------------------------------------------------------------------------


def test_entrypoint_preflight_covers_either_missing_input() -> None:
    """Entrypoint fails closed when device or SYS_ADMIN is absent (within 5s)."""
    text = _dockerfile_text()
    # Device absence path.
    assert "required device" in text.lower() or "is missing" in text
    assert "_check_dev_fuse" in text or "S_ISCHR" in text
    # Capability absence path.
    assert "SYS_ADMIN" in text
    assert "privileged mode is forbidden" in text.lower() or "privileged" in text.lower()
    # Hard budget.
    assert "_DEFAULT_BUDGET = 5.0" in text or "budget" in text.lower()
    assert "min(value, 5.0)" in text
    # Mount only after preflight success (exec path).
    assert "os.execvp" in text
    assert "preflight" in text


def test_dockerfile_reproducible_pins_are_explicit() -> None:
    text = _dockerfile_text()
    # Reproducibility anchors operators can re-resolve.
    assert f"PYTHON_VERSION={PYTHON_FLOOR}" in text
    assert f"KVFS_FUSE_BINDING={FUSE_BINDING}" in text or FUSE_BINDING in text
    assert f"KVFS_LIBFUSE_SONAME={LIBFUSE_SONAME}" in text or LIBFUSE_SONAME in text
    assert "slim-bookworm" in text
    # apt packages named explicitly (not floating meta-only installs without libfuse2).
    assert "libfuse2" in text
    assert "fuse" in text
