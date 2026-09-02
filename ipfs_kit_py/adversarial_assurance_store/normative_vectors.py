"""Packaged Datasets assurance constructors (PCPR-025).

Kit tests and installed distributions must not walk an adjacent
``ipfs_datasets_py`` tests/ tree or a sibling checkout. These compact
recipes reconstruct the historical AAE constructors from public
``ipfs_datasets_py.logic.software_contracts.adversarial_assurance`` types.

Missing Datasets remains typed unavailable; these recipes are not live
qualification and are not a closed PCPR release.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Final

from ipfs_datasets_py.logic.software_contracts.content import cid_for_bytes
from ipfs_datasets_py.logic.software_contracts.adversarial_assurance.analysis_contracts import (
    AssuranceGap,
    AssuranceGapClass,
    GapSeverity,
    MinimizedEvidenceBinding,
    SourceSpan,
    SurvivingMutantReport,
    SurvivorRiskClass,
)
from ipfs_datasets_py.logic.software_contracts.adversarial_assurance.common import (
    ArtifactProvenance,
    AssuranceArtifactHeader,
    AssuranceTerminalStatus,
    AuthoritySource,
    ExecutionMode,
    GeneratorIdentity,
    VersionBinding,
)
from ipfs_datasets_py.logic.software_contracts.adversarial_assurance.mutation_contracts import (
    MutationCandidate,
    MutationOperatorDefinition,
    MutationRiskClass,
    MutationTarget,
    OperatorClass,
    PropertyClass,
    RollbackDeclaration,
    RollbackStrategy,
    SandboxMode,
    SandboxRequirement,
    ScopeLimits,
    SeedConfigBinding,
)
from ipfs_datasets_py.logic.software_contracts.adversarial_assurance.receipt_contracts import (
    EXISTING_SIGNATURE_ALGORITHM,
    EXISTING_SIGNATURE_AUTHORITY,
    AssuranceCampaignReceipt,
    HeldOutResult,
    ReceiptAction,
    ReceiptSignatureBinding,
    SealAvailabilityStatus,
    SealScopeItem,
    SignatureVerificationStatus,
)


VECTOR_INTERFACE: Final = "KitPackagedDatasetsAssuranceVectors@1"
VECTOR_SCHEMA: Final = "ipfs_kit_py/adversarial_assurance_store/normative-vectors@1"
SIBLING_TESTS_PACKAGE_REQUIRED: Final = False
SIBLING_CHECKOUT_REQUIRED: Final = False

_SIGNER = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"
_SIGNATURE = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def _cid(label: str) -> str:
    return cid_for_bytes(label.encode("utf-8"))


def _generator(*, generator_id: str, interface_id: str, **overrides: object) -> GeneratorIdentity:
    fields: dict[str, Any] = {
        "generator_id": generator_id,
        "generator_version": "1.0.0",
        "interface_id": interface_id,
    }
    fields.update(overrides)
    return GeneratorIdentity(**fields)  # type: ignore[arg-type]


def _versions(*, operator_id: str, generator: GeneratorIdentity, **overrides: object) -> VersionBinding:
    fields: dict[str, Any] = {
        "operator_id": operator_id,
        "operator_version": "1",
        "campaign_policy_id": "default_campaign",
        "campaign_policy_version": "1.0.0",
        "generator": generator,
    }
    fields.update(overrides)
    return VersionBinding(**fields)  # type: ignore[arg-type]


def _provenance(
    *,
    authority_source: AuthoritySource,
    tool_id: str,
    **overrides: object,
) -> ArtifactProvenance:
    fields: dict[str, Any] = {
        "producer_id": "adversarial_assurance",
        "producer_version": "1",
        "execution_mode": ExecutionMode.LIVE,
        "authority_source": authority_source,
        "input_cids": (_cid("input-a"),),
        "tool_ids": (tool_id,),
        "policy_cid": _cid("policy"),
        "notes": None,
    }
    fields.update(overrides)
    return ArtifactProvenance(**fields)  # type: ignore[arg-type]


def _header_common(
    artifact_kind: str,
    *,
    versions: VersionBinding,
    provenance: ArtifactProvenance,
    metadata: dict[str, Any],
    receipt_cids: tuple[str, ...],
    proof_cids: tuple[str, ...],
    **overrides: object,
) -> AssuranceArtifactHeader:
    fields: dict[str, Any] = {
        "artifact_kind": artifact_kind,
        "repository_id": "repository:sha256:test-repo-identity",
        "repository_state_cid": _cid("repo-state"),
        "target_symbol_ids": ("mod.fn",),
        "target_artifact_cids": (_cid("artifact-a"),),
        "capsule_cids": (_cid("capsule-a"),),
        "proof_unit_cids": (_cid("proof-unit-a"),),
        "environment_cid": _cid("environment"),
        "dependency_lock_cid": _cid("dependency-lock"),
        "versions": versions,
        "provenance": provenance,
        "terminal_status": AssuranceTerminalStatus.COMPLETE,
        "receipt_cids": receipt_cids,
        "proof_cids": proof_cids,
        "metadata": metadata,
    }
    fields.update(overrides)
    return AssuranceArtifactHeader(**fields)  # type: ignore[arg-type]


def _mutation_header(artifact_kind: str, **overrides: object) -> AssuranceArtifactHeader:
    return _header_common(
        artifact_kind,
        versions=_versions(
            operator_id="control_flow_invert",
            generator=_generator(
                generator_id="mutation_campaign",
                interface_id="generate_mutation_candidates@1",
            ),
        ),
        provenance=_provenance(
            authority_source=AuthoritySource.DETERMINISTIC,
            tool_id="mutator.v1",
        ),
        metadata={"risk_class": "local_bug"},
        receipt_cids=(_cid("receipt-a"),),
        proof_cids=(_cid("proof-a"),),
        **overrides,
    )


def _receipt_header(artifact_kind: str, **overrides: object) -> AssuranceArtifactHeader:
    return _header_common(
        artifact_kind,
        versions=_versions(
            operator_id="campaign_operator",
            generator=_generator(
                generator_id="campaign_sealer",
                interface_id="seal_campaign@1",
            ),
        ),
        provenance=_provenance(
            authority_source=AuthoritySource.RECEIPT,
            tool_id="campaign.sealer.v1",
        ),
        metadata={},
        receipt_cids=(),
        proof_cids=(),
        **overrides,
    )


def _analysis_header(artifact_kind: str, **overrides: object) -> AssuranceArtifactHeader:
    return _header_common(
        artifact_kind,
        versions=_versions(
            operator_id="control_flow_invert",
            generator=_generator(
                generator_id="gap_diagnosis",
                interface_id="diagnose_assurance_gap@1",
            ),
        ),
        provenance=_provenance(
            authority_source=AuthoritySource.OBSERVED,
            tool_id="analyzer.v1",
        ),
        metadata={"risk_class": "authorization"},
        receipt_cids=(_cid("receipt-a"),),
        proof_cids=(_cid("proof-a"),),
        **overrides,
    )


def _seed_config(**overrides: object) -> SeedConfigBinding:
    fields: dict[str, Any] = {
        "seed": 42,
        "config": {"max_depth": 2, "operator_budget": 4},
    }
    fields.update(overrides)
    return SeedConfigBinding(**fields)  # type: ignore[arg-type]


def _rollback(**overrides: object) -> RollbackDeclaration:
    fields: dict[str, Any] = {
        "strategy": RollbackStrategy.WORKTREE_DISCARD,
        "requires_clean_worktree": True,
        "preserves_production": True,
    }
    fields.update(overrides)
    return RollbackDeclaration(**fields)  # type: ignore[arg-type]


def _sandbox(**overrides: object) -> SandboxRequirement:
    fields: dict[str, Any] = {
        "mode": SandboxMode.DISPOSABLE_WORKTREE,
        "network_disabled": True,
        "production_credentials_forbidden": True,
        "disposable_worktree_required": True,
    }
    fields.update(overrides)
    return SandboxRequirement(**fields)  # type: ignore[arg-type]


def _scope(**overrides: object) -> ScopeLimits:
    fields: dict[str, Any] = {
        "max_files": 1,
        "max_symbols": 2,
        "max_span_lines": 64,
        "allow_cross_module": False,
        "allow_verifier_mutation": False,
    }
    fields.update(overrides)
    return ScopeLimits(**fields)  # type: ignore[arg-type]


def _operator(**overrides: object) -> MutationOperatorDefinition:
    fields: dict[str, Any] = {
        "operator_id": "control_flow_invert",
        "operator_version": "1",
        "operator_class": OperatorClass.CONTROL_FLOW,
        "supported_languages": ("python",),
        "supported_artifact_types": ("source_module",),
        "target_prerequisites": ("parsed_ast", "symbol_table"),
        "semantic_intent": "Invert a boolean condition controlling a branch",
        "expected_violated_property_classes": (PropertyClass.CONTROL_INVARIANT,),
        "risk_class": MutationRiskClass.LOCAL_BUG,
        "likely_equivalent_conditions": ("condition_always_true",),
        "syntactic_transformation": "replace_if_test_with_not_test",
        "scope_limits": _scope(),
        "rollback": _rollback(),
        "required_sandbox": _sandbox(),
        "max_mutants_per_target": 8,
        "deterministic": True,
        "notes": None,
        "metadata": {},
    }
    fields.update(overrides)
    return MutationOperatorDefinition(**fields)  # type: ignore[arg-type]


def _target(**overrides: object) -> MutationTarget:
    fields: dict[str, Any] = {
        "target_id": "mod_fn",
        "repository_id": "repository:sha256:test-repo-identity",
        "repository_state_cid": _cid("repo-state"),
        "symbol_ids": ("mod.fn",),
        "artifact_cids": (_cid("artifact-a"),),
        "language": "python",
        "artifact_type": "source_module",
        "prerequisites": ("parsed_ast", "symbol_table", "type_check"),
        "risk_class": MutationRiskClass.LOCAL_BUG,
        "risk_weight_bp": 2_500,
        "capsule_cids": (_cid("capsule-a"),),
        "proof_unit_cids": (_cid("proof-unit-a"),),
        "source_path": "mod.py",
        "notes": None,
        "metadata": {},
    }
    fields.update(overrides)
    return MutationTarget(**fields)  # type: ignore[arg-type]


def _candidate(**overrides: object) -> MutationCandidate:
    operator = _operator()
    target = _target()
    fields: dict[str, Any] = {
        "header": _mutation_header("mutation_candidate"),
        "candidate_id": "cand_control_flow_invert_0",
        "operator_id": operator.operator_id,
        "operator_version": operator.operator_version,
        "operator_cid": operator.operator_cid,
        "target_id": target.target_id,
        "target_cid": target.target_cid,
        "seed_config": _seed_config(),
        "source_root_cid": _cid("source-root"),
        "repository_state_cid": _cid("repo-state"),
        "transformation_summary": "invert if-test at mod.fn:12",
        "expected_violated_property_classes": (PropertyClass.CONTROL_INVARIANT,),
        "risk_class": MutationRiskClass.LOCAL_BUG,
        "likely_equivalent": False,
        "scope_symbol_ids": ("mod.fn",),
        "scope_paths": ("mod.py",),
        "notes": None,
        "metadata": {},
    }
    fields.update(overrides)
    return MutationCandidate(**fields)  # type: ignore[arg-type]


def _signature(**overrides: object) -> ReceiptSignatureBinding:
    fields: dict[str, Any] = {
        "signer_identity": _SIGNER,
        "key_identity": _SIGNER,
        "audience": "adversarial_assurance.store",
        "action": ReceiptAction.COMPLETE_CAMPAIGN,
        "signature": _SIGNATURE,
        "signature_verification_status": SignatureVerificationStatus.VERIFIED,
        "signature_algorithm": EXISTING_SIGNATURE_ALGORITHM,
        "signature_authority": EXISTING_SIGNATURE_AUTHORITY,
    }
    fields.update(overrides)
    return ReceiptSignatureBinding(**fields)  # type: ignore[arg-type]


def _campaign_scope() -> tuple[str, ...]:
    return (
        SealScopeItem.OPERATOR_VERSIONS.value,
        SealScopeItem.CAMPAIGN_POLICY.value,
        SealScopeItem.ADMITTED_SET.value,
        SealScopeItem.EXPECTED_DETECTION_SETS.value,
        SealScopeItem.OUTCOMES.value,
        SealScopeItem.SURVIVOR_REPORTS.value,
        SealScopeItem.VACUITY_FINDINGS.value,
        SealScopeItem.HELD_OUT_EVALUATIONS.value,
        SealScopeItem.CAMPAIGN_ARTIFACTS.value,
        SealScopeItem.DECLARED_RESULT_COMPLETENESS.value,
        SealScopeItem.CAMPAIGN_RECEIPT.value,
    )


def _campaign(**overrides: object) -> AssuranceCampaignReceipt:
    fields: dict[str, Any] = {
        "header": _receipt_header("assurance_campaign_receipt"),
        "receipt_id": "campaign_receipt_1",
        "campaign_plan_cid": _cid("plan"),
        "campaign_policy_cid": _cid("campaign-policy"),
        "campaign_policy_version": "1.0.0",
        "admitted_set_cid": _cid("admitted"),
        "expected_detection_sets_cid": _cid("expected-detection"),
        "outcomes_cid": _cid("outcomes"),
        "survivor_reports_cid": _cid("survivors"),
        "vacuity_findings_cid": _cid("vacuity"),
        "held_out_evaluation_cid": _cid("held-out-eval"),
        "held_out_result": HeldOutResult.PASSED,
        "authorization_cid": _cid("external-authorization"),
        "expected_old_revision": "0.9.0",
        "seal_scope": _campaign_scope(),
        "seal_status": SealAvailabilityStatus.BOUND,
        "seal_evidence_cid": _cid("seal-evidence"),
        "gap_reports_cid": _cid("gaps"),
        "input_artifact_cids": (_cid("input-plan"), _cid("input-policy")),
        "signature": _signature(action=ReceiptAction.COMPLETE_CAMPAIGN),
        "notes": None,
        "metadata": {},
    }
    fields.update(overrides)
    return AssuranceCampaignReceipt(**fields)  # type: ignore[arg-type]


def _span(**overrides: object) -> SourceSpan:
    fields: dict[str, Any] = {
        "path": "src/mod.py",
        "start_line": 10,
        "end_line": 12,
        "start_col": 0,
        "end_col": 40,
    }
    fields.update(overrides)
    return SourceSpan(**fields)  # type: ignore[arg-type]


def _evidence(**overrides: object) -> MinimizedEvidenceBinding:
    fields: dict[str, Any] = {
        "evidence_cids": (_cid("min-evidence-1"),),
        "minimized": True,
        "minimization_failed": False,
        "reproduction_input_cid": _cid("repro-input"),
        "notes": None,
    }
    fields.update(overrides)
    return MinimizedEvidenceBinding(**fields)  # type: ignore[arg-type]


def _survivor(**overrides: object) -> SurvivingMutantReport:
    fields: dict[str, Any] = {
        "header": _analysis_header("surviving_mutant_report"),
        "report_id": "survivor_1",
        "candidate_id": "cand_control_flow_invert_0",
        "candidate_cid": _cid("candidate"),
        "outcome_cid": _cid("outcome"),
        "risk_class": SurvivorRiskClass.AUTHORIZATION,
        "symbol_ids": ("mod.fn",),
        "violated_or_missing_property": "authorization check must remain present",
        "detectors_run": ("unit.test_branch",),
        "detectors_omitted": ("static.authz_rule",),
        "expected_behavior": "reject unauthorized caller",
        "observed_behavior": "unauthorized caller accepted",
        "source_spans": (_span(),),
        "dependency_path": ("mod.fn", "authz.check"),
        "reproduction_command": "pytest -q tests/test_authz.py::test_reject",
        "minimized_evidence": _evidence(),
        "proof_cids": (_cid("proof-a"),),
        "receipt_cids": (_cid("receipt-a"),),
        "equivalence_assessment_cid": None,
        "notes": None,
        "metadata": {},
    }
    fields.update(overrides)
    return SurvivingMutantReport(**fields)  # type: ignore[arg-type]


def _gap(**overrides: object) -> AssuranceGap:
    survivor = _survivor()
    fields: dict[str, Any] = {
        "header": _analysis_header("assurance_gap"),
        "gap_id": "gap_1",
        "gap_class": AssuranceGapClass.MISSING_TEST,
        "severity": GapSeverity.HIGH,
        "risk_class": SurvivorRiskClass.AUTHORIZATION,
        "summary": "missing test for inverted authorization guard",
        "candidate_id": "cand_control_flow_invert_0",
        "candidate_cid": _cid("candidate"),
        "survivor_report_cid": survivor.report_cid,
        "violated_or_missing_property": "authorization check must remain present",
        "symbol_ids": ("mod.fn",),
        "source_spans": (_span(),),
        "dependency_path": ("mod.fn", "authz.check"),
        "minimized_evidence": _evidence(),
        "requires_human_review": False,
        "detection_failure_cids": (),
        "vacuity_finding_cids": (),
        "notes": None,
        "metadata": {},
    }
    fields.update(overrides)
    return AssuranceGap(**fields)  # type: ignore[arg-type]


mutation_fixtures = SimpleNamespace(
    _cid=_cid,
    _header=_mutation_header,
    _operator=_operator,
    _target=_target,
    _candidate=_candidate,
    _seed_config=_seed_config,
)
receipt_fixtures = SimpleNamespace(
    _cid=_cid,
    _header=_receipt_header,
    _signature=_signature,
    _campaign=_campaign,
)
analysis_fixtures = SimpleNamespace(
    _cid=_cid,
    _header=_analysis_header,
    _gap=_gap,
    _survivor=_survivor,
)


def packaged_vector_catalog() -> dict[str, Any]:
    """Compact catalog of packaged constructors. Not live evidence."""

    return {
        "schema": VECTOR_SCHEMA,
        "interface": VECTOR_INTERFACE,
        "sibling_tests_package_required": SIBLING_TESTS_PACKAGE_REQUIRED,
        "sibling_checkout_required": SIBLING_CHECKOUT_REQUIRED,
        "vectors": (
            "mutation_candidate",
            "mutation_operator",
            "assurance_campaign_receipt",
            "assurance_gap",
        ),
        "source": "ipfs_kit_py.adversarial_assurance_store.normative_vectors",
        "live": False,
        "simulated_represented_as_live": False,
    }


__all__ = [
    "VECTOR_INTERFACE",
    "VECTOR_SCHEMA",
    "SIBLING_TESTS_PACKAGE_REQUIRED",
    "SIBLING_CHECKOUT_REQUIRED",
    "mutation_fixtures",
    "receipt_fixtures",
    "analysis_fixtures",
    "packaged_vector_catalog",
]
