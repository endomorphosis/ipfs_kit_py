"""Async runtime client and adapters for the versioned Iroh sidecar boundary."""

from __future__ import annotations

import asyncio
import inspect
import itertools
import math
import os
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .errors import (
    IrohCancelledError,
    IrohError,
    IrohProtocolError,
    IrohTimeoutError,
    IrohUnavailableError,
    IrohUnsupportedVersionError,
    error_from_code,
)
from .protocol import (
    MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    REQUIRED_METHODS,
    RPCRequest,
    RPCResponse,
    RuntimeCapabilities,
    RuntimeVersion,
    decode_frame,
)


DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_OUTPUT = 64 * 1024
REDACTED = "<redacted>"

# Key matching intentionally uses semantic terms rather than exact spellings so
# snake_case, kebab-case and camelCase secret fields all fail closed.
_SENSITIVE_KEY = re.compile(
    r"(?:secret|token|ticket|password|passwd|private.?key|node.?key|"
    r"author.?key|api.?key|access.?key|capability|credential|authorization|"
    r"cookie|rpc.?payload|peer.?id|secret.?store)",
    re.IGNORECASE,
)
_URI_CREDENTIAL = re.compile(r"(?i)(credential://iroh/)[^\s/?#]+")
_BEARER = re.compile(r"(?i)\b(bearer|token)\s+[A-Za-z0-9._~+\-/=]+")
_URL_USERINFO = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^\s/@:]+(?::[^\s/@]*)?@")
_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:token|ticket|secret|password|credential|capability)=)[^&#\s]+"
)
_IROH_SECRET = re.compile(
    r"(?i)\b(iroh[-_](?:doc[-_])?(?:ticket|capability|private[-_]?key)[=:\s]+)"
    r"[^\s,;]+"
)

_COMPONENT_NAMES = frozenset({"iroh", "iroh_blobs", "iroh_docs", "iroh_gossip"})
_DEFAULT_COMPONENT_VERSIONS = {
    "iroh": "1.0.2",
    "iroh_blobs": "0.103.0",
    "iroh_docs": "0.101.0",
    "iroh_gossip": "0.101.0",
}


def redact(value: Any) -> Any:
    """Return a recursively redacted, log-safe copy of ``value``.

    The function never mutates caller-owned containers.  Binary values are
    always opaque at this boundary: attempting to decode them merely creates a
    second opportunity to leak secret or peer-sensitive payloads.
    """

    if isinstance(value, Mapping):
        return {
            key: REDACTED if _SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact(item) for item in value]
    if isinstance(value, (bytes, bytearray, memoryview)):
        return REDACTED
    if isinstance(value, str):
        result = _URI_CREDENTIAL.sub(r"\1" + REDACTED, value)
        result = _BEARER.sub(lambda match: f"{match.group(1)} {REDACTED}", result)
        result = _URL_USERINFO.sub(r"\1" + REDACTED + "@", result)
        result = _QUERY_SECRET.sub(r"\1" + REDACTED, result)
        return _IROH_SECRET.sub(r"\1" + REDACTED, result)
    return value


@runtime_checkable
class RPCAdapter(Protocol):
    """Structural transport interface consumed by :class:`IrohRuntimeClient`."""

    async def request(
        self, request: RPCRequest, *, timeout: float
    ) -> RPCResponse | Mapping[str, Any]: ...

    async def cancel(self, request_id: str) -> None: ...

    async def close(self) -> None: ...


@dataclass(slots=True)
class SidecarRPCAdapter:
    """One-request-per-connection JSON-RPC adapter for a local Unix socket.

    A fresh local connection makes timeout and task cancellation unambiguous:
    closing it cannot corrupt another in-flight request. Windows named pipes
    can be supplied through ``connector`` until asyncio exposes a portable pipe
    API.
    """

    endpoint: str | os.PathLike[str]
    connector: (
        Callable[
            ..., Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]
        ]
        | None
    ) = None
    max_frame_bytes: int = MAX_FRAME_BYTES

    def __post_init__(self) -> None:
        self.endpoint = os.fspath(self.endpoint)
        if not self.endpoint:
            raise ValueError("sidecar endpoint must not be empty")
        if (
            isinstance(self.max_frame_bytes, bool)
            or not isinstance(self.max_frame_bytes, int)
            or self.max_frame_bytes <= 0
            or self.max_frame_bytes > MAX_FRAME_BYTES
        ):
            raise ValueError(
                f"max_frame_bytes must be an integer from 1 to {MAX_FRAME_BYTES}"
            )

    async def request(self, request: RPCRequest, *, timeout: float) -> RPCResponse:
        del timeout  # The runtime client owns the single operation timeout.
        try:
            if self.connector is None:
                # asyncio's default stream limit is only 64 KiB, whereas a
                # protocol-1 response may be up to MAX_FRAME_BYTES.
                reader, writer = await asyncio.open_unix_connection(
                    path=self.endpoint, limit=self.max_frame_bytes + 1
                )
            else:
                try:
                    reader, writer = await self.connector(path=self.endpoint)
                except TypeError:
                    # Test adapters and Windows connector shims commonly
                    # expose a positional-only endpoint.
                    reader, writer = await self.connector(self.endpoint)
        except (OSError, EOFError):
            raise IrohUnavailableError(
                "cannot connect to the local Iroh sidecar"
            ) from None

        try:
            writer.write(request.to_bytes())
            await writer.drain()
            try:
                payload = await reader.readline()
            except (ValueError, asyncio.LimitOverrunError):
                raise IrohProtocolError(
                    "sidecar returned an oversized or incomplete frame"
                ) from None
            if not payload:
                raise IrohProtocolError(
                    "sidecar closed the connection without a response"
                )
            if len(payload) > self.max_frame_bytes + 1 or not payload.endswith(b"\n"):
                raise IrohProtocolError(
                    "sidecar returned an oversized or incomplete frame"
                )
            return RPCResponse.from_dict(
                decode_frame(payload), expected_id=request.request_id
            )
        except (ConnectionError, BrokenPipeError, EOFError):
            raise IrohUnavailableError("local Iroh sidecar connection failed") from None
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (AttributeError, ConnectionError, OSError):
                pass

    async def cancel(self, request_id: str) -> None:
        # Cancelling ``request`` closes its dedicated connection.  There is no
        # shared transport operation to cancel here.
        del request_id

    async def close(self) -> None:
        # Connections are per request and are closed in ``request``.
        return None


class DiagnosticCLIAdapter:
    """Side-effect-free adapter for the sole selected CLI command, ``--version``."""

    def __init__(
        self,
        executable: str | os.PathLike[str] = "ipfs-kit-iroh-sidecar",
        *,
        timeout: float = 5.0,
        expected_sidecar_version: str = "0.1.0",
        expected_components: Mapping[str, str] | None = None,
        process_factory: Callable[..., Awaitable[Any]] | None = None,
        max_output: int = DEFAULT_MAX_OUTPUT,
    ) -> None:
        self.executable = os.fspath(executable)
        if not self.executable:
            raise ValueError("diagnostic executable must not be empty")
        self.timeout = _validate_timeout(timeout)
        self.expected_sidecar_version = expected_sidecar_version
        self.expected_components = _normalize_expected_components(
            expected_components
        )
        self._process_factory = process_factory or asyncio.create_subprocess_exec
        if (
            isinstance(max_output, bool)
            or not isinstance(max_output, int)
            or max_output <= 0
        ):
            raise ValueError("max_output must be a positive integer")
        self.max_output = max_output

    async def version(self, *, timeout: float | None = None) -> RuntimeVersion:
        deadline = self.timeout if timeout is None else _validate_timeout(timeout)
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            process = await asyncio.wait_for(
                self._process_factory(
                    self.executable,
                    "--version",
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=deadline,
            )
        except asyncio.TimeoutError:
            raise IrohTimeoutError(
                "Iroh sidecar diagnostic timed out", operation="version"
            ) from None
        except asyncio.CancelledError:
            raise IrohCancelledError(
                "Iroh sidecar diagnostic was cancelled", operation="version"
            ) from None
        except (OSError, ValueError):
            raise IrohUnavailableError(
                "Iroh sidecar diagnostic executable is unavailable",
                operation="version",
            ) from None

        remaining = deadline - (loop.time() - started)
        if remaining <= 0:
            await _kill_process(process)
            raise IrohTimeoutError(
                "Iroh sidecar diagnostic timed out", operation="version"
            )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=remaining
            )
        except asyncio.TimeoutError:
            await _kill_process(process)
            raise IrohTimeoutError(
                "Iroh sidecar diagnostic timed out", operation="version"
            ) from None
        except asyncio.CancelledError:
            await _kill_process(process)
            raise IrohCancelledError(
                "Iroh sidecar diagnostic was cancelled", operation="version"
            ) from None

        if not isinstance(stdout, bytes) or not isinstance(stderr, bytes):
            raise IrohProtocolError(
                "diagnostic process returned non-binary output", operation="version"
            )
        if len(stdout) > self.max_output or len(stderr) > self.max_output:
            raise IrohProtocolError(
                "diagnostic output exceeds the size limit", operation="version"
            )
        if process.returncode != 0 or stderr:
            raise IrohUnavailableError(
                "Iroh sidecar diagnostic failed", operation="version"
            )
        try:
            line = stdout.decode("utf-8")
            version = RuntimeVersion.from_cli_line(line)
            _verify_version(
                version,
                expected_sidecar_version=self.expected_sidecar_version,
                expected_components=self.expected_components,
                operation="version",
            )
        except UnicodeDecodeError:
            raise IrohProtocolError(
                "diagnostic output is not valid UTF-8", operation="version"
            ) from None
        except IrohProtocolError:
            # A malformed executable response must be safe to display and must
            # not include its stdout/stderr bytes.
            raise IrohUnavailableError(
                "Iroh sidecar diagnostic output is incompatible",
                operation="version",
            ) from None
        return version

    async def inspect(self, *, timeout: float | None = None) -> RuntimeVersion:
        return await self.version(timeout=timeout)


class IrohRuntimeClient:
    """Typed, version-negotiating client for the protocol-1 local sidecar."""

    def __init__(
        self,
        adapter: RPCAdapter | None = None,
        *,
        transport: RPCAdapter | None = None,
        endpoint: str | os.PathLike[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        protocol_version: int = PROTOCOL_VERSION,
        release_bundle: str = "iroh-1.0.2-ipfs-kit.1",
        sidecar_version: str = "0.1.0",
        component_versions: Mapping[str, str] | None = None,
        required_methods: Sequence[str] = tuple(sorted(REQUIRED_METHODS)),
    ) -> None:
        if isinstance(protocol_version, bool) or protocol_version != PROTOCOL_VERSION:
            raise IrohUnsupportedVersionError(
                "client protocol version is unsupported"
            )
        if adapter is not None and transport is not None:
            raise ValueError("provide only one of adapter or transport")
        adapter = adapter or transport
        if adapter is None:
            if endpoint is None:
                raise ValueError("adapter or local endpoint is required")
            adapter = SidecarRPCAdapter(endpoint)
        self.adapter = adapter
        self.timeout = _validate_timeout(timeout)
        self.protocol_version = protocol_version
        self.release_bundle = release_bundle
        self.sidecar_version = sidecar_version
        if not isinstance(release_bundle, str) or not release_bundle:
            raise ValueError("release_bundle must be a non-empty string")
        if not isinstance(sidecar_version, str) or not sidecar_version:
            raise ValueError("sidecar_version must be a non-empty string")
        self.component_versions = _normalize_expected_components(component_versions)
        self.required_methods = frozenset(required_methods)
        invalid_methods = self.required_methods - REQUIRED_METHODS
        if invalid_methods:
            raise ValueError("required_methods contains an unknown protocol method")
        self._ids = itertools.count(1)
        self._capabilities: RuntimeCapabilities | None = None
        self._version: RuntimeVersion | None = None
        self._negotiation_lock = asyncio.Lock()
        self._closed = False

    async def __aenter__(self) -> "IrohRuntimeClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self.adapter, "close", None)
        if close is not None:
            result = close()
            if inspect.isawaitable(result):
                await result

    async def request(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
        require_negotiation: bool = True,
    ) -> Any:
        """Issue one typed request and translate transport/sidecar failures."""

        if self._closed:
            raise IrohUnavailableError(
                "Iroh runtime client is closed", operation=method
            )
        if require_negotiation and not method.startswith("system."):
            await self.negotiate(timeout=timeout)
            assert self._capabilities is not None
            if not self._capabilities.supports(method):
                raise IrohUnavailableError(
                    "required sidecar capability is unavailable", operation=method
                )

        request_timeout = self.timeout if timeout is None else _validate_timeout(timeout)
        rpc_request = RPCRequest(
            f"py-{next(self._ids)}", method, dict(params or {})
        )
        try:
            response_value = await asyncio.wait_for(
                self.adapter.request(rpc_request, timeout=request_timeout),
                timeout=request_timeout,
            )
            response = (
                response_value
                if isinstance(response_value, RPCResponse)
                else RPCResponse.from_dict(
                    response_value, expected_id=rpc_request.request_id
                )
            )
        except asyncio.TimeoutError:
            await self._cancel(rpc_request.request_id)
            raise IrohTimeoutError(
                "Iroh sidecar request timed out", operation=method
            ) from None
        except asyncio.CancelledError:
            await self._cancel(rpc_request.request_id)
            raise IrohCancelledError(
                "Iroh sidecar request was cancelled", operation=method
            ) from None
        except IrohError as exc:
            if exc.operation is None:
                exc.operation = method
            raise
        except (ConnectionError, EOFError, OSError):
            raise IrohUnavailableError(
                "Iroh sidecar request failed", operation=method
            ) from None
        except Exception:
            # Adapter exceptions never cross the public boundary verbatim.
            raise IrohProtocolError(
                "Iroh RPC adapter failed", operation=method
            ) from None

        if response.request_id != rpc_request.request_id:
            raise IrohProtocolError(
                "RPC response request id does not match", operation=method
            )
        if response.protocol_version != self.protocol_version:
            raise IrohUnsupportedVersionError(
                "sidecar RPC protocol version is unsupported", operation=method
            )
        if response.error is not None:
            public_data = _public_error_metadata(response.error.data)
            raise error_from_code(
                response.error.code,
                _error_message(response.error.code),
                operation=method,
                metadata=public_data,
            )
        return response.result

    call = request

    async def version(
        self, *, timeout: float | None = None, refresh: bool = False
    ) -> RuntimeVersion:
        if self._version is not None and not refresh:
            return self._version
        result = await self.request(
            "system.version", timeout=timeout, require_negotiation=False
        )
        try:
            version = RuntimeVersion.from_mapping(result)
            _verify_version(
                version,
                expected_sidecar_version=self.sidecar_version,
                expected_components=self.component_versions,
                expected_bundle=self.release_bundle,
                operation="system.version",
            )
        except IrohError as exc:
            if exc.operation is None:
                exc.operation = "system.version"
            raise
        self._version = version
        return version

    async def capabilities(
        self, *, timeout: float | None = None, refresh: bool = False
    ) -> RuntimeCapabilities:
        if self._capabilities is not None and not refresh:
            return self._capabilities
        result = await self.request(
            "system.capabilities", timeout=timeout, require_negotiation=False
        )
        try:
            capabilities = RuntimeCapabilities.from_result(result)
        except IrohError as exc:
            if exc.operation is None:
                exc.operation = "system.capabilities"
            raise
        missing = self.required_methods - capabilities.methods
        if missing:
            raise IrohUnavailableError(
                "Iroh sidecar is missing required capabilities",
                operation="system.capabilities",
                metadata={"missing_methods": sorted(missing)},
            )
        self._capabilities = capabilities
        return capabilities

    detect_capabilities = capabilities

    async def negotiate(
        self, *, timeout: float | None = None, refresh: bool = False
    ) -> RuntimeCapabilities:
        if not refresh and self._version is not None and self._capabilities is not None:
            return self._capabilities
        async with self._negotiation_lock:
            if not refresh and self._version is not None and self._capabilities is not None:
                return self._capabilities
            await self.version(timeout=timeout, refresh=refresh)
            return await self.capabilities(timeout=timeout, refresh=refresh)

    async def health(self, *, timeout: float | None = None) -> Mapping[str, Any]:
        result = await self.request(
            "system.health", timeout=timeout, require_negotiation=False
        )
        if not isinstance(result, Mapping) or result.get("healthy") is not True:
            raise IrohUnavailableError(
                "Iroh sidecar is unhealthy", operation="system.health"
            )
        return dict(result)

    async def diagnostics(
        self, *, timeout: float | None = None
    ) -> Mapping[str, Any]:
        result = await self.request(
            "system.health", timeout=timeout, require_negotiation=False
        )
        if not isinstance(result, Mapping):
            raise IrohProtocolError(
                "Iroh health result must be an object", operation="system.health"
            )
        # Diagnostics are still a public boundary: recurse through redaction
        # even though a protocol-1 sidecar promises secret-free health fields.
        return redact(dict(result))

    async def _cancel(self, request_id: str) -> None:
        cancel = getattr(self.adapter, "cancel", None)
        if cancel is None:
            return
        try:
            result = cancel(request_id)
            if inspect.isawaitable(result):
                # The caller's task is already cancelling, so shield the brief
                # transport cleanup/cancellation signal.
                await asyncio.shield(result)
        except (Exception, asyncio.CancelledError):
            # Cancellation is best effort and must not replace the primary
            # timeout/cancelled result.
            return


def _validate_timeout(value: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
    ):
        raise ValueError("timeout must be a finite positive number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("timeout must be a finite positive number")
    return result


def _normalize_expected_components(
    value: Mapping[str, str] | None,
) -> dict[str, str]:
    result = dict(_DEFAULT_COMPONENT_VERSIONS if value is None else value)
    if set(result) != _COMPONENT_NAMES or any(
        not isinstance(version, str) or not version for version in result.values()
    ):
        raise ValueError(
            "component versions must contain exactly iroh, iroh_blobs, "
            "iroh_docs, and iroh_gossip"
        )
    return result


async def _kill_process(process: Any) -> None:
    try:
        process.kill()
    except (ProcessLookupError, OSError):
        pass
    try:
        await asyncio.shield(process.wait())
    except (ProcessLookupError, OSError, asyncio.CancelledError):
        pass


def _verify_version(
    version: RuntimeVersion,
    *,
    expected_sidecar_version: str,
    expected_components: Mapping[str, str],
    operation: str,
    expected_bundle: str | None = None,
) -> None:
    actual = {
        "iroh": version.iroh,
        "iroh_blobs": version.iroh_blobs,
        "iroh_docs": version.iroh_docs,
        "iroh_gossip": version.iroh_gossip,
    }
    if (
        version.protocol != PROTOCOL_VERSION
        or version.sidecar != expected_sidecar_version
        or any(actual.get(name) != value for name, value in expected_components.items())
        or (
            expected_bundle is not None
            and version.release_bundle != expected_bundle
        )
    ):
        raise IrohUnsupportedVersionError(
            "Iroh sidecar release bundle is unsupported", operation=operation
        )


def _public_error_metadata(data: Mapping[str, Any]) -> dict[str, Any]:
    """Allow only contract-public conflict/integrity context across the boundary."""

    allowed = {
        "expected_revision",
        "actual_revision",
        "revision",
        "manifest_hash",
        "expected_manifest_hash",
        "actual_manifest_hash",
        "offset",
        "length",
    }
    return {key: redact(value) for key, value in data.items() if key in allowed}


def _error_message(code: str) -> str:
    messages = {
        "invalid_url": "Iroh URL is invalid",
        "invalid_path": "Iroh path is invalid",
        "invalid_hash": "Iroh hash is invalid",
        "invalid_manifest": "Iroh manifest is invalid",
        "invalid_config": "Iroh backend configuration is invalid",
        "unsupported_version": "Iroh version is unsupported",
        "unsupported_operation": "Iroh operation is unsupported",
        "not_found": "Iroh resource was not found",
        "already_exists": "Iroh resource already exists",
        "not_empty": "Iroh directory is not empty",
        "permission_denied": "Iroh operation was denied",
        "conflict": "Iroh manifest update conflicted",
        "unavailable": "Iroh sidecar is unavailable",
        "timeout": "Iroh sidecar request timed out",
        "cancelled": "Iroh sidecar request was cancelled",
        "integrity_error": "Iroh integrity verification failed",
        "io_error": "Iroh I/O operation failed",
        "protocol_error": "Iroh sidecar protocol error",
    }
    return messages.get(code, "Iroh sidecar returned an invalid error")


RuntimeClient = IrohRuntimeClient
SidecarAdapter = SidecarRPCAdapter
CLIAdapter = DiagnosticCLIAdapter
redact_secrets = redact


__all__ = [
    "DEFAULT_TIMEOUT",
    "DEFAULT_MAX_OUTPUT",
    "REDACTED",
    "RPCAdapter",
    "SidecarRPCAdapter",
    "DiagnosticCLIAdapter",
    "IrohRuntimeClient",
    "redact",
    "RuntimeClient",
    "SidecarAdapter",
    "CLIAdapter",
    "redact_secrets",
]
