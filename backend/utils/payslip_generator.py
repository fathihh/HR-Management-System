# utils/payslip_generator.py - FIXED VERSION

import os
import sqlite3
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from database.db_setup import get_employee_id_column
from config import config

def generate_payslip_text(emp_id: str):
    """Generate text-based payslip"""
    
    col_id = get_employee_id_column()
    
    try:
        conn = sqlite3.connect(config.DB_PATH)
        query = f"SELECT * FROM employees WHERE {col_id}=?"
        df = pd.read_sql(query, conn, params=(emp_id,))
        conn.close()
        
        if df.empty:
            return None, f"❌ Employee {emp_id} not found in database"
        
        data = df.iloc[0].to_dict()
        
        monthly_income = float(data.get('MonthlyIncome', 0))
        basic = monthly_income * 0.5
        hra = monthly_income * 0.2
        allowances = monthly_income * 0.3
        
        payslip_text = f"""
╔═══════════════════════════════════════════════════════╗
║              COMPANY XYZ - PAYSLIP                    ║
╚═══════════════════════════════════════════════════════╝

─────────────────────────────────────────────────────────
EMPLOYEE DETAILS
─────────────────────────────────────────────────────────
Employee ID:      {data.get('EmployeeNumber', emp_id)}
Name:             {data.get('Name', 'N/A')}
Department:       {data.get('Department', 'N/A')}
Job Role:         {data.get('JobRole', 'N/A')}
Email:            {data.get('email', 'N/A')}

─────────────────────────────────────────────────────────
SALARY BREAKDOWN
─────────────────────────────────────────────────────────
Basic Salary:     ₹{basic:,.2f}
HRA (20%):        ₹{hra:,.2f}
Allowances (30%): ₹{allowances:,.2f}
                  ─────────────
GROSS SALARY:     ₹{monthly_income:,.2f}

─────────────────────────────────────────────────────────
ADDITIONAL INFORMATION
─────────────────────────────────────────────────────────
Total Experience: {data.get('TotalWorkingYears', 0)} years
Overtime:         {data.get('OverTime', 'No')}
Payment Month:    {datetime.now().strftime('%B %Y')}

─────────────────────────────────────────────────────────
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
This is a computer-generated document.
─────────────────────────────────────────────────────────
"""
        
        os.makedirs("generated_payslips", exist_ok=True)
        filename = f"generated_payslips/payslip_{emp_id}_{datetime.now().strftime('%Y%m%d')}.txt"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(payslip_text)
        
        return filename, f"✅ Text payslip generated: {filename}"
    
    except Exception as e:
        return None, f"❌ Error generating text payslip: {str(e)}"


def generate_payslip_pdf(emp_id: str, month: str = None, salary: float = None):
    """Generate PDF payslip"""
    
    col_id = get_employee_id_column()
    
    try:
        conn = sqlite3.connect(config.DB_PATH)
        query = f"SELECT * FROM employees WHERE {col_id}=?"
        df = pd.read_sql(query, conn, params=(emp_id,))
        conn.close()
        
        if df.empty:
            return None, f"❌ Employee {emp_id} not found in database"
        
        data = df.iloc[0].to_dict()
        
        if month is None:
            month = datetime.now().strftime('%B %Y')
        if salary is None:
            salary = float(data.get('MonthlyIncome', 0))
        
        basic = salary * 0.5
        hra = salary * 0.2
        allowances = salary * 0.3
        
        os.makedirs("generated_payslips", exist_ok=True)
        
        filename = f"generated_payslips/payslip_{emp_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter
        
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(width/2, height - 50, "COMPANY XYZ")
        
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height - 80, "EMPLOYEE PAYSLIP")
        
        c.line(50, height - 100, width - 50, height - 100)
        
        y_position = height - 140
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "EMPLOYEE DETAILS")
        
        y_position -= 25
        c.setFont("Helvetica", 11)
        
        employee_details = [
            ("Employee ID:", data.get('EmployeeNumber', emp_id)),
            ("Name:", data.get('Name', 'N/A')),
            ("Department:", data.get('Department', 'N/A')),
            ("Job Role:", data.get('JobRole', 'N/A')),
            ("Email:", data.get('email', 'N/A')),
            ("Payment Month:", month),
        ]
        
        for label, value in employee_details:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(70, y_position, label)
            c.setFont("Helvetica", 10)
            c.drawString(200, y_position, str(value))
            y_position -= 20
        
        y_position -= 30
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "SALARY BREAKDOWN")
        
        y_position -= 25
        c.setFont("Helvetica-Bold", 11)
        c.drawString(70, y_position, "Description")
        c.drawString(400, y_position, "Amount (₹)")
        
        y_position -= 5
        c.line(70, y_position, width - 70, y_position)
        
        y_position -= 20
        c.setFont("Helvetica", 10)
        
        salary_items = [
            ("Basic Salary (50%)", basic),
            ("House Rent Allowance (20%)", hra),
            ("Other Allowances (30%)", allowances),
        ]
        
        for description, amount in salary_items:
            c.drawString(70, y_position, description)
            c.drawRightString(width - 70, y_position, f"₹{amount:,.2f}")
            y_position -= 20
        
        y_position -= 5
        c.line(70, y_position, width - 70, y_position)
        
        y_position -= 20
        c.setFont("Helvetica-Bold", 12)
        c.drawString(70, y_position, "GROSS SALARY")
        c.drawRightString(width - 70, y_position, f"₹{salary:,.2f}")
        
        y_position -= 50
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y_position, "ADDITIONAL INFORMATION")
        
        y_position -= 25
        c.setFont("Helvetica", 10)
        
        additional_info = [
            ("Total Experience:", f"{data.get('TotalWorkingYears', 0)} years"),
            ("Overtime Eligible:", data.get('OverTime', 'No')),
            ("Work-Life Balance:", data.get('WorkLifeBalance', 'N/A')),
        ]
        
        for label, value in additional_info:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(70, y_position, label)
            c.setFont("Helvetica", 9)
            c.drawString(220, y_position, str(value))
            y_position -= 18
        
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(50, 120, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawString(50, 105, "This is a computer-generated document and does not require a signature.")
        
        c.rect(30, 30, width - 60, height - 60)
        
        c.showPage()
        c.save()
        
        return filename, f"✅ PDF payslip generated: {filename}"
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"❌ Error generating PDF payslip: {str(e)}"