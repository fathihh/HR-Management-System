
import sqlite3
import pandas as pd
from database.db_setup import get_table_schema, get_employee_id_column
from config import config

class SQLAgent:
    """Enhanced SQL agent with CRUD operations for HR"""
    
    def __init__(self, llm):
        self.llm = llm
        
        self.query_mapping = {
            "location": "Location",
            "address": "Location",
            "job role": "JobRole",
            "role": "JobRole",
            "position": "JobRole",
            "name": "Name",
            "employee name": "Name",
            "email": "email",
            "salary": "MonthlyIncome",
            "income": "MonthlyIncome",
            "pay": "MonthlyIncome",
            "department": "Department",
            "dept": "Department",
            "age": "Age",
            "experience": "TotalWorkingYears",
            "years": "TotalWorkingYears",
            "overtime": "OverTime",
            "education": "Education",
            "qualification": "Education",
            "marital status": "MaritalStatus",
            "gender": "Gender",
            "distance": "DistanceFromHome",
            "satisfaction": "JobSatisfaction",
            "performance": "PerformanceRating"
        }
    
    def classify_sql_intent(self, nl_query: str, user_role: str) -> str:
        """Classify what type of SQL operation is needed"""
        
        query_lower = nl_query.lower()
        
        if user_role != "hr":
            return "SELECT"
        
        update_keywords = ["change", "update", "modify", "edit", "set", "alter"]
        if any(keyword in query_lower for keyword in update_keywords):
            return "UPDATE"
        
        insert_keywords = ["add", "create", "insert", "new employee", "hire"]
        if any(keyword in query_lower for keyword in insert_keywords):
            return "INSERT"
        
        delete_keywords = ["delete", "remove", "fire", "terminate"]
        if any(keyword in query_lower for keyword in delete_keywords):
            return "DELETE"
        
        return "SELECT"
    
    def generate_sql(self, nl_query: str, user_id=None, user_role="employee") -> str:
        """Generate SQL based on intent and role"""
        
        intent = self.classify_sql_intent(nl_query, user_role)
        
        print(f"[SQL Agent] Intent: {intent} | Role: {user_role}")
        
        if intent == "UPDATE":
            return self.generate_update_sql(nl_query)
        elif intent == "INSERT":
            return self.generate_insert_sql(nl_query)
        elif intent == "DELETE":
            return self.generate_delete_sql(nl_query)
        else:
            return self.generate_select_sql(nl_query, user_id)
    
    def generate_update_sql(self, nl_query: str) -> str:
        """Generate UPDATE statement for HR"""
        
        schema = get_table_schema()
        
        prompt = f"""You are a SQL expert. Generate an UPDATE statement for SQLite.

DATABASE SCHEMA:
{schema}

USER QUERY: {nl_query}

INSTRUCTIONS:
1. Generate ONLY the UPDATE statement
2. Use proper column names from schema
3. Include WHERE clause to target specific employee(s)
4. No explanations, no markdown, no semicolons
5. Format: UPDATE employees SET column = value WHERE condition

EXAMPLES:
Query: "change the name of employee id 1 to saghil"
SQL: UPDATE employees SET Name = 'saghil' WHERE EmployeeNumber = '1'

Query: "update salary of employee E001 to 50000"
SQL: UPDATE employees SET MonthlyIncome = 50000 WHERE EmployeeNumber = 'E001'

Query: "change department of John to Sales"
SQL: UPDATE employees SET Department = 'Sales' WHERE Name LIKE '%John%'

Query: "set overtime to Yes for all in IT department"
SQL: UPDATE employees SET OverTime = 'Yes' WHERE Department = 'IT'

Now generate SQL:
"""
        
        try:
            raw_response = self.llm._call(prompt)
            sql = self._clean_sql(raw_response)
            
            if not sql.upper().startswith("UPDATE"):
                return f"REJECTED_SQL: Must be UPDATE statement -> {sql}"
            
            if "WHERE" not in sql.upper():
                return f"REJECTED_SQL: UPDATE must have WHERE clause for safety -> {sql}"
            
            print(f"[SQL Agent] Generated UPDATE: {sql}")
            return sql
        
        except Exception as e:
            return f"REJECTED_SQL: Generation error: {str(e)}"
    
    def generate_insert_sql(self, nl_query: str) -> str:
        """Generate INSERT statement for HR"""
        
        schema = get_table_schema()
        id_col = get_employee_id_column()
        
        prompt = f"""You are a SQL expert. Generate an INSERT statement for SQLite.

DATABASE SCHEMA:
{schema}

USER QUERY: {nl_query}

INSTRUCTIONS:
1. Generate ONLY the INSERT statement
2. Include all mentioned fields
3. Generate unique EmployeeNumber if not provided (format: E + random 3 digits)
4. Use NULL or default values for missing fields
5. No explanations, no markdown, no semicolons

EXAMPLES:
Query: "add new employee named Alice with email alice@company.com in Sales department"
SQL: INSERT INTO employees (EmployeeNumber, Name, email, Department) VALUES ('E' || ABS(RANDOM() % 900 + 100), 'Alice', 'alice@company.com', 'Sales')

Query: "create employee John Doe, Sales Executive, salary 45000"
SQL: INSERT INTO employees (EmployeeNumber, Name, JobRole, MonthlyIncome, Department) VALUES ('E' || ABS(RANDOM() % 900 + 100), 'John Doe', 'Sales Executive', 45000, 'Sales')

Query: "hire new employee ID E999 named Bob in IT department"
SQL: INSERT INTO employees (EmployeeNumber, Name, Department) VALUES ('E999', 'Bob', 'IT')

Now generate SQL:
"""
        
        try:
            raw_response = self.llm._call(prompt)
            sql = self._clean_sql(raw_response)
            
            if not sql.upper().startswith("INSERT"):
                return f"REJECTED_SQL: Must be INSERT statement -> {sql}"
            
            print(f"[SQL Agent] Generated INSERT: {sql}")
            return sql
        
        except Exception as e:
            return f"REJECTED_SQL: Generation error: {str(e)}"
    
    def generate_delete_sql(self, nl_query: str) -> str:
        """Generate DELETE statement for HR"""
        
        schema = get_table_schema()
        
        prompt = f"""You are a SQL expert. Generate a DELETE statement for SQLite.

DATABASE SCHEMA:
{schema}

USER QUERY: {nl_query}

INSTRUCTIONS:
1. Generate ONLY the DELETE statement
2. MUST include WHERE clause (never delete all records)
3. Be specific with conditions
4. No explanations, no markdown, no semicolons

EXAMPLES:
Query: "delete employee id E001"
SQL: DELETE FROM employees WHERE EmployeeNumber = 'E001'

Query: "remove employee named John"
SQL: DELETE FROM employees WHERE Name LIKE '%John%'

Now generate SQL:
"""
        
        try:
            raw_response = self.llm._call(prompt)
            sql = self._clean_sql(raw_response)
            
            if not sql.upper().startswith("DELETE"):
                return f"REJECTED_SQL: Must be DELETE statement -> {sql}"
            
            if "WHERE" not in sql.upper():
                return f"REJECTED_SQL: DELETE must have WHERE clause for safety -> {sql}"
            
            print(f"[SQL Agent] Generated DELETE: {sql}")
            return sql
        
        except Exception as e:
            return f"REJECTED_SQL: Generation error: {str(e)}"
    
    def generate_select_sql(self, nl_query: str, user_id=None) -> str:
        """Generate SELECT statement (original logic)"""
        
        schema = get_table_schema()
        user_context = ""
        
        if user_id is not None:
            id_col = get_employee_id_column()
            user_context = f"""
CRITICAL SECURITY RULE: This query is from employee ID '{user_id}'.
You MUST add: WHERE {id_col} = '{user_id}'
"""
        
        nl_lower = nl_query.lower()
        column_hints = []
        
        for term, column in self.query_mapping.items():
            if term in nl_lower:
                column_hints.append(f"  - '{term}' → column '{column}'")
        
        hints_text = ""
        if column_hints:
            hints_text = "\nColumn Mappings:\n" + "\n".join(column_hints)
        
        prompt = f"""You are an expert SQL query generator for SQLite.

DATABASE SCHEMA:
{schema}

{hints_text}

{user_context}

USER QUERY: {nl_query}

INSTRUCTIONS:
1. Generate ONLY a valid SELECT statement
2. Use proper column names from schema
3. Add WHERE, ORDER BY, LIMIT as needed
4. Use LIKE for partial text matching
5. Handle aggregations (COUNT, AVG, SUM, MAX, MIN)
6. NO explanations, markdown, or semicolons

EXAMPLES:
Query: "What is my salary?"
SQL: SELECT MonthlyIncome FROM employees WHERE EmployeeNumber = '{user_id if user_id else 'E001'}'

Query: "Show all employees in Sales"
SQL: SELECT Name, JobRole, MonthlyIncome FROM employees WHERE Department = 'Sales'

Query: "Average salary by department"
SQL: SELECT Department, AVG(MonthlyIncome) as AvgSalary FROM employees GROUP BY Department

Now generate SQL:
"""
        
        try:
            raw_response = self.llm._call(prompt)
            sql = self._clean_sql(raw_response)
            
            if not sql.upper().startswith("SELECT"):
                return f"REJECTED_SQL: Must be SELECT statement -> {sql}"
            
            if user_id is not None:
                sql = self._ensure_user_filter(sql, user_id)
            
            print(f"[SQL Agent] Generated SELECT: {sql}")
            return sql
        
        except Exception as e:
            return f"REJECTED_SQL: Generation error: {str(e)}"
    
    def _clean_sql(self, sql: str) -> str:
        """Clean and format SQL query"""
        
        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0].strip()
        
        lines = sql.split('\n')
        for line in lines:
            line = line.strip()
            if line.upper().startswith(('SELECT', 'UPDATE', 'INSERT', 'DELETE')):
                sql = line
                break
        
        sql = sql.rstrip(";").strip()
        
        return sql
    
    def _ensure_user_filter(self, sql: str, user_id: str) -> str:
        """Ensure WHERE clause filters by user_id for employees"""
        
        sql_lower = sql.lower()
        id_col = get_employee_id_column()
        
        if "where" not in sql_lower:
            sql += f" WHERE {id_col} = '{user_id}'"
        elif id_col.lower() not in sql_lower or user_id not in sql:
            sql += f" AND {id_col} = '{user_id}'"
        
        return sql
    
    def execute_sql(self, sql: str, user_role="employee"):
        """Execute SQL with role-based permissions"""
        
        if sql.startswith("REJECTED_SQL"):
            return {"error": sql.replace("REJECTED_SQL: ", "")}
        
        try:
            conn = sqlite3.connect(config.DB_PATH)
            cursor = conn.cursor()
            
            sql_upper = sql.upper()
            
            if sql_upper.startswith("SELECT"):
                df = pd.read_sql(sql, conn)
                conn.close()
                
                if df.empty:
                    return {
                        "success": True,
                        "message": "No results found",
                        "sql": sql,
                        "data": [],
                        "count": 0
                    }
                
                records = df.to_dict(orient="records")
                
                for record in records:
                    for key, value in record.items():
                        if isinstance(value, float):
                            record[key] = round(value, 2)
                
                return {
                    "success": True,
                    "sql": sql,
                    "data": records,
                    "count": len(df),
                    "columns": list(df.columns)
                }
            
            elif sql_upper.startswith(("UPDATE", "INSERT", "DELETE")):
                if user_role != "hr":
                    conn.close()
                    return {
                        "error": "Permission denied. Only HR can modify employee data.",
                        "sql": sql
                    }
                
                cursor.execute(sql)
                conn.commit()
                rows_affected = cursor.rowcount
                conn.close()
                
                operation = sql.split()[0].upper()
                
                return {
                    "success": True,
                    "message": f"✅ {operation} successful! {rows_affected} row(s) affected.",
                    "sql": sql,
                    "rows_affected": rows_affected,
                    "operation": operation
                }
            
            else:
                conn.close()
                return {"error": "Unsupported SQL operation"}
        
        except sqlite3.IntegrityError as e:
            return {
                "error": f"Database constraint violation: {str(e)}",
                "sql": sql,
                "suggestion": "Check if employee ID already exists or required fields are missing"
            }
        
        except sqlite3.OperationalError as e:
            return {
                "error": f"Database error: {str(e)}",
                "sql": sql,
                "suggestion": "Please check column names and table structure"
            }
        
        except Exception as e:
            return {
                "error": f"Execution error: {str(e)}",
                "sql": sql
            }