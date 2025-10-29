"""
AlpacaDB - Main Entry Point

This file provides a simple CLI and demo to test the
storage engine functionality from end-to-end.
"""

import os
import shutil
from storage import PageManager, Catalog, TableManager

# Constants
DB_DIR = "data"
DB_FILE = os.path.join(DB_DIR, "alpacadb.db")

def run_demo():
    """
    Execute a simple demo:
    1. Clean up old data
    2. Initialize managers
    3. Create a 'users' table
    4. Insert 3 rows
    5. Select all rows back
    6. Close the database
    """
    print("🦙 Welcome to the AlpacaDB Demo!")
    print("="*40)
    
    # 1. Clean up old data directory
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)
        print(f"🧹 Cleaned up old '{DB_DIR}' directory.")
    os.makedirs(DB_DIR, exist_ok=True)

    # 2. Initialize all managers
    print(f"🚀 Initializing database file at: {DB_FILE}")
    page_manager = None
    try:
        page_manager = PageManager(DB_FILE)
        catalog = Catalog(page_manager)
        table_manager = TableManager(page_manager, catalog)
        
        # 3. Create a 'users' table
        print("\n[Demo] Creating 'users' table...")
        user_schema = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': False},
            {'name': 'age', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('users', user_schema)
        
        # 4. Insert rows
        print("\n[Demo] Inserting rows...")
        table_manager.insert_row('users', [1, 'Alice', 25])
        table_manager.insert_row('users', [2, 'Bob', 30])
        table_manager.insert_row('users', [3, 'Charlie', None])  # Test NULL
        
        # 5. Select all
        print("\n[Demo] Selecting all rows from 'users'...")
        rows = table_manager.select_all('users')
        
        print("\n📊 Results:")
        print("---------------------------------")
        print(f"  {'ID':<3} | {'Name':<10} | {'Age':<5}")
        print("---------------------------------")
        for row in rows:
            print(f"  {row[0]:<3} | {row[1]:<10} | {row[2] or 'NULL':<5}")
        print("---------------------------------")
        
    except Exception as e:
        print(f"\n🚨 An error occurred: {e}")
    
    finally:
        # 6. Close the database
        if page_manager:
            page_manager.close()
    
    print("\n="*40)
    print("Demo complete. Data is safe on disk.")

if __name__ == '__main__':
    # Add src to Python path to allow imports
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    from src.storage import PageManager, Catalog, TableManager
    run_demo()