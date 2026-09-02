"""Fail-closed PCPR-040 Kit binding to the shared-contract catalog.

Kit owns DurableArtifactReceipt. This module binds that identity to the
Accelerate-owned normative catalog and refuses reminting. Kit verifies
and stores exact bytes; it does not decide proof validity, task
completion, reuse, or semantic meaning.

This module does not import sibling Accelerate or Datasets packages. It
is not a freeze, not canonical-byte vectors, not a closed PCPR release,
and it never writes DuckDB or Quack state.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

INTERFACE: Final = "KitSharedContractBinding@1"
SCHEMA: Final = "ipfs_kit_py/assurance/shared-contract-binding@1"
NORMATIVE_SOURCE: Final = "ipfs_accelerate_py/assurance/shared-contracts-catalog@1"
NORMATIVE_INTERFACE: Final = "SharedContractCatalog@1"
PCPR_040_TASK_ID: Final = "PCPR-040"
PCPR_040_GOAL_ID: Final = "PCPR-G500"
PCPR_002_TASK_ID: Final = "PCPR-002"
PCPR_041_TASK_ID: Final = "PCPR-041"
OWNER_REPOSITORY: Final = "ipfs_kit_py"

KIT_OWNED_CONTRACTS: Final[tuple[str, ...]] = ("DurableArtifactReceipt",)

CONTRACT_SCHEMA_IDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "SupervisorObjectiveIntent": (
            "pcpr/shared-contracts/supervisor-objective-intent@1"
        ),
        "ObjectiveMaterializationReceipt": (
            "pcpr/shared-contracts/objective-materialization-receipt@1"
        ),
        "SupervisorContextPack": (
            "pcpr/shared-contracts/supervisor-context-pack@1"
        ),
        "SemanticArtifactIdentity": (
            "pcpr/shared-contracts/semantic-artifact-identity@1"
        ),
        "DurableArtifactReceipt": (
            "pcpr/shared-contracts/durable-artifact-receipt@1"
        ),
        "ProofObligation": "pcpr/shared-contracts/proof-obligation@1",
        "ProofResult": "pcpr/shared-contracts/proof-result@1",
        "ProofAdmissionDecision": (
            "pcpr/shared-contracts/proof-admission-decision@1"
        ),
        "ExecutionInvocation": "pcpr/shared-contracts/execution-invocation@1",
        "ExecutionReceipt": "pcpr/shared-contracts/execution-receipt@1",
        "SupervisorEvent": "pcpr/shared-contracts/supervisor-event@1",
        "TaskStateTransition": "pcpr/shared-contracts/task-state-transition@1",
        "ReleaseComponentManifest": (
            "pcpr/shared-contracts/release-component-manifest@1"
        ),
        "PortfolioCompatibilityManifest": (
            "pcpr/shared-contracts/portfolio-compatibility-manifest@1"
        ),
    }
)

OWNER_SCHEMAS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "DurableArtifactReceipt": (
            "pcpr/shared-contracts/durable-artifact-receipt@1"
        ),
    }
)

OWNER_INTERFACES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "DurableArtifactReceipt": "DurableArtifactReceipt@1",
    }
)


class KitSharedContractError(ValueError):
    """Kit attempted to remint or invent a shared-contract identity."""


def refuse_remint(name: str, schema: str) -> str:
    expected = CONTRACT_SCHEMA_IDS.get(name)
    if expected is None:
        raise KitSharedContractError(f"{name} is not a PCPR shared contract")
    if schema != expected:
        raise KitSharedContractError(
            f"{name} identity {schema} remints {expected}"
        )
    return expected


def kit_binding_mapping() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "interface": INTERFACE,
        "normative_source": NORMATIVE_SOURCE,
        "normative_interface": NORMATIVE_INTERFACE,
        "task_id": PCPR_040_TASK_ID,
        "goal_id": PCPR_040_GOAL_ID,
        "owner_repository": OWNER_REPOSITORY,
        "frozen": False,
        "freeze_task": PCPR_002_TASK_ID,
        "vector_task": PCPR_041_TASK_ID,
        "owned_contracts": list(KIT_OWNED_CONTRACTS),
        "contract_schema_ids": dict(CONTRACT_SCHEMA_IDS),
        "owner_schemas": dict(OWNER_SCHEMAS),
        "owner_interfaces": dict(OWNER_INTERFACES),
        "remint": False,
        "sibling_import": False,
        "semantic_authority": False,
        "proof_validity_authority": False,
        "task_completion_authority": False,
        "duckdb_or_quack_state_written": False,
    }


__all__ = (
    "CONTRACT_SCHEMA_IDS",
    "INTERFACE",
    "KIT_OWNED_CONTRACTS",
    "KitSharedContractError",
    "NORMATIVE_SOURCE",
    "OWNER_SCHEMAS",
    "PCPR_040_TASK_ID",
    "SCHEMA",
    "kit_binding_mapping",
    "refuse_remint",
)
