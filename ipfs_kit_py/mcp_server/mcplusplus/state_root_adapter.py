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

        return self._store.get(cid)

    def current_root(self, namespace: str) -> StateRootSnapshot:
        """Return the current typed root snapshot for ``namespace``."""

        return StateRootSnapshot.from_dict(self._store.current_state_root(namespace))

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

        result = self._store.compare_and_swap_state_root(
            namespace,
            expected_revision=expected_revision,
            expected_root_cid=expected_root_cid,
            new_root_cid=new_root_cid,
            operation_id=operation_id,
        )
        return StateRootCASResult.from_dict(result)

    def recover_roots(self) -> StateRootRecoveryReport:
        """Rebuild root indexes and return closed recovery evidence.

        Corruption remains fail-closed: no reconstructed root is returned when
        verification fails.
        """

        try:
            report = self._store.recover(rebuild=True)
        except (ArtifactIntegrityError, ValueError) as exc:
            return StateRootRecoveryReport(0, (), (), ({"code": "corrupt", "message": str(exc)},))
        return StateRootRecoveryReport(
            report["verified_blocks"],
            tuple(StateRootSnapshot.from_dict(snapshot) for snapshot in self._store.state_roots()),
            (),
            (),
        )


__all__ = ["DurableStateRootAdapter"]
