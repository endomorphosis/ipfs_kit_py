"""Load Datasets assurance constructors from packaged Kit vectors.

Kit tests must not require ``ipfs_datasets_py.tests`` as a packaged module or
a sibling checkout path (PCPR-025). Fixtures come from
``ipfs_kit_py.adversarial_assurance_store.normative_vectors``, which uses the
public Datasets software-contract types.
"""

from __future__ import annotations

from ipfs_kit_py.adversarial_assurance_store.normative_vectors import (
    analysis_fixtures,
    mutation_fixtures,
    receipt_fixtures,
)

__all__ = [
    "analysis_fixtures",
    "mutation_fixtures",
    "receipt_fixtures",
]
