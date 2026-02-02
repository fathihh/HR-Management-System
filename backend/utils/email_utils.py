# utils/email_utils.py
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

from config import config

SENDER_DISPLAY = "AUREON 360 HR"
SENDER_ADDR = config.EMAIL_USER

# If true, we simulate instead of actually sending (useful in dev)
EMAIL_DISABLE_SEND = os.getenv("EMAIL_DISABLE_SEND", "true").lower() in {"1", "true", "yes"}

def _send_plain_email(to_address: str, subject: str, body: str, attachment_path: str | None = None):
    """
    Send a professional plain-text email with optional attachment.
    Honors EMAIL_DISABLE_SEND for safe local testing.
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{SENDER_DISPLAY} <{SENDER_ADDR}>"
        msg["To"] = to_address
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain", _charset="utf-8"))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{os.path.basename(attachment_path)}"'
                )
                msg.attach(part)

        if EMAIL_DISABLE_SEND:
            # Simulate a successful send in development.
            return {
                "success": True,
                "message": "Email simulated (EMAIL_DISABLE_SEND=true)",
                "to": to_address,
                "subject": subject,
            }

        server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=30)
        server.starttls()
        server.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        return {"success": True, "message": f"Email sent to {to_address}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ----------------- Public helpers your app calls -----------------

def send_payslip_email(emp_id: str, email: str, payslip_path: str, employee_name: str | None = None):
    """
    Professional plain-text payslip message with attachment.
    Signature kept the same as your existing code path.
    """
    display_name = employee_name or f"Employee {emp_id}"
    subject = f"Payslip for {display_name}"
    body = (
        f"Dear {display_name},\n\n"
        "Please find attached your payslip.\n\n"
        "If you have any questions, please reply to this email or contact HR.\n\n"
        "Regards,\n"
        "AUREON 360 HR\n"
        "Smarter workflows. Happier teams.\n"
    )
    return _send_plain_email(email, subject, body, payslip_path)


def send_leave_request_to_hr(
    hr_email: str,
    employee_name: str,
    employee_id: str,
    department: str,
    start_date: str,
    end_date: str,
    days: int,
    reason: str,
):
    """
    Professional plain-text notification to HR when an employee applies for leave.
    """
    subject = f"Leave request submitted: Emp {employee_id} | {start_date} → {end_date} ({days} day{'s' if days != 1 else ''})"
    submitted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    body = (
        "Dear HR Team,\n\n"
        "A new leave request has been submitted in AUREON 360.\n\n"
        f"Employee: {employee_name} (ID {employee_id})\n"
        f"Department: {department}\n"
        f"Period: {start_date} to {end_date} ({days} day{'s' if days != 1 else ''})\n"
        f"Reason: {reason}\n\n"
        "Action required:\n"
        "Please review this request in the HR Portal (Approvals tab) and approve or reject as appropriate.\n\n"
        f"Submitted: {submitted_at}\n\n"
        "Regards,\n"
        "AUREON 360 Notifications\n"
        "Smarter workflows. Happier teams.\n"
        "(This is an automated message.)\n"
    )
    return _send_plain_email(hr_email, subject, body)


def send_leave_decision_to_employee(
    employee_email: str,
    employee_name: str,
    decision: str,   # "APPROVED" or "REJECTED"
    start_date: str,
    end_date: str,
    days: int,
    reason: str,
):
    """
    Professional plain-text message to employee when HR approves or rejects.
    """
    verb = "approved" if decision.upper() == "APPROVED" else "rejected"
    subject = f"Your leave request has been {verb}"
    decided_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    body = (
        f"Dear {employee_name},\n\n"
        f"Your leave request has been {verb}.\n\n"
        f"Period: {start_date} to {end_date} ({days} day{'s' if days != 1 else ''})\n"
        f"Reason (as submitted): {reason}\n"
        f"Decision time: {decided_at}\n\n"
        "If you have follow-up questions, please reply to this email or contact HR.\n\n"
        "Regards,\n"
        "AUREON 360 HR\n"
        "Smarter workflows. Happier teams.\n"
        "(This is an automated message.)\n"
    )
    return _send_plain_email(employee_email, subject, body)
