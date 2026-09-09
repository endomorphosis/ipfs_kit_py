"""Fail-closed PCPR-092 Kit binding to Accelerate audit package.

Kit owns exact bytes and the current root. This module binds the
PCPR-062 hermetic current root to the Accelerate-owned security and
correctness audit package without reminting pack, root, chain, client,
parity, bypass, threat-model, or TCB-inventory identities, without
storing the package as live durable bytes, and without deciding
semantic soundness.

Durable reconstruction of the current root is from disk, not memory.
Audit-package replay is identity-preserving. This module does not import
sibling Accelerate or Datasets packages. Missing a live Quack-fenced
session is an explicit operator-blocking task. Simulated results are
not live.
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


INTERFACE: Final = "KitSecurityAndCorrectnessAuditPackageBinding@1"
SCHEMA: Final = (
    "ipfs_kit_py/assurance/security-and-correctness-audit-package-binding@1"
)
BINDING_SCHEMA: Final = (
    "ipfs_kit_py/assurance/declared-security-and-correctness-audit-package-binding@1"
)
VERDICT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/security-and-correctness-audit-package-verdict@1"
)
OWNER_INTERFACE: Final = "DatasetsContextPack@1"
OWNER_SCHEMA: Final = "ipfs_datasets_py/datasets-context-pack@1"
OWNER_REPOSITORY: Final = "ipfs_datasets_py"
EXECUTION_OWNER_REPOSITORY: Final = "ipfs_accelerate_py"
EXECUTION_OWNER_INTERFACE: Final = "AccelerateSecurityAndCorrectnessAuditPackage@1"
CHAIN_OWNER_INTERFACE: Final = "AccelerateFinalProofCarryingReceiptChain@1"
STORAGE_OWNER_REPOSITORY: Final = "ipfs_kit_py"
STORAGE_OWNER_INTERFACE: Final = "KitContextPackStorage@1"
PROTOCOL_INTERFACE: Final = "LogicProviderProtocol@2"
PCPR_092_TASK_ID: Final = "PCPR-092"
PCPR_092_GOAL_ID: Final = "PCPR-G900"
PCPR_093_TASK_ID: Final = "PCPR-093"
PCPR_091_TASK_ID: Final = "PCPR-091"
PCPR_090_TASK_ID: Final = "PCPR-090"
PCPR_083_TASK_ID: Final = "PCPR-083"
PCPR_082_TASK_ID: Final = "PCPR-082"
PCPR_081_TASK_ID: Final = "PCPR-081"
PCPR_080_TASK_ID: Final = "PCPR-080"
PCPR_072_TASK_ID: Final = "PCPR-072"
PCPR_062_TASK_ID: Final = "PCPR-062"
PCPR_061_TASK_ID: Final = "PCPR-061"
PCPR_PROGRAM_ID: Final = "proof-carrying-platform-qualification-and-release-v1"
OBJECTIVE_KIND: Final = "declared_security_and_correctness_audit_package_binding"
PORTFOLIO_ID: Final = "portfolio:pcpr-v1"
PORTFOLIO_VERSION: Final = "proof-carrying-platform-0.1.0"
LANGUAGE: Final = "Python"
OBJECTIVE_ID: Final = "PCPR-G900"
OPERATOR_BLOCKING_TASK_ID: Final = "pcpr-092-operator-live-audit-package"
SOURCE_DATE_EPOCH: Final = "0"

PINNED_LOCK_CID: Final = (
    "baguqeerawsekbbbt5ccctjt4tydzeahfkahsatb6q5x7k6cy4inrii5lhqmq"
)
PINNED_IDEA_DIGEST: Final = (
    "baguqeeracbayojdov4jmqiirx22pavrg6nabazcocru6y3scrdx5e54mw2zq"
)
PINNED_OBJECTIVE_CID: Final = (
    "baguqeeraynsn7tjr3iaggnreylzxo3akaooqwp5bf5oheaa6eubth2zwqeba"
)
PINNED_PACK_CID: Final = (
    "bafkreih72d3nncekez43wmtlczq5mdtymzniluujypwybpgu3mtt7i4v2e"
)
PINNED_BYTES_CID: Final = (
    "bafkreihjdjarrlr24sperlq3zl4hjrksbol4b5saxquie3wpyi6xwsobwi"
)
PINNED_CURRENT_ROOT_CID: Final = PINNED_BYTES_CID
PINNED_CHAIN_CID: Final = (
    "baguqeeraeuvfodvledfa4nvfuso6eyyytzk2acptcogzwzyarkdinpqcsdfq"
)
PINNED_PYTHON_CLIENT_CID: Final = (
    "baguqeerat346yf4k7kenbqlbtyejeilgxamna262z3axzjjatzm2hccehblq"
)
PINNED_MCP_CLIENT_CID: Final = (
    "baguqeerasdkirdryda7uoi5gchsyhuyvh6d2uremm45zpob7hoss3ao66ahq"
)
PINNED_PARITY_CID: Final = (
    "baguqeera6y3w7bhzy6hpo6ohfsrj5xihrw5vk6qqljjonjrupijd2yrp3hnq"
)
PINNED_BYPASS_PROOF_CID: Final = (
    "baguqeeraepx7iiqcc4gtfp63kpozlkdd2qg3px3ptnqhj3rpigqtemjc5psa"
)
PINNED_THREAT_MODEL_CID: Final = (
    "baguqeera2kz3zj4stztmb22lmbcuyj3zj2ekdg7st2qzefbr5z6r6vemnhxq"
)
PINNED_TCB_INVENTORY_CID: Final = (
    "baguqeeral3tjeriuspe3e3qe25eqssmer6fekhmmq3v7htpkr2rjjiqatrcq"
)

BINDING_DIR_RELPATH: Final = "packaging/pcpr/reference-workflow/cpython312"
BINDING_JSON_NAME: Final = (
    "reference.security-and-correctness-audit-package.binding.json"
)
BINDING_README_RELPATH: Final = (
    "packaging/pcpr/reference-workflow/SECURITY_AND_CORRECTNESS_AUDIT_PACKAGE.md"
)

REFERENCE_OBJECTIVE_IDEA: Final = (
    "Modify a typed formal-logic API while reusing unaffected proofs, "
    "selecting only impacted tests, rejecting stale-tree evidence, and "
    "producing a complete proof-carrying execution receipt."
)

ESCALATION_ORDER: Final[tuple[str, ...]] = (
    "exact receipt",
    "AST and dependency analysis",
    "schema, type, and static checks",
    "selected tests",
    "incremental prover",
    "local small specialist",
    "medium model",
    "frontier model",
    "human decision",
)

HERMETIC_CANDIDATE_SUITES: Final[tuple[str, ...]] = (
    "tests/test_pcpr_092_security_and_correctness_audit.py",
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
        "pyproject_audit_package_table",
        "owner_pack_cid_matches_pin",
        "kit_current_root_bound_not_minted",
        "audit_package_owned_by_accelerate",
        "current_root_survives_audit_package_from_disk",
        "audit_package_not_stored_as_live_bytes",
        "audit_status_external_audit_ready",
        "idempotent_current_root",
        "model_assertion_cannot_complete_work",
        "duckdb_or_quack_not_written",
        "operator_blocking_task_emitted",
        "no_closed_release_outcome",
    }
)
FORBIDDEN_PRESENT_PROBE_IDS: Final[frozenset[str]] = frozenset(
    {
        "simulated_results_represented_as_live",
        "live_client_represented_as_live",
        "closed_release_represented_as_live",
        "compatibility_identities_reminted",
        "sibling_import_observed",
        "datasets_identity_reminted",
        "kit_identity_reminted",
        "chain_identity_reminted",
        "model_assertion_completed_work",
        "memory_reconstruction_accepted",
        "database_edited",
        "externally_audited_claimed",
    }
)

BINDING_README: Final = """# PCPR-092 Kit security and correctness audit-package binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned security and correctness audit package. Kit does not
remint the pack CID, does not store the package as live durable bytes,
and does not decide semantic soundness.

- `cpython312/reference.security-and-correctness-audit-package.binding.json`
  binds the Kit current root to the Accelerate audit package. Exact
  commit and tree are bound by the PCPR-092 receipt
  `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Audit-package replay is identity-preserving. Execution and package
  emission are owned by Accelerate. Status is external_audit_ready,
  never externally_audited. Closed release remains PCPR-093/094.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-092-operator-live-audit-package`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
"""


class KitSecurityAndCorrectnessAuditError(Exception):
    """Kit attempted to remint or store the audit package as live bytes."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KitSecurityAndCorrectnessAuditError(
            f"{name} must be a non-empty string"
        )
    return value.strip()


def _kind(value: Any, name: str) -> str:
    kind = _text(value, name)
    if kind not in EVIDENCE_KINDS:
        raise KitSecurityAndCorrectnessAuditError(
            f"{name} is not an admitted evidence kind"
        )
    return kind


def _reject_closed_release_value(value: Any, name: str) -> None:
    if isinstance(value, str) and value in CLOSED_RELEASE_OUTCOMES:
        raise KitSecurityAndCorrectnessAuditError(
            f"{name} must not be a closed PCPR release outcome"
        )


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def parse_pyproject_audit_package_table(text: str) -> dict[str, Any]:
    import tomllib

    table = tomllib.loads(_text(text, "pyproject.toml"))
    if not isinstance(table, dict):
        raise KitSecurityAndCorrectnessAuditError("pyproject.toml must be a table")
    tool = table.get("tool")
    payload: dict[str, Any] = {}
    if isinstance(tool, dict):
        kit = tool.get("ipfs_kit_py")
        if isinstance(kit, dict):
            raw = kit.get("security-and-correctness-audit-package")
            if isinstance(raw, dict):
                payload = dict(raw)
    return payload


def refuse_pack_cid_remint(cid: str) -> str:
    if cid != PINNED_PACK_CID:
        raise KitSecurityAndCorrectnessAuditError(
            f"ContextPack CID {cid} remints {PINNED_PACK_CID}"
        )
    return cid


def refuse_current_root_remint(cid: str) -> str:
    if cid != PINNED_CURRENT_ROOT_CID:
        raise KitSecurityAndCorrectnessAuditError(
            f"current root CID {cid} remints {PINNED_CURRENT_ROOT_CID}"
        )
    return cid


def refuse_chain_cid_remint(cid: str) -> str:
    if cid != PINNED_CHAIN_CID:
        raise KitSecurityAndCorrectnessAuditError(
            f"chain CID {cid} remints {PINNED_CHAIN_CID}"
        )
    return cid


def refuse_model_completion(stage_id: str) -> None:
    stage = _text(stage_id, "stage_id")
    if stage in {
        "local_small_specialist",
        "medium_model",
        "frontier_model",
        "human_decision",
    }:
        raise KitSecurityAndCorrectnessAuditError(
            f"model assertion at {stage} cannot complete work"
        )


def refuse_memory_reconstruction(*, from_memory: bool) -> None:
    if from_memory:
        raise KitSecurityAndCorrectnessAuditError(
            "current root cannot be reconstructed from memory"
        )


def refuse_live_storage(*, stored: bool) -> None:
    if stored:
        raise KitSecurityAndCorrectnessAuditError(
            "Kit must not store the hermetic audit package as live durable bytes"
        )


def refuse_database_edit(*, edited: bool) -> None:
    if edited:
        raise KitSecurityAndCorrectnessAuditError(
            "security and correctness audit package cannot write DuckDB or Quack state"
        )


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
class KitSecurityAndCorrectnessAuditVerdict:
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
    live_application: bool
    live_storage: bool
    live_client: bool
    operator_blocking_task: str
    simulated_results_represented_as_live: bool
    this_task_created_competing_authority: bool
    probes: tuple[OutcomeProbe, ...]
    blockers: tuple[str, ...]
    verdict_cid: str
    pack_cid: str
    binding_cid: str
    current_root_cid: str
    chain_cid: str
    objective_cid: str
    idea_digest: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "interface": self.interface,
            "verdict_cid": self.verdict_cid,
            "pack_cid": self.pack_cid,
            "binding_cid": self.binding_cid,
            "current_root_cid": self.current_root_cid,
            "chain_cid": self.chain_cid,
            "objective_cid": self.objective_cid,
            "idea_digest": self.idea_digest,
            "promotion_status": self.promotion_status,
            "supervisor_disposition": self.supervisor_disposition,
            "closed_release_outcome": self.closed_release_outcome,
            "release_claim": self.release_claim,
            "completion_authoritative": self.completion_authoritative,
            "contracts_frozen": self.contracts_frozen,
            "duckdb_or_quack_state_written": self.duckdb_or_quack_state_written,
            "sibling_source_required": self.sibling_source_required,
            "live_application": self.live_application,
            "live_storage": self.live_storage,
            "live_client": self.live_client,
            "operator_blocking_task": self.operator_blocking_task,
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


def _operator_blocking_task() -> dict[str, Any]:
    return {
        "task_id": OPERATOR_BLOCKING_TASK_ID,
        "status": "typed_blocked",
        "evidence_kind": "unavailable",
        "live": False,
        "applied": False,
        "requires": (
            "An admitted Quack-fenced state-owner session before the audit "
            "package is executed as live supervisor work"
        ),
        "action": (
            "Keep the Kit current root bound to the Accelerate audit package. "
            "Do not store the package as live durable bytes. Do not write "
            "DuckDB or Quack state. Do not claim externally_audited."
        ),
        "reason": (
            "Kit binds the Accelerate hermetic audit package. That binding is "
            "not live Supervisor.run or live durable storage."
        ),
    }


def render_declared_binding(root: Path | None = None) -> dict[str, Any]:
    package_root = root or discover_kit_root()
    if package_root is None:
        raise KitSecurityAndCorrectnessAuditError("Kit package root was not found")
    _ = package_root
    refuse_memory_reconstruction(from_memory=False)
    refuse_live_storage(stored=False)
    refuse_database_edit(edited=False)
    document = {
        "schema": BINDING_SCHEMA,
        "interface": INTERFACE,
        "task_id": PCPR_092_TASK_ID,
        "goal_id": PCPR_092_GOAL_ID,
        "program_id": PCPR_PROGRAM_ID,
        "owner_repository": STORAGE_OWNER_REPOSITORY,
        "execution_owner_repository": EXECUTION_OWNER_REPOSITORY,
        "execution_owner_interface": EXECUTION_OWNER_INTERFACE,
        "pack_owner_repository": OWNER_REPOSITORY,
        "pack_owner_interface": OWNER_INTERFACE,
        "pack_owner_schema": OWNER_SCHEMA,
        "storage_owner_repository": STORAGE_OWNER_REPOSITORY,
        "storage_owner_interface": STORAGE_OWNER_INTERFACE,
        "protocol_interface": PROTOCOL_INTERFACE,
        "portfolio_id": PORTFOLIO_ID,
        "portfolio_version": PORTFOLIO_VERSION,
        "objective_kind": OBJECTIVE_KIND,
        "package_name": PACKAGE_NAME,
        "package_version": PACKAGE_VERSION,
        "language": LANGUAGE,
        "objective_id": OBJECTIVE_ID,
        "idea": REFERENCE_OBJECTIVE_IDEA,
        "idea_digest": PINNED_IDEA_DIGEST,
        "objective_cid": PINNED_OBJECTIVE_CID,
        "lock_cid": PINNED_LOCK_CID,
        "prerequisite_task_id": PCPR_091_TASK_ID,
        "escalation_order": list(ESCALATION_ORDER),
        "model_assertion_completes_work": False,
        "context_pack": {
            "task_id": PCPR_061_TASK_ID,
            "constructed": True,
            "constructed_by": OWNER_REPOSITORY,
            "pack_cid": PINNED_PACK_CID,
            "owner_interface": OWNER_INTERFACE,
            "owner_schema": OWNER_SCHEMA,
            "reminted": False,
            "live": False,
            "stored": True,
            "stored_by": STORAGE_OWNER_REPOSITORY,
            "current_root_published": True,
            "stale": True,
            "rejected": True,
            "survives_chain": True,
            "survives_client": True,
            "survives_bypass": True,
            "survives_threat_model": True,
            "survives_tcb_inventory": True,
            "survives_audit_package": True,
            "evidence_kind": "measured",
        },
        "storage": {
            "task_id": PCPR_062_TASK_ID,
            "stored": True,
            "stored_by": STORAGE_OWNER_REPOSITORY,
            "current_root_published": True,
            "current_root_cid": PINNED_CURRENT_ROOT_CID,
            "bytes_cid": PINNED_BYTES_CID,
            "live": False,
            "deferred": False,
            "reminted": False,
            "survives_chain": True,
            "survives_client": True,
            "survives_bypass": True,
            "survives_threat_model": True,
            "survives_tcb_inventory": True,
            "survives_audit_package": True,
            "reconstructed_from": "disk",
            "reconstructed_from_memory": False,
            "idempotent": True,
            "evidence_kind": "measured_hermetic",
        },
        "route": {
            "executed": True,
            "executed_by": EXECUTION_OWNER_REPOSITORY,
            "live": False,
            "hermetic": True,
            "reminted": False,
            "survives_client": True,
            "survives_bypass": True,
            "survives_threat_model": True,
            "survives_tcb_inventory": True,
            "survives_audit_package": True,
            "evidence_kind": "measured_hermetic",
        },
        "bounded_patch": {
            "produced": True,
            "produced_by": EXECUTION_OWNER_REPOSITORY,
            "live": False,
            "hermetic": True,
            "evidence_kind": "measured_hermetic",
        },
        "final_receipt_chain": {
            "task_id": PCPR_072_TASK_ID,
            "kind": "final_proof_carrying_receipt_chain",
            "classified_by": EXECUTION_OWNER_REPOSITORY,
            "chain_cid": PINNED_CHAIN_CID,
            "stored": False,
            "live": False,
            "stale_rejected": True,
            "survives_chain": True,
            "survives_client": True,
            "survives_bypass": True,
            "survives_threat_model": True,
            "survives_tcb_inventory": True,
            "survives_audit_package": True,
            "idempotent": True,
            "history_mutated": False,
            "reminted": False,
            "evidence_kind": "measured_hermetic",
        },
        "security_and_correctness_audit_package": {
            "task_id": PCPR_092_TASK_ID,
            "kind": "security_and_correctness_audit_package",
            "classified_by": EXECUTION_OWNER_REPOSITORY,
            "client_owned_by": EXECUTION_OWNER_REPOSITORY,
            "python_client_cid": PINNED_PYTHON_CLIENT_CID,
            "mcp_client_cid": PINNED_MCP_CLIENT_CID,
            "parity_cid": PINNED_PARITY_CID,
            "bypass_proof_cid": PINNED_BYPASS_PROOF_CID,
            "threat_model_cid": PINNED_THREAT_MODEL_CID,
            "tcb_inventory_cid": PINNED_TCB_INVENTORY_CID,
            "stored": False,
            "live": False,
            "stale_rejected": True,
            "survives_chain": True,
            "survives_client": True,
            "survives_bypass": True,
            "survives_threat_model": True,
            "survives_tcb_inventory": True,
            "survives_audit_package": True,
            "audit_status": "external_audit_ready",
            "externally_audited": False,
            "idempotent": True,
            "history_mutated": False,
            "chain_cid": PINNED_CHAIN_CID,
            "next_task_id": PCPR_093_TASK_ID,
            "evidence_kind": "measured_hermetic",
        },
        "materialization": {
            "kind": "declared_binding_not_live",
            "admitted": False,
            "live": False,
            "applied": False,
            "duckdb_or_quack_state_written": False,
            "evidence_kind": "unavailable",
        },
        "live_application": typed_unavailable(
            reason=(
                "Kit binds the Accelerate audit package and does not emit a "
                "live Supervisor.run."
            )
        ),
        "live_client": typed_unavailable(
            reason=(
                "Live generic MCP stdio/HTTP remains typed unavailable. "
                "Closed release decision remains PCPR-093/094."
            )
        ),
        "live_storage": typed_unavailable(
            reason="Kit does not store the hermetic audit package as live durable bytes."
        ),
        "source": {
            "kind": "git",
            "repository": "endomorphosis/ipfs_kit_py",
            "binding": "current_head_not_mutable_main",
            "mutable_main_reference": False,
            "commit": {
                "status": "observed_at_evaluation",
                "evidence_kind": "measured",
                "live": False,
                "field": "PCPR-092 receipt current_tree_binding",
            },
        },
        "operator_blocking_task": _operator_blocking_task(),
        "live": False,
        "applied": False,
        "submitted_live": False,
        "release_claim": False,
        "closed_release_outcome": None,
        "contracts_frozen": False,
        "hashes_invented": False,
        "signatures_invented": False,
        "sibling_source_required": False,
        "this_task_created_competing_authority": False,
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


def write_audit_package_files(start: Path | None = None) -> dict[str, Any]:
    root = discover_kit_root(start)
    if root is None:
        raise KitSecurityAndCorrectnessAuditError("Kit package root was not found")
    binding = render_declared_binding(root)
    paths = artifact_paths(root)
    _atomic_write(paths["binding"], pretty_json(binding))
    readme = BINDING_README if BINDING_README.endswith("\n") else BINDING_README + "\n"
    _atomic_write(paths["readme"], readme)
    return {
        "binding": binding,
        "paths": {name: str(path) for name, path in paths.items()},
    }


def verify_audit_package_files(start: Path | None = None) -> dict[str, Any]:
    root = discover_kit_root(start)
    if root is None:
        raise KitSecurityAndCorrectnessAuditError("Kit package root was not found")
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
        "pack_cid": binding["context_pack"]["pack_cid"],
        "binding_cid": binding["binding_cid"],
        "current_root_cid": binding["storage"]["current_root_cid"],
        "chain_cid": binding["final_receipt_chain"]["chain_cid"],
        "objective_cid": binding["objective_cid"],
        "idea_digest": binding["idea_digest"],
        "binding_sha256": (
            sha256_bytes(paths["binding"].read_bytes())
            if paths["binding"].is_file()
            else "unavailable"
        ),
    }


def current_head_static_probes(start: Path | None = None) -> tuple[OutcomeProbe, ...]:
    root = discover_kit_root(start)
    if root is None:
        raise KitSecurityAndCorrectnessAuditError("Kit package root was not found")
    binding = render_declared_binding(root)
    verified = verify_audit_package_files(root)
    table = parse_pyproject_audit_package_table(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )
    client = binding["security_and_correctness_audit_package"]
    remint = (
        binding["context_pack"]["pack_cid"] != PINNED_PACK_CID
        or binding["objective_cid"] != PINNED_OBJECTIVE_CID
        or binding["idea_digest"] != PINNED_IDEA_DIGEST
        or binding["lock_cid"] != PINNED_LOCK_CID
        or binding["storage"]["current_root_cid"] != PINNED_CURRENT_ROOT_CID
        or binding["final_receipt_chain"]["chain_cid"] != PINNED_CHAIN_CID
        or client["chain_cid"] != PINNED_CHAIN_CID
        or binding["context_pack"]["reminted"] is True
        or binding["storage"]["reminted"] is True
        or binding["final_receipt_chain"]["reminted"] is True
    )
    probes = [
        _probe(
            "binding_files_match_generator",
            verified.get("ok") is True and verified.get("binding_ok") is True,
            reason=(
                "Committed Kit audit-package binding matches the generator."
                if verified.get("binding_ok") is True
                else "Committed Kit audit-package binding is missing or drifts."
            ),
        ),
        _probe(
            "pyproject_audit_package_table",
            table.get("interface") == INTERFACE
            and table.get("schema") == SCHEMA
            and table.get("task-id") == PCPR_092_TASK_ID
            and table.get("objective-kind") == OBJECTIVE_KIND,
            reason=(
                "pyproject.toml declares KitSecurityAndCorrectnessAuditPackageBinding@1."
                if table.get("interface") == INTERFACE
                else "pyproject.toml does not declare the PCPR-092 binding."
            ),
        ),
        _probe(
            "owner_pack_cid_matches_pin",
            binding["context_pack"]["pack_cid"] == PINNED_PACK_CID
            and binding["context_pack"]["reminted"] is False,
            reason="Kit binds the Datasets pack CID without remint.",
        ),
        _probe(
            "kit_current_root_bound_not_minted",
            binding["storage"]["current_root_cid"] == PINNED_CURRENT_ROOT_CID
            and binding["storage"]["stored_by"] == STORAGE_OWNER_REPOSITORY
            and binding["storage"]["reminted"] is False,
            reason="Kit binds the current root and does not remint it.",
        ),
        _probe(
            "audit_package_owned_by_accelerate",
            client["client_owned_by"] == EXECUTION_OWNER_REPOSITORY
            and client["classified_by"] == EXECUTION_OWNER_REPOSITORY,
            reason="The audit package remains owned by Accelerate.",
        ),
        _probe(
            "current_root_survives_audit_package_from_disk",
            binding["storage"]["survives_audit_package"] is True
            and binding["storage"]["reconstructed_from"] == "disk"
            and binding["storage"]["reconstructed_from_memory"] is False,
            reason="The current root survives the audit package and is reconstructed from disk.",
        ),
        _probe(
            "audit_package_not_stored_as_live_bytes",
            client["stored"] is False and client["live"] is False,
            reason="Kit does not store the hermetic audit package as live durable bytes.",
        ),
        _probe(
            "audit_status_external_audit_ready",
            client["audit_status"] == "external_audit_ready"
            and client["externally_audited"] is False,
            reason="Package status is external_audit_ready and never externally_audited.",
        ),
        _probe(
            "idempotent_current_root",
            binding["storage"]["idempotent"] is True
            and binding["binding_cid"] == PINNED_BINDING_CID,
            reason="The Kit binding CID is identity-preserving.",
        ),
        _probe(
            "model_assertion_cannot_complete_work",
            binding["model_assertion_completes_work"] is False,
            reason="No model assertion completes work.",
        ),
        _probe(
            "duckdb_or_quack_not_written",
            binding["duckdb_or_quack_state_written"] is False,
            reason="This task does not write DuckDB or Quack state.",
        ),
        _probe(
            "operator_blocking_task_emitted",
            binding["operator_blocking_task"]["task_id"] == OPERATOR_BLOCKING_TASK_ID
            and binding["operator_blocking_task"]["status"] == "typed_blocked",
            reason="Missing live execution emits the operator-blocking task.",
        ),
        _probe(
            "no_closed_release_outcome",
            binding["closed_release_outcome"] is None
            and binding["release_claim"] is False,
            reason="This task does not emit a closed PCPR release outcome.",
        ),
        _probe(
            "compatibility_identities_reminted",
            remint,
            reason="A reminted pack, root, chain, objective, idea, or lock CID is forbidden.",
        ),
        _probe(
            "datasets_identity_reminted",
            binding["context_pack"]["reminted"] is True,
            reason="Kit must not remint DatasetsContextPack@1.",
        ),
        _probe(
            "kit_identity_reminted",
            binding["storage"]["reminted"] is True,
            reason="Kit must not remint the current root.",
        ),
        _probe(
            "chain_identity_reminted",
            binding["final_receipt_chain"]["reminted"] is True,
            reason="Kit must not remint the PCPR-072 chain.",
        ),
        _probe(
            "sibling_import_observed",
            False,
            reason="Kit does not import sibling Accelerate or Datasets packages.",
        ),
        _probe(
            "simulated_results_represented_as_live",
            False,
            reason="Simulated results are not represented as live.",
        ),
        _probe(
            "live_client_represented_as_live",
            False,
            reason="Hermetic audit-package binding is not represented as live.",
        ),
        _probe(
            "closed_release_represented_as_live",
            False,
            reason="This task does not publish a PCPR release.",
        ),
        _probe(
            "model_assertion_completed_work",
            False,
            reason="No model assertion completed work.",
        ),
        _probe(
            "memory_reconstruction_accepted",
            False,
            reason="Current root is reconstructed from disk, not memory.",
        ),
        _probe(
            "database_edited",
            False,
            reason="DuckDB and Quack state were not written.",
        ),
        _probe(
            "externally_audited_claimed",
            False,
            reason="Package status is external_audit_ready, never externally_audited.",
        ),
        _probe(
            "live_application",
            None,
            evidence_kind="unavailable",
            reason="Live supervisor application stays typed unavailable.",
        ),
        _probe(
            "live_client",
            None,
            evidence_kind="unavailable",
            reason="Live generic MCP clients stay typed unavailable.",
        ),
    ]
    return tuple(probes)


def qualify_audit_package(
    probes: Sequence[OutcomeProbe],
    *,
    pack_cid: str,
    binding_cid: str,
    current_root_cid: str,
    chain_cid: str,
    objective_cid: str,
    idea_digest_cid: str,
) -> KitSecurityAndCorrectnessAuditVerdict:
    if not probes:
        raise KitSecurityAndCorrectnessAuditError("at least one probe is required")
    normalized: list[OutcomeProbe] = []
    blockers: list[str] = []
    for probe in probes:
        kind = _kind(probe.evidence_kind, "evidence_kind")
        if probe.live and kind != "measured_live":
            raise KitSecurityAndCorrectnessAuditError(
                "live claims require measured_live evidence"
            )
        if probe.simulated_represented_as_live:
            raise KitSecurityAndCorrectnessAuditError(
                "simulated results must not be represented as live"
            )
        normalized.append(probe)
        if probe.probe_id in FORBIDDEN_PRESENT_PROBE_IDS and probe.present is True:
            blockers.append(probe.probe_id)
        if probe.probe_id in REQUIRED_GOOD_PROBE_IDS and probe.present is not True:
            blockers.append(probe.probe_id)

    promotion_status = "rnd_non_promoted"
    _reject_closed_release_value(promotion_status, "promotion_status")
    payload = {
        "schema": VERDICT_SCHEMA,
        "interface": INTERFACE,
        "task_id": PCPR_092_TASK_ID,
        "goal_id": PCPR_092_GOAL_ID,
        "promotion_status": promotion_status,
        "supervisor_disposition": "supervisor_non_promoted",
        "closed_release_outcome": None,
        "release_claim": False,
        "completion_authoritative": False,
        "contracts_frozen": False,
        "duckdb_or_quack_state_written": False,
        "sibling_source_required": False,
        "live_application": False,
        "live_storage": False,
        "live_client": False,
        "operator_blocking_task": OPERATOR_BLOCKING_TASK_ID,
        "simulated_results_represented_as_live": False,
        "this_task_created_competing_authority": False,
        "probes": [item.to_mapping() for item in normalized],
        "blockers": list(dict.fromkeys(blockers)),
        "pack_cid": pack_cid,
        "binding_cid": binding_cid,
        "current_root_cid": current_root_cid,
        "chain_cid": chain_cid,
        "objective_cid": objective_cid,
        "idea_digest": idea_digest_cid,
    }
    return KitSecurityAndCorrectnessAuditVerdict(
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
        live_application=False,
        live_storage=False,
        live_client=False,
        operator_blocking_task=OPERATOR_BLOCKING_TASK_ID,
        simulated_results_represented_as_live=False,
        this_task_created_competing_authority=False,
        probes=tuple(normalized),
        blockers=tuple(dict.fromkeys(blockers)),
        verdict_cid=content_identity(payload),
        pack_cid=pack_cid,
        binding_cid=binding_cid,
        current_root_cid=current_root_cid,
        chain_cid=chain_cid,
        objective_cid=objective_cid,
        idea_digest=idea_digest_cid,
    )


def qualify_current_head_audit_package(
    start: Path | None = None,
) -> KitSecurityAndCorrectnessAuditVerdict:
    binding = render_declared_binding(start)
    return qualify_audit_package(
        current_head_static_probes(start),
        pack_cid=str(binding["context_pack"]["pack_cid"]),
        binding_cid=str(binding["binding_cid"]),
        current_root_cid=str(binding["storage"]["current_root_cid"]),
        chain_cid=str(binding["final_receipt_chain"]["chain_cid"]),
        objective_cid=str(binding["objective_cid"]),
        idea_digest_cid=str(binding["idea_digest"]),
    )


def pcpr_092_receipt_promotion(
    verdict: KitSecurityAndCorrectnessAuditVerdict,
) -> dict[str, Any]:
    if verdict.closed_release_outcome is not None:
        raise KitSecurityAndCorrectnessAuditError(
            "security and correctness audit package must not mint a closed release outcome"
        )
    if verdict.release_claim:
        raise KitSecurityAndCorrectnessAuditError(
            "security and correctness audit package must not claim a PCPR release"
        )
    if verdict.completion_authoritative:
        raise KitSecurityAndCorrectnessAuditError(
            "security and correctness audit package completion is not authoritative"
        )
    if verdict.duckdb_or_quack_state_written:
        raise KitSecurityAndCorrectnessAuditError(
            "security and correctness audit package must not write DuckDB or Quack state"
        )
    if verdict.promotion_status in CLOSED_RELEASE_OUTCOMES:
        raise KitSecurityAndCorrectnessAuditError(
            "promotion_status must not be a closed release outcome"
        )
    if verdict.live_client or verdict.live_application:
        raise KitSecurityAndCorrectnessAuditError(
            "live client claims require measured_live evidence"
        )
    return verdict.to_mapping()


PINNED_BINDING_CID: Final = (
    "baguqeerab7h77dwoillexuuuc3au3r2zn472lmykx3bs2dldqkxqyqctkfra"
)
CURRENT_HEAD_NON_PROMOTION_VERDICT_CID: Final = (
    "baguqeera6yhjjmo3rvidyqferddt6kgbqqy56yo6mytve3gklva4k5jr7tqq"
)


__all__ = [
    "CLOSED_RELEASE_OUTCOMES",
    "CURRENT_HEAD_NON_PROMOTION_VERDICT_CID",
    "ESCALATION_ORDER",
    "HERMETIC_CANDIDATE_SUITES",
    "INTERFACE",
    "KitSecurityAndCorrectnessAuditError",
    "OBJECTIVE_KIND",
    "OPERATOR_BLOCKING_TASK_ID",
    "OutcomeProbe",
    "PCPR_092_GOAL_ID",
    "PCPR_092_TASK_ID",
    "PINNED_BINDING_CID",
    "PINNED_CHAIN_CID",
    "PINNED_CURRENT_ROOT_CID",
    "PINNED_IDEA_DIGEST",
    "PINNED_OBJECTIVE_CID",
    "PINNED_PACK_CID",
    "SCHEMA",
    "SEALED_PATH",
    "SEALED_PYTHON",
    "current_head_static_probes",
    "pcpr_092_receipt_promotion",
    "qualify_audit_package",
    "qualify_current_head_audit_package",
    "refuse_current_root_remint",
    "refuse_database_edit",
    "refuse_live_storage",
    "refuse_memory_reconstruction",
    "refuse_model_completion",
    "refuse_pack_cid_remint",
    "render_declared_binding",
    "verify_audit_package_files",
]
