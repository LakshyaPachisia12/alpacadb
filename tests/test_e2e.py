"""
End-to-End Integration Tests.

Tests complete workflows from SQL queries through optimizer, executor, and storage.
"""

import pytest
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage import PageManager, Catalog, TableManager
from src.storage.indexing.index_manager import IndexManager
from src.query import Lexer, Parser
from src.executor import QueryExecutor


class TestE2EQueryWorkflows:
    """End-to-end tests for complete query workflows."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        temp_dir = tempfile.mkdtemp(prefix="e2e_test_")
        db_path = os.path.join(temp_dir, "test.db")
        
        page_manager = PageManager(db_path)
        catalog = Catalog(page_manager)
        index_manager = IndexManager(catalog, page_manager)
        table_manager = TableManager(page_manager, catalog, index_manager)
        executor = QueryExecutor(table_manager, catalog, index_manager)
        
        yield {
            'page_manager': page_manager,
            'catalog': catalog,
            'index_manager': index_manager,
            'table_manager': table_manager,
            'executor': executor
        }
        
        # Cleanup
        page_manager.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def _execute_sql(self, executor, sql):
        """Helper to execute SQL query."""
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        return executor.execute(ast)
    
    def test_create_table_insert_select(self, temp_db):
        """Test CREATE TABLE -> INSERT -> SELECT workflow."""
        executor = temp_db['executor']
        
        # CREATE TABLE
        create_sql = """
        CREATE TABLE employees (
            id INT,
            name STRING,
            dept STRING,
            salary INT
        );
        """
        self._execute_sql(executor, create_sql)
        
        # INSERT rows
        inserts = [
            "INSERT INTO employees VALUES (1, 'Alice', 'Engineering', 90000);",
            "INSERT INTO employees VALUES (2, 'Bob', 'Sales', 70000);",
            "INSERT INTO employees VALUES (3, 'Charlie', 'Engineering', 95000);",
            "INSERT INTO employees VALUES (4, 'Diana', 'HR', 60000);"
        ]
        for insert_sql in inserts:
            self._execute_sql(executor, insert_sql)
        
        # SELECT all
        rows, columns = self._execute_sql(executor, "SELECT * FROM employees;")
        
        assert len(rows) == 4
        assert columns == ['id', 'name', 'dept', 'salary']
        assert executor.last_plan == 'SeqScan'
    
    def test_create_index_automatic_usage(self, temp_db):
        """Test CREATE INDEX -> SELECT automatically uses index."""
        executor = temp_db['executor']
        catalog = temp_db['catalog']
        
        # Create table and insert data
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'email', 'type': 'STRING', 'nullable': True}
        ]
        catalog.create_table('users', columns)
        
        inserts = [
            "INSERT INTO users VALUES (1, 'alice@test.com');",
            "INSERT INTO users VALUES (2, 'bob@test.com');",
            "INSERT INTO users VALUES (3, 'charlie@test.com');"
        ]
        for insert_sql in inserts:
            self._execute_sql(executor, insert_sql)
        
        # Query without index - should use SeqScan
        rows_before, _ = self._execute_sql(
            executor, "SELECT * FROM users WHERE email = 'bob@test.com';"
        )
        assert executor.last_plan == 'SeqScan'
        assert len(rows_before) == 1
        
        # CREATE INDEX
        self._execute_sql(executor, "CREATE INDEX idx_email ON users(email);")
        
        # Query with index - should automatically use IndexScan
        rows_after, _ = self._execute_sql(
            executor, "SELECT * FROM users WHERE email = 'bob@test.com';"
        )
        assert executor.last_plan == 'IndexScan'
        assert len(rows_after) == 1
        
        # Results should be identical
        assert rows_before == rows_after
    
    def test_drop_index_falls_back_to_seqscan(self, temp_db):
        """Test DROP INDEX -> SELECT falls back to SeqScan."""
        executor = temp_db['executor']
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        
        # Setup table and index
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'code', 'type': 'STRING', 'nullable': True}
        ]
        catalog.create_table('products', columns)
        
        self._execute_sql(executor, "INSERT INTO products VALUES (1, 'ABC123');")
        self._execute_sql(executor, "INSERT INTO products VALUES (2, 'XYZ789');")
        
        index_manager.create_index('idx_code', 'products', 'code')
        
        # SELECT with index
        rows_with_index, _ = self._execute_sql(
            executor, "SELECT * FROM products WHERE code = 'ABC123';"
        )
        # For 2 rows with 2 distinct values (50% selectivity), cost-based optimizer
        # may choose SeqScan as it's cheaper. This is correct behavior.
        assert executor.last_plan in ('IndexScan', 'SeqScan')
        
        # DROP INDEX
        self._execute_sql(executor, "DROP INDEX idx_code ON products;")
        
        # Query after drop - should fall back to SeqScan
        rows_without_index, _ = self._execute_sql(
            executor, "SELECT * FROM products WHERE code = 'ABC123';"
        )
        assert executor.last_plan == 'SeqScan'
        
        # Results should still be correct
        assert rows_with_index == rows_without_index
    
    def test_insert_update_select_with_index(self, temp_db):
        """Test INSERT -> UPDATE -> SELECT with index maintenance."""
        executor = temp_db['executor']
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        
        # Setup
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'status', 'type': 'STRING', 'nullable': True}
        ]
        catalog.create_table('orders', columns)
        index_manager.create_index('idx_status', 'orders', 'status')
        
        # INSERT
        self._execute_sql(executor, "INSERT INTO orders VALUES (1, 'pending');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (2, 'pending');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (3, 'shipped');")
        
        # SELECT with index
        rows, _ = self._execute_sql(
            executor, "SELECT * FROM orders WHERE status = 'pending';"
        )
        # Phase 2: For 3 rows with 2 distinct values (50% selectivity), cost-based optimizer
        # may choose SeqScan as it's cheaper on small tables. This is correct behavior.
        assert executor.last_plan in ('IndexScan', 'SeqScan')
        # Verify correctness regardless of plan choice
        assert len(rows) == 2
        
        # UPDATE (should trigger index rebuild)
        self._execute_sql(
            executor, "UPDATE orders SET status = 'shipped' WHERE id = 1;"
        )
        
        # SELECT again - should reflect update
        rows_after, _ = self._execute_sql(
            executor, "SELECT * FROM orders WHERE status = 'pending';"
        )
        # Phase 2: Cost-based optimizer may choose SeqScan for small tables with low selectivity
        assert executor.last_plan in ('IndexScan', 'SeqScan')
        assert len(rows_after) == 1  # Only one pending now
        
        rows_shipped, _ = self._execute_sql(
            executor, "SELECT * FROM orders WHERE status = 'shipped';"
        )
        assert len(rows_shipped) == 2  # Two shipped now
    
    def test_insert_delete_select_with_index(self, temp_db):
        """Test INSERT -> DELETE -> SELECT with index maintenance."""
        executor = temp_db['executor']
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        
        # Setup
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'category', 'type': 'STRING', 'nullable': True}
        ]
        catalog.create_table('items', columns)
        index_manager.create_index('idx_category', 'items', 'category')
        
        # INSERT
        self._execute_sql(executor, "INSERT INTO items VALUES (1, 'electronics');")
        self._execute_sql(executor, "INSERT INTO items VALUES (2, 'books');")
        self._execute_sql(executor, "INSERT INTO items VALUES (3, 'electronics');")
        
        # SELECT before delete
        rows_before, _ = self._execute_sql(
            executor, "SELECT * FROM items WHERE category = 'electronics';"
        )
        # Phase 2: Cost-based optimizer may choose SeqScan for small tables with low selectivity
        assert executor.last_plan in ('IndexScan', 'SeqScan')
        assert len(rows_before) == 2
        
        # DELETE (should trigger index rebuild)
        self._execute_sql(executor, "DELETE FROM items WHERE id = 1;")
        
        # SELECT after delete
        rows_after, _ = self._execute_sql(
            executor, "SELECT * FROM items WHERE category = 'electronics';"
        )
        # Phase 2: Cost-based optimizer may choose SeqScan for small tables
        assert executor.last_plan in ('IndexScan', 'SeqScan')
        assert len(rows_after) == 1
    
    def test_complex_multi_query_workflow(self, temp_db):
        """Test complex workflow with multiple operations."""
        executor = temp_db['executor']
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        
        # 1. CREATE TABLE
        columns = [
            {'name': 'user_id', 'type': 'INT', 'nullable': False},
            {'name': 'username', 'type': 'STRING', 'nullable': False},
            {'name': 'email', 'type': 'STRING', 'nullable': False},
            {'name': 'active', 'type': 'INT', 'nullable': False}
        ]
        catalog.create_table('users', columns)
        
        # 2. INSERT initial data
        users = [
            (1, 'alice', 'alice@test.com', 1),
            (2, 'bob', 'bob@test.com', 1),
            (3, 'charlie', 'charlie@test.com', 0),
            (4, 'diana', 'diana@test.com', 1),
        ]
        for user_id, username, email, active in users:
            self._execute_sql(
                executor,
                f"INSERT INTO users VALUES ({user_id}, '{username}', '{email}', {active});"
            )
        
        # 3. Query without index
        rows, _ = self._execute_sql(
            executor, "SELECT * FROM users WHERE email = 'bob@test.com';"
        )
        assert executor.last_plan == 'SeqScan'
        assert len(rows) == 1
        
        # 4. CREATE INDEX on email
        index_manager.create_index('idx_email', 'users', 'email')
        
        # 5. Query with index
        rows, _ = self._execute_sql(
            executor, "SELECT username FROM users WHERE email = 'alice@test.com';"
        )
        assert executor.last_plan == 'IndexScan'
        assert rows[0] == ['alice']
        
        # 6. UPDATE email (triggers rebuild)
        self._execute_sql(
            executor,
            "UPDATE users SET email = 'alice.new@test.com' WHERE user_id = 1;"
        )
        
        # 7. Query old email - should return nothing
        rows, _ = self._execute_sql(
            executor, "SELECT * FROM users WHERE email = 'alice@test.com';"
        )
        assert len(rows) == 0
        
        # 8. Query new email - should find updated record
        rows, _ = self._execute_sql(
            executor, "SELECT username FROM users WHERE email = 'alice.new@test.com';"
        )
        assert len(rows) == 1
        assert rows[0] == ['alice']
        
        # 9. DELETE inactive user
        self._execute_sql(executor, "DELETE FROM users WHERE active = 0;")
        
        # 10. SELECT all - should have 3 users
        rows, _ = self._execute_sql(executor, "SELECT * FROM users;")
        assert len(rows) == 3
        
        # 11. DROP INDEX
        index_manager.drop_index('idx_email', 'users')
        
        # 12. Query falls back to SeqScan
        rows, _ = self._execute_sql(
            executor, "SELECT * FROM users WHERE email = 'bob@test.com';"
        )
        assert executor.last_plan == 'SeqScan'
        assert len(rows) == 1
    
    def test_select_with_projection_and_filter(self, temp_db):
        """Test SELECT with column projection, WHERE, and ORDER BY."""
        executor = temp_db['executor']
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        
        # Setup
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'product', 'type': 'STRING', 'nullable': False},
            {'name': 'price', 'type': 'INT', 'nullable': False},
            {'name': 'stock', 'type': 'INT', 'nullable': False}
        ]
        catalog.create_table('inventory', columns)
        
        items = [
            (1, 'Laptop', 1200, 5),
            (2, 'Mouse', 25, 50),
            (3, 'Keyboard', 75, 30),
            (4, 'Monitor', 300, 15),
        ]
        for item_id, product, price, stock in items:
            self._execute_sql(
                executor,
                f"INSERT INTO inventory VALUES ({item_id}, '{product}', {price}, {stock});"
            )
        
        # Create index
        index_manager.create_index('idx_product', 'inventory', 'product')
        
        # SELECT with projection and WHERE (uses index)
        rows, columns_out = self._execute_sql(
            executor,
            "SELECT product, price FROM inventory WHERE product = 'Mouse';"
        )
        
        assert executor.last_plan == 'IndexScan'
        assert columns_out == ['product', 'price']
        assert len(rows) == 1
        assert rows[0] == ['Mouse', 25]
    
    def test_multiple_indexes_different_columns(self, temp_db):
        """Test multiple indexes on different columns."""
        executor = temp_db['executor']
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        
        # Setup
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': False},
            {'name': 'dept', 'type': 'STRING', 'nullable': False}
        ]
        catalog.create_table('staff', columns)
        
        staff = [
            (1, 'Alice', 'Engineering'),
            (2, 'Bob', 'Sales'),
            (3, 'Charlie', 'Engineering'),
        ]
        for staff_id, name, dept in staff:
            self._execute_sql(
                executor,
                f"INSERT INTO staff VALUES ({staff_id}, '{name}', '{dept}');"
            )
        
        # Create indexes on both columns
        index_manager.create_index('idx_name', 'staff', 'name')
        index_manager.create_index('idx_dept', 'staff', 'dept')
        
        # Query by name - uses idx_name
        rows, _ = self._execute_sql(
            executor, "SELECT * FROM staff WHERE name = 'Alice';"
        )
        assert executor.last_plan == 'IndexScan'
        assert len(rows) == 1
        
        # Query by dept - uses idx_dept
        rows, _ = self._execute_sql(
            executor, "SELECT * FROM staff WHERE dept = 'Engineering';"
        )
        # Phase 2: Cost-based optimizer may choose SeqScan for 3 rows with 2 categories (50% selectivity)
        assert executor.last_plan in ('IndexScan', 'SeqScan')
        assert len(rows) == 2


class TestE2EErrorHandling:
    """Test error handling in E2E workflows."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        temp_dir = tempfile.mkdtemp(prefix="e2e_error_test_")
        db_path = os.path.join(temp_dir, "test.db")
        
        page_manager = PageManager(db_path)
        catalog = Catalog(page_manager)
        index_manager = IndexManager(catalog, page_manager)
        table_manager = TableManager(page_manager, catalog, index_manager)
        executor = QueryExecutor(table_manager, catalog, index_manager)
        
        yield {
            'page_manager': page_manager,
            'catalog': catalog,
            'index_manager': index_manager,
            'executor': executor
        }
        
        # Cleanup
        page_manager.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def _execute_sql(self, executor, sql):
        """Helper to execute SQL query."""
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        return executor.execute(ast)
    
    def test_index_on_nonexistent_table_fails(self, temp_db):
        """Test CREATE INDEX on non-existent table fails gracefully."""
        executor = temp_db['executor']
        
        with pytest.raises(Exception):  # Should raise ValueError or similar
            self._execute_sql(executor, "CREATE INDEX idx_test ON nonexistent(col);")
    
    def test_select_nonexistent_index_falls_back(self, temp_db):
        """Test SELECT still works even if index doesn't exist."""
        executor = temp_db['executor']
        catalog = temp_db['catalog']
        
        columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
        catalog.create_table('test', columns)
        
        self._execute_sql(executor, "INSERT INTO test VALUES (1);")
        
        # Query should work even without index
        rows, _ = self._execute_sql(executor, "SELECT * FROM test WHERE id = 1;")
        assert len(rows) == 1
        assert executor.last_plan == 'SeqScan'
    
    def test_inner_join_basic(self, temp_db):
        """Test basic INNER JOIN functionality."""
        executor = temp_db['executor']
        
        # Create users table
        self._execute_sql(executor, """
        CREATE TABLE users (
            id INT,
            name STRING
        );
        """)
        
        # Create orders table
        self._execute_sql(executor, """
        CREATE TABLE orders (
            id INT,
            user_id INT,
            product STRING
        );
        """)
        
        # Insert test data
        self._execute_sql(executor, "INSERT INTO users VALUES (1, 'Alice');")
        self._execute_sql(executor, "INSERT INTO users VALUES (2, 'Bob');")
        self._execute_sql(executor, "INSERT INTO users VALUES (3, 'Charlie');")
        
        self._execute_sql(executor, "INSERT INTO orders VALUES (1, 1, 'Laptop');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (2, 1, 'Mouse');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (3, 2, 'Keyboard');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (4, 99, 'Monitor');")  # No matching user
        
        # Test INNER JOIN
        rows, columns = self._execute_sql(executor, 
            "SELECT users.name, orders.product FROM users INNER JOIN orders ON users.id = orders.user_id;")
        
        # Should have 3 rows (orders 1, 2, 3 match users 1, 1, 2)
        assert len(rows) == 3
        assert columns == ['name', 'product']
        
        # Check the results
        results = [(row[0], row[1]) for row in rows]
        expected = [
            ('Alice', 'Laptop'),
            ('Alice', 'Mouse'), 
            ('Bob', 'Keyboard')
        ]
        assert sorted(results) == sorted(expected)
        
        assert executor.last_plan == 'Join'

    def test_left_join_basic(self, temp_db):
        """Test basic LEFT JOIN functionality."""
        executor = temp_db['executor']

        # Create tables
        self._execute_sql(executor, """
        CREATE TABLE users (
            id INT,
            name STRING
        );
        """)

        self._execute_sql(executor, """
        CREATE TABLE orders (
            id INT,
            user_id INT,
            product STRING
        );
        """)
        self._execute_sql(executor, "INSERT INTO users VALUES (1, 'Alice');")
        self._execute_sql(executor, "INSERT INTO users VALUES (2, 'Bob');")
        self._execute_sql(executor, "INSERT INTO users VALUES (3, 'Charlie');")

        self._execute_sql(executor, "INSERT INTO orders VALUES (1, 1, 'Laptop');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (2, 1, 'Mouse');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (3, 2, 'Keyboard');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (4, 99, 'Monitor');")

        rows, columns = self._execute_sql(executor,
            "SELECT users.name, orders.product FROM users LEFT JOIN orders ON users.id = orders.user_id;")

        # LEFT JOIN should include all users; Charlie has no matching order
        assert len(rows) == 4
        assert columns == ['name', 'product']

    def test_right_join_basic(self, temp_db):
        """Test basic RIGHT JOIN functionality."""
        executor = temp_db['executor']

        # Create tables
        self._execute_sql(executor, """
        CREATE TABLE users (
            id INT,
            name STRING
        );
        """)

        self._execute_sql(executor, """
        CREATE TABLE orders (
            id INT,
            user_id INT,
            product STRING
        );
        """)
        self._execute_sql(executor, "INSERT INTO users VALUES (1, 'Alice');")
        self._execute_sql(executor, "INSERT INTO users VALUES (2, 'Bob');")
        self._execute_sql(executor, "INSERT INTO users VALUES (3, 'Charlie');")

        self._execute_sql(executor, "INSERT INTO orders VALUES (1, 1, 'Laptop');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (2, 1, 'Mouse');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (3, 2, 'Keyboard');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (4, 99, 'Monitor');")

        rows, columns = self._execute_sql(executor,
            "SELECT users.name, orders.product FROM users RIGHT JOIN orders ON users.id = orders.user_id;")

        # RIGHT JOIN should include all orders; the Monitor row has no matching user
        assert len(rows) == 4
        assert columns == ['name', 'product']

    def test_full_join_basic(self, temp_db):
        """Test basic FULL JOIN functionality."""
        executor = temp_db['executor']

        # Create tables
        self._execute_sql(executor, """
        CREATE TABLE users (
            id INT,
            name STRING
        );
        """)

        self._execute_sql(executor, """
        CREATE TABLE orders (
            id INT,
            user_id INT,
            product STRING
        );
        """)
        self._execute_sql(executor, "INSERT INTO users VALUES (2, 'Bob');")
        self._execute_sql(executor, "INSERT INTO users VALUES (3, 'Charlie');")

        self._execute_sql(executor, "INSERT INTO orders VALUES (1, 1, 'Laptop');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (2, 1, 'Mouse');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (3, 2, 'Keyboard');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (4, 99, 'Monitor');")

        rows, columns = self._execute_sql(executor,
            "SELECT users.name, orders.product FROM users FULL JOIN orders ON users.id = orders.user_id;")

        # Should include all matched pairs, plus unmatched rows from both sides
        assert len(rows) == 5
        assert columns == ['name', 'product']

    def test_cross_join_basic(self, temp_db):
        """Test CROSS JOIN (Cartesian product)."""
        executor = temp_db['executor']

        # Create tables
        self._execute_sql(executor, """
        CREATE TABLE users (
            id INT,
            name STRING
        );
        """)

        self._execute_sql(executor, """
        CREATE TABLE orders (
            id INT,
            user_id INT,
            product STRING
        );
        """)
        self._execute_sql(executor, "INSERT INTO users VALUES (1, 'Alice');")
        self._execute_sql(executor, "INSERT INTO users VALUES (2, 'Bob');")
        self._execute_sql(executor, "INSERT INTO users VALUES (3, 'Charlie');")

        self._execute_sql(executor, "INSERT INTO orders VALUES (1, 1, 'Laptop');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (2, 1, 'Mouse');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (3, 2, 'Keyboard');")
        self._execute_sql(executor, "INSERT INTO orders VALUES (4, 99, 'Monitor');")

        rows, columns = self._execute_sql(executor,
            "SELECT users.name, orders.product FROM users CROSS JOIN orders;")

        # Cartesian product: 3 users * 4 orders
        assert len(rows) == 12
        assert columns == ['name', 'product']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
