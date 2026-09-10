"""Independent current-tree checks for DOEP-062 Kit durable storage and root CAS."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

IPFS_KIT_ROOT = Path(__file__).resolve().parents[2]
if str(IPFS_KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(IPFS_KIT_ROOT))

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (  # noqa: E402
    KIT_CONTEXT_PACK_STORAGE_OWNERSHIP,
    ROOT_CAS_INTERRUPTION_POINTS,
    STATE_ROOT_TRANSITION_SCHEMA,
    SUPERVISOR_CONTEXT_PACK_SCHEMA,
    SUPERVISOR_CONTEXT_PACK_SCHEMA_VERSION,
    SUPERVISOR_CONTEXT_PACK_STORAGE_FORBIDDEN_FIELDS,
    DurableCoordinationStore,
)


OWNER_RELATIVE_OUTPUTS = (
    "ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py",
    "tests/doep/test_doep_062_implement_kit_durable_storage_and_current_root_cas.py",
    "artifacts/agent_supervisor_direct_objective_event_driven_planning/outputs/DOEP-062.json",
    "artifacts/agent_supervisor_direct_objective_event_driven_planning/receipts/DOEP-062.json",
)
OUTPUT_PATH = IPFS_KIT_ROOT / OWNER_RELATIVE_OUTPUTS[2]
RECEIPT_PATH = IPFS_KIT_ROOT / OWNER_RELATIVE_OUTPUTS[3]
BASE_REPOSITORIES = {
    "ipfs_accelerate_py": {
        "commit": "87715e9295626e7918f7fc8a7b1a1531ab04208f",
        "tree": "1c9a399cc7a599d5904e5be2ae58c6be3650cff7",
    },
    "ipfs_datasets_py": {
        "commit": "3668b8857a9aa7b1a3c847be12725b5cd057d2e7",
        "tree": "456e09b51d6a07a3a5873436df24054768195320",
    },
    "ipfs_kit_py": {
        "commit": "b6c65ba732733d7e33852713ba18aa3b12235668",
        "tree": "14da7d92e130b7ba3523d0d6741a3ef7ef1e1bc2",
    },
    "lift_coding": {
        "commit": "bb8869ed72eb7002434345d9969efee729c4f7f6",
        "tree": "99e85bfe584b7688ffbeff86da1e612dd6893a42",
    },
}
TASK_CID = "sha256:c2027ab0ee4c77c34f933168d0815e11504014a06e75ef44509fea0a8ce55e1c"
PLAN_CID = "sha256:6c197a4b92682b3b813656123e09956846dc4f5abadf417f37fb7cc0133ddba4"
NAMESPACE = "context-pack/doep-062"


class InjectedInterruption(RuntimeError):
    """Stand-in for a process stop at a durable CAS boundary."""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _reference_cid(store: DurableCoordinationStore, label: str) -> str:
    return store.put({"schema": "example/state@1", "label": label})["cid"]


def _supervisor_pack(store: DurableCoordinationStore, *, task_id: str = "DOEP-062") -> dict[str, Any]:
    reference = _reference_cid(store, f"ref:{task_id}")
    return {
        "capsule_cids": [reference],
        "expansion_required": False,
        "pack_cid": reference,
        "producer": "ipfs_datasets_py.proof_context.context_pack",
        "repository_state_cid": reference,
        "required_source_cids": {
            "target_source": reference,
            "surrounding_source": reference,
            "test_source": reference,
        },
        "scanned_tree_oid": "16ef68abe8a35a3033dfaf1ed4e8d6132600df8f",
        "schema": SUPERVISOR_CONTEXT_PACK_SCHEMA,
        "schema_version": SUPERVISOR_CONTEXT_PACK_SCHEMA_VERSION,
        "sufficiency_state": "sufficient",
        "task_id": task_id,
    }


def test_declared_outputs_exist() -> None:
    assert all((IPFS_KIT_ROOT / path).is_file() for path in OWNER_RELATIVE_OUTPUTS)


def test_supervisor_context_pack_is_locally_durable_exact_bytes(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "coordination", clock_ms=lambda: 1_700_000_000_000) as store:
        payload = _supervisor_pack(store)
        stored = store.put_supervisor_context_pack(payload)
        assert stored["local_durable"] is True
        assert stored["durable"] is True
        assert stored["schema"] == SUPERVISOR_CONTEXT_PACK_SCHEMA
        assert stored["ownership"] == dict(KIT_CONTEXT_PACK_STORAGE_OWNERSHIP)
        assert store.get(stored["cid"]) == payload
        assert set(payload).isdisjoint(SUPERVISOR_CONTEXT_PACK_STORAGE_FORBIDDEN_FIELDS)


def test_current_root_cas_publishes_rejects_stale_and_replays(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "coordination") as store:
        first = store.put_supervisor_context_pack(_supervisor_pack(store, task_id="DOEP-062-a"))
        second = store.put_supervisor_context_pack(_supervisor_pack(store, task_id="DOEP-062-b"))
        assert store.current_root(NAMESPACE) == {
            "namespace": NAMESPACE,
            "root_cid": None,
            "revision": 0,
            "transition_cid": None,
        }

        updated = store.compare_and_swap_state_root(
            NAMESPACE,
            expected_revision=0,
            expected_root_cid=None,
            new_root_cid=first["cid"],
            operation_id="context-pack-root:1",
        )
        replay = store.compare_and_swap_root(
            NAMESPACE,
            expected_revision=0,
            expected_root_cid=None,
            new_root_cid=first["cid"],
            operation_id="context-pack-root:1",
        )
        stale = store.compare_and_swap_state_root(
            NAMESPACE,
            expected_revision=0,
            expected_root_cid=None,
            new_root_cid=second["cid"],
            operation_id="context-pack-root:2",
        )
        advanced = store.compare_and_swap_state_root(
            NAMESPACE,
            expected_revision=1,
            expected_root_cid=first["cid"],
            new_root_cid=second["cid"],
            operation_id="context-pack-root:3",
        )

        assert updated["status"] == "updated"
        assert updated["local_durable"] is True
        assert store.get(updated["transition_cid"])["schema"] == STATE_ROOT_TRANSITION_SCHEMA
        assert replay["status"] == "unchanged"
        assert replay["reason_code"] == "idempotent_replay"
        assert stale["status"] == "conflict"
        assert stale["reason_code"] == "stale_expectation"
        assert advanced["status"] == "updated"
        assert store.current_state_root(NAMESPACE) == advanced["after"]
        assert store.status()["counts"]["state_roots"] == 1
        assert store.status()["counts"]["state_root_transitions"] == 2
        assert store.status()["durable_storage"] == "DurableCoordinationStore"
        assert store.status()["current_root_cas"] == "compare_and_swap_state_root"
        assert store.status()["ownership"] == dict(KIT_CONTEXT_PACK_STORAGE_OWNERSHIP)


def test_storage_boundary_rejects_authority_fields_and_open_shapes(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "coordination") as store:
        payload = _supervisor_pack(store)
        with pytest.raises(ValueError, match="forbidden|unknown"):
            store.put_supervisor_context_pack({**payload, "execution_admission": True})
        with pytest.raises(ValueError, match="missing|unknown"):
            incomplete = dict(payload)
            del incomplete["task_id"]
            store.put_supervisor_context_pack(incomplete)


def test_recovery_rebuilds_context_pack_root_from_immutable_evidence(tmp_path: Path) -> None:
    root = tmp_path / "coordination"
    with DurableCoordinationStore(root) as store:
        stored = store.put_supervisor_context_pack(_supervisor_pack(store))
        published = store.compare_and_swap_state_root(
            NAMESPACE,
            expected_revision=0,
            expected_root_cid=None,
            new_root_cid=stored["cid"],
            operation_id="context-pack-root:recover",
        )
    (root / "coordination.sqlite3").unlink()
    for sidecar in root.glob("coordination.sqlite3-*"):
        sidecar.unlink()
    with DurableCoordinationStore(root) as recovered:
        assert recovered.current_root(NAMESPACE) == published["after"]
        assert recovered.get(stored["cid"])["schema"] == SUPERVISOR_CONTEXT_PACK_SCHEMA
        assert recovered.root_transitions(NAMESPACE)[0]["operation_id"] == "context-pack-root:recover"


@pytest.mark.parametrize("boundary", ROOT_CAS_INTERRUPTION_POINTS)
def test_root_cas_interruption_recovers_without_a_competing_store(
    tmp_path: Path, boundary: str
) -> None:
    root = tmp_path / boundary

    def interrupt(point: str) -> None:
        if point == boundary:
            raise InjectedInterruption(point)

    with DurableCoordinationStore(root, crash_injector=interrupt) as store:
        successor = store.put_supervisor_context_pack(_supervisor_pack(store))["cid"]
        with pytest.raises(InjectedInterruption, match=boundary):
            store.compare_and_swap_state_root(
                NAMESPACE,
                expected_revision=0,
                expected_root_cid=None,
                new_root_cid=successor,
                operation_id="context-pack-root:interrupted",
            )

    with DurableCoordinationStore(root) as recovered:
        current = recovered.current_root(NAMESPACE)
        if boundary in {"before_transaction", "after_expectation_verification"}:
            assert current["revision"] == 0
            assert current["root_cid"] is None
        else:
            assert current["revision"] == 1
            assert current["root_cid"] == successor
        replay = recovered.compare_and_swap_root(
            NAMESPACE,
            expected_revision=0,
            expected_root_cid=None,
            new_root_cid=successor,
            operation_id="context-pack-root:interrupted",
        )
        expected = (
            "updated"
            if boundary in {"before_transaction", "after_expectation_verification"}
            else "unchanged"
        )
        assert replay["status"] == expected
        assert recovered.current_root(NAMESPACE)["revision"] == 1
        assert recovered.status()["durable_storage"] == "DurableCoordinationStore"


def test_receipt_binds_exact_outputs_and_kit_authority_split() -> None:
    manifest, receipt = _load(OUTPUT_PATH), _load(RECEIPT_PATH)
    assert manifest["task_id"] == receipt["task_id"] == "DOEP-062"
    assert manifest["task_cid"] == receipt["task_cid"] == TASK_CID
    assert manifest["plan_cid"] == receipt["plan_cid"] == PLAN_CID
    assert manifest["declared_outputs"] == receipt["expected_outputs"] == list(OWNER_RELATIVE_OUTPUTS)
    assert manifest["durable_storage"] == "DurableCoordinationStore"
    assert manifest["current_root_cas"] == "compare_and_swap_state_root"
    assert manifest["state_root_transition_schema"] == STATE_ROOT_TRANSITION_SCHEMA
    assert manifest["supervisor_context_pack_schema"] == SUPERVISOR_CONTEXT_PACK_SCHEMA
    assert manifest["cross_repository_ownership"] == dict(KIT_CONTEXT_PACK_STORAGE_OWNERSHIP)
    assert manifest["no_competing_subsystem_created"] is True
    assert receipt["no_competing_subsystem_created"] is True
    assert receipt["authority"] == dict(KIT_CONTEXT_PACK_STORAGE_OWNERSHIP)
    digests = {path: _sha256(IPFS_KIT_ROOT / path) for path in OWNER_RELATIVE_OUTPUTS[:-1]}
    assert receipt["path_digests"] == digests
    canonical = json.dumps(digests, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert receipt["required_evidence"]["changed_path_digest"] == (
        "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    )
    assert receipt["required_evidence"]["source_commit_tree_gitlinks"] == BASE_REPOSITORIES
    assert receipt["required_evidence"]["test_proof_results"]["validation_command"] == [
        "python3",
        "-m",
        "pytest",
        "tests/doep/test_doep_062_implement_kit_durable_storage_and_current_root_cas.py",
        "-q",
    ]
