from __future__ import annotations

import json
import logging

import httpx

from ipfs_kit_py.ipfs import ipfs_py
from ipfs_kit_py.ipfs_kit import ipfs_kit


CID = "bafkreid3kqys6b7f6w4oc6m4c7r5xhx7xow4n2gt7v5ufsq2g5t5dgfu6i"


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_block_put_uses_modern_kubo_api_and_returns_cid():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v0/block/put"
        assert request.url.params["cid-codec"] == "raw"
        assert request.url.params["pin"] == "false"
        assert b"hello-kubo" in request.read()
        return httpx.Response(200, json={"Key": CID})

    client = ipfs_py(
        resources={
            "api_url": "http://127.0.0.1:5001",
            "http_client": _client(handler),
        }
    )
    result = client.block_put(b"hello-kubo", codec="raw")
    assert result["success"] is True
    assert result["cid"] == CID


def test_block_get_returns_exact_bytes_and_pin_surface_is_real():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/v0/block/get":
            assert request.url.params["arg"] == CID
            return httpx.Response(200, content=b"\x00exact\xff")
        if request.url.path == "/api/v0/pin/add":
            return httpx.Response(200, json={"Pins": [CID]})
        if request.url.path == "/api/v0/pin/ls":
            return httpx.Response(200, json={"Keys": {CID: {"Type": "recursive"}}})
        if request.url.path == "/api/v0/pin/rm":
            return httpx.Response(200, json={"Pins": [CID]})
        raise AssertionError(request.url)

    client = ipfs_py(
        resources={
            "api_url": "http://127.0.0.1:5001",
            "http_client": _client(handler),
        }
    )
    assert client.block_get(CID)["data"] == b"\x00exact\xff"
    assert client.pin_add(CID)["Pins"] == [CID]
    assert CID in client.pin_ls()["Keys"]
    assert client.pin_rm(CID)["Pins"] == [CID]
    assert calls == [
        "/api/v0/block/get",
        "/api/v0/pin/add",
        "/api/v0/pin/ls",
        "/api/v0/pin/rm",
    ]


def test_http_errors_fail_closed_and_outer_kit_exposes_block_methods():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text=json.dumps({"Message": "boom"}))

    client = ipfs_py(
        resources={
            "api_url": "http://127.0.0.1:5001",
            "http_client": _client(handler),
        }
    )
    result = client.block_get(CID)
    assert result["success"] is False
    assert result["error_type"] == "HTTPStatusError"

    # Avoid unrelated optional-kit initialization: this test is only about the
    # stable outer storage surface and its delegation contract.
    kit = object.__new__(ipfs_kit)
    kit.logger = logging.getLogger(__name__)
    kit.auto_start_daemons = False
    kit.ipfs = client
    assert kit.ipfs_block_get(CID)["success"] is False
    assert callable(kit.ipfs_block_put)
