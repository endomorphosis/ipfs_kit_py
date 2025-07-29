.PHONY: help clean lint format test coverage build install docs

# Default target
help:
	@echo "IPFS Kit Python Development Commands"
	@echo "===================================="
	@echo "clean      - Remove build artifacts and cache files"
	@echo "lint       - Run linting tools (pylint, mypy)"
	@echo "format     - Format code with Black and isort"
	@echo "test       - Run tests"
	@echo "coverage   - Run tests with coverage report"
	@echo "build      - Build package distributions"
	@echo "install    - Install in development mode with all dependencies"
	@echo "install-min- Install in development mode with minimal dependencies"
	@echo "docs       - Generate documentation"

# Clean build artifacts and cache files
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run linting tools
lint:
	python -m pylint ipfs_kit_py
	python -m mypy ipfs_kit_py

# Format code
format:
	python -m black ipfs_kit_py
	python -m isort ipfs_kit_py

# Run tests
test:
	python -m pytest

# Run tests with coverage
coverage:
	python -m pytest --cov=ipfs_kit_py --cov-report=term --cov-report=html

# Build package distributions
build: clean
	python -m build

# Install in development mode with all dependencies
install:
	pip install -e ".[dev,full]"

# Install in development mode with minimal dependencies
install-min:
	pip install -e .

# Generate documentation
docs:
	@echo "Building documentation..."
	cd docs && make html