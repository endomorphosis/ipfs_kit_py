from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (  # noqa: E402
    ArtifactIntegrityError,
    ArtifactNotFound,
    cid_for_artifact,
)
from ipfs_kit_py.mcp_server.mcplusplus.duckdb_coordination_storage import (  # noqa: E402
    DuckDBCoordinationStore,
    NativeOwnerBindingError,
)

NS = "source-forest/spar/profile1"
IDENTITY = dict(
    store_id="store1",
    server_id="server1",
    database_uuid="database1",
    process_birth_id="birth1",
    generation=1,
    fence_epoch=2,
    schema_revision=3,
)


def install_owner(connection, identity=None):
    identity = dict(IDENTITY if identity is None else identity)
    connection.execute("""CREATE TABLE IF NOT EXISTS store_generations (
        generation BIGINT PRIMARY KEY, schema_revision BIGINT NOT NULL,
        fence_epoch BIGINT NOT NULL, revision BIGINT NOT NULL,
        database_uuid VARCHAR NOT NULL, birth_id VARCHAR NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS state_servers (
        server_id VARCHAR PRIMARY KEY, store_id VARCHAR NOT NULL,
        database_uuid VARCHAR NOT NULL, process_birth_id VARCHAR NOT NULL,
        generation BIGINT NOT NULL, schema_revision BIGINT NOT NULL,
        status VARCHAR NOT NULL, stopped_at VARCHAR)""")
    connection.execute(
        "INSERT INTO store_generations VALUES (?, ?, ?, 1, ?, ?)",
        [
            identity[k]
            for k in (
                "generation",
                "schema_revision",
                "fence_epoch",
                "database_uuid",
                "process_birth_id",
            )
        ],
    )
    connection.execute(
        "INSERT INTO state_servers VALUES (?, ?, ?, ?, ?, ?, 'ready', NULL)",
        [
            identity[k]
            for k in (
                "server_id",
                "store_id",
                "database_uuid",
                "process_birth_id",
                "generation",
                "schema_revision",
            )
        ],
    )
    return identity


class MappingRow(dict):
    """Native accelerator rows iterate column names and permit integer lookup."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class MappingCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.columns = [item[0] for item in cursor.description]

    def fetchone(self):
        row = self.cursor.fetchone()
        return None if row is None else MappingRow(zip(self.columns, row))

    def fetchall(self):
        return [MappingRow(zip(self.columns, row)) for row in self.cursor.fetchall()]


class MappingConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, *args):
        return MappingCursor(self.connection.execute(*args))


@pytest.fixture(params=["raw", "mapping"])
def native(request, tmp_path):
    connection = duckdb.connect(str(tmp_path / "control.duckdb"))
    identity = install_owner(connection)
    lock = threading.RLock()
    store = DuckDBCoordinationStore(
        MappingConnection(connection) if request.param == "mapping" else connection,
        transaction_lock=lock,
        owner_identity=identity,
        namespace=NS,
    )
    yield connection, lock, store
    connection.close()


def artifact(value):
    return {"schema": "test/source-forest@1", "value": value}


def put(store, value):
    return store.put(artifact(value))["cid"]


def cas(store, cid, *, revision=0, root=None, operation="op1"):
    return store.compare_and_swap_state_root(
        NS,
        expected_revision=revision,
        expected_root_cid=root,
        new_root_cid=cid,
        operation_id=operation,
    )


def test_canonical_bytes_idempotence_and_missing_content(native):
    _, _, store = native
    body = artifact({"z": "é", "a": [1, 2]})
    first = store.put(body, expected_cid=cid_for_artifact(body))
    assert first == {
        "cid": cid_for_artifact(body),
        "kind": body["schema"],
        "codec": "dag-json",
        "byte_length": len(store.get_bytes(first["cid"])),
        "created": True,
        "replicated": False,
        "durable": True,
    }
    assert store.put(body)["created"] is False
    assert store.get(first["cid"]) == body
    assert store.has(first["cid"])
    missing = cid_for_artifact(artifact("missing"))
    assert not store.has(missing)
    with pytest.raises(ArtifactNotFound):
        store.get(missing)
    with pytest.raises(ArtifactIntegrityError):
        store.put(body, expected_cid=missing)


def test_cas_wire_shape_chain_replay_stale_and_aba(native):
    _, _, store = native
    one, two, three = [put(store, n) for n in range(3)]
    zero = dict(namespace=NS, root_cid=None, revision=0, transition_cid=None)
    assert store.current_state_root(NS) == zero
    first = cas(store, one)
    assert first == dict(
        status="updated",
        before=zero,
        after=store.current_state_root(NS),
        transition_cid=first["after"]["transition_cid"],
        reason_code="updated",
        local_durable=True,
        replicated=False,
    )
    assert store.get(first["transition_cid"])["new_root_cid"] == one
    second = cas(store, two, revision=1, root=one, operation="op2")
    assert second["after"]["revision"] == 2
    replay = cas(store, one)
    assert replay == dict(
        status="unchanged",
        before=second["after"],
        after=second["after"],
        transition_cid=None,
        reason_code="idempotent_replay",
        local_durable=True,
        replicated=False,
    )
    assert cas(store, three, operation="op1")["reason_code"] == "operation_id_reused"
    assert cas(store, three, operation="stale")["reason_code"] == "stale_expectation"
    third = cas(store, one, revision=2, root=two, operation="aba")
    assert third["after"]["revision"] == 3
    assert (
        cas(store, three, revision=1, root=one, operation="old-aba")["reason_code"]
        == "stale_expectation"
    )
    assert store.current_state_root(NS) == third["after"]


def test_fixed_namespace_isolates_blocks_and_operations(native):
    connection, lock, store = native
    other_ns = "source-forest/pcpr/profile1"
    other = DuckDBCoordinationStore(
        connection, transaction_lock=lock, owner_identity=IDENTITY, namespace=other_ns
    )
    cid = put(store, "one")
    assert not other.has(cid)
    with pytest.raises(ArtifactNotFound):
        other.get(cid)
    with pytest.raises(ValueError, match="outside"):
        other.current_state_root(NS)
    with pytest.raises(ValueError, match="outside"):
        other.compare_and_swap_state_root(
            NS, expected_revision=0, expected_root_cid=None, new_root_cid=cid, operation_id="op1"
        )
    other.put(artifact("one"))
    assert (
        other.compare_and_swap_state_root(
            other_ns,
            expected_revision=0,
            expected_root_cid=None,
            new_root_cid=cid,
            operation_id="op1",
        )["status"]
        == "updated"
    )
    assert cas(store, cid)["status"] == "updated"


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation", 2),
        ("schema_revision", 4),
        ("fence_epoch", 3),
        ("database_uuid", "foreign"),
        ("birth_id", "reused-pid"),
    ],
)
def test_generation_mutation_fences_every_read_and_write(native, field, value):
    connection, _, store = native
    cid = put(store, "one")
    cas(store, cid)
    connection.execute(f"UPDATE store_generations SET {field}=?", [value])
    calls = [
        lambda: store.get(cid),
        lambda: store.get_bytes(cid),
        lambda: store.has(cid),
        lambda: store.current_state_root(NS),
        lambda: put(store, "two"),
        lambda: cas(store, cid),
    ]
    for call in calls:
        with pytest.raises(NativeOwnerBindingError):
            call()


@pytest.mark.parametrize(
    "field,value",
    [
        ("store_id", "foreign"),
        ("server_id", "foreign"),
        ("process_birth_id", "foreign"),
        ("status", "stopped"),
        ("stopped_at", "2026-09-09T21:30:00Z"),
    ],
)
def test_ready_server_binding_fails_closed(native, field, value):
    connection, _, store = native
    connection.execute(f"UPDATE state_servers SET {field}=?", [value])
    with pytest.raises(NativeOwnerBindingError):
        store.current_state_root(NS)


def test_constructor_requires_native_identity_and_does_not_open_files(tmp_path):
    connection = duckdb.connect(":memory:")
    try:
        with pytest.raises(NativeOwnerBindingError):
            DuckDBCoordinationStore(
                connection,
                transaction_lock=threading.RLock(),
                owner_identity=IDENTITY,
                namespace=NS,
            )
        assert connection.execute("SELECT count(*) FROM information_schema.tables").fetchone() == (
            0,
        )
        with pytest.raises(TypeError):
            DuckDBCoordinationStore(
                tmp_path / "forbidden.duckdb",
                transaction_lock=threading.RLock(),
                owner_identity=IDENTITY,
                namespace=NS,
            )
        assert not list(tmp_path.iterdir())
    finally:
        connection.close()


def test_reads_preserve_callers_snapshot_transaction_and_connection(native):
    connection, lock, store = native
    cid = put(store, "one")
    cas(store, cid)
    connection.execute("CREATE TABLE caller_owned (value INTEGER)")
    with lock:
        connection.execute("BEGIN TRANSACTION")
        connection.execute("INSERT INTO caller_owned VALUES (1)")
        assert store.current_state_root(NS)["root_cid"] == cid
        assert store.get(cid) == artifact("one")
        assert store.get_bytes(cid)
        assert store.has(cid)
        connection.execute("ROLLBACK")
    assert connection.execute("SELECT count(*) FROM caller_owned").fetchone() == (0,)
    assert connection.execute("SELECT 42").fetchone() == (42,)


def test_nested_write_begin_failure_does_not_rollback_caller(native):
    connection, _, store = native
    connection.execute("CREATE TABLE caller_owned (value INTEGER)")
    connection.execute("BEGIN")
    connection.execute("INSERT INTO caller_owned VALUES (1)")
    with pytest.raises(duckdb.TransactionException):
        put(store, "one")
    # DuckDB marks the caller transaction aborted on a nested BEGIN. The backend
    # must leave rollback responsibility with that caller, never silently end it.
    connection.execute("ROLLBACK")
    assert connection.execute("SELECT count(*) FROM caller_owned").fetchone() == (0,)


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE kit_coordination_blocks SET block_bytes='broken'::BLOB WHERE cid=?",
        "UPDATE kit_coordination_blocks SET byte_length=1 WHERE cid=?",
        "UPDATE kit_coordination_blocks SET codec='raw' WHERE cid=?",
        "UPDATE kit_coordination_blocks SET kind='wrong' WHERE cid=?",
        "DELETE FROM kit_coordination_blocks WHERE cid=?",
    ],
)
def test_current_root_rejects_corrupt_or_missing_historical_content(native, mutation):
    connection, _, store = native
    one, two = put(store, "one"), put(store, "two")
    cas(store, one)
    cas(store, two, revision=1, root=one, operation="op2")
    connection.execute(mutation, [one])
    with pytest.raises(ArtifactIntegrityError):
        store.current_state_root(NS)
    with pytest.raises(ArtifactIntegrityError):
        cas(store, one)


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE kit_coordination_transitions SET operation_id='forged'",
        "UPDATE kit_coordination_transitions SET expected_revision=1",
        "UPDATE kit_coordination_transitions SET created_at_ms=0",
        "UPDATE kit_coordination_roots SET revision=10",
        "DELETE FROM kit_coordination_roots",
        "DELETE FROM kit_coordination_transitions",
    ],
)
def test_current_root_rejects_pointer_and_transition_corruption(native, mutation):
    connection, _, store = native
    cid = put(store, "one")
    cas(store, cid)
    connection.execute(mutation)
    with pytest.raises(ArtifactIntegrityError):
        store.current_state_root(NS)


class InjectedFailure(BaseException):
    pass


class FailingConnection:
    def __init__(self, connection, fragment, error):
        self.connection, self.fragment, self.error = connection, fragment, error

    def execute(self, sql, *args):
        if self.fragment in sql:
            raise self.error
        return self.connection.execute(sql, *args)


@pytest.mark.parametrize(
    "fragment",
    ["INSERT INTO kit_coordination_transitions", "INSERT INTO kit_coordination_roots", "COMMIT"],
)
@pytest.mark.parametrize("error", [RuntimeError("injected"), InjectedFailure("interrupted")])
def test_failure_rolls_back_transition_block_pointer_and_operation(native, fragment, error):
    connection, lock, store = native
    cid = put(store, "one")
    broken = DuckDBCoordinationStore(
        connection, transaction_lock=lock, owner_identity=IDENTITY, namespace=NS
    )
    broken._connection = FailingConnection(connection, fragment, error)
    with pytest.raises(type(error)):
        cas(broken, cid)
    assert store.current_state_root(NS)["revision"] == 0
    assert connection.execute("SELECT count(*) FROM kit_coordination_blocks").fetchone() == (1,)
    assert connection.execute("SELECT count(*) FROM kit_coordination_transitions").fetchone() == (
        0,
    )
    assert cas(store, cid)["status"] == "updated"


def test_shared_owner_lock_serializes_competing_cas(native):
    _, _, store = native
    one, two = put(store, "one"), put(store, "two")
    start = threading.Barrier(2)

    def update(cid, operation):
        start.wait()
        return cas(store, cid, operation=operation)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(update, one, "one"), pool.submit(update, two, "two")]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(result["status"] for result in results) == ["conflict", "updated"]
    assert store.current_state_root(NS)["revision"] == 1


@pytest.mark.parametrize(
    "kwargs", [{"replicate": True}, {"replicate": 1}, {"codec": "unsupported"}]
)
def test_no_replication_or_alternate_codec(native, kwargs):
    _, _, store = native
    with pytest.raises(ValueError):
        store.put(artifact("one"), **kwargs)


@pytest.mark.parametrize(
    "revision,root", [(True, None), (-1, None), (1, None), (0, cid_for_artifact(artifact("one")))]
)
def test_incoherent_cas_expectation_is_rejected(native, revision, root):
    _, _, store = native
    cid = put(store, "two")
    with pytest.raises(ValueError):
        cas(store, cid, revision=revision, root=root)
    assert store.current_state_root(NS)["revision"] == 0


def test_transition_schema_is_closed_and_namespace_bound(native):
    _, _, store = native
    cid = put(store, "one")
    result = cas(store, cid)
    transition = store.get(result["transition_cid"])
    with pytest.raises(ValueError):
        store.put({**transition, "extra": "not-permitted"})
    with pytest.raises(ValueError):
        store.put({**transition, "namespace": "foreign"})


def test_committed_native_blocks_and_roots_survive_process_crash(tmp_path):
    database = tmp_path / "owner.duckdb"
    result_path = tmp_path / "receipt.json"
    # This fixture owns opening the database. The backend receives only the
    # already-open native connection, including on generation rollover.
    script = """
import json, os, sys, threading
import duckdb
from test_duckdb_coordination_storage import install_owner, IDENTITY, NS
from ipfs_kit_py.mcp_server.mcplusplus.duckdb_coordination_storage import DuckDBCoordinationStore
c = duckdb.connect(sys.argv[1])
install_owner(c)
s = DuckDBCoordinationStore(c, transaction_lock=threading.RLock(), owner_identity=IDENTITY, namespace=NS)
cid = s.put({"schema": "test/crash@1", "value": 42})["cid"]
r = s.compare_and_swap_state_root(NS, expected_revision=0, expected_root_cid=None, new_root_cid=cid, operation_id="crash")
with open(sys.argv[2], "w") as f:
    json.dump(r, f)
    f.flush()
    os.fsync(f.fileno())
os._exit(23)
"""
    environment = dict(os.environ)
    root = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(root), str(root / "tests"), environment.get("PYTHONPATH", "")]
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, str(database), str(result_path)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 23, completed.stderr
    receipt = json.loads(result_path.read_text())
    connection = duckdb.connect(str(database))
    try:
        identity = dict(
            IDENTITY, generation=2, fence_epoch=3, server_id="server2", process_birth_id="birth2"
        )
        install_owner(connection, identity)
        store = DuckDBCoordinationStore(
            connection, transaction_lock=threading.RLock(), owner_identity=identity, namespace=NS
        )
        assert store.current_state_root(NS) == receipt["after"]
        assert store.get(receipt["after"]["root_cid"])["value"] == 42
        assert (
            cas(store, receipt["after"]["root_cid"], operation="crash")["reason_code"]
            == "idempotent_replay"
        )
        assert store.get(receipt["transition_cid"])["operation_id"] == "crash"
    finally:
        connection.close()


@pytest.mark.parametrize("point", ["INSERT INTO kit_coordination_roots", "COMMIT"])
def test_uncommitted_cas_is_rolled_back_after_whole_process_death(tmp_path, point):
    database = tmp_path / "owner.duckdb"
    script = """
import os, sys, threading
import duckdb
from test_duckdb_coordination_storage import install_owner, IDENTITY, NS
from ipfs_kit_py.mcp_server.mcplusplus.duckdb_coordination_storage import DuckDBCoordinationStore
c = duckdb.connect(sys.argv[1])
install_owner(c)
s = DuckDBCoordinationStore(c, transaction_lock=threading.RLock(), owner_identity=IDENTITY, namespace=NS)
cid = s.put({"schema": "test/crash@1", "value": 42})["cid"]
class CrashDuringCAS:
    def execute(self, sql, *args):
        if sys.argv[2] in sql:
            os._exit(24)
        return c.execute(sql, *args)
s._connection = CrashDuringCAS()
s.compare_and_swap_state_root(NS, expected_revision=0, expected_root_cid=None, new_root_cid=cid, operation_id="crash")
"""
    environment = dict(os.environ)
    root = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(root), str(root / "tests"), environment.get("PYTHONPATH", "")]
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, str(database), point],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 24, completed.stderr
    connection = duckdb.connect(str(database))
    try:
        identity = dict(
            IDENTITY, generation=2, fence_epoch=3, server_id="server2", process_birth_id="birth2"
        )
        install_owner(connection, identity)
        store = DuckDBCoordinationStore(
            connection, transaction_lock=threading.RLock(), owner_identity=identity, namespace=NS
        )
        assert store.current_state_root(NS)["revision"] == 0
        assert connection.execute("SELECT count(*) FROM kit_coordination_blocks").fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM kit_coordination_transitions"
        ).fetchone() == (0,)
        cid = cid_for_artifact({"schema": "test/crash@1", "value": 42})
        assert cas(store, cid, operation="crash")["status"] == "updated"
    finally:
        connection.close()


def test_changed_namespace_binding_fences_existing_store(native):
    connection, _, store = native
    cid = put(store, "one")
    connection.execute("UPDATE kit_coordination_namespaces SET database_uuid='foreign'")
    with pytest.raises(NativeOwnerBindingError, match="namespace binding"):
        store.get(cid)
    with pytest.raises(NativeOwnerBindingError):
        put(store, "two")


def test_non_duckdb_connection_is_rejected_without_schema_mutation():
    import sqlite3

    connection = sqlite3.connect(":memory:")
    try:
        with pytest.raises(NativeOwnerBindingError, match="DuckDB"):
            DuckDBCoordinationStore(
                connection,
                transaction_lock=threading.RLock(),
                owner_identity=IDENTITY,
                namespace=NS,
            )
        assert connection.execute("SELECT count(*) FROM sqlite_master").fetchone() == (0,)
    finally:
        connection.close()


def test_memory_owner_cannot_issue_durable_receipts():
    connection = duckdb.connect(":memory:")
    try:
        install_owner(connection)
        with pytest.raises(NativeOwnerBindingError, match="persistent native DuckDB"):
            DuckDBCoordinationStore(
                connection,
                transaction_lock=threading.RLock(),
                owner_identity=IDENTITY,
                namespace=NS,
            )
        assert connection.execute("SELECT count(*) FROM information_schema.tables").fetchone() == (
            2,
        )
    finally:
        connection.close()


def test_public_namespace_cannot_be_retargeted(native):
    _, _, store = native
    with pytest.raises(AttributeError):
        store.namespace = "source-forest/foreign/profile1"
    assert store.namespace == NS
