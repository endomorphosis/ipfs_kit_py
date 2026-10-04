# Iroh Binary Lifecycle Commands

IPFS Kit manages its pinned Iroh sidecar explicitly. Importing `ipfs_kit_py`,
`install_iroh`, or the lifecycle module does not download or execute Iroh.
Package setup only attempts binary installation when
`IPFS_KIT_AUTO_INSTALL_BINARIES=1` is set.

The installed console command is `ipfs-kit-iroh`; the PATH-independent form is
`python -m ipfs_kit_py.iroh_install_cli`. Both expose the same four commands:

```bash
ipfs-kit-iroh install --version 0.1.0 --dry-run
ipfs-kit-iroh install --version 0.1.0 --check
ipfs-kit-iroh inspect --check
ipfs-kit-iroh update --check
ipfs-kit-iroh update --version 0.1.0 --dry-run
ipfs-kit-iroh rollback --dry-run
ipfs-kit-iroh rollback --check
```

Use `--allow-prerelease` with `install` or `update` when the pinned manifest
selects a prerelease. A prerelease is otherwise refused. `--dry-run` validates
the pinned artifact and reports the intended operation without taking a lock or
changing files. `update --check` verifies the current installation and reports
whether the pinned version is newer.

The binary directory defaults to `~/.local/share/ipfs_kit_py/bin`. Override it
with `IPFS_KIT_BIN_DIR` or `--bin-dir`. Health checks invoke the resolved binary
in that directory directly and do not depend on shell `PATH`.

## Receipts and rollback

The current receipt is `.ipfs-kit-iroh-install.json`. It records the pinned
version, release URL, archive SHA-256 digest, UTC installation time, target,
absolute binary path, and installed executable digest. `inspect --check`
recomputes the executable digest and runs its side-effect-free `--version`
command.

An update retains exactly one prior verified binary and receipt using the
`.previous` suffix. `rollback` verifies that retained digest before swapping
the current and previous versions, so a second rollback can restore the version
that was active before the first rollback. Install, update, and rollback share
the non-blocking `.ipfs-kit-iroh-update.lock`; a concurrent mutation is refused
instead of waiting or interleaving state.

Lifecycle writes are atomic. Update and rollback snapshot every affected file
and restore that snapshot if a binary or receipt replacement fails.
