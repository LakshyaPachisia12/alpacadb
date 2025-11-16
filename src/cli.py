"""
Interactive CLI for AlpacaDB.

Provides a REPL (Read-Eval-Print-Loop) for executing queries.
"""

import os
import sys
import time
import csv
from typing import Optional

from src.storage import PageManager, Catalog, TableManager
from src.storage.indexing import IndexManager
from src.query import Lexer, Parser, LexerError, ParseError
from src.query.ast_nodes import (
    SelectNode, InsertNode, UpdateNode, DeleteNode,
    CreateTableNode, DropTableNode, CreateIndexNode, DropIndexNode,
    BinaryOp, ColumnRef, Literal, ASTNode, TransactionNode
)
from src.executor import QueryExecutor
from src.errors import AlpacaDBError

# Fix Unicode encoding on Windows
if sys.platform == 'win32':
    # Set stdout/stderr to UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AlpacaDBCLI:
    """Interactive command-line interface for AlpacaDB."""

    def __init__(self, db_path: str = "data/alpacadb.db"):
        """Initialize CLI with database connection."""
        self.db_path = db_path
        self.page_manager: Optional[PageManager] = None
        self.catalog: Optional[Catalog] = None
        self.table_manager: Optional[TableManager] = None
        self.index_manager: Optional[IndexManager] = None
        self.running = True
        self.executor: Optional[QueryExecutor] = None

        # Initialize database
        self._initialize_database()

    def _initialize_database(self):
        """Initialize or open existing database."""
        try:
            self.page_manager = PageManager(self.db_path)
            self.catalog = Catalog(self.page_manager)
            self.index_manager = IndexManager(self.catalog, self.page_manager)
            self.table_manager = TableManager(self.page_manager, self.catalog, self.index_manager)
            self.executor = QueryExecutor(self.table_manager, self.catalog, self.index_manager)
            print(f"Connected to: {self.db_path}")
        except Exception as e:
            print(f"❌ Failed to initialize database: {e}")
            sys.exit(1)

    def run(self):
        """Start the REPL."""
        self._print_welcome()

        while self.running:
            try:
                # Read query
                query = self._read_query()

                if not query.strip():
                    continue

                # Check for meta-commands (start with backslash)
                if query.startswith("\\"):
                    self._execute_meta_command(query)
                    continue

                # Execute SQL query
                self._execute_query(query)

            except KeyboardInterrupt:
                print("\n(Interrupted. Type '\\quit' or press Ctrl+D to exit)")
                continue
            except EOFError:
                print("\nGoodbye! 🦙")
                break

    def _print_welcome(self):
        """Print welcome message."""
        print("=" * 60)
        print("🦙 AlpacaDB v0.2 - Interactive Database Shell")
        print("=" * 60)
        print("Type '\\help' for commands, '\\quit' to exit\n")

    def _read_query(self) -> str:
        """Read query from user (supports multi-line input)."""
        query_lines = []
        prompt = "alpacadb> "

        while True:
            try:
                line = input(prompt).strip()

                # Empty line
                if not line:
                    if query_lines:
                        prompt = "...> "
                        continue
                    else:
                        return ""

                # Meta-command (starts with backslash) - execute immediately
                if line.startswith("\\"):
                    return line

                # Add line to query
                query_lines.append(line)

                # Check if query is complete (ends with semicolon)
                if line.endswith(";"):
                    break

                # Single-line commands (no semicolon needed)
                first_word = line.split()[0].upper() if line.split() else ""
                if first_word in ("BEGIN", "COMMIT", "ROLLBACK"):
                    break

                # Multi-line continuation
                prompt = "...> "

            except EOFError:
                raise

        return " ".join(query_lines)

    def _execute_meta_command(self, command: str):
        """Execute meta-command (commands starting with backslash)."""
        command = command.strip().lower()
        parts = command.split()

        if command in ("\\quit", "\\q", "\\exit"):
            print("Goodbye! 🦙")
            self.running = False

        elif command in ("\\tables", "\\dt"):
            self._show_tables()

        elif command.startswith("\\schema"):
            if len(parts) > 1:
                self._show_schema(parts[1])
            else:
                print("❌ Usage: \\schema <table_name>")

        elif command in ("\\indexes", "\\di"):
            self._show_indexes()

        elif command in ("\\info", "\\i"):
            self._show_database_info()

        elif command in ("\\stats"):
            self._show_statistics()

        elif command.startswith("\\explain"):
            if len(parts) > 1:
                query = " ".join(parts[1:])
                self._explain_query(query)
            else:
                print("❌ Usage: \\explain <query>")

        elif command.startswith("\\export"):
            if len(parts) > 2:
                table_name = parts[1]
                file_path = parts[2]
                self._export_table(table_name, file_path)
            else:
                print("❌ Usage: \\export <table> <file.csv>")

        elif command.startswith("\\import"):
            if len(parts) > 2:
                table_name = parts[1]
                file_path = parts[2]
                self._import_table(table_name, file_path)
            else:
                print("❌ Usage: \\import <table> <file.csv>")

        elif command in ("\\help", "\\h", "\\?"):
            self._show_help()

        else:
            print(f"❌ Unknown command: {command}")
            print("Type '\\help' for available commands")

    def _show_tables(self):
        """Display all tables in database."""
        if self.catalog is None:
            print("❌ Database not initialized")
            return

        tables = self.catalog.list_tables()

        if not tables:
            print("No tables in database")
            return

        print("\nAvailable tables:")
        print("┌" + "─" * 50 + "┐")
        print(f"│ {'Table Name':<30} {'Columns':<18} │")
        print("├" + "─" * 50 + "┤")
        for table_name in tables:
            schema = self.catalog.get_table_schema(table_name)
            if schema:
                col_count = len(schema.columns)
                row_count = len(self.table_manager.select_all(table_name))
                print(f"│ {table_name:<30} {col_count:<7} ({row_count} rows) │")
        print("└" + "─" * 50 + "┘")
        print()

    def _show_schema(self, table_name: str):
        """Display schema for a specific table."""
        if self.catalog is None:
            print("❌ Database not initialized")
            return

        schema = self.catalog.get_table_schema(table_name)
        if not schema:
            print(f"❌ Table '{table_name}' does not exist")
            return

        print(f"\n📋 Schema for table '{table_name}':")
        print("┌" + "─" * 70 + "┐")
        print(f"│ {'Column':<25} {'Type':<15} {'Nullable':<10} {'Primary Key':<17} │")
        print("├" + "─" * 70 + "┤")

        for col in schema.columns:
            col_name = col['name']
            col_type = col['type']
            nullable = "Yes" if col.get('nullable', True) else "No"
            primary_key = "Yes" if 'PRIMARY KEY' in col_type.upper() else "No"
            print(f"│ {col_name:<25} {col_type:<15} {nullable:<10} {primary_key:<17} │")

        print("└" + "─" * 70 + "┘")
        print()

    def _show_indexes(self):
        """Display all indexes in database."""
        if self.catalog is None:
            print("❌ Database not initialized")
            return

        indexes = self.catalog.list_indexes()
        if not indexes:
            print("No indexes in database")
            return

        print("\n🔍 Indexes:")
        print("┌" + "─" * 80 + "┐")
        print(f"│ {'Index Name':<25} {'Table':<20} {'Column':<20} {'Type':<12} │")
        print("├" + "─" * 80 + "┤")

        for index_name in indexes:
            idx_info = self.catalog.get_index(index_name)
            if idx_info:
                print(f"│ {idx_info.index_name:<25} {idx_info.table_name:<20} "
                      f"{idx_info.column_name:<20} {idx_info.index_type:<12} │")

        print("└" + "─" * 80 + "┘")
        print()

    def _show_database_info(self):
        """Display database information."""
        if self.page_manager is None or self.catalog is None:
            print("❌ Database not initialized")
            return

        num_pages = self.page_manager.get_num_pages()
        db_size = num_pages * 4096  # 4KB per page
        db_size_mb = db_size / (1024 * 1024)

        num_tables = len(self.catalog.list_tables())
        num_indexes = len(self.catalog.list_indexes())

        # Count total rows
        total_rows = 0
        for table_name in self.catalog.list_tables():
            try:
                rows = self.table_manager.select_all(table_name)
                total_rows += len(rows)
            except:
                pass

        print("\n📊 Database Information:")
        print("┌" + "─" * 50 + "┐")
        print(f"│ {'Property':<25} {'Value':<22} │")
        print("├" + "─" * 50 + "┤")
        print(f"│ {'Database Path':<25} {self.db_path[:22]:<22} │")
        print(f"│ {'Total Pages':<25} {num_pages:<22} │")
        print(f"│ {'Database Size':<25} {db_size_mb:.2f} MB{'':<15} │")
        print(f"│ {'Tables':<25} {num_tables:<22} │")
        print(f"│ {'Indexes':<25} {num_indexes:<22} │")
        print(f"│ {'Total Rows':<25} {total_rows:<22} │")
        print("└" + "─" * 50 + "┘")
        print()

    def _show_statistics(self):
        """Display query execution statistics."""
        if self.executor is None:
            print("❌ Executor not initialized")
            return

        print("\n📈 Query Execution Statistics:")
        print(f"  Last plan type: {self.executor.last_plan or 'N/A'}")
        print()

    def _show_help(self):
        """Display help message."""
        help_text = """
🦙 AlpacaDB Commands:

SQL Commands:
  CREATE TABLE name (col1 TYPE, ...)  Create a new table
  DROP TABLE name                     Delete a table
  CREATE INDEX name ON table (col)    Create an index
  DROP INDEX name                     Drop an index
  INSERT INTO table VALUES (...)      Insert a row
  UPDATE table SET col=val WHERE ...  Update rows
  DELETE FROM table WHERE ...         Delete rows
  SELECT * FROM table WHERE ...       Query data
  BEGIN / COMMIT / ROLLBACK           Transactions

Meta Commands:
  \\tables, \\dt              List all tables
  \\schema <table>           Show table schema
  \\indexes, \\di            List all indexes
  \\info, \\i                Database information
  \\stats                    Query statistics
  \\explain <query>          Show query execution plan
  \\export <table> <file>    Export table to CSV
  \\import <table> <file>    Import table from CSV
  \\help, \\h                Show this help
  \\quit, \\q                Exit AlpacaDB

Examples:
  CREATE TABLE users (id INT PRIMARY KEY, name STRING, age INT);
  CREATE INDEX idx_age ON users (age);
  INSERT INTO users VALUES (1, 'Alice', 25);
  SELECT * FROM users WHERE age > 20;
  EXPLAIN SELECT * FROM users WHERE age = 25;
  \\schema users
  \\indexes
"""
        print(help_text)

    def _explain_query(self, query: str):
        """Display query execution plan."""
        try:
            # Parse the query
            lexer = Lexer(query)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            ast = parser.parse()

            if not isinstance(ast, SelectNode):
                print("❌ EXPLAIN only works with SELECT queries")
                return

            if self.executor is None or self.executor.optimizer is None:
                print("❌ Optimizer not available")
                return

            # Get query plan
            plan = self.executor.optimizer.optimize(ast)

            # Generate explanation
            explanation = self.executor.optimizer.explain(plan)

            print("\n🔍 Query Execution Plan:")
            print("┌" + "─" * 70 + "┐")
            for line in explanation.split('\n'):
                if line.strip():
                    print(f"│ {line:<68} │")
            print("└" + "─" * 70 + "┘")

            # Estimate costs if cost-based optimizer is available
            if hasattr(self.executor.optimizer, 'estimate_cost'):
                cost = self.executor.optimizer.estimate_cost(plan)
                print(f"\n💰 Estimated Cost: {cost:.2f}")

            print()

        except AlpacaDBError as e:
            # All AlpacaDB errors already have nice formatting
            print(str(e))
        except Exception as e:
            # Internal errors - show a user-friendly message
            print("❌ ERROR [Internal]: An unexpected error occurred")
            print("💡 HINT: This may be a bug. Please report this issue.")
            print(f"📋 Details: {str(e)}")

    def _export_table(self, table_name: str, file_path: str):
        """Export table data to CSV file."""
        try:
            # Get table schema
            schema = self.catalog.get_table_schema(table_name)
            if not schema:
                print(f"❌ Table '{table_name}' does not exist")
                return

            # Get all rows
            rows = self.table_manager.select_all(table_name)
            if not rows:
                print(f"⚠️  Table '{table_name}' is empty")
                return

            # Get column names
            column_names = [col['name'] for col in schema.columns]

            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(column_names)  # Header
                writer.writerows(rows)  # Data

            print(f"✅ Exported {len(rows)} row(s) from '{table_name}' to '{file_path}'")

        except Exception as e:
            print(f"❌ Export failed: {e}")

    def _import_table(self, table_name: str, file_path: str):
        """Import table data from CSV file."""
        try:
            # Check if table exists
            schema = self.catalog.get_table_schema(table_name)
            if not schema:
                print(f"❌ Table '{table_name}' does not exist")
                print("   Create the table first using CREATE TABLE")
                return

            # Check if file exists
            if not os.path.exists(file_path):
                print(f"❌ File '{file_path}' does not exist")
                return

            column_names = [col['name'] for col in schema.columns]

            # Read from CSV
            imported_count = 0
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader, None)  # Skip header

                for row in reader:
                    if len(row) != len(column_names):
                        print(f"⚠️  Skipping row {imported_count + 1}: column count mismatch")
                        continue

                    # Convert values to appropriate types
                    typed_values = []
                    for i, value in enumerate(row):
                        col_type = schema.columns[i]['type'].upper()
                        if 'INT' in col_type:
                            try:
                                typed_values.append(int(value))
                            except ValueError:
                                typed_values.append(0)
                        elif 'STRING' in col_type:
                            typed_values.append(str(value))
                        elif 'BOOLEAN' in col_type:
                            typed_values.append(value.lower() == 'true')
                        else:
                            typed_values.append(value)

                    # Insert row
                    self.table_manager.insert_row(table_name, typed_values)
                    imported_count += 1

            print(f"✅ Imported {imported_count} row(s) from '{file_path}' into '{table_name}'")

        except Exception as e:
            print(f"❌ Import failed: {e}")

    def _execute_query(self, query: str):
        """Parse and execute SQL query."""
        start_time = time.time()

        try:
            # Lexical analysis
            lexer = Lexer(query)
            tokens = lexer.tokenize()

            # Parsing
            parser = Parser(tokens)
            ast = parser.parse()

            # Execution
            if self._should_use_executor(ast):
                # Use new executor path
                result = self._execute_with_executor(ast)
                print("(Executed using new executor)")
            else:
                # Use legacy path
                result = self._execute_ast(ast)
                print("(Executed using legacy path)")
            # Display result
            elapsed = (time.time() - start_time) * 1000  # milliseconds
            self._display_result(result, elapsed)

        except LexerError as e:
            print(f"❌ Lexer Error: {e}")
        except ParseError as e:
            print(f"❌ Syntax Error: {e}")
        except AlpacaDBError as e:
            # All AlpacaDB errors already have nice formatting
            print(str(e))
        except Exception as e:
            print("❌ ERROR [Internal]: An unexpected error occurred")
            print("💡 HINT: This may be a bug. Please report this issue.")
            print(f"📋 Details: {str(e)}")

    def _execute_ast(self, ast: ASTNode):
        """Execute parsed AST node."""
        # Safety checks
        if self.catalog is None or self.table_manager is None:
            raise Exception("Database not initialized")

        # DDL: CREATE TABLE
        if isinstance(ast, CreateTableNode):
            columns_dict = [
                {"name": col.name, "type": col.data_type, "nullable": col.nullable}
                for col in ast.columns
            ]
            success = self.catalog.create_table(ast.table_name, columns_dict)
            return {"type": "CREATE_TABLE", "success": success, "table": ast.table_name}

        # DDL: DROP TABLE
        elif isinstance(ast, DropTableNode):
            success = self.catalog.drop_table(ast.table_name)
            return {"type": "DROP_TABLE", "success": success, "table": ast.table_name}

        # DDL: CREATE INDEX
        elif isinstance(ast, CreateIndexNode):
            if self.index_manager:
                # Use IndexManager for full index creation with B-Tree
                self.index_manager.create_index(
                    ast.index_name,
                    ast.table_name,
                    ast.column_name,
                    self.table_manager
                )
                success = True
            else:
                # Fallback to catalog-only creation
                success = self.catalog.create_index(
                    ast.index_name,
                    ast.table_name,
                    ast.column_name
                )
            return {
                'type': 'CREATE_INDEX',
                'success': True,
                'index': ast.index_name,
                'table': ast.table_name,
                'column': ast.column_name
            }

        # DDL: DROP INDEX
        elif isinstance(ast, DropIndexNode):
            if self.index_manager:
                # Use IndexManager to properly clean up B-Tree
                self.index_manager.drop_index(ast.index_name, ast.table_name)
                success = True
            else:
                # Fallback to catalog-only drop
                success = self.catalog.drop_index(ast.index_name)
            return {
                'type': 'DROP_INDEX',
                'success': success,
                'index': ast.index_name,
                'table': ast.table_name
            }

        # DML: INSERT
        elif isinstance(ast, InsertNode):
            success = self.table_manager.insert_row(ast.table_name, ast.values)
            return {
                "type": "INSERT",
                "success": success,
                "table": ast.table_name,
                "rows": 1,
            }

        # DML: SELECT
        elif isinstance(ast, SelectNode):
            # Try to use index if WHERE clause has indexed column
            rows = None

            if ast.where_clause:
                # Check if WHERE clause is a simple equality on indexed column
                index_used = self._try_index_scan(ast.table_name, ast.where_clause)
                if index_used:
                    column_name, value = index_used
                    rows = self.table_manager.select_with_index(ast.table_name, column_name, value)

            # Fall back to full table scan if no index used
            if rows is None:
                rows = self.table_manager.select_all(ast.table_name)

                # Apply WHERE clause if present
                if ast.where_clause:
                    rows = self._filter_rows(rows, ast.where_clause, ast.table_name)

            # Apply ORDER BY if present
            if ast.order_by:
                rows = self._sort_rows(rows, ast.order_by, ast.table_name)

            return {
                "type": "SELECT",
                "table": ast.table_name,
                "columns": ast.columns,
                "rows": rows,
            }

        # DML: UPDATE
        elif isinstance(ast, UpdateNode):
            return {
                "type": "UPDATE",
                "success": True,
                "note": "UPDATE queued (implementation in Sprint 4)",
            }

        # DML: DELETE
        elif isinstance(ast, DeleteNode):
            return {
                "type": "DELETE",
                "success": True,
                "note": "DELETE queued (implementation in Sprint 4)",
            }

        # Transaction commands
        elif isinstance(ast, TransactionNode):
            return {
                "type": "TRANSACTION",
                "command": ast.command,
                "note": "Transaction support coming in Sprint 6",
            }

        else:
            raise Exception(f"Unsupported AST node type: {type(ast).__name__}")

    def _try_index_scan(self, table_name, where_clause):
        """
        Check if WHERE clause can use an index.

        Returns:
            (column_name, value) tuple if index can be used, None otherwise
        """
        # Only handle simple equality conditions: column = value
        if not isinstance(where_clause, BinaryOp):
            return None

        if where_clause.operator != '=':
            return None

        # Left side must be a column reference
        if not isinstance(where_clause.left, ColumnRef):
            return None

        # Right side must be a literal value
        if not isinstance(where_clause.right, Literal):
            return None

        column_name = where_clause.left.name
        value = where_clause.right.value

        # Check if there's an index on this column
        indexes = self.catalog.get_indexes_for_table(table_name)
        for idx in indexes:
            if idx.column_name == column_name:
                return (column_name, value)

        return None

    def _filter_rows(self, rows, where_clause, table_name):
        """Apply WHERE clause filtering."""
        if self.catalog is None:
            return rows

        schema = self.catalog.get_table_schema(table_name)
        if schema is None:
            return rows

        col_names = [col["name"] for col in schema.columns]

        filtered = []
        for row in rows:
            if self._evaluate_condition(row, col_names, where_clause):
                filtered.append(row)

        return filtered

    def _evaluate_condition(self, row, col_names, condition):
        """Evaluate WHERE condition for a single row."""
        if isinstance(condition, BinaryOp):
            # Get column value
            if isinstance(condition.left, ColumnRef):
                col_idx = col_names.index(condition.left.name)
                left_val = row[col_idx]
            else:
                left_val = condition.left

            # Get comparison value
            if isinstance(condition.right, Literal):
                right_val = condition.right.value
            else:
                right_val = condition.right

            # Perform comparison
            op = condition.operator
            if op == "=":
                return left_val == right_val
            elif op == "!=":
                return left_val != right_val
            elif op == ">":
                return left_val > right_val
            elif op == "<":
                return left_val < right_val
            elif op == ">=":
                return left_val >= right_val
            elif op == "<=":
                return left_val <= right_val
            elif op == "AND":
                return self._evaluate_condition(
                    row, col_names, condition.left
                ) and self._evaluate_condition(row, col_names, condition.right)
            elif op == "OR":
                return self._evaluate_condition(
                    row, col_names, condition.left
                ) or self._evaluate_condition(row, col_names, condition.right)

        return True

    def _sort_rows(self, rows, order_by, table_name):
        """Apply ORDER BY sorting."""
        if self.catalog is None:
            return rows

        schema = self.catalog.get_table_schema(table_name)
        if schema is None:
            return rows

        col_names = [col["name"] for col in schema.columns]

        col_name, direction = order_by
        col_idx = col_names.index(col_name)

        reverse = direction == "DESC"
        return sorted(rows, key=lambda r: r[col_idx], reverse=reverse)

    def _display_result(self, result, elapsed_ms):
        """Display query result in formatted output."""
        if result is None:
            return

        result_type = result.get("type")

        # CREATE TABLE
        if result_type == "CREATE_TABLE":
            if result["success"]:
                print(f"✅ Table '{result['table']}' created successfully")
            else:
                print(f"❌ Failed to create table '{result['table']}'")

        # DROP TABLE
        elif result_type == "DROP_TABLE":
            if result["success"]:
                print(f"✅ Table '{result['table']}' dropped")
            else:
                print(f"❌ Failed to drop table '{result['table']}'")

        # CREATE INDEX
        elif result_type == 'CREATE_INDEX':
            if result['success']:
                print(f"✅ Index '{result['index']}' created on {result['table']}.{result['column']}")
            else:
                print(f"❌ Failed to create index '{result['index']}'")

        # DROP INDEX
        elif result_type == 'DROP_INDEX':
            if result['success']:
                print(f"✅ Index '{result['index']}' dropped")
            else:
                print(f"❌ Failed to drop index '{result['index']}'")

        # INSERT
        elif result_type == "INSERT":
            if result["success"]:
                print(f"✅ {result['rows']} row(s) inserted into '{result['table']}'")
            else:
                print(f"❌ Failed to insert into '{result['table']}'")

        # SELECT
        elif result_type == "SELECT":
            rows = result["rows"]
            if not rows:
                print("(No rows returned)")
            else:
                # Get column names
                table_name = result["table"]

                if self.catalog is None:
                    print("❌ Database not initialized")
                    return

                schema = self.catalog.get_table_schema(table_name)
                if schema is None:
                    print(f"❌ Table '{table_name}' not found")
                    return

                if result["columns"] == ["*"]:
                    col_names = [col["name"] for col in schema.columns]
                else:
                    col_names = result["columns"]

                # Display as formatted table
                self._display_table(col_names, rows)
                # Show execution stats if available
                plan_info = ""
                if self.executor and self.executor.last_plan:
                    plan_info = f" [Plan: {self.executor.last_plan}]"

                print(f"\n{len(rows)} row(s) retrieved in {elapsed_ms:.3f}ms{plan_info}")

        # UPDATE
        elif result_type == "UPDATE":
            print("✅ UPDATE executed")
            if "note" in result:
                print(f"   Note: {result['note']}")

        # DELETE
        elif result_type == "DELETE":
            print("✅ DELETE executed")
            if "note" in result:
                print(f"   Note: {result['note']}")

        # TRANSACTION
        elif result_type == "TRANSACTION":
            print(f"✅ {result['command']} executed")
            if "note" in result:
                print(f"   Note: {result['note']}")

        print()  # Blank line

    def _display_table(self, columns, rows):
        """Display rows as formatted table with borders."""
        # Calculate column widths
        col_widths = [len(col) for col in columns]

        for row in rows:
            for i, val in enumerate(row):
                val_str = str(val)
                col_widths[i] = max(col_widths[i], len(val_str))

        # Top border
        print("┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐")

        # Header
        header_parts = [f" {col:{col_widths[i]}} " for i, col in enumerate(columns)]
        print("│" + "│".join(header_parts) + "│")

        # Header separator
        print("├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤")

        # Rows
        for row in rows:
            row_parts = [f" {str(val):{col_widths[i]}} " for i, val in enumerate(row)]
            print("│" + "│".join(row_parts) + "│")

        # Bottom border
        print("└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘")

    def close(self):
        """Clean shutdown."""
        if self.page_manager:
            self.page_manager.close()

    def _should_use_executor(self, ast: ASTNode) -> bool:
        """Decide whether to use new executor or legacy execution."""
        # Route all main query types to executor
        return isinstance(ast, (
            SelectNode,
            CreateTableNode,
            InsertNode,
            UpdateNode,
            DeleteNode,
        ))

    def _execute_with_executor(self, ast: ASTNode):
        """Execute AST using the new QueryExecutor."""
        try:
            rows, columns = self.executor.execute(ast)

            # Convert executor output to CLI result format
            if isinstance(ast, SelectNode):
                return {
                    "type": "SELECT",
                    "table": ast.table_name,
                    "columns": columns if columns else ["*"],
                    "rows": rows,
                }
            elif isinstance(ast, InsertNode):
                return {
                    "type": "INSERT",
                    "success": True,
                    "table": ast.table_name,
                    "rows": 1,
                }
            elif isinstance(ast, CreateTableNode):
                return {
                    "type": "CREATE_TABLE",
                    "success": True,
                    "table": ast.table_name,
                }
            elif isinstance(ast, UpdateNode):
                return {
                    "type": "UPDATE",
                    "success": True,
                    "table": ast.table_name,
                }
            elif isinstance(ast, DeleteNode):
                return {
                    "type": "DELETE",
                    "success": True,
                    "table": ast.table_name,
                }
            else:
                raise ValueError(f"Unsupported AST type: {type(ast).__name__}")

        except Exception as e:
            raise Exception(f"Executor error: {e}")

def main():
    """Entry point for CLI."""
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h", "help"):
        print("""
🦙 AlpacaDB - A custom relational database management system

Usage:
    alpaca [database_path]

Arguments:
    database_path    Path to the database file (default: data/alpacadb.db)

Examples:
    alpaca                           Start with default database
    alpaca data/mydb.db              Start with custom database file

Once inside AlpacaDB:
    Type SQL queries or use meta-commands (\\help for full list)
    Type \\quit or \\q to exit
""")
        return

    # Check for custom database path
    db_path = "data/alpacadb.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    # Create and run CLI
    cli = AlpacaDBCLI(db_path)

    try:
        cli.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Exiting...")
    finally:
        cli.close()


if __name__ == "__main__":
    main()
