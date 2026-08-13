"""Campaign Merkle roots, seal manifests, and benchmark artifacts (AAE-036).

``DurableAssuranceCampaignMerkleRepository`` is a thin typed layer over
``DurableCoordinationStore`` and ``DurableAssuranceArtifactStore``:

* closed required-set kinds for operator / policy / admitted / detection /
  outcome / survivor / vacuity / held-out commitments;
* deterministic per-set and campaign Merkle roots over sorted member CIDs;
* required-set completeness enforced before a campaign root may be published;
* seal manifests that make seal availability and seal status explicit;
* signature verification for signed receipts before any durable write, Merkle
  set inclusion, campaign-root input, or seal-manifest input — so invalid or
  not-yet-verified signed receipts cannot enter a manifest;
* operation-id idempotent CAS under the closed ``merkle`` namespace role;
* immutable benchmark artifact blocks with recomputed CIDs.

Does not open a second object store, WAL, daemon, envelope hierarchy, or
content-identity path.  Datasets remain the signature/receipt authority; kit
owns only set/root/seal/benchmark manifests and the CAS head.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Mapping, Optional, Protocol, Sequence

from ipfs_datasets_py.logic.software_contracts.adversarial_assurance import (
    SealAvailabilityStatus,
    SignatureVerificationStatus,
)
from ipfs_datasets_py.logic.software_contracts.adversarial_assurance.receipt_contracts import (
    ASSURANCE_CAMPAIGN_RECEIPT_SCHEMA,
    ASSURANCE_POLICY_PROMOTION_RECEIPT_SCHEMA,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes,
)
from ipfs_kit_py.mcp_server.mcplusplus.event_dag import build_merkle_tree
from ipfs_kit_py.adversarial_assurance_store.artifacts import (
    AssuranceArtifactAdmissionError,
    AssuranceArtifactError,
    DurableAssuranceArtifactStore,
    seal_assurance_artifact,
)
from ipfs_kit_py.adversarial_assurance_store.campaigns import (
    REQUIRED_RECEIPT_AUDIENCE,
    admit_campaign_receipt_payload,
    validate_campaign_id,
    validate_generation_expectation,
)
from ipfs_kit_py.adversarial_assurance_store.contracts import (
    AssuranceArtifactKind,
    AssuranceArtifactStoreContractError,
    AssuranceNamespaceRole,
    AssuranceStoreStatus,
    assurance_namespace,
    require_verified_signature_gate,
    validate_assurance_workspace,
    validate_operation_id,
    validate_reason_code,
    validate_semantic_dag_json_cid,
)

# ---------------------------------------------------------------------------
# Schema / interface constants
# ---------------------------------------------------------------------------

MERKLE_MODULE_INTERFACE: Final[str] = "AssuranceCampaignMerkleRepository@1"

MERKLE_SET_INTERFACE: Final[str] = "CampaignMerkleSet@1"
MERKLE_SET_SCHEMA: Final[str] = (
    "ipfs-kit.adversarial-assurance-store.merkle-set@1"
)

CAMPAIGN_MERKLE_ROOT_INTERFACE: Final[str] = "CampaignMerkleRoot@1"
CAMPAIGN_MERKLE_ROOT_SCHEMA: Final[str] = (
    "ipfs-kit.adversarial-assurance-store.campaign-merkle-root@1"
)

SEAL_MANIFEST_INTERFACE: Final[str] = "CampaignSealManifest@1"
SEAL_MANIFEST_SCHEMA: Final[str] = (
    "ipfs-kit.adversarial-assurance-store.seal-manifest@1"
)

BENCHMARK_ARTIFACT_INTERFACE: Final[str] = "AssuranceBenchmarkArtifact@1"
BENCHMARK_ARTIFACT_SCHEMA: Final[str] = (
    "ipfs-kit.adversarial-assurance-store.benchmark-artifact@1"
)

MAX_SET_MEMBERS: Final[int] = 4_096
MAX_BENCHMARK_ARTIFACT_CIDS: Final[int] = 4_096
MAX_BENCHMARK_ID_CHARS: Final[int] = 128
MAX_SUMMARY_CHARS: Final[int] = 2_048

# Schemas that identify signed receipt wire records requiring the gate before
# Merkle inclusion, seal input, or any durable write through this module.
_SIGNED_RECEIPT_SCHEMAS: Final[frozenset[str]] = frozenset(
    {
        ASSURANCE_CAMPAIGN_RECEIPT_SCHEMA,
        ASSURANCE_POLICY_PROMOTION_RECEIPT_SCHEMA,
    }
)

_BENCHMARK_ID: Final[re.Pattern[str]] = re.compile(
    r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?"
)

# Seal statuses that claim bound/released seal evidence is present.
_SEAL_EVIDENCE_REQUIRED: Final[frozenset[str]] = frozenset(
    {
        SealAvailabilityStatus.BOUND.value,
        SealAvailabilityStatus.RELEASED.value,
    }
)

# Seal statuses that count as "available" for explicit availability reporting.
_SEAL_AVAILABLE_STATUSES: Final[frozenset[str]] = frozenset(
    {
        SealAvailabilityStatus.BOUND.value,
        SealAvailabilityStatus.RELEASED.value,
    }
)


# ---------------------------------------------------------------------------
# Closed enumerations
# ---------------------------------------------------------------------------


class MerkleSetKind(str, Enum):
    """Closed required-set kinds committed by campaign Merkle roots (plan §14).

    Acceptance names these operator / policy / admitted / detection / outcome /
    survivor / vacuity / held-out.  Tokens align with that vocabulary.
    """

    OPERATOR = "operator"
    POLICY = "policy"
    ADMITTED = "admitted"
    DETECTION = "detection"
    OUTCOME = "outcome"
    SURVIVOR = "survivor"
    VACUITY = "vacuity"
    HELD_OUT = "held_out"


# Required sets are exhaustive and ordered for deterministic campaign roots.
REQUIRED_MERKLE_SET_KINDS: Final[tuple[MerkleSetKind, ...]] = (
    MerkleSetKind.OPERATOR,
    MerkleSetKind.POLICY,
    MerkleSetKind.ADMITTED,
    MerkleSetKind.DETECTION,
    MerkleSetKind.OUTCOME,
    MerkleSetKind.SURVIVOR,
    MerkleSetKind.VACUITY,
    MerkleSetKind.HELD_OUT,
)

REQUIRED_MERKLE_SET_KIND_VALUES: Final[tuple[str, ...]] = tuple(
    kind.value for kind in REQUIRED_MERKLE_SET_KINDS
)

_REQUIRED_SET_VALUE_SET: Final[frozenset[str]] = frozenset(
    REQUIRED_MERKLE_SET_KIND_VALUES
)


_MERKLE_SET_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface_id",
        "workspace",
        "campaign_id",
        "set_kind",
        "member_cids",
        "set_root",
        "member_count",
        "operation_id",
    }
)

_SET_ENTRY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "set_kind",
        "set_cid",
        "set_root",
        "member_count",
    }
)

_CAMPAIGN_ROOT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface_id",
        "workspace",
        "campaign_id",
        "generation",
        "set_entries",
        "required_set_completeness",
        "campaign_root",
        "previous_root_cid",
        "seal_manifest_cid",
        "operation_id",
    }
)

_SEAL_MANIFEST_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface_id",
        "workspace",
        "campaign_id",
        "campaign_root_cid",
        "required_sets",
        "present_sets",
        "missing_sets",
        "required_set_completeness",
        "set_cids",
        "seal_status",
        "seal_available",
        "seal_evidence_cid",
        "receipt_cid",
        "benchmark_artifact_cids",
        "operation_id",
    }
)

_BENCHMARK_ARTIFACT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface_id",
        "workspace",
        "campaign_id",
        "benchmark_id",
        "artifact_cids",
        "summary",
        "operation_id",
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MerkleStoreError(ValueError):
    """Base error for campaign Merkle / seal / benchmark store operations."""


class MerkleAdmissionError(MerkleStoreError):
    """Raised when an input is rejected by closed admission policy."""


class MerkleIntegrityError(MerkleStoreError):
    """Raised when stored heads, roots, or manifests fail verification."""


class MerkleConflictError(MerkleStoreError):
    """Raised when an operation_id is reused for a different root or artifact."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_nonnegative_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MerkleAdmissionError(f"{name} must be a non-negative integer")
    return value


def _require_positive_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise MerkleAdmissionError(f"{name} must be a positive integer")
    return value


def _require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise MerkleAdmissionError(f"{name} must be a boolean")
    return value


def _closed_mapping(
    value: object, fields: frozenset[str], name: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MerkleAdmissionError(f"{name} must be a mapping")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise MerkleAdmissionError(f"{name} has " + "; ".join(problems))
    return value


def coerce_merkle_set_kind(value: MerkleSetKind | str) -> MerkleSetKind:
    if isinstance(value, MerkleSetKind):
        return value
    if isinstance(value, str):
        try:
            return MerkleSetKind(value)
        except ValueError as exc:
            raise MerkleAdmissionError(
                f"unknown merkle set kind: {value!r}"
            ) from exc
    raise MerkleAdmissionError(
        "set_kind must be a MerkleSetKind or its closed string value"
    )


def merkle_set_kinds() -> tuple[str, ...]:
    return REQUIRED_MERKLE_SET_KIND_VALUES


def coerce_seal_availability_status(
    value: SealAvailabilityStatus | str,
) -> SealAvailabilityStatus:
    if isinstance(value, SealAvailabilityStatus):
        return value
    if isinstance(value, str):
        try:
            return SealAvailabilityStatus(value)
        except ValueError as exc:
            raise MerkleAdmissionError(
                f"unknown seal_status: {value!r}"
            ) from exc
    raise MerkleAdmissionError(
        "seal_status must be a SealAvailabilityStatus or its closed string value"
    )


def seal_availability_statuses() -> tuple[str, ...]:
    return tuple(status.value for status in SealAvailabilityStatus)


def seal_available_for_status(
    status: SealAvailabilityStatus | str,
) -> bool:
    """Explicit seal availability derived from closed seal_status vocabulary."""

    token = coerce_seal_availability_status(status)
    return token.value in _SEAL_AVAILABLE_STATUSES


def validate_benchmark_id(benchmark_id: object) -> str:
    if not isinstance(benchmark_id, str) or not _BENCHMARK_ID.fullmatch(
        benchmark_id
    ):
        raise MerkleAdmissionError(
            "benchmark_id must be a normalized identifier of length 1–128"
        )
    if len(benchmark_id) > MAX_BENCHMARK_ID_CHARS:
        raise MerkleAdmissionError(
            f"benchmark_id must be at most {MAX_BENCHMARK_ID_CHARS} characters"
        )
    return benchmark_id


def _sorted_unique_cids(
    values: object, name: str, *, maximum: int
) -> list[str]:
    if not isinstance(values, (list, tuple)):
        raise MerkleAdmissionError(f"{name} must be a list of CIDs")
    if len(values) > maximum:
        raise MerkleAdmissionError(
            f"{name} exceeds maximum length ({len(values)} > {maximum})"
        )
    sealed: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(values):
        try:
            cid = validate_semantic_dag_json_cid(item, f"{name}[{index}]")
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        if cid in seen:
            raise MerkleAdmissionError(
                f"{name} must not contain duplicate CIDs"
            )
        seen.add(cid)
        sealed.append(cid)
    sealed.sort()
    return sealed


def compute_member_set_root(member_cids: Sequence[str]) -> str:
    """Deterministic Merkle root over a sorted list of member CIDs."""

    if not isinstance(member_cids, (list, tuple)):
        raise MerkleAdmissionError("member_cids must be a sequence")
    # Callers must pre-sort; re-sort for fail-closed determinism.
    ordered = sorted(str(cid) for cid in member_cids)
    root, _layers = build_merkle_tree(ordered)
    if not isinstance(root, str) or not root:
        raise MerkleIntegrityError("merkle tree produced an empty root")
    return root


def compute_campaign_root_digest(
    set_entries: Sequence[Mapping[str, Any]],
) -> str:
    """Deterministic campaign root over ordered required-set roots."""

    if len(set_entries) != len(REQUIRED_MERKLE_SET_KINDS):
        raise MerkleAdmissionError(
            "campaign root requires exactly the required set entries"
        )
    leaves: list[str] = []
    for expected, entry in zip(REQUIRED_MERKLE_SET_KINDS, set_entries):
        if not isinstance(entry, Mapping):
            raise MerkleAdmissionError("set entry must be a mapping")
        kind = entry.get("set_kind")
        set_root = entry.get("set_root")
        if kind != expected.value:
            raise MerkleAdmissionError(
                f"set_entries must follow required order; "
                f"expected {expected.value!r}, got {kind!r}"
            )
        if not isinstance(set_root, str) or not set_root:
            raise MerkleAdmissionError("set_root must be a nonempty string")
        # Bind set_kind into the leaf so transposition cannot collide.
        leaves.append(f"{expected.value}:{set_root}")
    root, _layers = build_merkle_tree(leaves)
    if not isinstance(root, str) or not root:
        raise MerkleIntegrityError("campaign merkle tree produced an empty root")
    return root


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_merkle_set_commitment(
    *,
    workspace: str,
    campaign_id: str,
    set_kind: MerkleSetKind | str,
    member_cids: Sequence[str],
    operation_id: str,
) -> dict[str, Any]:
    """Build a closed, deterministic per-set Merkle commitment."""

    try:
        workspace = validate_assurance_workspace(workspace)
        campaign_id = validate_campaign_id(campaign_id)
        operation_id = validate_operation_id(operation_id)
    except (AssuranceArtifactStoreContractError, ValueError) as exc:
        # validate_campaign_id already raises CampaignAdmissionError which is
        # a ValueError subclass; normalize to MerkleAdmissionError.
        if isinstance(exc, MerkleAdmissionError):
            raise
        raise MerkleAdmissionError(str(exc)) from exc

    kind = coerce_merkle_set_kind(set_kind)
    members = _sorted_unique_cids(
        list(member_cids), "member_cids", maximum=MAX_SET_MEMBERS
    )
    set_root = compute_member_set_root(members)
    payload = {
        "schema": MERKLE_SET_SCHEMA,
        "interface_id": MERKLE_SET_INTERFACE,
        "workspace": workspace,
        "campaign_id": campaign_id,
        "set_kind": kind.value,
        "member_cids": members,
        "set_root": set_root,
        "member_count": len(members),
        "operation_id": operation_id,
    }
    _closed_mapping(payload, _MERKLE_SET_FIELDS, "merkle set commitment")
    return payload


def cid_for_merkle_set(commitment: Mapping[str, Any]) -> str:
    if not isinstance(commitment, Mapping):
        raise MerkleAdmissionError("merkle set commitment must be a mapping")
    return cid_for_artifact(dict(commitment))


def admit_merkle_set_commitment(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and re-seal a merkle-set commitment mapping."""

    data = dict(
        _closed_mapping(value, _MERKLE_SET_FIELDS, "merkle set commitment")
    )
    if data.get("schema") != MERKLE_SET_SCHEMA:
        raise MerkleAdmissionError(
            f"merkle set schema must be {MERKLE_SET_SCHEMA!r}"
        )
    if data.get("interface_id") != MERKLE_SET_INTERFACE:
        raise MerkleAdmissionError(
            f"merkle set interface_id must be {MERKLE_SET_INTERFACE!r}"
        )
    sealed = build_merkle_set_commitment(
        workspace=data["workspace"],
        campaign_id=data["campaign_id"],
        set_kind=data["set_kind"],
        member_cids=data["member_cids"],
        operation_id=data["operation_id"],
    )
    if sealed["set_root"] != data["set_root"]:
        raise MerkleAdmissionError(
            "set_root does not match recomputed member Merkle root"
        )
    if sealed["member_count"] != data["member_count"]:
        raise MerkleAdmissionError("member_count does not match member_cids")
    if sealed["member_cids"] != data["member_cids"]:
        # build re-sorts; stored form must already be sorted uniquely.
        raise MerkleAdmissionError(
            "member_cids must be uniquely sorted canonical CIDs"
        )
    return sealed


def _admit_set_entry(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MerkleAdmissionError("set entry must be a mapping")
    data = dict(_closed_mapping(value, _SET_ENTRY_FIELDS, "set entry"))
    kind = coerce_merkle_set_kind(data["set_kind"])
    try:
        set_cid = validate_semantic_dag_json_cid(data["set_cid"], "set_cid")
    except AssuranceArtifactStoreContractError as exc:
        raise MerkleAdmissionError(str(exc)) from exc
    set_root = data["set_root"]
    if not isinstance(set_root, str) or not set_root:
        raise MerkleAdmissionError("set_root must be a nonempty string")
    member_count = _require_nonnegative_int(data["member_count"], "member_count")
    return {
        "set_kind": kind.value,
        "set_cid": set_cid,
        "set_root": set_root,
        "member_count": member_count,
    }


def build_campaign_merkle_root(
    *,
    workspace: str,
    campaign_id: str,
    generation: int,
    set_entries: Sequence[Mapping[str, Any]],
    previous_root_cid: Optional[str],
    seal_manifest_cid: Optional[str],
    operation_id: str,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Build a closed campaign Merkle root committing all required sets."""

    try:
        workspace = validate_assurance_workspace(workspace)
        campaign_id = validate_campaign_id(campaign_id)
        operation_id = validate_operation_id(operation_id)
    except (AssuranceArtifactStoreContractError, ValueError) as exc:
        raise MerkleAdmissionError(str(exc)) from exc

    generation = _require_positive_int(generation, "generation")
    if previous_root_cid is not None:
        try:
            previous_root_cid = validate_semantic_dag_json_cid(
                previous_root_cid, "previous_root_cid"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc
    if seal_manifest_cid is not None:
        try:
            seal_manifest_cid = validate_semantic_dag_json_cid(
                seal_manifest_cid, "seal_manifest_cid"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc
    if generation == 1 and previous_root_cid is not None:
        raise MerkleAdmissionError(
            "generation-1 campaign root must not set previous_root_cid"
        )
    if generation > 1 and previous_root_cid is None:
        raise MerkleAdmissionError(
            "non-genesis campaign root requires previous_root_cid"
        )

    if not isinstance(set_entries, (list, tuple)):
        raise MerkleAdmissionError("set_entries must be a list")
    admitted = [_admit_set_entry(entry) for entry in set_entries]

    present = [entry["set_kind"] for entry in admitted]
    present_set = set(present)
    if len(present) != len(present_set):
        raise MerkleAdmissionError("set_entries must not duplicate set_kind")
    missing = [
        kind.value
        for kind in REQUIRED_MERKLE_SET_KINDS
        if kind.value not in present_set
    ]
    unknown = sorted(present_set - _REQUIRED_SET_VALUE_SET)
    if unknown:
        raise MerkleAdmissionError(
            "set_entries has unknown " + ", ".join(unknown)
        )
    completeness = len(missing) == 0 and len(admitted) == len(
        REQUIRED_MERKLE_SET_KINDS
    )
    if require_complete and not completeness:
        raise MerkleAdmissionError(
            "required-set completeness failed; missing "
            + ", ".join(missing)
        )
    if completeness:
        # Force required order for deterministic campaign_root.
        by_kind = {entry["set_kind"]: entry for entry in admitted}
        ordered = [by_kind[kind.value] for kind in REQUIRED_MERKLE_SET_KINDS]
    else:
        ordered = sorted(admitted, key=lambda item: item["set_kind"])

    campaign_root = compute_campaign_root_digest(ordered) if completeness else (
        compute_member_set_root(
            [f"{e['set_kind']}:{e['set_root']}" for e in ordered]
        )
    )

    payload = {
        "schema": CAMPAIGN_MERKLE_ROOT_SCHEMA,
        "interface_id": CAMPAIGN_MERKLE_ROOT_INTERFACE,
        "workspace": workspace,
        "campaign_id": campaign_id,
        "generation": generation,
        "set_entries": ordered,
        "required_set_completeness": completeness,
        "campaign_root": campaign_root,
        "previous_root_cid": previous_root_cid,
        "seal_manifest_cid": seal_manifest_cid,
        "operation_id": operation_id,
    }
    _closed_mapping(payload, _CAMPAIGN_ROOT_FIELDS, "campaign merkle root")
    return payload


def cid_for_campaign_merkle_root(root: Mapping[str, Any]) -> str:
    if not isinstance(root, Mapping):
        raise MerkleAdmissionError("campaign merkle root must be a mapping")
    return cid_for_artifact(dict(root))


def admit_campaign_merkle_root(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and re-seal a campaign merkle root mapping."""

    data = dict(
        _closed_mapping(value, _CAMPAIGN_ROOT_FIELDS, "campaign merkle root")
    )
    if data.get("schema") != CAMPAIGN_MERKLE_ROOT_SCHEMA:
        raise MerkleAdmissionError(
            f"campaign merkle root schema must be {CAMPAIGN_MERKLE_ROOT_SCHEMA!r}"
        )
    if data.get("interface_id") != CAMPAIGN_MERKLE_ROOT_INTERFACE:
        raise MerkleAdmissionError(
            f"campaign merkle root interface_id must be "
            f"{CAMPAIGN_MERKLE_ROOT_INTERFACE!r}"
        )
    sealed = build_campaign_merkle_root(
        workspace=data["workspace"],
        campaign_id=data["campaign_id"],
        generation=data["generation"],
        set_entries=data["set_entries"],
        previous_root_cid=data["previous_root_cid"],
        seal_manifest_cid=data["seal_manifest_cid"],
        operation_id=data["operation_id"],
        require_complete=bool(data.get("required_set_completeness", True)),
    )
    if sealed["campaign_root"] != data["campaign_root"]:
        raise MerkleAdmissionError(
            "campaign_root does not match recomputed digest"
        )
    if sealed["required_set_completeness"] != data["required_set_completeness"]:
        raise MerkleAdmissionError(
            "required_set_completeness does not match set_entries"
        )
    if sealed["set_entries"] != data["set_entries"]:
        raise MerkleAdmissionError(
            "set_entries must be the canonical required ordered form"
        )
    return sealed


def build_seal_manifest(
    *,
    workspace: str,
    campaign_id: str,
    campaign_root_cid: str,
    set_cids: Mapping[str, str],
    seal_status: SealAvailabilityStatus | str,
    seal_evidence_cid: Optional[str],
    receipt_cid: Optional[str],
    benchmark_artifact_cids: Sequence[str],
    operation_id: str,
) -> dict[str, Any]:
    """Build a closed seal manifest with explicit availability and status.

    ``seal_status`` uses the datasets ``SealAvailabilityStatus`` vocabulary.
    ``seal_available`` is the explicit boolean availability projection of that
    status (true only for bound/released).
    """

    try:
        workspace = validate_assurance_workspace(workspace)
        campaign_id = validate_campaign_id(campaign_id)
        operation_id = validate_operation_id(operation_id)
        campaign_root_cid = validate_semantic_dag_json_cid(
            campaign_root_cid, "campaign_root_cid"
        )
    except (AssuranceArtifactStoreContractError, ValueError) as exc:
        raise MerkleAdmissionError(str(exc)) from exc

    status = coerce_seal_availability_status(seal_status)
    available = seal_available_for_status(status)

    if status.value in _SEAL_EVIDENCE_REQUIRED:
        if seal_evidence_cid is None:
            raise MerkleAdmissionError(
                "bound/released seal_status requires seal_evidence_cid"
            )
    if status is SealAvailabilityStatus.UNAVAILABLE and seal_evidence_cid is not None:
        raise MerkleAdmissionError(
            "unavailable seal_status forbids seal_evidence_cid"
        )
    if seal_evidence_cid is not None:
        try:
            seal_evidence_cid = validate_semantic_dag_json_cid(
                seal_evidence_cid, "seal_evidence_cid"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc
    if receipt_cid is not None:
        try:
            receipt_cid = validate_semantic_dag_json_cid(
                receipt_cid, "receipt_cid"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc

    if not isinstance(set_cids, Mapping):
        raise MerkleAdmissionError("set_cids must be a mapping")
    sealed_set_cids: dict[str, str] = {}
    for raw_kind, raw_cid in set_cids.items():
        kind = coerce_merkle_set_kind(raw_kind)
        try:
            sealed_set_cids[kind.value] = validate_semantic_dag_json_cid(
                raw_cid, f"set_cids[{kind.value}]"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc
    # Canonical sorted keys for deterministic identity.
    ordered_set_cids = {
        kind: sealed_set_cids[kind]
        for kind in REQUIRED_MERKLE_SET_KIND_VALUES
        if kind in sealed_set_cids
    }
    # Reject unknown keys already handled by coerce; reject extras outside required.
    if set(sealed_set_cids) - _REQUIRED_SET_VALUE_SET:
        raise MerkleAdmissionError(
            "set_cids has unknown "
            + ", ".join(sorted(set(sealed_set_cids) - _REQUIRED_SET_VALUE_SET))
        )

    present = list(ordered_set_cids.keys())
    missing = [
        kind
        for kind in REQUIRED_MERKLE_SET_KIND_VALUES
        if kind not in ordered_set_cids
    ]
    completeness = len(missing) == 0
    benchmarks = _sorted_unique_cids(
        list(benchmark_artifact_cids),
        "benchmark_artifact_cids",
        maximum=MAX_BENCHMARK_ARTIFACT_CIDS,
    )

    payload = {
        "schema": SEAL_MANIFEST_SCHEMA,
        "interface_id": SEAL_MANIFEST_INTERFACE,
        "workspace": workspace,
        "campaign_id": campaign_id,
        "campaign_root_cid": campaign_root_cid,
        "required_sets": list(REQUIRED_MERKLE_SET_KIND_VALUES),
        "present_sets": present,
        "missing_sets": missing,
        "required_set_completeness": completeness,
        "set_cids": ordered_set_cids,
        "seal_status": status.value,
        "seal_available": available,
        "seal_evidence_cid": seal_evidence_cid,
        "receipt_cid": receipt_cid,
        "benchmark_artifact_cids": benchmarks,
        "operation_id": operation_id,
    }
    _closed_mapping(payload, _SEAL_MANIFEST_FIELDS, "seal manifest")
    return payload


def cid_for_seal_manifest(manifest: Mapping[str, Any]) -> str:
    if not isinstance(manifest, Mapping):
        raise MerkleAdmissionError("seal manifest must be a mapping")
    return cid_for_artifact(dict(manifest))


def admit_seal_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(_closed_mapping(value, _SEAL_MANIFEST_FIELDS, "seal manifest"))
    if data.get("schema") != SEAL_MANIFEST_SCHEMA:
        raise MerkleAdmissionError(
            f"seal manifest schema must be {SEAL_MANIFEST_SCHEMA!r}"
        )
    if data.get("interface_id") != SEAL_MANIFEST_INTERFACE:
        raise MerkleAdmissionError(
            f"seal manifest interface_id must be {SEAL_MANIFEST_INTERFACE!r}"
        )
    sealed = build_seal_manifest(
        workspace=data["workspace"],
        campaign_id=data["campaign_id"],
        campaign_root_cid=data["campaign_root_cid"],
        set_cids=data["set_cids"],
        seal_status=data["seal_status"],
        seal_evidence_cid=data["seal_evidence_cid"],
        receipt_cid=data["receipt_cid"],
        benchmark_artifact_cids=data["benchmark_artifact_cids"],
        operation_id=data["operation_id"],
    )
    if sealed != data:
        # Re-seal may reorder present/missing; compare key projections.
        if sealed["required_set_completeness"] != data["required_set_completeness"]:
            raise MerkleAdmissionError(
                "required_set_completeness does not match set_cids"
            )
        if sealed["seal_available"] != data["seal_available"]:
            raise MerkleAdmissionError(
                "seal_available does not match seal_status"
            )
        if sealed["set_cids"] != data["set_cids"]:
            raise MerkleAdmissionError("set_cids must be the canonical form")
        if sealed["present_sets"] != data["present_sets"]:
            raise MerkleAdmissionError("present_sets must match set_cids keys")
        if sealed["missing_sets"] != data["missing_sets"]:
            raise MerkleAdmissionError(
                "missing_sets must match required-set residual"
            )
        if sealed["required_sets"] != data["required_sets"]:
            raise MerkleAdmissionError(
                "required_sets must list the closed required vocabulary"
            )
        # If anything else diverged after those checks, fail closed.
        if sealed != data:
            raise MerkleAdmissionError(
                "seal manifest is not in canonical sealed form"
            )
    return sealed


def build_benchmark_artifact(
    *,
    workspace: str,
    campaign_id: str,
    benchmark_id: str,
    artifact_cids: Sequence[str],
    summary: str,
    operation_id: str,
) -> dict[str, Any]:
    """Build a closed durable benchmark artifact record."""

    try:
        workspace = validate_assurance_workspace(workspace)
        campaign_id = validate_campaign_id(campaign_id)
        operation_id = validate_operation_id(operation_id)
    except (AssuranceArtifactStoreContractError, ValueError) as exc:
        raise MerkleAdmissionError(str(exc)) from exc
    benchmark_id = validate_benchmark_id(benchmark_id)
    if not isinstance(summary, str):
        raise MerkleAdmissionError("summary must be a string")
    if len(summary) > MAX_SUMMARY_CHARS:
        raise MerkleAdmissionError(
            f"summary exceeds MAX_SUMMARY_CHARS ({len(summary)} > {MAX_SUMMARY_CHARS})"
        )
    if any(not ch.isprintable() for ch in summary):
        raise MerkleAdmissionError("summary must be printable text")
    members = _sorted_unique_cids(
        list(artifact_cids),
        "artifact_cids",
        maximum=MAX_BENCHMARK_ARTIFACT_CIDS,
    )
    payload = {
        "schema": BENCHMARK_ARTIFACT_SCHEMA,
        "interface_id": BENCHMARK_ARTIFACT_INTERFACE,
        "workspace": workspace,
        "campaign_id": campaign_id,
        "benchmark_id": benchmark_id,
        "artifact_cids": members,
        "summary": summary,
        "operation_id": operation_id,
    }
    _closed_mapping(payload, _BENCHMARK_ARTIFACT_FIELDS, "benchmark artifact")
    return payload


def cid_for_benchmark_artifact(artifact: Mapping[str, Any]) -> str:
    if not isinstance(artifact, Mapping):
        raise MerkleAdmissionError("benchmark artifact must be a mapping")
    return cid_for_artifact(dict(artifact))


def admit_benchmark_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(
        _closed_mapping(value, _BENCHMARK_ARTIFACT_FIELDS, "benchmark artifact")
    )
    if data.get("schema") != BENCHMARK_ARTIFACT_SCHEMA:
        raise MerkleAdmissionError(
            f"benchmark artifact schema must be {BENCHMARK_ARTIFACT_SCHEMA!r}"
        )
    if data.get("interface_id") != BENCHMARK_ARTIFACT_INTERFACE:
        raise MerkleAdmissionError(
            f"benchmark artifact interface_id must be "
            f"{BENCHMARK_ARTIFACT_INTERFACE!r}"
        )
    sealed = build_benchmark_artifact(
        workspace=data["workspace"],
        campaign_id=data["campaign_id"],
        benchmark_id=data["benchmark_id"],
        artifact_cids=data["artifact_cids"],
        summary=data["summary"],
        operation_id=data["operation_id"],
    )
    if sealed != data:
        raise MerkleAdmissionError(
            "benchmark artifact is not in canonical sealed form"
        )
    return sealed


# ---------------------------------------------------------------------------
# Wire / value records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MerkleRootSnapshot:
    """Currently visible campaign Merkle root head under the merkle namespace."""

    namespace: str
    root_cid: str | None
    generation: int
    transition_cid: str | None
    campaign_id: str | None
    campaign_root: str | None
    required_set_completeness: bool | None
    seal_manifest_cid: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise MerkleIntegrityError("namespace must be a nonempty string")
        if (
            not isinstance(self.generation, int)
            or isinstance(self.generation, bool)
            or self.generation < 0
        ):
            raise MerkleIntegrityError("generation must be a non-negative integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "root_cid": self.root_cid,
            "generation": self.generation,
            "transition_cid": self.transition_cid,
            "campaign_id": self.campaign_id,
            "campaign_root": self.campaign_root,
            "required_set_completeness": self.required_set_completeness,
            "seal_manifest_cid": self.seal_manifest_cid,
        }


@dataclass(frozen=True, slots=True)
class MerkleRootCommitResult:
    """Outcome of CAS-publishing a campaign Merkle root."""

    status: AssuranceStoreStatus
    before: MerkleRootSnapshot
    after: MerkleRootSnapshot
    root_cid: str | None
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    operation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, AssuranceStoreStatus):
            raise MerkleIntegrityError("status must be an AssuranceStoreStatus")
        validate_reason_code(self.reason_code)
        if not isinstance(self.local_durable, bool):
            raise MerkleIntegrityError("local_durable must be a boolean")
        if not isinstance(self.operation_id, str) or not self.operation_id:
            raise MerkleIntegrityError("operation_id must be a nonempty string")


@dataclass(frozen=True, slots=True)
class MerkleSetPersistResult:
    """Outcome of persisting a single set commitment block."""

    set_cid: str
    set_kind: MerkleSetKind
    set_root: str
    member_count: int
    local_durable: bool
    operation_id: str


@dataclass(frozen=True, slots=True)
class SealManifestPersistResult:
    """Outcome of signature-gated seal-manifest persistence."""

    seal_manifest_cid: str
    seal_status: SealAvailabilityStatus
    seal_available: bool
    required_set_completeness: bool
    local_durable: bool
    operation_id: str


@dataclass(frozen=True, slots=True)
class BenchmarkArtifactPersistResult:
    """Outcome of durable benchmark artifact persistence."""

    artifact_cid: str
    benchmark_id: str
    local_durable: bool
    operation_id: str


def _status_from_wire(value: object) -> AssuranceStoreStatus:
    if not isinstance(value, str):
        raise MerkleIntegrityError("status must be a string")
    try:
        return AssuranceStoreStatus(value)
    except ValueError as exc:
        raise MerkleIntegrityError(f"unknown store status: {value!r}") from exc


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class AssuranceCampaignMerkleRepository(Protocol):
    """Closed durable campaign Merkle / seal / benchmark repository surface."""

    def current_merkle_root(self, workspace: str) -> MerkleRootSnapshot: ...

    def commit_campaign_roots(
        self,
        workspace: str,
        *,
        campaign_id: str,
        set_commitments: Mapping[str, str],
        expected_generation: int,
        expected_root_cid: Optional[str],
        operation_id: str,
        seal_manifest_cid: Optional[str] = None,
    ) -> MerkleRootCommitResult: ...

    def publish_seal_manifest(
        self,
        workspace: str,
        *,
        campaign_id: str,
        campaign_root_cid: str,
        set_cids: Mapping[str, str],
        seal_status: SealAvailabilityStatus | str,
        seal_evidence_cid: Optional[str],
        receipt_cid: Optional[str],
        benchmark_artifact_cids: Sequence[str],
        operation_id: str,
    ) -> SealManifestPersistResult: ...


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class DurableAssuranceCampaignMerkleRepository:
    """Durable campaign Merkle roots, seal manifests, and benchmark artifacts.

    Implements ``AssuranceCampaignMerkleRepository@1``.
    """

    def __init__(
        self,
        store: DurableCoordinationStore,
        *,
        artifacts: DurableAssuranceArtifactStore | None = None,
    ) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store
        self._artifacts = artifacts or DurableAssuranceArtifactStore(store)
        self._owns_artifacts = artifacts is None

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    @property
    def artifacts(self) -> DurableAssuranceArtifactStore:
        return self._artifacts

    def close(self) -> None:
        if self._owns_artifacts:
            self._artifacts.close()

    def __enter__(self) -> "DurableAssuranceCampaignMerkleRepository":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _merkle_namespace(self, workspace: str) -> str:
        try:
            workspace = validate_assurance_workspace(workspace)
            return assurance_namespace(workspace, AssuranceNamespaceRole.MERKLE)
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Signature gate for Merkle / seal inputs
    # ------------------------------------------------------------------

    def _require_durable_cid(self, cid: str, name: str) -> bytes:
        try:
            cid = validate_semantic_dag_json_cid(cid, name)
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        try:
            data = self._store.get_bytes(cid)
        except ArtifactNotFound as exc:
            raise MerkleAdmissionError(
                f"{name} {cid} is not durable"
            ) from exc
        except ArtifactIntegrityError as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        if cid_for_bytes(data, "dag-json") != cid:
            raise MerkleAdmissionError(
                f"{name} {cid} bytes do not match CID"
            )
        return data

    def _gate_signed_receipt_mapping(
        self, payload: Mapping[str, Any], *, context: str
    ) -> dict[str, Any]:
        """Signature-verify a signed receipt before Merkle/seal/persist use.

        Runs before content addressing of any structure that includes the
        receipt and before any durable write that embeds it.
        """

        if not isinstance(payload, Mapping):
            raise MerkleAdmissionError(
                f"{context}: signed receipt payload must be a mapping"
            )
        schema = payload.get("schema")
        if schema == ASSURANCE_CAMPAIGN_RECEIPT_SCHEMA:
            try:
                return admit_campaign_receipt_payload(payload)
            except Exception as exc:
                raise MerkleAdmissionError(
                    f"unverified or invalid signed receipt rejected before "
                    f"{context}: {exc}"
                ) from exc
        if schema == ASSURANCE_POLICY_PROMOTION_RECEIPT_SCHEMA:
            try:
                require_verified_signature_gate(payload)
                sealed = seal_assurance_artifact(
                    AssuranceArtifactKind.ASSURANCE_POLICY_PROMOTION_RECEIPT,
                    payload,
                    enforce_signature_gate=True,
                )
            except (
                AssuranceArtifactAdmissionError,
                AssuranceArtifactStoreContractError,
                AssuranceArtifactError,
            ) as exc:
                raise MerkleAdmissionError(
                    f"unverified or invalid signed receipt rejected before "
                    f"{context}: {exc}"
                ) from exc
            signature = sealed.get("signature")
            if not isinstance(signature, Mapping):
                raise MerkleAdmissionError(
                    f"{context}: promotion receipt signature binding is required"
                )
            status = signature.get("signature_verification_status")
            if status != SignatureVerificationStatus.VERIFIED.value:
                raise MerkleAdmissionError(
                    f"unverified signed receipt rejected before {context} "
                    f"(status={status!r})"
                )
            audience = signature.get("audience")
            if audience != REQUIRED_RECEIPT_AUDIENCE:
                raise MerkleAdmissionError(
                    f"wrong-audience receipt rejected before {context}: "
                    f"expected {REQUIRED_RECEIPT_AUDIENCE!r}, got {audience!r}"
                )
            return sealed
        raise MerkleAdmissionError(
            f"{context}: payload schema is not a signed receipt"
        )

    def _gate_member_cid(self, cid: str, *, context: str) -> None:
        """Ensure a member CID is durable; signature-gate signed receipts first."""

        data = self._require_durable_cid(cid, "member_cid")
        try:
            raw = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Non-JSON dag-json is still a valid leaf if CID matched bytes.
            return
        if not isinstance(raw, Mapping):
            return
        schema = raw.get("schema")
        if schema in _SIGNED_RECEIPT_SCHEMAS:
            # Signature verification occurs before Merkle inclusion.
            self._gate_signed_receipt_mapping(raw, context=context)

    def _gate_optional_receipt_cid(
        self, receipt_cid: Optional[str], *, context: str
    ) -> Optional[Mapping[str, Any]]:
        if receipt_cid is None:
            return None
        data = self._require_durable_cid(receipt_cid, "receipt_cid")
        try:
            raw = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MerkleAdmissionError(
                f"{context}: receipt_cid is not a JSON mapping"
            ) from exc
        if not isinstance(raw, Mapping):
            raise MerkleAdmissionError(
                f"{context}: receipt_cid must decode to a mapping"
            )
        schema = raw.get("schema")
        if schema not in _SIGNED_RECEIPT_SCHEMAS:
            raise MerkleAdmissionError(
                f"{context}: receipt_cid is not a signed assurance receipt"
            )
        return self._gate_signed_receipt_mapping(raw, context=context)

    # ------------------------------------------------------------------
    # Benchmark artifacts
    # ------------------------------------------------------------------

    def persist_benchmark_artifact(
        self,
        workspace: str,
        *,
        campaign_id: str,
        benchmark_id: str,
        artifact_cids: Sequence[str],
        summary: str,
        expected_cid: str,
        operation_id: str,
    ) -> BenchmarkArtifactPersistResult:
        """Persist an immutable benchmark artifact block."""

        sealed = build_benchmark_artifact(
            workspace=workspace,
            campaign_id=campaign_id,
            benchmark_id=benchmark_id,
            artifact_cids=artifact_cids,
            summary=summary,
            operation_id=operation_id,
        )
        # Constituent CIDs must already be durable (and signature-gated if signed).
        for cid in sealed["artifact_cids"]:
            self._gate_member_cid(
                cid, context="benchmark artifact membership"
            )

        actual = cid_for_benchmark_artifact(sealed)
        try:
            expected_cid = validate_semantic_dag_json_cid(
                expected_cid, "expected_cid"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        if actual != expected_cid:
            raise MerkleIntegrityError(
                f"forged or mismatched benchmark CID: computed {actual}, "
                f"expected {expected_cid}"
            )

        try:
            put_result = self._store.put(
                sealed,
                expected_cid=expected_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        if str(put_result["cid"]) != expected_cid:
            raise MerkleIntegrityError(
                f"store returned unexpected CID {put_result['cid']!r}"
            )
        return BenchmarkArtifactPersistResult(
            artifact_cid=expected_cid,
            benchmark_id=str(sealed["benchmark_id"]),
            local_durable=True,
            operation_id=str(sealed["operation_id"]),
        )

    def get_verified_benchmark_artifact(self, cid: str) -> Mapping[str, Any]:
        try:
            cid = validate_semantic_dag_json_cid(cid, "cid")
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        try:
            raw = self._store.get(cid)
        except ArtifactNotFound as exc:
            raise MerkleIntegrityError(f"benchmark artifact {cid} is missing") from exc
        except ArtifactIntegrityError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        if not isinstance(raw, Mapping):
            raise MerkleIntegrityError(
                f"benchmark artifact {cid} is not a mapping"
            )
        try:
            sealed = admit_benchmark_artifact(raw)
        except MerkleAdmissionError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        if cid_for_benchmark_artifact(sealed) != cid:
            raise MerkleIntegrityError(
                f"benchmark artifact CID mismatch for {cid}"
            )
        return MappingProxyType(sealed)

    # ------------------------------------------------------------------
    # Set commitments
    # ------------------------------------------------------------------

    def commit_merkle_set(
        self,
        workspace: str,
        *,
        campaign_id: str,
        set_kind: MerkleSetKind | str,
        member_cids: Sequence[str],
        expected_cid: str,
        operation_id: str,
    ) -> MerkleSetPersistResult:
        """Persist a per-set Merkle commitment after gating every member.

        Signature verification for any signed receipt member runs before the
        set is content-addressed or written.
        """

        # Gate members before building the commitment (before content addressing).
        ordered_preview = _sorted_unique_cids(
            list(member_cids), "member_cids", maximum=MAX_SET_MEMBERS
        )
        kind = coerce_merkle_set_kind(set_kind)
        for cid in ordered_preview:
            self._gate_member_cid(
                cid,
                context=f"merkle set inclusion ({kind.value})",
            )

        sealed = build_merkle_set_commitment(
            workspace=workspace,
            campaign_id=campaign_id,
            set_kind=kind,
            member_cids=ordered_preview,
            operation_id=operation_id,
        )
        actual = cid_for_merkle_set(sealed)
        try:
            expected_cid = validate_semantic_dag_json_cid(
                expected_cid, "expected_cid"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        if actual != expected_cid:
            raise MerkleIntegrityError(
                f"forged or mismatched set CID: computed {actual}, "
                f"expected {expected_cid}"
            )

        try:
            put_result = self._store.put(
                sealed,
                expected_cid=expected_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        if str(put_result["cid"]) != expected_cid:
            raise MerkleIntegrityError(
                f"store returned unexpected CID {put_result['cid']!r}"
            )
        return MerkleSetPersistResult(
            set_cid=expected_cid,
            set_kind=kind,
            set_root=str(sealed["set_root"]),
            member_count=int(sealed["member_count"]),
            local_durable=True,
            operation_id=str(sealed["operation_id"]),
        )

    def get_verified_merkle_set(self, cid: str) -> Mapping[str, Any]:
        try:
            cid = validate_semantic_dag_json_cid(cid, "cid")
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        try:
            raw = self._store.get(cid)
        except ArtifactNotFound as exc:
            raise MerkleIntegrityError(f"merkle set {cid} is missing") from exc
        except ArtifactIntegrityError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        if not isinstance(raw, Mapping):
            raise MerkleIntegrityError(f"merkle set {cid} is not a mapping")
        try:
            sealed = admit_merkle_set_commitment(raw)
        except MerkleAdmissionError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        if cid_for_merkle_set(sealed) != cid:
            raise MerkleIntegrityError(f"merkle set CID mismatch for {cid}")
        # Re-gate signed members on verified read.
        for member in sealed["member_cids"]:
            self._gate_member_cid(
                str(member), context="verified merkle set membership"
            )
        return MappingProxyType(sealed)

    # ------------------------------------------------------------------
    # Campaign roots
    # ------------------------------------------------------------------

    def current_merkle_root(self, workspace: str) -> MerkleRootSnapshot:
        """Return the currently visible campaign Merkle root head (gen 0 if empty)."""

        namespace = self._merkle_namespace(workspace)
        try:
            root = self._store.current_state_root(namespace)
        except ArtifactIntegrityError as exc:
            raise MerkleIntegrityError(str(exc)) from exc

        generation = int(root["revision"])
        root_cid = root.get("root_cid")
        transition_cid = root.get("transition_cid")
        if generation == 0 or root_cid is None:
            return MerkleRootSnapshot(
                namespace=str(root["namespace"]),
                root_cid=None,
                generation=0,
                transition_cid=None,
                campaign_id=None,
                campaign_root=None,
                required_set_completeness=None,
                seal_manifest_cid=None,
            )

        sealed = self.get_verified_campaign_merkle_root(str(root_cid))
        return MerkleRootSnapshot(
            namespace=str(root["namespace"]),
            root_cid=str(root_cid),
            generation=generation,
            transition_cid=None if transition_cid is None else str(transition_cid),
            campaign_id=str(sealed["campaign_id"]),
            campaign_root=str(sealed["campaign_root"]),
            required_set_completeness=bool(sealed["required_set_completeness"]),
            seal_manifest_cid=sealed.get("seal_manifest_cid"),
        )

    def get_verified_campaign_merkle_root(self, root_cid: str) -> Mapping[str, Any]:
        try:
            root_cid = validate_semantic_dag_json_cid(root_cid, "root_cid")
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        try:
            raw = self._store.get(root_cid)
        except ArtifactNotFound as exc:
            raise MerkleIntegrityError(
                f"campaign merkle root {root_cid} is missing"
            ) from exc
        except ArtifactIntegrityError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        if not isinstance(raw, Mapping):
            raise MerkleIntegrityError(
                f"campaign merkle root {root_cid} is not a mapping"
            )
        try:
            sealed = admit_campaign_merkle_root(raw)
        except MerkleAdmissionError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        if cid_for_campaign_merkle_root(sealed) != root_cid:
            raise MerkleIntegrityError(
                f"campaign merkle root CID mismatch for {root_cid}"
            )
        return MappingProxyType(sealed)

    def commit_campaign_roots(
        self,
        workspace: str,
        *,
        campaign_id: str,
        set_commitments: Mapping[str, str],
        expected_generation: int,
        expected_root_cid: Optional[str],
        operation_id: str,
        seal_manifest_cid: Optional[str] = None,
    ) -> MerkleRootCommitResult:
        """CAS-publish a campaign Merkle root over the required sets.

        Requires required-set completeness.  Each set commitment is re-loaded
        and re-verified; every member (including signed receipts) is
        signature-gated before the root is content-addressed or CAS-published.
        """

        namespace = self._merkle_namespace(workspace)
        try:
            expected_generation, expected_root_cid = validate_generation_expectation(
                expected_generation, expected_root_cid
            )
            operation_id = validate_operation_id(operation_id)
            workspace_token = validate_assurance_workspace(workspace)
            campaign_id = validate_campaign_id(campaign_id)
        except (AssuranceArtifactStoreContractError, ValueError) as exc:
            raise MerkleAdmissionError(str(exc)) from exc

        if not isinstance(set_commitments, Mapping):
            raise MerkleAdmissionError("set_commitments must be a mapping")

        # Build ordered set entries from durable set-commitment CIDs.
        entries: list[dict[str, Any]] = []
        seen_kinds: set[str] = set()
        for raw_kind, raw_cid in set_commitments.items():
            kind = coerce_merkle_set_kind(raw_kind)
            if kind.value in seen_kinds:
                raise MerkleAdmissionError(
                    f"duplicate set commitment for {kind.value!r}"
                )
            seen_kinds.add(kind.value)
            try:
                set_cid = validate_semantic_dag_json_cid(
                    raw_cid, f"set_commitments[{kind.value}]"
                )
            except AssuranceArtifactStoreContractError as exc:
                raise MerkleAdmissionError(str(exc)) from exc
            verified = self.get_verified_merkle_set(set_cid)
            if str(verified["set_kind"]) != kind.value:
                raise MerkleAdmissionError(
                    f"set commitment kind mismatch for {kind.value!r}: "
                    f"block declares {verified['set_kind']!r}"
                )
            if str(verified.get("workspace")) != workspace_token:
                raise MerkleAdmissionError(
                    "set commitment workspace does not match commit workspace"
                )
            if str(verified.get("campaign_id")) != campaign_id:
                raise MerkleAdmissionError(
                    "set commitment campaign_id does not match commit campaign_id"
                )
            entries.append(
                {
                    "set_kind": kind.value,
                    "set_cid": set_cid,
                    "set_root": str(verified["set_root"]),
                    "member_count": int(verified["member_count"]),
                }
            )

        missing = [
            kind.value
            for kind in REQUIRED_MERKLE_SET_KINDS
            if kind.value not in seen_kinds
        ]
        if missing:
            raise MerkleAdmissionError(
                "required-set completeness failed; missing "
                + ", ".join(missing)
            )
        unknown = sorted(seen_kinds - _REQUIRED_SET_VALUE_SET)
        if unknown:
            raise MerkleAdmissionError(
                "set_commitments has unknown " + ", ".join(unknown)
            )

        if seal_manifest_cid is not None:
            # Seal manifests are re-verified and may embed a receipt that must
            # already have passed the signature gate at publish time.
            seal = self.get_verified_seal_manifest(seal_manifest_cid)
            if str(seal.get("workspace")) != workspace_token:
                raise MerkleAdmissionError(
                    "seal manifest workspace does not match commit workspace"
                )
            if str(seal.get("campaign_id")) != campaign_id:
                raise MerkleAdmissionError(
                    "seal manifest campaign_id does not match commit campaign_id"
                )

        if expected_generation == 0:
            previous_root_cid: Optional[str] = None
        else:
            assert expected_root_cid is not None
            prior = self.get_verified_campaign_merkle_root(expected_root_cid)
            if str(prior.get("workspace")) != workspace_token:
                raise MerkleAdmissionError(
                    "prior merkle root workspace does not match commit workspace"
                )
            previous_root_cid = expected_root_cid

        sealed = build_campaign_merkle_root(
            workspace=workspace_token,
            campaign_id=campaign_id,
            generation=expected_generation + 1,
            set_entries=entries,
            previous_root_cid=previous_root_cid,
            seal_manifest_cid=seal_manifest_cid,
            operation_id=operation_id,
            require_complete=True,
        )
        root_cid = cid_for_campaign_merkle_root(sealed)

        try:
            put_result = self._store.put(
                sealed,
                expected_cid=root_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        if str(put_result["cid"]) != root_cid:
            raise MerkleIntegrityError(
                f"store returned unexpected root CID {put_result['cid']!r}"
            )

        try:
            raw = self._store.compare_and_swap_state_root(
                namespace,
                expected_revision=expected_generation,
                expected_root_cid=expected_root_cid,
                new_root_cid=root_cid,
                operation_id=operation_id,
            )
        except ArtifactNotFound:
            before = self._empty_or_current(workspace, namespace)
            return MerkleRootCommitResult(
                AssuranceStoreStatus.UNAVAILABLE,
                before,
                before,
                None,
                None,
                "successor_unavailable",
                False,
                operation_id,
            )
        except ArtifactIntegrityError:
            before = self._empty_or_current(workspace, namespace)
            return MerkleRootCommitResult(
                AssuranceStoreStatus.CORRUPT,
                before,
                before,
                None,
                None,
                "integrity_failure",
                False,
                operation_id,
            )
        except ValueError as exc:
            raise MerkleAdmissionError(str(exc)) from exc

        return self._root_result_from_wire(
            raw, operation_id=operation_id, root_cid=root_cid
        )

    # ------------------------------------------------------------------
    # Seal manifests
    # ------------------------------------------------------------------

    def publish_seal_manifest(
        self,
        workspace: str,
        *,
        campaign_id: str,
        campaign_root_cid: str,
        set_cids: Mapping[str, str],
        seal_status: SealAvailabilityStatus | str,
        seal_evidence_cid: Optional[str],
        receipt_cid: Optional[str],
        benchmark_artifact_cids: Sequence[str],
        expected_cid: str,
        operation_id: str,
    ) -> SealManifestPersistResult:
        """Persist a seal manifest after signature-gating any receipt input.

        Signature verification for ``receipt_cid`` (when provided) runs before
        the seal manifest is content-addressed or written.  Required-set
        completeness and explicit seal availability/status are recorded on the
        sealed form.
        """

        # Gate receipt before building / content-addressing the seal.
        self._gate_optional_receipt_cid(
            receipt_cid, context="seal manifest input"
        )

        # Verify campaign root exists and re-seals.
        root = self.get_verified_campaign_merkle_root(campaign_root_cid)
        try:
            workspace_token = validate_assurance_workspace(workspace)
            campaign_id = validate_campaign_id(campaign_id)
        except (AssuranceArtifactStoreContractError, ValueError) as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        if str(root.get("workspace")) != workspace_token:
            raise MerkleAdmissionError(
                "campaign root workspace does not match seal workspace"
            )
        if str(root.get("campaign_id")) != campaign_id:
            raise MerkleAdmissionError(
                "campaign root campaign_id does not match seal campaign_id"
            )
        if not bool(root.get("required_set_completeness")):
            raise MerkleAdmissionError(
                "seal manifest requires a complete campaign merkle root"
            )

        # Re-verify each set CID and gate members (including signed receipts).
        if not isinstance(set_cids, Mapping):
            raise MerkleAdmissionError("set_cids must be a mapping")
        verified_set_cids: dict[str, str] = {}
        for raw_kind, raw_cid in set_cids.items():
            kind = coerce_merkle_set_kind(raw_kind)
            try:
                set_cid = validate_semantic_dag_json_cid(
                    raw_cid, f"set_cids[{kind.value}]"
                )
            except AssuranceArtifactStoreContractError as exc:
                raise MerkleAdmissionError(str(exc)) from exc
            verified = self.get_verified_merkle_set(set_cid)
            if str(verified["set_kind"]) != kind.value:
                raise MerkleAdmissionError(
                    f"set_cids kind mismatch for {kind.value!r}"
                )
            verified_set_cids[kind.value] = set_cid

        # Benchmark CIDs must be durable verified benchmark artifacts.
        for cid in benchmark_artifact_cids:
            self.get_verified_benchmark_artifact(str(cid))

        if seal_evidence_cid is not None:
            self._require_durable_cid(seal_evidence_cid, "seal_evidence_cid")

        sealed = build_seal_manifest(
            workspace=workspace_token,
            campaign_id=campaign_id,
            campaign_root_cid=campaign_root_cid,
            set_cids=verified_set_cids,
            seal_status=seal_status,
            seal_evidence_cid=seal_evidence_cid,
            receipt_cid=receipt_cid,
            benchmark_artifact_cids=benchmark_artifact_cids,
            operation_id=operation_id,
        )
        actual = cid_for_seal_manifest(sealed)
        try:
            expected_cid = validate_semantic_dag_json_cid(
                expected_cid, "expected_cid"
            )
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        if actual != expected_cid:
            raise MerkleIntegrityError(
                f"forged or mismatched seal manifest CID: computed {actual}, "
                f"expected {expected_cid}"
            )

        try:
            put_result = self._store.put(
                sealed,
                expected_cid=expected_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise MerkleAdmissionError(str(exc)) from exc
        if str(put_result["cid"]) != expected_cid:
            raise MerkleIntegrityError(
                f"store returned unexpected CID {put_result['cid']!r}"
            )
        return SealManifestPersistResult(
            seal_manifest_cid=expected_cid,
            seal_status=coerce_seal_availability_status(sealed["seal_status"]),
            seal_available=bool(sealed["seal_available"]),
            required_set_completeness=bool(sealed["required_set_completeness"]),
            local_durable=True,
            operation_id=str(sealed["operation_id"]),
        )

    def get_verified_seal_manifest(self, cid: str) -> Mapping[str, Any]:
        try:
            cid = validate_semantic_dag_json_cid(cid, "cid")
        except AssuranceArtifactStoreContractError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        try:
            raw = self._store.get(cid)
        except ArtifactNotFound as exc:
            raise MerkleIntegrityError(f"seal manifest {cid} is missing") from exc
        except ArtifactIntegrityError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        if not isinstance(raw, Mapping):
            raise MerkleIntegrityError(f"seal manifest {cid} is not a mapping")
        try:
            sealed = admit_seal_manifest(raw)
        except MerkleAdmissionError as exc:
            raise MerkleIntegrityError(str(exc)) from exc
        if cid_for_seal_manifest(sealed) != cid:
            raise MerkleIntegrityError(f"seal manifest CID mismatch for {cid}")
        # Re-gate receipt on verified read so unverified receipts never surface
        # as successful seal inputs after restart.
        self._gate_optional_receipt_cid(
            sealed.get("receipt_cid"),
            context="verified seal manifest receipt",
        )
        return MappingProxyType(sealed)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _empty_or_current(
        self, workspace: str, namespace: str
    ) -> MerkleRootSnapshot:
        try:
            return self.current_merkle_root(workspace)
        except MerkleStoreError:
            return MerkleRootSnapshot(
                namespace, None, 0, None, None, None, None, None
            )

    def _root_result_from_wire(
        self,
        raw: Mapping[str, Any],
        *,
        operation_id: str,
        root_cid: str,
    ) -> MerkleRootCommitResult:
        status = _status_from_wire(raw.get("status"))
        before_raw = raw["before"]
        after_raw = raw["after"]

        def _snap(row: Mapping[str, Any]) -> MerkleRootSnapshot:
            gen = int(row["revision"])
            cid = row.get("root_cid")
            transition = row.get("transition_cid")
            if gen == 0 or cid is None:
                return MerkleRootSnapshot(
                    namespace=str(row["namespace"]),
                    root_cid=None,
                    generation=0,
                    transition_cid=None,
                    campaign_id=None,
                    campaign_root=None,
                    required_set_completeness=None,
                    seal_manifest_cid=None,
                )
            sealed = self.get_verified_campaign_merkle_root(str(cid))
            return MerkleRootSnapshot(
                namespace=str(row["namespace"]),
                root_cid=str(cid),
                generation=gen,
                transition_cid=None if transition is None else str(transition),
                campaign_id=str(sealed["campaign_id"]),
                campaign_root=str(sealed["campaign_root"]),
                required_set_completeness=bool(
                    sealed["required_set_completeness"]
                ),
                seal_manifest_cid=sealed.get("seal_manifest_cid"),
            )

        before = _snap(before_raw)
        after = _snap(after_raw)
        transition_cid = raw.get("transition_cid")
        if transition_cid is not None:
            try:
                transition_cid = validate_semantic_dag_json_cid(
                    transition_cid, "transition_cid"
                )
            except AssuranceArtifactStoreContractError as exc:
                raise MerkleIntegrityError(str(exc)) from exc
        reason_code = raw.get("reason_code")
        if not isinstance(reason_code, str):
            raise MerkleIntegrityError("reason_code must be a string")
        local_durable = bool(raw.get("local_durable"))
        wire_op = raw.get("operation_id", operation_id)
        if not isinstance(wire_op, str):
            wire_op = operation_id
        result_root_cid: str | None
        if status is AssuranceStoreStatus.UPDATED:
            result_root_cid = root_cid
        elif status is AssuranceStoreStatus.UNCHANGED:
            result_root_cid = after.root_cid
        else:
            result_root_cid = None
        return MerkleRootCommitResult(
            status,
            before,
            after,
            result_root_cid,
            transition_cid,
            reason_code,
            local_durable,
            wire_op,
        )


__all__ = [
    "MERKLE_MODULE_INTERFACE",
    "MERKLE_SET_INTERFACE",
    "MERKLE_SET_SCHEMA",
    "CAMPAIGN_MERKLE_ROOT_INTERFACE",
    "CAMPAIGN_MERKLE_ROOT_SCHEMA",
    "SEAL_MANIFEST_INTERFACE",
    "SEAL_MANIFEST_SCHEMA",
    "BENCHMARK_ARTIFACT_INTERFACE",
    "BENCHMARK_ARTIFACT_SCHEMA",
    "REQUIRED_MERKLE_SET_KINDS",
    "REQUIRED_MERKLE_SET_KIND_VALUES",
    "MAX_SET_MEMBERS",
    "MAX_BENCHMARK_ARTIFACT_CIDS",
    "MerkleSetKind",
    "MerkleStoreError",
    "MerkleAdmissionError",
    "MerkleIntegrityError",
    "MerkleConflictError",
    "MerkleRootSnapshot",
    "MerkleRootCommitResult",
    "MerkleSetPersistResult",
    "SealManifestPersistResult",
    "BenchmarkArtifactPersistResult",
    "AssuranceCampaignMerkleRepository",
    "DurableAssuranceCampaignMerkleRepository",
    "coerce_merkle_set_kind",
    "merkle_set_kinds",
    "coerce_seal_availability_status",
    "seal_availability_statuses",
    "seal_available_for_status",
    "validate_benchmark_id",
    "compute_member_set_root",
    "compute_campaign_root_digest",
    "build_merkle_set_commitment",
    "cid_for_merkle_set",
    "admit_merkle_set_commitment",
    "build_campaign_merkle_root",
    "cid_for_campaign_merkle_root",
    "admit_campaign_merkle_root",
    "build_seal_manifest",
    "cid_for_seal_manifest",
    "admit_seal_manifest",
    "build_benchmark_artifact",
    "cid_for_benchmark_artifact",
    "admit_benchmark_artifact",
]
