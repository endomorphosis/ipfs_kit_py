"""Thin, provider-aware facade for durable state roots.

The adapter deliberately owns neither storage nor semantic identity.  Callers
provide the authoritative CID and an injected :class:`DurableCoordinationStore`
performs canonical storage and root publication.  Optional backend replication
is projected into closed result values without changing local durability.
"""

from __future__ import annotations

from typing import Any, Mapping

from .coordination_storage import ArtifactIntegrityError, DurableCoordinationStore
from .state_root_contracts import (
    ArtifactWriteResult,
    ProviderStatus,
    StateRootCASResult,
    StateRootRecoveryReport,
    StateRootSnapshot,
    validate_root_expectation,
    validate_semantic_dag_json_cid,
)


class DurableStateRootAdapter:
    """Compose an injected coordination store as the durable-roots protocol.

    No provider discovery occurs here: a backend is available only when one
    was injected into ``store``.  A replication problem is consequently a
    truthful partial-success result after the local immutable block has been
    committed, rather than an exception that obscures that durable fact.
    """

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store

    @property
    def store(self) -> DurableCoordinationStore:
        """The injected storage authority (provided for diagnostics only)."""

        return self._store

    def put_verified(
        self,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        replicate: bool = True,
    ) -> ArtifactWriteResult:
        """Persist a caller-identified artifact and truthfully project replication.

        The first local-only call intentionally verifies ``expected_cid``
        before any optional provider interaction.  Thus a CID mismatch cannot
        be transformed into a remote outcome or be used by a later root CAS.
        """

        # Validate before delegating so an invalid semantic identity cannot
        # create a local block or invoke an optional provider.
        expected_cid = validate_semantic_dag_json_cid(expected_cid, "expected_cid")
        local = self._store.put(
            payload, expected_cid=expected_cid, codec="dag-json", replicate=False
        )
        cid = local["cid"]

        if not replicate:
            return ArtifactWriteResult(
                cid, True, ProviderStatus.NOT_REQUESTED, False, "not_requested"
            )
        if self._store.backend is None:
            return ArtifactWriteResult(
                cid, True, ProviderStatus.UNAVAILABLE, False, "provider_unavailable"
            )

        try:
            remote = self._store.put(
                payload, expected_cid=expected_cid, codec="dag-json", replicate=True
            )
        except ArtifactIntegrityError:
            # IPFSHeliaBlockBackend raises this when a provider reports a
            # different CID.  Local durability remains true, but replication
            # is explicitly corrupt and never claimed as successful.
            return ArtifactWriteResult(
                cid, True, ProviderStatus.CORRUPT, False, "provider_corrupt"
            )
        except Exception:
            return ArtifactWriteResult(
                cid, True, ProviderStatus.FAILED, False, "provider_failed"
            )

        if remote.get("cid") != expected_cid or remote.get("replicated") is not True:
            return ArtifactWriteResult(
                cid, True, ProviderStatus.CORRUPT, False, "provider_corrupt"
            )
        return ArtifactWriteResult(
            expected_cid, True, ProviderStatus.AVAILABLE, True, "replicated"
        )

    def get_verified(self, cid: str) -> Mapping[str, Any]:
        """Return canonical, CID-verified content through the storage authority."""

        validate_semantic_dag_json_cid(cid)
        return self._store.get(cid)

    def current_root(self, namespace: str) -> StateRootSnapshot:
        """Return the current typed root snapshot for ``namespace``."""

        return self._semantic_snapshot(self._store.current_state_root(namespace))

    @staticmethod
    def _semantic_snapshot(value: Mapping[str, Any]) -> StateRootSnapshot:
        """Project a generic root only when all CID-bearing fields are structured."""

        snapshot = StateRootSnapshot.from_dict(value)
        if snapshot.root_cid is not None:
            validate_semantic_dag_json_cid(snapshot.root_cid, "root_cid")
        if snapshot.transition_cid is not None:
            validate_semantic_dag_json_cid(snapshot.transition_cid, "transition_cid")
        return snapshot

    def compare_and_swap_root(
        self,
        namespace: str,
        *,
        expected_revision: int,
        expected_root_cid: str | None,
        new_root_cid: str,
        operation_id: str,
    ) -> StateRootCASResult:
        """Publish a locally verified successor using the store's CAS boundary."""

        expected_revision, expected_root_cid = validate_root_expectation(
            expected_revision, expected_root_cid
        )
        new_root_cid = validate_semantic_dag_json_cid(new_root_cid, "new_root_cid")
        result = self._store.compare_and_swap_state_root(
            namespace,
            expected_revision=expected_revision,
            expected_root_cid=expected_root_cid,
            new_root_cid=new_root_cid,
            operation_id=operation_id,
        )
        typed = StateRootCASResult.from_dict(result)
        self._semantic_snapshot(typed.before.to_dict())
        self._semantic_snapshot(typed.after.to_dict())
        if typed.transition_cid is not None:
            validate_semantic_dag_json_cid(typed.transition_cid, "transition_cid")
        return typed

    def recover_roots(self) -> StateRootRecoveryReport:
        """Rebuild root indexes and return closed recovery evidence.

        Corruption remains fail-closed: no reconstructed root is returned when
        verification fails.
        """

        try:
            report = self._store.recover(rebuild=True)
        except (ArtifactIntegrityError, ValueError) as exc:
            return StateRootRecoveryReport(0, (), (), ({"code": "corrupt", "message": str(exc)},))
        snapshots = tuple(self._semantic_snapshot(snapshot) for snapshot in self._store.state_roots())
        return StateRootRecoveryReport(report["verified_blocks"], snapshots, (), ())


__all__ = ["DurableStateRootAdapter"]
