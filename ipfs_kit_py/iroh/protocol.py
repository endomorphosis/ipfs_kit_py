"""Version 1 wire types and validation for the IPFS Kit Iroh sidecar."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .errors import IrohProtocolError, IrohUnsupportedVersionError


PROTOCOL_VERSION = 1
JSONRPC_VERSION = "2.0"
MAX_FRAME_BYTES = 16 * 1024 * 1024

REQUIRED_METHODS = frozenset(
    {
        "system.version",
        "system.capabilities",
        "system.health",
        "system.shutdown",
        "blobs.ingest",
        "blobs.stat",
        "blobs.read_range",
        "blobs.protect",
        "blobs.release",
        "manifests.open",
        "manifests.create",
        "manifests.read",
        "manifests.compare_and_swap",
        "manifests.history",
        "sync.start",
        "sync.progress",
        "sync.cancel",
        "sync.status",
    }
)

_METHOD_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_VERSION_RE = re.compile(
    r"^ipfs-kit-iroh-sidecar (?P<sidecar>\d+\.\d+\.\d+) "
    r"\(protocol (?P<protocol>\d+); iroh (?P<iroh>\d+\.\d+\.\d+); "
    r"iroh-blobs (?P<blobs>\d+\.\d+\.\d+); "
    r"iroh-docs (?P<docs>\d+\.\d+\.\d+); "
    r"iroh-gossip (?P<gossip>\d+\.\d+\.\d+)\)\n$"
)


def _validate_json(value: Any, path: str = "value") -> None:
    """Reject values JSON cannot represent deterministically and safely."""

    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise IrohProtocolError(f"{path} contains a non-finite number")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise IrohProtocolError(f"{path} contains a non-string object key")
            _validate_json(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_json(item, f"{path}[{index}]")
        return
    raise IrohProtocolError(f"{path} is not JSON-compatible")


def _object(value: Any, description: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IrohProtocolError(f"{description} must be a JSON object")
    return value


@dataclass(frozen=True, slots=True)
class RPCRequest:
    """One protocol-1 JSON-RPC request."""

    request_id: str
    method: str
    params: Mapping[str, Any] = field(default_factory=dict)
    protocol_version: int = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id:
            raise IrohProtocolError("request id must be a non-empty string")
        if not isinstance(self.method, str) or not _METHOD_RE.fullmatch(self.method):
            raise IrohProtocolError("invalid RPC method identifier")
        if (
            isinstance(self.protocol_version, bool)
            or self.protocol_version != PROTOCOL_VERSION
        ):
            raise IrohUnsupportedVersionError("unsupported request protocol version")
        _object(self.params, "request params")
        _validate_json(self.params, "params")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))

    @property
    def id(self) -> str:
        return self.request_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "jsonrpc": JSONRPC_VERSION,
            "protocol_version": self.protocol_version,
            "id": self.request_id,
            "method": self.method,
            "params": dict(self.params),
        }

    def to_bytes(self) -> bytes:
        return encode_frame(self.to_dict())


@dataclass(frozen=True, slots=True)
class RPCError:
    code: str
    message: str
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RPCResponse:
    request_id: str
    result: Any = None
    error: RPCError | None = None
    protocol_version: int = PROTOCOL_VERSION

    @property
    def id(self) -> str:
        return self.request_id

    @property
    def ok(self) -> bool:
        return self.error is None

    @classmethod
    def from_dict(
        cls, value: Any, *, expected_id: str | None = None
    ) -> "RPCResponse":
        obj = _object(value, "RPC response")
        allowed = {"jsonrpc", "protocol_version", "id", "result", "error"}
        if any(key not in allowed for key in obj):
            raise IrohProtocolError("RPC response contains unknown fields")
        if obj.get("jsonrpc", JSONRPC_VERSION) != JSONRPC_VERSION:
            raise IrohProtocolError("unsupported JSON-RPC version")

        protocol = obj.get("protocol_version")
        if (
            isinstance(protocol, bool)
            or not isinstance(protocol, int)
            or protocol != PROTOCOL_VERSION
        ):
            raise IrohUnsupportedVersionError(
                "sidecar RPC protocol version is unsupported"
            )

        request_id = obj.get("id")
        if not isinstance(request_id, str) or not request_id:
            raise IrohProtocolError("RPC response has an invalid request id")
        if expected_id is not None and request_id != expected_id:
            raise IrohProtocolError("RPC response request id does not match")

        has_result = "result" in obj
        has_error = "error" in obj and obj.get("error") is not None
        if has_result == has_error:
            raise IrohProtocolError(
                "RPC response must contain exactly one of result or error"
            )

        if has_result:
            result = obj["result"]
            _validate_json(result, "result")
            return cls(request_id, result=result, protocol_version=protocol)

        error_obj = _object(obj["error"], "RPC error")
        if any(key not in {"code", "message", "data"} for key in error_obj):
            raise IrohProtocolError("RPC error contains unknown fields")
        code = error_obj.get("code")
        message = error_obj.get("message")
        if not isinstance(code, str) or not isinstance(message, str):
            raise IrohProtocolError("RPC error code and message must be strings")
        data = error_obj.get("data", {})
        if not isinstance(data, Mapping):
            raise IrohProtocolError("RPC error data must be a JSON object")
        _validate_json(data, "error.data")
        return cls(
            request_id,
            error=RPCError(code=code, message=message, data=dict(data)),
            protocol_version=protocol,
        )


@dataclass(frozen=True, slots=True)
class RuntimeVersion:
    sidecar: str
    protocol: int
    iroh: str
    iroh_blobs: str
    iroh_docs: str
    iroh_gossip: str
    release_bundle: str | None = None

    @property
    def protocol_version(self) -> int:
        return self.protocol

    @property
    def sidecar_version(self) -> str:
        return self.sidecar

    @classmethod
    def from_mapping(cls, value: Any) -> "RuntimeVersion":
        obj = _object(value, "version result")
        aliases = {
            "sidecar": ("sidecar", "sidecar_version"),
            "protocol": ("protocol", "protocol_version"),
            "iroh": ("iroh",),
            "iroh_blobs": ("iroh_blobs", "iroh-blobs"),
            "iroh_docs": ("iroh_docs", "iroh-docs"),
            "iroh_gossip": ("iroh_gossip", "iroh-gossip"),
        }
        parsed: dict[str, Any] = {}
        for target, names in aliases.items():
            present = [obj[name] for name in names if name in obj]
            if len(present) != 1:
                raise IrohProtocolError(
                    f"version result has invalid {target} field"
                )
            parsed[target] = present[0]

        protocol = parsed["protocol"]
        if isinstance(protocol, bool) or not isinstance(protocol, int):
            raise IrohProtocolError("version result protocol must be an integer")
        if any(
            not isinstance(parsed[name], str) or not parsed[name]
            for name in aliases
            if name != "protocol"
        ):
            raise IrohProtocolError(
                "version result contains an invalid component version"
            )
        bundle = obj.get("release_bundle")
        if bundle is not None and (not isinstance(bundle, str) or not bundle):
            raise IrohProtocolError("version result has an invalid release bundle")
        return cls(**parsed, release_bundle=bundle)

    @classmethod
    def from_cli_line(cls, line: str) -> "RuntimeVersion":
        if not isinstance(line, str):
            raise IrohProtocolError("diagnostic version output is malformed")
        match = _VERSION_RE.fullmatch(line)
        if match is None:
            raise IrohProtocolError("diagnostic version output is malformed")
        values = match.groupdict()
        return cls(
            sidecar=values["sidecar"],
            protocol=int(values["protocol"]),
            iroh=values["iroh"],
            iroh_blobs=values["blobs"],
            iroh_docs=values["docs"],
            iroh_gossip=values["gossip"],
        )


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    methods: frozenset[str]
    protocol_version: int = PROTOCOL_VERSION

    @classmethod
    def from_result(cls, value: Any) -> "RuntimeCapabilities":
        if isinstance(value, Mapping):
            protocol = value.get("protocol_version", PROTOCOL_VERSION)
            methods = value.get("methods")
        else:
            protocol = PROTOCOL_VERSION
            methods = value
        if (
            isinstance(protocol, bool)
            or not isinstance(protocol, int)
            or protocol != PROTOCOL_VERSION
        ):
            raise IrohUnsupportedVersionError(
                "capability protocol version is unsupported"
            )
        if not isinstance(methods, Sequence) or isinstance(methods, (str, bytes)):
            raise IrohProtocolError("capability methods must be an array")
        if any(
            not isinstance(method, str) or not _METHOD_RE.fullmatch(method)
            for method in methods
        ):
            raise IrohProtocolError("capability result contains an invalid method")
        if len(methods) != len(set(methods)):
            raise IrohProtocolError("capability result contains duplicate methods")
        return cls(frozenset(methods), protocol)

    @property
    def missing_required(self) -> frozenset[str]:
        return REQUIRED_METHODS - self.methods

    def supports(self, method: str) -> bool:
        return method in self.methods


def encode_frame(value: Mapping[str, Any]) -> bytes:
    """Encode one canonical, newline-delimited protocol frame."""

    _validate_json(value)
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        # Custom objects and codec errors can include their values in an
        # exception representation; never retain that cause across the public
        # runtime boundary.
        raise IrohProtocolError("could not encode RPC frame") from None
    if len(payload) > MAX_FRAME_BYTES:
        raise IrohProtocolError("RPC frame exceeds the size limit")
    return payload + b"\n"


def decode_frame(payload: bytes | str) -> Mapping[str, Any]:
    """Decode exactly one bounded UTF-8 JSON object frame."""

    if isinstance(payload, str):
        try:
            raw = payload.encode("utf-8")
        except UnicodeError:
            raise IrohProtocolError("RPC frame is not valid UTF-8") from None
    elif isinstance(payload, bytes):
        raw = payload
    else:
        raise IrohProtocolError("RPC frame must be bytes or text")
    if not raw or len(raw) > MAX_FRAME_BYTES + 1:
        raise IrohProtocolError("RPC frame is empty or exceeds the size limit")
    if b"\n" in raw.rstrip(b"\n"):
        raise IrohProtocolError("RPC transport returned more than one frame")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda constant: (_ for _ in ()).throw(ValueError(constant)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise IrohProtocolError("RPC frame is not valid JSON") from None
    return _object(value, "RPC frame")


# Compatibility aliases.  The RPC-prefixed names are canonical.
RpcRequest = RPCRequest
RpcResponse = RPCResponse
RpcError = RPCError
IrohRequest = RPCRequest
IrohResult = RPCResponse
Request = RPCRequest
Result = RPCResponse
VersionInfo = RuntimeVersion
Capabilities = RuntimeCapabilities
CapabilitySet = RuntimeCapabilities
REQUIRED_CAPABILITIES = REQUIRED_METHODS
EMPTY_PARAMS: Mapping[str, Any] = MappingProxyType({})


__all__ = [
    "PROTOCOL_VERSION",
    "JSONRPC_VERSION",
    "MAX_FRAME_BYTES",
    "REQUIRED_METHODS",
    "REQUIRED_CAPABILITIES",
    "EMPTY_PARAMS",
    "RPCRequest",
    "RPCResponse",
    "RPCError",
    "RuntimeVersion",
    "RuntimeCapabilities",
    "encode_frame",
    "decode_frame",
]
