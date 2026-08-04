"""Closed coverage catalog for KITA-003 hermetic fixtures.

Maps confirmed baseline blockers and acceptance categories onto stable ids.
"""

from __future__ import annotations

from typing import Final

CONFIRMED_BLOCKERS: Final[tuple[str, ...]] = (
    "vfs_rename_move_noop_false_success",
    "vfs_journal_methods_missing",
    "vfs_failed_op_create_delete_events",
    "bucket_multi_plane_overlap",
    "bucket_create_partial_writes_no_rollback",
    "bucket_iroh_tiering_external_before_txn",
    "wal_begin_commit_id_loss",
    "wal_mutation_before_durable_intent",
    "wal_incomplete_parent_durability",
    "wal_random_mock_handler",
    "wal_checkpoint_skips_unrecovered",
    "arc_stale_byte_accounting",
    "arc_ghost_hit_capacity_violation",
    "arc_unsynchronized_mutable_lists",
    "replica_ensure_replication_shadowed",
    "replica_pending_counted_as_success",
    "replica_policy_cross_field_incomplete",
    "backend_factory_absent_from_plugin",
    "backend_registry_schema_adapter_diverge",
    "backend_mcp_default_omits_ipfs",
    "mcp_plus_eventdagstore_unimported",
    "mcp_plus_profile_d_permissive_evaluator",
    "ucan_advisory_fail_open",
    "ucan_missing_attenuation_revocation_replay",
    "graphrag_pickle_cache_load",
    "graphrag_bruteforce_embeddings",
    "graphrag_eager_ml_import",
    "graphrag_index_not_rehydrated_on_restart",
    "graphrag_update_history_wrong_prior",
    "graphrag_incompatible_schemas",
    "interface_export_version_dependency_drift",
    "mcp_eager_optional_imports",
    "pytest_excludes_wal_arc_replica_coverage",
    "tests_accept_success_or_failure",
)

REQUIRED_COVERAGE_CATEGORIES: Final[tuple[str, ...]] = (
    "confirmed_blocker",
    "rename_move",
    "multi_store_bucket_saga",
    "commit_replay_checkpoint",
    "arc_growth_ghost_hits",
    "index_restart_history",
    "replica_drift",
    "ucan_absent",
    "ucan_forged",
    "ucan_revoked",
    "ucan_replayed",
    "interface_error_drift",
    "missing_optional_extras",
    "backend_retry_partial_effects",
    "resource_exhaustion",
    "nondeterministic_ordering",
)

REQUIRED_UCAN_VARIANTS: Final[tuple[str, ...]] = (
    "ucan_absent",
    "ucan_forged",
    "ucan_revoked",
    "ucan_replayed",
)

SYNTHETIC_BLOB: Final[dict[str, str]] = {
    "a": "content:blob-a-v1",
    "b": "content:blob-b-v1",
    "c": "content:blob-c-v1",
    "prior": "content:blob-prior-v0",
    "replacement": "content:blob-replacement-v1",
}
