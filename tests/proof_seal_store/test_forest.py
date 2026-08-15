"""Regression tests for deterministic proof-forest persistence (IPS-022).

Acceptance coverage:

* repository root matches datasets forest vectors;
* identical replay is deterministic;
* one or two independent changes touch only the expected branches;
* unaffected leaf loss fails closed;
* changed manifest paired with old aggregate fails closed;
* duplicate / reordered leaves are rejected via the datasets codec.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ipfs_datasets_py.logic.zkp.incremental_sealing.forest_codec import (
    FOREST_CATEGORIES,
    GENESIS_PARENT_SEAL,
    compute_repository_root,
    known_vectors,
    sample_category_leaves,
    sample_leaf,
    sample_repository_proof_root,
)
from ipfs_datasets_py.logic.zkp.incremental_sealing.identity import canonical_cid
from ipfs_kit_py.proof_seal_store.contracts import ExplicitRootRequiredError
from ipfs_kit_py.proof_seal_store.forest import (
    EVIDENCE_SUBSET,
    FOREST_STORE_INTERFACE,
    ForestDisposition,
    ForestReason,
    ProofForestStore,
    persist_forest,
    update_forest_branches,
    verify_unaffected_leaves,
)


def _sample_cid(label: str) -> str:
    return canonical_cid({"ips_forest_codec_sample": label, "v": 1})


def _base_category_leaves() -> dict[str, tuple[Any, ...]]:
    return {
        "unit_test": sample_category_leaves("unit_test"),
        "static_analysis": (
            sample_leaf(
                proof_unit_id="unit/static-a",
                category="static_analysis",
                position=0,
            ),
        ),
    }


def _persist_base(store: ProofForestStore) -> Any:
    leaves = _base_category_leaves()
    return store.persist_forest(
        repository_id="repo/datasets",
        revision="rev-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        source_root_cid=_sample_cid("source-root"),
        manifest_root_cid=_sample_cid("manifest-root"),
        environment_cid=_sample_cid("environment"),
        policy_cid=_sample_cid("policy"),
        category_leaves=leaves,
        parent_seal_cid=GENESIS_PARENT_SEAL,
        parent_revision_ids=(),
    )


def _store(tmp_path: Path) -> ProofForestStore:
    return ProofForestStore(tmp_path)


# ---------------------------------------------------------------------------
# Construction / constants
# ---------------------------------------------------------------------------


def test_schema_and_evidence_constants() -> None:
    assert EVIDENCE_SUBSET == "ips/proof-forest-store@1"
    assert FOREST_STORE_INTERFACE == "ProofForestStore@1"


def test_explicit_root_is_mandatory() -> None:
    with pytest.raises(ExplicitRootRequiredError):
        ProofForestStore(None)
    with pytest.raises(ExplicitRootRequiredError):
        ProofForestStore("relative/forest")
    with pytest.raises(ExplicitRootRequiredError):
        ProofForestStore("~/proof-forest")


# ---------------------------------------------------------------------------
# Root matches datasets vectors + deterministic replay
# ---------------------------------------------------------------------------


def test_root_matches_datasets_vectors(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = _persist_base(store)
    assert result.stored
    assert result.snapshot is not None

    vectors = known_vectors()
    expected_root = vectors["base"]["root_cid"]
    sample = sample_repository_proof_root()
    assert sample.root_cid == expected_root
    assert result.root_cid == expected_root
    assert result.snapshot.root_cid == expected_root
    assert dict(result.snapshot.category_roots) == dict(
        vectors["base"]["category_roots"]
    )

    # Codec-computed root from the same leaves matches the store.
    recomputed = compute_repository_root(
        repository_id="repo/datasets",
        revision="rev-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        source_root_cid=_sample_cid("source-root"),
        manifest_root_cid=_sample_cid("manifest-root"),
        environment_cid=_sample_cid("environment"),
        policy_cid=_sample_cid("policy"),
        category_leaves=_base_category_leaves(),
    )
    assert recomputed.root_cid == result.root_cid


def test_identical_replay_is_deterministic(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = _persist_base(store)
    second = _persist_base(store)
    assert first.root_cid == second.root_cid
    assert first.snapshot is not None and second.snapshot is not None
    assert dict(first.snapshot.category_roots) == dict(second.snapshot.category_roots)
    assert first.snapshot.node_cids == second.snapshot.node_cids
    assert second.disposition is ForestDisposition.ALREADY_EXISTS
    assert second.reason is ForestReason.ALREADY_EXISTS

    # Module-level alias and a second store root with identical inputs.
    other = _store(tmp_path / "other")
    via_alias = persist_forest(
        other,
        repository_id="repo/datasets",
        revision="rev-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        source_root_cid=_sample_cid("source-root"),
        manifest_root_cid=_sample_cid("manifest-root"),
        environment_cid=_sample_cid("environment"),
        policy_cid=_sample_cid("policy"),
        category_leaves=_base_category_leaves(),
    )
    assert via_alias.root_cid == first.root_cid
    loaded = store.load_forest(first.root_cid)
    assert loaded.root_cid == first.root_cid
    assert loaded.node_cids == first.snapshot.node_cids
    assert dict(loaded.category_roots) == dict(first.snapshot.category_roots)


# ---------------------------------------------------------------------------
# Affected-branch updates
# ---------------------------------------------------------------------------


def test_one_independent_change_touches_only_expected_branch(tmp_path: Path) -> None:
    store = _store(tmp_path)
    base = _persist_base(store)
    assert base.snapshot is not None
    parent = base.snapshot

    flipped_unit = (
        sample_leaf(proof_unit_id="unit/a", category="unit_test", position=0),
        sample_leaf(
            proof_unit_id="unit/b",
            category="unit_test",
            position=1,
            proof_object_cid=_sample_cid("proof:unit/b-flipped"),
        ),
    )
    update = store.update_forest_branches(
        parent.root_cid,
        affected_category_leaves={"unit_test": flipped_unit},
    )
    assert update.updated
    assert update.snapshot is not None
    assert update.touched_categories == ("unit_test",)
    assert "static_analysis" in update.reused_categories
    assert "unit_test" not in update.reused_categories

    # Only unit_test category root changes; static_analysis is reused.
    assert (
        update.snapshot.category_roots["unit_test"]
        != parent.category_roots["unit_test"]
    )
    assert (
        update.snapshot.category_roots["static_analysis"]
        == parent.category_roots["static_analysis"]
    )
    for cat in FOREST_CATEGORIES:
        if cat == "unit_test":
            continue
        assert (
            update.snapshot.category_roots[cat] == parent.category_roots[cat]
        )
        assert update.snapshot.branch_paths[cat] == parent.branch_paths[cat]

    assert update.root_cid != parent.root_cid
    assert update.snapshot.parent_forest_root_cid == parent.root_cid

    # Matches datasets one-bit mutation vector.
    vectors = known_vectors()
    assert update.root_cid == vectors["one_bit_leaf_mutation"]["root_cid"]


def test_two_independent_changes_touch_only_expected_branches(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    base = _persist_base(store)
    assert base.snapshot is not None
    parent = base.snapshot

    new_unit = (
        sample_leaf(proof_unit_id="unit/a", category="unit_test", position=0),
        sample_leaf(
            proof_unit_id="unit/b",
            category="unit_test",
            position=1,
            proof_object_cid=_sample_cid("proof:unit/b-two"),
        ),
    )
    new_static = (
        sample_leaf(
            proof_unit_id="unit/static-a",
            category="static_analysis",
            position=0,
            proof_object_cid=_sample_cid("proof:static-a-two"),
        ),
    )
    update = update_forest_branches(
        store,
        parent.root_cid,
        affected_category_leaves={
            "unit_test": new_unit,
            "static_analysis": new_static,
        },
    )
    assert update.updated
    assert set(update.touched_categories) == {"unit_test", "static_analysis"}
    for cat in update.touched_categories:
        assert (
            update.snapshot.category_roots[cat]  # type: ignore[union-attr]
            != parent.category_roots[cat]
        )
    for cat in FOREST_CATEGORIES:
        if cat in {"unit_test", "static_analysis"}:
            continue
        assert (
            update.snapshot.category_roots[cat]  # type: ignore[union-attr]
            == parent.category_roots[cat]
        )
        assert cat in update.reused_categories


# ---------------------------------------------------------------------------
# Fail-closed: lost leaves, old aggregate, codec rejects
# ---------------------------------------------------------------------------


def test_unaffected_leaf_loss_fails(tmp_path: Path) -> None:
    store = _store(tmp_path)
    base = _persist_base(store)
    assert base.snapshot is not None
    parent = base.snapshot

    # full map drops the static_analysis leaf while claiming only unit_test
    # is affected.
    flipped_unit = (
        sample_leaf(proof_unit_id="unit/a", category="unit_test", position=0),
        sample_leaf(
            proof_unit_id="unit/b",
            category="unit_test",
            position=1,
            proof_object_cid=_sample_cid("proof:unit/b-lost-path"),
        ),
    )
    full_missing_static = {
        "unit_test": flipped_unit,
        # static_analysis omitted / empty => lost unaffected leaf
        "static_analysis": (),
    }
    result = store.update_forest_branches(
        parent.root_cid,
        affected_category_leaves={"unit_test": flipped_unit},
        full_category_leaves=full_missing_static,
    )
    assert not result.updated
    assert result.disposition is ForestDisposition.REJECTED
    assert result.reason is ForestReason.LOST_UNAFFECTED_LEAF

    # Direct equality witness API.
    witness = verify_unaffected_leaves(
        parent.category_leaves_map(),
        full_missing_static,
        {"unit_test"},
    )
    assert not witness.verified
    assert witness.reason is ForestReason.LOST_UNAFFECTED_LEAF
    assert any("static_analysis" in item for item in witness.lost_leaves)


def test_changed_manifest_with_old_aggregate_fails(tmp_path: Path) -> None:
    store = _store(tmp_path)
    base = _persist_base(store)
    assert base.snapshot is not None
    parent = base.snapshot

    new_manifest = _sample_cid("manifest-root-mutated")
    assert new_manifest != parent.manifest_root_cid

    # Claim the old aggregate root while changing the manifest.
    result = store.update_forest_branches(
        parent.root_cid,
        affected_category_leaves={},
        manifest_root_cid=new_manifest,
        claimed_repository_root_cid=parent.root_cid,
    )
    assert not result.updated
    assert result.disposition is ForestDisposition.REJECTED
    assert result.reason is ForestReason.MANIFEST_AGGREGATE_MISMATCH

    # Honest manifest change without old-root claim succeeds and changes root.
    honest = store.update_forest_branches(
        parent.root_cid,
        affected_category_leaves={},
        manifest_root_cid=new_manifest,
    )
    assert honest.updated
    assert honest.root_cid != parent.root_cid
    assert honest.snapshot is not None
    assert honest.snapshot.manifest_root_cid == new_manifest
    # No category branches were content-affected.
    for cat in FOREST_CATEGORIES:
        assert (
            honest.snapshot.category_roots[cat] == parent.category_roots[cat]
        )


def test_old_aggregate_after_leaf_change_fails(tmp_path: Path) -> None:
    store = _store(tmp_path)
    base = _persist_base(store)
    assert base.snapshot is not None
    parent = base.snapshot

    flipped_unit = (
        sample_leaf(proof_unit_id="unit/a", category="unit_test", position=0),
        sample_leaf(
            proof_unit_id="unit/b",
            category="unit_test",
            position=1,
            proof_object_cid=_sample_cid("proof:unit/b-old-agg"),
        ),
    )
    result = store.update_forest_branches(
        parent.root_cid,
        affected_category_leaves={"unit_test": flipped_unit},
        claimed_repository_root_cid=parent.root_cid,
    )
    assert not result.updated
    assert result.reason is ForestReason.OLD_AGGREGATE


def test_duplicate_and_reordered_leaves_fail(tmp_path: Path) -> None:
    store = _store(tmp_path)
    dup = store.persist_forest(
        repository_id="repo/datasets",
        revision="rev-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        source_root_cid=_sample_cid("source-root"),
        manifest_root_cid=_sample_cid("manifest-root"),
        environment_cid=_sample_cid("environment"),
        policy_cid=_sample_cid("policy"),
        category_leaves={
            "unit_test": (
                sample_leaf(
                    proof_unit_id="unit/a", category="unit_test", position=0
                ),
                sample_leaf(
                    proof_unit_id="unit/a", category="unit_test", position=1
                ),
            )
        },
    )
    assert not dup.stored
    assert dup.reason is ForestReason.DUPLICATE_LEAF

    reordered = store.persist_forest(
        repository_id="repo/datasets",
        revision="rev-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        source_root_cid=_sample_cid("source-root"),
        manifest_root_cid=_sample_cid("manifest-root"),
        environment_cid=_sample_cid("environment"),
        policy_cid=_sample_cid("policy"),
        category_leaves={
            "unit_test": (
                sample_leaf(
                    proof_unit_id="unit/b", category="unit_test", position=0
                ),
                sample_leaf(
                    proof_unit_id="unit/a", category="unit_test", position=1
                ),
            )
        },
    )
    assert not reordered.stored
    assert reordered.reason is ForestReason.REORDERED_LEAVES


def test_immutable_merkle_nodes_are_persisted(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = _persist_base(store)
    assert result.snapshot is not None
    assert result.node_count > 0
    assert len(result.snapshot.node_cids) == result.node_count
    # Every forest node has a kit artifact reference under merkle_node.
    assert set(result.snapshot.artifact_refs) >= set(result.snapshot.node_cids)
    for forest_cid, artifact_cid in result.snapshot.artifact_refs.items():
        assert forest_cid
        assert artifact_cid
