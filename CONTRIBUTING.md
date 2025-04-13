# Contributing to IPFS Kit Python

Thank you for your interest in contributing to IPFS Kit Python! This document provides guidelines and instructions for contributing to this project.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- A GitHub account

### Setting Up the Development Environment

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/ipfs_kit_py.git
   cd ipfs_kit_py
   ```

3. Set up a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

4. Install the package in development mode with all development dependencies:
   ```bash
   pip install -e ".[dev,full]"
   ```

### Development Workflow

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and ensure they follow the project's coding standards

3. Run tests to make sure your changes don't break existing functionality:
   ```bash
   pytest
   ```

4. Commit your changes:
   ```bash
   git commit -m "Description of your changes"
   ```

5. Push your branch to GitHub:
   ```bash
   git push origin feature/your-feature-name
   ```

6. Create a Pull Request (PR) on GitHub

## Coding Standards

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guidelines
- Use [Black](https://black.readthedocs.io/) for code formatting
- Sort imports with [isort](https://pycqa.github.io/isort/)
- Use descriptive variable names and add docstrings to functions and classes
- Write tests for new features

## Pull Request Process

1. Ensure your code adheres to the project's coding standards
2. Update the documentation if necessary
3. Write or update tests as appropriate
4. Make sure all tests pass
5. Your PR should target the `main` branch
6. A maintainer will review your PR and may request changes
7. Once approved, a maintainer will merge your PR

## Testing

- Write unit tests for all new functionality
- Run the existing test suite to ensure your changes don't break anything
- Integration tests are encouraged for complex features

## Documentation

- Update the README.md if your changes affect usage
- Add docstrings to all public functions, classes, and methods
- Consider adding examples for new features

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code.

## Questions?

If you have any questions or need help, please open an issue on GitHub or reach out to the maintainers.

Thank you for contributing to IPFS Kit Python!