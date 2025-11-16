#!/usr/bin/env python3
"""
Phase 2 Demo: Cost-Based Query Optimization with Statistics

This demo shows:
1. Table statistics tracking (num_rows, num_pages)
2. Index statistics (num_distinct, null_count, min/max values)
3. Cost-based plan selection (SeqScan vs IndexScan)
4. Hybrid optimization (selectivity-based decisions)
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.storage import PageManager, Catalog, TableManager
from src.storage.indexing.index_manager import IndexManager
from src.query import Lexer, Parser
from src.executor import QueryExecutor


def execute_sql(executor, sql):
    """Helper to execute SQL and return results."""
    lexer = Lexer(sql)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    return executor.execute(ast)


def main():
    print("=" * 70)
    print("PHASE 2 DEMO: Cost-Based Query Optimization")
    print("=" * 70)
    
    # Setup temporary database
    temp_dir = tempfile.mkdtemp(prefix="phase2_demo_")
    db_path = os.path.join(temp_dir, "demo.db")
    
    try:
        # Initialize database
        page_manager = PageManager(db_path)
        catalog = Catalog(page_manager)
        index_manager = IndexManager(catalog, page_manager)
        table_manager = TableManager(page_manager, catalog, index_manager)
        executor = QueryExecutor(table_manager, catalog, index_manager)
        
        print("\n1. CREATE TABLE employees")
        print("-" * 70)
        execute_sql(executor, """
            CREATE TABLE employees (
                id INT,
                name STRING,
                email STRING,
                department STRING,
                salary INT
            );
        """)
        
        print("\n2. INSERT sample data (20 rows)")
        print("-" * 70)
        
        departments = ['Engineering', 'Sales', 'HR', 'Marketing']
        for i in range(1, 21):
            dept = departments[i % 4]
            execute_sql(executor, f"""
                INSERT INTO employees VALUES (
                    {i},
                    'Employee{i}',
                    'emp{i}@company.com',
                    '{dept}',
                    {50000 + i * 1000}
                );
            """)
        
        print("✅ Inserted 20 employees across 4 departments")
        
        # Check table stats
        stats = catalog.get_table_stats('employees')
        print(f"\n📊 Table Statistics:")
        print(f"   - Rows: {stats['num_rows']}")
        print(f"   - Pages: {stats['num_pages']}")
        
        print("\n3. Query WITHOUT index (SeqScan)")
        print("-" * 70)
        rows, _ = execute_sql(executor, "SELECT * FROM employees WHERE email = 'emp10@company.com';")
        print(f"✅ Plan: {executor.last_plan}")
        print(f"✅ Found {len(rows)} row(s)")
        print(f"   Result: {rows[0] if rows else 'None'}")
        
        print("\n4. CREATE INDEX on email (unique, high selectivity)")
        print("-" * 70)
        execute_sql(executor, "CREATE INDEX idx_email ON employees(email);")
        
        # Check index stats
        idx_stats = catalog.get_index_stats('idx_email')
        print(f"\n📊 Index Statistics (idx_email):")
        print(f"   - Distinct values: {idx_stats.get('num_distinct')}")
        print(f"   - Null count: {idx_stats.get('null_count')}")
        print(f"   - Min value: {idx_stats.get('min_value')}")
        print(f"   - Max value: {idx_stats.get('max_value')}")
        print(f"   - Selectivity: {1.0 / idx_stats.get('num_distinct', 1):.2%}")
        
        print("\n5. Query WITH index (cost-based choice)")
        print("-" * 70)
        rows, _ = execute_sql(executor, "SELECT * FROM employees WHERE email = 'emp15@company.com';")
        print(f"✅ Plan: {executor.last_plan} (chose based on statistics)")
        print(f"✅ Found {len(rows)} row(s)")
        print(f"   Result: {rows[0] if rows else 'None'}")
        
        print("\n6. CREATE INDEX on department (low selectivity)")
        print("-" * 70)
        execute_sql(executor, "CREATE INDEX idx_dept ON employees(department);")
        
        dept_stats = catalog.get_index_stats('idx_dept')
        print(f"\n📊 Index Statistics (idx_dept):")
        print(f"   - Distinct values: {dept_stats.get('num_distinct')}")
        print(f"   - Selectivity: {1.0 / dept_stats.get('num_distinct', 1):.2%} (low selectivity)")
        
        print("\n7. Query on low-selectivity column")
        print("-" * 70)
        rows, _ = execute_sql(executor, "SELECT * FROM employees WHERE department = 'Engineering';")
        print(f"✅ Plan: {executor.last_plan}")
        print(f"✅ Found {len(rows)} row(s) in Engineering")
        print(f"   (With 4 departments, selectivity = 25%, optimizer chooses optimal plan)")
        
        print("\n8. Cost Model Comparison")
        print("-" * 70)
        from src.optimizer.cost_estimator import cost_seq_scan, cost_index_scan
        
        table_stats = catalog.get_table_stats('employees')
        email_stats = catalog.get_index_stats('idx_email')
        dept_stats = catalog.get_index_stats('idx_dept')
        
        seq_cost = cost_seq_scan(table_stats)
        idx_email_cost = cost_index_scan(table_stats, email_stats, 'eq')
        idx_dept_cost = cost_index_scan(table_stats, dept_stats, 'eq')
        
        print(f"\nFor 20 rows:")
        print(f"   SeqScan cost:              {seq_cost:.4f}")
        print(f"   IndexScan (email, 5%):     {idx_email_cost:.4f} {'← CHOSEN' if idx_email_cost < seq_cost else ''}")
        print(f"   IndexScan (dept, 25%):     {idx_dept_cost:.4f} {'← CHOSEN' if idx_dept_cost < seq_cost else ''}")
        
        print("\n" + "=" * 70)
        print("✅ PHASE 2 DEMO COMPLETE")
        print("=" * 70)
        print("\nKey Features Demonstrated:")
        print("  ✓ Automatic statistics tracking (rows, pages, distinct values)")
        print("  ✓ Cost-based optimizer with hybrid selectivity rules")
        print("  ✓ Intelligent plan selection (SeqScan vs IndexScan)")
        print("  ✓ Statistics-driven performance optimization")
        print()
        
        # Cleanup
        page_manager.close()
        
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    main()
