"""Compatibility shim for importing/running `install_lotus`.

Some older scripts/tests expect `from install_lotus import install_lotus` from the
repository root. The canonical implementation lives in `ipfs_kit_py.install_lotus`.
"""

from ipfs_kit_py.install_lotus import install_lotus

__all__ = ["install_lotus"]


def main() -> None:
    # Delegate to the canonical CLI entrypoint if present.
    from ipfs_kit_py.install_lotus import main as _main

    _main()


if __name__ == "__main__":
    main()
