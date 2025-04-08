# Release Checklist for IPFS Kit v0.2.0

## Pre-Release Tasks

- [x] Update version number in `setup.py` (completed in commit fcf65bd)
- [x] Update version number in `pyproject.toml` (completed in commit fcf65bd)
- [x] Update version number in `ipfs_kit_py/__init__.py` (completed in commit fcf65bd)
- [x] Update test files for the new version (completed in commit fcf65bd)
- [x] Update CHANGELOG.md with release notes (completed in commit fcf65bd)
- [x] Create and push git tag for v0.2.0 (completed)

## Release Tasks

- [ ] Create GitHub Release with release notes
- [ ] Verify CI/CD workflows triggered by the tag:
  - [ ] Python package build and PyPI upload
  - [ ] Docker image build and publication
  - [ ] Helm chart packaging (if applicable)
- [ ] Verify package is available on PyPI
- [ ] Verify Docker image is available

## Post-Release Tasks

- [ ] Add "Unreleased" section back to CHANGELOG.md
- [ ] Announce the release to relevant channels
- [ ] Update documentation to reflect the new version
- [ ] Start planning for the next release

## Issues and Risks

- The GitHub CLI authentication is not available in this environment
- Need to verify that the CI/CD workflows execute successfully

## References

- [GitHub Releases Documentation](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [PyPI Upload Documentation](https://packaging.python.org/en/latest/tutorials/packaging-projects/#uploading-the-distribution-archives)
- [Docker Build and Push Documentation](https://docs.docker.com/build/ci/github-actions/)