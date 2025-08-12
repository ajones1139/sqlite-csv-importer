import sqlite3
import os
import time
import traceback
import csv
import mimetypes
import re
import argparse
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

# === Constants ===
LOG_FILE = 'sqlite_manager_error.log'  # Uniform, recognizable log file
MAX_CSV_SIZE = 10 * 1024 * 1024  # 10 MB max CSV file size
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")  # Valid SQLite identifiers

# Allowed SQL prefixes for safe and dangerous commands
SAFE_SQL_PREFIXES = ("SELECT", "PRAGMA", "EXPLAIN")
DANGEROUS_SQL_PREFIXES = ("UPDATE", "DELETE", "INSERT", "DROP", "ALTER", "REPLACE", "CREATE TABLE")


# === Logging Functions ===
def log_error(exc: Exception):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR: {exc}\n")
        traceback.print_exc(file=f)
        f.write('\n')


# === Database Manager Class ===
class DatabaseManager:
    def __init__(self, db_path: str):
        if not db_path.endswith('.sqlite') and not db_path.endswith('.db'):
            db_path += '.sqlite'
        self.db_path = db_path
        self.conn = None

    def connect(self):
        if self.conn:
            return
        self.conn = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_audit_table()

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            finally:
                self.conn = None

    def _create_audit_table(self):
        self.connect()
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def _log_event(self, event_type: str, details: str):
        try:
            with self.conn:
                self.conn.execute(
                    'INSERT INTO audit_log (event_type, details) VALUES (?, ?)',
                    (event_type, details)
                )
        except Exception as e:
            log_error(e)

    def list_tables(self):
        self.connect()
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        return [r[0] for r in cur.fetchall()]

    def safe_query(self, query: str):
        self.connect()
        cur = self.conn.cursor()
        cur.execute(query)
        return cur.fetchall()

    def table_info(self, table_name: str):
        self.connect()
        cur = self.conn.cursor()
        cur.execute(f"PRAGMA table_info('{table_name}')")
        return cur.fetchall()

    def import_csv(self, csv_path: str, table_name: str, append: bool = False, create_index_on: str | None = None):
        tn = sanitize_identifier(table_name)

        size = os.path.getsize(csv_path)
        if size > MAX_CSV_SIZE:
            raise ValueError(f"CSV file size {size} bytes exceeds max allowed {MAX_CSV_SIZE} bytes")

        mime_type, _ = mimetypes.guess_type(csv_path)
        if mime_type != "text/csv" and not csv_path.lower().endswith(".csv"):
            raise ValueError("Invalid file type. Only CSV allowed.")

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            if headers is None:
                raise ValueError("CSV appears empty")

            headers = [h.strip().replace(" ", "_") or f"col{i}" for i, h in enumerate(headers)]
            for i, h in enumerate(headers):
                if not IDENT_RE.match(h):
                    safe = re.sub(r"[^A-Za-z0-9_]", "_", h)
                    if not IDENT_RE.match(safe):
                        safe = f"col_{hash(h) & 0xFFFF}"
                    headers[i] = safe

            sample_rows = []
            for _ in range(20):
                try:
                    row = next(reader)
                    if len(row) != len(headers):
                        raise ValueError(f"CSV row length mismatch: expected {len(headers)}, got {len(row)}")
                    sample_rows.append(row)
                except StopIteration:
                    break

            columns_sql = []
            for col_idx, col_name in enumerate(headers):
                sample_vals = [row[col_idx] if col_idx < len(row) else "" for row in sample_rows]
                sql_type = consistent_types(sample_vals)
                columns_sql.append(f"'{col_name}' {sql_type}")

            self.connect()
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tn,))
            table_exists = bool(cur.fetchone())
            if table_exists and not append:
                raise FileExistsError(f"Table {tn} exists. Use append=True or drop table first.")

            create_fragment = ", ".join(columns_sql)

            with self.conn:
                cur.execute(f"CREATE TABLE IF NOT EXISTS '{tn}' ({create_fragment})")
                placeholders = ",".join(["?"] * len(headers))
                collist = ",".join([f"'{c}'" for c in headers])
                insert_sql = f"INSERT INTO '{tn}' ({collist}) VALUES ({placeholders})"

                for row in sample_rows:
                    cleaned = [str(cell).strip() for cell in row]
                    cur.execute(insert_sql, cleaned)

                for row in reader:
                    if len(row) != len(headers):
                        raise ValueError("CSV row length mismatch during import")
                    cleaned = [str(cell).strip() for cell in row]
                    cur.execute(insert_sql, cleaned)

                if create_index_on:
                    ci = sanitize_identifier(create_index_on)
                    idx_name = f"idx_{tn}_{ci}"
                    cur.execute(f"CREATE INDEX IF NOT EXISTS '{idx_name}' ON '{tn}'('{ci}')")

            self._log_event("IMPORT_CSV", f"Imported {tn} from {csv_path} ({size} bytes)")

    def export_table_to_csv(self, table_name: str, filepath: str):
        self.connect()
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM '{table_name}'")
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([row[col] for col in columns])
        self._log_event("EXPORT_CSV", f"Exported table {table_name} to {filepath}")


# === Helper Functions ===
def sanitize_identifier(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Identifier must be a string")
    name = name.strip()
    if not IDENT_RE.match(name):
        raise ValueError(f"Invalid identifier: {name!r}. Allowed: letters, numbers, underscore, not starting with number.")
    return name


def consistent_types(values):
    t = "INTEGER"
    for v in values:
        if v == "":
            return "TEXT"
        try:
            int(v)
            continue
        except Exception:
            try:
                float(v)
                if t == "INTEGER":
                    t = "REAL"
            except Exception:
                return "TEXT"
    return t


# === CLI Functions ===
def is_sql_dangerous(sql: str) -> bool:
    sql = sql.strip().upper()
    return any(sql.startswith(prefix) for prefix in DANGEROUS_SQL_PREFIXES)


def is_sql_safe(sql: str) -> bool:
    sql = sql.strip().upper()
    return any(sql.startswith(prefix) for prefix in SAFE_SQL_PREFIXES)


def cli_create_table(db_manager, create_stmt: str):
    if not create_stmt.strip().upper().startswith("CREATE TABLE"):
        print("Error: Only CREATE TABLE statements are allowed for create-table command.")
        return

    if ";" in create_stmt.strip()[:-1]:
        print("Error: Multiple statements are not allowed.")
        return

    try:
        db_manager.connect()
        with db_manager.conn:
            db_manager.conn.execute(create_stmt)
        db_manager._log_event("CREATE_TABLE", create_stmt)
        print("Table created successfully.")
    except Exception as e:
        print(f"Error creating table: {e}")
        log_error(e)


def cli_query(db_manager, query: str):
    sql_upper = query.strip().upper()

    if not (is_sql_safe(query) or is_sql_dangerous(query)):
        print("Error: Command not allowed.")
        return

    if is_sql_dangerous(query):
        confirm = input("WARNING: This command will modify the database. Are you sure? (y/n): ").strip().lower()
        if confirm not in ('y', 'yes'):
            print("Command cancelled.")
            return

    try:
        db_manager.connect()
        cur = db_manager.conn.cursor()
        cur.execute(query)

        if is_sql_safe(query):
            rows = cur.fetchall()
            if rows:
                columns = [desc[0] for desc in cur.description]
                print("\t".join(columns))
                for row in rows:
                    print("\t".join(str(row[col]) if row[col] is not None else "" for col in columns))
            else:
                print("No results.")
        else:
            print("Command executed successfully.")

        db_manager._log_event("QUERY", query[:200])

    except Exception as e:
        print(f"Error executing query: {e}")
        log_error(e)


# === GUI Application ===
class App:
    def __init__(self, root, db_manager):
        self.root = root
        self.db = db_manager
        self.root.title(f"SQLite CSV Importer - {self.db.db_path}")

        top = tk.Frame(root)
        top.pack(padx=10, pady=8, fill='x')
        tk.Label(top, text=f"Database: {self.db.db_path}").pack(side='left')
        tk.Button(top, text="Import CSV", command=self.import_csv_dialog).pack(side='right')
        tk.Button(top, text="Export Table", command=self.export_table_dialog).pack(side='right')

        mid = tk.Frame(root)
        mid.pack(padx=10, pady=8, fill='both', expand=True)

        left = tk.Frame(mid)
        left.pack(side='left', fill='y')
        tk.Label(left, text="Tables").pack()
        self.table_listbox = tk.Listbox(left, width=30)
        self.table_listbox.pack(side='left', fill='y')
        scrollbar = tk.Scrollbar(left, orient='vertical', command=self.table_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.table_listbox.config(yscrollcommand=scrollbar.set)
        self.table_listbox.bind('<<ListboxSelect>>', lambda e: self.on_table_select())

        right = tk.Frame(mid)
        right.pack(side='left', fill='both', expand=True)
        search_frame = tk.Frame(right)
        search_frame.pack(fill='x')
        tk.Label(search_frame, text="Search (SQL WHERE)").pack(side='left')
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side='left', fill='x', expand=True)
        tk.Button(search_frame, text="Go", command=self.on_search).pack(side='left')

        self.results = tk.Text(right, height=20)
        self.results.pack(fill='both', expand=True)

        bottom = tk.Frame(root)
        bottom.pack(padx=10, pady=8, fill='x')
        tk.Button(bottom, text="Refresh Tables", command=self.refresh_tables).pack(side='left')
        tk.Button(bottom, text="Show Schema", command=self.show_schema).pack(side='left')

        self.refresh_tables()

    def refresh_tables(self):
        try:
            tables = self.db.list_tables()
        except Exception as e:
            messagebox.showerror("Error", f"Could not list tables: {e}")
            tables = []
        self.table_listbox.delete(0, tk.END)
        for t in tables:
            self.table_listbox.insert(tk.END, t)

    def on_table_select(self):
        sel = self.table_listbox.curselection()
        if not sel:
            return
        table = self.table_listbox.get(sel[0])
        try:
            rows = self.db.safe_query(f"SELECT * FROM '{table}' LIMIT 50")
            self.display_rows(rows)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load table data: {e}")

    def on_search(self):
        sel = self.table_listbox.curselection()
        if not sel:
            messagebox.showinfo("Info", "Please select a table first")
            return
        table = self.table_listbox.get(sel[0])
        where_clause = self.search_var.get().strip()
        if where_clause:
            sql = f"SELECT * FROM '{table}' WHERE {where_clause} LIMIT 50"
        else:
            sql = f"SELECT * FROM '{table}' LIMIT 50"
        try:
            rows = self.db.safe_query(sql)
            self.display_rows(rows)
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")

    def display_rows(self, rows):
        self.results.delete('1.0', tk.END)
        if not rows:
            self.results.insert(tk.END, "No results found.")
            return
        cols = rows[0].keys()
        self.results.insert(tk.END, "\t".join(cols) + "\n")
        self.results.insert(tk.END, "-" * 50 + "\n")
        for row in rows:
            line = "\t".join(str(row[col]) if row[col] is not None else "" for col in cols)
            self.results.insert(tk.END, line + "\n")

    def import_csv_dialog(self):
        filepath = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not filepath:
            return
        table_name = simpledialog.askstring("Table Name", "Enter table name to import into:")
        if not table_name:
            messagebox.showinfo("Cancelled", "Import cancelled (no table name).")
            return
        try:
            self.db.import_csv(filepath, table_name)
            messagebox.showinfo("Success", f"Imported CSV into table '{table_name}'")
            self.refresh_tables()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import CSV: {e}")

    def export_table_dialog(self):
        sel = self.table_listbox.curselection()
        if not sel:
            messagebox.showinfo("Info", "Please select a table to export")
            return
        table = self.table_listbox.get(sel[0])
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not filepath:
            return
        try:
            self.db.export_table_to_csv(table, filepath)
            messagebox.showinfo("Success", f"Exported table '{table}' to CSV")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {e}")

    def show_schema(self):
        sel = self.table_listbox.curselection()
        if not sel:
            messagebox.showinfo("Info", "Please select a table first")
            return
        table = self.table_listbox.get(sel[0])
        try:
            schema = self.db.table_info(table)
            schema_str = "\n".join(f"{row['cid']}: {row['name']} {row['type']} (notnull={row['notnull']}, pk={row['pk']})" for row in schema)
            messagebox.showinfo(f"Schema for {table}", schema_str)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to retrieve schema: {e}")


# === Main ===
def main():
    parser = argparse.ArgumentParser(description="SQLite CSV Importer")
    parser.add_argument("--db", required=False, default="data.sqlite", help="SQLite database file name")
    parser.add_argument("--gui", action="store_true", help="Launch GUI mode")

    subparsers = parser.add_subparsers(dest="command")

    create_parser = subparsers.add_parser("create-table", help="Create a new table")
    create_parser.add_argument("create_stmt", help="CREATE TABLE statement")

    query_parser = subparsers.add_parser("query", help="Run a SQL query")
    query_parser.add_argument("query", help="SQL query string")

    args = parser.parse_args()

    db_manager = DatabaseManager(args.db)

    if args.gui:
        root = tk.Tk()
        app = App(root, db_manager)
        root.mainloop()
    elif args.command == "create-table":
        cli_create_table(db_manager, args.create_stmt)
    elif args.command == "query":
        cli_query(db_manager, args.query)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
