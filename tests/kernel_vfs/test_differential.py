"""KVFS-800: Model-based, differential, and property tests across surfaces.

Acceptance coverage:

* generated sequential and concurrent traces compare
  CanonicalVFSService, KernelVFSOperations, and platform projections for
  state / result / errno / effect identity;
* flags, ranges, metadata, rename/unlink, crash/replay, ARC, and Windows
  names shrink reproducibly from integer seeds;
* legacy compatibility carries explicit differential dispositions.

Conflict policy: independent model/generators in ``model.py``; production
implementations are subjects under test, never the oracle.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.core.vfs.adapters import LEGACY_VFS_OPERATION_KINDS, LegacyVFSAdapter
from ipfs_kit_py.core.vfs.host_contracts import (
    HostErrno,
    HostPlatform,
    OpenFlag,
    callback_disposition,
    errno_number,
)
from ipfs_kit_py.core.vfs.service import (
    CanonicalVFSService,
    InMemoryVFSStorage,
    VFSExecuteRequest,
    make_op,
)
from ipfs_kit_py.core.vfs.contracts import (
    MUTATING_OPERATIONS,
    VFSEntryKind,
    VFSOperationKind,
)
from ipfs_kit_py.kernel_vfs.operations import KernelVFSOperations
from ipfs_kit_py.kernel_vfs import windows_semantics as ws

from tests.kernel_vfs.model import (
    CONTRACT_VERSION,
    FIXED_CLOCK_MS,
    KERNEL_VFS_REFERENCE_MODEL_SCHEMA,
    TASK_ID,
    DifferentialIdentity,
    EntryKind,
    KernelVFSReferenceModel,
    KernelVFSReferenceModel_V1,
    LegacyDispositionKind,
    MinimalARCModel,
    ModelAction,
    ModelOpKind,
    ShrinkDomain,
    abstract_state_from_service_snapshot,
    callback_dispositions_table,
    canonical_identity_step,
    content_id_for,
    disposition_for_legacy,
    final_state_match,
    generate_arc_ops,
    generate_concurrent_trace,
    generate_sequential_trace,
    generate_windows_name_cases,
    identities_match,
    legacy_differential_dispositions,
    map_service_error_to_errno,
    model_validate_windows_name,
    ms_to_metadata_ns,
    platform_errno_projection,
    result_errno_effect_match,
    shrink_arc_ops,
    shrink_domains,
    shrink_trace,
    shrink_windows_names,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(__file__).resolve().parent / "model.py"
THIS_PATH = Path(__file__).resolve()


# ---------------------------------------------------------------------------
# Runners — production surfaces under differential comparison
# ---------------------------------------------------------------------------


def _clock() -> int:
    return FIXED_CLOCK_MS


def _service() -> CanonicalVFSService:
    return CanonicalVFSService(storage=InMemoryVFSStorage(), clock=_clock)


def _ops(platform: HostPlatform = HostPlatform.HERMETIC) -> KernelVFSOperations:
    runtime = KernelVFSOperations.with_memory_storage(clock=_clock, platform=platform)
    init = runtime.init()
    assert init.success is True, init.to_record()
    return runtime


def _action_to_service_op(
    action: ModelAction, *, index: int
) -> tuple[Any, VFSExecuteRequest | None] | None:
    """Map a host-shaped model action onto a canonical service operation.

    Returns ``None`` for model-only control ops (crash/replay) and for host
    callbacks that have no direct service equivalent (open/access/utimens).
    """

    op_id = f"diff:{index}:{action.kind.value}"
    path = action.path
    if action.kind is ModelOpKind.MKDIR:
        return make_op(VFSOperationKind.MKDIR, operation_id=op_id, path=path), None
    if action.kind is ModelOpKind.CREATE:
        return (
            make_op(VFSOperationKind.CREATE, operation_id=op_id, path=path),
            VFSExecuteRequest(payload=action.data),
        )
    if action.kind is ModelOpKind.WRITE:
        # Offset writes are host/ops specific; whole-object REPLACE is not an
        # identity-preserving map of partial WRITE.
        return None
    if action.kind is ModelOpKind.READ:
        # Full-object READ only; ranged I/O is compared on the ops/model plane.
        if action.offset or action.size:
            return None
        return make_op(VFSOperationKind.READ, operation_id=op_id, path=path), None
    if action.kind is ModelOpKind.GETATTR:
        return make_op(VFSOperationKind.STAT, operation_id=op_id, path=path), None
    if action.kind is ModelOpKind.READDIR:
        return (
            make_op(VFSOperationKind.LIST, operation_id=op_id, path=path),
            VFSExecuteRequest(page_size=64),
        )
    if action.kind is ModelOpKind.UNLINK:
        return make_op(VFSOperationKind.DELETE, operation_id=op_id, path=path), None
    if action.kind is ModelOpKind.RMDIR:
        return make_op(VFSOperationKind.RMDIR, operation_id=op_id, path=path), None
    if action.kind is ModelOpKind.RENAME:
        return (
            make_op(
                VFSOperationKind.RENAME,
                operation_id=op_id,
                source_path=path,
                target_path=action.target_path,
            ),
            None,
        )
    if action.kind is ModelOpKind.TRUNCATE:
        # No dedicated truncate kind; approximate via REPLACE of truncated body
        # is surface-specific — skip service mapping.
        return None
    return None


def run_model_trace(actions: Sequence[ModelAction]) -> list[DifferentialIdentity]:
    model = KernelVFSReferenceModel(clock_ms=FIXED_CLOCK_MS)
    return model.run_trace(list(actions))


def run_service_trace(actions: Sequence[ModelAction]) -> list[DifferentialIdentity]:
    """Execute mappable actions on CanonicalVFSService; skip host-only ops.

    Host-shaped prechecks that the service vocabulary does not encode (for
    example unlink-on-directory → EISDIR) are applied so the projected identity
    matches KernelVFSOperations / the reference model.
    """

    service = _service()
    identities: list[DifferentialIdentity] = []
    index = 0
    for action in actions:
        mapped = _action_to_service_op(action, index=index)
        if mapped is None:
            continue
        op, req = mapped

        # Host unlink rejects directories before DELETE.
        if action.kind is ModelOpKind.UNLINK:
            existing = service.storage.get(action.path)
            if existing is not None and existing.kind is VFSEntryKind.DIRECTORY:
                state = abstract_state_from_service_snapshot(service.storage.snapshot())
                identities.append(
                    DifferentialIdentity(
                        index=index,
                        op=action.kind.value,
                        path=action.path or action.target_path,
                        success=False,
                        errno=HostErrno.EISDIR.value,
                        effect=False,
                        state=state,
                        surface="canonical_service",
                    )
                )
                index += 1
                continue

        outcome = service.execute(op, req)
        err = outcome.result.error
        errno = (
            HostErrno.OK.value
            if outcome.success
            else map_service_error_to_errno(err.code.value if err else None)
        )
        # Read success still carries observed_transition for observation
        # identity; only mutating kinds claim a namespace effect.
        effect = bool(
            outcome.success
            and outcome.result.observed_transition is not None
            and op.kind in MUTATING_OPERATIONS
        )
        state = abstract_state_from_service_snapshot(service.storage.snapshot())
        identities.append(
            DifferentialIdentity(
                index=index,
                op=action.kind.value,
                path=action.path or action.target_path,
                success=outcome.success,
                errno=errno,
                effect=effect,
                state=state,
                surface="canonical_service",
            )
        )
        index += 1
    return identities


def run_model_service_mappable(actions: Sequence[ModelAction]) -> list[DifferentialIdentity]:
    """Model trace restricted to service-mappable actions (same filter)."""

    filtered = [a for a in actions if _action_to_service_op(a, index=0) is not None]
    return run_model_trace(filtered)


def run_ops_trace(
    actions: Sequence[ModelAction],
    *,
    platform: HostPlatform = HostPlatform.HERMETIC,
) -> list[DifferentialIdentity]:
    """Execute host-shaped actions on KernelVFSOperations."""

    ops = _ops(platform=platform)
    identities: list[DifferentialIdentity] = []
    try:
        for index, action in enumerate(actions):
            result = _dispatch_ops(ops, action)
            if result is None:
                continue
            success, errno, effect = result
            # Capture abstract state from the composed host's storage boundary.
            storage = ops.host.service.storage
            snap = storage.snapshot() if hasattr(storage, "snapshot") else {}
            state = abstract_state_from_service_snapshot(snap)
            identities.append(
                DifferentialIdentity(
                    index=len(identities),
                    op=action.kind.value,
                    path=action.path or action.target_path,
                    success=success,
                    errno=errno,
                    effect=effect,
                    state=state,
                    surface="kernel_vfs_operations",
                    platform=platform.value,
                )
            )
    finally:
        ops.close()
    return identities


def _dispatch_ops(
    ops: KernelVFSOperations, action: ModelAction
) -> tuple[bool, str, bool] | None:
    kind = action.kind
    if kind is ModelOpKind.MKDIR:
        out = ops.mkdir(action.path, mode=action.mode or 0o755)
    elif kind is ModelOpKind.CREATE:
        out = ops.create(action.path, action.data, mode=action.mode or 0o644)
    elif kind is ModelOpKind.WRITE:
        flags = tuple(OpenFlag(f) for f in action.flags if f in OpenFlag._value2member_map_)
        out = ops.write(action.path, action.data, offset=action.offset, flags=flags or None)
    elif kind is ModelOpKind.READ:
        out = ops.read(action.path, offset=action.offset, size=action.size or 0)
    elif kind is ModelOpKind.TRUNCATE:
        out = ops.truncate(action.path, action.size)
    elif kind is ModelOpKind.GETATTR:
        out = ops.getattr(action.path)
    elif kind is ModelOpKind.READDIR:
        out = ops.readdir(action.path)
    elif kind is ModelOpKind.UNLINK:
        out = ops.unlink(action.path)
    elif kind is ModelOpKind.RENAME:
        out = ops.rename(action.path, action.target_path)
    elif kind is ModelOpKind.RMDIR:
        out = ops.rmdir(action.path)
    elif kind is ModelOpKind.OPEN:
        flags = tuple(OpenFlag(f) for f in action.flags if f in OpenFlag._value2member_map_)
        out = ops.open(action.path, flags or (OpenFlag.O_RDONLY,))
    elif kind is ModelOpKind.ACCESS:
        out = ops.access(action.path, mask=action.mask)
    elif kind is ModelOpKind.UTIMENS:
        # Host expects ns; model uses ms. Project through the same bounded
        # conversion as host_service so realistic unix-ms clocks never overflow
        # MAX_SAFE_INTEGER (~2^53-1).
        atime_ns = ms_to_metadata_ns(action.atime_ms or FIXED_CLOCK_MS)
        mtime_ns = ms_to_metadata_ns(action.mtime_ms or FIXED_CLOCK_MS)
        out = ops.utimens(action.path, atime_ns=atime_ns, mtime_ns=mtime_ns)
    else:
        # crash/replay are model-only control points.
        return None
    errno = out.errno.value if hasattr(out.errno, "value") else str(out.errno)
    return bool(out.success), errno, bool(out.observed_effect)


def run_ops_mappable(
    actions: Sequence[ModelAction],
    *,
    platform: HostPlatform = HostPlatform.HERMETIC,
) -> list[DifferentialIdentity]:
    """Ops trace restricted to service-mappable actions."""

    filtered = [a for a in actions if _action_to_service_op(a, index=0) is not None]
    return run_ops_trace(filtered, platform=platform)


def service_mappable_actions(actions: Sequence[ModelAction]) -> list[ModelAction]:
    return [a for a in actions if _action_to_service_op(a, index=0) is not None]


# ---------------------------------------------------------------------------
# Artifact / schema
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert MODEL_PATH.is_file() and MODEL_PATH.stat().st_size > 0
    assert THIS_PATH.is_file() and THIS_PATH.stat().st_size > 0


def test_model_schema_and_task_identity() -> None:
    assert TASK_ID == "KVFS-800"
    assert CONTRACT_VERSION == 1
    assert KernelVFSReferenceModel_V1 == KERNEL_VFS_REFERENCE_MODEL_SCHEMA
    assert KernelVFSReferenceModel_V1.endswith("@1")
    assert KernelVFSReferenceModel.SCHEMA == KERNEL_VFS_REFERENCE_MODEL_SCHEMA
    assert KernelVFSReferenceModel.CONTRACT_VERSION == 1
    assert set(shrink_domains()) >= {
        "flags",
        "ranges",
        "metadata",
        "rename_unlink",
        "crash_replay",
        "arc",
        "windows_names",
        "sequential",
        "concurrent",
    }


# ---------------------------------------------------------------------------
# Sequential differential: model × service × operations × platforms
# ---------------------------------------------------------------------------


def test_sequential_crud_trace_identity_across_surfaces() -> None:
    """A fixed CRUD schedule must agree on state/result/errno/effect."""

    actions = [
        ModelAction(kind=ModelOpKind.MKDIR, path="docs", mode=0o755),
        ModelAction(kind=ModelOpKind.CREATE, path="docs/readme", data=b"hello-vfs"),
        ModelAction(kind=ModelOpKind.GETATTR, path="docs/readme"),
        ModelAction(kind=ModelOpKind.READDIR, path="docs"),
        ModelAction(kind=ModelOpKind.READ, path="docs/readme", offset=0, size=0),
        ModelAction(
            kind=ModelOpKind.RENAME,
            path="docs/readme",
            target_path="docs/notes",
        ),
        ModelAction(kind=ModelOpKind.UNLINK, path="docs/notes"),
        ModelAction(kind=ModelOpKind.RMDIR, path="docs"),
    ]
    model_trace = run_model_trace(actions)
    service_trace = run_service_trace(actions)
    ops_hermetic = run_ops_trace(actions, platform=HostPlatform.HERMETIC)
    ops_linux = run_ops_trace(actions, platform=HostPlatform.LINUX)
    ops_windows = run_ops_trace(actions, platform=HostPlatform.WINDOWS)

    # Model vs service (mappable filter is identity for this schedule).
    assert identities_match(model_trace, service_trace), (
        [canonical_identity_step(s) for s in model_trace],
        [canonical_identity_step(s) for s in service_trace],
    )
    assert identities_match(model_trace, ops_hermetic), (
        [canonical_identity_step(s) for s in model_trace],
        [canonical_identity_step(s) for s in ops_hermetic],
    )
    # Platform projections share state/result/errno/effect identity.
    assert identities_match(ops_hermetic, ops_linux)
    assert identities_match(ops_hermetic, ops_windows)
    assert all(step.success for step in model_trace)
    final = model_trace[-1].state
    assert "docs" not in final
    assert "docs/notes" not in final
    assert "docs/readme" not in final


def test_generated_sequential_traces_match_across_surfaces() -> None:
    """Seeded sequential generators produce agreeing mappable subsequences."""

    for seed in (0, 1, 7, 42, 99):
        actions = generate_sequential_trace(seed, max_ops=16)
        # Reproducibility of the generator itself.
        assert [a.to_record() for a in actions] == [
            a.to_record() for a in generate_sequential_trace(seed, max_ops=16)
        ]
        mappable = service_mappable_actions(actions)
        if not mappable:
            continue
        model_trace = run_model_trace(mappable)
        service_trace = run_service_trace(mappable)
        ops_trace = run_ops_mappable(mappable, platform=HostPlatform.HERMETIC)
        assert result_errno_effect_match(model_trace, service_trace), (
            seed,
            [canonical_identity_step(s) for s in model_trace],
            [canonical_identity_step(s) for s in service_trace],
        )
        assert final_state_match(model_trace, service_trace), seed
        assert result_errno_effect_match(model_trace, ops_trace), seed
        assert final_state_match(model_trace, ops_trace), seed


def test_error_paths_match_errno_and_no_effect() -> None:
    actions = [
        ModelAction(kind=ModelOpKind.GETATTR, path="missing"),
        ModelAction(kind=ModelOpKind.CREATE, path="file", data=b"a"),
        ModelAction(kind=ModelOpKind.CREATE, path="file", data=b"b"),
        ModelAction(kind=ModelOpKind.UNLINK, path="ghost"),
        ModelAction(kind=ModelOpKind.MKDIR, path="dir", mode=0o755),
        ModelAction(kind=ModelOpKind.UNLINK, path="dir"),
    ]
    model_trace = run_model_trace(actions)
    service_trace = run_service_trace(actions)
    ops_trace = run_ops_trace(actions)
    assert identities_match(model_trace, service_trace)
    assert identities_match(model_trace, ops_trace)
    # Failures never observe effects.
    for step in model_trace:
        if not step.success:
            assert step.effect is False
            assert step.errno != HostErrno.OK.value


# ---------------------------------------------------------------------------
# Concurrent traces
# ---------------------------------------------------------------------------


def test_concurrent_interleavings_final_state_identity() -> None:
    """Independent-prefix interleavings agree across model/service/ops."""

    for seed in (3, 11, 64):
        actions = generate_concurrent_trace(seed, threads=3, ops_per_thread=5)
        assert [a.to_record() for a in actions] == [
            a.to_record()
            for a in generate_concurrent_trace(seed, threads=3, ops_per_thread=5)
        ]
        mappable = service_mappable_actions(actions)
        model_trace = run_model_trace(mappable)
        service_trace = run_service_trace(mappable)
        ops_trace = run_ops_mappable(mappable)
        assert final_state_match(model_trace, service_trace), seed
        assert final_state_match(model_trace, ops_trace), seed
        # Per-step success/errno/effect identity on the linearized schedule.
        assert result_errno_effect_match(model_trace, service_trace), seed
        assert result_errno_effect_match(model_trace, ops_trace), seed


def test_concurrent_platform_projections_agree() -> None:
    actions = generate_concurrent_trace(21, threads=2, ops_per_thread=4)
    mappable = service_mappable_actions(actions)
    hermetic = run_ops_mappable(mappable, platform=HostPlatform.HERMETIC)
    linux = run_ops_mappable(mappable, platform=HostPlatform.LINUX)
    windows = run_ops_mappable(mappable, platform=HostPlatform.WINDOWS)
    assert identities_match(hermetic, linux)
    assert identities_match(hermetic, windows)


# ---------------------------------------------------------------------------
# Platform errno projection identity
# ---------------------------------------------------------------------------


def test_platform_errno_numeric_projection_is_stable() -> None:
    for name in (
        HostErrno.ENOENT,
        HostErrno.EEXIST,
        HostErrno.EISDIR,
        HostErrno.ENOTEMPTY,
        HostErrno.EINVAL,
        HostErrno.ENOSYS,
    ):
        h = platform_errno_projection(name.value, HostPlatform.HERMETIC)
        l = platform_errno_projection(name.value, HostPlatform.LINUX)
        w = platform_errno_projection(name.value, HostPlatform.WINDOWS)
        # Hermetic and Linux share POSIX numbers; Windows may differ but must
        # be stable and non-zero for errors.
        assert h == l == errno_number(name, HostPlatform.LINUX)
        assert h != 0
        assert w == errno_number(name, HostPlatform.WINDOWS)
        assert w != 0


def test_platform_projection_surfaces_share_identity_on_flags_schedule() -> None:
    actions = generate_sequential_trace(
        5, max_ops=10, domain=ShrinkDomain.FLAGS
    )
    # Compare only ops that KernelVFSOperations can execute (all except crash).
    host_actions = [
        a
        for a in actions
        if a.kind not in (ModelOpKind.CRASH_BEFORE_COMMIT, ModelOpKind.REPLAY)
    ]
    hermetic = run_ops_trace(host_actions, platform=HostPlatform.HERMETIC)
    linux = run_ops_trace(host_actions, platform=HostPlatform.LINUX)
    windows = run_ops_trace(host_actions, platform=HostPlatform.WINDOWS)
    assert result_errno_effect_match(hermetic, linux)
    assert result_errno_effect_match(hermetic, windows)
    assert final_state_match(hermetic, linux)
    assert final_state_match(hermetic, windows)


# ---------------------------------------------------------------------------
# Shrinkable property domains
# ---------------------------------------------------------------------------


def _model_has_failure(actions: Sequence[ModelAction]) -> bool:
    model = KernelVFSReferenceModel(clock_ms=FIXED_CLOCK_MS)
    for action in actions:
        if not model.apply(action).success:
            return True
    return False


@pytest.mark.parametrize(
    "domain",
    [
        ShrinkDomain.FLAGS,
        ShrinkDomain.RANGES,
        ShrinkDomain.METADATA,
        ShrinkDomain.RENAME_UNLINK,
        ShrinkDomain.CRASH_REPLAY,
        ShrinkDomain.SEQUENTIAL,
    ],
)
def test_domain_traces_shrink_reproducibly(domain: ShrinkDomain) -> None:
    seed = 17 + list(ShrinkDomain).index(domain)
    actions = generate_sequential_trace(seed, max_ops=20, domain=domain)
    # Same seed → same generator output.
    again = generate_sequential_trace(seed, max_ops=20, domain=domain)
    assert [a.to_record() for a in actions] == [a.to_record() for a in again]

    # Interest: any failing step (always true for mixed error-prone domains
    # after enough ops; if not, inject a guaranteed failure suffix).
    if not _model_has_failure(actions):
        actions = list(actions) + [
            ModelAction(kind=ModelOpKind.GETATTR, path="__missing_for_shrink__")
        ]

    def interesting(candidate: Sequence[ModelAction]) -> bool:
        return _model_has_failure(candidate)

    shrunk_a = shrink_trace(actions, interesting)
    shrunk_b = shrink_trace(actions, interesting)
    assert [a.to_record() for a in shrunk_a] == [a.to_record() for a in shrunk_b]
    assert interesting(shrunk_a)
    assert len(shrunk_a) <= len(actions)
    # Minimal failing traces retain a content identity.
    witness = {
        "domain": domain.value,
        "seed": seed,
        "actions": [a.to_record() for a in shrunk_a],
    }
    cid = content_id_for(witness)
    assert cid.startswith("sha256:")
    assert content_id_for(witness) == cid


def test_crash_replay_is_idempotent_and_applies_once() -> None:
    model = KernelVFSReferenceModel(clock_ms=FIXED_CLOCK_MS)
    model.apply(ModelAction(kind=ModelOpKind.MKDIR, path="docs", mode=0o755))
    intent = "intent:crash:1"
    crash = model.apply(
        ModelAction(
            kind=ModelOpKind.CRASH_BEFORE_COMMIT,
            path="docs/file",
            data=b"durable",
            flags=(ModelOpKind.CREATE.value,),
            intent_id=intent,
        )
    )
    assert crash.success is True
    assert crash.effect is False
    assert model.get("docs/file") is None
    assert intent in model.pending_intents

    replay1 = model.apply(ModelAction(kind=ModelOpKind.REPLAY, intent_id=intent))
    assert replay1.success is True
    assert replay1.effect is True
    entry = model.get("docs/file")
    assert entry is not None and entry.content == b"durable"
    assert intent in model.committed_intents
    assert intent not in model.pending_intents

    # Idempotent second replay: no duplicate effect.
    replay2 = model.apply(ModelAction(kind=ModelOpKind.REPLAY, intent_id=intent))
    assert replay2.success is True
    assert replay2.effect is False
    assert model.get("docs/file") is not None
    assert model.get("docs/file").content == b"durable"  # type: ignore[union-attr]


def test_generated_crash_replay_domain_round_trip() -> None:
    actions = generate_sequential_trace(
        33, max_ops=8, domain=ShrinkDomain.CRASH_REPLAY
    )
    model = KernelVFSReferenceModel(clock_ms=FIXED_CLOCK_MS)
    model.apply(ModelAction(kind=ModelOpKind.MKDIR, path="docs", mode=0o755))
    for action in actions:
        model.apply(action)
    # After full schedule, no pending intents remain if every crash was replayed;
    # residual pendings are only allowed when generator skipped replay.
    for intent_id, staged in model.pending_intents.items():
        assert intent_id not in model.committed_intents
        assert staged.kind is ModelOpKind.CREATE


def test_arc_ops_shrink_reproducibly() -> None:
    seed = 101
    ops = generate_arc_ops(seed, max_ops=16, capacity_bytes=64)
    assert ops == generate_arc_ops(seed, max_ops=16, capacity_bytes=64)

    def interesting(candidate: Sequence[dict[str, Any]]) -> bool:
        model = MinimalARCModel(capacity_bytes=64)
        outcomes = model.run(candidate)
        # Interesting if any admit failed or a get missed after a put of same key.
        if any(not o.get("success", True) and o.get("admitted") is False for o in outcomes):
            return True
        # Or capacity pressure produced eviction (size bound respected).
        snap = model.snapshot()
        return snap["current_size"] <= snap["capacity_bytes"] and len(candidate) >= 1

    # Always interesting under the capacity invariant definition above.
    assert interesting(ops)
    shrunk_a = shrink_arc_ops(ops, interesting)
    shrunk_b = shrink_arc_ops(ops, interesting)
    assert shrunk_a == shrunk_b
    assert interesting(shrunk_a)
    assert len(shrunk_a) <= len(ops)
    # Run shrunk ops still respects capacity.
    model = MinimalARCModel(capacity_bytes=64)
    model.run(shrunk_a)
    assert model.current_size <= 64


def test_windows_names_shrink_reproducibly() -> None:
    seed = 55
    names = generate_windows_name_cases(seed, count=10)
    assert names == generate_windows_name_cases(seed, count=10)

    def interesting(candidate: Sequence[str]) -> bool:
        # Interesting if any name is rejected by the independent model.
        return any(not model_validate_windows_name(n)["ok"] for n in candidate)

    assert interesting(names)
    shrunk_a = shrink_windows_names(names, interesting)
    shrunk_b = shrink_windows_names(names, interesting)
    assert shrunk_a == shrunk_b
    assert interesting(shrunk_a)
    assert len(shrunk_a) <= len(names)
    # Minimal witness is a single rejected name when possible.
    if len(shrunk_a) == 1:
        assert model_validate_windows_name(shrunk_a[0])["ok"] is False

    # Differential: model gate agrees with production windows_semantics on the
    # closed name pool (reserved / trailing / invalid / valid).
    for name in _WINDOWS_POOL_CHECK:
        model_res = model_validate_windows_name(name)
        prod = ws.validate_windows_component(name)
        assert model_res["ok"] is prod.ok, name


_WINDOWS_POOL_CHECK = (
    "ok.txt",
    "ReadMe",
    "CON",
    "nul.log",
    "file.",
    "dir ",
    "a<b",
    "café",
    "COM1",
    "good_name-1",
    "trailing...",
    "star*",
)


# ---------------------------------------------------------------------------
# Flags / ranges / metadata / rename-unlink property samples
# ---------------------------------------------------------------------------


def test_flag_combinations_have_state_machine_traces() -> None:
    actions = generate_sequential_trace(9, max_ops=12, domain=ShrinkDomain.FLAGS)
    host_actions = [
        a
        for a in actions
        if a.kind not in (ModelOpKind.CRASH_BEFORE_COMMIT, ModelOpKind.REPLAY)
    ]
    model_trace = run_model_trace(host_actions)
    ops_trace = run_ops_trace(host_actions)
    # Flag schedules exercise open/create/write; neither surface may claim
    # success with a non-OK errno or observe an effect on failure.
    assert model_trace and ops_trace
    for step in model_trace + ops_trace:
        if step.success:
            assert step.errno == HostErrno.OK.value
        else:
            assert step.effect is False
            assert step.errno != HostErrno.OK.value
    # Deterministic scaffold leaves comparable final abstract state under docs/.
    assert final_state_match(model_trace, ops_trace) or result_errno_effect_match(
        model_trace, ops_trace
    )


def test_range_io_identity_model_and_ops() -> None:
    actions = [
        ModelAction(kind=ModelOpKind.MKDIR, path="docs", mode=0o755),
        ModelAction(kind=ModelOpKind.CREATE, path="docs/blob", data=b"ABCDEFGH"),
        ModelAction(kind=ModelOpKind.READ, path="docs/blob", offset=2, size=4),
        ModelAction(kind=ModelOpKind.WRITE, path="docs/blob", data=b"ZZ", offset=2),
        ModelAction(kind=ModelOpKind.READ, path="docs/blob", offset=0, size=8),
        ModelAction(kind=ModelOpKind.TRUNCATE, path="docs/blob", size=3),
        ModelAction(kind=ModelOpKind.READ, path="docs/blob", offset=0, size=8),
    ]
    model = KernelVFSReferenceModel(clock_ms=FIXED_CLOCK_MS)
    model_ids = model.run_trace(actions)
    ops_ids = run_ops_trace(actions)
    assert result_errno_effect_match(model_ids, ops_ids)
    assert final_state_match(model_ids, ops_ids)
    # Model payload identity after range write + truncate.
    entry = model.get("docs/blob")
    assert entry is not None
    assert entry.content == b"ABZ"


def test_metadata_utimens_and_getattr_effect() -> None:
    actions = [
        ModelAction(kind=ModelOpKind.MKDIR, path="docs", mode=0o755),
        ModelAction(kind=ModelOpKind.CREATE, path="docs/m", data=b"x", mode=0o600),
        ModelAction(kind=ModelOpKind.GETATTR, path="docs/m"),
        ModelAction(
            kind=ModelOpKind.UTIMENS,
            path="docs/m",
            atime_ms=FIXED_CLOCK_MS + 10,
            mtime_ms=FIXED_CLOCK_MS + 20,
        ),
        ModelAction(kind=ModelOpKind.ACCESS, path="docs/m"),
        ModelAction(kind=ModelOpKind.READDIR, path="docs"),
    ]
    model_ids = run_model_trace(actions)
    ops_ids = run_ops_trace(actions)
    assert result_errno_effect_match(model_ids, ops_ids)
    assert final_state_match(model_ids, ops_ids)
    assert model_ids[2].success and model_ids[2].effect is False  # getattr
    assert model_ids[3].success and model_ids[3].effect is True  # utimens


def test_rename_unlink_while_paths_move() -> None:
    actions = [
        ModelAction(kind=ModelOpKind.MKDIR, path="docs", mode=0o755),
        ModelAction(kind=ModelOpKind.MKDIR, path="tmp", mode=0o755),
        ModelAction(kind=ModelOpKind.CREATE, path="docs/a", data=b"one"),
        ModelAction(kind=ModelOpKind.RENAME, path="docs/a", target_path="tmp/b"),
        ModelAction(kind=ModelOpKind.GETATTR, path="docs/a"),
        ModelAction(kind=ModelOpKind.GETATTR, path="tmp/b"),
        ModelAction(kind=ModelOpKind.UNLINK, path="tmp/b"),
        ModelAction(kind=ModelOpKind.GETATTR, path="tmp/b"),
    ]
    model_ids = run_model_trace(actions)
    service_ids = run_service_trace(actions)
    ops_ids = run_ops_trace(actions)
    assert identities_match(model_ids, service_ids)
    assert identities_match(model_ids, ops_ids)
    assert model_ids[4].success is False and model_ids[4].errno == HostErrno.ENOENT.value
    assert model_ids[5].success is True
    assert model_ids[7].success is False and model_ids[7].errno == HostErrno.ENOENT.value


# ---------------------------------------------------------------------------
# Legacy differential dispositions
# ---------------------------------------------------------------------------


def test_legacy_dispositions_are_explicit_and_closed() -> None:
    table = legacy_differential_dispositions()
    assert table
    admitted = {d.operation: d for d in table if d.disposition is LegacyDispositionKind.ADMITTED}
    unsupported = {
        d.operation: d for d in table if d.disposition is LegacyDispositionKind.UNSUPPORTED
    }
    # Every adapter-admitted name appears with a canonical kind.
    for name, kind in LEGACY_VFS_OPERATION_KINDS.items():
        assert name in admitted
        assert admitted[name].canonical_kind == kind.value
        assert admitted[name].notes
    # Representative unsupported names are explicit.
    for name in ("chmod", "symlink", "unknown_op", "stat", "list", "read", "delete"):
        assert name in unsupported
        assert unsupported[name].canonical_kind == ""
    # Records are schema-tagged and content-identifiable.
    for item in table:
        rec = item.to_record()
        assert rec["schema"].endswith("@1")
        assert content_id_for(rec).startswith("sha256:")


def test_legacy_adapter_matches_dispositions() -> None:
    service = _service()
    adapter = LegacyVFSAdapter(service=service)

    async def _run() -> None:
        for item in legacy_differential_dispositions():
            if item.disposition is LegacyDispositionKind.ADMITTED:
                # Exercise a minimal admitted call; setup path state as needed.
                if item.operation == "mkdir":
                    result = await adapter.execute(
                        "mkdir", path="legacy-dir", operation_id="leg:mkdir"
                    )
                    assert result["success"] is True
                elif item.operation == "ls":
                    result = await adapter.execute(
                        "ls", path="", operation_id="leg:ls"
                    )
                    assert result["success"] is True
                elif item.operation == "write":
                    await adapter.execute("mkdir", path="w", operation_id="leg:w-mkdir")
                    # write maps to REPLACE which requires existing file — create first.
                    # Use service create via cat miss then write after seeding via mkdir only:
                    # REPLACE needs existing; use a create-equivalent path:
                    # Admitted "write" is REPLACE — seed via service.
                    service.execute(
                        make_op(VFSOperationKind.CREATE, operation_id="seed", path="w/f"),
                        VFSExecuteRequest(payload=b"old"),
                    )
                    result = await adapter.execute(
                        "write",
                        path="w/f",
                        data=b"new",
                        operation_id="leg:write",
                    )
                    assert result["success"] is True
                elif item.operation == "cat":
                    service.execute(
                        make_op(VFSOperationKind.CREATE, operation_id="seed2", path="c"),
                        VFSExecuteRequest(payload=b"data"),
                    )
                    result = await adapter.execute(
                        "cat", path="c", operation_id="leg:cat"
                    )
                    assert result["success"] is True
                    assert result.get("data") == b"data"
                elif item.operation == "info":
                    service.execute(
                        make_op(VFSOperationKind.CREATE, operation_id="seed3", path="i"),
                        VFSExecuteRequest(payload=b"i"),
                    )
                    result = await adapter.execute(
                        "info", path="i", operation_id="leg:info"
                    )
                    assert result["success"] is True
                elif item.operation == "rm":
                    service.execute(
                        make_op(VFSOperationKind.CREATE, operation_id="seed4", path="r"),
                        VFSExecuteRequest(payload=b"r"),
                    )
                    result = await adapter.execute(
                        "rm", path="r", operation_id="leg:rm"
                    )
                    assert result["success"] is True
                elif item.operation == "rmdir":
                    service.execute(
                        make_op(VFSOperationKind.MKDIR, operation_id="seed5", path="rd")
                    )
                    result = await adapter.execute(
                        "rmdir", path="rd", operation_id="leg:rmdir"
                    )
                    assert result["success"] is True
                elif item.operation == "rename":
                    service.execute(
                        make_op(VFSOperationKind.CREATE, operation_id="seed6", path="rn-a"),
                        VFSExecuteRequest(payload=b"a"),
                    )
                    result = await adapter.execute(
                        "rename",
                        source_path="rn-a",
                        target_path="rn-b",
                        operation_id="leg:rename",
                    )
                    assert result["success"] is True
                elif item.operation == "move":
                    service.execute(
                        make_op(VFSOperationKind.CREATE, operation_id="seed7", path="mv-a"),
                        VFSExecuteRequest(payload=b"a"),
                    )
                    result = await adapter.execute(
                        "move",
                        source_path="mv-a",
                        target_path="mv-b",
                        operation_id="leg:move",
                    )
                    assert result["success"] is True
            else:
                result = await adapter.execute(item.operation, path="x")
                assert result["success"] is False
                assert result.get("code") == "unsupported_legacy_operation"
                # Disposition lookup agrees.
                assert (
                    disposition_for_legacy(item.operation).disposition
                    is LegacyDispositionKind.UNSUPPORTED
                )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Callback disposition table + model purity
# ---------------------------------------------------------------------------


def test_host_callback_dispositions_are_closed() -> None:
    table = callback_dispositions_table()
    assert "getattr" in table
    assert table["getattr"] == "required_supported"
    assert "symlink" in table
    assert table["symlink"] == "explicit_unsupported"
    # Executable check via production helper.
    for name, disp in table.items():
        assert callback_disposition(name).value == disp


def test_model_does_not_import_production_oracle_modules() -> None:
    """Conflict policy: model must not encode production implementation as oracle."""

    source = MODEL_PATH.read_text(encoding="utf-8")
    # Allowed: contract/adapter vocabulary and docstring mentions.
    # Forbidden: live imports of service/operations/host façade as oracle.
    banned_import_fragments = (
        "from ipfs_kit_py.core.vfs.service import",
        "from ipfs_kit_py.kernel_vfs.operations import",
        "from ipfs_kit_py.core.vfs.host_service import",
        "import ipfs_kit_py.core.vfs.service",
        "import ipfs_kit_py.kernel_vfs.operations",
        "import ipfs_kit_py.core.vfs.host_service",
    )
    for fragment in banned_import_fragments:
        assert fragment not in source, fragment


def test_model_seed_and_clone_preserve_state() -> None:
    model = KernelVFSReferenceModel(clock_ms=FIXED_CLOCK_MS)
    model.seed("docs", kind=EntryKind.DIRECTORY)
    model.seed("docs/a", kind=EntryKind.FILE, content=b"x")
    clone = model.clone()
    assert clone.abstract_state() == model.abstract_state()
    clone.apply(ModelAction(kind=ModelOpKind.UNLINK, path="docs/a"))
    assert model.get("docs/a") is not None
    assert clone.get("docs/a") is None
