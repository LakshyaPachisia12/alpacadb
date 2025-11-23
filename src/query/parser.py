"""
Parser for AlpacaDB query language.

Converts tokens into Abstract Syntax Tree (AST).
Uses recursive descent parsing.
"""

from typing import List
from .tokens import Token, TokenType
from .ast_nodes import *


# Keep old ParseError for backward compatibility but import from errors
from ..errors import ParserError, AlpacaSyntaxError
ParseError = ParserError  # Alias for backward compatibility


class Parser:
    """
    Recursive descent parser for AlpacaDB SQL-like syntax.

    Grammar (simplified):
        statement     → ddl_stmt | dml_stmt | txn_stmt
        ddl_stmt      → CREATE TABLE | DROP TABLE | CREATE INDEX
        dml_stmt      → SELECT | INSERT | UPDATE | DELETE
        txn_stmt      → BEGIN | COMMIT | ROLLBACK

    Usage:
        lexer = Lexer("SELECT * FROM users")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
    """

    def __init__(self, tokens: List[Token]):
        """
        Initialize parser with token stream.

        Args:
            tokens: List of tokens from lexer
        """
        self.tokens = tokens
        self.current = 0

    def parse(self) -> ASTNode:
        """
        Parse token stream into AST.

        Returns:
            Root AST node representing the query

        Raises:
            ParseError: If syntax is invalid
        """
        try:
            return self._statement()
        except AlpacaSyntaxError as e:
            raise ParserError(
                e.message,
                token=e.token,
                hint=e.hint,
                context=e.context
            ) from e
        except ParserError:
            raise
        except Exception as e:
            current_token = self._peek()
            raise ParserError(
                f"Unexpected error at line {current_token.line}, column {current_token.column}",
                hint="This may be a syntax error. Check your query syntax carefully.",
                token=current_token.lexeme if current_token else None,
                context=f"Line {current_token.line}, Column {current_token.column}"
            ) from e

    def _statement(self) -> ASTNode:
        """
        Parse any statement.

        Determines statement type from first keyword.
        """
        token = self._peek()

        # DDL statements
        if self._check(TokenType.CREATE):
            self._consume(TokenType.CREATE)
            return self._create_statement()
        elif self._check(TokenType.DROP):
            self._consume(TokenType.DROP)
            return self._drop_statement()

        # EXPLAIN statement
        elif self._check(TokenType.EXPLAIN):
            self._consume(TokenType.EXPLAIN)
            self._consume(TokenType.SELECT)
            select_node = self._select_statement()
            select_node.is_explain = True
            return select_node

        # DML statements
        elif self._check(TokenType.SELECT):
            self._consume(TokenType.SELECT)
            return self._select_statement()
        elif self._check(TokenType.INSERT):
            self._consume(TokenType.INSERT)
            return self._insert_statement()
        elif self._check(TokenType.UPDATE):
            self._consume(TokenType.UPDATE)
            return self._update_statement()
        elif self._check(TokenType.DELETE):
            self._consume(TokenType.DELETE)
            return self._delete_statement()

        # Transaction statements
        elif self._check(TokenType.BEGIN):
            self._consume(TokenType.BEGIN)
            return TransactionNode('BEGIN')
        elif self._check(TokenType.COMMIT):
            self._consume(TokenType.COMMIT)
            return TransactionNode('COMMIT')
        elif self._check(TokenType.ROLLBACK):
            self._consume(TokenType.ROLLBACK)
            return TransactionNode('ROLLBACK')

        else:
            raise AlpacaSyntaxError(
                f"Unexpected token '{token.lexeme}' at line {token.line}, column {token.column}",
                hint="Expected a statement keyword (CREATE, SELECT, INSERT, UPDATE, DELETE, DROP, BEGIN, COMMIT, ROLLBACK).",
                token=token.lexeme,
                context=f"Line {token.line}, Column {token.column}"
            )

    def _create_statement(self) -> ASTNode:
        """Parse CREATE TABLE or CREATE INDEX statement."""
        # CREATE token already consumed by _statement()
        next_token = self._peek()

        if next_token.type == TokenType.TABLE:
            return self._create_table()
        elif next_token.type == TokenType.INDEX:
            return self._create_index_statement()
        else:
            raise AlpacaSyntaxError(
                f"Expected 'TABLE' or 'INDEX' after CREATE, but got '{next_token.lexeme}'",
                hint="CREATE statement must be followed by TABLE or INDEX. Example: CREATE TABLE users ... or CREATE INDEX idx_name ...",
                token=next_token.lexeme,
                context=f"Line {next_token.line}, Column {next_token.column}"
            )

    def _create_index_statement(self) -> CreateIndexNode:
        """Parse CREATE INDEX statement."""
        self._consume(TokenType.INDEX)
        index_name = self._consume(TokenType.IDENTIFIER).value

        self._consume(TokenType.ON)
        table_name = self._consume(TokenType.IDENTIFIER).value

        self._consume(TokenType.LEFT_PAREN)
        column_name = self._consume(TokenType.IDENTIFIER).value
        self._consume(TokenType.RIGHT_PAREN)

        # Optional USING clause (for future index types)
        if self._check(TokenType.USING):
            self._consume(TokenType.USING)
            _index_type = self._consume(TokenType.IDENTIFIER).value
            # Currently ignored, but can be extended in future

        return CreateIndexNode(index_name, table_name, column_name)

    def _drop_statement(self) -> ASTNode:
        """Parse DROP TABLE or DROP INDEX statement."""
        # DROP token already consumed by _statement()
        next_token = self._peek()

        if next_token.type == TokenType.TABLE:
            return self._drop_table()
        elif next_token.type == TokenType.INDEX:
            return self._drop_index_statement()
        else:
            raise AlpacaSyntaxError(
                f"Expected 'TABLE' or 'INDEX' after DROP, but got '{next_token.lexeme}'",
                hint="DROP statement must be followed by TABLE or INDEX. Example: DROP TABLE users or DROP INDEX idx_name ...",
                token=next_token.lexeme,
                context=f"Line {next_token.line}, Column {next_token.column}"
            )

    def _drop_index_statement(self) -> DropIndexNode:
        """Parse DROP INDEX statement."""
        self._consume(TokenType.INDEX)
        index_name = self._consume(TokenType.IDENTIFIER).value

        self._consume(TokenType.ON)
        table_name = self._consume(TokenType.IDENTIFIER).value
        return DropIndexNode(index_name, table_name)

    # ==================== DDL Parsing ====================

    def _create_table(self) -> CreateTableNode:
        """
        Parse: CREATE TABLE table_name (col1 TYPE, col2 TYPE, ...)

        Example:
            CREATE TABLE users (
                id INT PRIMARY KEY,
                name STRING,
                age INT
            )
        """
        self._consume(TokenType.TABLE)

        # Table name
        table_name_token = self._consume(TokenType.IDENTIFIER)
        table_name = table_name_token.value

        # Opening parenthesis
        self._consume(TokenType.LEFT_PAREN)

        # Parse column definitions
        columns = []
        while not self._check(TokenType.RIGHT_PAREN):
            column = self._column_definition()
            columns.append(column)

            # Comma between columns (optional before closing paren)
            if not self._check(TokenType.RIGHT_PAREN):
                self._consume(TokenType.COMMA)

        # Closing parenthesis
        self._consume(TokenType.RIGHT_PAREN)

        # Semicolon (optional)
        if self._check(TokenType.SEMICOLON):
            self._consume(TokenType.SEMICOLON)

        # Validate: Only one PRIMARY KEY allowed
        primary_key_count = sum(1 for col in columns if col.is_primary_key)
        if primary_key_count > 1:
            raise AlpacaSyntaxError(
                f"Table '{table_name}' cannot have multiple PRIMARY KEY columns",
                hint="A table can only have one PRIMARY KEY. Remove extra PRIMARY KEY constraints or use a composite key.",
                token="PRIMARY KEY",
                context=f"Table: {table_name}"
            )

        return CreateTableNode(table_name, columns)

    def _column_definition(self) -> Column:
        """
        Parse single column definition.

        Grammar:
            column_name TYPE [PRIMARY KEY] [NOT NULL]

        Example:
            id INT PRIMARY KEY
            name STRING NOT NULL
            age INT
        """
        # Column name
        col_name_token = self._consume(TokenType.IDENTIFIER)
        col_name = col_name_token.value

        # Data type
        if self._check(TokenType.INT):
            data_type = 'INT'
            self._consume(TokenType.INT)
        elif self._check(TokenType.STRING):
            data_type = 'STRING'
            self._consume(TokenType.STRING)
        elif self._check(TokenType.BOOLEAN):
            data_type = 'BOOLEAN'
            self._consume(TokenType.BOOLEAN)
        else:
            token = self._peek()
            raise AlpacaSyntaxError(
                f"Expected data type (INT, STRING, BOOLEAN) at line {token.line}, but got '{token.lexeme}'",
                hint="Column definitions require a data type after the column name. Valid types: INT, STRING, BOOLEAN.",
                token=token.lexeme,
                context=f"Line {token.line}, Column {token.column}"
            )

        # Optional constraints
        is_primary_key = False
        nullable = True

        # PRIMARY KEY constraint
        if self._check(TokenType.PRIMARY):
            self._consume(TokenType.PRIMARY)
            self._consume(TokenType.KEY)
            is_primary_key = True
            nullable = False  # PRIMARY KEY implies NOT NULL

        # NOT NULL constraint (if not already set by PRIMARY KEY)
        # Note: We don't have NOT token, so we'll skip this for v1.0
        # In real SQL: "name STRING NOT NULL"

        return Column(col_name, data_type, is_primary_key, nullable)

    def _create_index(self) -> CreateIndexNode:
        """
        Parse: CREATE INDEX index_name ON table_name (column)

        Example:
            CREATE INDEX idx_age ON users (age)
        """
        self._consume(TokenType.INDEX)

        # Index name
        index_name_token = self._consume(TokenType.IDENTIFIER)
        index_name = index_name_token.value

        # ON keyword
        self._consume(TokenType.ON)

        # Table name
        table_name_token = self._consume(TokenType.IDENTIFIER)
        table_name = table_name_token.value

        # Column (in parentheses)
        self._consume(TokenType.LEFT_PAREN)
        column_token = self._consume(TokenType.IDENTIFIER)
        column_name = column_token.value
        self._consume(TokenType.RIGHT_PAREN)

        # Semicolon (optional)
        if self._check(TokenType.SEMICOLON):
            self._consume(TokenType.SEMICOLON)

        return CreateIndexNode(index_name, table_name, column_name)

    def _drop_table(self) -> DropTableNode:
        """
        Parse: DROP TABLE table_name

        Example:
            DROP TABLE users
        """
        self._consume(TokenType.TABLE)

        table_name_token = self._consume(TokenType.IDENTIFIER)
        table_name = table_name_token.value

        # Semicolon (optional)
        if self._check(TokenType.SEMICOLON):
            self._consume(TokenType.SEMICOLON)

        return DropTableNode(table_name)

    # ==================== DML Parsing ====================

    def _insert_statement(self) -> InsertNode:
        """
        Parse: INSERT INTO table_name VALUES (val1, val2, ...)

        Example:
            INSERT INTO users VALUES (1, 'Alice', 25)
        """
        # INSERT token already consumed by _statement()
        self._consume(TokenType.INTO)

        # Table name
        table_name_token = self._consume(TokenType.IDENTIFIER)
        table_name = table_name_token.value

        # VALUES keyword
        self._consume(TokenType.VALUES)

        # Values (in parentheses)
        self._consume(TokenType.LEFT_PAREN)

        values = []
        while not self._check(TokenType.RIGHT_PAREN):
            value = self._literal()
            values.append(value)

            if not self._check(TokenType.RIGHT_PAREN):
                self._consume(TokenType.COMMA)

        self._consume(TokenType.RIGHT_PAREN)

        # Semicolon (optional)
        if self._check(TokenType.SEMICOLON):
            self._consume(TokenType.SEMICOLON)

        return InsertNode(table_name, values)

    def _select_statement(self) -> SelectNode:
        """
        Parse: SELECT columns FROM table [WHERE condition] [GROUP BY cols] [HAVING condition] [ORDER BY column]

        Examples:
            SELECT * FROM users
            SELECT COUNT(*), department FROM employees GROUP BY department
            SELECT department, AVG(salary) FROM employees GROUP BY department HAVING AVG(salary) > 50000
        """
        # SELECT token already consumed by _statement()

        # Columns (* or col1, col2, ... or aggregate functions)
        columns = []
        aggregates = []

        if self._check(TokenType.STAR):
            self._consume(TokenType.STAR)
            columns = ['*']
        else:
            while True:
                # Check if it's an aggregate function
                if self._check_aggregate_function():
                    agg_func = self._parse_aggregate_function()
                    aggregates.append(agg_func)
                    # Also add to columns for backward compatibility
                    columns.append(str(agg_func))
                else:
                    col_token = self._consume(TokenType.IDENTIFIER)
                    columns.append(col_token.value)

                if not self._check(TokenType.COMMA):
                    break
                self._consume(TokenType.COMMA)

        # FROM keyword (required)
        try:
            self._consume(TokenType.FROM)
        except (ParserError, AlpacaSyntaxError):
            token = self._peek()
            raise AlpacaSyntaxError(
                f"Expected 'FROM' keyword at line {token.line}, column {token.column}, but got '{token.lexeme}'",
                hint="SELECT statement must include a FROM clause. Example: SELECT * FROM table_name",
                token=token.lexeme,
                context=f"Line {token.line}, Column {token.column}"
            )

        # Table name and optional alias
        try:
            table_name_token = self._consume(TokenType.IDENTIFIER)
            table_name = table_name_token.value
        except (ParserError, AlpacaSyntaxError):
            token = self._peek()
            raise AlpacaSyntaxError(
                f"Expected table name after FROM at line {token.line}, column {token.column}, but got '{token.lexeme}'",
                hint="After FROM, specify the table name. Example: SELECT * FROM users",
                token=token.lexeme,
                context=f"Line {token.line}, Column {token.column}"
            )

        # Optional table alias
        table_alias = None
        if self._check(TokenType.IDENTIFIER) or self._check(TokenType.AS):
            if self._check(TokenType.AS):
                self._consume(TokenType.AS)
            alias_token = self._consume(TokenType.IDENTIFIER)
            table_alias = alias_token.value

        # Optional JOIN clauses (multiple)
        joins = []
        while (self._check(TokenType.INNER) or self._check(TokenType.LEFT) or
               self._check(TokenType.RIGHT) or self._check(TokenType.FULL) or
               self._check(TokenType.CROSS) or self._check(TokenType.JOIN)):
            join_clause = self._join_clause()
            joins.append(join_clause)

        # For backward compatibility, set join_clause if there's only one join
        join_clause = joins[0] if len(joins) == 1 else None

        # Optional WHERE clause
        where_clause = None
        if self._check(TokenType.WHERE):
            self._consume(TokenType.WHERE)
            where_clause = self._expression()

        # Optional GROUP BY clause
        group_by = None
        if self._check(TokenType.GROUP):
            group_by = self._parse_group_by_clause()

        # Optional ORDER BY clause
        order_by = None
        if self._check(TokenType.ORDER):
            self._consume(TokenType.ORDER)
            self._consume(TokenType.BY)
            col_token = self._consume(TokenType.IDENTIFIER)
            direction = 'ASC'  # Default
            if self._check(TokenType.IDENTIFIER):
                dir_token = self._peek()
                if dir_token.value.upper() in ('ASC', 'DESC'):
                    self._advance()
                    direction = dir_token.value.upper()
            order_by = col_token.value, direction

        # Semicolon (optional)
        if self._check(TokenType.SEMICOLON):
            self._consume(TokenType.SEMICOLON)

        return SelectNode(
            columns=columns,
            table_name=table_name,
            alias=table_alias,
            joins=joins,
            where_clause=where_clause,
            group_by=group_by,
            order_by=order_by,
            join_clause=join_clause,
            aggregates=aggregates
        )

    def _update_statement(self) -> UpdateNode:
        """
        Parse: UPDATE table SET col1=val1, col2=val2 WHERE condition

        Example:
            UPDATE users SET age=26, name='Bob' WHERE id=1
        """
        # UPDATE token already consumed by _statement()

        # Table name
        table_name_token = self._consume(TokenType.IDENTIFIER)
        table_name = table_name_token.value

        # SET keyword
        self._consume(TokenType.SET)

        # Assignments
        assignments = []
        while True:
            col_token = self._consume(TokenType.IDENTIFIER)
            col_name = col_token.value

            self._consume(TokenType.EQUALS)

            value = self._literal()
            assignments.append((col_name, value))

            if not self._check(TokenType.COMMA):
                break
            self._consume(TokenType.COMMA)

        # Optional WHERE clause
        where_clause = None
        if self._check(TokenType.WHERE):
            self._consume(TokenType.WHERE)
            where_clause = self._expression()

        # Semicolon (optional)
        if self._check(TokenType.SEMICOLON):
            self._consume(TokenType.SEMICOLON)

        return UpdateNode(table_name, assignments, where_clause)

    def _delete_statement(self) -> DeleteNode:
        """
        Parse: DELETE FROM table WHERE condition

        Example:
            DELETE FROM users WHERE age < 18
        """
        # DELETE token already consumed by _statement()
        self._consume(TokenType.FROM)

        # Table name
        table_name_token = self._consume(TokenType.IDENTIFIER)
        table_name = table_name_token.value

        # Optional WHERE clause
        where_clause = None
        if self._check(TokenType.WHERE):
            self._consume(TokenType.WHERE)
            where_clause = self._expression()

        # Semicolon (optional)
        if self._check(TokenType.SEMICOLON):
            self._consume(TokenType.SEMICOLON)

        return DeleteNode(table_name, where_clause)

    def _join_clause(self) -> JoinClause:
        """
        Parse join clauses: [INNER|LEFT|RIGHT|FULL|CROSS] JOIN table [AS alias] [ON condition]

        Examples:
            INNER JOIN orders ON users.id = orders.user_id
            LEFT JOIN orders o ON users.id = o.user_id
            CROSS JOIN products
            FULL OUTER JOIN categories c ON p.category_id = c.id
        """
        # Join type
        join_type = 'INNER'  # Default

        if self._check(TokenType.INNER):
            self._consume(TokenType.INNER)
            join_type = 'INNER'
        elif self._check(TokenType.LEFT):
            self._consume(TokenType.LEFT)
            if self._check(TokenType.OUTER):
                self._consume(TokenType.OUTER)
            join_type = 'LEFT'
        elif self._check(TokenType.RIGHT):
            self._consume(TokenType.RIGHT)
            if self._check(TokenType.OUTER):
                self._consume(TokenType.OUTER)
            join_type = 'RIGHT'
        elif self._check(TokenType.FULL):
            self._consume(TokenType.FULL)
            if self._check(TokenType.OUTER):
                self._consume(TokenType.OUTER)
            join_type = 'FULL'
        elif self._check(TokenType.CROSS):
            self._consume(TokenType.CROSS)
            join_type = 'CROSS'

        self._consume(TokenType.JOIN)

        # Table name
        table_token = self._consume(TokenType.IDENTIFIER)
        table_name = table_token.value

        # Optional alias
        alias = None
        if self._check(TokenType.IDENTIFIER) or self._check(TokenType.AS):
            if self._check(TokenType.AS):
                self._consume(TokenType.AS)
            alias_token = self._consume(TokenType.IDENTIFIER)
            alias = alias_token.value

        # ON condition (not for CROSS JOIN)
        condition = None
        if join_type != 'CROSS' and self._check(TokenType.ON):
            self._consume(TokenType.ON)
            condition = self._expression()

        return JoinClause(join_type, table_name, alias, condition)

    def _parse_aggregate_function(self) -> AggregateFunction:
        """
        Parse aggregate function: COUNT(*), SUM(column), etc.

        Examples:
            COUNT(*)
            SUM(salary)
            AVG(age) AS average_age
        """
        # Consume the function name token
        func_token = self._consume_aggregate_function()
        func_name = func_token.value.upper()

        self._consume(TokenType.LEFT_PAREN)

        column = None
        if not self._check(TokenType.STAR):
            col_token = self._consume(TokenType.IDENTIFIER)
            column = col_token.value
        else:
            self._consume(TokenType.STAR)

        self._consume(TokenType.RIGHT_PAREN)

        # Optional AS alias
        alias = None
        if self._check(TokenType.AS):
            self._consume(TokenType.AS)
            alias_token = self._consume(TokenType.IDENTIFIER)
            alias = alias_token.value
        elif self._check(TokenType.IDENTIFIER):
            # Support implicit aliases without the AS keyword
            alias_token = self._consume(TokenType.IDENTIFIER)
            alias = alias_token.value

        return AggregateFunction(func_name, column, alias)

    def _parse_group_by_clause(self) -> GroupByNode:
        """
        Parse GROUP BY clause with optional HAVING.

        Examples:
            GROUP BY department
            GROUP BY department, city HAVING COUNT(*) > 5
        """
        self._consume(TokenType.GROUP)
        self._consume(TokenType.BY)

        # Group columns
        columns = []
        while True:
            col_token = self._consume(TokenType.IDENTIFIER)
            columns.append(col_token.value)

            if not self._check(TokenType.COMMA):
                break
            self._consume(TokenType.COMMA)

        # Optional HAVING clause
        having_clause = None
        if self._check(TokenType.HAVING):
            self._consume(TokenType.HAVING)
            having_clause = self._expression()

        return GroupByNode(columns, having_clause)

    def _consume_aggregate_function(self) -> Token:
        """Consume and return an aggregate function token."""
        if self._check(TokenType.COUNT):
            return self._consume(TokenType.COUNT)
        elif self._check(TokenType.SUM):
            return self._consume(TokenType.SUM)
        elif self._check(TokenType.AVG):
            return self._consume(TokenType.AVG)
        elif self._check(TokenType.MIN):
            return self._consume(TokenType.MIN)
        elif self._check(TokenType.MAX):
            return self._consume(TokenType.MAX)
        else:
            token = self._peek()
            raise AlpacaSyntaxError(
                f"Expected aggregate function (COUNT, SUM, AVG, MIN, MAX) at line {token.line}, but got '{token.lexeme}'",
                hint="Aggregate functions must be: COUNT, SUM, AVG, MIN, or MAX. Example: COUNT(*) or AVG(salary)",
                token=token.lexeme,
                context=f"Line {token.line}, Column {token.column}"
            )

    def _check_aggregate_function(self) -> bool:
        """Check if current token is an aggregate function."""
        return self._check(TokenType.COUNT) or self._check(TokenType.SUM) or \
               self._check(TokenType.AVG) or self._check(TokenType.MIN) or \
               self._check(TokenType.MAX)

    # ==================== Expression Parsing ====================

    def _expression(self) -> BinaryOp:
        """
        Parse expression with AND/OR precedence.

        Grammar:
            expression → or_expr
            or_expr    → and_expr ('OR' and_expr)*
            and_expr   → comparison ('AND' comparison)*
        """
        return self._or_expression()

    def _or_expression(self) -> BinaryOp:
        """Parse OR expressions (lowest precedence)."""
        left = self._and_expression()

        while self._check(TokenType.OR):
            self._consume(TokenType.OR)
            right = self._and_expression()
            left = BinaryOp(left, 'OR', right)

        return left

    def _and_expression(self) -> BinaryOp:
        """Parse AND expressions (higher precedence than OR)."""
        left = self._comparison()

        while self._check(TokenType.AND):
            self._consume(TokenType.AND)
            right = self._comparison()
            left = BinaryOp(left, 'AND', right)

        return left

    def _comparison(self) -> BinaryOp:
        """
        Parse comparison: column op value

        Examples:
            age > 18
            name = 'Alice'
            id != 5
        """
        # Left side can be a column reference or aggregate function
        if self._check_aggregate_function():
            left = self._parse_aggregate_function()
        elif self._check(TokenType.IDENTIFIER):
            left_token = self._consume(TokenType.IDENTIFIER)
            left = ColumnRef(left_token.value)
        else:
            token = self._peek()
            raise AlpacaSyntaxError(
                f"Expected column name or aggregate function at line {token.line}, column {token.column}, but got '{token.lexeme}'",
                hint="Comparisons require a column/aggregate on the left side. Example: COUNT(*) > 5",
                token=token.lexeme,
                context=f"Line {token.line}, Column {token.column}"
            )

        # Operator
        op_token = self._peek()
        if op_token.type in (TokenType.EQUALS, TokenType.NOT_EQUALS,
                             TokenType.LESS_THAN, TokenType.GREATER_THAN,
                             TokenType.LESS_EQUAL, TokenType.GREATER_EQUAL):
            self._advance()
            operator = {
                TokenType.EQUALS: '=',
                TokenType.NOT_EQUALS: '!=',
                TokenType.LESS_THAN: '<',
                TokenType.GREATER_THAN: '>',
                TokenType.LESS_EQUAL: '<=',
                TokenType.GREATER_EQUAL: '>='
            }[op_token.type]
        else:
            raise AlpacaSyntaxError(
                f"Expected comparison operator (=, !=, <, >, <=, >=) at line {op_token.line}, column {op_token.column}, but got '{op_token.lexeme}'",
                hint="Valid comparison operators are: = (equal), != (not equal), < (less), > (greater), <= (less or equal), >= (greater or equal). Example: age > 25",
                token=op_token.lexeme,
                context=f"Line {op_token.line}, Column {op_token.column}"
            )

        # Right side (column reference or literal value)
        if self._check_aggregate_function():
            right = self._parse_aggregate_function()
        elif self._check(TokenType.IDENTIFIER):
            # Column reference
            right_token = self._consume(TokenType.IDENTIFIER)
            right = ColumnRef(right_token.value)
        else:
            # Literal value
            right = Literal(self._literal())

        return BinaryOp(left, operator, right)

    def _literal(self) -> Any:
        """
        Parse literal value.

        Returns actual Python value (int, str, bool, None)
        """
        token = self._peek()

        if token.type == TokenType.INTEGER_LITERAL:
            self._advance()
            return token.value
        elif token.type == TokenType.STRING_LITERAL:
            self._advance()
            return token.value
        elif token.type == TokenType.BOOLEAN_LITERAL:
            self._advance()
            return token.value
        elif token.type == TokenType.NULL:
            self._advance()
            return None
        else:
            raise AlpacaSyntaxError(
                f"Expected literal value (number, string, boolean, NULL) at line {token.line}, column {token.column}, but got '{token.lexeme}'",
                hint="Literal values can be: numbers (25), strings ('text'), booleans (TRUE/FALSE), or NULL. Example: WHERE age = 25",
                token=token.lexeme,
                context=f"Line {token.line}, Column {token.column}"
            )

    # ==================== Helper Methods ====================

    def _check(self, token_type: TokenType) -> bool:
        """Check if current token matches type (without consuming)."""
        if self._is_at_end():
            return False
        return self._peek().type == token_type

    def _consume(self, token_type: TokenType) -> Token:
        """
        Consume current token if it matches type.

        Raises ParseError if mismatch.
        """
        if self._check(token_type):
            return self._advance()

        current = self._peek()
        raise AlpacaSyntaxError(
            f"Expected {token_type.name} at line {current.line}, column {current.column}, but got {current.type.name} ('{current.lexeme}')",
            hint=f"Expected {token_type.name} token here. Check your syntax.",
            token=current.lexeme,
            context=f"Line {current.line}, Column {current.column}"
        )

    def _advance(self) -> Token:
        """Consume and return current token."""
        if not self._is_at_end():
            self.current += 1
        return self._previous()

    def _is_at_end(self) -> bool:
        """Check if at end of token stream."""
        return self._peek().type == TokenType.EOF

    def _peek(self) -> Token:
        """Return current token without consuming."""
        return self.tokens[self.current]

    def _previous(self) -> Token:
        """Return previous token."""
        return self.tokens[self.current - 1]
