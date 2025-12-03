# Test Suite Documentation

This directory contains the comprehensive test suite for the OParl Data Pipeline project.

## 📁 Test Structure

```
tests/
├── README.md                # This file
├── conftest.py              # Shared pytest fixtures
├── run_tests.py             # Custom test runner with CLI
├── test_client.py           # OParlClient API tests
├── test_extraction.py       # PDF extraction tests
├── test_storage.py          # Parquet/RDF/GeoJSON storage tests
├── test_state.py            # State management & checkpoint tests
├── test_spatial.py          # Location extraction & geocoding tests
└── test_integration.py      # End-to-end pipeline tests
```

## 🎯 Test Philosophy

### Unit Tests (Mocked, Fast)
All unit tests use **mocking** to avoid external dependencies:
- **No network calls** - API responses are mocked
- **No real PDFs** - Small fake PDF bytes are used
- **No actual geocoding** - Geocoding results are mocked
- **Fast execution** - All unit tests complete in seconds

### Integration Tests (Real Data, Slow)
Integration tests use real data and external services:
- Marked with `@pytest.mark.slow`
- May require network access
- Can be skipped with `--fast` flag

## 🚀 Running Tests

### Quick Start

```bash
# Install test dependencies first
pip install pytest pytest-cov pytest-xdist

# Run all tests
python tests/run_tests.py

# Or use pytest directly
pytest tests/
```

### Common Test Commands

```bash
# Only unit tests (fast, no network)
python tests/run_tests.py --unit

# Only integration tests
python tests/run_tests.py --integration

# Skip slow tests
python tests/run_tests.py --fast

# Skip tests requiring network
python tests/run_tests.py --no-network

# Run specific test file
pytest tests/test_extraction.py -v

# Run specific test function
pytest tests/test_client.py::TestOParlClient::test_init -v

# Run with coverage report
python tests/run_tests.py --coverage
pytest --cov=src --cov-report=html tests/
```

### Parallel Execution

```bash
# Run tests in parallel (requires pytest-xdist)
python tests/run_tests.py --parallel
pytest -n auto tests/
```

## 🔧 Test Fixtures (conftest.py)

Shared fixtures available in all tests:

### Directory & Config
- `temp_dir` - Temporary directory for test outputs (auto-cleanup)
- `mock_config` - Mock configuration dictionary

### OParl Test Data
- `mock_paper` - Mock OParl Paper object with PDF URL
- `mock_meeting` - Mock OParl Meeting object
- `mock_pdf_text` - Sample extracted PDF text

### Spatial Test Data
- `mock_location` - Mock extracted location with coordinates

### RDF Test Data
- `sample_rdf_graph` - Example RDF graph for validation tests

## 📝 Test Coverage by Module

### test_client.py
Tests the OParl API client:
- ✓ HTTP requests with retry logic
- ✓ Pagination handling
- ✓ Date filtering
- ✓ Error handling (404, timeouts, invalid JSON)
- ✓ Rate limiting

### test_extraction.py
Tests PDF text extraction with **ephemeral storage**:
- ✓ PyMuPDF extraction (primary method)
- ✓ pdfplumber fallback (for tables)
- ✓ OCR fallback (for scanned PDFs)
- ✓ Large PDF handling (>10MB uses temp files)
- ✓ HTTP download with retry
- ✓ Batch extraction with threading
- ✓ PDFExtractionResult dataclass

**Note on Ephemeral Storage:**
The extraction module uses temporary files for large PDFs (>10MB) to prevent memory overflow. Tests **mock** this behavior with small fake PDFs, so no actual temp files are created during testing.

### test_storage.py
Tests data persistence:
- ✓ Parquet writing (partitioned by city/year)
- ✓ RDF/Turtle serialization
- ✓ GeoJSON export for mapping
- ✓ Incremental N-Triples append
- ✓ Data schema validation

### test_state.py
Tests pipeline state management:
- ✓ Resource tracking (processed/failed/skipped)
- ✓ Checkpoint creation & recovery
- ✓ SQLite persistence
- ✓ Resumable pipeline execution
- ✓ Failed resource retry logic

### test_spatial.py
Tests location extraction & geocoding:
- ✓ NER with spaCy (German model)
- ✓ Regex pattern matching (B-Pläne, Flurnummern)
- ✓ Fuzzy matching (Levenshtein distance)
- ✓ OSM validation
- ✓ Geocoding with Nominatim
- ✓ Cache functionality

### test_integration.py
End-to-end pipeline tests:
- ✓ Complete data flow (API → PDF → Location → Storage)
- ✓ Batch processing
- ✓ Error recovery
- ✓ Data provenance tracking
- ✓ Multi-format output validation

## 🏷️ Test Markers

Tests are marked for selective execution:

```python
@pytest.mark.slow          # Long-running tests (>5 seconds)
@pytest.mark.network       # Requires internet connection
@pytest.mark.optional      # Optional features (Wikidata, ML)
```

Run specific markers:
```bash
pytest -m "not slow" tests/           # Skip slow tests
pytest -m "not network" tests/        # Skip network tests
pytest -m "slow" tests/               # Only slow tests
```

## 📊 Coverage Reports

Generate HTML coverage reports:

```bash
pytest --cov=src --cov-report=html tests/
open htmlcov/index.html  # macOS
```

Target coverage: **>80%** for core modules

## 🐛 Troubleshooting

### Import Errors

```bash
# Add src to Python path
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"

# Or use editable install
pip install -e .
```

### Missing pytest

```bash
pip install pytest pytest-cov pytest-xdist
```

### Mock Errors

If tests fail with import errors on mocked modules:
- Check that `unittest.mock.patch` targets are correct
- Verify import paths match actual module structure
- Use `patch('module.function')` not `patch('function')`

### Fixture Not Found

If a fixture is not available:
- Check `conftest.py` for fixture definition
- Ensure fixture name matches function parameter
- Verify pytest is discovering `conftest.py`

## 📚 Writing New Tests

### Basic Test Template

```python
import pytest
from unittest.mock import Mock, patch

def test_my_feature(mock_config, temp_dir):
    """Test description"""
    # Arrange
    component = MyComponent(mock_config)

    # Act
    result = component.do_something()

    # Assert
    assert result is not None
    assert result.success is True
```

### Testing with Mocks

```python
@patch('requests.get')
def test_with_network_mock(mock_get, mock_config):
    """Test HTTP calls without actual network"""
    mock_response = Mock()
    mock_response.json.return_value = {'data': 'test'}
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    client = OParlClient(mock_config)
    result = client.fetch_data()

    assert result == {'data': 'test'}
```

### Testing Ephemeral Storage

When testing components that use temporary files:

```python
def test_temp_file_handling(temp_dir):
    """Test that temp files are properly cleaned up"""
    extractor = PDFExtractor()

    # This should use temp files internally
    result = extractor.extract_from_bytes(large_pdf_bytes)

    # Temp files should be cleaned up automatically
    assert result.used_ephemeral_storage is True
    assert result.success is True
```

## 🔍 Debugging Tests

### Verbose Output

```bash
pytest tests/ -v -s          # Show print statements
pytest tests/ -vv            # Extra verbose
pytest tests/ --tb=short     # Shorter tracebacks
```

### Run Single Test

```bash
pytest tests/test_extraction.py::TestPDFExtractor::test_init -v
```

### Debug with pdb

```python
def test_debugging():
    import pdb; pdb.set_trace()  # Breakpoint
    result = function_to_debug()
    assert result == expected
```

### Check Test Discovery

```bash
pytest --collect-only tests/
```

## 📖 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Guide](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py Docs](https://coverage.readthedocs.io/)
- [Main Testing Guide](../TESTING.md)

## ✅ Test Checklist

Before committing:
- [ ] All tests pass locally
- [ ] New features have tests
- [ ] Test coverage >80%
- [ ] No network dependencies in unit tests
- [ ] Mocks are properly cleaned up
- [ ] Test names are descriptive
- [ ] Slow tests are marked with `@pytest.mark.slow`
