# AlpacaDB

> A relational database management system built from scratch in Python.

AlpacaDB is a custom relational database engine implemented from the ground up in Python. It includes its own SQL lexer and parser, abstract syntax tree, query execution engine, page-based storage layer, catalog, B-tree indexing, and cost-based query optimizer.

The project was developed as part of the **UE23CS341A Database Management Systems** course at PES University.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Storage Engine](#storage-engine)
- [B-Tree Indexing](#b-tree-indexing)
- [Query Optimizer](#query-optimizer)
- [Query Execution](#query-execution)
- [Aggregation and GROUP BY](#aggregation-and-group-by)
- [Joins](#joins)
- [Interactive CLI](#interactive-cli)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Development Architecture](#development-architecture)
- [Team](#team)
- [Project Goals](#project-goals)
- [Documentation](#documentation)

---

## Overview

AlpacaDB is designed to explore the internal components of a relational database rather than relying on an existing database engine.

A SQL query passes through the following pipeline:

```text
SQL Query
   │
   ▼
Lexer
   │
   ▼
Parser
   │
   ▼
Abstract Syntax Tree
   │
   ▼
Query Optimizer
   │
   ▼
Query Executor
   │
   ▼
Storage Engine / Indexes
```

Each layer is implemented as part of the project.

---

## Features

### SQL Processing

AlpacaDB implements its own SQL processing pipeline consisting of a lexer, parser, token definitions, and AST nodes.

Supported operations include:

- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`
- `CREATE TABLE`
- `CREATE INDEX`
- `DROP INDEX`
- `WHERE`
- `ORDER BY`
- `GROUP BY`
- `HAVING`
- `INNER JOIN`
- `LEFT JOIN`
- `RIGHT JOIN`
- `CROSS JOIN`
- Aggregate functions
  - `COUNT`
  - `SUM`
  - `AVG`
  - `MIN`
  - `MAX`
- Complex `AND` / `OR` predicates
- Index range scans
- `EXPLAIN`
- Transactions with `BEGIN`, `COMMIT`, and `ROLLBACK`

Example:

```sql
CREATE TABLE employees (
    id INT,
    name STRING,
    department STRING,
    salary INT
);

INSERT INTO employees
VALUES (1, 'Alice', 'Engineering', 85000);

SELECT department, AVG(salary)
FROM employees
GROUP BY department;
```

---

## Storage Engine

AlpacaDB implements its own storage layer instead of using an existing database engine.

The storage subsystem is responsible for managing:

- Database pages
- Persistent database files
- Tables
- Table metadata
- System catalog
- Indexes
- Page allocation and management

The storage implementation is organized as:

```text
src/storage/
├── catalog.py
├── page.py
├── page_manager.py
├── table_manager.py
└── indexing/
    ├── btree.py
    └── index_manager.py
```

---

## B-Tree Indexing

AlpacaDB includes a B-tree based indexing system.

Indexes can be created using SQL:

```sql
CREATE INDEX idx_employee_department
ON employees(department);
```

The query optimizer can use available indexes when they provide a more efficient access path.

Range scans are also supported for indexed predicates such as:

```sql
SELECT *
FROM employees
WHERE salary > 70000;
```

The indexing subsystem consists of a B-tree implementation and an index manager responsible for integrating indexes with the storage layer.

---

## Query Optimizer

AlpacaDB includes a cost-based query optimizer that estimates the cost of different access strategies and selects an execution plan.

Depending on the query and available indexes, the optimizer can choose between sequential and indexed access paths:

```text
SeqScan
```

or:

```text
IndexScan
IndexRangeScan
```

The optimizer also supports query plan inspection through `EXPLAIN`.

This separates **query planning** from **query execution**, allowing the database to choose different execution strategies for different workloads.

---

## Query Execution

The executor evaluates parsed queries using relational execution operators.

The execution layer supports:

- Sequential scans
- Index scans
- Index range scans
- Filtering
- Projection
- Inserts
- Updates
- Deletes
- Joins
- Aggregation
- Grouping
- Ordering

The execution layer is implemented under:

```text
src/executor/
├── executor.py
└── operators.py
```

---

## Aggregation and GROUP BY

AlpacaDB supports common aggregate functions:

```sql
SELECT COUNT(*)
FROM employees;
```

```sql
SELECT AVG(salary), MIN(salary), MAX(salary)
FROM employees;
```

Aggregates can also be combined with grouping:

```sql
SELECT department, COUNT(*), AVG(salary)
FROM employees
GROUP BY department;
```

The repository includes an end-to-end aggregation demonstration covering multiple aggregate functions, grouping, filtering, and more complex queries.

---

## Joins

The query execution engine supports multiple join operations:

- `INNER JOIN`
- `LEFT JOIN`
- `RIGHT JOIN`
- `CROSS JOIN`

Example:

```sql
SELECT *
FROM employees
INNER JOIN departments
ON employees.department = departments.name;
```

---

## Interactive CLI

AlpacaDB provides an interactive command-line database shell.

Start it with:

```bash
alpaca
```

The CLI supports multi-line SQL queries as well as database-specific meta commands.

Example:

```text
============================================================
🦙 AlpacaDB v0.2 - Interactive Database Shell
============================================================
Type '\help' for commands, '\quit' to exit

alpacadb>
```

Common SQL operations can be executed directly from the shell:

```sql
CREATE TABLE users (
    id INT,
    name STRING,
    age INT
);

INSERT INTO users VALUES (1, 'Alice', 21);

SELECT *
FROM users
WHERE age > 18;
```

The CLI also provides commands for inspecting tables, schemas, and indexes.

---

## Testing

The repository includes a comprehensive end-to-end test suite covering the major database features.

The comprehensive suite contains **40 tests** covering:

- CRUD operations
- B-tree indexing
- Automatic index usage
- Index range scans
- Aggregate functions
- `GROUP BY`
- Joins
- Query optimization
- `EXPLAIN`
- `ORDER BY`
- Complex `WHERE` conditions
- Real-world query scenarios
- Edge cases and stress tests

The comprehensive suite currently passes:

```text
40 passed
```

The test dataset includes:

- 100 employees
- 5 departments
- 20 projects
- 150 employee-project assignments

Run the comprehensive test suite:

```bash
pytest tests/test_comprehensive_all_features.py -v
```

Run with detailed output:

```bash
pytest tests/test_comprehensive_all_features.py -v -s
```

Run a specific test:

```bash
pytest tests/test_comprehensive_all_features.py::TestComprehensiveAlpacaDB::test_10_index_automatic_usage -v
```

> **Note:** The repository also contains older test files targeting previous APIs and implementation behavior. Some of those tests currently require updates to match the latest implementation. The comprehensive test suite is the primary end-to-end validation suite.

---

## Project Structure

```text
alpacadb/
│
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── cli.py
│   ├── errors.py
│   │
│   ├── query/
│   │   ├── __init__.py
│   │   ├── tokens.py
│   │   ├── lexer.py
│   │   ├── parser.py
│   │   └── ast_nodes.py
│   │
│   ├── executor/
│   │   ├── __init__.py
│   │   ├── executor.py
│   │   └── operators.py
│   │
│   ├── optimizer/
│   │   ├── __init__.py
│   │   ├── optimizer.py
│   │   └── cost_estimator.py
│   │
│   └── storage/
│       ├── __init__.py
│       ├── catalog.py
│       ├── page.py
│       ├── page_manager.py
│       ├── table_manager.py
│       │
│       └── indexing/
│           ├── __init__.py
│           ├── btree.py
│           └── index_manager.py
│
├── tests/
├── docs/
├── demo_aggregates.py
├── pyproject.toml
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10 or newer
- `pip`

### Installation

Clone the repository:

```bash
git clone https://github.com/LakshyaPachisia12/alpacadb.git
cd alpacadb
```

Install the project:

```bash
pip install -e .
```

### Start AlpacaDB

```bash
alpaca
```

By default, the CLI uses:

```text
data/alpacadb.db
```

You can then execute SQL directly through the interactive shell.

---

## Development Architecture

AlpacaDB is divided into independent components that mirror the major responsibilities of a relational database system.

### Query Layer

Converts SQL text into an AST:

```text
SQL
 ↓
Lexer
 ↓
Parser
 ↓
AST
```

Implemented under:

```text
src/query/
```

### Optimizer

Analyzes queries and chooses an execution strategy based on estimated costs and available indexes.

Implemented under:

```text
src/optimizer/
```

### Executor

Executes the selected query plan using relational operators.

Implemented under:

```text
src/executor/
```

### Storage

Manages pages, tables, metadata, and persistent database state.

Implemented under:

```text
src/storage/
```

### Indexing

Provides B-tree indexes and index management for efficient data access.

Implemented under:

```text
src/storage/indexing/
```

---

## Team

AlpacaDB was developed as a team project at PES University.

### Team Alpaca

- **Lakshya Pachisia** — [@LakshyaPachisia12](https://github.com/LakshyaPachisia12)
- **Laxman** — [@laxmanclo](https://github.com/laxmanclo)
- **Alex Hunterz** — [@Alex-Hunterz](https://github.com/Alex-Hunterz)
- **Manit** — [@manit-7117](https://github.com/manit-7117)

---

## Project Goals

The primary goal of AlpacaDB was to understand the internal architecture of a relational database by implementing its major components from scratch.

The project explores how a database:

- Parses SQL queries
- Represents queries as abstract syntax trees
- Plans and optimizes queries
- Executes relational operations
- Stores records on database pages
- Maintains table metadata
- Builds and uses indexes
- Estimates query execution costs
- Selects between different access strategies

Rather than treating a database as a black box, AlpacaDB provides a hands-on implementation of the core concepts behind a relational database management system.

---

## Documentation

Additional project documentation is available in the `docs/` directory, including:

- Comprehensive test results
- Presentation and feature documentation
- Development notes
