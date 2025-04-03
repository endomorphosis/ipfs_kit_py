# PyPI Release Checklist

This document provides a checklist for preparing and publishing releases of the `ipfs_kit_py` package to PyPI.

## Pre-Release Checklist

- [ ] Update version number in:
  - [ ] `pyproject.toml`
  - [ ] `setup.py`
  - [ ] `ipfs_kit_py/__init__.py` (version attribute)

- [ ] Ensure all tests pass:
  ```bash
  pytest
  ```

- [ ] Check code style and formatting:
  ```bash
  black --check ipfs_kit_py test
  isort --check ipfs_kit_py test
  pylint ipfs_kit_py
  mypy ipfs_kit_py
  ```

- [ ] Update `CHANGELOG.md`:
  - [ ] Move "Unreleased" changes to new version section
  - [ ] Add release date
  - [ ] Update links at bottom of file

- [ ] Review documentation:
  - [ ] `README.md` is up to date
  - [ ] `README-PyPI.md` is up to date (simplified version for PyPI)
  - [ ] API documentation is current
  - [ ] Example code works with latest version

- [ ] Check package metadata:
  - [ ] Description in `pyproject.toml` is accurate
  - [ ] Classifiers are appropriate
  - [ ] Dependencies are correct
  - [ ] URLs are valid

## Build and Test Package

- [ ] Clean previous builds:
  ```bash
  rm -rf build/ dist/ *.egg-info/
  ```

- [ ] Build the package:
  ```bash
  python -m build
  ```

- [ ] Check distribution contents:
  ```bash
  tar tzf dist/*.tar.gz | sort
  ```

- [ ] Verify package metadata:
  ```bash
  twine check dist/*
  ```

- [ ] Test installation from local build:
  ```bash
  pip install dist/*.whl
  ```

- [ ] Test package functionality (quick smoke test)

## Test PyPI Release (Optional)

- [ ] Upload to Test PyPI:
  ```bash
  twine upload --repository-url https://test.pypi.org/legacy/ dist/*
  ```

- [ ] Install from Test PyPI and verify:
  ```bash
  pip install --index-url https://test.pypi.org/simple/ ipfs_kit_py
  ```

## Release to PyPI

- [ ] Create a Git tag:
  ```bash
  git tag -a v0.1.0 -m "Release v0.1.0"
  git push origin v0.1.0
  ```

- [ ] Upload to PyPI:
  ```bash
  twine upload dist/*
  ```

- [ ] Verify installation from PyPI:
  ```bash
  pip install ipfs_kit_py
  ```

## Post-Release

- [ ] Create GitHub Release:
  - [ ] Navigate to Releases page on GitHub
  - [ ] Create a new release from the tag
  - [ ] Copy changelog entry to release notes
  - [ ] Upload distribution files

- [ ] Announce release (if applicable):
  - [ ] Project communication channels
  - [ ] Social media
  - [ ] Community forums

- [ ] Start next development cycle:
  - [ ] Update version to next development version (e.g., "0.2.0-dev")
  - [ ] Create new "Unreleased" section in `CHANGELOG.md`

## Continuous Integration

- [ ] GitHub Actions workflow should handle:
  - [ ] Testing on multiple Python versions
  - [ ] Linting code
  - [ ] Building package
  - [ ] Publishing to TestPyPI on commits to main branch
  - [ ] Publishing to PyPI on version tags (v*)

## Authentication for PyPI

This project uses trusted publishing via GitHub Actions. Make sure:

1. GitHub Actions environment secrets are configured for both PyPI and TestPyPI
2. Appropriate permissions are granted to the GitHub Actions workflow

## Notes for First Release

For the first release, you may need to reserve the package name on PyPI in advance:

```bash
pip install build twine
python -m build
twine upload dist/*
```

Follow the prompts to create a PyPI account if you don't have one.