"""Bounded live Kubo HTTP pubsub. Publication acceptance is not delivery or durability."""
from __future__ import annotations

import base64
import http.client
import socket
import threading
import time
import uuid
from urllib.parse import urlencode, urlsplit

_MAX_FRAME = 16384
_MAX_BODY = 65536


def _origin(api_url: str) -> str:
    parsed = urlsplit(api_url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port not in (5032, 5033)
            or parsed.path not in ("", "/") or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("pubsub API must be an owned credential-free loopback peer")
    return f"http://127.0.0.1:{parsed.port}"


def _check(deadline: float, cancel_event: threading.Event) -> float:
    if not isinstance(deadline, (int, float)):
        raise ValueError("pubsub deadline invalid")
    if cancel_event is None or not hasattr(cancel_event, "is_set"):
        raise ValueError("pubsub cancel_event required")
    if cancel_event.is_set():
        raise RuntimeError("pubsub cancelled")
    remaining = float(deadline) - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("pubsub deadline exceeded")
    return remaining


def encode_topic(topic: str) -> str:
    if type(topic) is not str or not 0 < len(topic.encode("utf-8")) <= 1024:
        raise ValueError("pubsub topic invalid")
    return "u" + base64.urlsafe_b64encode(topic.encode("utf-8")).decode().rstrip("=")


class _Subscription:
    def __init__(self, api_url: str, topic: str, deadline: float, cancel_event: threading.Event, max_frames: int, max_bytes: int, timeout: float):
        if type(max_frames) is not int or type(max_bytes) is not int or max_frames < 1 or max_bytes < 1 or max_bytes > _MAX_BODY:
            raise ValueError("pubsub stream bounds invalid")
        self.api_url, self.topic, self.deadline, self.cancel_event = api_url, topic, deadline, cancel_event
        self.max_frames, self.max_bytes, self.timeout = max_frames, max_bytes, timeout
        self._conn = None
        self._sock = None
        self._response = None
        self._opened = False
        self._closed = False
        self._frames = 0
        self._total = 0

    def open(self) -> None:
        if self._opened or self._closed:
            return
        remaining = _check(self.deadline, self.cancel_event)
        parsed = urlsplit(self.api_url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=min(self.timeout, remaining))
        try:
            target = "/api/v0/pubsub/sub?" + urlencode({"arg": encode_topic(self.topic)})
            conn.request("POST", target, body=b"", headers={"Content-Length": "0"})
            response = conn.getresponse()
            if response.status != 200:
                raise RuntimeError(f"pubsub_http_{response.status}")
        except Exception:
            conn.close()
            raise
        self._conn, self._sock, self._response, self._opened = conn, conn.sock, response, True

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def __iter__(self):
        return self

    def __next__(self):
        if self._closed:
            raise StopIteration
        self.open()
        while not self._closed:
            if self.cancel_event.is_set():
                raise RuntimeError("pubsub cancelled")
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or self._frames >= self.max_frames or self._total >= self.max_bytes:
                raise StopIteration
            try:
                # One blocking read for the remaining deadline. A short poll
                # raises socket.timeout inside HTTPResponse.readline and leaves
                # the chunked decoder unusable, so the next line is lost.
                self._sock.settimeout(remaining)
                line = self._response.readline(_MAX_FRAME + 1)
            except (TimeoutError, socket.timeout):
                raise StopIteration
            except OSError:
                if self._closed or self.cancel_event.is_set():
                    raise StopIteration
                raise
            if not line:
                raise StopIteration
            if len(line) > _MAX_FRAME or self._total + len(line) > self.max_bytes:
                raise RuntimeError("pubsub stream bounds exceeded")
            self._frames += 1
            self._total += len(line)
            return {"raw_frame": line}
        raise StopIteration

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        sock, conn = self._sock, self._conn
        self._sock = self._conn = None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if conn is not None:
            conn.close()


class LivePinnedPubsubAdapter:
    def __init__(self, api_url: str, timeout: float = 10) -> None:
        if not isinstance(timeout, (int, float)) or not 0 < float(timeout) <= 120:
            raise ValueError("pubsub timeout invalid")
        self.api_url = _origin(api_url)
        self.timeout = float(timeout)
        self.simulated = False
        self.live_provider = True
        self.transport_kind = "http"
        self._transport = None
        self._subscriptions = []

    def close(self) -> None:
        for sub in list(self._subscriptions):
            sub.close()
        self._subscriptions.clear()

    def _post(self, path: str, query: list, body: bytes, headers: dict, deadline: float, cancel_event: threading.Event) -> bytes:
        remaining = _check(deadline, cancel_event)
        parsed = urlsplit(self.api_url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=min(self.timeout, remaining))
        try:
            conn.request("POST", path + "?" + urlencode(query, doseq=True), body=body, headers=headers)
            _check(deadline, cancel_event)
            response = conn.getresponse()
            payload = response.read(_MAX_BODY + 1)
            if len(payload) > _MAX_BODY:
                raise RuntimeError("pubsub_response_bounds")
            if response.status != 200:
                raise RuntimeError(f"pubsub_http_{response.status}")
            return payload
        finally:
            conn.close()

    def subscribe(self, topic: str, *, deadline: float, cancel_event: threading.Event, max_frames: int, max_bytes: int):
        sub = _Subscription(self.api_url, topic, deadline, cancel_event, max_frames, max_bytes, self.timeout)
        sub.open()
        self._subscriptions.append(sub)
        return sub

    def pubsub_publish(self, topic: str, data: bytes, *, deadline: float, cancel_event: threading.Event) -> dict:
        if type(data) is not bytes or not 0 < len(data) <= _MAX_BODY:
            raise ValueError("pubsub payload bounds")
        boundary = "svf" + uuid.uuid4().hex
        while boundary.encode() in data:
            boundary = "svf" + uuid.uuid4().hex
        head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"payload\"\r\n"
                "Content-Type: application/octet-stream\r\n\r\n").encode()
        body = head + data + f"\r\n--{boundary}--\r\n".encode()
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))}
        self._post("/api/v0/pubsub/pub", [("arg", encode_topic(topic))], body, headers, deadline, cancel_event)
        return {"accepted": True, "durable": False, "effect_kind": "EXTERNAL_NOTIFY", "state": "ACCEPTED",
                "request_id": str(uuid.uuid4()), "operation_id": str(uuid.uuid4())}

    def pubsub_peers(self, topic: str, *, deadline: float, cancel_event: threading.Event) -> list:
        import json
        raw = self._post("/api/v0/pubsub/peers", [("arg", encode_topic(topic))], b"", {"Content-Length": "0"}, deadline, cancel_event)
        try:
            value = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("pubsub_peers_malformed") from exc
        strings = value.get("Strings") if type(value) is dict else None
        if strings is None:
            return []
        if type(strings) is not list or len(strings) > 16 or any(type(item) is not str for item in strings):
            raise RuntimeError("pubsub_peers_malformed")
        return list(strings)

    def swarm_connect(self, multiaddr: str, *, deadline: float, cancel_event: threading.Event) -> None:
        if type(multiaddr) is not str or len(multiaddr) > 512:
            raise ValueError("swarm multiaddr invalid")
        prefix32, prefix33 = "/ip4/127.0.0.1/tcp/40032/p2p/", "/ip4/127.0.0.1/tcp/40033/p2p/"
        if not (multiaddr.startswith(prefix32) or multiaddr.startswith(prefix33)):
            raise ValueError("swarm connect requires the other owned loopback peer")
        self._post("/api/v0/swarm/connect", [("arg", multiaddr)], b"", {"Content-Length": "0"}, deadline, cancel_event)
