# 🦙 AlpacaDB Error Handling Examples

## Error System Overview

AlpacaDB now has a comprehensive, user-friendly error handling system with structured error messages, helpful hints, and context information.

## Error Categories

### 1. **Syntax Errors** (Lexer/Parser)
- Invalid SQL syntax
- Missing keywords
- Unexpected tokens

### 2. **Execution Errors**
- Table not found
- Column not found
- Type mismatches
- Invalid operations

### 3. **Optimizer Errors**
- Invalid query plans
- Table validation errors

## Example Error Messages

### Syntax Error Example
```sql
SELECT * users;
```
**Output:**
```
❌ ERROR [SyntaxError]: Expected 'FROM' keyword at line 1, column 14, but got 'users'
📍 At: "users"
📋 Context: Line 1, Column 14
💡 HINT: SELECT statement must include a FROM clause. Example: SELECT * FROM table_name
```

### Table Not Found Example
```sql
SELECT * FROM nonexistent;
```
**Output:**
```
❌ ERROR [TableNotFoundError]: Table "nonexistent" does not exist.
📍 At: "nonexistent"
💡 HINT: Use \tables to view all available tables.
```

### Column Not Found Example
```sql
SELECT ageee FROM users;
```
**Output:**
```
❌ ERROR [ColumnNotFoundError]: Column "ageee" does not exist.
📍 At: "ageee"
💡 HINT: Use \schema users to view the table structure.
```

### Missing FROM Clause Example
```sql
SELECT * WHERE age > 25;
```
**Output:**
```
❌ ERROR [SyntaxError]: Expected 'FROM' keyword at line 1, column 9, but got 'WHERE'
📍 At: "WHERE"
📋 Context: Line 1, Column 9
💡 HINT: SELECT statement must include a FROM clause. Example: SELECT * FROM table_name
```

### Invalid Operator Example
```sql
SELECT * FROM users WHERE age <> 25;
```
**Output:**
```
❌ ERROR [ExecutionError]: Unknown operator: <>
💡 HINT: Supported operators: =, !=, <, >, <=, >=, AND, OR. Got: <>
```

### Invalid Data Type Example
```sql
CREATE TABLE users (name VARCHAR);
```
**Output:**
```
❌ ERROR [SyntaxError]: Expected data type (INT, STRING, BOOLEAN) at line 1, but got 'VARCHAR'
📍 At: "VARCHAR"
📋 Context: Line 1, Column 23
💡 HINT: Column definitions require a data type after the column name. Valid types: INT, STRING, BOOLEAN.
```

### Index Creation on Non-existent Column
```sql
CREATE INDEX idx_age ON users (ageee);
```
**Output:**
```
❌ ERROR [ColumnNotFoundError]: Column "ageee" does not exist in table "users".
📍 At: "ageee"
💡 HINT: Use \schema users to view the table structure.
```

## Error Features

### 1. **Structured Format**
- ❌ Error icon
- Error type in brackets
- Clear message
- Location (token/column)
- Context (line number)
- Helpful hint

### 2. **Context Information**
- Line numbers
- Column positions
- Offending tokens
- Available alternatives

### 3. **Helpful Hints**
- Suggestions for fixing the error
- Examples of correct syntax
- Commands to check database state
- Available options

## Error Class Hierarchy

```
AlpacaDBError (base class)
├── SyntaxError
├── ParserError
├── LexerError
├── OptimizerError
├── ExecutionError
│   ├── TableNotFoundError
│   ├── ColumnNotFoundError
│   ├── TypeMismatchError
│   ├── DivisionByZeroError
│   └── ...
├── IndexError
│   ├── IndexNotFoundError
│   └── ...
└── InternalError
```

## Usage in Code

```python
from src.errors import TableNotFoundError, ColumnNotFoundError

# Raise a table not found error
if not table_exists:
    raise TableNotFoundError("users")

# Raise a column not found error
if not column_exists:
    raise ColumnNotFoundError("age", "users")
```

## CLI Integration

The CLI automatically catches all `AlpacaDBError` exceptions and displays them with proper formatting:

```python
try:
    result = executor.execute(ast)
except AlpacaDBError as e:
    print(str(e))  # Automatically formatted with hints
except Exception as e:
    print("❌ ERROR [Internal]: An unexpected error occurred")
    print("💡 HINT: This may be a bug. Please report this issue.")
```

## Testing

All error classes can be tested:

```python
from src.errors import *

# Test table not found
e = TableNotFoundError("users")
print(str(e))

# Test column not found
e = ColumnNotFoundError("age", "users")
print(str(e))

# Test custom error
e = SyntaxError("Unexpected token", token="FROM", hint="Did you forget SELECT?")
print(str(e))
```

