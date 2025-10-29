"""
Unit tests for Lexer.
"""

import pytest
from src.query import Lexer, LexerError, TokenType


def test_lexer_keywords():
    """Test that keywords are recognized."""
    lexer = Lexer("SELECT INSERT UPDATE DELETE CREATE DROP")
    tokens = lexer.tokenize()
    
    assert tokens[0].type == TokenType.SELECT
    assert tokens[1].type == TokenType.INSERT
    assert tokens[2].type == TokenType.UPDATE
    assert tokens[3].type == TokenType.DELETE
    assert tokens[4].type == TokenType.CREATE
    assert tokens[5].type == TokenType.DROP


def test_lexer_identifiers():
    """Test identifier tokenization."""
    lexer = Lexer("users table_name column_123")
    tokens = lexer.tokenize()
    
    assert tokens[0].type == TokenType.IDENTIFIER
    assert tokens[0].value == "users"
    
    assert tokens[1].type == TokenType.IDENTIFIER
    assert tokens[1].value == "table_name"


def test_lexer_string_literals():
    """Test string literal parsing."""
    lexer = Lexer("'Alice' \"Bob\" 'O\\'Neil'")
    tokens = lexer.tokenize()
    
    assert tokens[0].type == TokenType.STRING_LITERAL
    assert tokens[0].value == "Alice"
    
    assert tokens[1].type == TokenType.STRING_LITERAL
    assert tokens[1].value == "Bob"
    
    assert tokens[2].type == TokenType.STRING_LITERAL
    assert tokens[2].value == "O'Neil"


def test_lexer_integer_literals():
    """Test integer literal parsing."""
    lexer = Lexer("123 -456 0")
    tokens = lexer.tokenize()
    
    assert tokens[0].type == TokenType.INTEGER_LITERAL
    assert tokens[0].value == 123
    
    assert tokens[1].type == TokenType.INTEGER_LITERAL
    assert tokens[1].value == -456


def test_lexer_operators():
    """Test operator tokenization."""
    lexer = Lexer("= != < > <= >=")
    tokens = lexer.tokenize()
    
    assert tokens[0].type == TokenType.EQUALS
    assert tokens[1].type == TokenType.NOT_EQUALS
    assert tokens[2].type == TokenType.LESS_THAN
    assert tokens[3].type == TokenType.GREATER_THAN
    assert tokens[4].type == TokenType.LESS_EQUAL
    assert tokens[5].type == TokenType.GREATER_EQUAL


def test_lexer_symbols():
    """Test symbol tokenization."""
    lexer = Lexer("* , ; ( )")
    tokens = lexer.tokenize()
    
    assert tokens[0].type == TokenType.STAR
    assert tokens[1].type == TokenType.COMMA
    assert tokens[2].type == TokenType.SEMICOLON
    assert tokens[3].type == TokenType.LEFT_PAREN
    assert tokens[4].type == TokenType.RIGHT_PAREN


def test_lexer_complete_query():
    """Test complete SELECT query."""
    query = "SELECT * FROM users WHERE age > 18"
    lexer = Lexer(query)
    tokens = lexer.tokenize()
    
    assert tokens[0].type == TokenType.SELECT
    assert tokens[1].type == TokenType.STAR
    assert tokens[2].type == TokenType.FROM
    assert tokens[3].type == TokenType.IDENTIFIER
    assert tokens[3].value == "users"
    assert tokens[4].type == TokenType.WHERE
    assert tokens[5].type == TokenType.IDENTIFIER
    assert tokens[5].value == "age"
    assert tokens[6].type == TokenType.GREATER_THAN
    assert tokens[7].type == TokenType.INTEGER_LITERAL
    assert tokens[7].value == 18


def test_lexer_comments():
    """Test comment handling."""
    query = """
    -- This is a comment
    SELECT * FROM users; /* Multi-line
    comment */
    """
    lexer = Lexer(query)
    tokens = lexer.tokenize()
    
    # Should skip comments
    assert tokens[0].type == TokenType.SELECT


def test_lexer_invalid_character():
    """Test error on invalid character."""
    lexer = Lexer("SELECT @ FROM users")
    
    with pytest.raises(LexerError):
        lexer.tokenize()


def test_lexer_unterminated_string():
    """Test error on unterminated string."""
    lexer = Lexer("SELECT 'Alice FROM users")
    
    with pytest.raises(LexerError):
        lexer.tokenize()