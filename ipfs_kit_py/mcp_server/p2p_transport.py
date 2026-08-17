"""Optional libp2p P2P transport for the MCP++ server (Profile E hardened).

Serves the same JSON-RPC handler over a libp2p stream protocol when py-libp2p is
installed, so peers can call tools over ``/mcp+p2p/1.0.0`` (MCP++ Profile E).
When libp2p is unavailable, ``HAVE_LIBP2P`` is False and the server stays
HTTP/stdio.

Runtime binding (RuntimeP2pAdapter@1 / kit side):
  * Versioned stream protocol id ``/mcp+p2p/1.0.0``
  * LengthPrefixedFrame@1 (u32 BE + UTF-8 JSON), default max 16 MiB
  * Fail-closed on oversized / truncated / invalid frames
  * Transport success is not application success
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from json import JSONDecodeError
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Profile E constants
# ---------------------------------------------------------------------------

PROTOCOL_ID = "/mcp+p2p/1.0.0"
SUPPORTED_PROTOCOL_IDS: frozenset[str] = frozenset({PROTOCOL_ID})
INTERFACE_LABEL = "RuntimeP2pAdapter@1"
RUNTIME_ID = "kit"

HEADER_SIZE = 4
DEFAULT_MAX_FRAME_BYTES = 16 * 1024 * 1024  # 16 MiB
MAX_FRAME_BYTES = DEFAULT_MAX_FRAME_BYTES

CANONICAL_MCP_VERSION = "2026-07-28"
LEGACY_MCP_VERSION = "2024-11-05"
ACCEPTED_MCP_VERSIONS: frozenset[str] = frozenset(
    {CANONICAL_MCP_VERSION, LEGACY_MCP_VERSION}
)

DEFAULT_MAX_STREAMS_PER_PEER = 32
DEFAULT_RATE_CAPACITY = 100.0
DEFAULT_RATE_REFILL_PER_SEC = 50.0

HAVE_LIBP2P = False

try:  # py-libp2p is an optional extra
    import libp2p  # type: ignore  # noqa: F401

    HAVE_LIBP2P = True
except Exception:  # pragma: no cover
    libp2p = None  # type: ignore


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FramingError(Exception):
    """Raised when frame encoding/decoding fails."""


class FrameSizeExceededError(FramingError):
    """Raised when a frame exceeds the configured maximum size."""


class QuotaExceededError(Exception):
    """Raised when a transport quota is exceeded."""


class ReplayDetectedError(Exception):
    """Raised when a duplicate frame or response id is observed."""


# ---------------------------------------------------------------------------
# Length-prefixed framing (LengthPrefixedFrame@1)
# ---------------------------------------------------------------------------


def encode_frame(
    payload: Mapping[str, Any],
    *,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> bytes:
    """Encode *payload* as a u32 big-endian length-prefixed UTF-8 JSON frame."""
    if not isinstance(payload, Mapping):
        raise FramingError("payload_not_object")
    body = json.dumps(dict(payload), separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    limit = int(max_frame_bytes)
    if len(body) > limit:
        raise FrameSizeExceededError(f"frame_too_large:{len(body)}>{limit}")
    return len(body).to_bytes(HEADER_SIZE, byteorder="big", signed=False) + body


def decode_frame(
    frame: bytes,
    *,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> Tuple[Dict[str, Any], int]:
    """Decode a length-prefixed frame; return ``(payload, consumed_bytes)``."""
    if not isinstance(frame, (bytes, bytearray, memoryview)):
        raise FramingError("frame_not_bytes")
    data = bytes(frame)
    if len(data) < HEADER_SIZE:
        raise FramingError("incomplete_prefix")
    declared = int.from_bytes(data[:HEADER_SIZE], byteorder="big", signed=False)
    limit = int(max_frame_bytes)
    if declared > limit:
        raise FrameSizeExceededError(f"declared_frame_too_large:{declared}>{limit}")
    if len(data) < HEADER_SIZE + declared:
        raise FramingError("incomplete_body")
    body = data[HEADER_SIZE : HEADER_SIZE + declared]
    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FramingError("invalid_utf8") from exc
    try:
        payload = json.loads(decoded)
    except JSONDecodeError as exc:
        raise FramingError("invalid_json") from exc
    if not isinstance(payload, dict):
        raise FramingError("payload_not_object")
    return payload, HEADER_SIZE + declared


def is_supported_protocol_id(protocol_id: Optional[str]) -> bool:
    """Return True when *protocol_id* is a negotiated Profile E stream id."""
    if protocol_id is None:
        return False
    return str(protocol_id) in SUPPORTED_PROTOCOL_IDS


def is_forged_protocol_version(
    protocol_id: Optional[str] = None,
    *,
    mcp_version: Optional[str] = None,
    accepted_protocol_ids: Optional[Set[str]] = None,
    accepted_mcp_versions: Optional[Set[str]] = None,
) -> bool:
    """Detect forged / unsupported transport or MCP versions."""
    accepted_pids = accepted_protocol_ids or set(SUPPORTED_PROTOCOL_IDS)
    accepted_mcp = accepted_mcp_versions or set(ACCEPTED_MCP_VERSIONS)
    if protocol_id is not None and str(protocol_id) not in accepted_pids:
        return True
    if mcp_version is not None and str(mcp_version) not in accepted_mcp:
        return True
    return False


def _looks_raw_json(data: bytes) -> bool:
    """True when *data* looks like a UTF-8 JSON object/array (legacy body).

    Valid Profile E frames with body size ≤ 16 MiB have a leading 0x00 (or
    0x01 at exactly 16 MiB) length byte, never ``{`` / ``[``.
    """
    if not data:
        return False
    i = 0
    while i < len(data) and data[i] in b" \t\r\n":
        i += 1
    return i < len(data) and data[i : i + 1] in (b"{", b"[")


def _looks_length_prefixed(data: bytes, *, max_frame_bytes: int) -> bool:
    if len(data) < HEADER_SIZE:
        return False
    if _looks_raw_json(data):
        return False
    declared = int.from_bytes(data[:HEADER_SIZE], byteorder="big", signed=False)
    if declared > int(max_frame_bytes):
        # Binary length-prefix attack (not plausible JSON text).
        return True
    return len(data) >= HEADER_SIZE + declared


def decode_wire_message(
    raw: bytes,
    *,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    framed: bool | None = None,
) -> Tuple[Dict[str, Any], bool]:
    """Decode a wire message (length-prefixed preferred; raw JSON legacy).

    Returns ``(payload, was_framed)``.
    """
    data = bytes(raw)
    use_frame = framed
    if use_frame is None:
        use_frame = _looks_length_prefixed(data, max_frame_bytes=max_frame_bytes)
    if use_frame:
        payload, _ = decode_frame(data, max_frame_bytes=max_frame_bytes)
        return payload, True
    if len(data) > int(max_frame_bytes):
        raise FrameSizeExceededError(
            f"frame_too_large:{len(data)}>{int(max_frame_bytes)}"
        )
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise FramingError("invalid_json") from exc
    if not isinstance(payload, dict):
        raise FramingError("payload_not_object")
    return payload, False


def encode_wire_message(
    payload: Mapping[str, Any],
    *,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    framed: bool = False,
) -> bytes:
    """Encode a response; *framed* selects length-prefix vs raw JSON body."""
    if framed:
        return encode_frame(payload, max_frame_bytes=max_frame_bytes)
    body = json.dumps(dict(payload), separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    if len(body) > int(max_frame_bytes):
        raise FrameSizeExceededError(
            f"frame_too_large:{len(body)}>{int(max_frame_bytes)}"
        )
    return body


# ---------------------------------------------------------------------------
# Stream / rate quotas (TransportQuota@1 subset)
# ---------------------------------------------------------------------------


@dataclass
class StreamQuota:
    """Per-peer open-stream quota (fail closed)."""

    max_streams_per_peer: int = DEFAULT_MAX_STREAMS_PER_PEER
    _open: Dict[str, int] = field(default_factory=dict)

    def try_open(self, peer_id: str) -> bool:
        key = str(peer_id)
        n = self._open.get(key, 0)
        if n >= int(self.max_streams_per_peer):
            return False
        self._open[key] = n + 1
        return True

    def open(self, peer_id: str) -> None:
        if not self.try_open(peer_id):
            raise QuotaExceededError(
                f"stream_quota_exceeded:{self._open.get(str(peer_id), 0)}>="
                f"{self.max_streams_per_peer}"
            )

    def close(self, peer_id: str) -> None:
        key = str(peer_id)
        self._open[key] = max(0, self._open.get(key, 0) - 1)

    def open_count(self, peer_id: str) -> int:
        return self._open.get(str(peer_id), 0)


@dataclass
class TokenBucketLimiter:
    """Token-bucket rate limiter for inbound message flood control."""

    capacity: float = DEFAULT_RATE_CAPACITY
    refill_rate_per_sec: float = DEFAULT_RATE_REFILL_PER_SEC
    _tokens: float = 0.0
    _last_ts: float = 0.0

    def __post_init__(self) -> None:
        self.capacity = float(max(1.0, self.capacity))
        self.refill_rate_per_sec = float(max(0.0001, self.refill_rate_per_sec))
        self._tokens = self.capacity
        self._last_ts = 0.0

    def allow(self, *, now: float, cost: float = 1.0) -> bool:
        elapsed = max(0.0, float(now) - self._last_ts)
        self._last_ts = float(now)
        self._tokens = min(
            self.capacity, self._tokens + elapsed * self.refill_rate_per_sec
        )
        c = float(max(0.0, cost))
        if self._tokens >= c:
            self._tokens -= c
            return True
        return False


# ---------------------------------------------------------------------------
# Runtime adapter (kit)
# ---------------------------------------------------------------------------


@dataclass
class RuntimeP2pAdapter:
    """Kit-side RuntimeP2pAdapter@1 bound to hardened Profile E framing."""

    runtime_id: str = RUNTIME_ID
    protocol_id: str = PROTOCOL_ID
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES
    max_streams_per_peer: int = DEFAULT_MAX_STREAMS_PER_PEER
    peer_id: str = ""
    stream_ready: bool = False
    protocol_negotiated: bool = False
    stream_quota: StreamQuota = field(init=False)
    _seen_frames: Set[str] = field(default_factory=set, init=False)
    _seen_response_ids: Set[str] = field(default_factory=set, init=False)
    _rate: TokenBucketLimiter = field(default_factory=TokenBucketLimiter, init=False)

    def __post_init__(self) -> None:
        self.max_frame_bytes = int(self.max_frame_bytes)
        self.stream_quota = StreamQuota(max_streams_per_peer=self.max_streams_per_peer)

    def negotiate_protocol(self, protocol_id: str) -> None:
        if not is_supported_protocol_id(protocol_id):
            raise FramingError(f"unsupported_protocol_id:{protocol_id}")
        if is_forged_protocol_version(protocol_id):
            raise FramingError(f"forged_protocol_id:{protocol_id}")
        self.protocol_id = str(protocol_id)
        self.protocol_negotiated = True
        self.stream_ready = True

    def open_stream(self, peer_id: str = "") -> None:
        if not self.protocol_negotiated:
            raise FramingError("protocol_not_negotiated")
        pid = str(peer_id or self.peer_id or "local")
        self.peer_id = pid
        self.stream_quota.open(pid)
        self.stream_ready = True

    def close_stream(self) -> None:
        if self.peer_id:
            self.stream_quota.close(self.peer_id)

    def encode_frame(self, payload: Mapping[str, Any]) -> bytes:
        return encode_frame(payload, max_frame_bytes=self.max_frame_bytes)

    def decode_frame(self, frame: bytes) -> Dict[str, Any]:
        payload, _ = decode_frame(frame, max_frame_bytes=self.max_frame_bytes)
        return payload

    def admit_frame(
        self,
        frame: bytes,
        *,
        check_replay: bool = True,
        now: float = 0.0,
    ) -> Dict[str, Any]:
        if not (self.stream_ready and self.protocol_negotiated):
            raise FramingError("request_before_negotiation")
        payload, _ = decode_frame(frame, max_frame_bytes=self.max_frame_bytes)
        fp = str(hash(bytes(frame)))
        if check_replay:
            if fp in self._seen_frames:
                raise ReplayDetectedError("duplicate_frame")
            self._seen_frames.add(fp)
        if not self._rate.allow(now=now, cost=1.0):
            raise QuotaExceededError("message_rate_exceeded")
        return payload

    def admit_response_id(self, response_id: Any, *, peer_id: str = "") -> None:
        key = f"{peer_id}|{response_id!r}"
        if key in self._seen_response_ids:
            raise ReplayDetectedError(f"duplicate_response_id:{response_id!r}")
        self._seen_response_ids.add(key)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "interface": INTERFACE_LABEL,
            "runtime_id": self.runtime_id,
            "protocol_id": self.protocol_id,
            "supported_protocol_ids": sorted(SUPPORTED_PROTOCOL_IDS),
            "max_frame_bytes": self.max_frame_bytes,
            "max_streams_per_peer": self.max_streams_per_peer,
            "stream_ready": self.stream_ready,
            "protocol_negotiated": self.protocol_negotiated,
            "have_libp2p": HAVE_LIBP2P,
        }


def get_runtime_adapter(**kwargs: Any) -> RuntimeP2pAdapter:
    """Factory for a kit RuntimeP2pAdapter@1 instance."""
    return RuntimeP2pAdapter(**kwargs)


# ---------------------------------------------------------------------------
# Stream message handler (body-level + framed)
# ---------------------------------------------------------------------------


async def handle_stream_message(
    raw: bytes, handler: Callable[[dict], Awaitable[dict]]
) -> bytes:
    """Decode a JSON-RPC request, dispatch it, encode the response.

    Accepts either a length-prefixed Profile E frame or a raw JSON body
    (legacy CI path). Responses mirror the input framing style so existing
    e2e tests that parse raw JSON continue to work.
    """
    payload, was_framed = decode_wire_message(raw, max_frame_bytes=MAX_FRAME_BYTES)
    resp = await handler(payload)
    if resp is None:  # notification — nothing to send back
        return b""
    return encode_wire_message(
        resp, max_frame_bytes=MAX_FRAME_BYTES, framed=was_framed
    )


async def handle_framed_stream_message(
    raw: bytes, handler: Callable[[dict], Awaitable[dict]]
) -> bytes:
    """Strict length-prefixed Profile E path (no raw-JSON fallback)."""
    payload, _ = decode_frame(raw, max_frame_bytes=MAX_FRAME_BYTES)
    resp = await handler(payload)
    if resp is None:
        return b""
    return encode_frame(resp, max_frame_bytes=MAX_FRAME_BYTES)


async def serve_p2p(handler: Callable[[dict], Awaitable[dict]]) -> None:
    """Serve the MCP handler over libp2p. Raises if libp2p is unavailable."""
    if not HAVE_LIBP2P:  # pragma: no cover
        raise RuntimeError("libp2p transport requires the 'libp2p' extra")
    from libp2p import new_host  # type: ignore

    host = new_host()
    adapter = get_runtime_adapter()
    adapter.negotiate_protocol(PROTOCOL_ID)

    async def _stream(stream):  # pragma: no cover - needs live libp2p
        data = await stream.read()
        await stream.write(await handle_framed_stream_message(data, handler))
        await stream.close()

    host.set_stream_handler(PROTOCOL_ID, _stream)
    import anyio

    await anyio.sleep_forever()


__all__ = [
    "PROTOCOL_ID",
    "SUPPORTED_PROTOCOL_IDS",
    "INTERFACE_LABEL",
    "RUNTIME_ID",
    "HEADER_SIZE",
    "DEFAULT_MAX_FRAME_BYTES",
    "MAX_FRAME_BYTES",
    "CANONICAL_MCP_VERSION",
    "LEGACY_MCP_VERSION",
    "ACCEPTED_MCP_VERSIONS",
    "HAVE_LIBP2P",
    "FramingError",
    "FrameSizeExceededError",
    "QuotaExceededError",
    "ReplayDetectedError",
    "encode_frame",
    "decode_frame",
    "is_supported_protocol_id",
    "is_forged_protocol_version",
    "decode_wire_message",
    "encode_wire_message",
    "StreamQuota",
    "TokenBucketLimiter",
    "RuntimeP2pAdapter",
    "get_runtime_adapter",
    "handle_stream_message",
    "handle_framed_stream_message",
    "serve_p2p",
]
