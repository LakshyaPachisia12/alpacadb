"""
Interactive CLI for AlpacaDB.

Provides a REPL (Read-Eval-Print-Loop) for executing queries.
"""

import os
import sys
import time
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage import PageManager, Catalog, TableManager
from src.query import Lexer, Parser, LexerError, ParseError
from src.query.ast_nodes import *
from src.executor import QueryExecutor


class AlpacaDBCLI:
    """Interactive command-line interface for AlpacaDB."""

    def __init__(self, db_path: str = "data/alpacadb.db"):
        """Initialize CLI with database connection."""
        self.db_path = db_path
        self.page_manager: Optional[PageManager] = None
        self.catalog: Optional[Catalog] = None
        self.table_manager: Optional[TableManager] = None
        self.running = True
        self.executor: Optional[QueryExecutor] = None

        # Initialize database
        self._initialize_database()

    def _initialize_database(self):
        """Initialize or open existing database."""
        try:
            self.page_manager = PageManager(self.db_path)
            self.catalog = Catalog(self.page_manager)
            self.table_manager = TableManager(self.page_manager, self.catalog)
            self.executor = QueryExecutor(self.table_manager, self.catalog)
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

        if command in ("\\quit", "\\q", "\\exit"):
            print("Goodbye! 🦙")
            self.running = False

        elif command in ("\\tables", "\\dt"):
            self._show_tables()

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
        for table_name in tables:
            schema = self.catalog.get_table_schema(table_name)
            if schema:
                col_count = len(schema.columns)
                print(f"  • {table_name} ({col_count} columns)")
        print()

    def _show_help(self):
        """Display help message."""
        help_text = """
AlpacaDB Commands:

SQL Commands:
  CREATE TABLE name (col1 TYPE, ...)  Create a new table
  DROP TABLE name                     Delete a table
  CREATE INDEX name ON table (col)    Create an index
  INSERT INTO table VALUES (...)      Insert a row
  UPDATE table SET col=val WHERE ...  Update rows
  DELETE FROM table WHERE ...         Delete rows
  SELECT * FROM table WHERE ...       Query data
  BEGIN / COMMIT / ROLLBACK           Transactions

Meta Commands:
  \\tables, \\dt      List all tables
  \\help, \\h         Show this help
  \\quit, \\q         Exit AlpacaDB

Examples:
  CREATE TABLE users (id INT PRIMARY KEY, name STRING, age INT);
  INSERT INTO users VALUES (1, 'Alice', 25);
  SELECT * FROM users WHERE age > 20;
  UPDATE users SET age=26 WHERE id=1;
  DELETE FROM users WHERE age < 18;
"""
        print(help_text)

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
                print(f"(Executed using new executor)")
            else:
                # Use legacy path
                result = self._execute_ast(ast)
                print(f"(Executed using legacy path)")
            # Display result
            elapsed = (time.time() - start_time) * 1000  # milliseconds
            self._display_result(result, elapsed)

        except LexerError as e:
            print(f"❌ Lexer Error: {e}")
        except ParseError as e:
            print(f"❌ Syntax Error: {e}")
        except Exception as e:
            print(f"❌ Execution Error: {e}")

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
            return {
                "type": "CREATE_INDEX",
                "success": True,
                "index": ast.index_name,
                "note": "Index creation queued (implementation in Sprint 4)",
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
        elif result_type == "CREATE_INDEX":
            print(f"✅ Index '{result['index']}' created")
            if "note" in result:
                print(f"   Note: {result['note']}")

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
                print(f"\n{len(rows)} row(s) retrieved ({elapsed_ms:.3f}ms)")

        # UPDATE
        elif result_type == "UPDATE":
            print(f"✅ UPDATE executed")
            if "note" in result:
                print(f"   Note: {result['note']}")

        # DELETE
        elif result_type == "DELETE":
            print(f"✅ DELETE executed")
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

