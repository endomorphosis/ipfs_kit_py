"""Pinned-service readiness contracts for the promoted storage adapters.

The doubles deliberately implement only the service protocols.  They prove
that adapters do not use an in-process/local fallback when a service fails.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
import pytest

from ipfs_kit_py.backends.ipfs_backend import IPFSBackendAdapter
from ipfs_kit_py.backends.s3_backend import S3BackendAdapter
from ipfs_kit_py.iroh.backend import IrohBackendPlugin


class _Body:
    def __init__(self, value: bytes) -> None:
        self.value = value

    def read(self) -> bytes:
        return self.value


class _S3:
    def __init__(self, *, fail_head: bool = False) -> None:
        self.fail_head = fail_head
        self.objects: dict[str, bytes] = {}
        self.uploads: dict[str, dict[int, bytes]] = {}
        self.aborted: list[str] = []

    def head_bucket(self, **_: Any) -> None:
        if self.fail_head:
            self.fail_head = False
            raise RuntimeError("token=do-not-leak")

    def put_object(self, *, Key: str, Body: bytes, **_: Any) -> dict[str, str]:
        self.objects[Key] = Body
        return {"ETag": f'"{hashlib.md5(Body).hexdigest()}"'}  # nosec B303 - protocol double

    def create_multipart_upload(self, **_: Any) -> dict[str, str]:
        upload_id = f"upload-{len(self.uploads)}"
        self.uploads[upload_id] = {}
        return {"UploadId": upload_id}

    def upload_part(self, *, UploadId: str, PartNumber: int, Body: bytes, **_: Any) -> dict[str, str]:
        self.uploads[UploadId][PartNumber] = Body
        return {"ETag": f'"part-{PartNumber}"'}

    def complete_multipart_upload(self, *, Key: str, UploadId: str, **_: Any) -> None:
        parts = self.uploads.pop(UploadId)
        self.objects[Key] = b"".join(parts[part] for part in sorted(parts))

    def abort_multipart_upload(self, *, UploadId: str, **_: Any) -> None:
        self.aborted.append(UploadId)
        self.uploads.pop(UploadId, None)

    def get_object(self, *, Key: str, Range: str | None = None, **_: Any) -> dict[str, _Body]:
        value = self.objects[Key]
        if Range:
            start, end = (int(number) for number in Range.removeprefix("bytes=").split("-"))
            value = value[start : end + 1]
        return {"Body": _Body(value)}

    def list_objects_v2(self, *, Prefix: str, MaxKeys: int, ContinuationToken: str | None = None, **_: Any) -> dict[str, Any]:
        keys = sorted(key for key in self.objects if key.startswith(Prefix))
        start = int(ContinuationToken or 0)
        page = keys[start : start + MaxKeys]
        next_start = start + len(page)
        return {
            "Contents": [{"Key": key} for key in page],
            "IsTruncated": next_start < len(keys),
            "NextContinuationToken": str(next_start) if next_start < len(keys) else None,
        }

    def delete_object(self, *, Key: str, **_: Any) -> None:
        self.objects.pop(Key, None)


class _SlowS3:
    def head_bucket(self, **_: Any) -> None:
        time.sleep(0.2)


class _UnavailableS3:
    def head_bucket(self, **_: Any) -> None:
        raise RuntimeError("secret=never-expose-this")


@dataclass
class _Response:
    payload: Any = None
    content: bytes = b""
    status_code: int = 200

    def json(self) -> Any:
        return self.payload


class _IPFS:
    def __init__(self, *, fail_version_once: bool = False) -> None:
        self.fail_version_once = fail_version_once
        self.blobs: dict[str, bytes] = {}
        self.pins: set[str] = set()

    def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        path = url.split(":5001", 1)[-1]
        if path == "/api/v0/version":
            if self.fail_version_once:
                self.fail_version_once = False
                raise RuntimeError("credential=private-service-secret")
            return _Response({"Version": "0.30.0"})
        if path == "/api/v0/add":
            data = kwargs["files"]["file"][1]
            cid = f"cid-{hashlib.sha256(data).hexdigest()[:12]}"
            self.blobs[cid] = data
            return _Response({"Hash": cid})
        cid = kwargs.get("params", {}).get("arg")
        if path == "/api/v0/cat":
            value = self.blobs[cid]
            byte_range = kwargs.get("headers", {}).get("Range")
            if byte_range:
                start, end = (int(number) for number in byte_range.removeprefix("bytes=").split("-"))
                value = value[start : end + 1]
            return _Response(content=value)
        if path == "/api/v0/pin/add":
            self.pins.add(cid)
            return _Response({"Pins": [cid]})
        if path == "/api/v0/pin/rm":
            self.pins.discard(cid)
            return _Response({"Pins": [cid]})
        if path == "/api/v0/pin/ls":
            return _Response({"Keys": {value: {"Type": "recursive"} for value in sorted(self.pins)}})
        raise AssertionError(f"unexpected IPFS request: {method} {path}")


class _UnavailableIPFS:
    def request(self, *_: Any, **__: Any) -> _Response:
        raise RuntimeError("token=never-expose-this")


def _iroh_config(tmp_path: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "pinned_iroh",
        "type": "iroh",
        "enabled": True,
        "namespace": {"id": "a4d26868017c0ccffe2efe50944ef42125f9b8692f2a8f46f5f7d6c483ad127a", "access": "read-write"},
        "service": {"instance": "primary", "managed": False, "rpc_endpoint": f"unix://{tmp_path}/iroh.sock"},
        "credentials": {"node_key_ref": "secretref:enhanced-secrets:node", "write_capability_ref": "secretref:enhanced-secrets:write"},
        "timeouts": {"connect_seconds": 1, "operation_seconds": 1, "shutdown_seconds": 1},
        "sync": {"enabled": False, "on_open": False, "read_consistency": "local", "conflict_policy": "fail"},
    }


def test_s3_inert_constructor_and_full_pinned_service_operations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    first, stable = _S3(fail_head=True), _S3()
    clients = iter((first, stable))
    adapter = S3BackendAdapter("digitalocean", client_factory=lambda: next(clients))
    assert not (tmp_path / ".ipfs_kit").exists()

    async def exercise() -> None:
        receipt = await adapter.certify_live_service()
        assert receipt["status"] == "passed"
        assert receipt["provider"] == "s3-compatible"  # alias is not a provider claim
        payload = b"0123456789"
        written = await adapter.put_object("items/a", payload, multipart_threshold=4, part_size=3)
        assert written["multipart"] is True
        assert await adapter.get_object("items/a", byte_range=(2, 5)) == b"2345"
        assert await adapter.get_object("items/a", expected_sha256=hashlib.sha256(payload).hexdigest()) == payload
        await adapter.put_object("items/b", b"b")
        first_page = await adapter.list_objects("items/", page_size=1)
        second_page = await adapter.list_objects("items/", continuation_token=first_page["next_token"], page_size=1)
        assert first_page["truncated"] and second_page["objects"]
        with pytest.raises(ValueError, match="SHA-256"):
            await adapter.get_object("items/a", expected_sha256="0" * 64)
        await adapter.delete_object("items/b")
        assert "items/b" not in stable.objects

    anyio.run(exercise)


def test_s3_cancellation_and_unavailable_service_are_not_passes() -> None:
    async def exercise() -> None:
        adapter = S3BackendAdapter(client=_SlowS3())
        with anyio.move_on_after(0.01) as cancelled:
            await adapter.certify_live_service()
        assert cancelled.cancel_called
        blocked = await S3BackendAdapter(client=_UnavailableS3(), config_manager=None).certify_live_service()
        assert blocked["status"] == "blocked"
        assert "never-expose-this" not in blocked["reason"]

    anyio.run(exercise)


def test_ipfs_pinned_api_operations_redaction_and_no_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    client = _IPFS(fail_version_once=True)
    adapter = IPFSBackendAdapter(http_client=client)
    assert not (tmp_path / ".ipfs_kit").exists()

    async def exercise() -> None:
        receipt = await adapter.certify_live_service()
        assert receipt["status"] == "passed"  # retried against the same pinned API
        uploaded = await adapter.add_bytes(b"abcdef")
        await adapter.pin(uploaded["cid"])
        page = await adapter.list_pins_page(limit=1)
        assert page["pins"] == [uploaded["cid"]]
        assert await adapter.cat(uploaded["cid"], byte_range=(1, 3)) == b"bcd"
        with pytest.raises(ValueError, match="SHA-256"):
            await adapter.cat(uploaded["cid"], expected_sha256="0" * 64)
        await adapter.unpin(uploaded["cid"])
        blocked = await IPFSBackendAdapter(http_client=_UnavailableIPFS()).certify_live_service()
        assert blocked["status"] == "blocked"
        assert "never-expose-this" not in blocked["reason"]

    anyio.run(exercise)


def test_iroh_certification_requires_rpc_negotiation_and_redacts_failure(tmp_path: Path) -> None:
    class Ready:
        async def health(self, *, timeout: float) -> dict[str, Any]:
            return {"ready": True, "token": "do-not-leak"}

        async def negotiate(self, *, timeout: float) -> None:
            return None

    class Down:
        async def health(self, *, timeout: float) -> dict[str, Any]:
            raise RuntimeError("ticket=do-not-leak")

    async def exercise() -> None:
        plugin = IrohBackendPlugin()
        passed = await plugin.certify_live_service(_iroh_config(tmp_path), client=Ready())
        assert passed["status"] == "passed"
        assert passed["health"]["token"] == "<redacted>"
        blocked = await plugin.certify_live_service(_iroh_config(tmp_path), client=Down())
        assert blocked["status"] == "blocked"
        assert "do-not-leak" not in blocked["reason"]
        assert plugin.health(_iroh_config(tmp_path))["certification_status"] == "blocked"

    anyio.run(exercise)
