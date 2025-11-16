# Indexing Tests

This folder contains comprehensive tests for the indexing functionality:

## 1. test_indexing_complete.py
**Comprehensive unit and integration tests for all index functionality**

### What it tests (27 tests total):

#### Section 1: SQL Parsing (5 tests)
- ✅ CREATE INDEX parsing (basic, with/without semicolon, with USING clause)
- ✅ DROP INDEX parsing
- ✅ Multiple indexes on same table

#### Section 2: Catalog Operations (9 tests)
- ✅ Index creation success/failure
- ✅ Duplicate index rejection
- ✅ Validation (non-existent tables/columns)
- ✅ Index dropping
- ✅ Listing indexes
- ✅ Index persistence (save/load from disk)

#### Section 3: Query Integration (8 tests)
- ✅ SELECT with index (single match, multiple matches, no match)
- ✅ Index vs full scan equivalence
- ✅ CLI automatic index usage
- ✅ Multiple indexes on same table
- ✅ Index correctness after inserts
- ✅ Fallback to scan after index drop

#### Section 4: Edge Cases (5 tests)
- ✅ Index on empty table
- ✅ NULL value handling
- ✅ Many duplicate keys
- ✅ Case sensitivity
- ✅ Index name uniqueness

### How to run:
```powershell
# Run all indexing tests (27 tests)
python -m pytest tests/test_indexing_complete.py -v

# Run specific test section
python -m pytest tests/test_indexing_complete.py::TestIndexParsing -v
python -m pytest tests/test_indexing_complete.py::TestIndexCatalog -v
python -m pytest tests/test_indexing_complete.py::TestQueryIndexIntegration -v
python -m pytest tests/test_indexing_complete.py::TestIndexEdgeCases -v

# Run specific test
python -m pytest tests/test_indexing_complete.py::TestQueryIndexIntegration::test_select_with_index_single_match -v
```

---

## 2. test_index_performance.py
**Performance tests with large datasets (10k-100k rows)**

### What it tests:
- 📊 Data insertion speed
- 🔍 Index creation time
- ⚡ Query performance WITH vs WITHOUT indexes
- 📈 Speedup calculations

### Dataset sizes:
- **Small**: 10,000 rows
- **Medium**: 50,000 rows  
- **Large**: 100,000 rows

### How to run:

```powershell
# Run small dataset test (10k rows) - Quick test
python tests/test_index_performance.py --size small

# Run medium dataset test (50k rows)
python tests/test_index_performance.py --size medium

# Run large dataset test (100k rows)
python tests/test_index_performance.py --size large

# Run ALL performance tests (takes several minutes)
python tests/test_index_performance.py --size all
```

### Expected Output:
```
=============================================================
TEST 1: Small Dataset (10,000 rows)
=============================================================
🔧 Setting up test database...
✅ Test table 'users' created

📊 Inserting 10,000 rows...
✅ Inserted 10,000 rows in 2.34 seconds
   (4273.50 rows/second)

🔍 Testing index creation performance...
✅ Index created in 0.15 seconds

🔍 Testing 100 queries WITHOUT index (baseline)...
✅ 100 queries completed in 5.43 seconds
   Average: 54.30 ms per query

🔍 Testing 100 queries WITH index...
✅ 100 queries completed in 1.12 seconds
   Average: 11.20 ms per query

📈 Results Summary (10k rows):
  Data insertion: 2.34s
  Index creation: 0.15s
  Query without index: 54.30ms avg
  Query with index: 11.20ms avg
  Speedup: 4.85x
```

---

## Quick Test Commands

```powershell
# Navigate to project directory
cd "P:\5th sem\1Software Engineering\Project\alpaca\PESU_RR_CSE_F_P71_Automated_Database_Backup_System_Alpaca"

# Run functional tests (fast)
python -m pytest tests/test_indexing.py -v

# Run performance test (quick - 10k rows)
python tests/test_index_performance.py --size small

# Run comprehensive performance test (slow - all sizes)
python tests/test_index_performance.py --size all
```

---

## Test Categories

### Functional Tests (test_indexing.py)
- Parser validation
- Catalog operations
- Edge case handling
- Data persistence

### Performance Tests (test_index_performance.py)
- Large-scale data insertion
- Index creation overhead
- Query optimization validation
- Comparative analysis

---

## Notes

⚠️ **Performance tests create temporary database files:**
- Default location: `data/perf_test.db`
- Automatically cleaned up after tests
- May take several minutes for large datasets

💡 **Tips:**
- Run `test_indexing.py` first to verify functionality
- Run `test_index_performance.py --size small` for quick performance check
- Run larger datasets only when needed for comprehensive testing

---

## Interpreting Results

### Good Performance Indicators:
- ✅ Index creation completes quickly (< 1s for 10k rows)
- ✅ Queries with index are faster than without
- ✅ Speedup > 2x for indexed queries
- ✅ No errors during bulk operations

### Red Flags:
- ❌ Index creation takes very long
- ❌ Queries with index are slower (index overhead)
- ❌ Memory errors with large datasets
- ❌ Data corruption or loss
