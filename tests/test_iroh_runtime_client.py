"""Contract tests for the versioned Iroh runtime client boundary."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from ipfs_kit_py.iroh.client import (
    DiagnosticCLIAdapter,
    IrohRuntimeClient,
    redact,
)
from ipfs_kit_py.iroh.errors import (
    IrohCancelledError,
    IrohConflictError,
    IrohProtocolError,
    IrohTimeoutError,
    IrohUnavailableError,
    IrohUnsupportedVersionError,
)
from ipfs_kit_py.iroh.protocol import PROTOCOL_VERSION, REQUIRED_METHODS, RPCRequest


VERSION = {
    "sidecar_version": "0.1.0",
    "protocol_version": 1,
    "release_bundle": "iroh-1.0.2-ipfs-kit.1",
    "iroh": "1.0.2",
    "iroh_blobs": "0.103.0",
    "iroh_docs": "0.101.0",
    "iroh_gossip": "0.101.0",
}


class FakeAdapter:
    def __init__(self, results: dict[str, Any], *, delay: float = 0) -> None:
        self.results = results
        self.delay = delay
        self.requests: list[RPCRequest] = []
        self.cancelled: list[str] = []
        self.closed = False

    async def request(self, request: RPCRequest, *, timeout: float) -> dict[str, Any]:
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        value = self.results[request.method]
        if callable(value):
            value = value(request)
        if isinstance(value, Exception):
            raise value
        body = value if isinstance(value, dict) and ({"result", "error"} & value.keys()) else {"result": value}
        return {
            "jsonrpc": "2.0",
            "protocol_version": PROTOCOL_VERSION,
            "id": request.request_id,
            **body,
        }

    async def cancel(self, request_id: str) -> None:
        self.cancelled.append(request_id)

    async def close(self) -> None:
        self.closed = True


def system_results() -> dict[str, Any]:
    return {
        "system.version": VERSION,
        "system.capabilities": {
            "protocol_version": 1,
            "methods": sorted(REQUIRED_METHODS),
        },
        "system.health": {"healthy": True},
    }


@pytest.mark.asyncio
async def test_output_is_typed_and_storage_calls_negotiate_once() -> None:
    adapter = FakeAdapter(
        {
            **system_results(),
            "blobs.stat": {"hash": "ab" * 32, "size": 3},
        }
    )
    async with IrohRuntimeClient(adapter) as client:
        version = await client.version()
        result = await client.request("blobs.stat", {"hash": "ab" * 32})
        await client.request("blobs.stat", {"hash": "ab" * 32})

    assert version.sidecar == "0.1.0"
    assert version.protocol_version == 1
    assert result["size"] == 3
    methods = [request.method for request in adapter.requests]
    assert methods.count("system.version") == 1
    assert methods.count("system.capabilities") == 1
    assert adapter.closed is True


@pytest.mark.asyncio
async def test_timeout_is_typed_and_attempts_transport_cancellation() -> None:
    adapter = FakeAdapter(system_results(), delay=0.1)
    client = IrohRuntimeClient(adapter, timeout=0.01)
    with pytest.raises(IrohTimeoutError) as raised:
        await client.version()
    assert raised.value.code == "timeout"
    assert raised.value.operation == "system.version"
    assert adapter.cancelled == [adapter.requests[0].request_id]


@pytest.mark.asyncio
async def test_caller_cancellation_is_typed_and_attempts_transport_cancellation() -> None:
    adapter = FakeAdapter(system_results(), delay=10)
    client = IrohRuntimeClient(adapter)
    task = asyncio.create_task(client.version())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(IrohCancelledError) as raised:
        await task
    assert raised.value.code == "cancelled"
    assert adapter.cancelled == [adapter.requests[0].request_id]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"protocol_version": 2},
        {"sidecar_version": "0.2.0"},
        {"iroh_blobs": "0.104.0"},
        {"release_bundle": "other"},
    ],
)
async def test_version_skew_fails_closed(change: dict[str, Any]) -> None:
    version = {**VERSION, **change}
    client = IrohRuntimeClient(FakeAdapter({"system.version": version}))
    with pytest.raises(IrohUnsupportedVersionError) as raised:
        await client.version()
    assert raised.value.code == "unsupported_version"


@pytest.mark.asyncio
async def test_missing_capability_fails_before_storage_operation() -> None:
    methods = sorted(REQUIRED_METHODS - {"blobs.stat"})
    adapter = FakeAdapter(
        {
            **system_results(),
            "system.capabilities": {"protocol_version": 1, "methods": methods},
        }
    )
    client = IrohRuntimeClient(adapter)
    with pytest.raises(IrohUnavailableError) as raised:
        await client.request("blobs.stat")
    assert raised.value.metadata == {"missing_methods": ["blobs.stat"]}
    assert "blobs.stat" not in [request.method for request in adapter.requests]


@pytest.mark.asyncio
async def test_remote_error_is_typed_and_only_public_metadata_crosses_boundary() -> None:
    adapter = FakeAdapter(
        {
            **system_results(),
            "manifests.compare_and_swap": {
                "error": {
                    "code": "conflict",
                    "message": "token Bearer very-secret disagrees",
                    "data": {"actual_revision": 7, "ticket": "secret-ticket"},
                }
            },
        }
    )
    client = IrohRuntimeClient(adapter)
    with pytest.raises(IrohConflictError) as raised:
        await client.request("manifests.compare_and_swap")
    assert raised.value.code == "conflict"
    assert raised.value.metadata == {"actual_revision": 7}
    assert "very-secret" not in str(raised.value)
    assert "very-secret" not in repr(raised.value.as_dict())


def test_recursive_redaction_does_not_mutate_input() -> None:
    source = {
        "namespace": "public",
        "node_key": "private",
        "nested": {
            "ticket_ref": "credential://iroh/example",
            "message": "Bearer abc.def",
        },
        "payload": b"opaque",
    }
    result = redact(source)
    assert source["node_key"] == "private"
    assert result["node_key"] == "<redacted>"
    assert result["nested"]["message"] == "Bearer <redacted>"
    assert result["payload"] == "<redacted>"


class FakeProcess:
    def __init__(
        self, stdout: bytes, stderr: bytes = b"", returncode: int = 0
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout, self.stderr

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return self.returncode


@pytest.mark.asyncio
async def test_diagnostic_cli_uses_an_argument_vector_and_parses_exact_output() -> None:
    calls: list[tuple[Any, ...]] = []

    async def factory(*args: Any, **kwargs: Any) -> FakeProcess:
        assert "shell" not in kwargs
        calls.append(args)
        return FakeProcess(
            b"ipfs-kit-iroh-sidecar 0.1.0 (protocol 1; iroh 1.0.2; "
            b"iroh-blobs 0.103.0; iroh-docs 0.101.0; iroh-gossip 0.101.0)\n"
        )

    version = await DiagnosticCLIAdapter(
        "/safe path/sidecar", process_factory=factory
    ).version()
    assert calls == [("/safe path/sidecar", "--version")]
    assert version.iroh_docs == "0.101.0"


@pytest.mark.asyncio
async def test_diagnostic_cli_rejects_stderr_and_malformed_output_without_leaking_it() -> None:
    async def factory(*args: Any, **kwargs: Any) -> FakeProcess:
        return FakeProcess(b"secret-ticket", b"warning: secret-ticket")

    with pytest.raises(IrohUnavailableError) as raised:
        await DiagnosticCLIAdapter(process_factory=factory).version()
    assert "secret-ticket" not in str(raised.value)


def test_corrupt_response_is_a_protocol_error() -> None:
    from ipfs_kit_py.iroh.protocol import decode_frame

    with pytest.raises(IrohProtocolError):
        decode_frame(b'{"not":"complete"\n')


def test_protocol_rejects_non_json_params_and_duplicate_capabilities() -> None:
    from ipfs_kit_py.iroh.protocol import RuntimeCapabilities

    with pytest.raises(IrohProtocolError):
        RPCRequest("id", "blobs.stat", {"bad": {1, 2}})
    with pytest.raises(IrohProtocolError):
        RuntimeCapabilities.from_result(
            {"protocol_version": 1, "methods": ["blobs.stat", "blobs.stat"]}
        )
