# syntax=docker/dockerfile:1.6
# =============================================================================
# KVFS-701 — Dedicated minimally privileged Linux FUSE image for kernel VFS
# =============================================================================
# Contract (fail-closed):
#   * Python floor >= 3.12 (reproducible base pin)
#   * Optional [fuse] extra installed (pinned fusepy binding only)
#   * libfuse2 ABI (libfuse.so.2) + fusermount helper present and verified
#   * Mount runs foreground / PID-1 aware with readiness handshake
#   * WAL, cache, and state paths are distinct volume roots
#   * Runtime requires /dev/fuse + CAP_SYS_ADMIN; NEVER --privileged
#   * Either missing required input (/dev/fuse or SYS_ADMIN) fails within 5s
#
# This image is intentionally separate from the normal unprivileged ipfs-kit
# image. Blanket privileged mode is forbidden by project SLO.
# =============================================================================

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# ---- Reproducible identity / profile labels ---------------------------------
ARG PYTHON_VERSION=3.12
ARG KVFS_TASK_ID=KVFS-701
ARG KVFS_FUSE_EXTRA=fuse
ARG KVFS_FUSE_BINDING=fusepy==3.0.1
ARG KVFS_LIBFUSE_SONAME=libfuse.so.2
ARG KVFS_CAPABILITY_BUDGET_SECONDS=5

LABEL org.opencontainers.image.title="ipfs-kit-kernel-vfs" \
      org.opencontainers.image.description="Minimally privileged Linux FUSE image for ipfs_kit_py kernel VFS" \
      org.opencontainers.image.source="https://github.com/endomorphosis/ipfs_kit_py" \
      kvfs.task_id="${KVFS_TASK_ID}" \
      kvfs.schema="KernelVFSContainerImageProfile@1" \
      kvfs.profile="linux-fuse-minimal" \
      kvfs.python_floor="${PYTHON_VERSION}" \
      kvfs.fuse_extra="${KVFS_FUSE_EXTRA}" \
      kvfs.fuse_binding="${KVFS_FUSE_BINDING}" \
      kvfs.libfuse_abi="libfuse2" \
      kvfs.libfuse_soname="${KVFS_LIBFUSE_SONAME}" \
      kvfs.fusermount="required" \
      kvfs.privileged="false" \
      kvfs.required_device="/dev/fuse" \
      kvfs.required_cap="SYS_ADMIN" \
      kvfs.missing_input_fail_seconds="${KVFS_CAPABILITY_BUDGET_SECONDS}" \
      kvfs.mount_mode="foreground" \
      kvfs.readiness="required" \
      kvfs.volumes="state,wal,cache"

# Distinct durable roots (Compose binds separate named volumes here).
# Foreground mount with readiness (PID-1 aware under docker init).
# Reproducible package surface pins match packaging policy (KVFS-703).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    IPFS_KIT_KERNEL_VFS_MOUNTPOINT=/mnt/ipfs-kit-vfs \
    IPFS_KIT_KERNEL_VFS_STATE_DIR=/var/lib/ipfs-kit-vfs/state \
    IPFS_KIT_KERNEL_VFS_WAL_DIR=/var/lib/ipfs-kit-vfs/wal \
    IPFS_KIT_KERNEL_VFS_CACHE_DIR=/var/lib/ipfs-kit-vfs/cache \
    IPFS_KIT_KERNEL_VFS_READY_DIR=/var/run/ipfs-kit-vfs \
    IPFS_KIT_KERNEL_VFS_FOREGROUND=1 \
    IPFS_KIT_KERNEL_VFS_READINESS=1 \
    IPFS_KIT_KERNEL_VFS_CAPABILITY_BUDGET_SECONDS=5 \
    KVFS_FUSE_EXTRA=fuse \
    KVFS_FUSE_BINDING=fusepy==3.0.1 \
    KVFS_LIBFUSE_SONAME=libfuse.so.2 \
    KVFS_REQUIRED_DEVICE=/dev/fuse \
    KVFS_REQUIRED_CAP=SYS_ADMIN \
    KVFS_PRIVILEGED=false

# ---- Native FUSE floor: libfuse2 ABI + fusermount helper --------------------
# Debian bookworm packages:
#   * libfuse2  -> libfuse.so.2 (fusepy high-level FUSE 2.x ABI)
#   * fuse      -> fusermount userspace helper
# Exact package names keep the image profile reproducible across rebuilds.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        fuse \
        libfuse2 \
    ; \
    rm -rf /var/lib/apt/lists/*; \
    # fusermount must be present (never invoke it at build time for mounts).
    if [ -x /bin/fusermount ]; then \
        FUSEMOUNT=/bin/fusermount; \
    elif [ -x /usr/bin/fusermount ]; then \
        FUSEMOUNT=/usr/bin/fusermount; \
    else \
        echo "ERROR: fusermount helper missing after fuse package install" >&2; \
        exit 1; \
    fi; \
    # libfuse2 soname must resolve (architecture multiarch paths).
    if ! ldconfig -p 2>/dev/null | grep -q 'libfuse\.so\.2'; then \
        if ! find /lib /usr/lib -name 'libfuse.so.2*' 2>/dev/null | grep -q .; then \
            echo "ERROR: libfuse.so.2 not found after libfuse2 install" >&2; \
            exit 1; \
        fi; \
    fi; \
    # Record verified helper path for operators / profile tests.
    printf '%s\n' "${FUSEMOUNT}" > /etc/ipfs-kit-kernel-vfs.fusermount; \
    # Python floor sanity on the base image.
    python -c 'import sys; assert sys.version_info[:2] >= (3, 12), sys.version'

WORKDIR /app

# Copy package sources required for a reproducible wheel/editable install.
# Context is the ipfs_kit_py package root (see docker-compose.kernel-vfs.yml).
COPY pyproject.toml setup.py README.md LICENSE MANIFEST.in ./
COPY ipfs_kit_py ./ipfs_kit_py

# Install the package with the pinned [fuse] extra only (no privileged extras).
# Binding pin is exact (fusepy==3.0.1) via pyproject optional-dependencies.
RUN set -eux; \
    python -m pip install --upgrade pip setuptools wheel; \
    python -m pip install --no-cache-dir ".[fuse]"; \
    # Reproducible fuse extra surface (Python floor already asserted above).
    python -c "import importlib.metadata as m; v=m.version('fusepy'); print('fusepy', v)"; \
    python -c "import fuse; print('fuse-binding-ok')"; \
    # Console script from packaging metadata (KVFS-703 / KVFS-702).
    command -v ipfs-kit-kernel-vfs >/dev/null

# Distinct volume roots for recovery state, WAL, and ARC cache.
RUN set -eux; \
    mkdir -p \
        /mnt/ipfs-kit-vfs \
        /var/lib/ipfs-kit-vfs/state \
        /var/lib/ipfs-kit-vfs/wal \
        /var/lib/ipfs-kit-vfs/cache \
        /var/run/ipfs-kit-vfs \
    ; \
    chmod 0755 /mnt/ipfs-kit-vfs /var/run/ipfs-kit-vfs; \
    chmod 0700 \
        /var/lib/ipfs-kit-vfs/state \
        /var/lib/ipfs-kit-vfs/wal \
        /var/lib/ipfs-kit-vfs/cache

# Named volume mount points (Compose binds three separate volumes).
VOLUME ["/var/lib/ipfs-kit-vfs/state", "/var/lib/ipfs-kit-vfs/wal", "/var/lib/ipfs-kit-vfs/cache"]

# ---- Entrypoint: 5s fail-closed preflight, then foreground mount ------------
# Either missing required input fails within IPFS_KIT_KERNEL_VFS_CAPABILITY_BUDGET_SECONDS
# (default 5). Never elevates to privileged. Never mounts without preflight.
RUN set -eux; \
    cat > /usr/local/bin/kernel-vfs-entrypoint.py <<'PY'
#!/usr/bin/env python3
"""KVFS-701 container entrypoint: capability preflight + foreground mount.

Required inputs (fail within budget if either is missing):
  * /dev/fuse device node present and character-special
  * CAP_SYS_ADMIN effective in this process (Compose cap_add: SYS_ADMIN)

Never requests privileged mode. Mount runs foreground with readiness.
"""
from __future__ import annotations

import os
import stat
import sys
import time
from pathlib import Path

# CAP_SYS_ADMIN is capability bit 21 (linux/capability.h).
_CAP_SYS_ADMIN = 1 << 21
_DEFAULT_BUDGET = 5.0
_DEV_FUSE = os.environ.get("KVFS_REQUIRED_DEVICE", "/dev/fuse")
_MOUNT_CLI = os.environ.get("KVFS_MOUNT_CLI", "ipfs-kit-kernel-vfs")


def _budget_seconds() -> float:
    raw = os.environ.get("IPFS_KIT_KERNEL_VFS_CAPABILITY_BUDGET_SECONDS", str(_DEFAULT_BUDGET))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = _DEFAULT_BUDGET
    return max(0.1, min(value, 5.0))


def _read_cap_eff() -> int | None:
    """Return CapEff bitmask from /proc/self/status, or None if unreadable."""
    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("CapEff:"):
                    hex_value = line.split(":", 1)[1].strip()
                    return int(hex_value, 16)
    except (OSError, ValueError):
        return None
    return None


def _has_sys_admin() -> bool:
    caps = _read_cap_eff()
    if caps is None:
        return False
    return bool(caps & _CAP_SYS_ADMIN)


def _check_dev_fuse(device: str) -> tuple[bool, str]:
    path = Path(device)
    if not path.exists():
        return False, f"required device {device} is missing"
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        return False, f"required device {device} is not accessible: {exc}"
    if not stat.S_ISCHR(mode):
        return False, f"{device} exists but is not a character device"
    if not os.access(device, os.R_OK | os.W_OK):
        return False, f"{device} is not read/write accessible"
    return True, "ok"


def preflight(budget: float) -> int:
    """Fail closed when either required input is absent; always within budget."""
    started = time.monotonic()
    deadline = started + budget
    errors: list[str] = []

    ok_dev, dev_msg = _check_dev_fuse(_DEV_FUSE)
    if not ok_dev:
        errors.append(dev_msg)

    if not _has_sys_admin():
        errors.append(
            "required capability SYS_ADMIN is not effective "
            "(Compose must cap_add: [SYS_ADMIN]; privileged mode is forbidden)"
        )

    elapsed = time.monotonic() - started
    # Stay inside the budget even if checks were instant.
    if time.monotonic() > deadline:
        # Should never happen for pure path/stat probes; still report fail-closed.
        errors.append(f"capability preflight exceeded {budget:.1f}s budget")

    if errors:
        print(
            "kernel-vfs capability preflight FAILED "
            f"(elapsed={elapsed:.3f}s budget={budget:.1f}s privileged=false):",
            file=sys.stderr,
        )
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        print(
            "Remediation: pass --device /dev/fuse and --cap-add SYS_ADMIN; "
            "do not use --privileged.",
            file=sys.stderr,
        )
        return 1

    print(
        "kernel-vfs capability preflight OK "
        f"(device={_DEV_FUSE} cap=SYS_ADMIN elapsed={elapsed:.3f}s "
        f"budget={budget:.1f}s privileged=false foreground=1 readiness=1)",
        file=sys.stderr,
    )
    return 0


def build_mount_argv(user_argv: list[str]) -> list[str]:
    """Compose the foreground mount CLI invocation with readiness."""
    mountpoint = os.environ.get("IPFS_KIT_KERNEL_VFS_MOUNTPOINT", "/mnt/ipfs-kit-vfs")
    state_dir = os.environ.get("IPFS_KIT_KERNEL_VFS_STATE_DIR", "/var/lib/ipfs-kit-vfs/state")
    wal_dir = os.environ.get("IPFS_KIT_KERNEL_VFS_WAL_DIR", "/var/lib/ipfs-kit-vfs/wal")
    cache_dir = os.environ.get("IPFS_KIT_KERNEL_VFS_CACHE_DIR", "/var/lib/ipfs-kit-vfs/cache")
    ready_dir = os.environ.get("IPFS_KIT_KERNEL_VFS_READY_DIR", "/var/run/ipfs-kit-vfs")

    if user_argv:
        # Operator override: still always run through the CLI binary.
        return [_MOUNT_CLI, *user_argv]

    return [
        _MOUNT_CLI,
        "mount",
        "--foreground",
        "--readiness",
        f"--mountpoint={mountpoint}",
        f"--state-dir={state_dir}",
        f"--wal-dir={wal_dir}",
        f"--cache-dir={cache_dir}",
        f"--ready-dir={ready_dir}",
    ]


def main(argv: list[str]) -> int:
    budget = _budget_seconds()
    # Explicit subcommands that skip mount (doctor/status/unmount) still preflight
    # device/cap when they touch native capability — always preflight here.
    rc = preflight(budget)
    if rc != 0:
        return rc

    if argv and argv[0] in {"preflight", "capability-check"}:
        return 0

    mount_argv = build_mount_argv(argv)
    os.execvp(mount_argv[0], mount_argv)
    return 127  # pragma: no cover — execvp never returns on success


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
PY
    chmod 0755 /usr/local/bin/kernel-vfs-entrypoint.py; \
    # Tiny shell wrapper so ENTRYPOINT stays simple and PID-1 friendly.
    printf '%s\n' \
        '#!/bin/sh' \
        'set -eu' \
        'exec python3 /usr/local/bin/kernel-vfs-entrypoint.py "$@"' \
        > /usr/local/bin/kernel-vfs-entrypoint; \
    chmod 0755 /usr/local/bin/kernel-vfs-entrypoint

# Health: readiness file written by mount CLI after recovery (not privileged).
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import os,sys; p=os.environ.get('IPFS_KIT_KERNEL_VFS_READY_DIR','/var/run/ipfs-kit-vfs'); sys.exit(0 if os.path.isfile(os.path.join(p,'ready.json')) else 1)"

# Document required runtime inputs (Compose supplies them; never privileged).
# device=/dev/fuse  cap_add=SYS_ADMIN  privileged=false
STOPSIGNAL SIGTERM

ENTRYPOINT ["/usr/local/bin/kernel-vfs-entrypoint"]
# Default: foreground mount with readiness using env-configured paths.
CMD []
