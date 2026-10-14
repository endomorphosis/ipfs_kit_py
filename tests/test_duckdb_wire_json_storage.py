"""Exact historical wire JSON on a fresh persistent native Kit owner.

Authored owner fixtures exercise SDK durability, not production launch or
remote Quack qualification. No provider, model, or prover calls are made.
"""

from __future__ import annotations

import json
import threading

import duckdb
import pytest
from test_duckdb_coordination_storage import IDENTITY, install_owner

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    STATE_ROOT_TRANSITION_SCHEMA,
    ArtifactIntegrityError,
    cid_for_bytes,
)
from ipfs_kit_py.mcp_server.mcplusplus.duckdb_coordination_storage import (
    MAX_WIRE_JSON_BYTES,
    WIRE_JSON_KIND,
    DuckDBCoordinationStore,
    NativeOwnerBindingError,
)

NS = "source-forest/wire-json-test/shard-01"


def wire_bytes(body):
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def put_wire(store, body):
    raw = wire_bytes(body)
    return store.put_wire_json(raw, expected_cid=cid_for_bytes(raw, codec="raw"))


@pytest.fixture
def native(tmp_path):
    path = tmp_path / "wire.duckdb"
    connection = duckdb.connect(str(path))
    install_owner(connection)
    store = DuckDBCoordinationStore(
        connection, transaction_lock=threading.RLock(), owner_identity=IDENTITY, namespace=NS
    )
    yield path, connection, store
    connection.close()


@pytest.mark.parametrize(
    "body",
    [
        {"repository": "toy", "value": "schemaless"},
        {"value": "café λ 中文 👩", "nested": {"message": "\n\x00"}},
        {"event_type": "tool_result", "payload_cid": "opaque-context", "sequence": 1},
        {"schema": "mcp++/profile-f/event@1", "type": "tool_result", "payload": {}},
    ],
)
def test_exact_wire_identity_and_profile_f_bodies_roundtrip(native, body):
    _, _, store = native
    raw = wire_bytes(body)
    expected = cid_for_bytes(raw, codec="raw")
    receipt = store.put_wire_json(raw, expected_cid=expected)
    assert receipt == {
        "cid": expected,
        "kind": WIRE_JSON_KIND,
        "codec": "raw",
        "byte_length": len(raw),
        "created": True,
        "replicated": False,
        "durable": True,
    }
    assert store.get_bytes(expected) == raw
    assert store.get(expected) == body
    assert store.has(expected) is True
    assert store.put_wire_json(raw, expected_cid=expected)["created"] is False


def test_wire_close_reopen_keeps_exact_bytes_and_fixed_owner(native):
    path, connection, store = native
    body = {"message": "café λ"}
    receipt = put_wire(store, body)
    connection.close()
    reopened = duckdb.connect(str(path))
    try:
        fresh = DuckDBCoordinationStore(
            reopened, transaction_lock=threading.RLock(), owner_identity=IDENTITY, namespace=NS
        )
        assert fresh.get_bytes(receipt["cid"]) == wire_bytes(body)
        assert fresh.get(receipt["cid"]) == body
    finally:
        reopened.close()


@pytest.mark.parametrize("normal_first", [True, False])
def test_immutable_dedup_retains_actual_existing_row_kind(native, normal_first):
    _, connection, store = native
    body = {"schema": "test/native@1", "value": "ASCII"}
    if normal_first:
        first = store.put(body, codec="raw")
        second = put_wire(store, body)
    else:
        first = put_wire(store, body)
        second = store.put(body, codec="raw")
    assert first["created"] is True and second["created"] is False
    assert second["kind"] == first["kind"]
    assert (
        connection.execute(
            "SELECT kind FROM kit_coordination_blocks WHERE namespace=? AND cid=?",
            [NS, first["cid"]],
        ).fetchone()[0]
        == first["kind"]
    )
    assert store.get(first["cid"]) == body


@pytest.mark.parametrize("codec", ["raw", "dag-json"])
def test_normal_schema_mapping_unicode_contract_is_unchanged(native, codec):
    _, _, store = native
    body = {"schema": "test/native@1", "value": "café"}
    native_bytes = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()
    expected = cid_for_bytes(native_bytes, codec=codec)
    receipt = store.put(body, expected_cid=expected, codec=codec)
    assert receipt["kind"] == body["schema"]
    assert store.get_bytes(expected) == native_bytes
    assert store.get(expected) == body


@pytest.mark.parametrize("field", ["schema", "kind"])
def test_wire_marker_cannot_be_minted_by_normal_mapping(native, field):
    _, _, store = native
    body = {"schema": "test/native@1", field: WIRE_JSON_KIND}
    with pytest.raises(ValueError, match="reserved"):
        store.put(body)


@pytest.mark.parametrize(
    "raw",
    [
        b"[]",
        b'"text"',
        b"null",
        b"{} ",
        b'{"b":1,"a":2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":-Infinity}',
        b'{"a":1,"a":1}',
        b'{"a":"caf\xc3\xa9"}',
        b"{",
        b'{"a":1e10000}',
    ],
)
def test_noncanonical_nonfinite_or_nonobject_wire_bytes_are_refused(native, raw):
    _, connection, store = native
    with pytest.raises(ValueError):
        store.put_wire_json(raw, expected_cid=cid_for_bytes(raw, codec="raw"))
    assert connection.execute("SELECT count(*) FROM kit_coordination_blocks").fetchone()[0] == 0


def test_only_raw_expected_identity_is_allowed_and_mismatch_never_writes(native):
    _, connection, store = native
    raw = wire_bytes({"value": 1})
    for wrong in [cid_for_bytes(raw), cid_for_bytes(wire_bytes({"value": 2}), codec="raw")]:
        with pytest.raises(ArtifactIntegrityError):
            store.put_wire_json(raw, expected_cid=wrong)
    assert connection.execute("SELECT count(*) FROM kit_coordination_blocks").fetchone()[0] == 0


@pytest.mark.parametrize("value", [bytearray(b"{}"), "{}", {}, None])
def test_wire_input_is_exact_bytes(native, value):
    _, _, store = native
    with pytest.raises(TypeError):
        store.put_wire_json(value, expected_cid=cid_for_bytes(b"{}", codec="raw"))


@pytest.mark.parametrize("replicate", [True, 0, None])
def test_wire_replication_has_no_fallback(native, replicate):
    _, _, store = native
    with pytest.raises(ValueError, match="replication"):
        store.put_wire_json(
            b"{}", expected_cid=cid_for_bytes(b"{}", codec="raw"), replicate=replicate
        )


def test_wire_exact_size_bound_and_empty_oversize_refusal(native):
    _, _, store = native
    raw = wire_bytes({"x": "a" * (MAX_WIRE_JSON_BYTES - len(wire_bytes({"x": ""})))})
    assert len(raw) == MAX_WIRE_JSON_BYTES
    receipt = store.put_wire_json(raw, expected_cid=cid_for_bytes(raw, codec="raw"))
    assert store.get_bytes(receipt["cid"]) == raw
    for bad in [b"", wire_bytes({"x": "a" * MAX_WIRE_JSON_BYTES})]:
        with pytest.raises(ValueError, match="bound"):
            store.put_wire_json(bad, expected_cid=cid_for_bytes(bad, codec="raw"))


@pytest.mark.parametrize("field", ["kind", "codec", "byte_length", "block_bytes"])
def test_wire_metadata_or_bytes_tampering_fails_authenticated_reads(native, field):
    _, connection, store = native
    receipt = put_wire(store, {"value": "café"})
    changed = {"kind": "test/wrong@1", "codec": "dag-json", "byte_length": 0, "block_bytes": b"{}"}
    connection.execute(
        f"UPDATE kit_coordination_blocks SET {field}=? WHERE namespace=? AND cid=?",
        [changed[field], NS, receipt["cid"]],
    )
    for read in [store.get_bytes, store.get, store.has]:
        with pytest.raises(ArtifactIntegrityError):
            read(receipt["cid"])


def test_wire_row_with_dag_json_identity_is_not_a_wire_transport(native):
    _, connection, store = native
    body = {"schema": "test/native@1", "value": 1}
    receipt = store.put(body)
    connection.execute(
        "UPDATE kit_coordination_blocks SET kind=? WHERE namespace=? AND cid=?",
        [WIRE_JSON_KIND, NS, receipt["cid"]],
    )
    with pytest.raises(ArtifactIntegrityError):
        store.get_bytes(receipt["cid"])


def test_corrupt_oversize_wire_blob_is_rejected_without_returning_its_bytes(native):
    _, connection, store = native
    receipt = put_wire(store, {"value": 1})
    connection.execute(
        "UPDATE kit_coordination_blocks SET block_bytes=?, byte_length=? WHERE namespace=? AND cid=?",
        [b"x" * (MAX_WIRE_JSON_BYTES + 1), MAX_WIRE_JSON_BYTES + 1, NS, receipt["cid"]],
    )
    with pytest.raises(ArtifactIntegrityError, match="byte bound"):
        store.get_bytes(receipt["cid"])


def test_changed_fence_refuses_reads_and_write_without_new_bytes(native):
    _, connection, store = native
    receipt = put_wire(store, {"value": 1})
    connection.execute("UPDATE store_generations SET fence_epoch=99")
    with pytest.raises(NativeOwnerBindingError):
        put_wire(store, {"value": 2})
    with pytest.raises(NativeOwnerBindingError):
        store.get(receipt["cid"])
    assert connection.execute("SELECT count(*) FROM kit_coordination_blocks").fetchone()[0] == 1


def test_wire_root_transition_keeps_original_namespace_validation(native):
    _, _, store = native
    body = {
        "schema": STATE_ROOT_TRANSITION_SCHEMA,
        "namespace": "outside/scope",
        "operation_id": "op1",
        "expected_root_cid": None,
        "expected_revision": 0,
        "new_root_cid": cid_for_bytes(b"{}"),
        "new_revision": 1,
        "created_at_ms": 0,
    }
    with pytest.raises(ValueError, match="scope"):
        put_wire(store, body)
    body["namespace"] = NS
    body["new_revision"] = 0
    with pytest.raises(ValueError):
        put_wire(store, body)
    body["new_revision"] = 1
    receipt = put_wire(store, body)
    assert store.get(receipt["cid"]) == body
    assert store.current_state_root(NS)["revision"] == 0
