"""KVFS-404: Exact ARC invalidation/generation advance from mutation and replay.

Acceptance coverage:

* committed create/replace/write/truncate/unlink/rename and recovery replay
  advance or invalidate exactly affected bindings before new admission;
* unrelated data remains;
* aborted/failed effects do not publish; and
* randomized interleavings return no stale committed byte.
"""

from __future__ import annotations

import ast
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import pytest

from ipfs_kit_py.arc_cache import GenerationBoundARC
from ipfs_kit_py.cache.arc.contracts import ARCConfig
from ipfs_kit_py.cache.arc.range_bindings import RangeBinding
from ipfs_kit_py.kernel_vfs import cache_coherence as cc_mod
from ipfs_kit_py.kernel_vfs.cache_coherence import (
    CACHE_COHERENCE_SCHEMA,
    CONTRACT_VERSION,
    COHERENCE_EVENT_SCHEMA,
    COHERENCE_METRICS_SCHEMA,
    COHERENCE_PROJECTOR_SCHEMA,
    COHERENCE_RECEIPT_SCHEMA,
    GENERATION_ADVANCE_SCHEMA,
    SCHEMA_VERSION,
    TASK_ID,
    CacheCoherence,
    CacheCoherence_V1,
    CoherenceAction,
    CoherenceAdmissionBlocked,
    CoherenceDisposition,
    CoherenceEvent,
    CoherenceMutationKind,
    CoherenceProjector,
    CoherenceProjector_V1,
    CoherenceReceipt,
    CoherenceSource,
    CoherenceValidationError,
    GenerationAdvance_V1,
    next_generation,
    path_to_content_id,
)
from ipfs_kit_py.kernel_vfs.cached_storage import CachedStorage

# test file: .../tests/kernel_vfs/arc/test_coherence.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "kernel_vfs" / "cache_coherence.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _binding(
    *,
    namespace: str = "ns-a",
    content_id: str = "path:docs.file",
    version: str = "v1",
    generation: str = "g:1",
    serializer: str = "bytes@1",
    offset: int = 0,
    length: int = 8,
    policy: str = "public",
) -> RangeBinding:
    return RangeBinding(
        namespace=namespace,
        content_id=content_id,
        version=version,
        generation=generation,
        serializer=serializer,
        offset=offset,
        length=length,
        policy=policy,
    )


def _storage(**kwargs) -> CachedStorage:
    defaults = dict(
        authorize=lambda _b: True,
        consistent=lambda _b: True,
        capacity_bytes=256 * 1024,
    )
    defaults.update(kwargs)
    return CachedStorage(**defaults)


def _coherence(storage: CachedStorage | None = None, **kwargs) -> CacheCoherence:
    if storage is None:
        storage = _storage()
    return CacheCoherence(storage, **kwargs)


def _event(
    kind: CoherenceMutationKind | str,
    *,
    disposition: CoherenceDisposition | str = CoherenceDisposition.COMMITTED,
    path: str = "docs/file",
    content_id: str = "",
    namespace: str = "ns-a",
    generation: str = "g:2",
    prior_generation: str = "g:1",
    offset: int | None = None,
    length: int | None = None,
    size: int | None = None,
    target_path: str = "",
    target_content_id: str = "",
    effect_id: str = "effect:1",
    transaction_id: str = "txn:1",
    source: CoherenceSource | str = CoherenceSource.MUTATION,
    version: str = "v2",
    prior_version: str = "v1",
) -> CoherenceEvent:
    return CoherenceEvent(
        kind=kind,
        disposition=disposition,
        path=path,
        content_id=content_id or path_to_content_id(path),
        namespace=namespace,
        generation=generation,
        prior_generation=prior_generation,
        version=version,
        prior_version=prior_version,
        offset=offset,
        length=length,
        size=size,
        target_path=target_path,
        target_content_id=target_content_id,
        effect_id=effect_id,
        transaction_id=transaction_id,
        source=source,
        serializer="bytes@1",
        policy="public",
    )


def _admit(
    coh: CacheCoherence,
    binding: RangeBinding,
    payload: bytes | None = None,
) -> bool:
    data = payload if payload is not None else b"X" * binding.length
    # CachedStorage / coherence put_committed require exact length match.
    assert len(data) == binding.length, (
        f"test payload length {len(data)} disagrees with binding length "
        f"{binding.length}: {data!r}"
    )
    return coh.put_committed(binding, data)


# ---------------------------------------------------------------------------
# Artifact / schema / inertness
# ---------------------------------------------------------------------------


def test_declared_module_exists() -> None:
    assert MODULE_PATH.is_file()
    assert MODULE_PATH.stat().st_size > 0


def test_schema_versions_and_aliases() -> None:
    assert TASK_ID == "KVFS-404"
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert CACHE_COHERENCE_SCHEMA == CacheCoherence_V1
    assert COHERENCE_PROJECTOR_SCHEMA == CoherenceProjector_V1
    assert GENERATION_ADVANCE_SCHEMA == GenerationAdvance_V1
    assert CacheCoherence_V1.endswith("@1")
    assert COHERENCE_EVENT_SCHEMA.endswith("@1")
    assert COHERENCE_RECEIPT_SCHEMA.endswith("@1")
    assert COHERENCE_METRICS_SCHEMA.endswith("@1")
    assert CoherenceProjector is CacheCoherence


def test_module_has_no_fusepy_dependency() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = frozenset({"fuse", "fusepy"})
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in banned
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in banned


def test_exports_are_importable() -> None:
    assert cc_mod.CacheCoherence is CacheCoherence
    assert cc_mod.path_to_content_id is path_to_content_id
    assert cc_mod.next_generation is next_generation


def test_path_to_content_id_and_next_generation() -> None:
    assert path_to_content_id("docs/file") == "path:docs.file"
    assert next_generation(None) == "g:1"
    assert next_generation("g:1") == "g:2"
    g = next_generation(effect_id="effect:abc")
    assert g.startswith("g:")
    assert g == next_generation(effect_id="effect:abc")


# ---------------------------------------------------------------------------
# Committed mutations advance/invalidate exactly affected bindings
# ---------------------------------------------------------------------------


def test_committed_create_advances_generation_and_drops_prior() -> None:
    store = _storage()
    coh = _coherence(store)
    cid = path_to_content_id("docs/file")
    old = _binding(content_id=cid, generation="g:1", length=8)
    unrelated = _binding(
        content_id=path_to_content_id("other/file"),
        generation="g:1",
        length=8,
    )
    assert _admit(coh, old, b"old-data")
    assert _admit(coh, unrelated, b"unrelate")
    assert coh.get(old) == b"old-data"

    receipt = coh.publish(
        _event(
            CoherenceMutationKind.CREATE,
            path="docs/file",
            content_id=cid,
            generation="g:2",
            prior_generation="g:1",
            effect_id="effect:create-1",
        )
    )
    assert receipt.published is True
    assert receipt.action in {
        CoherenceAction.ADVANCE_GENERATION,
        CoherenceAction.INVALIDATE_AND_ADVANCE,
        CoherenceAction.INVALIDATE,
    }
    assert receipt.bindings_invalidated >= 1
    assert coh.active_generation(cid, namespace="ns-a") == "g:2"
    # Prior generation is gone; unrelated remains.
    assert coh.get(old) is None
    assert store.get(old) is None
    assert coh.get(unrelated) == b"unrelate"

    # New admission under advanced generation succeeds; stale generation blocked.
    fresh = old.with_generation("g:2")
    assert _admit(coh, fresh, b"new-data")
    assert coh.get(fresh) == b"new-data"
    with pytest.raises(CoherenceAdmissionBlocked):
        coh.require_admit(old)


def test_committed_replace_invalidates_whole_scope_only() -> None:
    store = _storage()
    coh = _coherence(store)
    cid = path_to_content_id("docs/file")
    r0 = _binding(content_id=cid, generation="g:1", offset=0, length=4)
    r1 = _binding(content_id=cid, generation="g:1", offset=4, length=4)
    other = _binding(
        content_id=path_to_content_id("docs/other"),
        generation="g:1",
        offset=0,
        length=4,
    )
    assert _admit(coh, r0, b"aaaa")
    assert _admit(coh, r1, b"bbbb")
    assert _admit(coh, other, b"cccc")

    receipt = coh.publish(
        _event(
            CoherenceMutationKind.REPLACE,
            path="docs/file",
            content_id=cid,
            generation="g:2",
            effect_id="effect:replace-1",
        )
    )
    assert receipt.published is True
    assert receipt.bindings_invalidated == 2
    assert coh.get(r0) is None
    assert coh.get(r1) is None
    assert coh.get(other) == b"cccc"


def test_committed_write_invalidates_affected_and_advances_before_admission() -> None:
    store = _storage()
    coh = _coherence(store)
    cid = path_to_content_id("docs/file")
    head = _binding(content_id=cid, generation="g:1", offset=0, length=4)
    mid = _binding(content_id=cid, generation="g:1", offset=4, length=4)
    tail = _binding(content_id=cid, generation="g:1", offset=8, length=4)
    assert _admit(coh, head, b"HEAD")
    assert _admit(coh, mid, b"MIDD")
    assert _admit(coh, tail, b"TAIL")

    # Write mid range → generation advance drops all prior-gen bindings.
    receipt = coh.publish(
        _event(
            CoherenceMutationKind.WRITE,
            path="docs/file",
            content_id=cid,
            generation="g:2",
            prior_generation="g:1",
            offset=4,
            length=4,
            effect_id="effect:write-1",
        )
    )
    assert receipt.published is True
    assert receipt.generation == "g:2"
    assert receipt.bindings_invalidated == 3
    assert coh.get(head) is None
    assert coh.get(mid) is None
    assert coh.get(tail) is None

    # Before new admission under g:2, stale get is None.
    assert not coh.may_admit(head)
    # New admission under g:2 for the written extent.
    mid_new = mid.with_generation("g:2")
    assert _admit(coh, mid_new, b"NEW!")
    assert coh.get(mid_new) == b"NEW!"
    # Stale generation still blocked.
    assert coh.get(mid) is None


def test_committed_truncate_drops_past_end_and_prior_generation() -> None:
    store = _storage()
    coh = _coherence(store)
    cid = path_to_content_id("docs/file")
    keep_range = _binding(content_id=cid, generation="g:1", offset=0, length=4)
    past = _binding(content_id=cid, generation="g:1", offset=8, length=4)
    assert _admit(coh, keep_range, b"KEEP")
    assert _admit(coh, past, b"PAST")

    receipt = coh.publish(
        _event(
            CoherenceMutationKind.TRUNCATE,
            path="docs/file",
            content_id=cid,
            generation="g:2",
            prior_generation="g:1",
            size=8,
            effect_id="effect:trunc-1",
        )
    )
    assert receipt.published is True
    assert receipt.bindings_invalidated == 2  # generation advance drops both
    assert coh.get(keep_range) is None
    assert coh.get(past) is None
    # Re-admit under new generation for kept prefix only.
    keep_new = keep_range.with_generation("g:2")
    assert _admit(coh, keep_new, b"KEEP")
    assert coh.get(keep_new) == b"KEEP"


def test_committed_unlink_invalidates_scope_and_clears_generation() -> None:
    store = _storage()
    coh = _coherence(store)
    cid = path_to_content_id("docs/file")
    binding = _binding(content_id=cid, generation="g:1", length=8)
    other = _binding(
        content_id=path_to_content_id("docs/keep"),
        generation="g:1",
        length=8,
    )
    assert _admit(coh, binding, b"doomed!!")
    assert _admit(coh, other, b"survive!")

    receipt = coh.publish(
        _event(
            CoherenceMutationKind.UNLINK,
            path="docs/file",
            content_id=cid,
            generation="g:2",
            effect_id="effect:unlink-1",
        )
    )
    assert receipt.published is True
    assert receipt.bindings_invalidated >= 1
    assert receipt.generation == ""
    assert coh.active_generation(cid, namespace="ns-a") is None
    assert coh.get(binding) is None
    assert coh.get(other) == b"survive!"


def test_committed_rename_invalidates_source_and_target() -> None:
    store = _storage()
    coh = _coherence(store)
    src = path_to_content_id("docs/old")
    dst = path_to_content_id("docs/new")
    src_b = _binding(content_id=src, generation="g:1", length=8)
    dst_b = _binding(content_id=dst, generation="g:1", length=8)
    other = _binding(
        content_id=path_to_content_id("docs/other"),
        generation="g:1",
        length=8,
    )
    assert _admit(coh, src_b, b"src-data")
    assert _admit(coh, dst_b, b"dst-data")
    assert _admit(coh, other, b"other!!!")

    receipt = coh.publish(
        _event(
            CoherenceMutationKind.RENAME,
            path="docs/old",
            content_id=src,
            target_path="docs/new",
            target_content_id=dst,
            generation="g:2",
            effect_id="effect:rename-1",
        )
    )
    assert receipt.published is True
    assert receipt.bindings_invalidated == 2
    assert coh.get(src_b) is None
    assert coh.get(dst_b) is None
    assert coh.get(other) == b"other!!!"
    # Source generation cleared; target advanced.
    assert coh.active_generation(src, namespace="ns-a") is None
    assert coh.active_generation(dst, namespace="ns-a") == "g:2"


# ---------------------------------------------------------------------------
# Recovery replay
# ---------------------------------------------------------------------------


def test_recovery_replay_advances_same_as_commit() -> None:
    store = _storage()
    coh = _coherence(store)
    cid = path_to_content_id("docs/file")
    stale = _binding(content_id=cid, generation="g:1", length=8)
    assert _admit(coh, stale, b"precrash")

    events = [
        _event(
            CoherenceMutationKind.WRITE,
            path="docs/file",
            content_id=cid,
            generation="g:2",
            prior_generation="g:1",
            offset=0,
            length=8,
            effect_id="effect:replay-write",
            source=CoherenceSource.MUTATION,  # stamped to recovery by helper
        )
    ]
    receipts = coh.publish_recovery_replay(events)
    assert len(receipts) == 1
    assert receipts[0].published is True
    assert receipts[0].source is CoherenceSource.RECOVERY_REPLAY
    assert coh.get(stale) is None
    assert coh.active_generation(cid, namespace="ns-a") == "g:2"
    assert coh.metrics().recovery_replays == 1

    fresh = stale.with_generation("g:2")
    assert _admit(coh, fresh, b"recoverd")
    assert coh.get(fresh) == b"recoverd"


def test_recovery_replay_batch_is_ordered_and_idempotent_per_effect() -> None:
    coh = _coherence()
    cid_a = path_to_content_id("a")
    cid_b = path_to_content_id("b")
    a = _binding(content_id=cid_a, generation="g:1", length=4)
    b = _binding(content_id=cid_b, generation="g:1", length=4)
    assert _admit(coh, a, b"aaaa")
    assert _admit(coh, b, b"bbbb")

    batch = [
        _event(
            CoherenceMutationKind.REPLACE,
            path="a",
            content_id=cid_a,
            generation="g:2",
            effect_id="effect:a",
        ),
        _event(
            CoherenceMutationKind.UNLINK,
            path="b",
            content_id=cid_b,
            generation="g:2",
            effect_id="effect:b",
        ),
    ]
    r1 = coh.publish_recovery_replay(batch)
    r2 = coh.publish_recovery_replay(batch)
    assert all(r.published for r in r1)
    # Idempotent: same effect_id returns prior receipt without double-counting
    # invalidations beyond the first projection.
    assert r2[0].effect_id == "effect:a"
    assert coh.get(a) is None
    assert coh.get(b) is None


# ---------------------------------------------------------------------------
# Aborted / failed effects do not publish
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "disposition",
    [
        CoherenceDisposition.ABORTED,
        CoherenceDisposition.FAILED,
        CoherenceDisposition.REJECTED,
        CoherenceDisposition.COMPENSATED,
        CoherenceDisposition.PARTIAL,
        CoherenceDisposition.CRASHED,
    ],
)
def test_non_committed_dispositions_do_not_publish(
    disposition: CoherenceDisposition,
) -> None:
    store = _storage()
    coh = _coherence(store)
    cid = path_to_content_id("docs/file")
    binding = _binding(content_id=cid, generation="g:1", length=8)
    assert _admit(coh, binding, b"live-dat")

    receipt = coh.publish(
        _event(
            CoherenceMutationKind.WRITE,
            disposition=disposition,
            path="docs/file",
            content_id=cid,
            generation="g:2",
            prior_generation="g:1",
            offset=0,
            length=8,
            effect_id=f"effect:{disposition.value}",
        )
    )
    assert receipt.published is False
    assert receipt.action is CoherenceAction.SUPPRESSED
    assert receipt.bindings_invalidated == 0
    # Live data untouched; generation not advanced.
    assert coh.get(binding) == b"live-dat"
    assert coh.active_generation(cid, namespace="ns-a") == "g:1"
    metrics = coh.metrics()
    assert metrics.suppressed >= 1
    assert metrics.publishes == 0


def test_publish_mutation_result_adapter_respects_committed_flag() -> None:
    coh = _coherence()
    cid = path_to_content_id("docs/file")
    binding = _binding(content_id=cid, generation="g:1", length=4)
    assert _admit(coh, binding, b"data")

    @dataclass
    class FakeResult:
        kind: Any
        disposition: Any
        path: str
        target_path: str = ""
        committed: bool = False
        effect_id: str = ""
        transaction_id: str = ""
        version_cid: str = ""
        content_cid: str = ""

    aborted = FakeResult(
        kind=CoherenceMutationKind.WRITE,
        disposition=CoherenceDisposition.ABORTED,
        path="docs/file",
        committed=False,
        effect_id="effect:abort",
    )
    r = coh.publish_mutation_result(
        aborted,
        namespace="ns-a",
        content_id=cid,
        generation="g:2",
        prior_generation="g:1",
        offset=0,
        length=4,
    )
    assert r.published is False
    assert coh.get(binding) == b"data"

    committed = FakeResult(
        kind=CoherenceMutationKind.WRITE,
        disposition=CoherenceDisposition.COMMITTED,
        path="docs/file",
        committed=True,
        effect_id="effect:ok",
        version_cid="v2",
    )
    r2 = coh.publish_mutation_result(
        committed,
        namespace="ns-a",
        content_id=cid,
        generation="g:2",
        prior_generation="g:1",
        offset=0,
        length=4,
    )
    assert r2.published is True
    assert coh.get(binding) is None


# ---------------------------------------------------------------------------
# Unrelated data remains; dirty clear after commit
# ---------------------------------------------------------------------------


def test_unrelated_namespace_and_content_remain() -> None:
    coh = _coherence()
    a = _binding(namespace="ns-a", content_id="cid-a", generation="g:1", length=4)
    b = _binding(namespace="ns-b", content_id="cid-a", generation="g:1", length=4)
    c = _binding(namespace="ns-a", content_id="cid-c", generation="g:1", length=4)
    assert _admit(coh, a, b"aaaa")
    assert _admit(coh, b, b"bbbb")
    assert _admit(coh, c, b"cccc")

    coh.publish(
        _event(
            CoherenceMutationKind.REPLACE,
            path="a",
            content_id="cid-a",
            namespace="ns-a",
            generation="g:2",
            effect_id="effect:ns",
        )
    )
    assert coh.get(a) is None
    assert coh.get(b) == b"bbbb"
    assert coh.get(c) == b"cccc"


def test_publish_clears_dirty_scope_before_new_admission() -> None:
    store = _storage()
    coh = _coherence(store)
    cid = path_to_content_id("docs/file")
    binding = _binding(content_id=cid, generation="g:1", length=8)
    assert _admit(coh, binding, b"committd")
    store.mark_dirty(namespace="ns-a", content_id=cid)
    assert store.is_dirty(binding)

    coh.publish(
        _event(
            CoherenceMutationKind.WRITE,
            path="docs/file",
            content_id=cid,
            generation="g:2",
            prior_generation="g:1",
            offset=0,
            length=8,
            effect_id="effect:dirty-clear",
        )
    )
    # Dirty mark cleared so post-commit admission can proceed.
    assert not store.is_dirty(namespace="ns-a", content_id=cid)
    fresh = binding.with_generation("g:2")
    assert _admit(coh, fresh, b"post!!!!")
    assert coh.get(fresh) == b"post!!!!"


def test_generation_bound_arc_optional_target() -> None:
    """Optional GenerationBoundARC advances in lockstep with range storage."""

    from ipfs_kit_py.arc_cache import CacheBinding

    store = _storage()
    arc = GenerationBoundARC(ARCConfig(capacity_bytes=4096))
    coh = CacheCoherence(store, generation_arc=arc)

    # Seed whole-object binding in GenerationBoundARC.
    whole = CacheBinding(
        content_id="cid-obj",
        version="v1",
        namespace="ns-a",
        policy="public",
        serializer="bytes@1",
        generation="g:1",
    )
    assert arc.put(whole, b"object!!")

    range_b = _binding(content_id="cid-obj", generation="g:1", length=8)
    assert _admit(coh, range_b, b"object!!")

    receipt = coh.publish(
        _event(
            CoherenceMutationKind.REPLACE,
            path="obj",
            content_id="cid-obj",
            generation="g:2",
            effect_id="effect:arc",
        )
    )
    assert receipt.published is True
    assert coh.get(range_b) is None
    # GenerationBoundARC should have advanced; old generation miss.
    assert (
        arc.get(whole, authorize=lambda _: True, consistent=lambda _: True) is None
    )


# ---------------------------------------------------------------------------
# Fence ordering: invalidate before new admission
# ---------------------------------------------------------------------------


def test_publish_completes_invalidation_before_new_admission() -> None:
    """Committed publish drops stale bindings before a successor may admit."""

    store = _storage()
    coh = _coherence(store)
    cid = path_to_content_id("docs/file")
    old = _binding(content_id=cid, generation="g:1", length=8)
    assert _admit(coh, old, b"stale!!!")
    assert coh.get(old) == b"stale!!!"

    # Instrument invalidation to prove it runs while the publish fence is held
    # and before the receipt is returned to the caller.
    original = coh._invalidate_affected_locked
    observed: dict[str, Any] = {}

    def instrumented(event, *, generation):
        observed["fenced_during_invalidate"] = coh.is_fenced(
            cid, namespace="ns-a"
        )
        observed["stale_present_before"] = old.cache_key in {
            b.cache_key for b in coh.tracked_bindings(content_id=cid)
        }
        result = original(event, generation=generation)
        observed["stale_present_after"] = old.cache_key in {
            b.cache_key for b in coh.tracked_bindings(content_id=cid)
        }
        observed["active_during"] = coh.active_generation(cid, namespace="ns-a")
        return result

    coh._invalidate_affected_locked = instrumented  # type: ignore[method-assign]

    receipt = coh.publish(
        _event(
            CoherenceMutationKind.WRITE,
            path="docs/file",
            content_id=cid,
            generation="g:2",
            prior_generation="g:1",
            offset=0,
            length=8,
            effect_id="effect:fence",
        )
    )
    assert receipt.published is True
    assert observed["fenced_during_invalidate"] is True
    assert observed["stale_present_before"] is True
    assert observed["stale_present_after"] is False
    assert observed["active_during"] == "g:2"
    # Fence released after publish returns.
    assert not coh.is_fenced(cid, namespace="ns-a")
    # Stale generation cannot be read or re-admitted; new generation can.
    assert coh.get(old) is None
    assert not coh.may_admit(old)
    assert coh.may_admit(old.with_generation("g:2"))
    assert _admit(coh, old.with_generation("g:2"), b"fresh!!!")
    assert coh.get(old.with_generation("g:2")) == b"fresh!!!"


# ---------------------------------------------------------------------------
# Randomized interleavings: no stale committed byte
# ---------------------------------------------------------------------------


def test_randomized_interleavings_return_no_stale_committed_byte() -> None:
    """Concurrent admits and commits never surface a prior-generation payload."""

    store = _storage()
    coh = _coherence(store)
    cid = path_to_content_id("docs/file")
    namespace = "ns-a"
    rng = random.Random(404)
    generations = [f"g:{i}" for i in range(1, 9)]
    errors: list[str] = []
    observed: list[tuple[str, bytes]] = []
    commit_lock = Lock()
    committed_index = 0

    def committer(gen_index: int) -> None:
        nonlocal committed_index
        # The product accepts opaque generation tokens, but this fixture models
        # one ordered mutation stream.  Catch up under one sequencer so the
        # active generation cannot regress or exhibit an ABA transition.
        with commit_lock:
            while committed_index < gen_index:
                next_index = committed_index + 1
                gen = generations[next_index]
                prior = generations[next_index - 1]
                coh.publish(
                    _event(
                        CoherenceMutationKind.WRITE,
                        path="docs/file",
                        content_id=cid,
                        namespace=namespace,
                        generation=gen,
                        prior_generation=prior,
                        offset=0,
                        length=8,
                        effect_id=f"effect:rand-{gen}",
                        transaction_id=f"txn:rand-{gen}",
                    )
                )
                committed_index = next_index

    def reader_writer(worker_id: int) -> None:
        for step in range(40):
            # Snapshot active generation under the coherence lock via public API.
            active = coh.active_generation(cid, namespace=namespace)
            # Pick a generation: sometimes current, sometimes deliberately stale.
            if active is None:
                gen = generations[0]
            elif rng.random() < 0.7:
                gen = active
            else:
                # Stale: an earlier generation if possible.
                idx = generations.index(active) if active in generations else 0
                gen = generations[max(0, idx - 1)]

            binding = _binding(
                namespace=namespace,
                content_id=cid,
                generation=gen,
                length=8,
            )
            # A binding is one ARC key, so concurrent puts may legally update
            # it.  Use one exact payload per generation to keep the subsequent
            # read an assertion about stale bytes, not writer ownership.
            payload = f"{gen}:data".encode("ascii")[:8].ljust(8, b"0")

            if rng.random() < 0.5:
                # Attempt admit.
                try:
                    ok = coh.put_committed(binding, payload)
                except CoherenceAdmissionBlocked:
                    ok = False
                if ok:
                    got = coh.get(binding)
                    if got is not None and got != payload:
                        errors.append(
                            f"admit payload mismatch worker={worker_id} "
                            f"gen={gen} got={got!r}"
                        )
            else:
                active_before = coh.active_generation(cid, namespace=namespace)
                got = coh.get(binding)
                active_after = coh.active_generation(cid, namespace=namespace)
                if got is not None:
                    observed.append((gen, got))
                    # A generation change concurrent with get means the hit
                    # may have linearized before that commit.  When both
                    # snapshots agree, a different generation is genuinely
                    # stale for the whole observation window.
                    if (
                        active_before is not None
                        and active_before == active_after
                        and gen != active_after
                    ):
                        errors.append(
                            f"stale hit worker={worker_id} gen={gen} "
                            f"active={active_after} payload={got!r}"
                        )

            # Occasional commit from readers too (interleaved).
            if step % 11 == 0 and worker_id == 0:
                idx = generations.index(active) + 1 if active in generations else 1
                if idx < len(generations):
                    committer(idx)

    # Seed generation g:1.
    seed = _binding(namespace=namespace, content_id=cid, generation="g:1", length=8)
    assert _admit(coh, seed, b"g:1:seed")

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(reader_writer, i) for i in range(6)]
        # Parallel committers advancing generations.
        for gi in range(1, len(generations)):
            futures.append(pool.submit(committer, gi))
        for fut in as_completed(futures):
            fut.result()

    assert not errors, f"stale or corrupt observations: {errors[:5]}"
    # Final active generation is the latest committed.
    final = coh.active_generation(cid, namespace=namespace)
    assert final is not None
    # No live tracked binding under a generation other than final.
    for binding in coh.tracked_bindings(namespace=namespace, content_id=cid):
        assert binding.generation == final
        got = coh.get(binding)
        if got is not None:
            assert binding.generation == final


def test_event_validation_rejects_bad_rename() -> None:
    with pytest.raises(CoherenceValidationError):
        CoherenceEvent(
            kind=CoherenceMutationKind.RENAME,
            disposition=CoherenceDisposition.COMMITTED,
            path="docs/a",
            content_id="cid-a",
            # missing target_path
        )


def test_event_from_mapping_roundtrip() -> None:
    event = _event(CoherenceMutationKind.TRUNCATE, size=10, path="p", content_id="cid-p")
    restored = CoherenceEvent.from_mapping(event.to_dict())
    assert restored.kind is CoherenceMutationKind.TRUNCATE
    assert restored.size == 10
    assert restored.content_id == "cid-p"


def test_metrics_snapshot_is_independent() -> None:
    coh = _coherence()
    snap = coh.metrics()
    coh.publish(
        _event(
            CoherenceMutationKind.CREATE,
            path="x",
            content_id="cid-x",
            generation="g:1",
            effect_id="effect:metrics",
        )
    )
    assert snap.publishes == 0
    assert coh.metrics().publishes == 1


def test_assert_invariants_holds_after_ops() -> None:
    coh = _coherence()
    cid = path_to_content_id("docs/file")
    b = _binding(content_id=cid, generation="g:1", length=4)
    assert _admit(coh, b, b"zzzz")
    coh.publish(
        _event(
            CoherenceMutationKind.REPLACE,
            path="docs/file",
            content_id=cid,
            generation="g:2",
            effect_id="effect:inv",
        )
    )
    coh.assert_invariants()
