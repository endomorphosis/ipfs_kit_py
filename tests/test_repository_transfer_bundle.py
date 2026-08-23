"""Deterministic tests for EAAEF-021 bounded repository transfer modes."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from ipfs_kit_py.repository_transfer.bundle import (
    CONTRACT_VERSION,
    DIRTY_OVERLAY_MANIFEST_INTERFACE,
    REPOSITORY_HANDOFF_BUNDLE_INTERFACE,
    REPOSITORY_SNAPSHOT_MANIFEST_INTERFACE,
    REPOSITORY_TRANSFER_CONTRACT_FAMILY,
    REPOSITORY_TRANSFER_RECEIPT_INTERFACE,
    SCHEMA_VERSION,
    ApprovedRemoteAlias,
    ArtifactKind,
    ArtifactStore,
    DirtyOverlayManifest,
    ManagedAlias,
    OverlayEntry,
    OverlayStatus,
    RepositoryHandoffBundle,
    RepositorySnapshotManifest,
    RepositoryTransferError,
    RepositoryTransferMode,
    RepositoryTransferReceipt,
    RepositoryTransferRequest,
    SourceBundleManifest,
    SourceFileEntry,
    TransferError,
    TransferIdentityError,
    TransferLocator,
    TransferPolicy,
    TransferRefusal,
    TransferVerdict,
    TransferVersionError,
    admit_transfer,
    admit_transfer_request,
    artifact_identity,
    canonical_json_bytes,
    content_identity,
    create_git_bundle,
    decode_transfer_contract,
    encode_git_object_set,
    looks_like_host_path,
    transfer_repository,
)

FIXED_KEY = "idempotency:repository-transfer-1"
README_BODY = b"hello repository transfer\n"
STACK_COMPATIBILITY = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "architecture"
    / "external_agent_autonomous_execution_fabric"
    / "stack_compatibility_manifest.json"
)
HOST_PATHS = (
    "/tmp/other-repo",
    "C:\\Users\\operator\\repo",
    "file:///tmp/repo.git",
    "git@github.com:example/repo.git",
    "ssh://git@example.test/repo.git",
    "../sibling",
    "./checkout",
    "\\\\fileserver\\repo",
    "git+ssh://git@example.test/repo.git",
)


def _git_env() -> dict[str, str]:
    from ipfs_kit_py.repository_transfer.bundle import _GIT_ENV

    return dict(_GIT_ENV)


def _run_git(args: list[str], cwd: Path) -> str:
    import os
    import subprocess

    env = dict(os.environ)
    env.update(_git_env())
    env["HOME"] = str(cwd)
    completed = subprocess.run(
        ["git", "-c", "init.defaultBranch=main", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _init_fixture_repo(root: Path, body: bytes = README_BODY) -> str:
    root.mkdir(parents=True, exist_ok=True)
    _run_git(["init", "--quiet"], cwd=root)
    (root / "README.md").write_bytes(body)
    _run_git(["add", "README.md"], cwd=root)
    _run_git(["commit", "--quiet", "-m", "init"], cwd=root)
    return _run_git(["rev-parse", "HEAD"], cwd=root)


def _request(
    mode: RepositoryTransferMode,
    locator: TransferLocator | dict[str, object] | str,
    **changes: object,
) -> RepositoryTransferRequest:
    values: dict[str, object] = {
        "mode": mode,
        "locator": locator,
        "idempotency_key": FIXED_KEY,
    }
    values.update(changes)
    return RepositoryTransferRequest(**values)


def _source_file(path: str = "README.md", body: bytes = README_BODY) -> SourceFileEntry:
    return SourceFileEntry(
        path=path,
        digest=artifact_identity(body),
        mode="100644",
        byte_count=len(body),
    )


def test_frozen_contract_family_matches_stack_compatibility_names() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION == 1
    expected = {
        "bundle": REPOSITORY_HANDOFF_BUNDLE_INTERFACE,
        "snapshot": REPOSITORY_SNAPSHOT_MANIFEST_INTERFACE,
        "overlay": DIRTY_OVERLAY_MANIFEST_INTERFACE,
        "receipt": REPOSITORY_TRANSFER_RECEIPT_INTERFACE,
    }
    assert dict(REPOSITORY_TRANSFER_CONTRACT_FAMILY) == expected
    if STACK_COMPATIBILITY.is_file():
        manifest = json.loads(STACK_COMPATIBILITY.read_text(encoding="utf-8"))
        frozen = dict(manifest["frozen_contracts"]["repository_transfer"])
        frozen.pop("status", None)
        assert frozen == expected


def test_looks_like_host_path_detects_filesystem_and_scp_locators() -> None:
    for value in HOST_PATHS:
        assert looks_like_host_path(value), value
    assert not looks_like_host_path("kit-main")
    assert not looks_like_host_path("sha256:" + ("a" * 64))
    assert not looks_like_host_path("https://github.com/example/repo.git")


def test_request_rejects_arbitrary_remote_host_paths() -> None:
    for value in HOST_PATHS:
        with pytest.raises(RepositoryTransferError, match="host path"):
            _request(RepositoryTransferMode.GIT_BUNDLE, value)
        with pytest.raises(RepositoryTransferError, match="host path"):
            _request(RepositoryTransferMode.MANAGED_ALIAS, {"alias": value})
        with pytest.raises(RepositoryTransferError, match="host path"):
            _request(
                RepositoryTransferMode.APPROVED_REMOTE_ALIAS,
                {"url": value},
            )


def test_mapping_request_with_host_path_returns_typed_refusal(tmp_path: Path) -> None:
    result = transfer_repository(
        {
            "schema": "ipfs_kit_py/repository-transfer/transfer-request@1",
            "mode": "git_bundle",
            "locator": {"mode": "git_bundle", "path": "/tmp/repo.git"},
            "idempotency_key": FIXED_KEY,
        },
        quarantine_root=tmp_path / "quarantine",
    )
    assert result.receipt.verdict is TransferVerdict.REFUSED
    assert result.receipt.reason_code == TransferRefusal.ARBITRARY_HOST_PATH.value
    assert result.bundle is None


def test_managed_alias_cannot_embed_host_path_or_url() -> None:
    digest = artifact_identity(b"bundle")
    with pytest.raises(RepositoryTransferError, match="host path|remote URL"):
        ManagedAlias.from_dict(
            {
                "schema": "ipfs_kit_py/repository-transfer/managed-alias@1",
                "interface": "ManagedAlias@1",
                "contract_version": 1,
                "name": "kit-main",
                "artifact_kind": "git_bundle",
                "artifact_id": digest,
                "path": "/opt/src/kit",
            }
        )
    with pytest.raises(RepositoryTransferError, match="host path|https"):
        ApprovedRemoteAlias(
            name="origin-kit",
            approved_url="file:///tmp/repo.git",
            artifact_kind=ArtifactKind.GIT_BUNDLE,
            artifact_id=digest,
        )
    with pytest.raises(RepositoryTransferError, match="local host path"):
        ApprovedRemoteAlias(
            name="origin-kit",
            approved_url="https://127.0.0.1/repo.git",
            artifact_kind=ArtifactKind.GIT_BUNDLE,
            artifact_id=digest,
        )


def test_git_bundle_reconstructs_declared_head_without_mutating_checkout(
    tmp_path: Path,
) -> None:
    user = tmp_path / "user-checkout"
    user_head = _init_fixture_repo(user, b"user checkout must stay\n")
    user_readme = (user / "README.md").read_bytes()
    source = tmp_path / "source"
    head = _init_fixture_repo(source)
    tree = _run_git(["rev-parse", "HEAD^{tree}"], cwd=source)
    bundle_bytes = create_git_bundle(source)
    store = ArtifactStore()
    artifact_id = store.add(bundle_bytes)
    quarantine = tmp_path / "quarantine"
    request = _request(
        RepositoryTransferMode.GIT_BUNDLE,
        {"artifact_id": artifact_id, "declared_head": head, "declared_tree": tree},
        declared_head=head,
        declared_tree=tree,
        origin_alias="kit-main",
    )
    result = transfer_repository(
        request,
        artifacts=store,
        quarantine_root=quarantine,
        user_checkout=user,
    )
    assert result.admitted
    assert result.receipt.verdict is TransferVerdict.ADMITTED
    assert result.receipt.user_checkout_mutated is False
    assert result.snapshot is not None
    assert result.snapshot.head_commit == head
    assert result.snapshot.head_tree == tree
    assert result.snapshot.origin_alias == "kit-main"
    assert result.snapshot.hooks_disabled is True
    assert result.snapshot.is_git_repository is True
    assert result.bundle is not None
    assert result.bundle.mode is RepositoryTransferMode.GIT_BUNDLE
    assert result.bundle.reconstructed_tree_id == tree
    reconstructed = quarantine / result.repository_root
    config = (reconstructed / ".git" / "config").read_text(encoding="utf-8")
    assert "file://" not in config
    assert "alias:kit-main" in config
    assert ".git/hooks-disabled" in config
    assert _run_git(["rev-parse", "HEAD"], cwd=user) == user_head
    assert (user / "README.md").read_bytes() == user_readme


def test_managed_alias_resolves_to_staged_git_bundle(tmp_path: Path) -> None:
    source = tmp_path / "source"
    head = _init_fixture_repo(source)
    bundle_bytes = create_git_bundle(source)
    store = ArtifactStore()
    artifact_id = store.add(bundle_bytes)
    alias = ManagedAlias(
        name="kit-main",
        artifact_kind=ArtifactKind.GIT_BUNDLE,
        artifact_id=artifact_id,
        declared_head=head,
    )
    request = _request(RepositoryTransferMode.MANAGED_ALIAS, {"alias": "kit-main"})
    assert admit_transfer_request(request, managed_aliases=(alias,)) is None
    result = transfer_repository(
        request,
        artifacts=store,
        managed_aliases={"kit-main": alias},
        quarantine_root=tmp_path / "quarantine",
    )
    assert result.admitted
    assert result.snapshot is not None
    assert result.snapshot.head_commit == head
    assert result.bundle is not None
    assert result.bundle.origin_alias == "kit-main"


def test_unknown_managed_alias_is_refused(tmp_path: Path) -> None:
    request = _request(RepositoryTransferMode.MANAGED_ALIAS, {"alias": "missing-kit"})
    assert (
        admit_transfer_request(request, managed_aliases=())
        is TransferRefusal.UNKNOWN_ALIAS
    )
    result = transfer_repository(
        request,
        quarantine_root=tmp_path / "quarantine",
    )
    assert result.receipt.verdict is TransferVerdict.REFUSED
    assert result.receipt.reason_code == TransferRefusal.UNKNOWN_ALIAS.value


def test_approved_remote_alias_reconstructs_from_staged_artifact_not_url(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    head = _init_fixture_repo(source)
    bundle_bytes = create_git_bundle(source)
    store = ArtifactStore()
    artifact_id = store.add(bundle_bytes)
    remote = ApprovedRemoteAlias(
        name="origin-kit",
        approved_url="https://github.com/example/ipfs-kit.git",
        artifact_kind=ArtifactKind.GIT_BUNDLE,
        artifact_id=artifact_id,
        declared_head=head,
    )
    request = _request(
        RepositoryTransferMode.APPROVED_REMOTE_ALIAS, {"alias": "origin-kit"}
    )
    result = transfer_repository(
        request,
        artifacts=store,
        approved_remotes=(remote,),
        quarantine_root=tmp_path / "quarantine",
    )
    assert result.admitted
    assert result.snapshot is not None
    assert result.snapshot.head_commit == head
    assert result.snapshot.origin_alias == "origin-kit"


def test_approved_remote_without_staged_artifact_does_not_fetch(
    tmp_path: Path,
) -> None:
    remote = ApprovedRemoteAlias(
        name="origin-kit",
        approved_url="https://github.com/example/ipfs-kit.git",
        artifact_kind=ArtifactKind.GIT_BUNDLE,
        artifact_id=artifact_identity(b"absent-bundle-bytes"),
    )
    request = _request(
        RepositoryTransferMode.APPROVED_REMOTE_ALIAS, {"alias": "origin-kit"}
    )
    result = transfer_repository(
        request,
        artifacts=ArtifactStore(),
        approved_remotes=(remote,),
        quarantine_root=tmp_path / "quarantine",
    )
    assert result.receipt.verdict is TransferVerdict.REFUSED
    assert result.receipt.reason_code == TransferRefusal.REMOTE_FETCH_NOT_ADMITTED.value


def test_unapproved_remote_alias_is_refused(tmp_path: Path) -> None:
    request = _request(
        RepositoryTransferMode.APPROVED_REMOTE_ALIAS, {"alias": "not-approved"}
    )
    result = transfer_repository(request, quarantine_root=tmp_path / "quarantine")
    assert result.receipt.reason_code == TransferRefusal.UNAPPROVED_REMOTE.value


def test_manifested_source_bundle_reconstructs_declared_tree(tmp_path: Path) -> None:
    body = README_BODY
    extra = b"print('ok')\n"
    store = ArtifactStore()
    store.add(body)
    store.add(extra)
    files = (
        _source_file("README.md", body),
        SourceFileEntry(
            path="src/hello.py",
            digest=artifact_identity(extra),
            mode="100755",
            byte_count=len(extra),
        ),
    )
    manifest = SourceBundleManifest(files=files, untracked=("scratch.log",))
    store.add(manifest.canonical_bytes())
    request = _request(
        RepositoryTransferMode.MANIFESTED_SOURCE_BUNDLE,
        {"manifest_id": manifest.content_id, "declared_tree": manifest.tree_identity()},
        declared_tree=manifest.tree_identity(),
        overlay_entries=(
            OverlayEntry(path="scratch.log", status=OverlayStatus.UNTRACKED),
        ),
    )
    result = transfer_repository(
        request,
        artifacts=store,
        source_manifests={manifest.content_id: manifest},
        quarantine_root=tmp_path / "quarantine",
    )
    assert result.admitted
    assert result.snapshot is not None
    assert result.snapshot.head_tree == manifest.tree_identity()
    assert result.snapshot.is_git_repository is False
    assert "src/hello.py" in result.snapshot.executable_paths
    assert result.overlay is not None
    assert any(item.path == "scratch.log" for item in result.overlay.entries)
    reconstructed = tmp_path / "quarantine" / result.repository_root
    assert (reconstructed / "README.md").read_bytes() == body
    assert (reconstructed / "src" / "hello.py").read_bytes() == extra


def test_source_bundle_rejects_escaped_and_git_metadata_paths(tmp_path: Path) -> None:
    body = README_BODY
    store = ArtifactStore()
    digest = store.add(body)
    with pytest.raises(RepositoryTransferError, match="repository-relative|host path"):
        SourceFileEntry(path="../secret", digest=digest)
    with pytest.raises(RepositoryTransferError, match="Git metadata"):
        SourceFileEntry(path=".git/hooks/post-checkout", digest=digest)
    with pytest.raises(RepositoryTransferError, match="host path"):
        SourceFileEntry(path="/etc/passwd", digest=digest)


def test_uploaded_object_set_reconstructs_git_objects(tmp_path: Path) -> None:
    source = tmp_path / "source"
    head = _init_fixture_repo(source)
    tree = _run_git(["rev-parse", "HEAD^{tree}"], cwd=source)
    payload = encode_git_object_set(source)
    store = ArtifactStore()
    artifact_id = store.add(payload)
    request = _request(
        RepositoryTransferMode.UPLOADED_OBJECT_SET,
        {"artifact_id": artifact_id, "declared_head": head},
        declared_head=head,
        declared_tree=tree,
    )
    result = transfer_repository(
        request,
        artifacts=store,
        quarantine_root=tmp_path / "quarantine",
    )
    assert result.admitted
    assert result.snapshot is not None
    assert result.snapshot.head_commit == head
    assert result.snapshot.head_tree == tree
    reconstructed = tmp_path / "quarantine" / result.repository_root
    assert (reconstructed / "README.md").read_bytes() == README_BODY


def test_declared_state_mismatch_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _init_fixture_repo(source)
    store = ArtifactStore()
    artifact_id = store.add(create_git_bundle(source))
    request = _request(
        RepositoryTransferMode.GIT_BUNDLE,
        {"artifact_id": artifact_id},
        declared_head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    result = transfer_repository(
        request,
        artifacts=store,
        quarantine_root=tmp_path / "quarantine",
    )
    assert result.receipt.verdict is TransferVerdict.REFUSED
    assert result.receipt.reason_code == TransferRefusal.DECLARED_STATE_MISMATCH.value


def test_missing_artifact_is_refused(tmp_path: Path) -> None:
    request = _request(
        RepositoryTransferMode.GIT_BUNDLE,
        {"artifact_id": artifact_identity(b"no-such-bundle")},
    )
    result = transfer_repository(request, quarantine_root=tmp_path / "quarantine")
    assert result.receipt.reason_code == TransferRefusal.ARTIFACT_MISSING.value


def test_user_checkout_cannot_be_used_as_quarantine(tmp_path: Path) -> None:
    user = tmp_path / "user-checkout"
    _init_fixture_repo(user)
    source = tmp_path / "source"
    _init_fixture_repo(source)
    store = ArtifactStore()
    artifact_id = store.add(create_git_bundle(source))
    request = _request(
        RepositoryTransferMode.GIT_BUNDLE, {"artifact_id": artifact_id}
    )
    result = transfer_repository(
        request,
        artifacts=store,
        quarantine_root=user,
        user_checkout=user,
    )
    assert result.receipt.reason_code == TransferRefusal.QUARANTINE_UNSAFE.value
    assert (user / "README.md").read_bytes() == README_BODY


def test_records_round_trip_and_are_frozen() -> None:
    digest = artifact_identity(README_BODY)
    locator = TransferLocator(
        mode=RepositoryTransferMode.GIT_BUNDLE, artifact_id=digest
    )
    overlay = DirtyOverlayManifest(
        entries=(OverlayEntry(path="scratch.log", status=OverlayStatus.UNTRACKED),)
    )
    snapshot = RepositorySnapshotManifest(
        head_tree=digest,
        worktree_tree=digest,
        hooks_disabled=True,
        is_git_repository=False,
    )
    bundle = RepositoryHandoffBundle(
        mode=RepositoryTransferMode.GIT_BUNDLE,
        locator=locator,
        snapshot_id=snapshot.content_id,
        overlay_id=overlay.content_id,
        reconstructed_tree_id=digest,
        artifact_ids=(digest,),
    )
    receipt = RepositoryTransferReceipt(
        request_id=digest,
        verdict=TransferVerdict.ADMITTED,
        mode=RepositoryTransferMode.GIT_BUNDLE,
        policy_id="repository-transfer@1",
        bundle_id=bundle.content_id,
        snapshot_id=snapshot.content_id,
        overlay_id=overlay.content_id,
        reconstructed_tree_id=digest,
    )
    for value in (
        TransferPolicy(),
        locator,
        overlay,
        snapshot,
        bundle,
        receipt,
        ManagedAlias(
            name="kit-main",
            artifact_kind=ArtifactKind.GIT_BUNDLE,
            artifact_id=digest,
        ),
        ApprovedRemoteAlias(
            name="origin-kit",
            approved_url="https://github.com/example/ipfs-kit.git",
            artifact_kind=ArtifactKind.GIT_BUNDLE,
            artifact_id=digest,
        ),
    ):
        restored = type(value).from_json(value.to_json())
        assert restored == value
        assert restored.content_id == value.content_id
        assert decode_transfer_contract(json.loads(value.to_json())) == value
        payload = json.loads(value.to_json())
        assert payload["contract_version"] == 1
        assert payload["schema"].endswith("@1")
        assert payload["interface"].endswith("@1")
    with pytest.raises(FrozenInstanceError):
        locator.alias = "mutated"  # type: ignore[misc]


def test_serialization_is_deterministic_across_input_order() -> None:
    first = SourceBundleManifest(
        files=(
            _source_file("b.txt", b"b"),
            _source_file("a.txt", b"a"),
        )
    )
    second = SourceBundleManifest(
        files=(
            _source_file("a.txt", b"a"),
            _source_file("b.txt", b"b"),
        )
    )
    assert first.to_json() == second.to_json()
    assert first.content_id == second.content_id
    assert first.to_json() == json.dumps(
        json.loads(first.to_json()),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert canonical_json_bytes(first.to_dict()) == first.canonical_bytes()


def test_unknown_schema_and_forged_identity_are_rejected() -> None:
    digest = artifact_identity(b"x")
    locator = TransferLocator(
        mode=RepositoryTransferMode.GIT_BUNDLE, artifact_id=digest
    )
    payload = locator.to_dict()
    payload["schema"] = "ipfs_kit_py/repository-transfer/locator@2"
    with pytest.raises(TransferVersionError):
        TransferLocator.from_dict(payload)
    payload = locator.to_dict()
    payload["content_id"] = "sha256:" + ("a" * 64)
    with pytest.raises(TransferIdentityError):
        TransferLocator.from_dict(payload)
    with pytest.raises(TransferVersionError):
        decode_transfer_contract({"schema": "UnknownRecord@1", "contract_version": 1})


def test_hidden_chain_of_thought_and_private_material_are_rejected() -> None:
    digest = artifact_identity(b"x")
    with pytest.raises(RepositoryTransferError, match="hidden chain-of-thought"):
        TransferLocator.from_dict(
            {
                "schema": "ipfs_kit_py/repository-transfer/locator@1",
                "interface": "TransferLocator@1",
                "contract_version": 1,
                "mode": "git_bundle",
                "artifact_id": digest,
                "thinking": "secret scratchpad",
            }
        )
    with pytest.raises(RepositoryTransferError, match="private material"):
        TransferLocator.from_dict(
            {
                "schema": "ipfs_kit_py/repository-transfer/locator@1",
                "interface": "TransferLocator@1",
                "contract_version": 1,
                "mode": "git_bundle",
                "artifact_id": digest,
                "api_key": "secret",
            }
        )


def test_unknown_transfer_mode_is_rejected() -> None:
    with pytest.raises(RepositoryTransferError, match="must be one of"):
        _request("rsync_host", {"artifact_id": artifact_identity(b"x")})  # type: ignore[arg-type]


def test_bounds_policy_rejects_oversized_bundle(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _init_fixture_repo(source)
    store = ArtifactStore()
    artifact_id = store.add(create_git_bundle(source))
    policy = TransferPolicy(max_artifact_bytes=16)
    request = _request(
        RepositoryTransferMode.GIT_BUNDLE, {"artifact_id": artifact_id}
    )
    result = transfer_repository(
        request,
        artifacts=store,
        quarantine_root=tmp_path / "quarantine",
        policy=policy,
    )
    assert result.receipt.reason_code == TransferRefusal.BOUNDS_EXCEEDED.value


def test_all_closed_transfer_modes_are_named() -> None:
    assert {item.value for item in RepositoryTransferMode} == {
        "managed_alias",
        "git_bundle",
        "manifested_source_bundle",
        "approved_remote_alias",
        "uploaded_object_set",
    }


def test_content_identity_is_stable() -> None:
    first = content_identity({"mode": "git_bundle", "alias": "kit-main"})
    second = content_identity({"alias": "kit-main", "mode": "git_bundle"})
    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == 71


def test_compact_compatibility_admission_has_no_reconstruction_authority() -> None:
    request = admit_transfer(mode="managed_alias", locator="repos/core", alias="core")
    assert request.mode == "managed_alias"
    assert request.to_dict()["reconstruction_authority"] is False
    with pytest.raises(TransferError, match="host paths"):
        admit_transfer(mode="git_bundle", locator="/etc/passwd")


def test_quarantine_rejects_symlink_and_preserves_target(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("preserved", encoding="utf-8")
    quarantine = tmp_path / "quarantine"
    quarantine.symlink_to(outside, target_is_directory=True)
    request = _request(
        RepositoryTransferMode.GIT_BUNDLE,
        {"artifact_id": artifact_identity(b"missing")},
    )
    result = transfer_repository(request, quarantine_root=quarantine)
    assert result.receipt.reason_code == TransferRefusal.QUARANTINE_UNSAFE.value
    assert sentinel.read_text(encoding="utf-8") == "preserved"


def test_quarantine_rejects_populated_unowned_scope_without_deleting(
    tmp_path: Path,
) -> None:
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    sentinel = quarantine / "sentinel"
    sentinel.write_text("caller-owned", encoding="utf-8")
    request = _request(
        RepositoryTransferMode.GIT_BUNDLE,
        {"artifact_id": artifact_identity(b"missing")},
    )
    result = transfer_repository(request, quarantine_root=quarantine)
    assert result.receipt.reason_code == TransferRefusal.QUARANTINE_UNSAFE.value
    assert sentinel.read_text(encoding="utf-8") == "caller-owned"
