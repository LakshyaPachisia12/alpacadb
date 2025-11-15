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


def test_parse_select_count():
    """Test SELECT with COUNT aggregate."""
    query = "SELECT COUNT(*) FROM users"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert ast.table_name == "users"
    assert len(ast.aggregates) == 1
    
    agg = ast.aggregates[0]
    assert agg.func_name == "COUNT"
    assert agg.column is None  # COUNT(*)
    assert agg.alias is None


def test_parse_select_count_column():
    """Test SELECT with COUNT(column)."""
    query = "SELECT COUNT(age) FROM users"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert len(ast.aggregates) == 1
    
    agg = ast.aggregates[0]
    assert agg.func_name == "COUNT"
    assert agg.column == "age"


def test_parse_select_multiple_aggregates():
    """Test SELECT with multiple aggregates."""
    query = "SELECT COUNT(*), SUM(salary), AVG(age) FROM employees"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert len(ast.aggregates) == 3
    
    assert ast.aggregates[0].func_name == "COUNT"
    assert ast.aggregates[0].column is None
    
    assert ast.aggregates[1].func_name == "SUM"
    assert ast.aggregates[1].column == "salary"
    
    assert ast.aggregates[2].func_name == "AVG"
    assert ast.aggregates[2].column == "age"


def test_parse_select_group_by():
    """Test SELECT with GROUP BY."""
    query = "SELECT department, COUNT(*) FROM employees GROUP BY department"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert ast.table_name == "employees"
    assert ast.group_by is not None
    assert ast.group_by.columns == ["department"]
    assert len(ast.aggregates) == 1


def test_parse_select_group_by_multiple():
    """Test SELECT with GROUP BY multiple columns."""
    query = "SELECT dept, city, COUNT(*) FROM employees GROUP BY dept, city"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert ast.group_by.columns == ["dept", "city"]
    assert len(ast.aggregates) == 1


def test_parse_select_having():
    """Test SELECT with HAVING clause."""
    query = "SELECT department, COUNT(*) FROM employees GROUP BY department HAVING COUNT(*) > 5"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert ast.group_by is not None
    assert ast.group_by.having_clause is not None


def test_parse_inner_join():
    """Test parsing INNER JOIN."""
    query = "SELECT * FROM users INNER JOIN orders ON users.id = orders.user_id"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert len(ast.joins) == 1
    join = ast.joins[0]
    assert join.join_type == 'INNER'
    assert join.table_name == 'orders'
    assert join.on_condition is not None


def test_parse_left_join():
    """Test parsing LEFT JOIN."""
    query = "SELECT * FROM users LEFT JOIN orders ON users.id = orders.user_id"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert len(ast.joins) == 1
    join = ast.joins[0]
    assert join.join_type == 'LEFT'
    assert join.table_name == 'orders'


def test_parse_right_join():
    """Test parsing RIGHT JOIN."""
    query = "SELECT * FROM users RIGHT JOIN orders ON users.id = orders.user_id"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert len(ast.joins) == 1
    join = ast.joins[0]
    assert join.join_type == 'RIGHT'
    assert join.table_name == 'orders'


def test_parse_full_join():
    """Test parsing FULL JOIN."""
    query = "SELECT * FROM users FULL JOIN orders ON users.id = orders.user_id"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert len(ast.joins) == 1
    join = ast.joins[0]
    assert join.join_type == 'FULL'
    assert join.table_name == 'orders'


def test_parse_cross_join():
    """Test parsing CROSS JOIN."""
    query = "SELECT * FROM users CROSS JOIN orders"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert len(ast.joins) == 1
    join = ast.joins[0]
    assert join.join_type == 'CROSS'
    assert join.table_name == 'orders'
    assert join.on_condition is None


def test_parse_join_with_alias():
    """Test parsing JOIN with table alias."""
    query = "SELECT * FROM users u INNER JOIN orders o ON u.id = o.user_id"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert ast.alias == 'u'
    assert len(ast.joins) == 1
    join = ast.joins[0]
    assert join.join_type == 'INNER'
    assert join.table_name == 'orders'
    assert join.alias == 'o'


def test_parse_multiple_joins():
    """Test parsing multiple JOINs."""
    query = "SELECT * FROM users u INNER JOIN orders o ON u.id = o.user_id LEFT JOIN products p ON o.product_id = p.id"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert len(ast.joins) == 2
    
    join1 = ast.joins[0]
    assert join1.join_type == 'INNER'
    assert join1.table_name == 'orders'
    assert join1.alias == 'o'
    
    join2 = ast.joins[1]
    assert join2.join_type == 'LEFT'
    assert join2.table_name == 'products'
    assert join2.alias == 'p'


def test_parse_join_with_outer():
    """Test parsing JOIN with OUTER keyword."""
    query = "SELECT * FROM users LEFT OUTER JOIN orders ON users.id = orders.user_id"
    ast = parse_query(query)
    
    assert isinstance(ast, SelectNode)
    assert len(ast.joins) == 1
    join = ast.joins[0]
    assert join.join_type == 'LEFT'
    assert join.table_name == 'orders'