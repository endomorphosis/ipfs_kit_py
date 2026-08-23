"""EAAEF-095: content-addressed history artifacts; lag cannot grant authority."""

from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError

import pytest

from ipfs_kit_py.external_agent_history.publication import (
    ContentAddressedArtifact,
    HistoryLagAuthorityError,
    HistoryPublicationApprovalError,
    HistoryPublicationPrivacyError,
    PrivacySafeManifest,
    PublicationApproval,
    address_car,
    address_ipfs,
    address_ipld,
    address_parquet,
    authority_from_lag,
    publish_artifacts,
)

PARQUET = b"PAR1\x00fake-columnar-payloadPAR1"
IPLD = {"event_id": "evt-1", "kind": "audit", "count": 2}
CAR = b"\x0a\xa1\x65roots\x81dummy-car-bytes"
IPFS = b"cid-payload-bytes"


def _digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def test_content_address_parquet_ipld_car_ipfs() -> None:
    parquet = address_parquet(PARQUET)
    ipld = address_ipld(IPLD)
    car = address_car(CAR)
    ipfs = address_ipfs(IPFS)
    assert parquet.kind == "parquet"
    assert ipld.kind == "ipld"
    assert car.kind == "car"
    assert ipfs.kind == "ipfs"
    assert parquet.digest == _digest(PARQUET)
    assert car.digest == _digest(CAR)
    assert ipfs.digest == _digest(IPFS)
    assert ipld.digest.startswith("sha256:")
    assert parquet.published is False
    assert ipld.published is False


def test_unpublished_is_still_content_addressed() -> None:
    artifacts = (address_parquet(PARQUET), address_car(CAR), address_ipfs(IPFS))
    unpublished = publish_artifacts(
        artifacts,
        epoch_id="epoch-1",
        event_ids=("evt-1",),
        snapshot_digest="sha256:" + ("b" * 64),
        publish=False,
    )
    assert isinstance(unpublished, PrivacySafeManifest)
    assert unpublished.published is False
    assert unpublished.content_digest.startswith("sha256:")
    assert all(item.digest.startswith("sha256:") for item in unpublished.artifacts)
    assert all(item.published is False for item in unpublished.artifacts)
    published = publish_artifacts(
        artifacts,
        epoch_id="epoch-1",
        event_ids=("evt-1",),
        snapshot_digest="sha256:" + ("b" * 64),
        publish=True,
        approval=PublicationApproval(
            approval_id="sha256:" + ("d" * 64),
            epoch_id="epoch-1",
            artifact_digests=tuple(item.digest for item in artifacts),
            artifact_kinds=tuple(item.kind for item in artifacts),
            policy_id="history-publication@1",
        ),
        authenticate_approval=lambda claims: claims["approval_id"]
        == "sha256:" + ("d" * 64),
    )
    assert published.published is True
    assert published.approval_id == "sha256:" + ("d" * 64)
    assert all(item.published is True for item in published.artifacts)
    assert {item.digest for item in published.artifacts} == {
        item.digest for item in unpublished.artifacts
    }
    with pytest.raises(FrozenInstanceError):
        unpublished.published = True  # type: ignore[misc]


def test_publication_requires_exact_authenticated_approval() -> None:
    artifact = address_car(CAR)
    with pytest.raises(HistoryPublicationApprovalError, match="authenticated"):
        publish_artifacts((artifact,), epoch_id="epoch-1", publish=True)
    with pytest.raises(HistoryPublicationApprovalError, match="authenticated"):
        ContentAddressedArtifact(
            kind=artifact.kind,
            digest=artifact.digest,
            payload=artifact.payload,
            published=True,
        )
    approval = PublicationApproval(
        approval_id="sha256:" + ("e" * 64),
        epoch_id="epoch-other",
        artifact_digests=(artifact.digest,),
        artifact_kinds=(artifact.kind,),
        policy_id="history-publication@1",
    )
    with pytest.raises(HistoryPublicationApprovalError, match="epoch"):
        publish_artifacts(
            (artifact,),
            epoch_id="epoch-1",
            publish=True,
            approval=approval,
            authenticate_approval=lambda _claims: True,
        )


def test_manifest_rejects_secrets_and_transcripts() -> None:
    from ipfs_kit_py.external_agent_history.publication import build_manifest

    artifact = address_parquet(PARQUET)
    with pytest.raises(HistoryPublicationPrivacyError, match="secret"):
        build_manifest(
            epoch_id="epoch-1",
            artifacts=(artifact,),
            extra={"api_key": "secret"},
        )
    with pytest.raises(HistoryPublicationPrivacyError, match="transcript"):
        build_manifest(
            epoch_id="epoch-1",
            artifacts=(artifact,),
            extra={"transcript_body": "nope"},
        )
    payload = publish_artifacts((artifact,), epoch_id="epoch-1").as_mapping()
    assert "secret" not in str(payload)
    assert "transcript" not in str(payload)


def test_authority_from_lag_never_changes_authority() -> None:
    assert authority_from_lag("behind") is False
    assert authority_from_lag({"behind_ordinals": 12, "available": False}) is False
    with pytest.raises(HistoryLagAuthorityError, match="required"):
        authority_from_lag(None)
    with pytest.raises(HistoryLagAuthorityError, match="cannot grant"):
        authority_from_lag({"grant_authority": True})
    with pytest.raises(HistoryLagAuthorityError, match="cannot grant"):
        authority_from_lag({"revoke_authority": True})
    artifact = address_parquet(PARQUET)
    assert isinstance(artifact, ContentAddressedArtifact)
    assert artifact.as_mapping()["published"] is False


def test_no_live_ipfs_daemon_required() -> None:
    import ast
    import inspect
    from pathlib import Path

    from ipfs_kit_py.external_agent_history import publication as mod

    tree = ast.parse(Path(inspect.getsourcefile(mod) or "").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert "socket" not in imported
    assert "requests" not in imported
    addressed = address_ipfs(IPFS)
    assert addressed.payload == IPFS
    assert addressed.digest == _digest(IPFS)
