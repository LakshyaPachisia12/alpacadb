import pytest
import tempfile
import os
from src.storage.page_manager import PageManager
from src.storage.catalog import Catalog
from src.storage.table_manager import TableManager
from src.storage.indexing.index_manager import IndexManager
from src.query.lexer import Lexer
from src.query.parser import Parser
from src.executor import QueryExecutor
from src.optimizer.cost_estimator import cost_seq_scan, cost_index_scan


def parse(sql):
    lexer = Lexer(sql)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


class TestExecutorJoins:
    @pytest.fixture
    def db(self):
        temp_dir = tempfile.mkdtemp(prefix="ex_joindb_")
        db_path = os.path.join(temp_dir, "test.db")
        page_manager = PageManager(db_path)
        catalog = Catalog(page_manager)
        table_manager = TableManager(page_manager, catalog)
        index_manager = IndexManager(catalog, page_manager)
        table_manager.index_manager = index_manager
        executor = QueryExecutor(table_manager, catalog, index_manager)
        yield executor
        page_manager.close()

    def test_last_plan_set_for_joins(self, db):
        execute = lambda q: db.execute(parse(q))
        execute("CREATE TABLE a (id INT, v INT);")
        execute("CREATE TABLE b (id INT, v INT);")
        execute("INSERT INTO a VALUES (1, 10);")
        execute("INSERT INTO b VALUES (1, 10);")
        rows, cols = execute("SELECT * FROM a INNER JOIN b ON a.v = b.v;")
        assert db.last_plan == 'Join'


class TestCostEstimatorDirect:
    def test_cost_seq_scan_basic(self):
        cost = cost_seq_scan({'num_pages': 5, 'num_rows': 100})
        assert cost > 0

    def test_cost_index_scan_large_distinct(self):
        table_stats = {'num_pages': 1000, 'num_rows': 100000}
        index_stats = {'num_distinct': 100000}
        cost = cost_index_scan(table_stats, index_stats, 'eq')
        assert cost > 0

    def test_cost_index_scan_low_selectivity_penalty(self):
        table_stats = {'num_pages': 50, 'num_rows': 100}
        index_stats = {'num_distinct': 2}
        cost_idx = cost_index_scan(table_stats, index_stats, 'eq')
        cost_seq = cost_seq_scan(table_stats)
        # With selectivity of 50%, index scan should be significantly more expensive than seq scan
        assert cost_idx > cost_seq, f"Index cost {cost_idx} should be > seq cost {cost_seq} for 50% selectivity"


def test_index_build_sets_stats(tmp_path):
    db_file = tmp_path / "dbfile.db"
    page_manager = PageManager(str(db_file))
    catalog = Catalog(page_manager)
    table_manager = TableManager(page_manager, catalog)
    index_manager = IndexManager(catalog, page_manager)
    table_manager.index_manager = index_manager

    columns = [
        {'name': 'id', 'type': 'INT', 'nullable': False},
        {'name': 'category', 'type': 'STRING', 'nullable': True}
    ]
    catalog.create_table('products', columns)

    # Insert rows with two categories A/B
    for i in range(10):
        table_manager.insert_row('products', [i, 'A' if i % 2 == 0 else 'B'])

    index_manager.create_index('idx_cat', 'products', 'category', table_manager)

    idx = catalog.get_index('idx_cat')
    assert idx is not None
    assert idx.stats.get('num_distinct', None) == 2
    page_manager.close()
