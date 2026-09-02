"""PCPR-026 Python/CLI/MCP/MCP++ parity surface.

Binds the live local POSIX store to the canonical operation registry and
projects put/get/digest/delete through Python, CLI, MCP, and MCP++ adapters
under AllInterfaceParityPolicy@1. Adapter sessions are not live MCP server
processes, not pinned IPFS, and not a closed PCPR release.

Fail-closed invariants:

* semantic payloads match across python/cli/mcp/mcpp after transport-only
  field strip;
* CIDs are produced by the live local store, never fabricated;
* hermetic or simulated adapters cannot mint live qualification;
* missing live MCP servers and missing IPFS stay typed unavailable;
* this surface never writes DuckDB or Quack state.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Final

from ipfs_kit_py.assurance.local_durable import (
    BACKEND_ID as LOCAL_BACKEND_ID,
    INTERFACE as LOCAL_ADAPTER_INTERFACE,
    SCHEMA as LOCAL_ADAPTER_SCHEMA,
    LiveLocalBackendError,
    LiveLocalFilesystemAdapter,
)
from ipfs_kit_py.cli.operation_adapter import CLIAdapter
from ipfs_kit_py.core.operation_contracts import (
    OPERATION_RESULT_SCHEMA,
    STORAGE_ERROR_SCHEMA,
    ErrorCategory,
    ErrorCode,
    OperationResult,
    OperationState,
    Retryability,
    StorageError,
)
from ipfs_kit_py.core.operation_registry import (
    AuthorizationRequirement,
    CapabilityTier,
    OperationDefinition,
    OperationRegistry,
)
from ipfs_kit_py.core.service_router import DispatchContext, ServiceRouter
from ipfs_kit_py.high_level_api.operation_adapter import PythonAdapter
from ipfs_kit_py.mcp_server.tools.operation_adapter import (
    MCPPlusPlusToolAdapter,
    MCPToolAdapter,
    semantic_payload,
    strip_transport_fields,
)


INTERFACE: Final = "InterfaceParitySurface@1"
SCHEMA: Final = "ipfs_kit_py/assurance/interface-parity@1"
BACKEND_ID: Final = "interface_parity"
SUPPORT_CLASS: Final = "conditional"
LIVE_SUPPORT_CLAIM: Final = False
CERTIFICATION_SCOPE: Final = (
    "pcpr-026-python-cli-mcp-mcpp-adapter-parity; not a closed PCPR release"
)
POLICY: Final = "AllInterfaceParityPolicy@1"
HANDLER_ROUTE: Final = "pcpr-026-local-durable"
CAPABILITY: Final = "storage.local-durable"
REQUEST_SCHEMA: Final = "ipfs_kit_py/assurance/interface-parity-request@1"
PARITY_PAYLOAD: Final = b"pcpr-026-local-durable-parity-vector-v1"
SURFACES: Final[tuple[str, ...]] = ("python", "cli", "mcp", "mcpp")
OPERATIONS: Final[tuple[str, ...]] = ("put", "get", "digest", "delete")
PUBLIC_NAMES: Final[Mapping[str, str]] = {
    "put": "local-durable-put",
    "get": "local-durable-get",
    "digest": "local-durable-digest",
    "delete": "local-durable-delete",
}
OPERATION_IDS: Final[Mapping[str, str]] = {
    "put": "storage.local-durable.put",
    "get": "storage.local-durable.get",
    "digest": "storage.local-durable.digest",
    "delete": "storage.local-durable.delete",
}


class InterfaceParityError(ValueError):
    """Malformed parity request or a forbidden authority claim."""


def _transport_names(public_name: str) -> dict[str, str]:
    return {
        "python": public_name,
        "cli": public_name,
        "mcp": public_name,
        "mcpp": public_name,
    }


def parity_operation_definitions() -> tuple[OperationDefinition, ...]:
    return tuple(
        OperationDefinition(
            operation_id=OPERATION_IDS[operation],
            version=1,
            request_schema=REQUEST_SCHEMA,
            result_schema=OPERATION_RESULT_SCHEMA,
            error_schema=STORAGE_ERROR_SCHEMA,
            capability=CAPABILITY,
            authorization=AuthorizationRequirement.public(),
            handler_route=HANDLER_ROUTE,
            transport_names=_transport_names(PUBLIC_NAMES[operation]),
            support_tier=CapabilityTier.CONDITIONAL,
        )
        for operation in OPERATIONS
    )


def _request_id(operation: str, request: Mapping[str, Any]) -> str:
    supplied = request.get("request_id")
    if isinstance(supplied, str) and supplied.strip():
        return supplied.strip()
    path = request.get("path")
    suffix = "missing"
    if isinstance(path, str) and path.strip():
        suffix = path.strip().replace("/", "-").replace(".", "-")
    return f"pcpr-026-{operation}-{suffix}"


def _decode_payload(request: Mapping[str, Any]) -> bytes:
    encoded = request.get("data_b64")
    if not isinstance(encoded, str) or not encoded:
        raise InterfaceParityError("put requires data_b64")
    try:
        return base64.b64decode(encoded.encode("ascii"), validate=True)
    except (ValueError, TypeError) as exc:
        raise InterfaceParityError("data_b64 is not valid base64") from exc


def _path(request: Mapping[str, Any]) -> str:
    path = request.get("path")
    if not isinstance(path, str) or not path.strip():
        raise InterfaceParityError("path is required")
    return path.strip()


def _accepted(
    *,
    request_id: str,
    operation_id: str,
    content_cid: str,
) -> OperationResult:
    return OperationResult(
        request_id=request_id,
        operation_id=operation_id,
        state=OperationState.ACCEPTED,
        success=True,
        resulting_content_cid=content_cid,
        backend_id=LOCAL_BACKEND_ID,
    )


@dataclass
class LocalDurableParityService:
    """Canonical storage service wrapping the live local POSIX adapter."""

    store: LiveLocalFilesystemAdapter

    def execute(
        self,
        operation: OperationDefinition,
        request: Any,
        context: DispatchContext,
    ) -> OperationResult | StorageError:
        del context
        if not isinstance(request, Mapping):
            return StorageError(
                code=ErrorCode.INVALID_REQUEST,
                category=ErrorCategory.VALIDATION,
                message="request must be an object",
                retryability=Retryability.NEVER,
                state=OperationState.REJECTED,
                related_operation_id=operation.operation_id,
            )
        try:
            if operation.operation_id == OPERATION_IDS["put"]:
                result = self.store.put(_path(request), _decode_payload(request))
            elif operation.operation_id == OPERATION_IDS["get"]:
                result = self.store.get(_path(request))
            elif operation.operation_id == OPERATION_IDS["digest"]:
                result = self.store.digest(_path(request))
            elif operation.operation_id == OPERATION_IDS["delete"]:
                result = self.store.delete(_path(request))
            else:
                return StorageError(
                    code=ErrorCode.UNSUPPORTED,
                    category=ErrorCategory.UNSUPPORTED,
                    message="operation is not a local-durable parity operation",
                    retryability=Retryability.NEVER,
                    state=OperationState.UNSUPPORTED,
                    related_operation_id=operation.operation_id,
                )
        except InterfaceParityError as exc:
            return StorageError(
                code=ErrorCode.INVALID_REQUEST,
                category=ErrorCategory.VALIDATION,
                message=str(exc),
                retryability=Retryability.NEVER,
                state=OperationState.REJECTED,
                related_operation_id=operation.operation_id,
            )
        except LiveLocalBackendError as exc:
            return exc.error
        verb = operation.operation_id.rsplit(".", 1)[-1]
        return _accepted(
            request_id=_request_id(verb, request),
            operation_id=operation.operation_id,
            content_cid=result.resulting_content_cid,
        )


@dataclass
class InterfaceParityStack:
    """One bound registry, router, adapters, and live local store."""

    root: Path
    store: LiveLocalFilesystemAdapter
    registry: OperationRegistry
    router: ServiceRouter
    python: PythonAdapter
    cli: CLIAdapter
    mcp: MCPToolAdapter
    mcpp: MCPPlusPlusToolAdapter

    def close(self) -> None:
        self.store.close()


def build_parity_stack(root: str | Path) -> InterfaceParityStack:
    store = LiveLocalFilesystemAdapter(root)
    registry = OperationRegistry(parity_operation_definitions())
    router = ServiceRouter(registry)
    router.bind_service(
        HANDLER_ROUTE,
        LocalDurableParityService(store),
        capabilities={CAPABILITY},
    )
    return InterfaceParityStack(
        root=Path(root).resolve(),
        store=store,
        registry=registry,
        router=router,
        python=PythonAdapter(registry, router),
        cli=CLIAdapter(registry, router, program_name="ipfs-kit-pcpr-026"),
        mcp=MCPToolAdapter(registry, router),
        mcpp=MCPPlusPlusToolAdapter(registry, router),
    )


def parity_payload_b64() -> str:
    return base64.b64encode(PARITY_PAYLOAD).decode("ascii")


def parity_cid() -> str:
    return LiveLocalFilesystemAdapter.content_cid(PARITY_PAYLOAD)


def make_request(operation: str, path: str, *, request_id: str | None = None) -> dict[str, Any]:
    verb = operation if operation in OPERATIONS else operation.rsplit("-", 1)[-1]
    payload: dict[str, Any] = {
        "request_id": request_id or f"pcpr-026-{verb}-{path.replace('/', '-')}",
        "path": path,
    }
    if verb == "put":
        payload["data_b64"] = parity_payload_b64()
    return payload


def call_python(stack: InterfaceParityStack, operation: str, request: Mapping[str, Any]) -> Any:
    return stack.python.call(PUBLIC_NAMES[operation], dict(request))


def invoke_cli(stack: InterfaceParityStack, operation: str, request: Mapping[str, Any]) -> Any:
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(stack.cli.invoke(PUBLIC_NAMES[operation], dict(request)))
    raise InterfaceParityError("CLI invoke cannot run inside an event loop")


def call_mcp(stack: InterfaceParityStack, operation: str, request: Mapping[str, Any]) -> Any:
    return stack.mcp.call(PUBLIC_NAMES[operation], {"request": dict(request)})


def call_mcpp_framed(
    stack: InterfaceParityStack,
    operation: str,
    request: Mapping[str, Any],
    *,
    framing: str = "stdio",
) -> Any:
    import asyncio

    return asyncio.run(
        stack.mcpp.call_framed(
            framing, PUBLIC_NAMES[operation], {"request": dict(request)}
        )
    )


def run_cli_stdout(
    stack: InterfaceParityStack, operation: str, request: Mapping[str, Any]
) -> tuple[int, dict[str, Any]]:
    stdout, stderr = StringIO(), StringIO()
    code = stack.cli.run(
        [
            PUBLIC_NAMES[operation],
            "--request-json",
            json.dumps(dict(request), separators=(",", ":")),
        ],
        stdout=stdout,
        stderr=stderr,
    )
    if stderr.getvalue():
        raise InterfaceParityError("CLI stderr must be empty")
    return code, json.loads(stdout.getvalue())


def call_mcp_jsonrpc(
    stack: InterfaceParityStack, operation: str, request: Mapping[str, Any]
) -> dict[str, Any]:
    import asyncio

    return asyncio.run(
        stack.mcp.handle_jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": f"pcpr-026-mcp-{operation}",
                "method": "tools/call",
                "params": {
                    "name": PUBLIC_NAMES[operation],
                    "arguments": {"request": dict(request)},
                },
            }
        )
    )


def resulting_cid(response: Any) -> str:
    if hasattr(response, "to_dict"):
        payload = response.to_dict()
    elif isinstance(response, Mapping):
        payload = dict(response)
    else:
        raise InterfaceParityError("response is not a mapping")
    record = ((payload.get("result") or {}) if isinstance(payload.get("result"), Mapping) else {})
    if isinstance(record, Mapping) and isinstance(record.get("record"), Mapping):
        cid = record["record"].get("resulting_content_cid")
        if isinstance(cid, str):
            return cid
    nested = payload.get("result")
    if isinstance(nested, Mapping) and isinstance(nested.get("record"), Mapping):
        cid = nested["record"].get("resulting_content_cid")
        if isinstance(cid, str):
            return cid
    raise InterfaceParityError("response is missing resulting_content_cid")


def parity_contract() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "interface": INTERFACE,
        "backend_id": BACKEND_ID,
        "support_class": SUPPORT_CLASS,
        "live_support_claim": LIVE_SUPPORT_CLAIM,
        "is_hermetic": False,
        "live_provider": True,
        "simulated": False,
        "production_authorized": False,
        "policy": POLICY,
        "surfaces": list(SURFACES),
        "operations": list(OPERATIONS),
        "local_adapter_schema": LOCAL_ADAPTER_SCHEMA,
        "local_adapter_interface": LOCAL_ADAPTER_INTERFACE,
        "local_backend_id": LOCAL_BACKEND_ID,
        "certification_scope": CERTIFICATION_SCOPE,
        "live_mcp_server": False,
        "live_ipfs": False,
    }


def refuse_simulated_as_live(adapter: Any) -> None:
    live_provider = bool(getattr(adapter, "live_provider", False))
    hermetic = bool(getattr(adapter, "is_hermetic", True))
    simulated = bool(getattr(adapter, "simulated", False))
    live_claim = bool(getattr(adapter, "live_support_claim", False))
    if hermetic or simulated or not live_provider or live_claim:
        raise InterfaceParityError(
            "hermetic or simulated adapters cannot mint live interface-parity qualification"
        )
    if getattr(adapter, "backend_id", None) not in {LOCAL_BACKEND_ID, BACKEND_ID}:
        raise InterfaceParityError(
            "interface parity requires the live local filesystem or parity surface"
        )


__all__ = [
    "INTERFACE",
    "SCHEMA",
    "BACKEND_ID",
    "SUPPORT_CLASS",
    "LIVE_SUPPORT_CLAIM",
    "CERTIFICATION_SCOPE",
    "POLICY",
    "PARITY_PAYLOAD",
    "SURFACES",
    "OPERATIONS",
    "PUBLIC_NAMES",
    "OPERATION_IDS",
    "InterfaceParityError",
    "InterfaceParityStack",
    "LocalDurableParityService",
    "build_parity_stack",
    "parity_contract",
    "parity_cid",
    "parity_payload_b64",
    "make_request",
    "call_python",
    "invoke_cli",
    "run_cli_stdout",
    "call_mcp",
    "call_mcpp_framed",
    "call_mcp_jsonrpc",
    "resulting_cid",
    "semantic_payload",
    "strip_transport_fields",
    "refuse_simulated_as_live",
]
