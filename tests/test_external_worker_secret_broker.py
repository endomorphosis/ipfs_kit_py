"""EAAEF-124: opaque secret handles bind lease/task/policy and revoke at terminal."""

from __future__ import annotations

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
