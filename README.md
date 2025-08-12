# SQLite CSV Importer & Manager

## Overview

This lightweight, portable SQLite database management tool was created to empower **students**, **tech enthusiasts**, **self-starters**, **small companies**, and **researchers** alike. It offers an easy way to:

- Import CSV files into SQLite tables quickly
- Explore and query your data with a simple GUI or command-line interface
- Export data back to CSV
- Safely create tables and run queries with built-in input sanitization and security measures

Whether you're learning SQL, testing queries, or need a small but capable database system, this project gives you a **user-friendly yet powerful** solution without the complexity or overhead of heavier DBMS setups.

---

## Features

- Import CSV files into new or existing SQLite tables
- Export tables to CSV files
- Browse tables and view data in a GUI with search/filter support
- Run safe SQL queries from CLI (SELECT, PRAGMA, EXPLAIN, CREATE TABLE)
- Run write queries (INSERT, UPDATE, DELETE, DROP) with confirmation prompts to prevent accidental data loss
- Input sanitization to prevent SQL injection and ensure valid table/column names
- Detailed audit logging of imports, queries, table creations, and errors
- Lightweight and portable — single Python script using standard libraries and Tkinter
- Helpful SQL cheat sheet included for beginners

---

## Motivation

I built this tool to give learners and professionals a **simple, safe, and effective** environment for practicing and managing SQLite databases. It serves several use cases:

- **Students & Beginners:** Practice SQL queries and database design without setup headaches
- **Tech Enthusiasts:** Quickly import/export and explore data from CSVs
- **Self-Starters & Researchers:** Manage datasets on your local machine easily
- **Small Companies & Freelancers:** Use as a portable DBMS for lightweight projects or data management tasks

The goal is to provide **accessible database tools** that don’t require expensive or complicated software, while also emphasizing security and reliability.

---

## Requirements

- Python 3.8 or newer
- Standard Python libraries (sqlite3, tkinter, argparse, csv, etc.)

---

## Getting Started

### GUI Mode

Run the tool in GUI mode for interactive usage:

```bash
python sqlite-db.py --gui --db your_database.sqlite
```
  If the database file doesn’t exist, it will be created.

-- Import CSV files into new tables via the Import CSV button.

-- Select tables on the left to browse data.

-- Use the Search box to filter rows with SQL WHERE clauses.

-- Export selected tables to CSV files.

-- View table schema details.

-- Refresh the table list to see updates.


## CLI Mode
The CLI offers two main commands: create-table and query.

## Create a New Table
Run a safe CREATE TABLE statement:
```
python sqlite-db.py --db your_database.sqlite create-table "CREATE TABLE test(id INTEGER PRIMARY KEY, name TEXT)"
```
## Run a Query
Run read-only queries freely:
```
python sqlite-db.py --db your_database.sqlite query "SELECT * FROM test LIMIT 10"
```
For modifying queries (INSERT, UPDATE, DELETE, DROP), you’ll receive a confirmation prompt:
```WARNING: This command will modify the database. Are you sure? (y/n):
Type y to proceed.
```
## Security & Safety
Only safe queries allowed by default (SELECT, PRAGMA, EXPLAIN, and CREATE TABLE)

Dangerous queries require explicit user confirmation

Input sanitization prevents SQL injection and invalid names

Audit logs track all imports, queries, and errors for traceability

CSV imports enforce file size limits and validate data consistency

## Included Cheat Sheet
Check out the SQL_Cheat_Sheet.md for a curated list of beginner-friendly SQL commands to get you started quickly with the CLI interface, including:

-- Basic SELECT statements

-- Filtering with WHERE clauses

-- Creating tables

-- Inserting data

-- Updating and deleting records

-- Useful PRAGMA commands

## License
MIT License — free to use, modify, and share!

## Contact
Created by Antoine Jones. For questions, contributions, or freelance inquiries, feel free to reach out!

Thank you for trying out this tool! I hope it helps you explore and master SQLite databases with ease.
