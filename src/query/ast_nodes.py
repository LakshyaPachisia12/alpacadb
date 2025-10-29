"""
Abstract Syntax Tree (AST) node definitions.

Each node represents a parsed SQL command structure.
"""

from typing import List, Optional, Any
from dataclasses import dataclass


@dataclass
class Column:
    """Represents a column definition in CREATE TABLE."""
    name: str
    data_type: str  # 'INT', 'STRING', 'BOOLEAN'
    is_primary_key: bool = False
    nullable: bool = True
    
    def __repr__(self):
        pk = " PRIMARY KEY" if self.is_primary_key else ""
        null = " NOT NULL" if not self.nullable else ""
        return f"{self.name} {self.data_type}{pk}{null}"


# Base class for all AST nodes
class ASTNode:
    """Base class for all AST nodes."""
    pass


# ==================== DDL Nodes ====================

@dataclass
class CreateTableNode(ASTNode):
    """
    Represents: CREATE TABLE table_name (col1 TYPE, col2 TYPE, ...)
    
    Example:
        CREATE TABLE users (id INT PRIMARY KEY, name STRING, age INT)
    """
    table_name: str
    columns: List[Column]
    
    def __repr__(self):
        cols = ', '.join(str(c) for c in self.columns)
        return f"CreateTableNode(table={self.table_name}, columns=[{cols}])"


@dataclass
class DropTableNode(ASTNode):
    """
    Represents: DROP TABLE table_name
    
    Example:
        DROP TABLE users
    """
    table_name: str
    
    def __repr__(self):
        return f"DropTableNode(table={self.table_name})"


@dataclass
class CreateIndexNode(ASTNode):
    """
    Represents: CREATE INDEX index_name ON table_name (column)
    
    Example:
        CREATE INDEX idx_age ON users (age)
    """
    index_name: str
    table_name: str
    column_name: str
    
    def __repr__(self):
        return f"CreateIndexNode(index={self.index_name}, table={self.table_name}, column={self.column_name})"


@dataclass
class DropIndexNode(ASTNode):
    """
    Represents: DROP INDEX index_name ON table_name
    
    Example:
        DROP INDEX idx_age ON users
    """
    index_name: str
    table_name: str
    
    def __repr__(self):
        return f"DropIndexNode(index={self.index_name}, table={self.table_name})"


# ==================== DML Nodes ====================

@dataclass
class InsertNode(ASTNode):
    """
    Represents: INSERT INTO table_name VALUES (val1, val2, ...)
    
    Example:
        INSERT INTO users VALUES (1, 'Alice', 25)
    """
    table_name: str
    values: List[Any]
    
    def __repr__(self):
        vals = ', '.join(repr(v) for v in self.values)
        return f"InsertNode(table={self.table_name}, values=[{vals}])"


@dataclass
class UpdateNode(ASTNode):
    """
    Represents: UPDATE table_name SET col1=val1, col2=val2 WHERE condition
    
    Example:
        UPDATE users SET age=26 WHERE id=1
    """
    table_name: str
    assignments: List[tuple]  # [(column, value), ...]
    where_clause: Optional['BinaryOp'] = None
    
    def __repr__(self):
        assigns = ', '.join(f"{col}={val}" for col, val in self.assignments)
        where = f" WHERE {self.where_clause}" if self.where_clause else ""
        return f"UpdateNode(table={self.table_name}, set=[{assigns}]{where})"


@dataclass
class DeleteNode(ASTNode):
    """
    Represents: DELETE FROM table_name WHERE condition
    
    Example:
        DELETE FROM users WHERE age < 18
    """
    table_name: str
    where_clause: Optional['BinaryOp'] = None
    
    def __repr__(self):
        where = f" WHERE {self.where_clause}" if self.where_clause else ""
        return f"DeleteNode(table={self.table_name}{where})"


@dataclass
class SelectNode(ASTNode):
    """
    Represents: SELECT columns FROM table WHERE condition ORDER BY column
    
    Example:
        SELECT id, name FROM users WHERE age > 18 ORDER BY name ASC
    """
    columns: List[str]  # ['*'] or ['id', 'name']
    table_name: str
    where_clause: Optional['BinaryOp'] = None
    order_by: Optional[tuple] = None  # (column, 'ASC'|'DESC')
    join_clause: Optional['JoinClause'] = None
    
    def __repr__(self):
        cols = ', '.join(self.columns)
        where = f" WHERE {self.where_clause}" if self.where_clause else ""
        order = f" ORDER BY {self.order_by[0]} {self.order_by[1]}" if self.order_by else ""
        join = f" JOIN {self.join_clause}" if self.join_clause else ""
        return f"SelectNode(columns=[{cols}], table={self.table_name}{where}{order}{join})"


# ==================== Expression Nodes ====================

@dataclass
class BinaryOp(ASTNode):
    """
    Represents binary operations: left op right
    
    Examples:
        age > 18
        name = 'Alice'
        (age > 18) AND (name = 'Alice')
    """
    left: Any  # Can be Column, Literal, or another BinaryOp
    operator: str  # '=', '>', '<', '>=', '<=', '!=', 'AND', 'OR'
    right: Any
    
    def __repr__(self):
        return f"({self.left} {self.operator} {self.right})"


@dataclass
class ColumnRef:
    """Reference to a column in a query."""
    name: str
    
    def __repr__(self):
        return f"Column({self.name})"


@dataclass
class Literal:
    """Literal value (integer, string, boolean, null)."""
    value: Any
    
    def __repr__(self):
        if isinstance(self.value, str):
            return f"'{self.value}'"
        return str(self.value)


@dataclass
class JoinClause:
    """
    Represents: INNER JOIN table ON condition
    
    Example:
        INNER JOIN orders ON users.id = orders.user_id
    """
    join_type: str  # 'INNER' (only type supported in v1.0)
    table_name: str
    on_condition: BinaryOp
    
    def __repr__(self):
        return f"{self.join_type} JOIN {self.table_name} ON {self.on_condition}"


# ==================== Transaction Nodes ====================

@dataclass
class TransactionNode(ASTNode):
    """
    Represents transaction commands: BEGIN, COMMIT, ROLLBACK
    """
    command: str  # 'BEGIN', 'COMMIT', or 'ROLLBACK'
    
    def __repr__(self):
        return f"TransactionNode({self.command})"


# ==================== Security Nodes (Sprint 7) ====================

@dataclass
class GrantNode(ASTNode):
    """Represents: GRANT privilege ON table TO user"""
    privilege: str
    table_name: str
    user_name: str


@dataclass
class RevokeNode(ASTNode):
    """Represents: REVOKE privilege ON table FROM user"""
    privilege: str
    table_name: str
    user_name: str 