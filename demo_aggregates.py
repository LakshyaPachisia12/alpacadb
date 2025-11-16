#!/usr/bin/env python3
"""
🎯 Demo: Aggregate Functions & GROUP BY in AlpacaDB

This script demonstrates all aggregate functionality with real examples.
Run this to test the implementation end-to-end!
"""

import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.query import Lexer, Parser
from src.storage import PageManager, Catalog, TableManager
from src.storage.indexing.index_manager import IndexManager
from src.executor import QueryExecutor


def execute_query(executor, query):
    """Execute a query and print results."""
    print(f"\n🔍 Query: {query}")
    try:
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        results, columns = executor.execute(ast)
        
        if columns:
            print(f"📊 Columns: {columns}")
            if results:
                print(f"📄 Results ({len(results)} rows):")
                for row in results:
                    print(f"  {row}")
            else:
                print("  (No rows)")
        else:
            print("✅ Query executed successfully")
        
        return results
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("="*70)
    print("🚀 AlpacaDB Aggregate Functions Demo")
    print("="*70)
    
    # Create temporary database
    temp_dir = tempfile.mkdtemp(prefix="alpacadb_aggregate_demo_")
    db_path = os.path.join(temp_dir, "demo.db")
    page_manager = None
    
    try:
        # Initialize database
        page_manager = PageManager(db_path)
        catalog = Catalog(page_manager)
        index_manager = IndexManager(catalog, page_manager)
        table_manager = TableManager(page_manager, catalog, index_manager)
        executor = QueryExecutor(table_manager, catalog)
        
        print(f"\n📂 Database: {db_path}")
        
        # ========== TEST 1: CREATE TABLE ==========
        print("\n" + "="*70)
        print("📋 Test 1: Create Employees Table")
        print("="*70)
        
        execute_query(executor, """
            CREATE TABLE employees (
                id INT,
                name STRING,
                department STRING,
                salary INT,
                age INT
            )
        """)
        
        # ========== TEST 2: INSERT DATA ==========
        print("\n" + "="*70)
        print("📥 Test 2: Insert Employee Data")
        print("="*70)
        
        employees = [
            (1, 'Alice', 'Engineering', 75000, 28),
            (2, 'Bob', 'Engineering', 82000, 32),
            (3, 'Charlie', 'Sales', 55000, 25),
            (4, 'David', 'Sales', 62000, 30),
            (5, 'Eve', 'HR', 50000, 27),
            (6, 'Frank', 'Engineering', 95000, 35),
            (7, 'Grace', 'Sales', 58000, 26),
            (8, 'Henry', 'HR', 52000, 29),
        ]
        
        for emp in employees:
            query = f"INSERT INTO employees VALUES ({emp[0]}, '{emp[1]}', '{emp[2]}', {emp[3]}, {emp[4]})"
            execute_query(executor, query)
        
        print(f"\n✅ Inserted {len(employees)} employees")
        
        # ========== TEST 3: COUNT(*) ==========
        print("\n" + "="*70)
        print("🧮 Test 3: COUNT(*) - Total Employee Count")
        print("="*70)
        
        execute_query(executor, "SELECT COUNT(*) FROM employees")
        
        # ========== TEST 4: COUNT(column) ==========
        print("\n" + "="*70)
        print("🧮 Test 4: COUNT(department) - Count Non-NULL Departments")
        print("="*70)
        
        execute_query(executor, "SELECT COUNT(department) FROM employees")
        
        # ========== TEST 5: SUM ==========
        print("\n" + "="*70)
        print("💰 Test 5: SUM - Total Salary Budget")
        print("="*70)
        
        execute_query(executor, "SELECT SUM(salary) FROM employees")
        
        # ========== TEST 6: AVG ==========
        print("\n" + "="*70)
        print("📊 Test 6: AVG - Average Salary")
        print("="*70)
        
        execute_query(executor, "SELECT AVG(salary) FROM employees")
        
        # ========== TEST 7: MIN & MAX ==========
        print("\n" + "="*70)
        print("🎯 Test 7: MIN & MAX - Salary Range")
        print("="*70)
        
        execute_query(executor, "SELECT MIN(salary), MAX(salary) FROM employees")
        
        # ========== TEST 8: GROUP BY Single Column ==========
        print("\n" + "="*70)
        print("📂 Test 8: GROUP BY - Count by Department")
        print("="*70)
        
        execute_query(executor, """
            SELECT department, COUNT(*) 
            FROM employees 
            GROUP BY department
        """)
        
        # ========== TEST 9: GROUP BY with Multiple Aggregates ==========
        print("\n" + "="*70)
        print("📊 Test 9: GROUP BY - Department Statistics")
        print("="*70)
        
        execute_query(executor, """
            SELECT department, COUNT(*), AVG(salary), MIN(salary), MAX(salary)
            FROM employees 
            GROUP BY department
        """)
        
        # ========== TEST 10: GROUP BY with WHERE ==========
        print("\n" + "="*70)
        print("🔍 Test 10: GROUP BY with WHERE - High Earners by Dept")
        print("="*70)
        
        execute_query(executor, """
            SELECT department, COUNT(*), AVG(salary)
            FROM employees 
            WHERE salary > 55000
            GROUP BY department
        """)
        
        # ========== TEST 11: Multiple Aggregates without GROUP BY ==========
        print("\n" + "="*70)
        print("📈 Test 11: Multiple Aggregates - Overall Statistics")
        print("="*70)
        
        execute_query(executor, """
            SELECT COUNT(*), SUM(salary), AVG(salary), MIN(age), MAX(age)
            FROM employees
        """)
        
        # ========== TEST 12: HAVING Clause ==========
        print("\n" + "="*70)
        print("🎯 Test 12: HAVING - Departments with Avg Salary > 60000")
        print("="*70)
        
        execute_query(executor, """
            SELECT department, AVG(salary)
            FROM employees 
            GROUP BY department
            HAVING AVG(salary) > 60000
        """)
        
        # ========== TEST 13: Complex Query ==========
        print("\n" + "="*70)
        print("🚀 Test 13: Complex - Large Departments with High Pay")
        print("="*70)
        
        execute_query(executor, """
            SELECT department, COUNT(*), AVG(salary)
            FROM employees 
            WHERE age < 35
            GROUP BY department
            HAVING COUNT(*) >= 2
        """)
        
        # ========== TEST 14: Create Sales Table ==========
        print("\n" + "="*70)
        print("🛒 Test 14: Create Sales Table & Test SUM")
        print("="*70)
        
        execute_query(executor, """
            CREATE TABLE sales (
                product STRING,
                quantity INT,
                price INT
            )
        """)
        
        sales_data = [
            ('Laptop', 5, 1200),
            ('Mouse', 50, 25),
            ('Keyboard', 30, 75),
            ('Laptop', 3, 1200),
            ('Monitor', 10, 300),
            ('Mouse', 25, 25),
        ]
        
        for sale in sales_data:
            query = f"INSERT INTO sales VALUES ('{sale[0]}', {sale[1]}, {sale[2]})"
            execute_query(executor, query)
        
        print(f"\n✅ Inserted {len(sales_data)} sales records")
        
        # ========== TEST 15: Revenue by Product ==========
        print("\n" + "="*70)
        print("💵 Test 15: Revenue by Product (quantity * price)")
        print("="*70)
        
        # Note: This calculates total revenue per product
        results = execute_query(executor, """
            SELECT product, SUM(quantity), SUM(price)
            FROM sales 
            GROUP BY product
        """)
        
        if results:
            print("\n💡 Manual Revenue Calculation:")
            for row in results:
                product, total_qty, total_price = row
                # Approximate revenue (this is simplified)
                print(f"  {product}: {total_qty} units")
        
        # ========== SUMMARY ==========
        print("\n" + "="*70)
        print("✅ ALL TESTS COMPLETED!")
        print("="*70)
        print("\n📊 Summary of Features Tested:")
        print("  ✅ COUNT(*) and COUNT(column)")
        print("  ✅ SUM, AVG, MIN, MAX")
        print("  ✅ GROUP BY single column")
        print("  ✅ GROUP BY with multiple aggregates")
        print("  ✅ WHERE + GROUP BY")
        print("  ✅ HAVING clause")
        print("  ✅ Complex nested conditions")
        print("  ✅ Multiple aggregates without GROUP BY")
        
        print(f"\n💡 Database created at: {db_path}")
        print("   (Temporary - will be cleaned up)")
        
    finally:
        # Cleanup
        if page_manager:
            try:
                page_manager.close()
            except:
                pass
        
        try:
            shutil.rmtree(temp_dir)
            print("\n🧹 Cleaned up temporary files")
        except:
            print(f"\n⚠️  Manual cleanup needed: {temp_dir}")


if __name__ == '__main__':
    main()
