"""
Parser for AlpacaDB query language.

Converts tokens into Abstract Syntax Tree (AST).
Uses recursive descent parsing.
"""

from typing import List
from .tokens import Token, TokenType
from .ast_nodes import *


class ParseError(Exception):
    """Raised when parser encounters syntax error."""
    pass


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
        except ParseError as e:
            raise e
        except Exception as e:
            current_token = self._peek()
            raise ParseError(
                f"Unexpected error at line {current_token.line}, "
                f"column {current_token.column}: {e}"
            )
    
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
            raise ParseError(
                f"Unexpected token '{token.lexeme}' at line {token.line}, "
                f"column {token.column}. Expected statement keyword "
                f"(CREATE, SELECT, INSERT, etc.)"
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
            raise ParseError("Expected 'TABLE' or 'INDEX' after CREATE")
            
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
            raise ParseError("Expected 'TABLE' or 'INDEX' after DROP")
            
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
            raise ParseError(f"Table '{table_name}' cannot have multiple PRIMARY KEY columns")
        
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
            raise ParseError(
                f"Expected data type (INT, STRING, BOOLEAN) at line {self._peek().line}"
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
        Parse: SELECT columns FROM table [WHERE condition] [ORDER BY column]
        
        Examples:
            SELECT * FROM users
            SELECT id, name FROM users WHERE age > 18
            SELECT * FROM users ORDER BY name ASC
        """
        # SELECT token already consumed by _statement()
        
        # Columns (* or col1, col2, ...)
        columns = []
        if self._check(TokenType.STAR):
            self._consume(TokenType.STAR)
            columns = ['*']
        else:
            while True:
                col_token = self._consume(TokenType.IDENTIFIER)
                columns.append(col_token.value)
                
                if not self._check(TokenType.COMMA):
                    break
                self._consume(TokenType.COMMA)
        
        # FROM keyword
        self._consume(TokenType.FROM)
        
        # Table name
        table_name_token = self._consume(TokenType.IDENTIFIER)
        table_name = table_name_token.value
        
        # Optional WHERE clause
        where_clause = None
        if self._check(TokenType.WHERE):
            self._consume(TokenType.WHERE)
            where_clause = self._expression()
        
        # Optional JOIN clause
        join_clause = None
        if self._check(TokenType.INNER) or self._check(TokenType.JOIN):
            join_clause = self._join_clause()
        
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
            order_by = (col_token.value, direction)
        
        # Semicolon (optional)
        if self._check(TokenType.SEMICOLON):
            self._consume(TokenType.SEMICOLON)
        
        return SelectNode(columns, table_name, where_clause, order_by, join_clause)
    
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
        Parse: INNER JOIN table ON condition
        
        Example:
            INNER JOIN orders ON users.id = orders.user_id
        """
        # INNER keyword (optional)
        if self._check(TokenType.INNER):
            self._consume(TokenType.INNER)
        
        self._consume(TokenType.JOIN)
        
        # Table name
        table_token = self._consume(TokenType.IDENTIFIER)
        table_name = table_token.value
        
        # ON keyword
        self._consume(TokenType.ON)
        
        # Join condition
        condition = self._expression()
        
        return JoinClause('INNER', table_name, condition)
    
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
        # Left side (column reference)
        if not self._check(TokenType.IDENTIFIER):
            raise ParseError(f"Expected column name at line {self._peek().line}")
        
        left_token = self._consume(TokenType.IDENTIFIER)
        left = ColumnRef(left_token.value)
        
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
            raise ParseError(
                f"Expected comparison operator (=, !=, <, >, <=, >=) at line {op_token.line}"
            )
        
        # Right side (literal value)
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
            raise ParseError(
                f"Expected literal value at line {token.line}, got '{token.lexeme}'"
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
        raise ParseError(
            f"Expected {token_type.name} at line {current.line}, column {current.column}, "
            f"but got {current.type.name} ('{current.lexeme}')"
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