# External Documentation Sources

| Field | Value |
|---|---|
| Task | KDOC-044 — Document external gitlinks and embedded project ownership |
| Goal | KDOC-G050 |
| Track | information-architecture |
| Authority class | **External** (ownership/boundary record; not authored kit guidance) |
| Record date | 2026-08-03 |
| Tree baseline | Git commit `c7fa64bef37748dd868cec531f71ea4beaa738c2` |
| Scope | Documentation gitlinks under `docs/`, embedded `docs/py-ipld-*` snapshots, and related root-level submodule declarations |
| External content | **Not fetched.** Documentation gitlink working trees remain empty unless a human intentionally initializes them. |
| Method | Offline inspection of `.gitmodules`, `git ls-files -s` (mode `160000`), and local `docs/py-ipld-*` tree walks only |
| Related evidence | [DOCUMENTATION_INVENTORY.md](../audits/DOCUMENTATION_INVENTORY.md) §4.7–4.8; plan §3.1 / §4 |

This document is the **ownership and boundary record** for external and embedded material that lives beside authored `ipfs_kit_py` documentation. It exists so navigation, coverage metrics, and agents treat these paths correctly and so readers know when upstream material may be **absent** from a checkout.

---

## 1. Why this boundary exists

The `docs/` tree mixes:

1. **Authored package documentation** — canonical, historical, generated, and proposed material owned by the `ipfs_kit_py` documentation program.
2. **External documentation gitlinks** — submodule pins to upstream documentation or SDK repositories under `docs/`.
3. **Embedded project snapshots** — full mini-projects (package sources, tests, CI configs) checked into `docs/py-ipld-*` as ordinary tree files.

Authority class **External** (from `docs/documentation_plan.md` §3.1):

| Class | Meaning | Update rule |
|---|---|---|
| **External** | Vendored or gitlinked upstream material | Ownership and revision are explicit; **excluded from authored-doc coverage** |

**Invariants:**

- External and embedded paths are **not** counted as authored package documentation in coverage, completeness, freshness, or quality metrics.
- Documentation tasks **must not** initialize or fetch external documentation gitlinks (`documentation_plan.md` §3.4).
- Empty gitlink directories are expected and valid; absence of upstream files is not a documentation defect.
- Authored kit guides remain authoritative for how `ipfs_kit_py` uses related capabilities; upstream trees do not override kit runtime contracts.

---

## 2. Reader guide: when upstream material may be absent

| Situation | What you see locally | Interpretation |
|---|---|---|
| Uninitialized documentation gitlink | Empty directory (0 files) under a path listed in §3 | Upstream content was **not** checked out. Pin SHA exists in the Git index only. |
| Declared in `.gitmodules` but no index gitlink | Path may be missing entirely (see §3.2) | Submodule is declared but not currently committed as a mode-`160000` entry. |
| Embedded `docs/py-ipld-*` snapshot | Full mini-project present as regular files | Content is a **vendored snapshot**, not a live submodule at that path. It may lag upstream. |
| Root-level `py-ipld-*` in `.gitmodules` | Paths may be empty or missing; dual relationship with `docs/py-ipld-*` | Root submodule pins (when present) are separate from the `docs/` snapshots. Do not assume they are synchronized. |

**Do not treat empty external directories as missing kit docs.** Prefer authored paths under `docs/architecture/`, `docs/guides/`, `docs/integration/`, and `docs/reference/` for current product guidance. For upstream-specific detail when a gitlink is empty, use the recorded upstream URL at the pin revision listed below, or the public project site—without requiring a submodule fetch for documentation work.

**Safe environment for documentation checks:**

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
# Do not run: git submodule update --init docs/...
```

---

## 3. External documentation gitlinks (`docs/`)

### 3.1 Committed mode-`160000` gitlinks (present in index)

These paths appear as Git submodule gitlinks. Working trees in the documentation baseline are **empty** (local file count = 0). Content was **not** fetched for this record.

| Path | Upstream origin (`.gitmodules`) | Tracked branch | Recorded pin SHA (`git ls-files -s`) | Local availability | License (upstream; not re-fetched) | Ownership |
|---|---|---|---|---|---|---|
| `docs/filesystem_spec` | https://github.com/fsspec/filesystem_spec.git | `main` | `fec09b04ad626df44a03bc605cb2e526b752b042` | **Absent** (empty tree) | Upstream project license | External — fsspec / filesystem_spec maintainers |
| `docs/ipfs-docs` | https://github.com/ipfs/ipfs-docs.git | `main` | `4cf83720b59738d93db4068976f9c2a11f023e45` | **Absent** (empty tree) | Upstream project license | External — IPFS docs maintainers |
| `docs/ipfs_cluster` | https://github.com/ipfs-cluster/ipfs-cluster-website.git | `main` | `c7ca8b5f87b41fcc795297ca65b0bb41c10234bf` | **Absent** (empty tree) | Upstream project license | External — IPFS Cluster website maintainers |
| `docs/ipfsspec` | https://github.com/fsspec/ipfsspec.git | `main` | `03f5199b9bf5a96c7ebf5e2e6f5dce8cf58b655f` | **Absent** (empty tree) | Upstream project license | External — fsspec / ipfsspec maintainers |
| `docs/lassie` | https://github.com/filecoin-project/lassie.git | `main` | `c6ba777810d03fed23aea11b5969b7d8a97f1edf` | **Absent** (empty tree) | Upstream project license | External — Filecoin / Lassie maintainers |
| `docs/libp2p-universal-connectivity` | https://github.com/libp2p/universal-connectivity.git | `main` | `e18a6de9c020c5e406d9f61b638f5d276054798d` | **Absent** (empty tree) | Upstream project license | External — libp2p universal-connectivity maintainers |
| `docs/libp2p_docs` | https://github.com/libp2p/docs.git | `main` | `17cee4a438797313d1e878b103abc1dbefdf423e` | **Absent** (empty tree) | Upstream project license | External — libp2p docs maintainers |
| `docs/lighthouse-python-sdk` | https://github.com/lighthouse-web3/lighthouse-python-sdk.git | `main` | `6b2c86693090c770d2c9a4d82ba315000a77068b` | **Absent** (empty tree) | Upstream project license | External — Lighthouse Web3 SDK maintainers |
| `docs/mcp-python-sdk` | https://github.com/modelcontextprotocol/python-sdk.git | `main` | `d3133ae6ce7333a501e38046aff4275c44326f90` | **Absent** (empty tree) | Upstream project license | External — Model Context Protocol Python SDK maintainers |
| `docs/storacha_specs` | https://github.com/storacha/specs.git | `main` | `3b6791869635735ddb1a54aed7450ad6ef687c06` | **Absent** (empty tree) | Upstream project license | External — Storacha specs maintainers |

**Count:** 10 documentation gitlinks with mode `160000` under `docs/`.

**Kit ownership of the pin:** The `ipfs_kit_py` repository owns only the **submodule pointer** (path + SHA) and this boundary record. Upstream owns the content at that SHA.

**License note:** Licenses for empty gitlinks are **not** restated here because content is not present in the worktree. When material is intentionally checked out by a human, consult the license files inside that checkout. Do not invent or copy license text from network sources during documentation tasks.

### 3.2 Declared in `.gitmodules` but not a current `docs/` gitlink

| Path in `.gitmodules` | Upstream origin | Index gitlink present? | Local availability | Notes |
|---|---|---|---|---|
| `docs/filecoin-address-python` | https://github.com/ciknight/filecoin-address-python.git | **No** mode-`160000` entry observed | Path may be missing or empty | Declared submodule; not committed as a documentation gitlink in this baseline. Still **External** if/when material appears. Do not invent content. |

### 3.3 Role of each documentation gitlink (navigation only)

These paths are **reference material for adjacent ecosystems**, not substitutes for kit guides.

| Path | Typical upstream subject | Prefer authored kit docs for… |
|---|---|---|
| `docs/ipfs-docs` | Official IPFS documentation site sources | Kit install, runtime, backends, CLI/MCP |
| `docs/libp2p_docs` | Official libp2p documentation | Kit network/transport contracts (`docs/architecture/NETWORK_TRANSPORTS.md`, `docs/iroh/`) |
| `docs/libp2p-universal-connectivity` | Universal connectivity demos/specs | Kit connectivity features only as implemented and tested in-tree |
| `docs/ipfs_cluster` | IPFS Cluster website/docs sources | Kit cluster coordination guides |
| `docs/filesystem_spec` / `docs/ipfsspec` | fsspec and IPFS fsspec implementations | Kit fsspec/VFS integration docs |
| `docs/lassie` | Lassie retrieval client | Kit retrieval/integration notes that cite kit code |
| `docs/lighthouse-python-sdk` | Lighthouse storage SDK | Kit Lighthouse/backend integration surfaces |
| `docs/mcp-python-sdk` | MCP Python SDK | Kit MCP control-plane and controller docs |
| `docs/storacha_specs` | Storacha specifications | Kit Storacha-related integration only where implemented |
| `docs/filecoin-address-python` | Filecoin address helpers (if present) | Kit Filecoin surfaces under `ipfs_kit_py` |

Do **not** link empty external directories from primary navigation indexes as if they were populated guides.

---

## 4. Embedded `py-ipld-*` project snapshots

### 4.1 What they are

Under `docs/` the repository vendors **three complete mini-projects** as ordinary files (mode `100644`), not as mode-`160000` gitlinks at these paths:

| Path | Package name (`pyproject.toml`) | Snapshot files (approx.) | Upstream homepage | Declared license in snapshot |
|---|---|---:|---|---|
| `docs/py-ipld-car/` | `ipld_car` | 10 | https://github.com/storacha/py-ipld-car | Apache-2.0 OR MIT (`LICENSE.md`, permissive license stack) |
| `docs/py-ipld-dag-pb/` | `ipld_dag_pb` | 19 | https://github.com/storacha/py-ipld-dag-pb | Apache-2.0 OR MIT (`LICENSE.md`, permissive license stack) |
| `docs/py-ipld-unixfs/` | `ipld_unixfs` | 27 | https://github.com/storacha/py-ipld-unixfs | Apache-2.0 OR MIT (`LICENSE.md`, permissive license stack) |

Each snapshot includes package source, tests, `pyproject.toml`, `README.md`, `LICENSE.md`, and a small GitHub Actions test workflow. They are **upstream project trees embedded for reference**, not authored `ipfs_kit_py` documentation.

**Authority class:** **External** (embedded project snapshot).  
**Owner of content:** Storacha / corresponding authors of the `py-ipld-*` projects (see each `pyproject.toml` and `LICENSE.md`).  
**Owner of placement:** `ipfs_kit_py` repository maintainers (decide whether to refresh, relocate, or remove the snapshot).  
**Revision identity:** Snapshot tree hashes as committed in this repository—not a live submodule pin at `docs/py-ipld-*`. Version fields in snapshot `pyproject.toml` may be `0.0.1` and must not be treated as the kit’s release version.

### 4.2 Dual-path relationship with root-level submodule declarations

`.gitmodules` also declares **root-level** submodule paths (separate from the `docs/` snapshots):

| Submodule name | Path | Upstream origin | Branch |
|---|---|---|---|
| `py-ipld-car` | `py-ipld-car` | https://github.com/storacha/py-ipld-car.git | `main` |
| `py-ipld-dag-pb` | `py-ipld-dag-pb` | https://github.com/storacha/py-ipld-dag-pb.git | `main` |
| `py-ipld-unixfs` | `py-ipld-unixfs` | https://github.com/storacha/py-ipld-unixfs.git | `main` |

In this documentation baseline, root-level `py-ipld-*` paths are **not** necessarily populated as checked-out submodules. Packaging may also pull related libraries via dependency metadata (for example `pyproject.toml` / `config/pyproject.toml` entries for `py-ipld-car`, `py-ipld-dag-pb`, `py-ipld-unixfs` / `ipld-unixfs`). Those packaging dependencies are **runtime/build** concerns; they do not reclassify the `docs/py-ipld-*` trees as authored docs.

| Location | Form | Use for documentation metrics? |
|---|---|---|
| `docs/py-ipld-car/`, `docs/py-ipld-dag-pb/`, `docs/py-ipld-unixfs/` | Embedded file snapshots | **No** — External |
| Root `py-ipld-*` submodule paths | Optional gitlinks / empty | **No** — External (when present) |
| Authored IPLD integration guidance (e.g. `docs/integration/ipld_integration.md`) | Kit-authored | **Yes** — subject to normal coverage rules |

### 4.3 Snapshot contents (navigation aid)

| Path | Primary modules / signals |
|---|---|
| `docs/py-ipld-car/` | `ipld_car/`, CAR encode/decode tests, hatchling `pyproject.toml` |
| `docs/py-ipld-dag-pb/` | `ipld_dag_pb/` (encode/decode/node/util + `dag-pb.proto`), tests |
| `docs/py-ipld-unixfs/` | `ipld_unixfs/` (file chunker/layout, multiformats helpers), tests |

Readers needing **how the kit uses IPLD** should start from authored integration and architecture docs, not from these vendor trees.

---

## 5. Related non-`docs/` submodule (out of documentation metrics)

| Path | Upstream origin | Pin SHA (when present) | Notes |
|---|---|---|---|
| `ipfs_accelerate_py` | https://github.com/endomorphosis/ipfs_accelerate_py | `4ad26c94d2f6aa17329fb53a301244a7a9cb1b30` | Root-level dependency submodule; **not** package docs. Excluded from authored documentation metrics. |

---

## 6. Coverage, build, and metrics treatment

### 6.1 Authored package documentation metrics — exclusions

The following **must be excluded** from authored package documentation coverage, completeness, freshness, quality scores, and “missing doc” findings:

| Exclusion set | Paths / pattern |
|---|---|
| Empty external doc gitlinks | All §3.1 paths (and §3.2 if material appears only as upstream content) |
| Embedded IPLD snapshots | `docs/py-ipld-car/**`, `docs/py-ipld-dag-pb/**`, `docs/py-ipld-unixfs/**` |
| Root external project checkouts | `py-ipld-car/**`, `py-ipld-dag-pb/**`, `py-ipld-unixfs/**`, `ipfs_accelerate_py/**` when present as external trees |

**What still counts as authored** when documenting IPLD/adjacent features:

- Kit-written guides (for example under `docs/integration/`, `docs/architecture/`, `docs/reference/`).
- Generated API inventories under `docs/api_generated/` (separate **Generated** contract, not External).
- Historical reports under `docs/ARCHIVE/` (Historical class — provenance only).

### 6.2 Build and CI

| Concern | Treatment |
|---|---|
| Documentation validation / link checks | Must not require initialized external gitlinks. Empty trees are success for “present pin, absent content.” |
| Package build / pytest for `ipfs_kit_py` | Must not treat `docs/py-ipld-*` as the installable kit package. Prefer declared dependencies or root packaging layout. |
| Snapshot-internal CI workflows | Files under `docs/py-ipld-*/.github/workflows/` belong to the **embedded upstream project**. They are not the kit’s documentation CI contract. |
| Auto-install binaries | Keep `IPFS_KIT_AUTO_INSTALL_BINARIES=0` for documentation validation. |

### 6.3 Suggested metric filter (informative)

When counting Markdown or “doc files” under `docs/`:

```bash
# Example exclusion sketch (adapt to the real metrics tool)
find docs -type f \( -name '*.md' -o -name '*.rst' \) \
  ! -path 'docs/py-ipld-car/*' \
  ! -path 'docs/py-ipld-dag-pb/*' \
  ! -path 'docs/py-ipld-unixfs/*' \
  ! -path 'docs/filesystem_spec/*' \
  ! -path 'docs/ipfs-docs/*' \
  ! -path 'docs/ipfs_cluster/*' \
  ! -path 'docs/ipfsspec/*' \
  ! -path 'docs/lassie/*' \
  ! -path 'docs/libp2p-universal-connectivity/*' \
  ! -path 'docs/libp2p_docs/*' \
  ! -path 'docs/lighthouse-python-sdk/*' \
  ! -path 'docs/mcp-python-sdk/*' \
  ! -path 'docs/storacha_specs/*' \
  ! -path 'docs/filecoin-address-python/*'
```

Empty gitlink directories contribute **zero** files and must not lower authored coverage percentages.

---

## 7. Update policy

| Event | Who | Action |
|---|---|---|
| Refresh a documentation gitlink pin | Human maintainer (not automated doc agents) | Update submodule SHA deliberately; record intent in commit message; re-verify this boundary file if paths or origins change. **Do not** fetch as part of ordinary documentation tasks. |
| Refresh an embedded `docs/py-ipld-*` snapshot | Human maintainer | Replace snapshot tree with a deliberate vendor refresh; preserve license files; keep External classification; do not re-label as authored docs. |
| Add/remove a documentation submodule | Human maintainer | Update `.gitmodules`, index gitlink, and this file in the same change. |
| Authored kit behavior changes involving IPLD/MCP/fsspec/etc. | Documentation program | Update **authored** guides and architecture docs only; do not edit upstream trees to “fix” kit docs. |
| Automated agents / KDOC workers | Agents | Read this file; classify External; **never** `git submodule update --init` for documentation gitlinks; never count External paths as authored coverage. |

**Conflict policy (KDOC-044):** Own this external-source reference only; never fetch or modify external content as part of documenting the boundary.

---

## 8. Offline verification (no network)

Reproduce the classification without initializing submodules:

```bash
# Documentation gitlinks under docs/
git ls-files -s docs | awk '$1=="160000" {print}'

# Submodule path/url map (local file only)
rg -n '\[submodule |"path = |"url = ' .gitmodules

# Empty-tree check for known doc gitlinks
for d in docs/filesystem_spec docs/ipfs-docs docs/ipfs_cluster docs/ipfsspec \
         docs/lassie docs/libp2p-universal-connectivity docs/libp2p_docs \
         docs/lighthouse-python-sdk docs/mcp-python-sdk docs/storacha_specs; do
  printf '%s local_files=%s\n' "$d" "$(find "$d" -type f 2>/dev/null | wc -l)"
done

# Embedded py-ipld snapshots (regular files, not gitlinks at these paths)
for d in docs/py-ipld-car docs/py-ipld-dag-pb docs/py-ipld-unixfs; do
  echo "== $d =="
  find "$d" -type f | wc -l
  git ls-files -s "$d" | awk '{print $1}' | sort -u
  test -f "$d/pyproject.toml" && rg -n '^(name|license|Homepage) ?=' "$d/pyproject.toml" || true
done
```

Expected shape for this baseline:

- 10 mode-`160000` entries under `docs/`;
- 0 local files in each listed documentation gitlink working tree;
- non-zero file counts and mode `100644` only under `docs/py-ipld-*`.

---

## 9. Summary for agents and metrics tools

| Rule | Detail |
|---|---|
| Authority | **External** for all §3 gitlinks and §4 `py-ipld-*` snapshots |
| Metrics | **Exclude** from authored package documentation coverage |
| Absence | Empty gitlinks mean **upstream material not present**, not a broken kit doc tree |
| Fetch policy | **Do not** initialize/fetch documentation gitlinks for documentation work |
| Authored substitute | Use kit architecture, guides, integration, and reference docs |
| This file | Boundary record only; not a substitute for upstream content |

---

## 10. Related documents

| Document | Role |
|---|---|
| [DOCUMENTATION_INVENTORY.md](../audits/DOCUMENTATION_INVENTORY.md) | Corpus inventory; §4.7–4.8 first classification of External families |
| [FRESHNESS_AND_CHANGE_AUDIT.md](../audits/FRESHNESS_AND_CHANGE_AUDIT.md) | Freshness findings including empty vendor directories |
| [HISTORICAL_DOCUMENT_REGISTER.md](../audits/HISTORICAL_DOCUMENT_REGISTER.md) | Historical class (separate from External) |
| [COMPATIBILITY_LAYERS.md](../architecture/COMPATIBILITY_LAYERS.md) | Notes empty external doc gitlinks as non-runtime |
| [SOURCE_OF_TRUTH_MAP.md](../architecture/SOURCE_OF_TRUTH_MAP.md) | Source authority map; points external material here |
| `.gitmodules` | Local submodule path and URL declarations |
| `docs/documentation_plan.md` | Program policy: External class and no-fetch rule |

---

*Last verified offline against the worktree baseline in the metadata table. Do not treat this file as evidence that upstream documentation was downloaded.*
