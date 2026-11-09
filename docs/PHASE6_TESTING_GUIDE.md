# Phase 6 Testing Guide

Complete guide for running, maintaining, and extending the Phase 6 test suite.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Suite Overview](#test-suite-overview)
3. [Running Tests](#running-tests)
4. [Coverage Reports](#coverage-reports)
5. [Test Organization](#test-organization)
6. [Writing New Tests](#writing-new-tests)
7. [Troubleshooting](#troubleshooting)
8. [CI/CD Integration](#cicd-integration)

---

## Quick Start

### Install Dependencies

```bash
# Core dependencies
pip install pytest pytest-cov pytest-anyio anyio

# Optional dependencies (for all tests to run)
pip install fastapi uvicorn cbor2 rdflib matplotlib sentence-transformers wasmtime

# Or install from requirements
pip install -r requirements-test.txt
```

### Run All Phase 6 Tests

```bash
# Basic run
pytest tests/test_phase6_*.py -v

# With coverage
pytest tests/test_phase6_*.py --cov=ipfs_kit_py --cov-report=html

# Fast run (parallel)
pytest tests/test_phase6_*.py -n auto
```

---

## Test Suite Overview

### Test Files (10 files, 400+ tests)

| File | Tests | Purpose | Coverage Target |
|------|-------|---------|-----------------|
| test_phase6_mobile_sdk_100.py | 14 | Mobile SDK | 100% ✅ |
| test_phase6_s3_gateway_comprehensive.py | 60 | S3 Gateway | 80%+ |
| test_phase6_wasm_comprehensive.py | 70 | WASM Support | 85%+ |
| test_phase6_multiregion_comprehensive.py | 40 | Multi-Region | 95%+ |
| test_phase6_final_comprehensive.py | 50 | GraphRAG/Analytics/Bucket | 80-90%+ |
| test_phase6_edge_cases.py | 45 | Edge Cases | Comprehensive |
| test_phase6_integration.py | 25 | Integration | End-to-end |
| test_phase6_final_coverage.py | 40 | Final Coverage | Complete |
| test_phase6_fixtures.py | N/A | Fixtures & Utilities | Support |
| test_phase6_parametrized.py | 100+ | Parameterized Tests | Efficient |

**Total:** 400+ test combinations

---

## Running Tests

### By Module

```bash
# Mobile SDK (100% coverage)
pytest tests/test_phase6_mobile_sdk_100.py -v

# S3 Gateway
pytest tests/test_phase6_s3_gateway_comprehensive.py -v

# WASM Support
pytest tests/test_phase6_wasm_comprehensive.py -v

# Multi-Region Cluster
pytest tests/test_phase6_multiregion_comprehensive.py -v

# GraphRAG, Analytics, Bucket Metadata
pytest tests/test_phase6_final_comprehensive.py -v

# Edge Cases
pytest tests/test_phase6_edge_cases.py -v

# Integration Tests
pytest tests/test_phase6_integration.py -v

# Parameterized Tests
pytest tests/test_phase6_parametrized.py -v
```

### By Feature

```bash
# Test specific feature
pytest tests/test_phase6_*.py -k "mobile_sdk" -v
pytest tests/test_phase6_*.py -k "s3_gateway" -v
pytest tests/test_phase6_*.py -k "wasm" -v
pytest tests/test_phase6_*.py -k "multiregion" -v
pytest tests/test_phase6_*.py -k "graphrag" -v
pytest tests/test_phase6_*.py -k "analytics" -v
pytest tests/test_phase6_*.py -k "bucket" -v
```

### By Test Type

```bash
# Error handling tests
pytest tests/test_phase6_*.py -k "error" -v

# Edge case tests
pytest tests/test_phase6_*.py -k "edge" -v

# Integration tests
pytest tests/test_phase6_*.py -k "integration" -v

# Performance tests
pytest tests/test_phase6_*.py -k "performance" -v
```

### Test Selection

```bash
# Run specific test class
pytest tests/test_phase6_mobile_sdk_100.py::TestMobileSDKErrorHandling -v

# Run specific test
pytest tests/test_phase6_mobile_sdk_100.py::TestMobileSDKErrorHandling::test_ios_sdk_generation_error_handling -v

# Run with markers
pytest tests/test_phase6_*.py -m anyio -v  # All async tests
```

---

## Coverage Reports

### Generate Coverage Report

```bash
# HTML report (recommended)
pytest tests/test_phase6_*.py \
       --cov=ipfs_kit_py \
       --cov-report=html \
       --cov-report=term

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Coverage by Module

```bash
# Mobile SDK coverage
pytest tests/test_phase6_mobile_sdk_100.py \
       --cov=ipfs_kit_py/mobile_sdk \
       --cov-report=term-missing

# S3 Gateway coverage
pytest tests/test_phase6_s3_gateway_comprehensive.py \
       --cov=ipfs_kit_py/s3_gateway \
       --cov-report=term-missing

# All PR features
pytest tests/test_phase6_*.py \
       --cov=ipfs_kit_py/mobile_sdk \
       --cov=ipfs_kit_py/s3_gateway \
       --cov=ipfs_kit_py/wasm_support \
       --cov=ipfs_kit_py/multi_region_cluster \
       --cov=ipfs_kit_py/graphrag \
       --cov=ipfs_kit_py/analytics_dashboard \
       --cov=ipfs_kit_py/bucket_metadata_transfer \
       --cov-report=html
```

### Coverage Thresholds

```bash
# Fail if coverage below threshold
pytest tests/test_phase6_*.py \
       --cov=ipfs_kit_py \
       --cov-fail-under=80 \
       --cov-report=term
```

---

## Test Organization

### Directory Structure

```
tests/
├── test_phase6_mobile_sdk_100.py          # Mobile SDK tests
├── test_phase6_s3_gateway_comprehensive.py # S3 Gateway tests
├── test_phase6_wasm_comprehensive.py      # WASM tests
├── test_phase6_multiregion_comprehensive.py # Multi-region tests
├── test_phase6_final_comprehensive.py     # GraphRAG/Analytics/Bucket
├── test_phase6_edge_cases.py              # Edge cases
├── test_phase6_integration.py             # Integration tests
├── test_phase6_final_coverage.py          # Final coverage
├── test_phase6_fixtures.py                # Shared fixtures
└── test_phase6_parametrized.py            # Parameterized tests
```

### Test Class Organization

Each test file contains multiple test classes:
- **Feature tests:** Core functionality
- **Error tests:** Error handling
- **Edge case tests:** Boundary conditions
- **Integration tests:** Cross-feature workflows

### Naming Conventions

```python
# Test files
test_phase6_<module>_<type>.py

# Test classes
class Test<Feature><TestType>:
    """Test <feature> <test type>."""
    
# Test methods
def test_<what_is_being_tested>(self):
    """Test <specific behavior>."""
```

---

## Writing New Tests

### Using Fixtures

```python
def test_with_mock_ipfs(mock_ipfs_client):
    """Test using mock IPFS client."""
    # mock_ipfs_client is available from fixtures
    result = await some_operation(mock_ipfs_client)
    assert result is not None
```

### Using Test Data Factory

```python
def test_with_factory(test_data_factory):
    """Test using data factory."""
    region = test_data_factory.create_region(
        region_id="custom-region",
        priority=5
    )
    assert region["region_id"] == "custom-region"
```

### Writing Parameterized Tests

```python
@pytest.mark.parametrize("input_value,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_doubling(input_value, expected):
    """Test doubling function."""
    assert double(input_value) == expected
```

### Writing Async Tests

```python
@pytest.mark.anyio
async def test_async_operation():
    """Test async operation."""
    result = await async_function()
    assert result is not None
```

### Test Template

```python
class TestNewFeature:
    """Test new feature functionality."""
    
    def test_basic_operation(self):
        """Test basic operation succeeds."""
        # Arrange
        feature = NewFeature()
        
        # Act
        result = feature.do_something()
        
        # Assert
        assert result is not None
        assert result.status == "success"
    
    def test_error_handling(self):
        """Test error handling."""
        feature = NewFeature()
        
        with pytest.raises(ValueError):
            feature.do_invalid_operation()
    
    @pytest.mark.anyio
    async def test_async_operation(self):
        """Test async operation."""
        feature = NewFeature()
        result = await feature.do_async_operation()
        assert result is not None
```

---

## Troubleshooting

### Common Issues

#### Issue: ModuleNotFoundError

```bash
# Install missing dependencies
pip install <missing-module>

# Or skip tests requiring it
pytest tests/test_phase6_*.py -k "not fastapi"
```

#### Issue: Tests Running Slowly

```bash
# Run in parallel
pytest tests/test_phase6_*.py -n auto

# Run specific subset
pytest tests/test_phase6_mobile_sdk_100.py -v
```

#### Issue: Coverage Not Generated

```bash
# Ensure pytest-cov is installed
pip install pytest-cov

# Check coverage settings in pytest.ini or pyproject.toml
```

#### Issue: Async Tests Failing

```bash
# Ensure pytest-anyio is installed
pip install pytest-anyio anyio

# Check for proper @pytest.mark.anyio decorator
```

### Debug Mode

```bash
# Run with verbose output
pytest tests/test_phase6_*.py -vv

# Show print statements
pytest tests/test_phase6_*.py -s

# Drop into debugger on failure
pytest tests/test_phase6_*.py --pdb

# Show locals on failure
pytest tests/test_phase6_*.py -l
```

### Selective Testing

```bash
# Run only failed tests from last run
pytest tests/test_phase6_*.py --lf

# Run failed tests first, then others
pytest tests/test_phase6_*.py --ff

# Stop on first failure
pytest tests/test_phase6_*.py -x

# Stop after N failures
pytest tests/test_phase6_*.py --maxfail=3
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Phase 6 Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install pytest pytest-cov pytest-anyio anyio
        pip install -r requirements.txt
    
    - name: Run Phase 6 tests
      run: |
        pytest tests/test_phase6_*.py \
               --cov=ipfs_kit_py \
               --cov-report=xml \
               --cov-report=term
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        file: ./coverage.xml
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest tests/test_phase6_*.py --exitfirst
```

### Makefile

```makefile
.PHONY: test test-phase6 test-cov

test-phase6:
	pytest tests/test_phase6_*.py -v

test-cov:
	pytest tests/test_phase6_*.py \
	       --cov=ipfs_kit_py \
	       --cov-report=html

test-fast:
	pytest tests/test_phase6_*.py -n auto
```

---

## Performance Benchmarks

### Running Benchmarks

```bash
# Run with timing
pytest tests/test_phase6_*.py --durations=10

# Profile tests
pytest tests/test_phase6_*.py --profile

# Memory profiling (requires pytest-memprof)
pytest tests/test_phase6_*.py --memprof
```

### Expected Performance

- **Total test time:** 10-30 seconds
- **Average test time:** 0.05-0.1 seconds
- **Slowest tests:** Integration tests (~0.5 seconds)

---

## Maintenance

### Regular Tasks

1. **Update fixtures** when APIs change
2. **Add tests** for new features
3. **Review coverage** monthly
4. **Update documentation** as needed
5. **Clean up** deprecated tests

### Best Practices

- ✅ Keep tests isolated and independent
- ✅ Use fixtures for common setup
- ✅ Mock external dependencies
- ✅ Test both success and failure paths
- ✅ Use descriptive test names
- ✅ Document complex test scenarios
- ✅ Maintain ~80%+ coverage
- ✅ Run tests before committing

---

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-anyio Documentation](https://github.com/agronholm/anyio)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)

---

## Contact & Support

For issues or questions about the test suite:
1. Check this documentation
2. Review test file docstrings
3. Check existing test examples
4. Open an issue in the repository

**Happy Testing!** 🎉
