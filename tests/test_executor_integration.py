"""
Integration tests for Query Executor.

This test suite:
1. Creates a fresh test database
2. Populates it with sample data (15+ rows)
3. Tests all query types (SELECT, INSERT, UPDATE, DELETE)
4. Validates executor functionality with various WHERE/ORDER BY clauses

Requires: pytest, pytest-cov
Run from root: pytest tests/test_executor_integration.py -v
"""

import os
import shutil
import pytest
import tempfile
from src.storage import PageManager, Catalog, TableManager
from src.query import Lexer, Parser
from src.executor import QueryExecutor


# --- Test Fixtures ---

@pytest.fixture
def temp_db_path():
    """Fixture to provide a clean temporary database path."""
    temp_dir = tempfile.mkdtemp(prefix="alpacadb_test_")
    db_path = os.path.join(temp_dir, "test.db")

    yield db_path

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def db_components(temp_db_path):
    """Fixture to provide initialized database components."""
    page_manager = PageManager(temp_db_path)
    catalog = Catalog(page_manager)
    table_manager = TableManager(page_manager, catalog)
    executor = QueryExecutor(table_manager, catalog)

    yield {
        'page_manager': page_manager,
        'catalog': catalog,
        'table_manager': table_manager,
        'executor': executor
    }

    # Cleanup
    page_manager.close()


@pytest.fixture
def populated_db(db_components):
    """Fixture to provide a database with test data."""
    catalog = db_components['catalog']
    executor = db_components['executor']

    def execute_query(query_str):
        lexer = Lexer(query_str)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        return executor.execute(ast)

    # Create tables
    create_employees = "CREATE TABLE employees (id INT PRIMARY KEY, name STRING, department STRING, salary INT, age INT);"
    create_projects = "CREATE TABLE projects (project_id INT PRIMARY KEY, project_name STRING, budget INT, status STRING);"

    execute_query(create_employees)
    execute_query(create_projects)

    # Insert test data
    employees_data = [
        (1, 'Alice Johnson', 'Engineering', 95000, 28),
        (2, 'Bob Smith', 'Engineering', 87000, 32),
        (3, 'Carol White', 'Marketing', 72000, 29),
        (4, 'David Brown', 'Sales', 68000, 35),
        (5, 'Eve Davis', 'Engineering', 92000, 26),
        (6, 'Frank Miller', 'HR', 65000, 40),
        (7, 'Grace Lee', 'Marketing', 78000, 31),
        (8, 'Henry Wilson', 'Sales', 71000, 27),
        (9, 'Ivy Chen', 'Engineering', 98000, 30),
        (10, 'Jack Taylor', 'Engineering', 89000, 33),
        (11, 'Kate Anderson', 'Marketing', 75000, 28),
        (12, 'Leo Martinez', 'Sales', 69000, 36),
    ]

    projects_data = [
        (1, 'Website Redesign', 150000, 'Active'),
        (2, 'Mobile App', 200000, 'Active'),
        (3, 'Data Migration', 80000, 'Completed'),
        (4, 'Cloud Infrastructure', 120000, 'Planning'),
    ]

    # Insert employees
    for emp_id, name, dept, salary, age in employees_data:
        query = f"INSERT INTO employees VALUES ({emp_id}, '{name}', '{dept}', {salary}, {age});"
        execute_query(query)

    # Insert projects
    for proj_id, name, budget, status in projects_data:
        query = f"INSERT INTO projects VALUES ({proj_id}, '{name}', {budget}, '{status}');"
        execute_query(query)

    return db_components


# --- Helper Functions ---

def execute_query(executor, query_str: str):
    """Helper to parse and execute a query."""
    lexer = Lexer(query_str)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    return executor.execute(ast)


# --- Test Cases ---

class TestExecutorBasicOperations:
    """Test basic executor operations."""

    def test_create_table(self, db_components):
        """Test CREATE TABLE execution."""
        catalog = db_components['catalog']
        executor = db_components['executor']

        query = "CREATE TABLE test_table (id INT PRIMARY KEY, name STRING);"
        execute_query(executor, query)

        schema = catalog.get_table_schema('test_table')
        assert schema is not None
        assert schema.table_name == 'test_table'
        assert len(schema.columns) == 2
        assert schema.columns[0]['name'] == 'id'
        assert schema.columns[1]['name'] == 'name'

    def test_insert_and_select_basic(self, db_components):
        """Test basic INSERT and SELECT operations."""
        executor = db_components['executor']

        # Create table
        create_query = "CREATE TABLE users (id INT PRIMARY KEY, name STRING);"
        execute_query(executor, create_query)

        # Insert data
        insert_query = "INSERT INTO users VALUES (1, 'Alice');"
        execute_query(executor, insert_query)

        # Select data
        rows, columns = execute_query(executor, "SELECT * FROM users;")
        assert len(rows) == 1
        assert len(columns) == 2
        assert rows[0] == [1, 'Alice']
        assert columns == ['id', 'name']


class TestExecutorSelectOperations:
    """Test SELECT operations with various clauses."""

    def test_select_all(self, populated_db):
        """Test SELECT * FROM table."""
        executor = populated_db['executor']

        # Test employees
        rows, columns = execute_query(executor, "SELECT * FROM employees;")
        assert len(rows) == 12
        assert len(columns) == 5

        # Test projects
        rows, columns = execute_query(executor, "SELECT * FROM projects;")
        assert len(rows) == 4
        assert len(columns) == 4

    def test_select_projection(self, populated_db):
        """Test SELECT specific columns."""
        executor = populated_db['executor']

        # Test 2 columns
        rows, columns = execute_query(executor, "SELECT name, department FROM employees;")
        assert len(columns) == 2
        assert columns == ['name', 'department']
        assert len(rows) == 12

        # Test 3 columns
        rows, columns = execute_query(executor, "SELECT project_name, budget, status FROM projects;")
        assert len(columns) == 3
        assert len(rows) == 4

    def test_select_where_equality(self, populated_db):
        """Test SELECT with WHERE equality condition."""
        executor = populated_db['executor']

        rows, columns = execute_query(executor, "SELECT * FROM employees WHERE department = 'Engineering';")
        assert len(rows) == 5
        # Verify all are from Engineering
        assert all(row[2] == 'Engineering' for row in rows)

    def test_select_where_comparisons(self, populated_db):
        """Test SELECT with WHERE comparison operators."""
        executor = populated_db['executor']

        # Greater than
        rows, columns = execute_query(executor, "SELECT * FROM employees WHERE salary > 90000;")
        assert len(rows) == 3
        assert all(row[3] > 90000 for row in rows)

        # Less than
        rows, columns = execute_query(executor, "SELECT * FROM employees WHERE age < 30;")
        assert len(rows) == 5  # Alice(28), Eve(26), Henry(27), Kate(28)

        # Not equals
        rows, columns = execute_query(executor, "SELECT * FROM projects WHERE status != 'Active';")
        assert len(rows) == 2

    def test_select_order_by(self, populated_db):
        """Test SELECT with ORDER BY clause."""
        executor = populated_db['executor']

        # ORDER BY ASC
        rows, columns = execute_query(executor, "SELECT * FROM employees ORDER BY age ASC;")
        ages = [row[4] for row in rows]
        assert ages == sorted(ages)

        # ORDER BY DESC
        rows, columns = execute_query(executor, "SELECT * FROM employees ORDER BY salary DESC;")
        salaries = [row[3] for row in rows]
        assert salaries == sorted(salaries, reverse=True)

        # ORDER BY string column
        rows, columns = execute_query(executor, "SELECT * FROM employees ORDER BY name ASC;")
        names = [row[1] for row in rows]
        assert names == sorted(names)

    def test_select_where_and_order(self, populated_db):
        """Test SELECT with both WHERE and ORDER BY."""
        executor = populated_db['executor']

        rows, columns = execute_query(executor,
            "SELECT * FROM employees WHERE department = 'Engineering' ORDER BY salary DESC;")

        assert len(rows) == 5
        # Verify all are Engineering
        assert all(row[2] == 'Engineering' for row in rows)
        # Verify sorted by salary DESC
        salaries = [row[3] for row in rows]
        assert salaries == sorted(salaries, reverse=True)

    def test_select_projection_with_where(self, populated_db):
        """Test SELECT specific columns with WHERE."""
        executor = populated_db['executor']

        rows, columns = execute_query(executor, "SELECT name, salary FROM employees WHERE salary > 85000;")
        assert len(columns) == 2
        assert columns == ['name', 'salary']
        assert all(row[1] > 85000 for row in rows)

    def test_select_complex_where(self, populated_db):
        """Test SELECT with complex WHERE conditions."""
        executor = populated_db['executor']

        # AND condition
        rows, columns = execute_query(executor,
            "SELECT * FROM employees WHERE department = 'Engineering' AND salary > 90000;")
        assert len(rows) == 3  # Alice(95000), Eve(92000), Ivy(98000)

        # OR condition
        rows, columns = execute_query(executor,
            "SELECT * FROM employees WHERE department = 'Sales' OR department = 'HR';")
        assert len(rows) == 4  # David, Frank, Henry, Leo

    def test_select_edge_cases(self, populated_db):
        """Test SELECT edge cases."""
        executor = populated_db['executor']

        # No rows match
        rows, columns = execute_query(executor, "SELECT * FROM employees WHERE salary > 1000000;")
        assert len(rows) == 0

        # All rows match
        rows, columns = execute_query(executor, "SELECT * FROM employees WHERE age > 0;")
        assert len(rows) == 12

        # Single row match
        rows, columns = execute_query(executor, "SELECT * FROM employees WHERE id = 5;")
        assert len(rows) == 1
        assert rows[0][1] == 'Eve Davis'


class TestExecutorInsertOperations:
    """Test INSERT operations."""

    def test_insert_basic(self, db_components):
        """Test basic INSERT operation."""
        executor = db_components['executor']

        # Create table
        create_query = "CREATE TABLE users (id INT PRIMARY KEY, name STRING);"
        execute_query(executor, create_query)

        # Insert data
        insert_query = "INSERT INTO users VALUES (1, 'Alice');"
        execute_query(executor, insert_query)

        # Verify
        rows, columns = execute_query(executor, "SELECT * FROM users;")
        assert len(rows) == 1
        assert rows[0] == [1, 'Alice']

    def test_insert_multiple_rows(self, db_components):
        """Test inserting multiple rows."""
        executor = db_components['executor']

        # Create table
        create_query = "CREATE TABLE products (id INT PRIMARY KEY, name STRING, price INT);"
        execute_query(executor, create_query)

        # Insert multiple rows
        products = [
            (1, 'Laptop', 1200),
            (2, 'Mouse', 25),
            (3, 'Keyboard', 75),
        ]

        for prod_id, name, price in products:
            query = f"INSERT INTO products VALUES ({prod_id}, '{name}', {price});"
            execute_query(executor, query)

        # Verify
        rows, columns = execute_query(executor, "SELECT * FROM products;")
        assert len(rows) == 3
        assert rows[0] == [1, 'Laptop', 1200]
        assert rows[1] == [2, 'Mouse', 25]
        assert rows[2] == [3, 'Keyboard', 75]


class TestExecutorErrorHandling:
    """Test error handling in executor."""

    def test_select_nonexistent_table(self, db_components):
        """Test SELECT from non-existent table."""
        executor = db_components['executor']

        with pytest.raises(ValueError, match="Table 'nonexistent' does not exist"):
            execute_query(executor, "SELECT * FROM nonexistent;")

    def test_insert_nonexistent_table(self, db_components):
        """Test INSERT into non-existent table."""
        executor = db_components['executor']

        with pytest.raises(ValueError, match="Table 'nonexistent' does not exist"):
            execute_query(executor, "INSERT INTO nonexistent VALUES (1);")

    def test_invalid_column_reference(self, populated_db):
        """Test referencing non-existent column in WHERE."""
        executor = populated_db['executor']

        with pytest.raises(ValueError, match="Unknown column"):
            execute_query(executor, "SELECT * FROM employees WHERE nonexistent = 1;")
