# PCPR-053 declared release-profile dependency locks

These files freeze the Kit *release* profile as declared PEP 508 specs
from `pyproject.toml` `[project].dependencies`. They are not a hashed
pip-tools / uv lock, not a live PyPI resolution, and not a closed PCPR
release.

- `cpython312/release.lock.json` is the canonical declared-spec lock.
- `cpython312/release.txt` is the pip-installable declared-spec list.
- Hash and transitive resolution remain typed unavailable until a live
  sealed-PATH resolver is admitted. Hashes are never invented.
- Named extras `libp2p` and `ipld-github` may carry source-checkout Git
  pins and are not this release lock.
- `python-magic` is declared; host libmagic remains typed unavailable
  unless independently detected and is never production-authorized here.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
Provider-local `~/.local` tools such as `uv` are not sealed-environment
authority.
