# DINQ Tests

This directory contains all tests for the DINQ project, organized into categories for better maintainability and clarity.

## Test Categories

### API Tests (`api_tests/`)

Tests for API endpoints and server routes.

- `test_scholar_pk_api.py` - Tests for the Scholar PK API
- `test_talents.py` - Tests for the top talents API
- `test_report_generator.py` - Tests for report generation API

### Database Tests (`db_tests/`)

Tests for database operations, caching, and persistence.

- `test_db.py` - Basic database connection and operations tests
- `test_db_cache.py` - Tests for database caching functionality
- `test_db_cache_mock.py` - Tests with mock data for database caching
- `test_scholar_cache.py` - Tests for scholar data caching
- `test_scholar_cache_simple.py` - Simplified tests for scholar caching
- `test_scholar_service_cache.py` - Tests for scholar service with caching
- `test_scholar_service_cache_full.py` - Full tests for scholar service caching
- `test_stream_processor_cache.py` - Tests for stream processor with caching

### Integration Tests (`integration_tests/`)

Tests that cover multiple components working together.

- `test_daiheng_gao_search.py` - Integration tests for Daiheng Gao search
- `test_scholar_search.py` - Integration tests for scholar search functionality
- `test_scholar_fix.py` - Tests for scholar data fixes and corrections
- `test_full_flow.py` - End-to-end tests for the full application flow
- `test_level_info_robustness.py` - Tests for robustness of level information

### Unit Tests (`unit_tests/`)

Tests for individual functions and classes.

- `test_filter_scholar.py` - Tests for scholar filtering functions
- `test_scholar.py` - Tests for scholar-related functions
- `test_scholar_id.py` - Tests for scholar ID handling
- `test_year_distribution.py` - Tests for year distribution calculations
- `test_kimi_evaluator.py` - Tests for Kimi evaluator functionality

### Configuration Tests (`config_tests/`)

Tests for configuration and environment settings.

- `test_env_config.py` - Tests for environment configuration

## Running Tests

To run all tests:

```bash
python -m unittest discover -s tests
```

To run tests in a specific category:

```bash
python -m unittest discover -s tests/api_tests
python -m unittest discover -s tests/db_tests
python -m unittest discover -s tests/integration_tests
python -m unittest discover -s tests/unit_tests
python -m unittest discover -s tests/config_tests
```

To run a specific test file:

```bash
python -m unittest tests/api_tests/test_scholar_pk_api.py
```

## Adding New Tests

When adding new tests, please follow these guidelines:

1. Place the test in the appropriate category directory
2. Name the file with a `test_` prefix
3. Use descriptive test method names that explain what is being tested
4. Include docstrings for test classes and methods
5. Keep tests focused on a single functionality or component
