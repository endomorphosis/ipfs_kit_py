"""Regression tests for repository/branch current-seal CAS (IPS-023).

Acceptance coverage:

* exactly one concurrent writer wins;
* wrong branch / parent / generation rejects;
* pointer bytes are rehashed on every read;
* directory durability (file + parent fsync) is enforced;
* explicit root only (no default user state or daemon).
"""

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest import mock

import pytest

from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    CurrentSealPointer,
    ExplicitRootRequiredError,
    ProofSealStoreContractError,
)
from ipfs_kit_py.proof_seal_store.local_store import content_cid_for_bytes
from ipfs_kit_py.proof_seal_store.pointer import (
    EVIDENCE_SUBSET,
    POINTER_ENVELOPE_SCHEMA,
    POINTER_STORE_INTERFACE,
    CurrentSealRepository,
    PointerCasRejected,
    PointerDisposition,
    PointerIntegrityError,
    PointerReason,
    compare_and_swap_current_seal,
    get_current_seal,
    namespace_digest,
    namespace_key,
    payload_digest_hex,
    pointer_payload_bytes,
)


def _cid(tag: bytes) -> str:
    return content_cid_for_bytes(b'{"seal":"' + tag + b'"}')


def _pointer(
    *,
    repository_id: str = "repo:kit",
    branch_id: str = "main",
    seal_tag: bytes = b"seal-1",
    seal_kind: ArtifactKind = ArtifactKind.CHECKPOINT_SEAL,
    generation: int = 0,
    parent_seal_cid: str = "",
    seal_cid: str | None = None,
) -> CurrentSealPointer:
    return CurrentSealPointer(
        repository_id=repository_id,
        branch_id=branch_id,
        seal_cid=seal_cid if seal_cid is not None else _cid(seal_tag),
        seal_kind=seal_kind,
        generation=generation,
        parent_seal_cid=parent_seal_cid,
    )


def _repo(tmp_path: Path) -> CurrentSealRepository:
    return CurrentSealRepository(tmp_path)


def _envelope_path(repo: CurrentSealRepository, pointer: CurrentSealPointer) -> Path:
    digest = namespace_digest(pointer.repository_id, pointer.branch_id)
    return repo.root_path / "current_seals" / f"{digest}.json"


# ---------------------------------------------------------------------------
# Construction / constants
# ---------------------------------------------------------------------------


def test_schema_and_evidence_constants() -> None:
    assert EVIDENCE_SUBSET == "ips/current-seal-cas@1"
    assert POINTER_STORE_INTERFACE == "CurrentSealRepository@1"
    assert POINTER_ENVELOPE_SCHEMA.endswith("@1")


def test_explicit_root_is_mandatory() -> None:
    with pytest.raises(ExplicitRootRequiredError):
        CurrentSealRepository(None)
    with pytest.raises(ExplicitRootRequiredError):
        CurrentSealRepository("relative/pointers")
    with pytest.raises(ExplicitRootRequiredError):
        CurrentSealRepository("~/current-seals")


def test_namespace_helpers() -> None:
    assert namespace_key("repo:a", "main") == "repo:a#main"
    digest = namespace_digest("repo:a", "main")
    assert len(digest) == 64
    assert digest == hashlib.sha256(b"repo:a#main").hexdigest()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_genesis_cas_and_read_round_trip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert repo.get_current_seal("repo:kit", "main") is None

    first = _pointer(seal_tag=b"gen0", generation=0)
    assert compare_and_swap_current_seal(repo, None, first) is True
    current = get_current_seal(repo, "repo:kit", "main")
    assert current == first
    assert current is not None
    assert current.role.value == "current"
    assert current.namespace_key == "repo:kit#main"


def test_sequential_cas_advances_parent_and_generation(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _pointer(seal_tag=b"s0", generation=0)
    assert repo.compare_and_swap_current_seal(None, first) is True

    second = _pointer(
        seal_tag=b"s1",
        generation=1,
        parent_seal_cid=first.seal_cid,
        seal_kind=ArtifactKind.DELTA_SEAL,
    )
    assert repo.compare_and_swap_current_seal(first, second) is True
    assert repo.get_current_seal("repo:kit", "main") == second

    third = _pointer(
        seal_tag=b"s2",
        generation=2,
        parent_seal_cid=second.seal_cid,
        seal_kind=ArtifactKind.DELTA_SEAL,
    )
    result = repo.compare_and_swap_current_seal_result(second, third)
    assert result.swapped
    assert result.disposition is PointerDisposition.SWAPPED
    assert result.reason is PointerReason.OK
    assert repo.get_current_seal("repo:kit", "main") == third


def test_namespaces_are_independent(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    main = _pointer(branch_id="main", seal_tag=b"main", generation=0)
    develop = _pointer(branch_id="develop", seal_tag=b"dev", generation=0)
    assert repo.compare_and_swap_current_seal(None, main) is True
    assert repo.compare_and_swap_current_seal(None, develop) is True
    assert repo.get_current_seal("repo:kit", "main") == main
    assert repo.get_current_seal("repo:kit", "develop") == develop


# ---------------------------------------------------------------------------
# Wrong branch / parent / generation reject
# ---------------------------------------------------------------------------


def test_wrong_branch_between_expected_and_new_rejects(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _pointer(branch_id="main", seal_tag=b"s0", generation=0)
    assert repo.compare_and_swap_current_seal(None, first) is True

    wrong_branch = _pointer(
        branch_id="other",
        seal_tag=b"s1",
        generation=1,
        parent_seal_cid=first.seal_cid,
    )
    with pytest.raises(PointerCasRejected) as exc_info:
        repo.compare_and_swap_current_seal(first, wrong_branch)
    assert exc_info.value.reason is PointerReason.BRANCH_MISMATCH
    assert repo.get_current_seal("repo:kit", "main") == first


def test_wrong_parent_between_expected_and_new_rejects(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _pointer(seal_tag=b"s0", generation=0)
    assert repo.compare_and_swap_current_seal(None, first) is True

    wrong_parent = _pointer(
        seal_tag=b"s1",
        generation=1,
        parent_seal_cid=_cid(b"not-parent"),
    )
    with pytest.raises(PointerCasRejected) as exc_info:
        repo.compare_and_swap_current_seal(first, wrong_parent)
    assert exc_info.value.reason is PointerReason.PARENT_MISMATCH
    assert repo.get_current_seal("repo:kit", "main") == first


def test_wrong_generation_between_expected_and_new_rejects(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _pointer(seal_tag=b"s0", generation=0)
    assert repo.compare_and_swap_current_seal(None, first) is True

    wrong_gen = _pointer(
        seal_tag=b"s1",
        generation=5,
        parent_seal_cid=first.seal_cid,
    )
    with pytest.raises(PointerCasRejected) as exc_info:
        repo.compare_and_swap_current_seal(first, wrong_gen)
    assert exc_info.value.reason is PointerReason.GENERATION_MISMATCH
    assert repo.get_current_seal("repo:kit", "main") == first


def test_genesis_with_parent_rejects(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    bad = _pointer(
        seal_tag=b"s0",
        generation=0,
        parent_seal_cid=_cid(b"unexpected-parent"),
    )
    with pytest.raises(PointerCasRejected) as exc_info:
        repo.compare_and_swap_current_seal(None, bad)
    assert exc_info.value.reason is PointerReason.PARENT_MISMATCH


def test_stale_expected_parent_returns_false(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _pointer(seal_tag=b"s0", generation=0)
    second = _pointer(
        seal_tag=b"s1",
        generation=1,
        parent_seal_cid=first.seal_cid,
    )
    third = _pointer(
        seal_tag=b"s2",
        generation=1,
        parent_seal_cid=first.seal_cid,
    )
    assert repo.compare_and_swap_current_seal(None, first) is True
    assert repo.compare_and_swap_current_seal(first, second) is True

    # Stale writer still expects `first` after `second` won.
    assert repo.compare_and_swap_current_seal(first, third) is False
    assert repo.get_current_seal("repo:kit", "main") == second

    result = repo.compare_and_swap_current_seal_result(first, third)
    assert not result.swapped
    assert result.disposition is PointerDisposition.STALE
    assert result.reason is PointerReason.STALE_PARENT
    assert result.current == second


def test_stale_generation_on_disk_returns_false(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _pointer(seal_tag=b"s0", generation=0)
    second = _pointer(
        seal_tag=b"s1",
        generation=1,
        parent_seal_cid=first.seal_cid,
    )
    assert repo.compare_and_swap_current_seal(None, first) is True
    assert repo.compare_and_swap_current_seal(first, second) is True

    # Expected claims generation 0 with first's seal, but current is gen 1.
    stale_expected = _pointer(
        seal_tag=b"s0",
        generation=0,
        seal_cid=first.seal_cid,
    )
    contender = _pointer(
        seal_tag=b"s9",
        generation=1,
        parent_seal_cid=first.seal_cid,
    )
    result = repo.compare_and_swap_current_seal_result(stale_expected, contender)
    assert result.disposition is PointerDisposition.STALE
    assert result.reason is PointerReason.STALE_PARENT
    assert result.diagnostics.get("detail") in {
        PointerReason.GENERATION_MISMATCH.value,
        PointerReason.PARENT_MISMATCH.value,
        None,
    }
    assert repo.get_current_seal("repo:kit", "main") == second


# ---------------------------------------------------------------------------
# Concurrent writers: exactly one wins
# ---------------------------------------------------------------------------


def test_exactly_one_concurrent_writer_wins(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    parent = _pointer(seal_tag=b"parent", generation=0)
    assert repo.compare_and_swap_current_seal(None, parent) is True

    contenders = [
        _pointer(
            seal_tag=f"writer-{i}".encode("ascii"),
            generation=1,
            parent_seal_cid=parent.seal_cid,
            seal_kind=ArtifactKind.DELTA_SEAL,
        )
        for i in range(8)
    ]

    def _attempt(pointer: CurrentSealPointer) -> tuple[str, bool]:
        # Fresh repository handles share the same root + flock fence.
        local = CurrentSealRepository(tmp_path)
        return pointer.seal_cid, local.compare_and_swap_current_seal(parent, pointer)

    wins: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_attempt, p) for p in contenders]
        for future in as_completed(futures):
            seal_cid, won = future.result()
            if won:
                wins.append(seal_cid)

    assert len(wins) == 1
    current = repo.get_current_seal("repo:kit", "main")
    assert current is not None
    assert current.seal_cid == wins[0]
    assert current.generation == 1
    assert current.parent_seal_cid == parent.seal_cid
    # Losers must not have overwritten the winner.
    assert sum(1 for c in contenders if c.seal_cid == current.seal_cid) == 1


def test_concurrent_genesis_exactly_one_wins(tmp_path: Path) -> None:
    contenders = [
        _pointer(seal_tag=f"g{i}".encode("ascii"), generation=0) for i in range(6)
    ]

    def _attempt(pointer: CurrentSealPointer) -> tuple[str, bool]:
        local = CurrentSealRepository(tmp_path)
        return pointer.seal_cid, local.compare_and_swap_current_seal(None, pointer)

    wins: list[str] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_attempt, p) for p in contenders]
        for future in as_completed(futures):
            seal_cid, won = future.result()
            if won:
                wins.append(seal_cid)

    assert len(wins) == 1
    repo = CurrentSealRepository(tmp_path)
    current = repo.get_current_seal("repo:kit", "main")
    assert current is not None
    assert current.seal_cid == wins[0]


def _process_cas_worker(
    root: str,
    expected_dict: dict[str, object] | None,
    new_dict: dict[str, object],
    result_path: str,
) -> None:
    """Subprocess entry for multi-process CAS fencing."""

    repo = CurrentSealRepository(root)
    expected = (
        None
        if expected_dict is None
        else CurrentSealPointer.from_dict(expected_dict)
    )
    new_pointer = CurrentSealPointer.from_dict(new_dict)
    won = repo.compare_and_swap_current_seal(expected, new_pointer)
    Path(result_path).write_text(
        json.dumps({"seal_cid": new_pointer.seal_cid, "won": won}),
        encoding="utf-8",
    )


def test_exactly_one_concurrent_process_wins(tmp_path: Path) -> None:
    import multiprocessing as mp

    repo = _repo(tmp_path)
    parent = _pointer(seal_tag=b"proc-parent", generation=0)
    assert repo.compare_and_swap_current_seal(None, parent) is True

    contenders = [
        _pointer(
            seal_tag=f"proc-{i}".encode("ascii"),
            generation=1,
            parent_seal_cid=parent.seal_cid,
            seal_kind=ArtifactKind.DELTA_SEAL,
        )
        for i in range(4)
    ]
    results_dir = tmp_path / "proc-results"
    results_dir.mkdir()

    # Prefer fork on Linux so the worker need not re-import the pytest module.
    start_method = "fork" if "fork" in mp.get_all_start_methods() else "spawn"
    ctx = mp.get_context(start_method)
    processes: list[mp.Process] = []
    result_paths: list[Path] = []
    for index, pointer in enumerate(contenders):
        result_path = results_dir / f"{index}.json"
        result_paths.append(result_path)
        process = ctx.Process(
            target=_process_cas_worker,
            args=(
                str(tmp_path),
                parent.to_dict(),
                pointer.to_dict(),
                str(result_path),
            ),
        )
        processes.append(process)

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0

    wins = []
    for result_path in result_paths:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        if payload["won"]:
            wins.append(payload["seal_cid"])

    assert len(wins) == 1
    current = repo.get_current_seal("repo:kit", "main")
    assert current is not None
    assert current.seal_cid == wins[0]
    assert current.generation == 1


# ---------------------------------------------------------------------------
# Rehash + durability
# ---------------------------------------------------------------------------


def test_pointer_bytes_are_rehashed_on_read(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _pointer(seal_tag=b"rehash", generation=0)
    assert repo.compare_and_swap_current_seal(None, first) is True

    path = _envelope_path(repo, first)
    assert path.is_file()
    envelope = json.loads(path.read_text(encoding="utf-8"))
    assert envelope["schema"] == POINTER_ENVELOPE_SCHEMA
    expected_digest = payload_digest_hex(pointer_payload_bytes(first))
    assert envelope["payload_digest"] == expected_digest
    assert envelope["namespace_digest"] == namespace_digest(
        first.repository_id, first.branch_id
    )

    # Tamper seal_cid without updating payload_digest → rehash fails.
    envelope["pointer"]["seal_cid"] = _cid(b"tampered")
    path.write_text(json.dumps(envelope, sort_keys=True), encoding="utf-8")

    with pytest.raises(PointerIntegrityError) as exc_info:
        repo.get_current_seal("repo:kit", "main")
    assert exc_info.value.reason is PointerReason.INTEGRITY_FAILED


def test_payload_digest_mismatch_rejects(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _pointer(seal_tag=b"digest", generation=0)
    assert repo.compare_and_swap_current_seal(None, first) is True

    path = _envelope_path(repo, first)
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["payload_digest"] = "0" * 64
    path.write_text(json.dumps(envelope, sort_keys=True), encoding="utf-8")

    with pytest.raises(PointerIntegrityError) as exc_info:
        repo.get_current_seal("repo:kit", "main")
    assert exc_info.value.reason is PointerReason.INTEGRITY_FAILED


def test_directory_durability_fsyncs_file_and_parent(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _pointer(seal_tag=b"durable", generation=0)

    fsync_fds: list[int] = []
    real_fsync = os.fsync
    real_open = os.open
    opened_paths: list[str] = []

    def _tracking_fsync(fd: int) -> None:
        fsync_fds.append(fd)
        real_fsync(fd)

    def _tracking_open(
        path: str | bytes | os.PathLike[str],
        flags: int,
        *args: object,
        **kwargs: object,
    ) -> int:
        raw = os.fspath(path)
        opened_paths.append(raw if isinstance(raw, str) else os.fsdecode(raw))
        return real_open(path, flags, *args, **kwargs)

    with (
        mock.patch("os.fsync", side_effect=_tracking_fsync),
        mock.patch("os.open", side_effect=_tracking_open),
    ):
        assert repo.compare_and_swap_current_seal(None, first) is True

    # Durable publish fsyncs the pointer file and its parent directory.
    assert len(fsync_fds) >= 2
    parent_dir = str(repo.root_path / "current_seals")
    assert any(
        os.path.abspath(path) == os.path.abspath(parent_dir) for path in opened_paths
    )
    # Published pointer file must exist after successful durable CAS.
    assert _envelope_path(repo, first).is_file()


def test_fsync_failure_aborts_without_admitting(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _pointer(seal_tag=b"fsync-fail", generation=0)

    with mock.patch("os.fsync", side_effect=OSError("simulated fsync failure")):
        result = repo.compare_and_swap_current_seal_result(None, first)
    assert not result.swapped
    assert result.reason is PointerReason.FSYNC_FAILED
    assert repo.get_current_seal("repo:kit", "main") is None
    # No durable pointer file may remain after a failed publish.
    digest = namespace_digest(first.repository_id, first.branch_id)
    assert not (repo.root_path / "current_seals" / f"{digest}.json").exists()


def test_module_helpers_require_repository_type(tmp_path: Path) -> None:
    with pytest.raises(ProofSealStoreContractError):
        get_current_seal(object(), "repo:kit", "main")  # type: ignore[arg-type]
    with pytest.raises(ProofSealStoreContractError):
        compare_and_swap_current_seal(
            object(),  # type: ignore[arg-type]
            None,
            _pointer(),
        )


def test_compare_and_swap_type_checks(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(ProofSealStoreContractError):
        repo.compare_and_swap_current_seal(None, object())  # type: ignore[arg-type]
    with pytest.raises(ProofSealStoreContractError):
        repo.compare_and_swap_current_seal(object(), _pointer())  # type: ignore[arg-type]
