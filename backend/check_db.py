# backend/check_db.py
import sqlite3
from pathlib import Path
import sys

DB_PATH = Path(__file__).with_name("hr_employees.db")

LEAVE_REQ_DDL = """
CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    days       INTEGER NOT NULL,
    reason     TEXT,
    status     TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | APPROVED | REJECTED
    decided_by TEXT,
    decided_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(employee_id) REFERENCES employees(EmpID)
);
"""

NOTIF_DDL = """
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER,                 -- NULL means HR/broadcast
    target_role TEXT NOT NULL,           -- 'EMPLOYEE' | 'HR'
    title TEXT NOT NULL,
    body  TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor  TEXT NOT NULL,     -- 'EMP:<id>' | 'HR:<id/email>' | 'SYSTEM'
    action TEXT NOT NULL,     -- e.g. 'LEAVE_REQUEST', 'LEAVE_APPROVE'
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

def ensure_tables_and_columns() -> None:
    """Create aux tables if missing and add leave_remaining if not present."""
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()

        # Create aux tables (no change to existing employees schema)
        cur.execute(LEAVE_REQ_DDL)
        cur.execute(NOTIF_DDL)
        cur.execute(AUDIT_DDL)

        # Add leave_remaining to employees if missing
        cur.execute("PRAGMA table_info(employees)")
        cols = {row[1] for row in cur.fetchall()}
        if "leave_remaining" not in cols:
            try:
                cur.execute("ALTER TABLE employees ADD COLUMN leave_remaining INTEGER DEFAULT 24")
                print("Added employees.leave_remaining (default 24).")
            except sqlite3.OperationalError as e:
                # If employees table doesn't exist yet (CSV not loaded), just skip silently
                print(f"Note: couldn't add leave_remaining (employees may not exist yet): {e}")

        con.commit()

def print_employee(emp_id: int) -> None:
    """Quick info print, compatible with your earlier script."""
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        try:
            cur.execute("SELECT * FROM employees WHERE EmpID = ?", (emp_id,))
            row = cur.fetchone()
        except sqlite3.OperationalError as e:
            print("employees table not found yet. Load your CSV first.")
            print(f"Details: {e}")
            return

        if row:
            columns = [desc[0] for desc in cur.description]
            print(f"\nEmployee ID {emp_id} Data:")
            print("-" * 50)
            for col, val in zip(columns, row):
                print(f"{col:20}: {val}")
        else:
            print(f"Employee {emp_id} not found")

if __name__ == "__main__":
    print(f"Using DB: {DB_PATH}")
    ensure_tables_and_columns()

    # Optional: allow `python check_db.py 1481` to print that employee
    emp_arg = None
    if len(sys.argv) > 1:
        try:
            emp_arg = int(sys.argv[1])
        except ValueError:
            pass

    if emp_arg is None:
        # Backward-compatible default (your previous check used 1481)
        emp_arg = 1481

    print_employee(emp_arg)
