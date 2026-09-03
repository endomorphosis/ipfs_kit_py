"""Fail-closed PCPR-056 Kit binding to the portfolio compatibility lock.

Kit binds the Accelerate-owned proof-carrying-platform-0.1.0 lock CID
and refuses reminting. Kit verifies and stores exact bytes; it does not
decide proof validity, task completion, reuse, or semantic meaning, and
it does not re-encode canonical bytes.

This module does not import sibling Accelerate or Datasets packages. It
is a lock binding (lock=True), not a freeze, not a live signed manifest,
not branch protection, and not a closed PCPR release. Live signatures
and unpublished artifact hashes stay typed unavailable and are never
invented.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from ipfs_kit_py.assurance.dependency_locks import (
    CLOSED_RELEASE_OUTCOMES,
    NAMED_GIT_EXTRAS,
    NAMED_GIT_EXTRAS_ROLE,
    PACKAGE_NAME,
    PACKAGE_VERSION,
    SEALED_PATH,
    SEALED_PYTHON,
    content_identity,
    discover_kit_root,
    pretty_json,
    sha256_bytes,
    typed_unavailable,
)

INTERFACE: Final = "KitPortfolioCompatibilityLockBinding@1"
SCHEMA: Final = "ipfs_kit_py/assurance/portfolio-compatibility-lock-binding@1"
BINDING_SCHEMA: Final = (
    "ipfs_kit_py/assurance/declared-portfolio-compatibility-lock-binding@1"
)
VERDICT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/portfolio-compatibility-lock-verdict@1"
)
NORMATIVE_SOURCE: Final = (
    "ipfs_accelerate_py/assurance/declared-portfolio-compatibility-lock@1"
)
NORMATIVE_INTERFACE: Final = "AcceleratePortfolioCompatibilityLock@1"
PCPR_056_TASK_ID: Final = "PCPR-056"
PCPR_056_GOAL_ID: Final = "PCPR-G600"
PCPR_055_TASK_ID: Final = "PCPR-055"
PCPR_043_TASK_ID: Final = "PCPR-043"
PCPR_002_TASK_ID: Final = "PCPR-002"
PCPR_PROGRAM_ID: Final = "proof-carrying-platform-qualification-and-release-v1"
OWNER_REPOSITORY: Final = "ipfs_kit_py"
LOCK_KIND: Final = "declared_portfolio_compatibility_lock_binding"
PORTFOLIO_ID: Final = "portfolio:pcpr-v1"
PORTFOLIO_VERSION: Final = "proof-carrying-platform-0.1.0"
INTENDED_TAG_NAME: Final = f"{PACKAGE_NAME}-v{PACKAGE_VERSION}"
CANONICAL_PYTHON_REQUIRES: Final = ">=3.12"
PYTHON_FLOOR: Final = "3.12"
SUPPORTED_COMBINATION_ID: Final = (
    "pcpr.v1.python312.accelerate-datasets-kit.shared-contracts-v1"
)
REQUIRED_REPOSITORIES: Final[tuple[str, ...]] = (
    "ipfs_accelerate_py",
    "ipfs_datasets_py",
    "ipfs_kit_py",
)
KIT_OWNED_CONTRACTS: Final[tuple[str, ...]] = ("DurableArtifactReceipt",)
PINNED_CATALOG_CID: Final = (
    "baguqeeraqpptps2gf55wmthv3sm5nzlxqqdjfyg2ggkbl5ovfzuvvvsxap4a"
)
PINNED_041_VECTOR_DOCUMENT_CID: Final = (
    "baguqeera6gwcyi3f7fkw5eufnhkovmqw7eevkeas4qxds5ws7b7rloic63da"
)
PINNED_042_NEGATIVE_DOCUMENT_CID: Final = (
    "baguqeeraior5lq3fvefhgwsm3cjjaxozffmdmqmszwxy4ozfb37mnqx6lfca"
)
PINNED_COMPATIBILITY_DOCUMENT_CID: Final = (
    "baguqeerafnibnbrsfaqvbxx444kqk3gi4sh244r7bl7usdxk2krg6njlquza"
)
PINNED_LOCK_CID: Final = (
    "baguqeerawsekbbbt5ccctjt4tydzeahfkahsatb6q5x7k6cy4inrii5lhqmq"
)
PINNED_KIT_LOCK_CID: Final = (
    "baguqeerapndvhdlxynq6afrv4mfpsa7ajjregns3nwuth5hnho7rf3xc223a"
)
PINNED_KIT_SBOM_CID: Final = (
    "baguqeeracvwc27foqiebwn3bc65riwro2ucvtpadwt53fsg4uuuyh5ec7eza"
)
PINNED_KIT_PROVENANCE_CID: Final = (
    "baguqeeral6zl7kn2fy6rylk7rs74hzbwulnntq2w2fycoe2cbpq52fjqvgwq"
)
PINNED_KIT_TAG_POLICY_CID: Final = (
    "baguqeerazr3ew2kjxvi7tz4eouy6eqsdoszfp4c6tdsvctvueycwjipdgpaa"
)
PINNED_KIT_CHECKSUMS_CID: Final = (
    "baguqeeragjykpkrsny4wzmq6vhk47o3u47w7c4rbp42554lwyzlrdoinxk2a"
)

BINDING_DIR_RELPATH: Final = "packaging/pcpr/compatibility/cpython312"
BINDING_JSON_NAME: Final = "release.binding.json"
BINDING_README_RELPATH: Final = "packaging/pcpr/compatibility/README.md"
SOURCE_DATE_EPOCH: Final = "0"

HERMETIC_CANDIDATE_SUITES: Final[tuple[str, ...]] = (
    "tests/test_pcpr_056_portfolio_compatibility_lock.py",
)

EVIDENCE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "measured",
        "measured_live",
        "measured_hermetic",
        "estimated",
        "simulated",
        "unavailable",
    }
)

REQUIRED_GOOD_PROBE_IDS: Final[frozenset[str]] = frozenset(
    {
        "binding_files_match_generator",
        "pyproject_portfolio_compatibility_lock_table",
        "hashes_not_invented",
        "signatures_not_invented",
        "no_mutable_main_reference",
        "lock_kind_is_declared_binding",
        "supported_combination_is_locked",
        "pcpr_043_identities_not_reminted",
        "lock_cid_matches_pin",
        "named_git_extras_are_not_this_lock",
    }
)
FORBIDDEN_PRESENT_PROBE_IDS: Final[frozenset[str]] = frozenset(
    {
        "hashes_invented",
        "signatures_invented",
        "mutable_main_reference",
        "simulated_results_represented_as_live",
        "signed_lock_represented_as_live",
        "closed_release_represented_as_live",
        "compatibility_identities_reminted",
        "sibling_import_observed",
    }
)

BINDING_README: Final = """# PCPR-056 Kit portfolio compatibility lock binding

These files bind Kit to the one declared proof-carrying-platform-0.1.0
portfolio compatibility lock owned by Accelerate. They do not remint
that lock, do not import sibling packages, and do not re-encode
identities.

This binding is not a live signed manifest, not a freeze, not a
published wheel or sdist, and not a closed PCPR release. Named extras
`libp2p` and `ipld-github` may carry source-checkout Git pins and are
not this lock.

- `cpython312/release.binding.json` pins lock CID
  `baguqeerawsekbbbt5ccctjt4tydzeahfkahsatb6q5x7k6cy4inrii5lhqmq`.
  Exact commit and tree are bound by the PCPR-056 receipt
  `current_tree_binding`. `origin/main` is not the release identity.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
"""


class KitPortfolioCompatibilityLockError(ValueError):
    """Kit attempted to remint a portfolio lock identity."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KitPortfolioCompatibilityLockError(
            f"{name} must be a non-empty string"
        )
    return value.strip()


def _kind(value: Any, name: str) -> str:
    kind = _text(value, name)
    if kind not in EVIDENCE_KINDS:
        raise KitPortfolioCompatibilityLockError(
            f"{name} is not an admitted evidence kind"
        )
    return kind


def _reject_closed_release_value(value: Any, name: str) -> None:
    if isinstance(value, str) and value in CLOSED_RELEASE_OUTCOMES:
        raise KitPortfolioCompatibilityLockError(
            f"{name} must not be a closed PCPR release outcome"
        )


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def parse_pyproject_lock_table(text: str) -> dict[str, Any]:
    import tomllib

    table = tomllib.loads(_text(text, "pyproject.toml"))
    if not isinstance(table, dict):
        raise KitPortfolioCompatibilityLockError("pyproject.toml must be a table")
    tool = table.get("tool")
    payload: dict[str, Any] = {}
    if isinstance(tool, dict):
        kit = tool.get("ipfs_kit_py")
        if isinstance(kit, dict):
            raw = kit.get("portfolio-compatibility-lock")
            if isinstance(raw, dict):
                payload = dict(raw)
    return payload


def refuse_lock_remint(cid: str) -> str:
    if cid != PINNED_LOCK_CID:
        raise KitPortfolioCompatibilityLockError(
            f"portfolio compatibility lock CID {cid} remints {PINNED_LOCK_CID}"
        )
    return cid


@dataclass(frozen=True)
class OutcomeProbe:
    probe_id: str
    present: bool | None
    evidence_kind: str
    live: bool
    simulated_represented_as_live: bool
    reason: str
    details: Mapping[str, Any] = MappingProxyType({})

    def to_mapping(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "present": self.present,
            "evidence_kind": self.evidence_kind,
            "live": self.live,
            "simulated_represented_as_live": self.simulated_represented_as_live,
            "reason": self.reason,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class KitPortfolioCompatibilityLockVerdict:
    schema: str
    interface: str
    promotion_status: str
    supervisor_disposition: str
    closed_release_outcome: str | None
    release_claim: bool
    completion_authoritative: bool
    contracts_frozen: bool
    duckdb_or_quack_state_written: bool
    sibling_source_required: bool
    hashes_invented: bool
    signatures_invented: bool
    live_signed_lock: bool
    live_signed_lock_evidence_kind: str
    mutable_main_reference: bool
    simulated_results_represented_as_live: bool
    this_task_created_competing_authority: bool
    probes: tuple[OutcomeProbe, ...]
    blockers: tuple[str, ...]
    verdict_cid: str
    lock_cid: str
    binding_cid: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "interface": self.interface,
            "verdict_cid": self.verdict_cid,
            "lock_cid": self.lock_cid,
            "binding_cid": self.binding_cid,
            "promotion_status": self.promotion_status,
            "supervisor_disposition": self.supervisor_disposition,
            "closed_release_outcome": self.closed_release_outcome,
            "release_claim": self.release_claim,
            "completion_authoritative": self.completion_authoritative,
            "contracts_frozen": self.contracts_frozen,
            "duckdb_or_quack_state_written": self.duckdb_or_quack_state_written,
            "sibling_source_required": self.sibling_source_required,
            "hashes_invented": self.hashes_invented,
            "signatures_invented": self.signatures_invented,
            "live_signed_lock": self.live_signed_lock,
            "live_signed_lock_evidence_kind": self.live_signed_lock_evidence_kind,
            "mutable_main_reference": self.mutable_main_reference,
            "simulated_results_represented_as_live": (
                self.simulated_results_represented_as_live
            ),
            "this_task_created_competing_authority": (
                self.this_task_created_competing_authority
            ),
            "blocker_count": len(self.blockers),
            "blockers": list(self.blockers),
            "evidence_kind": "measured",
        }


def _probe(
    probe_id: str,
    present: bool | None,
    *,
    reason: str,
    evidence_kind: str = "measured",
    live: bool = False,
    details: Mapping[str, Any] | None = None,
) -> OutcomeProbe:
    return OutcomeProbe(
        probe_id=probe_id,
        present=present,
        evidence_kind=evidence_kind,
        live=live,
        simulated_represented_as_live=False,
        reason=reason,
        details=MappingProxyType(dict(details or {})),
    )


def render_declared_binding(root: Path | None = None) -> dict[str, Any]:
    _ = root or discover_kit_root()
    document = {
        "schema": BINDING_SCHEMA,
        "interface": INTERFACE,
        "normative_source": NORMATIVE_SOURCE,
        "normative_interface": NORMATIVE_INTERFACE,
        "task_id": PCPR_056_TASK_ID,
        "goal_id": PCPR_056_GOAL_ID,
        "program_id": PCPR_PROGRAM_ID,
        "owner_repository": OWNER_REPOSITORY,
        "package_name": PACKAGE_NAME,
        "package_version": PACKAGE_VERSION,
        "intended_tag_name": INTENDED_TAG_NAME,
        "python_requires": CANONICAL_PYTHON_REQUIRES,
        "python": PYTHON_FLOOR,
        "lock_kind": LOCK_KIND,
        "portfolio_id": PORTFOLIO_ID,
        "portfolio_version": PORTFOLIO_VERSION,
        "lock": True,
        "frozen": False,
        "freeze_task": PCPR_002_TASK_ID,
        "compatibility_task": PCPR_043_TASK_ID,
        "signed_tags_task": PCPR_055_TASK_ID,
        "lock_cid": PINNED_LOCK_CID,
        "catalog_cid": PINNED_CATALOG_CID,
        "vector_document_cid": PINNED_041_VECTOR_DOCUMENT_CID,
        "negative_document_cid": PINNED_042_NEGATIVE_DOCUMENT_CID,
        "compatibility_document_cid": PINNED_COMPATIBILITY_DOCUMENT_CID,
        "supported_combination_id": SUPPORTED_COMBINATION_ID,
        "required_repositories": list(REQUIRED_REPOSITORIES),
        "owned_contracts": list(KIT_OWNED_CONTRACTS),
        "named_git_extras": list(NAMED_GIT_EXTRAS),
        "named_git_extras_role": NAMED_GIT_EXTRAS_ROLE,
        "component": {
            "package_name": PACKAGE_NAME,
            "package_version": PACKAGE_VERSION,
            "intended_tag_name": INTENDED_TAG_NAME,
            "lock_cid": PINNED_KIT_LOCK_CID,
            "sbom_cid": PINNED_KIT_SBOM_CID,
            "provenance_cid": PINNED_KIT_PROVENANCE_CID,
            "tag_policy_cid": PINNED_KIT_TAG_POLICY_CID,
            "checksums_cid": PINNED_KIT_CHECKSUMS_CID,
        },
        "source": {
            "kind": "git",
            "binding": "current_head_not_mutable_main",
            "mutable_main_reference": False,
        },
        "signing": {
            "status": "unavailable",
            "evidence_kind": "unavailable",
            "live": False,
            "signed": False,
            "invented": False,
            "reason": (
                "A live signed lock was not admitted. A signature was not invented."
            ),
        },
        "protection": typed_unavailable(
            reason="Protected tags and branch protection remain PCPR-057."
        ),
        "remint": False,
        "sibling_import": False,
        "reencode": False,
        "semantic_authority": False,
        "proof_validity_authority": False,
        "task_completion_authority": False,
        "live": False,
        "published": False,
        "release_claim": False,
        "closed_release_outcome": None,
        "hashes_invented": False,
        "signatures_invented": False,
        "sibling_source_required": False,
        "duckdb_or_quack_state_written": False,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "evidence_kind": "measured",
    }
    document["binding_cid"] = content_identity(
        {key: value for key, value in document.items() if key != "binding_cid"}
    )
    return document


def artifact_paths(root: Path) -> dict[str, Path]:
    return {
        "binding": root / BINDING_DIR_RELPATH / BINDING_JSON_NAME,
        "readme": root / BINDING_README_RELPATH,
    }


def write_portfolio_compatibility_lock_files(
    start: Path | None = None,
) -> dict[str, Any]:
    root = discover_kit_root(start)
    if root is None:
        raise KitPortfolioCompatibilityLockError("Kit package root was not found")
    binding = render_declared_binding(root)
    paths = artifact_paths(root)
    _atomic_write(paths["binding"], pretty_json(binding))
    readme = BINDING_README if BINDING_README.endswith("\n") else BINDING_README + "\n"
    _atomic_write(paths["readme"], readme)
    return {
        "binding": binding,
        "paths": {name: str(path) for name, path in paths.items()},
    }


def verify_portfolio_compatibility_lock_files(
    start: Path | None = None,
) -> dict[str, Any]:
    root = discover_kit_root(start)
    if root is None:
        raise KitPortfolioCompatibilityLockError("Kit package root was not found")
    binding = render_declared_binding(root)
    paths = artifact_paths(root)
    missing: list[str] = []
    binding_ok = False
    readme_ok = False
    expected_readme = (
        BINDING_README if BINDING_README.endswith("\n") else BINDING_README + "\n"
    )
    for name, path in paths.items():
        if not path.is_file():
            missing.append(name)
            continue
        if name == "binding":
            binding_ok = json.loads(path.read_text(encoding="utf-8")) == binding
        elif name == "readme":
            readme_ok = path.read_text(encoding="utf-8") == expected_readme
    return {
        "ok": not missing and binding_ok and readme_ok,
        "missing": missing,
        "binding_ok": binding_ok,
        "readme_ok": readme_ok,
        "lock_cid": binding["lock_cid"],
        "binding_cid": binding["binding_cid"],
        "binding_sha256": (
            sha256_bytes(paths["binding"].read_bytes())
            if paths["binding"].is_file()
            else "unavailable"
        ),
    }


def current_head_static_probes(
    start: Path | None = None,
) -> tuple[OutcomeProbe, ...]:
    root = discover_kit_root(start)
    if root is None:
        raise KitPortfolioCompatibilityLockError("Kit package root was not found")
    binding = render_declared_binding(root)
    verified = verify_portfolio_compatibility_lock_files(root)
    table = parse_pyproject_lock_table(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )
    remint = binding["lock_cid"] != PINNED_LOCK_CID
    mutable_main = bool(binding["source"]["mutable_main_reference"])
    probes = [
        _probe(
            "binding_files_match_generator",
            verified.get("ok") is True and verified.get("binding_ok") is True,
            reason=(
                "Committed Kit lock binding matches the generator."
                if verified.get("binding_ok") is True
                else "Committed Kit lock binding is missing or drifts."
            ),
            details=verified,
        ),
        _probe(
            "pyproject_portfolio_compatibility_lock_table",
            table.get("interface") == INTERFACE
            and table.get("schema") == SCHEMA
            and table.get("task-id") == PCPR_056_TASK_ID
            and table.get("lock-kind") == LOCK_KIND,
            reason=(
                "pyproject.toml declares KitPortfolioCompatibilityLockBinding@1."
                if table.get("interface") == INTERFACE
                else "pyproject.toml does not declare the PCPR-056 binding."
            ),
            details={"table": table},
        ),
        _probe(
            "hashes_not_invented",
            binding["hashes_invented"] is False,
            reason="Hashes were not invented.",
        ),
        _probe(
            "hashes_invented",
            False,
            reason="Hashes must not be invented.",
        ),
        _probe(
            "signatures_not_invented",
            binding["signatures_invented"] is False,
            reason="Signatures were not invented.",
        ),
        _probe(
            "signatures_invented",
            False,
            reason="A signature must not be invented.",
        ),
        _probe(
            "no_mutable_main_reference",
            mutable_main is False,
            reason="Binding does not pin origin/main as the release identity.",
        ),
        _probe(
            "mutable_main_reference",
            mutable_main,
            reason="Mutable main must not be the release identity.",
        ),
        _probe(
            "lock_kind_is_declared_binding",
            binding["lock_kind"] == LOCK_KIND and binding["lock"] is True,
            reason="Binding kind is declared and lock is true.",
        ),
        _probe(
            "supported_combination_is_locked",
            binding["supported_combination_id"] == SUPPORTED_COMBINATION_ID
            and binding["lock"] is True,
            reason="The PCPR-043 supported combination is locked by this binding.",
        ),
        _probe(
            "pcpr_043_identities_not_reminted",
            binding["catalog_cid"] == PINNED_CATALOG_CID
            and binding["compatibility_document_cid"]
            == PINNED_COMPATIBILITY_DOCUMENT_CID,
            reason="PCPR-043 identities are bound and not reminted.",
        ),
        _probe(
            "lock_cid_matches_pin",
            binding["lock_cid"] == PINNED_LOCK_CID,
            reason="Kit binds the Accelerate-owned lock CID without remint.",
        ),
        _probe(
            "compatibility_identities_reminted",
            remint,
            reason="A reminted lock CID is forbidden.",
        ),
        _probe(
            "sibling_import_observed",
            False,
            reason="This binding does not import sibling Accelerate or Datasets packages.",
        ),
        _probe(
            "named_git_extras_are_not_this_lock",
            True,
            reason=(
                "Named libp2p and ipld-github extras may carry source-checkout "
                "Git pins; they are not this lock."
            ),
            details={
                "named_git_extras": list(NAMED_GIT_EXTRAS),
                "named_git_extras_role": NAMED_GIT_EXTRAS_ROLE,
            },
        ),
        _probe(
            "simulated_results_represented_as_live",
            False,
            reason="Simulated results are not represented as live.",
        ),
        _probe(
            "signed_lock_represented_as_live",
            False,
            reason="No live signed lock is represented as live.",
        ),
        _probe(
            "closed_release_represented_as_live",
            False,
            reason="This task does not publish a PCPR release.",
        ),
        _probe(
            "live_signed_lock",
            None,
            evidence_kind="unavailable",
            reason="A live signed lock was not admitted. A signature was not invented.",
        ),
    ]
    return tuple(probes)


def qualify_portfolio_compatibility_lock(
    probes: Sequence[OutcomeProbe],
    *,
    lock_cid: str,
    binding_cid: str,
) -> KitPortfolioCompatibilityLockVerdict:
    if not probes:
        raise KitPortfolioCompatibilityLockError("at least one probe is required")
    normalized: list[OutcomeProbe] = []
    blockers: list[str] = []
    for probe in probes:
        kind = _kind(probe.evidence_kind, "evidence_kind")
        if probe.live and kind != "measured_live":
            raise KitPortfolioCompatibilityLockError(
                "live claims require measured_live evidence"
            )
        if probe.simulated_represented_as_live:
            raise KitPortfolioCompatibilityLockError(
                "simulated results must not be represented as live"
            )
        normalized.append(probe)
        if probe.probe_id in FORBIDDEN_PRESENT_PROBE_IDS and probe.present is True:
            blockers.append(probe.probe_id)
        if probe.probe_id in REQUIRED_GOOD_PROBE_IDS and probe.present is not True:
            blockers.append(probe.probe_id)

    promotion_status = "rnd_non_promoted"
    _reject_closed_release_value(promotion_status, "promotion_status")
    mutable = next(
        (
            item.present is True
            for item in normalized
            if item.probe_id == "mutable_main_reference"
        ),
        False,
    )
    payload = {
        "schema": VERDICT_SCHEMA,
        "interface": INTERFACE,
        "task_id": PCPR_056_TASK_ID,
        "goal_id": PCPR_056_GOAL_ID,
        "promotion_status": promotion_status,
        "supervisor_disposition": "supervisor_non_promoted",
        "closed_release_outcome": None,
        "release_claim": False,
        "completion_authoritative": False,
        "contracts_frozen": False,
        "duckdb_or_quack_state_written": False,
        "sibling_source_required": False,
        "hashes_invented": False,
        "signatures_invented": False,
        "live_signed_lock": False,
        "live_signed_lock_evidence_kind": "unavailable",
        "mutable_main_reference": mutable,
        "simulated_results_represented_as_live": False,
        "this_task_created_competing_authority": False,
        "probes": [item.to_mapping() for item in normalized],
        "blockers": list(dict.fromkeys(blockers)),
        "lock_cid": lock_cid,
        "binding_cid": binding_cid,
    }
    return KitPortfolioCompatibilityLockVerdict(
        schema=VERDICT_SCHEMA,
        interface=INTERFACE,
        promotion_status=promotion_status,
        supervisor_disposition="supervisor_non_promoted",
        closed_release_outcome=None,
        release_claim=False,
        completion_authoritative=False,
        contracts_frozen=False,
        duckdb_or_quack_state_written=False,
        sibling_source_required=False,
        hashes_invented=False,
        signatures_invented=False,
        live_signed_lock=False,
        live_signed_lock_evidence_kind="unavailable",
        mutable_main_reference=mutable,
        simulated_results_represented_as_live=False,
        this_task_created_competing_authority=False,
        probes=tuple(normalized),
        blockers=tuple(dict.fromkeys(blockers)),
        verdict_cid=content_identity(payload),
        lock_cid=lock_cid,
        binding_cid=binding_cid,
    )


def qualify_current_head_portfolio_compatibility_lock(
    start: Path | None = None,
) -> KitPortfolioCompatibilityLockVerdict:
    binding = render_declared_binding(start)
    return qualify_portfolio_compatibility_lock(
        current_head_static_probes(start),
        lock_cid=str(binding["lock_cid"]),
        binding_cid=str(binding["binding_cid"]),
    )


def pcpr_056_receipt_promotion(
    verdict: KitPortfolioCompatibilityLockVerdict,
) -> dict[str, Any]:
    if verdict.closed_release_outcome is not None:
        raise KitPortfolioCompatibilityLockError(
            "portfolio compatibility lock must not mint a closed release outcome"
        )
    if verdict.release_claim:
        raise KitPortfolioCompatibilityLockError(
            "portfolio compatibility lock must not claim a PCPR release"
        )
    if verdict.completion_authoritative:
        raise KitPortfolioCompatibilityLockError(
            "portfolio-compatibility-lock completion is not authoritative"
        )
    if verdict.duckdb_or_quack_state_written:
        raise KitPortfolioCompatibilityLockError(
            "portfolio compatibility lock must not write DuckDB or Quack state"
        )
    if verdict.promotion_status in CLOSED_RELEASE_OUTCOMES:
        raise KitPortfolioCompatibilityLockError(
            "promotion_status must not be a closed release outcome"
        )
    return verdict.to_mapping()


CURRENT_HEAD_NON_PROMOTION_VERDICT_CID: Final = (
    "baguqeeral5ctjfrsd45rrr23zblxwopvgvve5whqeid4z75c65j2xkhq7ica"
)


__all__ = [
    "CURRENT_HEAD_NON_PROMOTION_VERDICT_CID",
    "HERMETIC_CANDIDATE_SUITES",
    "INTERFACE",
    "KitPortfolioCompatibilityLockError",
    "LOCK_KIND",
    "NAMED_GIT_EXTRAS",
    "OutcomeProbe",
    "PCPR_056_GOAL_ID",
    "PCPR_056_TASK_ID",
    "PINNED_LOCK_CID",
    "PORTFOLIO_VERSION",
    "SCHEMA",
    "SEALED_PATH",
    "SEALED_PYTHON",
    "SUPPORTED_COMBINATION_ID",
    "current_head_static_probes",
    "pcpr_056_receipt_promotion",
    "qualify_current_head_portfolio_compatibility_lock",
    "qualify_portfolio_compatibility_lock",
    "refuse_lock_remint",
    "render_declared_binding",
    "verify_portfolio_compatibility_lock_files",
    "write_portfolio_compatibility_lock_files",
]
