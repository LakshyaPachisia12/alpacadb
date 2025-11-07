"""
Integration tests for parser with storage engine.
"""

import pytest
from src.storage import PageManager, Catalog, TableManager
from src.query import Lexer, Parser
from src.query.ast_nodes import *


@pytest.fixture
def setup_database(tmp_path):
    """Create temporary database for testing."""
    db_path = tmp_path / "test_integration.db"
    page_manager = PageManager(str(db_path))
    catalog = Catalog(page_manager)
    table_manager = TableManager(page_manager, catalog)
    
    yield page_manager, catalog, table_manager
    
    # Cleanup
    page_manager.close()

def parse_and_execute(query: str, catalog, table_manager):
    """Helper to parse and execute query."""
    lexer = Lexer(query)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    
    # Execute based on AST type
    if isinstance(ast, CreateTableNode):
        columns_dict = [
            {
                'name': col.name,
                'type': col.data_type,
                'nullable': col.nullable
            }
            for col in ast.columns
        ]
        return catalog.create_table(ast.table_name, columns_dict)
    
    elif isinstance(ast, InsertNode):
        return table_manager.insert_row(ast.table_name, ast.values)
    
    elif isinstance(ast, SelectNode):
        return table_manager.select_all(ast.table_name)
    
    return None


def test_end_to_end_workflow(setup_database):
    """Test complete workflow: CREATE → INSERT → SELECT."""
    page_manager, catalog, table_manager = setup_database
    
    # Step 1: CREATE TABLE
    create_query = "CREATE TABLE users (id INT PRIMARY KEY, name STRING, age INT)"
    result = parse_and_execute(create_query, catalog, table_manager)
    assert result == True
    
    # Verify table exists
    schema = catalog.get_table_schema('users')
    assert schema is not None
    assert len(schema.columns) == 3
    
    # Step 2: INSERT rows
    insert_queries = [
        "INSERT INTO users VALUES (1, 'Alice', 25)",
        "INSERT INTO users VALUES (2, 'Bob', 30)",
        "INSERT INTO users VALUES (3, 'Charlie', 35)"
    ]
    
    for query in insert_queries:
        result = parse_and_execute(query, catalog, table_manager)
        assert result == True
    
    # Step 3: SELECT data
    select_query = "SELECT * FROM users"
    rows = parse_and_execute(select_query, catalog, table_manager)
    
    assert len(rows) == 3
    assert rows[0] == [1, 'Alice', 25]
    assert rows[1] == [2, 'Bob', 30]
    assert rows[2] == [3, 'Charlie', 35]


def test_multiple_tables(setup_database):
    """Test creating and querying multiple tables."""
    page_manager, catalog, table_manager = setup_database
    
    # Create first table
    parse_and_execute(
        "CREATE TABLE employees (emp_id INT PRIMARY KEY, name STRING)",
        catalog, table_manager
    )
    
    # Create second table
    parse_and_execute(
        "CREATE TABLE departments (dept_id INT PRIMARY KEY, dept_name STRING)",
        catalog, table_manager
    )
    
    # Verify both exist
    tables = catalog.list_tables()
    assert 'employees' in tables
    assert 'departments' in tables
    
    # Insert into both
    parse_and_execute("INSERT INTO employees VALUES (101, 'Alice')", catalog, table_manager)
    parse_and_execute("INSERT INTO departments VALUES (1, 'Engineering')", catalog, table_manager)
    
    # Query both
    emp_rows = parse_and_execute("SELECT * FROM employees", catalog, table_manager)
    dept_rows = parse_and_execute("SELECT * FROM departments", catalog, table_manager)
    
    assert len(emp_rows) == 1
    assert len(dept_rows) == 1


def test_data_persistence(setup_database, tmp_path):
    """Test that data survives database restart."""
    page_manager, catalog, table_manager = setup_database
    db_path = tmp_path / "test_integration.db"
    
    # Create table and insert data
    parse_and_execute(
        "CREATE TABLE test (id INT PRIMARY KEY, value STRING)",
        catalog, table_manager
    )
    parse_and_execute("INSERT INTO test VALUES (1, 'persistent')", catalog, table_manager)
    
    # Close database
    page_manager.close()
    
    # Reopen database
    page_manager2 = PageManager(str(db_path))
    catalog2 = Catalog(page_manager2)
    table_manager2 = TableManager(page_manager2, catalog2)
    
    # Verify data still exists
    rows = parse_and_execute("SELECT * FROM test", catalog2, table_manager2)
    assert len(rows) == 1
    assert rows[0] == [1, 'persistent']
    
    page_manager2.close()


def test_complex_query_with_where(setup_database):
    """Test parsing and execution of queries with WHERE clause."""
    page_manager, catalog, table_manager = setup_database
    
    # Setup
    parse_and_execute(
        "CREATE TABLE products (id INT PRIMARY KEY, name STRING, price INT)",
        catalog, table_manager
    )
    
    parse_and_execute("INSERT INTO products VALUES (1, 'Laptop', 1000)", catalog, table_manager)
    parse_and_execute("INSERT INTO products VALUES (2, 'Mouse', 20)", catalog, table_manager)
    parse_and_execute("INSERT INTO products VALUES (3, 'Keyboard', 50)", catalog, table_manager)
    
    # Parse query with WHERE (note: actual WHERE execution is in CLI for Sprint 2)
    query = "SELECT * FROM products WHERE price > 30"
    lexer = Lexer(query)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    
    # Verify AST structure
    assert isinstance(ast, SelectNode)
    assert ast.where_clause is not None
    assert ast.where_clause.operator == '>'
