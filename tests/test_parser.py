"""
Unit tests for Parser.
"""

import pytest
from src.query import Lexer, Parser, ParseError
from src.query.ast_nodes import *


def parse_query(query: str):
    """Helper to parse query."""
    lexer = Lexer(query)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def test_parse_create_table():
    """Test CREATE TABLE parsing."""
    query = "CREATE TABLE users (id INT PRIMARY KEY, name STRING, age INT)"
    ast = parse_query(query)
    
    assert isinstance(ast, CreateTableNode)
    assert ast.table_name == "users"
    assert len(ast.columns) == 3
    
    assert ast.columns[0].name == "id"
    assert ast.columns[0].data_type == "INT"
    assert ast.columns[0].is_primary_key == True
    
    assert ast.columns[1].name == "name"
    assert ast.columns[1].data_type == "STRING"


def test_parse_insert():
    """Test INSERT parsing."""
    query = "INSERT INTO users VALUES (1, 'Alice', 25)"
    ast = parse_query(query)
    
    assert isinstance(ast, InsertNode)
    assert ast.table_name == "users"
    assert ast.values == [1, 'Alice', 25]


def test_parse_select_star():
    """Test SELECT * parsing."""
    query = "SELECT * FROM users"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert ast.columns == ['*']
    assert ast.table_name == "users"
    assert ast.where_clause is None


def test_parse_select_with_where():
    """Test SELECT with WHERE clause."""
    query = "SELECT * FROM users WHERE age > 18"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert ast.where_clause is not None
    assert isinstance(ast.where_clause, BinaryOp)
    assert ast.where_clause.operator == '>'


def test_parse_select_with_order_by():
    """Test SELECT with ORDER BY."""
    query = "SELECT * FROM users ORDER BY name ASC"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert ast.order_by == ('name', 'ASC')


def test_parse_update():
    """Test UPDATE parsing."""
    query = "UPDATE users SET age=26, name='Bob' WHERE id=1"
    ast = parse_query(query)
    
    assert isinstance(ast, UpdateNode)
    assert ast.table_name == "users"
    assert len(ast.assignments) == 2
    assert ast.assignments[0] == ('age', 26)


def test_parse_delete():
    """Test DELETE parsing."""
    query = "DELETE FROM users WHERE age < 18"
    ast = parse_query(query)
    
    assert isinstance(ast, DeleteNode)
    assert ast.table_name == "users"
    assert ast.where_clause is not None


def test_parse_transaction_commands():
    """Test transaction command parsing."""
    for command in ['BEGIN', 'COMMIT', 'ROLLBACK']:
        ast = parse_query(command)
        assert isinstance(ast, TransactionNode)
        assert ast.command == command


def test_parse_create_index():
    """Test CREATE INDEX parsing."""
    query = "CREATE INDEX idx_age ON users (age)"
    ast = parse_query(query)
    
    assert isinstance(ast, CreateIndexNode)
    assert ast.index_name == "idx_age"
    assert ast.table_name == "users"
    assert ast.column_name == "age"


def test_parse_invalid_syntax():
    """Test error on invalid syntax."""
    with pytest.raises(ParseError):
        parse_query("SELCET * FROM users")  # Typo


def test_parse_missing_semicolon():
    """Test that semicolon is optional."""
    # Should parse successfully without semicolon
    ast = parse_query("SELECT * FROM users")
    assert isinstance(ast, SelectNode)
    
    # Should also parse with semicolon
    ast = parse_query("SELECT * FROM users;")
    assert isinstance(ast, SelectNode)