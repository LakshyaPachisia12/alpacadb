# src/query/tokens.py

"""
Token definitions for AlpacaDB query language.

Tokens are the atomic units produced by the lexer.
Each token has a type and an optional value.
"""

from enum import Enum, auto
from typing import Any, Optional


class TokenType(Enum):
    """
    All possible token types in AlpacaDB query language.
    
    Keywords (SQL commands)
    """
    # DDL Keywords
    CREATE = auto()
    DROP = auto()
    TABLE = auto()
    INDEX = auto()
    USING = auto()  # For CREATE INDEX ... USING
    
    # DML Keywords
    SELECT = auto()
    INSERT = auto()
    UPDATE = auto()
    DELETE = auto()
    EXPLAIN = auto()
    
    # Aggregate Functions
    COUNT = auto()
    SUM = auto()
    AVG = auto()
    MIN = auto()
    MAX = auto()
    
    # Grouping Keywords
    GROUP = auto()
    HAVING = auto()
    
    # Aggregate Functions
    COUNT = auto()
    SUM = auto()
    AVG = auto()
    MIN = auto()
    MAX = auto()
    
    # Grouping Keywords
    GROUP = auto()
    HAVING = auto()
    
    # Clauses
    FROM = auto()
    WHERE = auto()
    INTO = auto()
    VALUES = auto()
    SET = auto()
    AS = auto()
    ORDER = auto()
    BY = auto()
    JOIN = auto()
    INNER = auto()
    LEFT = auto()
    RIGHT = auto()
    FULL = auto()
    OUTER = auto()
    CROSS = auto()
    ON = auto()
    
    # Transaction Keywords
    BEGIN = auto()
    COMMIT = auto()
    ROLLBACK = auto()
    
    # Security Keywords
    GRANT = auto()
    REVOKE = auto()
    
    # Data Types
    INT = auto()
    STRING = auto()
    BOOLEAN = auto()
    
    # Constraints
    PRIMARY = auto()
    KEY = auto()
    
    # Operators
    EQUALS = auto()           # =
    NOT_EQUALS = auto()       # !=
    LESS_THAN = auto()        # 
    GREATER_THAN = auto()     # >
    LESS_EQUAL = auto()       # <=
    GREATER_EQUAL = auto()    # >=
    
    # Logical Operators
    AND = auto()
    OR = auto()
    NOT = auto()
    
    # Symbols
    STAR = auto()             # *
    COMMA = auto()            # ,
    SEMICOLON = auto()        # ;
    LEFT_PAREN = auto()       # (
    RIGHT_PAREN = auto()      # )
    
    # Literals
    IDENTIFIER = auto()       # table_name, column_name
    INTEGER_LITERAL = auto()  # 123, -456
    STRING_LITERAL = auto()   # 'Alice', "Bob"
    BOOLEAN_LITERAL = auto()  # TRUE, FALSE
    NULL = auto()             # NULL
    
    # Special
    EOF = auto()              # End of input
    UNKNOWN = auto()          # Invalid token


class Token:
    """
    Represents a single token from the lexer.
    
    Examples:
        Token(TokenType.SELECT, "SELECT")
        Token(TokenType.IDENTIFIER, "users")
        Token(TokenType.INTEGER_LITERAL, "123", value=123)
    """
    
    def __init__(self, token_type: TokenType, lexeme: str, value: Optional[Any] = None,
                 line: int = 1, column: int = 1):
        """
        Create a new token.
        
        Args:
            token_type: Type of token
            lexeme: Raw string from source
            value: Parsed value (for literals)
            line: Line number in source
            column: Column number in source
        """
        self.type = token_type
        self.lexeme = lexeme
        self.value = value if value is not None else lexeme
        self.line = line
        self.column = column
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        if self.value != self.lexeme:
            return f"Token({self.type.name}, '{self.lexeme}', value={self.value}, line={self.line}, col={self.column})"
        return f"Token({self.type.name}, '{self.lexeme}', line={self.line}, col={self.column})"
    
    def __eq__(self, other) -> bool:
        """Check equality (for testing)."""
        if not isinstance(other, Token):
            return False
        return self.type == other.type and self.value == other.value


# Keyword mapping (case-insensitive)
KEYWORDS = {
    'CREATE': TokenType.CREATE,
    'DROP': TokenType.DROP,
    'TABLE': TokenType.TABLE,
    'INDEX': TokenType.INDEX,
    'USING': TokenType.USING,
    'SELECT': TokenType.SELECT,
    'INSERT': TokenType.INSERT,
    'UPDATE': TokenType.UPDATE,
    'DELETE': TokenType.DELETE,
    'EXPLAIN': TokenType.EXPLAIN,
    'COUNT': TokenType.COUNT,
    'SUM': TokenType.SUM,
    'AVG': TokenType.AVG,
    'MIN': TokenType.MIN,
    'MAX': TokenType.MAX,
    'GROUP': TokenType.GROUP,
    'HAVING': TokenType.HAVING,
    'FROM': TokenType.FROM,
    'WHERE': TokenType.WHERE,
    'INTO': TokenType.INTO,
    'VALUES': TokenType.VALUES,
    'SET': TokenType.SET,
    'AS': TokenType.AS,
    'ORDER': TokenType.ORDER,
    'BY': TokenType.BY,
    'JOIN': TokenType.JOIN,
    'INNER': TokenType.INNER,
    'LEFT': TokenType.LEFT,
    'RIGHT': TokenType.RIGHT,
    'FULL': TokenType.FULL,
    'OUTER': TokenType.OUTER,
    'CROSS': TokenType.CROSS,
    'ON': TokenType.ON,
    'BEGIN': TokenType.BEGIN,
    'COMMIT': TokenType.COMMIT,
    'ROLLBACK': TokenType.ROLLBACK,
    'GRANT': TokenType.GRANT,
    'REVOKE': TokenType.REVOKE,
    'INT': TokenType.INT,
    'STRING': TokenType.STRING,
    'BOOLEAN': TokenType.BOOLEAN,
    'PRIMARY': TokenType.PRIMARY,
    'KEY': TokenType.KEY,
    'AND': TokenType.AND,
    'OR': TokenType.OR,
    'NOT': TokenType.NOT,
    'TRUE': TokenType.BOOLEAN_LITERAL,
    'FALSE': TokenType.BOOLEAN_LITERAL,
    'NULL': TokenType.NULL,
}