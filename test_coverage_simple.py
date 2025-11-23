"""
Simplified Coverage Test Suite for AlpacaDB
Tests core functionality with proper API usage
"""
import pytest
import os
import sys
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.storage.table_manager import TableManager
from src.storage.catalog import Catalog
from src.storage.page_manager import PageManager
from src.storage.indexing.index_manager import IndexManager
from src.storage.indexing.btree import BTree
from src.query.lexer import Lexer
from src.query.parser import Parser
from src.query.tokens import TokenType
from src.executor.executor import QueryExecutor
from src.optimizer.optimizer import QueryOptimizer
from src.optimizer import cost_estimator


class TestBasicStorage:
    """Test basic storage operations"""
    
    def setup_method(self):
        self.test_db = "test_simple_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
    
    def teardown_method(self):
        try:
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_create_table_via_catalog(self):
        """Test table creation through catalog"""
        from src.query.ast_nodes import Column
        
        schema = {
            'id': Column('id', 'INT', primary_key=True),
            'name': Column('name', 'STRING'),
            'age': Column('age', 'INT')
        }
        
        self.catalog.create_table('users', schema)
        assert self.catalog.table_exists('users')
        
        table_info = self.catalog.get_table('users')
        assert table_info is not None
        assert table_info.name == 'users'
    
    def test_insert_and_scan(self):
        """Test basic insert and scan"""
        from src.query.ast_nodes import Column
        
        # Create table
        schema = {
            'id': Column('id', 'INT'),
            'data': Column('data', 'STRING')
        }
        self.catalog.create_table('test', schema)
        
        # Insert rows
        for i in range(5):
            values = [i, f"data_{i}"]
            self.table_manager.insert_row('test', values)
        
        # Scan rows
        rows = list(self.table_manager.scan_table('test'))
        assert len(rows) >= 5


class TestBTree:
    """Test BTree operations"""
    
    def test_btree_insert_search(self):
        """Test BTree insert and search"""
        btree = BTree()
        
        # Insert values
        for i in range(10):
            btree.insert(i, f"value_{i}")
        
        # Search
        result = btree.search(5)
        assert result == "value_5"
        
        # Search non-existent
        result = btree.search(100)
        assert result is None
    
    def test_btree_range_scan(self):
        """Test BTree range scanning"""
        btree = BTree()
        
        for i in range(20):
            btree.insert(i * 2, f"value_{i*2}")
        
        results = btree.range_scan(10, 20)
        assert len(results) > 0


class TestLexerParser:
    """Test query lexing and parsing"""
    
    def test_lexer_basic(self):
        """Test basic lexer functionality"""
        query = "SELECT * FROM users"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        
        assert len(tokens) > 0
        assert tokens[0].type == TokenType.SELECT
        assert tokens[1].type == TokenType.STAR
        assert tokens[2].type == TokenType.FROM
    
    def test_parser_select(self):
        """Test parsing SELECT statement"""
        query = "SELECT * FROM users"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert ast is not None
        assert ast.table_name == 'users'
    
    def test_parser_select_with_where(self):
        """Test SELECT with WHERE clause"""
        query = "SELECT * FROM users WHERE age > 25"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert ast is not None
        assert ast.where is not None
    
    def test_parser_create_table(self):
        """Test CREATE TABLE parsing"""
        query = "CREATE TABLE students (id INT, name STRING, age INT)"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert ast is not None
        assert ast.table_name == 'students'
        assert len(ast.columns) == 3
    
    def test_parser_update(self):
        """Test UPDATE parsing"""
        query = "UPDATE users SET age = 30 WHERE id = 1"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert ast is not None
        assert ast.table_name == 'users'
    
    def test_parser_delete(self):
        """Test DELETE parsing"""
        query = "DELETE FROM users WHERE age < 18"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert ast is not None
        assert ast.table_name == 'users'


class TestExecutorBasic:
    """Test query executor"""
    
    def setup_method(self):
        self.test_db = "test_exec_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
        self.index_manager = IndexManager(self.catalog, self.page_manager)
        self.executor = QueryExecutor(self.table_manager, self.catalog, self.index_manager)
    
    def teardown_method(self):
        try:
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_executor_create_table(self):
        """Test executing CREATE TABLE"""
        query = "CREATE TABLE products (id INT, name STRING, price INT)"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        result = self.executor.execute(ast)
        assert self.catalog.table_exists('products')
    
    def test_executor_workflow(self):
        """Test complete CRUD workflow"""
        # Create table
        create_sql = "CREATE TABLE items (id INT, value INT)"
        ast = Parser(Lexer(create_sql).tokenize()).parse()
        self.executor.execute(ast)
        
        # Insert data
        insert_sql = "INSERT INTO items VALUES (1, 100)"
        ast = Parser(Lexer(insert_sql).tokenize()).parse()
        result = self.executor.execute(ast)
        
        # Select data
        select_sql = "SELECT * FROM items"
        ast = Parser(Lexer(select_sql).tokenize()).parse()
        result = self.executor.execute(ast)
        assert result is not None


class TestOptimizer:
    """Test query optimizer"""
    
    def setup_method(self):
        self.test_db = "test_opt_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
        self.index_manager = IndexManager(self.catalog, self.page_manager)
    
    def teardown_method(self):
        try:
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_cost_estimator(self):
        """Test cost estimation functions"""
        from src.query.ast_nodes import Column
        
        # Create a table
        schema = {
            'id': Column('id', 'INT'),
            'data': Column('data', 'STRING')
        }
        self.catalog.create_table('test_table', schema)
        
        # Insert some data
        for i in range(10):
            self.table_manager.insert_row('test_table', [i, f"data_{i}"])
        
        # Get table stats
        table_stats = self.catalog.get_table_stats('test_table')
        
        # Estimate sequential scan cost
        cost = cost_estimator.cost_seq_scan(table_stats)
        assert cost > 0
    
    def test_optimizer_creation(self):
        """Test optimizer can be created"""
        optimizer = QueryOptimizer(self.catalog, self.index_manager, self.table_manager)
        assert optimizer is not None


class TestIndexing:
    """Test indexing functionality"""
    
    def setup_method(self):
        self.test_db = "test_index_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
        self.index_manager = IndexManager(self.catalog, self.page_manager)
    
    def teardown_method(self):
        try:
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_create_index(self):
        """Test index creation"""
        from src.query.ast_nodes import Column
        
        # Create table first
        schema = {
            'id': Column('id', 'INT'),
            'name': Column('name', 'STRING')
        }
        self.catalog.create_table('indexed_table', schema)
        
        # Create index
        self.index_manager.create_index('idx_id', 'indexed_table', 'id', self.table_manager)
        
        # Verify index exists
        assert self.catalog.index_exists('indexed_table', 'idx_id')


class TestErrorHandling:
    """Test error handling"""
    
    def setup_method(self):
        self.test_db = "test_err_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
    
    def teardown_method(self):
        try:
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_table_not_found(self):
        """Test accessing non-existent table"""
        with pytest.raises(Exception):
            list(self.table_manager.scan_table('nonexistent'))
    
    def test_invalid_query_syntax(self):
        """Test invalid query syntax"""
        query = "SELECTFROM users"  # Invalid syntax
        
        with pytest.raises(Exception):
            lexer = Lexer(query)
            tokens = lexer.tokenize()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src", "--cov-report=html", "--cov-report=term"])
