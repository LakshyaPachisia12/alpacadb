# 🧪 Complete Indexing Test Guide for AlpacaDB

This guide explains all indexing-related tests and how to run them.

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Test Files Overview](#test-files-overview)
3. [Running Tests](#running-tests)
4. [Test Coverage](#test-coverage)
5. [Performance Tests](#performance-tests)

---

## 🚀 Quick Start

### Run ALL Indexing Tests (Recommended)

```powershell
# Run the comprehensive master test suite
pytest tests/test_full_indexing_suite.py -v

# Run with output (see print statements)
pytest tests/test_full_indexing_suite.py -v -s

# Run without slow tests (faster validation)
pytest tests/test_full_indexing_suite.py -v -m "not slow"
```

### Run Individual Test Suites

```powershell
# B-Tree data structure tests
pytest tests/test_full_indexing_suite.py::TestBTreeDataStructure -v

# SQL parsing tests
pytest tests/test_full_indexing_suite.py::TestIndexSQLParsing -v

# Index manager tests
pytest tests/test_full_indexing_suite.py::TestIndexManager -v

# Catalog integration tests
pytest tests/test_full_indexing_suite.py::TestCatalogIntegration -v

# Query optimizer tests
pytest tests/test_full_indexing_suite.py::TestQueryOptimizer -v

# Query executor tests
pytest tests/test_full_indexing_suite.py::TestQueryExecutor -v

# End-to-end integration tests
pytest tests/test_full_indexing_suite.py::TestEndToEndIntegration -v

# Edge cases tests
pytest tests/test_full_indexing_suite.py::TestEdgeCases -v

# Performance tests (marked as slow)
pytest tests/test_full_indexing_suite.py::TestPerformance -v
```

---

## 📁 Test Files Overview

### 🎯 Master Test Suite (PRIMARY)

**File:** `test_full_indexing_suite.py`

**Description:** Comprehensive test suite with ALL indexing tests in one organized file.

**Contains:** 51+ tests organized into 9 sections:
- ✅ B-Tree Data Structure (7 tests)
- ✅ SQL Parsing (5 tests)
- ✅ Index Manager (11 tests)
- ✅ Catalog Integration (6 tests)
- ✅ Query Optimizer (6 tests)
- ✅ Query Executor (6 tests)
- ✅ End-to-End Integration (3 tests)
- ✅ Edge Cases (5 tests)
- ✅ Performance (2 tests)

**Why use this?** 
- ✅ Single file with all indexing tests
- ✅ Well-organized into logical sections
- ✅ Easy to run all or specific sections
- ✅ Complete coverage

**Replaces:** `test_btree_basic.py`, `test_indexing.py`, `test_indexing_complete.py`, `test_optimizer.py` (removed)

---

### 📊 Performance Benchmark Script (SUPPLEMENTAL)

**File:** `test_index_performance.py`
**Focus:** Performance benchmarks with large datasets (standalone script)
```powershell
# Small dataset (10k rows)
python tests/test_index_performance.py --size small

# Large dataset (100k rows)
python tests/test_index_performance.py --size large

# All benchmarks
python tests/test_index_performance.py --size all
```
**Tests:**
- Data insertion speed (10k-100k rows)
- Index creation time
- Query performance (with vs without index)
- Speedup calculations

**Note:** This is a standalone script (not pytest-based) for detailed benchmarking.

---

### 📚 Other Test Files (Non-Indexing)

These files test other components and should be kept:

- `test_storage.py` - Storage engine (pages, catalog, table operations)
- `test_lexer.py` - Lexer/tokenization
- `test_parser.py` - SQL parser (general)
- `test_integration_parser.py` - Parser integration
- `test_executor_integration.py` - Executor (UPDATE, DELETE, etc.)
- `test_e2e.py` - End-to-end workflows

---

## 🧪 Test Coverage

### What is Tested

#### ✅ B-Tree Implementation
- [x] Insert operations
- [x] Search operations (single & all)
- [x] Node splitting
- [x] Duplicate key handling
- [x] Serialization/deserialization
- [x] Persistence to disk

#### ✅ SQL Parsing
- [x] CREATE INDEX basic syntax
- [x] CREATE INDEX with USING clause
- [x] DROP INDEX
- [x] Multiple index commands

#### ✅ Index Manager
- [x] Index creation
- [x] Index dropping
- [x] Search operations
- [x] Multiple indexes per table
- [x] Automatic maintenance on INSERT
- [x] B-Tree caching
- [x] Error handling

#### ✅ Catalog Integration
- [x] Index metadata storage
- [x] Index persistence
- [x] Duplicate name rejection
- [x] List indexes
- [x] Get indexes for table

#### ✅ Query Optimizer
- [x] SeqScan selection (no index)
- [x] IndexScan selection (with index)
- [x] Equality predicate detection
- [x] Complex WHERE clauses (AND/OR)
- [x] Multiple index scenarios
- [x] No WHERE clause handling

#### ✅ Query Executor
- [x] IndexScanOperator execution
- [x] Integration with optimizer
- [x] Projection with indexes
- [x] Sorting with indexes
- [x] Correctness verification

#### ✅ End-to-End
- [x] CREATE TABLE → INSERT → CREATE INDEX → SELECT
- [x] Multiple queries same index
- [x] DROP INDEX fallback
- [x] Real-world workflows

#### ✅ Edge Cases
- [x] Empty table indexing
- [x] NULL value handling
- [x] Many duplicate keys
- [x] Large datasets
- [x] Index after many inserts

#### ✅ Performance
- [x] Index creation benchmarks
- [x] Query speedup measurements
- [x] Scalability tests

---

## ⚡ Performance Tests

### Quick Performance Check

```powershell
# Run performance tests (may take a few minutes)
pytest tests/test_full_indexing_suite.py::TestPerformance -v -s
```

### Detailed Performance Benchmark

```powershell
# Comprehensive benchmark with multiple dataset sizes
python tests/test_index_performance.py --size all
```

**Expected Results:**
- **10k rows:** ~4-5x speedup with index
- **50k rows:** ~10-15x speedup with index
- **100k rows:** ~20-30x speedup with index

---

## 🎯 Recommended Test Workflow

### During Development
```powershell
# Quick validation (fast tests only)
pytest tests/test_full_indexing_suite.py -v -m "not slow"
```

### Before Committing
```powershell
# Run all indexing tests
pytest tests/test_full_indexing_suite.py -v
```

### Before Release
```powershell
# Run ALL tests including performance
pytest tests/test_full_indexing_suite.py -v
python tests/test_index_performance.py --size all
```

---

## 📊 Test Statistics

### Coverage Summary
- **Total Tests:** 51+ comprehensive indexing tests
- **Test Files:** 7 files (+ 1 master suite)
- **Lines of Test Code:** 2000+
- **Coverage Areas:** 9 major components

### Test Distribution
```
TestBTreeDataStructure       7 tests   (13.7%)
TestIndexSQLParsing          5 tests   ( 9.8%)
TestIndexManager            11 tests   (21.6%)
TestCatalogIntegration       6 tests   (11.8%)
TestQueryOptimizer           6 tests   (11.8%)
TestQueryExecutor            6 tests   (11.8%)
TestEndToEndIntegration      3 tests   ( 5.9%)
TestEdgeCases                5 tests   ( 9.8%)
TestPerformance              2 tests   ( 3.9%)
                            ──────────────────
                            51 tests  (100.0%)
```

---

## 🐛 Troubleshooting

### Tests Fail with "pytest not found"
```powershell
# Install pytest
pip install pytest

# Or activate virtual environment first
.\v_alpaca\Scripts\activate
pip install pytest
```

### Tests Fail with Import Errors
```powershell
# Make sure you're in the project root
cd "P:\5th sem\1Software Engineering\Project\alpaca\PESU_RR_CSE_F_P71_Automated_Database_Backup_System_Alpaca"

# Run tests
pytest tests/test_full_indexing_suite.py -v
```

### Performance Tests are Slow
```powershell
# Skip slow tests
pytest tests/test_full_indexing_suite.py -v -m "not slow"

# Or run only fast tests
pytest tests/test_full_indexing_suite.py -v --durations=0
```

---

## ✅ Success Criteria

All tests should pass with output like:

```
tests/test_full_indexing_suite.py::TestBTreeDataStructure::test_btree_insert_single PASSED
tests/test_full_indexing_suite.py::TestBTreeDataStructure::test_btree_insert_multiple PASSED
tests/test_full_indexing_suite.py::TestBTreeDataStructure::test_btree_insert_causes_split PASSED
...
tests/test_full_indexing_suite.py::TestPerformance::test_query_speedup_with_index PASSED

================================================ 51 passed in 15.23s ================================================
```

---

## 📝 Notes

- **Master Suite:** `test_full_indexing_suite.py` is the recommended way to run all tests
- **Individual Files:** Original test files still work independently
- **Performance Tests:** Marked with `@pytest.mark.slow` decorator
- **Temporary Files:** All tests use temporary databases (auto-cleaned)
- **Isolation:** Each test is independent (no side effects)

---

## 🎓 For Developers

### Adding New Index Tests

Add tests to the master suite (`test_full_indexing_suite.py`):

```python
class TestNewFeature:
    """Test new indexing feature."""
    
    def test_new_functionality(self):
        """Test description."""
        # Your test code here
        assert expected == actual
```

### Running Specific Tests

```powershell
# Run single test by name
pytest tests/test_full_indexing_suite.py::TestBTreeDataStructure::test_btree_insert_single -v

# Run tests matching pattern
pytest tests/test_full_indexing_suite.py -k "btree" -v

# Run with coverage
pytest tests/test_full_indexing_suite.py --cov=src.storage.indexing -v
```

---

**Happy Testing! 🦙**
