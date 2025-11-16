"""
Lexer for AlpacaDB query language.

Converts raw SQL-like text into a stream of tokens.
"""

from typing import List
from .tokens import Token, TokenType, KEYWORDS
from ..errors import LexerError


class Lexer:
    """
    Lexical analyzer for AlpacaDB queries.
    
    Converts text like "SELECT * FROM users" into tokens:
    [SELECT, STAR, FROM, IDENTIFIER(users)]
    """
    
    def __init__(self, source: str):
        """
        Initialize lexer with source code.
        
        Args:
            source: SQL query string
        """
        self.source = source
        self.tokens: List[Token] = []
        self.start = 0      # Start of current lexeme
        self.current = 0    # Current character position
        self.line = 1       # Current line number
        self.column = 1     # Current column number
    
    def tokenize(self) -> List[Token]:
        """
        Tokenize the entire source code.
        
        Returns:
            List of tokens (including EOF token at end)
            
        Raises:
            LexerError: If invalid syntax encountered
        """
        while not self._is_at_end():
            self.start = self.current
            self._scan_token()
        
        # Add EOF token
        self.tokens.append(Token(TokenType.EOF, '', line=self.line, column=self.column))
        return self.tokens
    
    def _scan_token(self):
        """Scan and classify next token."""
        char = self._advance()
        
        # Skip whitespace
        if char in ' \t\r':
            self.column += 1
            return
        
        # Newline
        if char == '\n':
            self.line += 1
            self.column = 1
            return
        
        # Comments
        if char == '-' and self._peek() == '-':
            # Single-line comment: -- comment
            while self._peek() != '\n' and not self._is_at_end():
                self._advance()
            return
        
        if char == '/' and self._peek() == '*':
            # Multi-line comment: /* comment */
            self._advance()  # consume *
            while not self._is_at_end():
                if self._peek() == '*' and self._peek_next() == '/':
                    self._advance()  # consume *
                    self._advance()  # consume /
                    break
                if self._peek() == '\n':
                    self.line += 1
                    self.column = 1
                self._advance()
            return
        
        # Single-character tokens
        if char == '*':
            self._add_token(TokenType.STAR)
        elif char == ',':
            self._add_token(TokenType.COMMA)
        elif char == ';':
            self._add_token(TokenType.SEMICOLON)
        elif char == '(':
            self._add_token(TokenType.LEFT_PAREN)
        elif char == ')':
            self._add_token(TokenType.RIGHT_PAREN)
        
        # Operators
        elif char == '=':
            self._add_token(TokenType.EQUALS)
        elif char == '!':
            if self._match('='):
                self._add_token(TokenType.NOT_EQUALS)
            else:
                raise LexerError(
                    f"Unexpected character '!' at line {self.line}, column {self.column}",
                    hint="Did you mean '!=' (not equal)?",
                    token="!",
                    context=f"Line {self.line}, Column {self.column}"
                )
        elif char == '<':
            if self._match('='):
                self._add_token(TokenType.LESS_EQUAL)
            else:
                self._add_token(TokenType.LESS_THAN)
        elif char == '>':
            if self._match('='):
                self._add_token(TokenType.GREATER_EQUAL)
            else:
                self._add_token(TokenType.GREATER_THAN)
        
        # String literals
        elif char in ('"', "'"):
            self._string_literal(char)
        
        # Number literals
        elif char.isdigit() or (char == '-' and self._peek().isdigit()):
            self._number_literal()
        
        # Identifiers and keywords
        elif char.isalpha() or char == '_':
            self._identifier()
        
        else:
            raise LexerError(
                f"Unexpected character '{char}' at line {self.line}, column {self.column}",
                hint="Invalid character in SQL query. Check for typos or unsupported characters.",
                token=char,
                context=f"Line {self.line}, Column {self.column}"
            )
    
    def _string_literal(self, quote_char: str):
        """Parse string literal enclosed in quotes."""
        value = ""
        
        while self._peek() != quote_char and not self._is_at_end():
            if self._peek() == '\n':
                self.line += 1
                self.column = 1
            if self._peek() == '\\':  # Escape sequences
                self._advance()
                next_char = self._advance()
                if next_char == 'n':
                    value += '\n'
                elif next_char == 't':
                    value += '\t'
                elif next_char == quote_char:
                    value += quote_char
                elif next_char == '\\':
                    value += '\\'
                else:
                    value += next_char
            else:
                value += self._advance()
        
        if self._is_at_end():
            raise LexerError(
                f"Unterminated string literal starting at line {self.line}",
                hint=f"String must be closed with '{quote_char}'. Did you forget the closing quote?",
                token=quote_char,
                context=f"Line {self.line}"
            )
        
        # Consume closing quote
        self._advance()
        
        lexeme = self.source[self.start:self.current]
        self._add_token(TokenType.STRING_LITERAL, value)
    
    def _number_literal(self):
        """Parse integer literal."""
        while self._peek().isdigit():
            self._advance()
        
        lexeme = self.source[self.start:self.current]
        value = int(lexeme)
        self._add_token(TokenType.INTEGER_LITERAL, value)
    
    def _identifier(self):
        """Parse identifier or keyword (including qualified names like table.column)."""
        while self._peek().isalnum() or self._peek() in ('_', '.'):
            self._advance()
        
        lexeme = self.source[self.start:self.current]
        lexeme_upper = lexeme.upper()
        
        # Check if keyword
        token_type = KEYWORDS.get(lexeme_upper, TokenType.IDENTIFIER)
        
        # Special handling for boolean literals
        if token_type == TokenType.BOOLEAN_LITERAL:
            value = (lexeme_upper == 'TRUE')
            self._add_token(token_type, value)
        else:
            self._add_token(token_type, lexeme)
    
    def _match(self, expected: str) -> bool:
        """Match and consume next character if it equals expected."""
        if self._is_at_end():
            return False
        if self.source[self.current] != expected:
            return False
        self.current += 1
        self.column += 1
        return True
    
    def _advance(self) -> str:
        """Consume and return current character."""
        char = self.source[self.current]
        self.current += 1
        self.column += 1
        return char
    
    def _peek(self) -> str:
        """Return current character without consuming."""
        if self._is_at_end():
            return '\0'
        return self.source[self.current]
    
    def _peek_next(self) -> str:
        """Return next character without consuming."""
        if self.current + 1 >= len(self.source):
            return '\0'
        return self.source[self.current + 1]
    
    def _is_at_end(self) -> bool:
        """Check if at end of source."""
        return self.current >= len(self.source)
    
    def _add_token(self, token_type: TokenType, value=None):
        """Add token to list."""
        lexeme = self.source[self.start:self.current]
        token = Token(token_type, lexeme, value, self.line, self.column - len(lexeme))
        self.tokens.append(token)