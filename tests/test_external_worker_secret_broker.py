"""EAAEF-124: opaque secret handles bind lease/task/policy and revoke at terminal."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from ipfs_kit_py.secret_broker.external_worker import OpaqueHandle, SecretBroker, SecretBrokerError


def test_resolve_is_bound_and_redacted() -> None:
    broker = SecretBroker()
    handle = broker.issue(
        "super-secret",
        lease_id="lease:1",
        task_id="task:1",
        policy_id="policy:1",
    )
    assert isinstance(handle, OpaqueHandle)
    assert "super-secret" not in handle.as_event_field()
    material = broker.resolve(
        handle,
        lease_id="lease:1",
        task_id="task:1",
        policy_id="policy:1",
    )
    assert material == "super-secret"
    event = broker.redact({"kind": "checkpoint", "secret": "super-secret", "handle": handle.handle_id})
    assert event["secret"] == "[redacted]"
    assert "super-secret" not in str(event)


def test_wrong_lease_and_revoke_fail_closed() -> None:
    broker = SecretBroker()
    handle = broker.issue(
        "super-secret",
        lease_id="lease:1",
        task_id="task:1",
        policy_id="policy:1",
    )
    with pytest.raises(SecretBrokerError, match="not bound"):
        broker.resolve(handle, lease_id="lease:other", task_id="task:1", policy_id="policy:1")
    broker.revoke(handle)
    with pytest.raises(SecretBrokerError, match="revoked"):
        broker.resolve(handle, lease_id="lease:1", task_id="task:1", policy_id="policy:1")


def test_ephemeral_file_is_owner_only_and_boundary_revokes(tmp_path: Path) -> None:
    broker = SecretBroker(tmp_path / "secret-root")
    handle = broker.issue(
        b"binary-secret",
        lease_id="lease:1",
        task_id="task:1",
        policy_id="policy:1",
    )
    mounted = broker.mount_ephemeral_file(
        handle,
        lease_id="lease:1",
        task_id="task:1",
        policy_id="policy:1",
        filename="provider-token",
    )
    assert mounted.path.read_bytes() == b"binary-secret"
    assert stat.S_IMODE(mounted.path.stat().st_mode) == 0o400
    revoked = broker.revoke_at_boundary(
        lease_id="lease:1",
        task_id="task:1",
        policy_id="policy:1",
        boundary="checkpoint",
    )
    assert revoked == (handle.handle_id,)
    assert not mounted.path.exists()
    with pytest.raises(SecretBrokerError, match="revoked"):
        broker.resolve(
            handle,
            lease_id="lease:1",
            task_id="task:1",
            policy_id="policy:1",
        )


def test_ttl_recursive_redaction_and_bounded_cleanup(tmp_path: Path) -> None:
    now = [10.0]
    broker = SecretBroker(
        tmp_path / "secret-root",
        default_ttl_seconds=1.0,
        clock=lambda: now[0],
    )
    handle = broker.issue(
        "super-secret",
        lease_id="lease:1",
        task_id="task:1",
        policy_id="policy:1",
    )
    nested = broker.redact(
        {"payload": {"message": "prefix super-secret suffix", "api_key": "other"}}
    )
    assert "super-secret" not in str(nested)
    assert nested["payload"]["api_key"] == "[redacted]"
    now[0] = 12.0
    with pytest.raises(SecretBrokerError, match="expired") as expired:
        broker.resolve(
            handle,
            lease_id="lease:1",
            task_id="task:1",
            policy_id="policy:1",
        )
    assert expired.value.reason_code == "expired"

    second = broker.issue(
        "mounted-secret",
        lease_id="lease:2",
        task_id="task:2",
        policy_id="policy:2",
    )
    mounted = broker.mount_ephemeral_file(
        second,
        lease_id="lease:2",
        task_id="task:2",
        policy_id="policy:2",
    )
    unexpected = mounted.path.parent / "unexpected"
    unexpected.write_text("do not recursively delete", encoding="utf-8")
    with pytest.raises(SecretBrokerError) as cleanup:
        broker.revoke(second)
    assert cleanup.value.reason_code == "cleanup_failed"
    assert unexpected.read_text(encoding="utf-8") == "do not recursively delete"


def test_secret_root_rejects_symlinks(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SecretBrokerError) as unsafe:
        SecretBroker(linked)
    assert unsafe.value.reason_code == "unsafe_root"
