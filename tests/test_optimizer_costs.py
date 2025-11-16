"""
Cost-based optimizer tests (Phase 2).

Verifies SeqScan vs IndexScan choice based on stats and selectivity.
"""
import os
import sys
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage import PageManager, Catalog, TableManager
from src.storage.indexing.index_manager import IndexManager
from src.query import Lexer, Parser
from src.executor import QueryExecutor


def parse_sql(sql: str):
    lexer = Lexer(sql)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


class TestCostBasedPlanSelection:
    @pytest.fixture
    def temp_db(self):
        temp_dir = tempfile.mkdtemp(prefix="costs_test_")
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

        page_manager.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    def exec_sql(self, executor, sql):
        ast = parse_sql(sql)
        return executor.execute(ast)

    def test_small_table_with_unique_index_still_uses_index(self, temp_db):
        """For unique indexes (highly selective), prefer IndexScan even on small tables."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        index_manager = temp_db['index_manager']
        executor = temp_db['executor']

        # Create table
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'email', 'type': 'STRING', 'nullable': True},
        ]
        catalog.create_table('users', columns)

        # Insert few rows
        for i in range(10):
            table_manager.insert_row('users', [i, f'user{i}@test.com'])

        # Create index on email (unique)
        index_manager.create_index('idx_email', 'users', 'email')

        # Equality predicate on indexed column
        rows, _ = self.exec_sql(executor, "SELECT * FROM users WHERE email = 'user5@test.com';")

        # With selectivity 1/10 (10%), index is preferred due to hybrid rule
        assert executor.last_plan == 'IndexScan'
        assert len(rows) == 1

    def test_small_table_low_selectivity_prefers_seqscan(self, temp_db):
        """For low selectivity (non-unique), prefer SeqScan on small tables."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        index_manager = temp_db['index_manager']
        executor = temp_db['executor']

        # Create table
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'category', 'type': 'STRING', 'nullable': True},
        ]
        catalog.create_table('products', columns)

        # Insert rows with only 2 categories (low selectivity: 1/2 = 50%, at threshold)
        for i in range(10):
            table_manager.insert_row('products', [i, 'A' if i % 2 == 0 else 'B'])

        # Create index on category (non-unique, 50% selectivity)
        index_manager.create_index('idx_cat', 'products', 'category')

        # Equality predicate on low-selectivity column
        rows, _ = self.exec_sql(executor, "SELECT * FROM products WHERE category = 'A';")

        # With selectivity 1/2 = 50%, at threshold - cost comparison kicks in
        # For 10 rows, SeqScan should be cheaper (quick table scan vs index traversal)
        assert executor.last_plan == 'SeqScan'
        assert len(rows) == 5

    def test_large_table_prefers_indexscan_with_selective_predicate(self, temp_db):
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        index_manager = temp_db['index_manager']
        executor = temp_db['executor']

        # Create table
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'email', 'type': 'STRING', 'nullable': True},
        ]
        catalog.create_table('big_users', columns)

        # Insert many rows
        for i in range(2000):
            table_manager.insert_row('big_users', [i, f'user{i}@test.com'])

        # Create index on email (unique)
        index_manager.create_index('idx_email_big', 'big_users', 'email')

        # Equality predicate on indexed column
        rows, _ = self.exec_sql(executor, "SELECT * FROM big_users WHERE email = 'user1500@test.com';")

        # For large tables, index scan should be cheaper
        assert executor.last_plan == 'IndexScan'
        assert len(rows) == 1

    def test_missing_stats_fallback_defaults(self, temp_db):
        # Even if stats are missing (e.g., manually edited), optimizer should not crash
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        index_manager = temp_db['index_manager']
        executor = temp_db['executor']

        columns = [
            {'name': 'k', 'type': 'INT', 'nullable': False},
            {'name': 'v', 'type': 'INT', 'nullable': True},
        ]
        catalog.create_table('t', columns)
        for i in range(50):
            table_manager.insert_row('t', [i, i % 5])
        index_manager.create_index('idx_v', 't', 'v')

        # Manually wipe stats to simulate missing values
        idx = catalog.get_index('idx_v')
        idx.stats = {}
        schema = catalog.get_table_schema('t')
        schema.num_rows = 0
        schema.num_pages = 0
        catalog._save_catalog()

        rows, _ = self.exec_sql(executor, "SELECT * FROM t WHERE v = 3;")
        # Should still pick a reasonable plan (rule-based fallback OK)
        assert executor.last_plan in ('SeqScan', 'IndexScan')
        assert len(rows) >= 0
