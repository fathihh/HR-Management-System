import sqlite3
import pandas as pd
from config import config
from database.db_setup import get_employee_id_column
from utils.payslip_generator import generate_payslip_pdf, generate_payslip_text
from utils.email_utils import send_payslip_email

class EmployeeAgent:
    """Agent for employee-related operations"""
    
    def __init__(self, sql_agent):
        self.sql_agent = sql_agent
    
    def classify_employee_intent(self, query: str, user_role: str) -> str:
        """Classify what the user wants to do"""
        
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["payslip", "pay slip", "salary slip"]):
            if any(word in query_lower for word in ["generate", "create", "make"]):
                return "generate_payslip"
            elif any(word in query_lower for word in ["email", "send", "mail"]):
                return "send_payslip_email"
            else:
                return "generate_payslip" 
        
        if any(word in query_lower for word in ["email", "send", "mail"]) and user_role == "hr":
            return "send_email"
        
        if user_role == "hr":
            if any(word in query_lower for word in ["create", "add", "insert", "new employee"]):
                return "create_employee"
            elif any(word in query_lower for word in ["update", "modify", "change", "edit"]):
                return "update_employee"
            elif any(word in query_lower for word in ["delete", "remove"]):
                return "delete_employee"
        
        return "query_data"
    
    def handle_query(self, query: str, user_role: str, user_id: str = None) -> dict:
        """Main handler for employee queries"""
        
        intent = self.classify_employee_intent(query, user_role)
        
        print(f"[Employee Agent] Intent: {intent} | Role: {user_role} | User: {user_id}")
        
        if intent == "generate_payslip":
            return self.generate_payslip(query, user_id, user_role)
        
        elif intent == "send_payslip_email":
            return self.send_payslip_email(query, user_id, user_role)
        
        elif intent == "send_email":
            return self.send_email(query, user_id)
        
        elif intent == "create_employee" and user_role == "hr":
            return self.create_employee(query)
        
        elif intent == "update_employee" and user_role == "hr":
            return self.update_employee(query)
        
        elif intent == "delete_employee" and user_role == "hr":
            return self.delete_employee(query)
        
        elif intent == "query_data":
            return self.query_employee_data(query, user_id, user_role)
        
        else:
            return {"error": "❌ Operation not permitted or unknown intent"}
    
    def generate_payslip(self, query: str, user_id: str, user_role: str) -> dict:
        """Generate payslip (PDF or text)"""
        
        emp_id = user_id
        
        if user_role == "hr":
            words = query.split()
            for i, word in enumerate(words):
                if word.lower() in ["for", "of"] and i + 1 < len(words):
                    potential_id = words[i + 1].strip(",.;")
                    if potential_id:
                        emp_id = potential_id
                        break
        
        if not emp_id:
            return {"error": "❌ Employee ID not specified"}
        
        use_pdf = "pdf" in query.lower() or "PDF" in query
        
        try:
            if use_pdf:
                filename, message = generate_payslip_pdf(emp_id)
            else:
                filename, message = generate_payslip_text(emp_id)
            
            if filename:
                return {
                    "success": True,
                    "message": message,
                    "filename": filename,
                    "employee_id": emp_id
                }
            else:
                return {"error": message}
        
        except Exception as e:
            return {"error": f"❌ Payslip generation failed: {str(e)}"}
    
    def send_payslip_email(self, query: str, user_id: str, user_role: str) -> dict:
        """Generate payslip and send via email"""
        
        emp_id = user_id
        
        if user_role == "hr":
            words = query.split()
            for i, word in enumerate(words):
                if word.lower() in ["for", "to"] and i + 1 < len(words):
                    potential_id = words[i + 1].strip(",.;")
                    if potential_id:
                        emp_id = potential_id
                        break
        
        if not emp_id:
            return {"error": "❌ Employee ID not specified"}
        
        try:
            col_id = get_employee_id_column()
            conn = sqlite3.connect(config.DB_PATH)
            df = pd.read_sql(
                f"SELECT email, Name FROM employees WHERE {col_id}='{emp_id}'", 
                conn
            )
            conn.close()
            
            if df.empty:
                return {"error": f"❌ Employee {emp_id} not found"}
            
            email = df.iloc[0]['email']
            name = df.iloc[0].get('Name', emp_id)
            
            if not email or '@' not in email:
                return {"error": f"❌ No valid email found for employee {emp_id}"}
            
            filename, message = generate_payslip_pdf(emp_id)
            
            if not filename:
                return {"error": f"❌ Failed to generate payslip: {message}"}
            
            result = send_payslip_email(emp_id, email, filename)
            
            if result.get("success"):
                return {
                    "success": True,
                    "message": f"✅ Payslip sent to {name} ({email})",
                    "email": email,
                    "filename": filename
                }
            else:
                return {"error": result.get("message", "Email sending failed")}
        
        except Exception as e:
            return {"error": f"❌ Error: {str(e)}"}
    
    def send_email(self, query: str, user_id: str) -> dict:
        """Send custom email (HR only)"""
        return {"message": "📧 Custom email sending not yet implemented"}
    
    def query_employee_data(self, query: str, user_id: str, user_role: str) -> dict:
        """Query employee data from database"""
        
        try:
            sql = self.sql_agent.generate_sql(query, user_id)
            result = self.sql_agent.execute_sql(sql)
            return result
        
        except Exception as e:
            return {"error": f"❌ Query error: {str(e)}"}
    
    def create_employee(self, query: str) -> dict:
        """Create new employee (HR only) - Placeholder"""
        return {"message": "🔨 Employee creation not yet implemented"}
    
    def update_employee(self, query: str) -> dict:
        """Update employee data (HR only) - Placeholder"""
        return {"message": "🔨 Employee update not yet implemented"}
    
    def delete_employee(self, query: str) -> dict:
        """Delete employee (HR only) - Placeholder"""
        return {"message": "🔨 Employee deletion not yet implemented"}