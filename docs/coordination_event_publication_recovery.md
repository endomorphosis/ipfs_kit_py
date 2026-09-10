# Event publication recovery

`DurableCoordinationStore.publish_event` writes immutable event and publication blocks before committing their SQLite index. An interruption in that interval leaves valid publication evidence that a retry must preserve.

Publication now verifies local immutable blocks and reconciles the derived publication index under the same `BEGIN IMMEDIATE` writer transaction used for replay checks and new publication. This also covers another store connection that was already open when the first writer failed. Replays return the original publication CID and timestamp; operation/event reuse returns the existing typed conflict. Recovery never creates replacement immutable evidence, changes a root chain, or rewrites healthy publication indexes. Conflicting immutable history remains an integrity error.

The recovery scan is linear in local immutable blocks for each publication. This deliberately favors correctness over an unproven process-local cache; a future incremental index must also detect evidence left by other writer processes before admitting a publication.

The regression suite injects failure after the publication block is durably written and checks replay/conflicting reuse on both original and already-open peer connections. It verifies unchanged immutable bytes, one recovered publication, and successful reopening. An existing duplicate immutable history is rejected without extending it.

This change does not amend historical DOEP-031 or DOEP-062 task receipts. Their source digests require independent current-root requalification and accepted evidence before native task completion can be asserted. Standalone storage tests do not grant supervisor ownership, callback closure, or task acceptance.
