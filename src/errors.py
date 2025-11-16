"""
AlpacaDB Error Handling System

Provides structured, user-friendly error messages with hints and context.
"""

from typing import Optional, Any


class AlpacaDBError(Exception):
    """
    Base exception class for all AlpacaDB errors.
    
    Provides structured error messages with:
    - Error type
    - Descriptive message
    - Optional hints
    - Optional token/context
    """
    
    def __init__(
        self,
        message: str,
        hint: Optional[str] = None,
        token: Optional[Any] = None,
        error_type: Optional[str] = None,
        context: Optional[str] = None
    ):
        """
        Initialize an AlpacaDB error.
        
        Args:
            message: Main error message
            hint: Optional helpful hint for the user
            token: Optional token or value that caused the error
            error_type: Optional error type name (defaults to class name)
            context: Optional additional context (line number, query, etc.)
        """
        self.message = message
        self.hint = hint
        self.token = token
        self.error_type = error_type or self.__class__.__name__
        self.context = context
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """Format error message for display."""
        lines = []
        lines.append(f"❌ ERROR [{self.error_type}]: {self.message}")
        
        if self.token is not None:
            token_str = str(self.token) if not isinstance(self.token, str) else f'"{self.token}"'
            lines.append(f"📍 At: {token_str}")
        
        if self.context:
            lines.append(f"📋 Context: {self.context}")
        
        if self.hint:
            lines.append(f"💡 HINT: {self.hint}")
        
        return "\n".join(lines)
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"{self.__class__.__name__}({self.message!r}, hint={self.hint!r})"


# ==================== Parser Errors ====================

class SyntaxError(AlpacaDBError):
    """Syntax error in SQL query."""
    
    def __init__(self, message: str, token: Optional[Any] = None, hint: Optional[str] = None, context: Optional[str] = None):
        super().__init__(message, hint=hint, token=token, error_type="SyntaxError", context=context)


class ParserError(AlpacaDBError):
    """Error during query parsing."""
    
    def __init__(self, message: str, token: Optional[Any] = None, hint: Optional[str] = None, context: Optional[str] = None):
        super().__init__(message, hint=hint, token=token, error_type="ParserError", context=context)


class LexerError(AlpacaDBError):
    """Error during lexical analysis (tokenization)."""
    
    def __init__(self, message: str, token: Optional[Any] = None, hint: Optional[str] = None, context: Optional[str] = None):
        super().__init__(message, hint=hint, token=token, error_type="LexerError", context=context)


# ==================== Optimizer Errors ====================

class OptimizerError(AlpacaDBError):
    """Error during query optimization."""
    
    def __init__(self, message: str, hint: Optional[str] = None, context: Optional[str] = None):
        super().__init__(message, hint=hint, error_type="OptimizerError", context=context)


# ==================== Execution Errors ====================

class ExecutionError(AlpacaDBError):
    """Error during query execution."""
    
    def __init__(self, message: str, hint: Optional[str] = None, context: Optional[str] = None):
        super().__init__(message, hint=hint, error_type="ExecutionError", context=context)


def _normalize_identifier(identifier: Optional[Any]) -> str:
    """Best-effort extraction of the core identifier from a noisy string."""
    if identifier is None:
        return "unknown"
    text = str(identifier).strip()
    lowered = text.lower()
    if lowered.startswith("table ") and "does not exist" in lowered:
        for quote in ('"', "'"):
            first = text.find(quote)
            second = text.find(quote, first + 1) if first != -1 else -1
            if first != -1 and second != -1:
                return text[first + 1:second]
        # Fall back to the word after TABLE
        parts = text.split()
        if len(parts) >= 2:
            return parts[1].strip("'\"")
    return text


class TableNotFoundError(AlpacaDBError):
    """Table does not exist."""
    
    def __init__(self, table_name: str, hint: Optional[str] = None):
        normalized_name = _normalize_identifier(table_name)
        message = f'Table "{normalized_name}" does not exist.'
        if not hint:
            hint = f'Use \\tables to view all available tables.'
        super().__init__(message, hint=hint, token=normalized_name, error_type="TableNotFoundError")


class ColumnNotFoundError(AlpacaDBError):
    """Column does not exist."""
    
    def __init__(self, column_name: str, table_name: Optional[str] = None, hint: Optional[str] = None):
        if table_name:
            message = f'Column "{column_name}" does not exist in table "{table_name}".'
        else:
            message = f'Column "{column_name}" does not exist.'
        
        if not hint:
            if table_name:
                hint = f'Use \\schema {table_name} to view the table structure.'
            else:
                hint = 'Use \\schema <table> to view table structure.'
        
        super().__init__(message, hint=hint, token=column_name, error_type="ColumnNotFoundError")


class IndexError(AlpacaDBError):
    """Error related to indexes."""
    
    def __init__(self, message: str, index_name: Optional[str] = None, hint: Optional[str] = None):
        super().__init__(message, hint=hint, token=index_name, error_type="IndexError")


class IndexNotFoundError(IndexError):
    """Index does not exist."""
    
    def __init__(self, index_name: str, hint: Optional[str] = None):
        message = f'Index "{index_name}" does not exist.'
        if not hint:
            hint = 'Use \\indexes to view all available indexes.'
        super().__init__(message, index_name=index_name, hint=hint)


class DuplicateTableError(AlpacaDBError):
    """Table already exists."""
    
    def __init__(self, table_name: str, hint: Optional[str] = None):
        message = f'Table "{table_name}" already exists.'
        if not hint:
            hint = f'Use DROP TABLE {table_name} to remove it first, or choose a different name.'
        super().__init__(message, hint=hint, token=table_name, error_type="DuplicateTableError")


class DuplicateIndexError(IndexError):
    """Index already exists."""
    
    def __init__(self, index_name: str, hint: Optional[str] = None):
        message = f'Index "{index_name}" already exists.'
        if not hint:
            hint = f'Use DROP INDEX {index_name} to remove it first, or choose a different name.'
        super().__init__(message, index_name=index_name, hint=hint)


class InvalidSchemaError(AlpacaDBError):
    """Invalid table or column schema."""
    
    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__(message, hint=hint, error_type="InvalidSchemaError")


class TypeMismatchError(AlpacaDBError):
    """Type mismatch in operation."""
    
    def __init__(self, message: str, expected_type: Optional[str] = None, actual_type: Optional[str] = None, hint: Optional[str] = None):
        if expected_type and actual_type:
            message = f"{message} (Expected: {expected_type}, Got: {actual_type})"
        super().__init__(message, hint=hint, error_type="TypeMismatchError")


class DivisionByZeroError(ExecutionError):
    """Division by zero error."""
    
    def __init__(self, hint: Optional[str] = None):
        message = "Division by zero is not allowed."
        if not hint:
            hint = "Check your WHERE clause or use NULLIF to handle zero values."
        super().__init__(message, hint=hint, error_type="DivisionByZeroError")


class StorageError(AlpacaDBError):
    """Error related to storage operations."""
    
    def __init__(self, message: str, hint: Optional[str] = None, context: Optional[str] = None):
        super().__init__(message, hint=hint, error_type="StorageError", context=context)


class CorruptedPageError(StorageError):
    """Page is corrupted."""
    
    def __init__(self, page_id: int, hint: Optional[str] = None):
        message = f"Page {page_id} is corrupted and cannot be read."
        if not hint:
            hint = "The database file may be corrupted. Consider restoring from backup."
        super().__init__(message, hint=hint, context=f"Page ID: {page_id}")


# ==================== Internal Errors ====================

class InternalError(AlpacaDBError):
    """Internal error (should not happen in normal operation)."""
    
    def __init__(self, message: str, hint: Optional[str] = None):
        if not hint:
            hint = "This is an internal error. Please report this issue."
        super().__init__(message, hint=hint, error_type="InternalError")

