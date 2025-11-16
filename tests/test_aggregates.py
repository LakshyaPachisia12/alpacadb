#!/usr/bin/env python3
"""
Unit tests for aggregate functions and GROUP BY functionality.

Tests parser-level and executor-level aggregate operations.
"""

import pytest
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.query import Lexer, Parser
from src.storage import PageManager, Catalog, TableManager
from src.storage.indexing.index_manager import IndexManager
from src.executor import QueryExecutor


class TestAggregateParsing:
    """Test aggregate function parsing."""
    
    def test_count_parsing(self):
        """Test basic COUNT parsing."""
        lexer = Lexer('SELECT COUNT(*) FROM users')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert len(ast.aggregates) == 1
        assert ast.aggregates[0].func_name == 'COUNT'
        assert ast.aggregates[0].column is None  # COUNT(*)
    
    def test_group_by_parsing(self):
        """Test GROUP BY parsing."""
        lexer = Lexer('SELECT COUNT(*) FROM users GROUP BY department')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert ast.group_by is not None
        assert 'department' in ast.group_by.columns
    
    def test_multiple_aggregates_parsing(self):
        """Test parsing multiple aggregates."""
        lexer = Lexer('SELECT COUNT(*), SUM(salary), AVG(age) FROM employees')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert len(ast.aggregates) == 3
        assert ast.aggregates[0].func_name == 'COUNT'
        assert ast.aggregates[1].func_name == 'SUM'
        assert ast.aggregates[2].func_name == 'AVG'


class TestAggregateExecution:
    """Test aggregate function execution end-to-end."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        temp_dir = tempfile.mkdtemp(prefix="aggregate_test_")
        db_path = os.path.join(temp_dir, "test.db")
        
        page_manager = PageManager(db_path)
        catalog = Catalog(page_manager)
        index_manager = IndexManager(catalog, page_manager)
        table_manager = TableManager(page_manager, catalog, index_manager)
        executor = QueryExecutor(table_manager, catalog)
        
        # Create test table
        catalog.create_table('employees', [
            {'name': 'id', 'type': 'INT'},
            {'name': 'department', 'type': 'STRING'},
            {'name': 'salary', 'type': 'INT'}
        ])
        
        # Insert test data
        table_manager.insert_row('employees', [1, 'Engineering', 75000])
        table_manager.insert_row('employees', [2, 'Engineering', 82000])
        table_manager.insert_row('employees', [3, 'Sales', 55000])
        table_manager.insert_row('employees', [4, 'Sales', 62000])
        table_manager.insert_row('employees', [5, 'HR', 50000])
        
        yield {
            'executor': executor,
            'catalog': catalog,
            'table_manager': table_manager,
            'page_manager': page_manager
        }
        
        # Cleanup
        page_manager.close()
        shutil.rmtree(temp_dir)
    
    def test_count_star_execution(self, temp_db):
        """Test COUNT(*) returns correct count."""
        executor = temp_db['executor']
        
        lexer = Lexer('SELECT COUNT(*) FROM employees')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        results, columns = executor.execute(ast)
        
        assert len(results) == 1
        assert results[0][0] == 5  # 5 employees
    
    def test_sum_execution(self, temp_db):
        """Test SUM aggregation."""
        executor = temp_db['executor']
        
        lexer = Lexer('SELECT SUM(salary) FROM employees')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        results, columns = executor.execute(ast)
        
        assert len(results) == 1
        assert results[0][0] == 324000  # Total salary
    
    def test_avg_execution(self, temp_db):
        """Test AVG aggregation."""
        executor = temp_db['executor']
        
        lexer = Lexer('SELECT AVG(salary) FROM employees')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        results, columns = executor.execute(ast)
        
        assert len(results) == 1
        assert results[0][0] == 64800  # Average salary
    
    def test_group_by_execution(self, temp_db):
        """Test GROUP BY with COUNT."""
        executor = temp_db['executor']
        
        lexer = Lexer('SELECT department, COUNT(*) FROM employees GROUP BY department')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        results, columns = executor.execute(ast)
        
        assert len(results) == 3  # 3 departments
        # Convert to dict for easier assertion
        dept_counts = {row[0]: row[1] for row in results}
        assert dept_counts['Engineering'] == 2
        assert dept_counts['Sales'] == 2
        assert dept_counts['HR'] == 1
    
    def test_group_by_with_multiple_aggregates(self, temp_db):
        """Test GROUP BY with multiple aggregates."""
        executor = temp_db['executor']
        
        lexer = Lexer('SELECT department, COUNT(*), AVG(salary) FROM employees GROUP BY department')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        results, columns = executor.execute(ast)
        
        assert len(results) == 3
        assert columns == ['department', 'COUNT(*)', 'AVG(salary)']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])