"""Safety checks for the legacy MCP facade's explicit backend boundary."""

from __future__ import annotations

import sys
from types import ModuleType

import anyio
import pytest

from ipfs_kit_py.mcp_server import core_operations
from ipfs_kit_py.mcp_server.mcplusplus import artifacts


def test_constructor_failure_never_selects_a_successful_stub(monkeypatch) -> None:
    failing_module = ModuleType("ipfs_kit_py.ipfs_kit")

    class _FailingFactory:
        @staticmethod
        def create(**_kwargs):
            raise RuntimeError("fixture constructor failure")

    failing_module.ipfs_kit = _FailingFactory
    monkeypatch.setitem(sys.modules, "ipfs_kit_py.ipfs_kit", failing_module)
    monkeypatch.setattr(core_operations, "_kit", None)

    async def invoke() -> dict:
        return await core_operations._call(
            "ipfs_add",
            file_path="must-not-be-reported-as-added",
        )

    result = anyio.run(invoke)

    assert result["status"] == "error"
    assert result["result"]["success"] is False
    assert result["result"]["error_type"] == "unsupported_operation"
    assert not hasattr(core_operations, "_StubKit")


def test_missing_bound_backend_method_returns_typed_failure() -> None:
    async def invoke() -> dict:
        return await core_operations._call("ipfs_dag_put", data={"a": 1})

    with core_operations.use_core_backend(object()):
        result = anyio.run(invoke)

    assert result == {
        "status": "error",
        "result": {
            "success": False,
            "operation": "ipfs_dag_put",
            "error": "backend operation is unavailable",
            "error_type": "unsupported_operation",
            "reason": "object",
            "recoverable": False,
        },
    }


def test_context_local_bindings_do_not_cross_concurrent_requests() -> None:
    class _Backend:
        def __init__(self, identity: str) -> None:
            self.identity = identity

        async def ipfs_id(self) -> dict:
            await anyio.sleep(0)
            return {"success": True, "id": self.identity}

    observed: dict[str, str] = {}

    async def invoke(identity: str) -> None:
        with core_operations.use_core_backend(_Backend(identity)):
            await anyio.sleep(0)
            result = await core_operations._call("ipfs_id")
            observed[identity] = result["result"]["id"]

    async def run_concurrently() -> None:
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(invoke, "backend-a")
            tasks.start_soon(invoke, "backend-b")

    anyio.run(run_concurrently)

    assert observed == {
        "backend-a": "backend-a",
        "backend-b": "backend-b",
    }


def test_bound_backend_exception_is_a_typed_failure_without_exception_text() -> None:
    class _FailingBackend:
        async def ipfs_id(self) -> dict:
            raise RuntimeError("private provider detail")

    with core_operations.use_core_backend(_FailingBackend()):
        result = anyio.run(core_operations._call, "ipfs_id")

    assert result["status"] == "error"
    assert result["result"]["error_type"] == "RuntimeError"
    assert "private provider detail" not in str(result)


@pytest.mark.parametrize(
    "malformed",
    [
        "scalar-result",
        {"cid": "bafy-missing-success"},
        {"success": 1, "cid": "bafy-truthy-non-bool"},
    ],
)
def test_malformed_backend_results_fail_closed(malformed) -> None:
    class _MalformedBackend:
        async def ipfs_id(self):
            return malformed

    with core_operations.use_core_backend(_MalformedBackend()):
        result = anyio.run(core_operations._call, "ipfs_id")

    assert result == {
        "status": "error",
        "result": {
            "success": False,
            "operation": "ipfs_id",
            "error": "backend returned an invalid operation result",
            "error_type": "invalid_backend_result",
            "recoverable": False,
        },
    }


def test_profile_b_normalization_keeps_nested_domain_fields_content_bound() -> None:
    left = {
        "_dispatch": {"request_id": "dispatcher-a"},
        "request_id": "domain-a",
        "result": {
            "request_id": "domain-a",
            "timestamp": "2026-08-03T00:00:00Z",
            "transport": "domain-protocol-a",
        },
    }
    right = {
        "_dispatch": {"request_id": "dispatcher-b"},
        "request_id": "domain-b",
        "result": {
            "request_id": "domain-b",
            "timestamp": "2026-08-04T00:00:00Z",
            "transport": "domain-protocol-b",
        },
    }

    left_payload = artifacts.semantic_result_payload(left)
    right_payload = artifacts.semantic_result_payload(right)

    assert "_dispatch" not in left_payload
    assert left_payload["request_id"] == "domain-a"
    assert right_payload["request_id"] == "domain-b"
    assert left_payload["result"] == left["result"]
    assert right_payload["result"] == right["result"]
    assert artifacts.semantic_result_payload(
        {**left, "_dispatch": {"request_id": "dispatcher-c"}}
    ) == left_payload
    assert artifacts.compute_artifact_cid(left_payload) != artifacts.compute_artifact_cid(
        right_payload
    )
