#db_setup.py

import os
import sqlite3
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from config import config

engine = create_engine(config.DATABASE_URL, future=True)

def init_database(csv_path=None):
    """Initialize the SQLite database with employee data from a CSV."""
    if not csv_path or not csv_path.endswith('.csv'):
        print("❌ No valid CSV file provided")
        return False

    try:
        df = pd.read_csv(csv_path)
        df.columns = [c.strip() for c in df.columns]

        conn = sqlite3.connect(config.DB_PATH)
        df.to_sql("employees", conn, if_exists="replace", index=False)
        conn.close()

        print(f"✅ Database initialized with {len(df)} employees")

        inspector = inspect(engine)
        columns = inspector.get_columns("employees")
        print("\n📊 Database Schema:")
        for col in columns:
            print(f"  Column: {col['name']:20} Type: {col['type']}")

        return True

    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_database_exists():
    """Check if the database exists and has at least one employee."""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False

def get_table_schema():
    """Return schema of the employees table as text."""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        schema_info = cursor.fetchall()
        conn.close()

        schema_text = "employees table columns:\n"
        for info in schema_info:
            schema_text += f"- {info[1]} ({info[2]})\n"
        return schema_text
    except Exception as e:
        return f"Schema error: {e}"

def get_employee_id_column():
    """Dynamically detect employee ID column."""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        columns = [info[1] for info in cursor.fetchall()]
        conn.close()

        for col in columns:
            if "emp" in col.lower() and ("id" in col.lower() or "number" in col.lower()):
                return col

        if "EmployeeNumber" in columns:
            return "EmployeeNumber"
        if "EmpID" in columns:
            return "EmpID"

        return columns[0] if columns else "id"
    except:
        return "id"

def get_sample_employees(limit=5):
    """Fetch a few rows for testing."""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        df = pd.read_sql(f"SELECT * FROM employees LIMIT {limit}", conn)
        conn.close()
        return df
    except Exception as e:
        print(f"❌ Error reading employees table: {e}")
        return pd.DataFrame()