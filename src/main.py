"""
AlpacaDB Demo Application

Demonstrates storage engine and query parser functionality.
"""

import os
import sys
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage import PageManager, Catalog, TableManager
from src.query import Lexer, Parser


def demo_storage_engine(db_path: Optional[str] = None):
    """Demo original storage engine (Sprint 1)."""
    print("=" * 60)
    print("🦙 AlpacaDB Demo - Storage Engine (Sprint 1)")
    print("=" * 60)
    
    # Clean up old database
    db_path = db_path or 'data/alpacadb_demo.db'
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Initialize
    page_manager = PageManager(db_path)
    catalog = Catalog(page_manager)
    table_manager = TableManager(page_manager, catalog)
    
    print("\n[1] Creating 'users' table...")
    catalog.create_table('users', [
        {'name': 'id', 'type': 'INT', 'nullable': False},
        {'name': 'name', 'type': 'STRING', 'nullable': False},
        {'name': 'age', 'type': 'INT', 'nullable': True}
    ])
    
    print("\n[2] Inserting rows...")
    table_manager.insert_row('users', [1, 'Alice', 25])
    table_manager.insert_row('users', [2, 'Bob', 30])
    table_manager.insert_row('users', [3, 'Charlie', 35])
    
    print("\n[3] Selecting all rows...")
    rows = table_manager.select_all('users')
    
    print("\nResults:")
    print("-" * 60)
    for row in rows:
        print(f"  {row}")
    
    page_manager.close()
    print("\n" + "=" * 60)


def demo_query_parser():
    """Demo query parser (Sprint 2)."""
    print("\n\n")
    print("=" * 60)
    print("🦙 AlpacaDB Demo - Query Parser (Sprint 2)")
    print("=" * 60)
    
    queries = [
        "CREATE TABLE employees (emp_id INT PRIMARY KEY, name STRING, salary INT)",
        "INSERT INTO employees VALUES (101, 'Alice', 50000)",
        "SELECT * FROM employees WHERE salary > 40000",
        "UPDATE employees SET salary=55000 WHERE emp_id=101",
        "DELETE FROM employees WHERE salary < 30000",
        "CREATE INDEX idx_salary ON employees (salary)",
        "BEGIN",
        "COMMIT"
    ]
    
    print("\n[Parsing Example Queries]\n")
    
    for i, query in enumerate(queries, 1):
        print(f"{i}. Query: {query}")
        
        try:
            # Lexical analysis
            lexer = Lexer(query)
            tokens = lexer.tokenize()
            print(f"   Tokens: {len(tokens)-1} tokens generated")  # -1 for EOF
            
            # Parsing
            parser = Parser(tokens)
            ast = parser.parse()
            print(f"   AST: {type(ast).__name__}")
            print(f"   ✅ Parsed successfully\n")
            
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
    
    print("=" * 60)


def demo_interactive_cli():
    """Show how to use interactive CLI."""
    print("\n\n")
    print("=" * 60)
    print("🦙 AlpacaDB - Interactive CLI")
    print("=" * 60)
    
    print("\nTo use the interactive CLI, run:")
    print("\n  python src/cli.py")
    
    print("\nExample session:")
    print("""
    alpacadb> CREATE TABLE products (id INT PRIMARY KEY, name STRING, price INT);
    ✅ Table 'products' created successfully
    
    alpacadb> INSERT INTO products VALUES (1, 'Laptop', 1000);
    ✅ 1 row(s) inserted into 'products'
    
    alpacadb> SELECT * FROM products;
    ┌────┬────────┬───────┐
    │ id │ name   │ price │
    ├────┼────────┼───────┤
    │ 1  │ Laptop │ 1000  │
    └────┴────────┴───────┘
    1 row(s) retrieved (0.002ms)
    
    alpacadb> \\quit
    Goodbye! 🦙
    """)
    
    print("=" * 60)


def main():
    """Run all demos."""
    # Demo 1: Storage Engine
    demo_storage_engine()
    
    # Demo 2: Query Parser
    demo_query_parser()
    
    # Demo 3: Interactive CLI instructions
    demo_interactive_cli()
    
    print("\n✅ Demo completed successfully!")
    print("\nNext steps:")
    print("  • Try interactive CLI: python src/cli.py")
    print("  • Run tests: pytest tests/ -v")
    print("  • Check coverage: pytest --cov=src --cov-report=html")


if __name__ == '__main__':
    main()