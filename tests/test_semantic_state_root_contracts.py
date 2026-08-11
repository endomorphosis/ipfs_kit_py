"""Focused contract tests for the inert state-root value layer."""

import base64

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import cid_for_bytes
from ipfs_kit_py.mcp_server.mcplusplus.state_root_contracts import (
    ArtifactWriteResult, ProviderStatus, RootUpdateStatus, StateRootCASResult,
    StateRootRecoveryReport, StateRootSnapshot,
)


CID = cid_for_bytes(b"state-root-contract")
TRANSITION = cid_for_bytes(b"state-root-transition")


def _cid_from_wire(wire: bytes) -> str:
    return "b" + base64.b32encode(wire).decode("ascii").lower().rstrip("=")


def _wire(cid: str) -> bytes:
    return base64.b32decode(cid[1:].upper() + "=" * ((8 - len(cid[1:]) % 8) % 8))


def _overlong_varint(cid: str, offset: int) -> str:
    wire = _wire(cid)
    return _cid_from_wire(wire[:offset] + bytes((wire[offset] | 0x80, 0)) + wire[offset + 1:])


def _nonzero_pad_bits(cid: str) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz234567"
    return cid[:-1] + alphabet[alphabet.index(cid[-1]) | 1]


def test_closed_contracts_round_trip_deterministically():
    before = StateRootSnapshot("semantic/worker-1", None, 0, None)
    after = StateRootSnapshot("semantic/worker-1", CID, 1, TRANSITION)
    result = StateRootCASResult(RootUpdateStatus.UPDATED, before, after, TRANSITION, "updated", True, True)
    report = StateRootRecoveryReport(2, (after,), (TRANSITION,), ({"code": "corrupt", "message": "rejected"},))
    write = ArtifactWriteResult(CID, True, ProviderStatus.AVAILABLE, True, "replicated")

    assert StateRootCASResult.from_dict(result.to_dict()) == result
    assert StateRootRecoveryReport.from_dict(report.to_dict()).to_dict() == report.to_dict()
    assert ArtifactWriteResult.from_dict(write.to_dict()) == write


@pytest.mark.parametrize("namespace", ["", "Upper", "/start", "end/", "double//slash", "has space"])
def test_snapshots_reject_malformed_namespaces(namespace):
    with pytest.raises(ValueError):
        StateRootSnapshot(namespace, None, 0, None)


@pytest.mark.parametrize("cid", ["cid", "bnot-base32!", "bafkqaaa", "B" + CID[1:]])
def test_contracts_reject_malformed_cids(cid):
    with pytest.raises(ValueError):
        StateRootSnapshot("semantic", cid, 1, TRANSITION)


@pytest.mark.parametrize("cid", [
    _overlong_varint(CID, 0), _overlong_varint(CID, 1),
    _overlong_varint(CID, 3), _overlong_varint(CID, 4),
    _nonzero_pad_bits(CID), "B" + CID[1:],
    _cid_from_wire(b"\x01\x70\x12\x20" + b"x" * 32),
    _cid_from_wire(b"\x01\x55\x13\x20" + b"x" * 32),
    _cid_from_wire(b"\x01\x55\x12\x1f" + b"x" * 31),
])
def test_contracts_reject_noncanonical_and_wrong_profile_cids(cid):
    with pytest.raises(ValueError):
        StateRootSnapshot("semantic", cid, 1, TRANSITION)


def test_contracts_reject_invalid_status_and_false_durability_claims():
    before = StateRootSnapshot("semantic", None, 0, None)
    after = StateRootSnapshot("semantic", CID, 1, TRANSITION)
    with pytest.raises(ValueError):
        StateRootCASResult("updated", before, after, TRANSITION, "updated", True, False)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ArtifactWriteResult(CID, False, ProviderStatus.AVAILABLE, True, "bad")
    with pytest.raises(ValueError):
        ArtifactWriteResult.from_dict({"cid": CID, "local_durable": True, "provider_status": "invented", "replicated": False, "reason_code": "bad"})


def test_cas_rejects_inconsistent_revisions_and_closed_wire_objects():
    before = StateRootSnapshot("semantic", None, 0, None)
    after = StateRootSnapshot("semantic", CID, 2, TRANSITION)
    with pytest.raises(ValueError):
        StateRootCASResult(RootUpdateStatus.UPDATED, before, after, TRANSITION, "updated", True, False)
    with pytest.raises(ValueError):
        StateRootSnapshot.from_dict({"namespace": "semantic", "root_cid": None, "revision": 0, "transition_cid": None, "extra": True})
    with pytest.raises(ValueError):
        StateRootRecoveryReport(-1, (), (), ())
