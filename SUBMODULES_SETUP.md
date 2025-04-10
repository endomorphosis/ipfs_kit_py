# Git Submodule Setup

This document summarizes the git submodules setup process for the ipfs_kit_py project.

## Submodules Added

We've set up the following repositories as git submodules to ensure they're properly tracked and maintained:

1. **Documentation Repositories**
   - `docs/ipfs-docs` - https://github.com/ipfs/ipfs-docs
   - `docs/libp2p_docs` - https://github.com/libp2p/docs
   - `docs/ipfs_cluster` - https://github.com/ipfs-cluster/ipfs-cluster-website
   - `docs/filesystem_spec` - https://github.com/fsspec/filesystem_spec
   - `docs/libp2p-universal-connectivity` - https://github.com/libp2p/universal-connectivity
   - `docs/lotus` - https://github.com/filecoin-project/lotus
   - `docs/ipfsspec` - https://github.com/fsspec/ipfsspec
   - `docs/lassie` - https://github.com/filecoin-project/lassie
   - `docs/lighthouse-python-sdk` - https://github.com/lighthouse-web3/lighthouse-python-sdk
   - `docs/filecoin-address-python` - https://github.com/ciknight/filecoin-address-python
   - `docs/storacha_specs` - https://github.com/storacha/specs

2. **IPLD Implementations**
   - `py-ipld-car` - https://github.com/storacha/py-ipld-car
   - `py-ipld-dag-pb` - https://github.com/storacha/py-ipld-dag-pb
   - `py-ipld-unixfs` - https://github.com/storacha/py-ipld-unixfs

## Benefits of Using Submodules

Using git submodules provides several benefits:

1. **Clean Repository Structure**: Separates external code from internal code
2. **Version Control**: Ensures specific versions of dependencies are used
3. **Smaller Repository Size**: Avoids storing large documentation repositories directly
4. **Easier Updates**: Simplifies updating to newer versions of dependencies
5. **Improved Collaboration**: Makes it easier for contributors to understand what's part of the project vs. external code

## Working with Submodules

### Cloning the Repository with Submodules

When cloning the repository, use the following command to also fetch all submodules:

```bash
git clone --recurse-submodules https://github.com/endomorphosis/ipfs_kit_py.git
```

If you've already cloned the repository without submodules, initialize and update them:

```bash
git submodule init
git submodule update
```

### Updating Submodules

To update all submodules to their latest versions:

```bash
git submodule update --remote
git add .
git commit -m "Update submodules to latest versions"
```

## Maintenance Notes

- Submodules are pinned to specific commits. When updating, be aware of potential breaking changes.
- When making changes to submodules, make sure to do so in a separate branch and carefully test the integration.
- The `.gitmodules` file contains the configuration for all submodules.