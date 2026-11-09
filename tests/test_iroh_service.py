"""Contract tests for managed Iroh service lifecycle supervision."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
from pathlib import Path

import pytest

from ipfs_kit_py.iroh.config import IrohServiceConfig
from ipfs_kit_py.iroh.errors import IrohConflictError, IrohUnavailableError
from ipfs_kit_py.iroh.service import IrohService


def _config(
    tmp_path: Path, *, binds: tuple[str, ...] = ("127.0.0.1:0",)
) -> IrohServiceConfig:
    base = IrohServiceConfig.default("test", state_root=tmp_path, enabled=True)
    return IrohServiceConfig(
        instance=base.instance,
        layout=base.layout,
        enabled=True,
        node_identity_ref=base.node_identity_ref,
        endpoint_bind=binds,
    )


def _sleeper_command() -> tuple[str, ...]:
    return (sys.executable, "-c", "import time; time.sleep(60)")


def _service(tmp_path: Path, **kwargs: object) -> IrohService:
    return IrohService(
        _config(tmp_path),
        executable=sys.executable,
        command=_sleeper_command(),
        readiness_probe=lambda: True,
        startup_timeout=1,
        shutdown_timeout=0.05,
        kill_timeout=1,
        probe_interval=0.01,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_start_status_concurrent_idempotence_and_shutdown(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        assert await asyncio.gather(service.start(), service.start()) == [True, True]
        status = await service.status()
        assert status["running"] is status["ready"] is True
        assert status["pid"] > 0
        receipt = json.loads(service.layout.pid_path.read_text())
        assert receipt["birth"] and receipt["owner_token"]
        assert await service.stop() is True
        assert (await service.status())["status"] == "stopped"
        assert not service.layout.pid_path.exists()
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_new_service_object_adopts_owned_orphan_and_can_stop_it(tmp_path: Path) -> None:
    owner = _service(tmp_path)
    await owner.start()
    adopter = _service(tmp_path)
    try:
        assert (await adopter.status())["pid_ownership"] == "owned"
        assert await adopter.stop()
        await asyncio.sleep(0.05)
        assert not owner.layout.crash_receipt_path.exists()
    finally:
        await owner.stop()


def test_canonical_registry_registers_iroh() -> None:
    from ipfs_kit_py.service_registry import ServiceRegistry

    assert "iroh" in ServiceRegistry().get_available_service_types()


@pytest.mark.asyncio
async def test_stale_pid_is_recovered_before_start(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.layout.runtime_dir.mkdir(parents=True)
    service.layout.pid_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "ipfs-kit-iroh-process",
                "instance": "test",
                "pid": 999999999,
                "birth": "gone",
                "executable": os.fspath(Path(sys.executable).resolve()),
                "owner_token": "old",
            }
        )
    )
    try:
        assert await service.start()
        assert json.loads(service.layout.pid_path.read_text())["pid"] != 999999999
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_wrong_live_pid_is_never_signalled(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.layout.runtime_dir.mkdir(parents=True)
    service.layout.pid_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "ipfs-kit-iroh-process",
                "instance": "other",
                "pid": os.getpid(),
                "birth": "wrong",
                "executable": os.fspath(Path(sys.executable).resolve()),
                "owner_token": "not-ours",
            }
        )
    )
    with pytest.raises(IrohConflictError, match="not owned"):
        await service.stop()
    assert (await service.status())["status"] == "foreign"


@pytest.mark.asyncio
async def test_fixed_port_conflict_fails_before_spawn(tmp_path: Path) -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    config = _config(tmp_path, binds=(f"127.0.0.1:{port}",))
    service = IrohService(
        config,
        executable=sys.executable,
        command=_sleeper_command(),
        readiness_probe=lambda: True,
    )
    try:
        with pytest.raises(IrohConflictError, match="already in use"):
            await service.start()
        assert not service.layout.pid_path.exists()
    finally:
        listener.close()


@pytest.mark.asyncio
async def test_restart_replaces_pid(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        await service.start()
        first = (await service.status())["pid"]
        await service.restart()
        second = (await service.status())["pid"]
        assert second > 0 and second != first
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_startup_failures_activate_persistent_crash_loop(tmp_path: Path) -> None:
    service = IrohService(
        _config(tmp_path),
        executable=sys.executable,
        command=_sleeper_command(),
        readiness_probe=lambda: False,
        startup_timeout=0.03,
        shutdown_timeout=0.01,
        kill_timeout=0.2,
        probe_interval=0.01,
        crash_limit=2,
    )
    for _ in range(2):
        with pytest.raises(IrohUnavailableError, match="ready"):
            await service.start()
    with pytest.raises(IrohUnavailableError, match="crash-loop"):
        await service.start()
    assert (await service.status())["crash_count"] == 2
