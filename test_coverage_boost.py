"""
HIGH COVERAGE BOOSTER TESTS - Target 80%+
==========================================
Focused tests to boost coverage on low-coverage modules.
"""
import pytest
import tempfile
import shutil
from pathlib import Path

from src.storage.page_manager import PageManager
from src.storage.catalog import Catalog
from src.storage.table_manager import TableManager
from src.storage.indexing.index_manager import IndexManager
from src.executor.executor import QueryExecutor
from src.optimizer.optimizer import QueryOptimizer
from src.optimizer import cost_estimator
from src.query.lexer import Lexer
from src.query.parser import Parser
from src.errors import *


@pytest.fixture
def temp_db():
    """Create temporary database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    
    pm = PageManager(str(db_path))
    cat = Catalog(pm)
    tm = TableManager(pm, cat)
    im = IndexManager(cat, pm)
    ex = QueryExecutor(tm, cat, im)
    opt = QueryOptimizer(cat, im)
    
    yield {'pm': pm, 'cat': cat, 'tm': tm, 'im': im, 'ex': ex, 'opt': opt}
    
    pm.close()
    shutil.rmtree(temp_dir)


def sql(executor, query):
    """Execute SQL helper."""
    lex = Lexer(query)
    par = Parser(lex.tokenize())
    ast = par.parse()
    return executor.execute(ast)


# =============================================================================
# COST ESTIMATOR TESTS (25.64% → 80%+)
# =============================================================================

def test_cost_seq_scan(temp_db):
    stats = {'row_count': 1000, 'page_count': 10, 'avg_row_size': 100}
    cost = cost_estimator.cost_seq_scan(stats)
    assert cost > 0


def test_cost_seq_scan_selectivity(temp_db):
    stats = {'row_count': 10000, 'page_count': 100, 'avg_row_size': 50}
    cost1 = cost_estimator.cost_seq_scan(stats, selectivity=0.01)
    cost2 = cost_estimator.cost_seq_scan(stats, selectivity=0.99)
    assert cost1 > 0 and cost2 > 0


def test_cost_index_scan(temp_db):
    tstats = {'row_count': 1000, 'page_count': 10}
    istats = {'height': 3, 'leaf_pages': 5, 'total_entries': 1000}
    cost = cost_estimator.cost_index_scan(tstats, istats, 'equality')
    assert cost > 0


def test_cost_sort(temp_db):
    cost = cost_estimator.cost_sort(1000)
    assert cost > 0


def test_cost_sort_scaling(temp_db):
    small = cost_estimator.cost_sort(100)
    large = cost_estimator.cost_sort(10000)
    assert large > small


# =============================================================================
# TABLE MANAGER TESTS (63.27% → 80%+)
# =============================================================================

def test_insert_batch_rows(temp_db):
    cat, tm = temp_db['cat'], temp_db['tm']
    cat.create_table('batch', [{'name': 'id', 'type': 'INT', 'nullable': False}])
    
    for i in range(50):
        tm.insert_row('batch', [i])
    
    rows = list(tm.scan_table('batch'))
    assert len(rows) == 50


def test_update_rows(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('upd', [
        {'name': 'id', 'type': 'INT', 'nullable': False},
        {'name': 'val', 'type': 'STRING', 'nullable': True}
    ])
    
    tm.insert_row('upd', [1, 'old'])
    sql(ex, "UPDATE upd SET val = 'new' WHERE id = 1")
    
    rows = list(tm.scan_table('upd'))
    assert rows[0][1] == 'new'


def test_delete_rows(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('del', [{'name': 'id', 'type': 'INT', 'nullable': False}])
    
    for i in range(5):
        tm.insert_row('del', [i])
    
    sql(ex, "DELETE FROM del WHERE id > 2")
    rows = list(tm.scan_table('del'))
    assert len(rows) == 3


def test_scan_empty_table(temp_db):
    cat, tm = temp_db['cat'], temp_db['tm']
    cat.create_table('empty', [{'name': 'id', 'type': 'INT', 'nullable': False}])
    rows = list(tm.scan_table('empty'))
    assert len(rows) == 0


def test_scan_large_table(temp_db):
    cat, tm = temp_db['cat'], temp_db['tm']
    cat.create_table('large', [
        {'name': 'id', 'type': 'INT', 'nullable': False},
        {'name': 'data', 'type': 'STRING', 'nullable': True}
    ])
    
    for i in range(100):
        tm.insert_row('large', [i, f'data{i}'])
    
    rows = list(tm.scan_table('large'))
    assert len(rows) == 100


# =============================================================================
# SQL EXECUTION TESTS (operators + executor)
# =============================================================================

def test_complex_where(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('where_test', [
        {'name': 'age', 'type': 'INT', 'nullable': False},
        {'name': 'score', 'type': 'INT', 'nullable': False}
    ])
    
    for age, score in [(25, 80), (30, 90), (35, 70), (40, 95)]:
        tm.insert_row('where_test', [age, score])
    
    results = sql(ex, "SELECT * FROM where_test WHERE age >= 30 AND score >= 90")
    assert len(results) == 2


def test_projection(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('proj', [
        {'name': 'id', 'type': 'INT', 'nullable': False},
        {'name': 'name', 'type': 'STRING', 'nullable': True}
    ])
    
    tm.insert_row('proj', [1, 'Alice'])
    tm.insert_row('proj', [2, 'Bob'])
    
    results = sql(ex, "SELECT name FROM proj")
    assert len(results) == 2
    assert results[0] == ['Alice']


def test_order_by_asc(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('sort', [{'name': 'val', 'type': 'INT', 'nullable': False}])
    
    for val in [3, 1, 4, 1, 5]:
        tm.insert_row('sort', [val])
    
    results = sql(ex, "SELECT * FROM sort ORDER BY val")
    vals = [r[0] for r in results]
    assert vals == sorted(vals)


def test_order_by_desc(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('sortd', [{'name': 'val', 'type': 'INT', 'nullable': False}])
    
    for val in [5, 2, 8, 1]:
        tm.insert_row('sortd', [val])
    
    results = sql(ex, "SELECT * FROM sortd ORDER BY val DESC")
    vals = [r[0] for r in results]
    assert vals == sorted(vals, reverse=True)


def test_limit(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('lim', [{'name': 'id', 'type': 'INT', 'nullable': False}])
    
    for i in range(10):
        tm.insert_row('lim', [i])
    
    results = sql(ex, "SELECT * FROM lim LIMIT 3")
    assert len(results) == 3


def test_count_agg(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('cnt', [{'name': 'val', 'type': 'INT', 'nullable': False}])
    
    for i in range(5):
        tm.insert_row('cnt', [i])
    
    results = sql(ex, "SELECT COUNT(*) FROM cnt")
    assert results[0][0] == 5


def test_sum_agg(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('sum', [{'name': 'amt', 'type': 'INT', 'nullable': False}])
    
    for val in [10, 20, 30]:
        tm.insert_row('sum', [val])
    
    results = sql(ex, "SELECT SUM(amt) FROM sum")
    assert results[0][0] == 60


def test_avg_agg(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('avg', [{'name': 'score', 'type': 'INT', 'nullable': False}])
    
    for val in [80, 90, 100]:
        tm.insert_row('avg', [val])
    
    results = sql(ex, "SELECT AVG(score) FROM avg")
    assert results[0][0] == 90


def test_min_max(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('mm', [{'name': 'val', 'type': 'INT', 'nullable': False}])
    
    for val in [5, 15, 3, 42]:
        tm.insert_row('mm', [val])
    
    results = sql(ex, "SELECT MIN(val), MAX(val) FROM mm")
    assert results[0][0] == 3
    assert results[0][1] == 42


def test_group_by(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('grp', [
        {'name': 'dept', 'type': 'STRING', 'nullable': True},
        {'name': 'sal', 'type': 'INT', 'nullable': False}
    ])
    
    tm.insert_row('grp', ['Sales', 50000])
    tm.insert_row('grp', ['Sales', 60000])
    tm.insert_row('grp', ['Eng', 80000])
    
    results = sql(ex, "SELECT dept, COUNT(*) FROM grp GROUP BY dept")
    assert len(results) == 2


# =============================================================================
# ERROR HANDLING TESTS (64% → 80%+)
# =============================================================================

def test_table_not_found(temp_db):
    ex = temp_db['ex']
    with pytest.raises(TableNotFoundError):
        sql(ex, "SELECT * FROM nonexistent")


def test_column_not_found(temp_db):
    cat, ex = temp_db['cat'], temp_db['ex']
    cat.create_table('colfail', [{'name': 'id', 'type': 'INT', 'nullable': False}])
    with pytest.raises(ColumnNotFoundError):
        sql(ex, "SELECT badcol FROM colfail")


def test_syntax_error(temp_db):
    with pytest.raises(SyntaxError):
        lex = Lexer("INVALID * FROM t")
        par = Parser(lex.tokenize())
        par.parse()


def test_duplicate_table(temp_db):
    cat = temp_db['cat']
    cols = [{'name': 'id', 'type': 'INT', 'nullable': False}]
    cat.create_table('dup', cols)
    with pytest.raises(DuplicateTableError):
        cat.create_table('dup', cols)


def test_duplicate_index(temp_db):
    cat, im = temp_db['cat'], temp_db['im']
    cat.create_table('idxdup', [{'name': 'id', 'type': 'INT', 'nullable': False}])
    im.create_index('idxdup', 'id', 'idx1')
    with pytest.raises(DuplicateIndexError):
        im.create_index('idxdup', 'id', 'idx1')


def test_index_not_found(temp_db):
    im = temp_db['im']
    with pytest.raises(IndexNotFoundError):
        im.drop_index('nonexistent_idx')


# =============================================================================
# INDEX MANAGER TESTS (73.11% → 80%+)
# =============================================================================

def test_create_index_string_col(temp_db):
    cat, im = temp_db['cat'], temp_db['im']
    cat.create_table('stridx', [
        {'name': 'id', 'type': 'INT', 'nullable': False},
        {'name': 'name', 'type': 'STRING', 'nullable': True}
    ])
    
    im.create_index('stridx', 'name', 'idx_name')
    idxs = cat.get_indexes('stridx')
    assert len(idxs) > 0


def test_index_usage(temp_db):
    cat, tm, im, ex = temp_db['cat'], temp_db['tm'], temp_db['im'], temp_db['ex']
    cat.create_table('idxuse', [
        {'name': 'id', 'type': 'INT', 'nullable': False},
        {'name': 'val', 'type': 'INT', 'nullable': True}
    ])
    
    for i in range(50):
        tm.insert_row('idxuse', [i, i * 10])
    
    im.create_index('idxuse', 'id', 'idx_id')
    
    results = sql(ex, "SELECT * FROM idxuse WHERE id = 25")
    assert len(results) == 1
    assert results[0][0] == 25


def test_drop_index_fallback(temp_db):
    cat, tm, im, ex = temp_db['cat'], temp_db['tm'], temp_db['im'], temp_db['ex']
    cat.create_table('dropidx', [{'name': 'id', 'type': 'INT', 'nullable': False}])
    
    tm.insert_row('dropidx', [1])
    im.create_index('dropidx', 'id', 'idx_tmp')
    im.drop_index('idx_tmp')
    
    results = sql(ex, "SELECT * FROM dropidx WHERE id = 1")
    assert len(results) == 1


def test_multiple_indexes(temp_db):
    cat, im = temp_db['cat'], temp_db['im']
    cat.create_table('multiidx', [
        {'name': 'id', 'type': 'INT', 'nullable': False},
        {'name': 'age', 'type': 'INT', 'nullable': True},
        {'name': 'score', 'type': 'INT', 'nullable': True}
    ])
    
    im.create_index('multiidx', 'id', 'idx_id')
    im.create_index('multiidx', 'age', 'idx_age')
    im.create_index('multiidx', 'score', 'idx_score')
    
    idxs = cat.get_indexes('multiidx')
    assert len(idxs) == 3


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

def test_complete_crud(temp_db):
    ex = temp_db['ex']
    
    sql(ex, "CREATE TABLE prod (id INT, name STRING, price INT)")
    sql(ex, "INSERT INTO prod VALUES (1, 'Laptop', 1000)")
    sql(ex, "INSERT INTO prod VALUES (2, 'Mouse', 25)")
    
    results = sql(ex, "SELECT * FROM prod")
    assert len(results) == 2
    
    sql(ex, "UPDATE prod SET price = 950 WHERE id = 1")
    results = sql(ex, "SELECT price FROM prod WHERE id = 1")
    assert results[0][0] == 950
    
    sql(ex, "DELETE FROM prod WHERE id = 2")
    results = sql(ex, "SELECT * FROM prod")
    assert len(results) == 1


def test_complex_agg_sort(temp_db):
    cat, tm, ex = temp_db['cat'], temp_db['tm'], temp_db['ex']
    cat.create_table('sal', [
        {'name': 'dept', 'type': 'STRING', 'nullable': True},
        {'name': 'salary', 'type': 'INT', 'nullable': False}
    ])
    
    for dept, sal in [('Eng', 100000), ('Eng', 110000), ('Sales', 80000)]:
        tm.insert_row('sal', [dept, sal])
    
    results = sql(ex, "SELECT dept, AVG(salary) FROM sal GROUP BY dept ORDER BY dept")
    assert len(results) == 2


def test_index_large_dataset(temp_db):
    cat, tm, im, ex = temp_db['cat'], temp_db['tm'], temp_db['im'], temp_db['ex']
    cat.create_table('big', [
        {'name': 'id', 'type': 'INT', 'nullable': False},
        {'name': 'data', 'type': 'STRING', 'nullable': True}
    ])
    
    for i in range(200):
        tm.insert_row('big', [i, f'data{i}'])
    
    im.create_index('big', 'id', 'idx_big_id')
    
    results = sql(ex, "SELECT * FROM big WHERE id = 150")
    assert len(results) == 1
    assert results[0][0] == 150


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=src', '--cov-report=html', '--cov-report=term'])
