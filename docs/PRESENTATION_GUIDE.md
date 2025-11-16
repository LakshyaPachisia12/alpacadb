# 🦙 AlpacaDB Presentation Guide

## Overview
AlpacaDB is a fully-functional relational database management system built from scratch, featuring:
- **Paging Mechanism**: Fixed-size 4KB page storage with serialization
- **Query Parser**: Lexer + Parser that converts SQL to AST
- **Query Executor**: Physical operators (Scan, Filter, Project, Sort, Aggregate, IndexScan)
- **Query Optimizer**: Rule-based + Cost-based optimization with index selection
- **B-Tree Indexes**: Efficient indexing for fast lookups
- **Interactive CLI**: Professional command-line interface

---

## 🚀 Getting Started

### Installation
```bash
# Install the package (creates 'alpaca' command)
pip install -e .

# Or run directly
python -m src.cli
```

### Basic Usage
```bash
# Start AlpacaDB
alpaca

# Or specify a database file
alpaca data/mydb.db
```

---

## 🎯 Presentation Highlights

### 1. Interactive CLI Experience
```bash
alpacadb> CREATE TABLE users (id INT PRIMARY KEY, name STRING, age INT);
✅ Table 'users' created successfully

alpacadb> INSERT INTO users VALUES (1, 'Alice', 25);
✅ 1 row(s) inserted into 'users'

alpacadb> SELECT * FROM users;
┌────┬───────┬─────┐
│ id │ name  │ age │
├────┼───────┼─────┤
│ 1  │ Alice │ 25  │
└────┴───────┴─────┘

1 row(s) retrieved in 2.345ms [Plan: SeqScan]
```

### 2. Query Optimization Demo

**Before Index:**
```bash
alpacadb> EXPLAIN SELECT * FROM users WHERE age = 25;
┌──────────────────────────────────────────────────────────────┐
│ Query Plan for table 'users':                                │
│   Scan Type: SeqScan                                         │
│   Estimated Cost: 105.00                                     │
└──────────────────────────────────────────────────────────────┘
💰 Estimated Cost: 105.00
```

**Create Index:**
```bash
alpacadb> CREATE INDEX idx_age ON users (age);
✅ Index 'idx_age' created on users.age
```

**After Index:**
```bash
alpacadb> EXPLAIN SELECT * FROM users WHERE age = 25;
┌──────────────────────────────────────────────────────────────┐
│ Query Plan for table 'users':                                │
│   Scan Type: IndexScan                                       │
│   Index: idx_age                                             │
│   Column: age                                                │
│   Search Key: 25                                             │
│   Estimated Cost: 3.50                                       │
└──────────────────────────────────────────────────────────────┘
💰 Estimated Cost: 3.50
```

**Performance Improvement**: Cost reduced from 105.00 → 3.50 (30x faster!)

### 3. Database Information Commands

```bash
# List all tables
alpacadb> \tables
📊 Available tables:
┌──────────────────────────────┬──────────────────┐
│ Table Name                   │ Columns          │
├──────────────────────────────┼──────────────────┤
│ users                        │ 3 (150 rows)     │
│ orders                       │ 4 (500 rows)     │
└──────────────────────────────┴──────────────────┘

# Show table schema
alpacadb> \schema users
📋 Schema for table 'users':
┌─────────────────────────┬───────────────┬──────────┬─────────────────┐
│ Column                  │ Type          │ Nullable │ Primary Key     │
├─────────────────────────┼───────────────┼──────────┼─────────────────┤
│ id                      │ INT           │ No       │ Yes             │
│ name                    │ STRING        │ Yes      │ No              │
│ age                     │ INT           │ Yes      │ No              │
└─────────────────────────┴───────────────┴──────────┴─────────────────┘

# List all indexes
alpacadb> \indexes
🔍 Indexes:
┌─────────────────────────┬────────────────────┬────────────────────┬────────────┐
│ Index Name              │ Table              │ Column             │ Type       │
├─────────────────────────┼────────────────────┼────────────────────┼────────────┤
│ idx_age                 │ users              │ age                │ B-Tree     │
│ idx_user_id             │ orders             │ user_id            │ B-Tree     │
└─────────────────────────┴────────────────────┴────────────────────┴────────────┘

# Database statistics
alpacadb> \info
📊 Database Information:
┌─────────────────────────┬──────────────────────┐
│ Property                │ Value                │
├─────────────────────────┼──────────────────────┤
│ Database Path           │ data/alpacadb.db     │
│ Total Pages             │ 15                   │
│ Database Size           │ 0.06 MB              │
│ Tables                  │ 2                    │
│ Indexes                 │ 2                    │
│ Total Rows              │ 650                  │
└─────────────────────────┴──────────────────────┘
```

### 4. CSV Export/Import

```bash
# Export table to CSV
alpacadb> \export users users_backup.csv
✅ Exported 150 row(s) from 'users' to 'users_backup.csv'

# Import from CSV
alpacadb> \import users_new users_backup.csv
✅ Imported 150 row(s) from 'users_backup.csv' into 'users_new'
```

### 5. Advanced Query Features

```bash
# Aggregates with GROUP BY
alpacadb> SELECT age, COUNT(*) as count, AVG(id) as avg_id 
         FROM users 
         GROUP BY age;
┌─────┬───────┬────────┐
│ age │ count │ avg_id │
├─────┼───────┼────────┤
│ 25  │ 10    │ 50.5   │
│ 30  │ 15    │ 75.2   │
└─────┴───────┴────────┘

# ORDER BY
alpacadb> SELECT * FROM users ORDER BY age DESC LIMIT 5;

# Complex WHERE clauses
alpacadb> SELECT * FROM users WHERE age > 25 AND name LIKE 'A%';
```

---

## 💡 Key Features to Highlight

### 1. **Architecture**
- **Storage Layer**: Page-based storage (4KB pages) with serialization
- **Query Processing**: Lexer → Parser → AST → Optimizer → Executor
- **Indexing**: B-Tree indexes for O(log n) lookups
- **Physical Operators**: Iterator model (Volcano/Iterator)

### 2. **Optimization**
- **Rule-Based**: Index selection based on WHERE clauses
- **Cost-Based**: Estimates query execution cost
- **Plan Selection**: Chooses between SeqScan and IndexScan

### 3. **User Experience**
- **Interactive CLI**: Multi-line queries, auto-completion (meta-commands)
- **Formatted Output**: Beautiful table formatting with Unicode borders
- **Query Plans**: EXPLAIN shows execution plans
- **Statistics**: Real-time query performance metrics

### 4. **Data Management**
- **CSV Import/Export**: Easy data migration
- **Schema Introspection**: \schema, \tables, \indexes commands
- **Transaction Support**: BEGIN, COMMIT, ROLLBACK (foundation laid)

---

## 📊 Demo Script for Presentation

```bash
# 1. Start AlpacaDB
alpaca

# 2. Create demo table
CREATE TABLE students (id INT PRIMARY KEY, name STRING, age INT, grade FLOAT);

# 3. Insert sample data
INSERT INTO students VALUES (1, 'Alice', 20, 85.5);
INSERT INTO students VALUES (2, 'Bob', 21, 90.0);
INSERT INTO students VALUES (3, 'Charlie', 20, 78.5);
# ... (insert more)

# 4. Show database info
\info

# 5. Show table schema
\schema students

# 6. Query without index (slow)
EXPLAIN SELECT * FROM students WHERE age = 20;

# 7. Create index
CREATE INDEX idx_age ON students (age);

# 8. Query with index (fast)
EXPLAIN SELECT * FROM students WHERE age = 20;

# 9. Show indexes
\indexes

# 10. Aggregate query
SELECT age, COUNT(*) as count, AVG(grade) as avg_grade 
FROM students 
GROUP BY age 
ORDER BY age;

# 11. Export data
\export students students.csv

# 12. Show execution statistics
\stats
```

---

## 🎓 Technical Highlights

### What Makes This Impressive:

1. **Built from Scratch**: Not using SQLite or PostgreSQL - truly custom
2. **Complete Stack**: Storage → Parser → Optimizer → Executor
3. **Production-Quality**: Error handling, formatted output, CLI polish
4. **Extensible**: Modular design allows easy feature additions
5. **Optimized**: Cost-based optimizer with index selection
6. **Professional UX**: Beautiful CLI with helpful commands

### Architecture Diagram:
```
SQL Query
    ↓
[Lexer] → Tokens
    ↓
[Parser] → AST
    ↓
[Optimizer] → Query Plan (with cost estimation)
    ↓
[Executor] → Physical Operators
    ↓
[Storage] → Pages → Disk
```

---

## 🔧 Installation Instructions

For the presentation, make sure to:

1. **Install dependencies**:
   ```bash
   pip install -e .
   ```

2. **Test the CLI**:
   ```bash
   alpaca --help  # Should show usage
   alpaca         # Should start REPL
   ```

3. **Prepare demo data** (optional):
   - Create CSV files with sample data
   - Use \import to load them during demo

---

## 🎯 Presentation Tips

1. **Start with Architecture**: Show the complete stack from storage to CLI
2. **Demo Query Optimization**: Before/after index comparison
3. **Show CLI Features**: \info, \schema, EXPLAIN commands
4. **Highlight Cost Model**: Explain how optimizer estimates costs
5. **Emphasize Completeness**: Full database system, not just a toy project

---

## 📝 Feature Checklist

✅ **Core Features**:
- [x] Paging mechanism (4KB pages)
- [x] Query parser (Lexer + Parser)
- [x] Query executor (Physical operators)
- [x] Query optimizer (Rule-based + Cost-based)
- [x] B-Tree indexes
- [x] Interactive CLI

✅ **Enhanced Features**:
- [x] EXPLAIN command (SQL + meta-command)
- [x] Database info commands (\info, \schema, \indexes, \stats)
- [x] CSV export/import
- [x] Query execution statistics
- [x] Cost estimation in optimizer
- [x] Formatted table output
- [x] Global CLI command (`alpaca`)

✅ **Future Enhancements** (mention if asked):
- [ ] JOIN operations
- [ ] Range index scans (>, <, BETWEEN)
- [ ] Query statistics collection
- [ ] Transaction isolation levels
- [ ] Concurrent query execution

---

Good luck with your presentation! 🦙🚀

