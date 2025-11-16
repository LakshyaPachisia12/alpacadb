# 🦙 AlpacaDB Sample Queries

## Try These Queries to See Error Handling in Action!

### ✅ **Working Queries** (These should work fine)

```sql
-- List tables
\tables

-- Show table schema
\schema sales

-- Show all indexes
\indexes

-- Database information
\info

-- Create a table
CREATE TABLE students (id INT PRIMARY KEY, name STRING, age INT);

-- Insert data
INSERT INTO students VALUES (1, 'Alice', 20);
INSERT INTO students VALUES (2, 'Bob', 21);
INSERT INTO students VALUES (3, 'Charlie', 22);

-- Simple SELECT
SELECT * FROM students;

-- SELECT with WHERE
SELECT * FROM students WHERE age > 20;

-- Create an index
CREATE INDEX idx_age ON students (age);

-- Query with index (should be fast!)
SELECT * FROM students WHERE age = 21;

-- Show query plan
EXPLAIN SELECT * FROM students WHERE age = 21;
```

---

### ❌ **Error Examples** (These will show beautiful error messages!)

#### 1. **Table Not Found**
```sql
SELECT * FROM nonexistent;
```
**Expected Output:**
```
❌ ERROR [TableNotFoundError]: Table "nonexistent" does not exist.
📍 At: "nonexistent"
💡 HINT: Use \tables to view all available tables.
```

#### 2. **Missing FROM Clause**
```sql
SELECT * WHERE age > 20;
```
**Expected Output:**
```
❌ ERROR [SyntaxError]: Expected 'FROM' keyword at line 1, column 9, but got 'WHERE'
📍 At: "WHERE"
📋 Context: Line 1, Column 9
💡 HINT: SELECT statement must include a FROM clause. Example: SELECT * FROM table_name
```

#### 3. **Column Not Found**
```sql
SELECT ageee FROM students;
```
**Expected Output:**
```
❌ ERROR [ColumnNotFoundError]: Column "ageee" does not exist.
📍 At: "ageee"
💡 HINT: Use \schema students to view the table structure.
```

#### 4. **Invalid Data Type**
```sql
CREATE TABLE test (name VARCHAR);
```
**Expected Output:**
```
❌ ERROR [SyntaxError]: Expected data type (INT, STRING, BOOLEAN) at line 1, but got 'VARCHAR'
📍 At: "VARCHAR"
📋 Context: Line 1, Column 23
💡 HINT: Column definitions require a data type after the column name. Valid types: INT, STRING, BOOLEAN.
```

#### 5. **Unexpected Token**
```sql
SELECT * users;
```
**Expected Output:**
```
❌ ERROR [SyntaxError]: Expected 'FROM' keyword at line 1, column 9, but got 'users'
📍 At: "users"
📋 Context: Line 1, Column 9
💡 HINT: SELECT statement must include a FROM clause. Example: SELECT * FROM table_name
```

#### 6. **Invalid Operator**
```sql
SELECT * FROM students WHERE age <> 20;
```
**Expected Output:**
```
❌ ERROR [ExecutionError]: Unknown operator: <>
💡 HINT: Supported operators: =, !=, <, >, <=, >=, AND, OR. Got: <>
```

#### 7. **Missing CREATE Keyword**
```sql
TABLE users (id INT);
```
**Expected Output:**
```
❌ ERROR [SyntaxError]: Unexpected token 'TABLE' at line 1, column 1
📍 At: "TABLE"
📋 Context: Line 1, Column 1
💡 HINT: Expected a statement keyword (CREATE, SELECT, INSERT, UPDATE, DELETE, DROP, BEGIN, COMMIT, ROLLBACK).
```

#### 8. **Unterminated String**
```sql
INSERT INTO students VALUES (1, 'Alice, 20);
```
**Expected Output:**
```
❌ ERROR [LexerError]: Unterminated string literal starting at line 1
📍 At: "'"
📋 Context: Line 1
💡 HINT: String must be closed with '''. Did you forget the closing quote?
```

#### 9. **Invalid CREATE Statement**
```sql
CREATE users (id INT);
```
**Expected Output:**
```
❌ ERROR [SyntaxError]: Expected 'TABLE' or 'INDEX' after CREATE, but got 'users'
📍 At: "users"
📋 Context: Line 1, Column 8
💡 HINT: CREATE statement must be followed by TABLE or INDEX. Example: CREATE TABLE users ... or CREATE INDEX idx_name ...
```

#### 10. **Column Not Found in WHERE**
```sql
SELECT * FROM students WHERE ageee > 20;
```
**Expected Output:**
```
❌ ERROR [ColumnNotFoundError]: Column "ageee" not found in table. Available columns: id, name, age
📍 At: "ageee"
💡 HINT: Column 'ageee' not found in table. Available columns: id, name, age
```

---

## 🎯 **Quick Test Script**

Copy and paste this into AlpacaDB to test error handling:

```sql
-- First, create a test table
CREATE TABLE test_users (id INT PRIMARY KEY, name STRING, age INT);

-- Insert some data
INSERT INTO students VALUES (1, 'Alice', 25);
INSERT INTO students VALUES (2, 'Bob', 30);

-- Now try these error cases:

-- 1. Missing FROM
SELECT * WHERE age > 20;

-- 2. Wrong table name
SELECT * FROM wrong_table;

-- 3. Wrong column name
SELECT wrong_column FROM test_users;

-- 4. Invalid syntax
SELECT * test_users;

-- 5. Check what tables exist
\tables

-- 6. Check schema
\schema test_users
```

---

## 💡 **Tips**

1. **Use meta-commands** (start with `\`):
   - `\tables` - List all tables
   - `\schema <table>` - Show table structure
   - `\indexes` - List all indexes
   - `\info` - Database statistics
   - `\help` - Show all commands

2. **Error messages include:**
   - ❌ Error type and message
   - 📍 Location of the problem
   - 📋 Context (line/column)
   - 💡 Helpful hints to fix it

3. **Common mistakes:**
   - Forgetting `FROM` in SELECT
   - Typos in table/column names
   - Missing quotes around strings
   - Invalid data types

Enjoy testing! 🦙

