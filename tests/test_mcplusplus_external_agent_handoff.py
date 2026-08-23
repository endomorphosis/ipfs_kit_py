"""EAAEF-113: MCP++ handoff binder reuses existing profiles only."""

from __future__ import annotations

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.external_agent_handoff import (
    HANDOFF_OPERATIONS,
    ExternalAgentHandoffBindError,
    bind_handoff_operation,
)


def test_binds_existing_profiles_without_storage_authority() -> None:
    bound = bind_handoff_operation(
        "handoff",
        profiles={
            "interface": "profile-a",
            "artifact": "profile-b",
            "delegation": "profile-c",
            "event": "profile-f",
            "fencing": "durable-executor",
        },
        effects=("inspect_repository",),
    )
    assert bound["new_profile"] is False
    assert bound["storage_authority"] is False
    assert bound["operation"] == "handoff"
    assert set(HANDOFF_OPERATIONS)


def test_unknown_profile_and_storage_effects_fail_closed() -> None:
    with pytest.raises(ExternalAgentHandoffBindError, match="unknown MCP\\+\\+ profile"):
        bind_handoff_operation("status", profiles={"profile-i": "new"})
    with pytest.raises(ExternalAgentHandoffBindError, match="storage"):
        bind_handoff_operation("handoff", effects=("storage",))
    with pytest.raises(ExternalAgentHandoffBindError, match="storage"):
        bind_handoff_operation("handoff", effects=("Proof-Key",))
    with pytest.raises(ExternalAgentHandoffBindError, match="identifier"):
        bind_handoff_operation("status", profiles={"interface": "invented-profile"})
    with pytest.raises(ExternalAgentHandoffBindError, match="DurableExecutor"):
        bind_handoff_operation("resume", runtime_method="resume", durable_executor_configured=False)
    with pytest.raises(ExternalAgentHandoffBindError, match="unknown handoff") as unknown:
        bind_handoff_operation("grant_backend")
    assert unknown.value.reason_code == "unknown_operation"
    with pytest.raises(ExternalAgentHandoffBindError) as unconfigured:
        bind_handoff_operation(
            "resume", runtime_method="resume", durable_executor_configured=False
        )
    assert unconfigured.value.reason_code == "durable_executor_unconfigured"
