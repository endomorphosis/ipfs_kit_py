"""Kit-owned Proof-Carrying Context Engine v0.1 persistence port.

Cold import is hermetic: no daemon, network, or default user-state root.
"""

from __future__ import annotations

SCHEMA = "ipfs-kit.proof-context.v0.1"

__all__ = ["SCHEMA"]
