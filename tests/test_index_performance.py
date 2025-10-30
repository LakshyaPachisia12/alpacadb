"""
Performance tests for indexing with large datasets.

Tests index efficiency with 10k-100k rows.
"""

import os
import sys
import time
import random
import string

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage import PageManager, Catalog, TableManager
from src.storage.indexing.index_manager import IndexManager
from src.query import Lexer, Parser


class IndexPerformanceTester:
    """Test indexing performance with large datasets."""
    
    def __init__(self, db_path='data/perf_test.db'):
        """Initialize performance tester."""
        self.db_path = db_path
        self.page_manager = None
        self.catalog = None
        self.table_manager = None
        self.index_manager = None
        
    def setup(self):
        """Set up test database."""
        print("🔧 Setting up test database...")
        
        # Remove old test database if exists
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        # Create new database
        self.page_manager = PageManager(self.db_path)
        self.catalog = Catalog(self.page_manager)
        self.index_manager = IndexManager(self.catalog, self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog, self.index_manager)
        
        # Create test table
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': True},
            {'name': 'email', 'type': 'STRING', 'nullable': True},
            {'name': 'age', 'type': 'INT', 'nullable': True},
            {'name': 'city', 'type': 'STRING', 'nullable': True}
        ]
        self.catalog.create_table('users', columns)
        print("✅ Test table 'users' created")
    
    def cleanup(self):
        """Clean up test database."""
        # Close the page manager before attempting to delete
        if self.page_manager:
            self.page_manager.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            print("🗑️  Test database removed")
    
    def generate_random_string(self, length=10):
        """Generate random string."""
        return ''.join(random.choices(string.ascii_letters, k=length))
    
    def generate_random_email(self):
        """Generate random email."""
        username = self.generate_random_string(8)
        domain = random.choice(['gmail.com', 'yahoo.com', 'outlook.com', 'example.com'])
        return f"{username}@{domain}"
    
    def insert_bulk_data(self, num_rows):
        """Insert large number of rows into the database."""
        print(f"\n📊 Inserting {num_rows:,} rows...")
        
        start_time = time.time()
        
        for i in range(num_rows):
            values = [
                i + 1,                              # id
                self.generate_random_string(15),    # name
                self.generate_random_email(),       # email
                random.randint(18, 80),             # age
                random.choice(['NYC', 'LA', 'Chicago', 'Houston', 'Phoenix'])  # city
            ]
            
            if self.table_manager:
                self.table_manager.insert_row('users', values)
            
            # Progress indicator
            if (i + 1) % 1000 == 0:
                print(f"  Inserted {i + 1:,} rows...", end='\r')
        
        elapsed = time.time() - start_time
        rows_per_sec = num_rows / elapsed
        
        print(f"\n✅ Inserted {num_rows:,} rows in {elapsed:.2f} seconds")
        print(f"   ({rows_per_sec:.2f} rows/second)")
        
        return elapsed
    
    def test_create_index_performance(self):
        """Test index creation time on large dataset."""
        print("\n🔍 Testing index creation performance...")
        
        start_time = time.time()
        if self.index_manager:
            self.index_manager.create_index('idx_email', 'users', 'email')
        elapsed = time.time() - start_time
        
        print(f"✅ Index created in {elapsed:.2f} seconds")
        
        return elapsed
    
    def fetch_row_by_location(self, table_name: str, page_id: int, row_id: int):
        """
        Fetch a single row by its physical location.
        
        Args:
            table_name: Name of the table
            page_id: Page ID where row is stored
            row_id: Row ID within the page
            
        Returns:
            Row as list of values, or None if not found
        """
        if not self.catalog:
            return None
        schema = self.catalog.get_table_schema(table_name)
        if not schema:
            return None
        
        if not self.page_manager:
            return None
        page = self.page_manager.read_page(page_id)
        if not page or row_id >= len(page.records):
            return None
            
        try:
            record_bytes = page.records[row_id]
            if not self.table_manager:
                return None
            row = self.table_manager._deserialize_row(schema, record_bytes)
            return row
        except Exception as e:
            print(f"⚠️  Warning: Failed to fetch row: {e}")
            return None
    
    def test_query_without_index(self, num_queries=100):
        """Test query performance WITHOUT index (full table scan)."""
        print(f"\n🔍 Testing {num_queries} queries WITHOUT index (baseline)...")
        
        # Drop index if exists
        if not self.catalog or not self.index_manager:
            return 0.0, 0.0
        index = self.catalog.get_index('idx_email')
        if index:
            # Remove from IndexManager cache
            if 'idx_email' in self.index_manager._btrees:
                del self.index_manager._btrees['idx_email']
            # Remove from catalog
            if 'idx_email' in self.catalog.indexes:
                del self.catalog.indexes['idx_email']
                self.catalog._save_catalog()
        
        # Get column index for 'email' (should be index 2: id=0, name=1, email=2, age=3, city=4)
        email_col_idx = 2
        
        start_time = time.time()
        
        for i in range(num_queries):
            # Simulate searching for random email
            test_email = self.generate_random_email()
            if not self.table_manager:
                continue
            rows = self.table_manager.select_all('users')
            
            # Filter manually (simulating WHERE clause without index)
            # rows are returned as list of lists: [id, name, email, age, city]
            matches = [row for row in rows if row[email_col_idx] == test_email]
        
        elapsed = time.time() - start_time
        avg_query_time = (elapsed / num_queries) * 1000  # in milliseconds
        
        print(f"✅ {num_queries} queries completed in {elapsed:.2f} seconds")
        print(f"   Average: {avg_query_time:.2f} ms per query")
        
        return elapsed, avg_query_time
    
    def test_query_with_index(self, num_queries=100):
        """Test query performance WITH index."""
        print(f"\n🔍 Testing {num_queries} queries WITH index...")
        
        # Create index
        if not self.index_manager:
            return 0.0, 0.0
        self.index_manager.create_index('idx_email', 'users', 'email')
        
        start_time = time.time()
        
        for i in range(num_queries):
            # Simulate searching for random email
            test_email = self.generate_random_email()
            
            # ✅ USE THE INDEX instead of table scan!
            result = self.index_manager.search_index('idx_email', test_email)
            
            if result:
                # Index found the key - fetch the actual row
                page_id, row_id = result
                row = self.fetch_row_by_location('users', page_id, row_id)
                matches = [row] if row else []
            else:
                # Not found
                matches = []
        
        elapsed = time.time() - start_time
        avg_query_time = (elapsed / num_queries) * 1000  # in milliseconds
        
        print(f"✅ {num_queries} queries completed in {elapsed:.2f} seconds")
        print(f"   Average: {avg_query_time:.2f} ms per query")
        
        return elapsed, avg_query_time
    
    def run_small_dataset_test(self):
        """Run test with 10k rows."""
        print("\n" + "="*60)
        print("TEST 1: Small Dataset (10,000 rows)")
        print("="*60)
        
        self.setup()
        insert_time = self.insert_bulk_data(10000)
        index_time = self.test_create_index_performance()
        
        without_index_time, without_index_avg = self.test_query_without_index(100)
        with_index_time, with_index_avg = self.test_query_with_index(100)
        
        print("\n📈 Results Summary (10k rows):")
        print(f"  Data insertion: {insert_time:.2f}s")
        print(f"  Index creation: {index_time:.2f}s")
        print(f"  Query without index: {without_index_avg:.2f}ms avg")
        print(f"  Query with index: {with_index_avg:.2f}ms avg")
        
        if without_index_avg > 0:
            speedup = without_index_avg / with_index_avg if with_index_avg > 0 else 1
            print(f"  Speedup: {speedup:.2f}x")
        
        self.cleanup()
    
    def run_medium_dataset_test(self):
        """Run test with 50k rows."""
        print("\n" + "="*60)
        print("TEST 2: Medium Dataset (50,000 rows)")
        print("="*60)
        
        self.setup()
        insert_time = self.insert_bulk_data(50000)
        index_time = self.test_create_index_performance()
        
        without_index_time, without_index_avg = self.test_query_without_index(50)
        with_index_time, with_index_avg = self.test_query_with_index(50)
        
        print("\n📈 Results Summary (50k rows):")
        print(f"  Data insertion: {insert_time:.2f}s")
        print(f"  Index creation: {index_time:.2f}s")
        print(f"  Query without index: {without_index_avg:.2f}ms avg")
        print(f"  Query with index: {with_index_avg:.2f}ms avg")
        
        if without_index_avg > 0:
            speedup = without_index_avg / with_index_avg if with_index_avg > 0 else 1
            print(f"  Speedup: {speedup:.2f}x")
        
        self.cleanup()
    
    def run_large_dataset_test(self):
        """Run test with 100k rows."""
        print("\n" + "="*60)
        print("TEST 3: Large Dataset (100,000 rows)")
        print("="*60)
        
        self.setup()
        insert_time = self.insert_bulk_data(100000)
        index_time = self.test_create_index_performance()
        
        without_index_time, without_index_avg = self.test_query_without_index(25)
        with_index_time, with_index_avg = self.test_query_with_index(25)
        
        print("\n📈 Results Summary (100k rows):")
        print(f"  Data insertion: {insert_time:.2f}s")
        print(f"  Index creation: {index_time:.2f}s")
        print(f"  Query without index: {without_index_avg:.2f}ms avg")
        print(f"  Query with index: {with_index_avg:.2f}ms avg")
        
        if without_index_avg > 0:
            speedup = without_index_avg / with_index_avg if with_index_avg > 0 else 1
            print(f"  Speedup: {speedup:.2f}x")
        
        self.cleanup()
    
    def run_all_tests(self):
        """Run all performance tests."""
        print("\n" + "🚀 "*30)
        print("INDEXING PERFORMANCE TEST SUITE")
        print("🚀 "*30)
        
        try:
            self.run_small_dataset_test()
            self.run_medium_dataset_test()
            self.run_large_dataset_test()
            
            print("\n" + "="*60)
            print("✅ All performance tests completed!")
            print("="*60)
            
        except Exception as e:
            print(f"\n❌ Error during testing: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()


def main():
    """Main entry point for performance tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Index performance testing')
    parser.add_argument('--size', choices=['small', 'medium', 'large', 'all'],
                       default='small',
                       help='Dataset size to test (default: small)')
    
    args = parser.parse_args()
    
    tester = IndexPerformanceTester()
    
    if args.size == 'small':
        tester.run_small_dataset_test()
    elif args.size == 'medium':
        tester.run_medium_dataset_test()
    elif args.size == 'large':
        tester.run_large_dataset_test()
    else:  # all
        tester.run_all_tests()


if __name__ == '__main__':
    main()
