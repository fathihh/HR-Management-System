# main.py
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List

import google.generativeai as genai
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic.v1 import PrivateAttr
from langchain.llms.base import LLM

from config import config
from database.db_setup import init_database, check_database_exists
from agents.main_agent import MainAgent

# Email helpers used elsewhere (leave decisions etc.) — unchanged
from utils.email_utils import (
    send_leave_request_to_hr,
    send_leave_decision_to_employee,
)

# ================== NEW: stdlib email sender for OTP only ==================
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
import random


def _send_login_otp_email(to_addr: str, name: str, code: str, role: str) -> dict:
    """
    Plain-text professional OTP email for login.
    Does not affect existing payslip/leave emails (uses separate utils there).
    """
    subject = f"AUREON 360 Login Verification Code"
    body = (
        f"Dear {name or 'User'},\n\n"
        f"Your one-time verification code for {role.upper()} login is: {code}\n\n"
        f"This code is valid for 10 minutes. Do not share it with anyone.\n\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"Regards,\n"
        f"HR Systems Team\n"
        f"AUREON 360\n"
    )

    # Allow simulation for dev
    disable = os.getenv("EMAIL_DISABLE_SEND", "").lower() == "true"
    if disable:
        return {"success": True, "message": "Email simulation enabled (EMAIL_DISABLE_SEND=true)"}

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = formataddr(("AUREON 360", config.EMAIL_USER))
        msg["To"] = to_addr

        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
            server.send_message(msg)
        return {"success": True, "message": f"OTP sent to {to_addr}"}
    except Exception as e:
        return {"success": False, "message": f"OTP email error: {e}"}


# ================== /NEW ==================

# --------------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------------
app = FastAPI(title="HR Agent System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# Gemini LLM wrapper (unchanged)
# --------------------------------------------------------------------------
class GeminiLLM(LLM):
    _model: any = PrivateAttr()  # type: ignore

    def __init__(self, model, **kwargs):
        super().__init__(**kwargs)
        self._model = model

    def _call(self, prompt: str, stop=None) -> str:
        resp = self._model.generate_content(prompt)
        txt = resp.text if hasattr(resp, "text") else str(resp)
        if stop:
            for s in stop:
                txt = txt.split(s)[0]
        return txt

    def generate(self, prompt: str) -> str:
        return self._call(prompt)

    @property
    def _identifying_params(self):
        return {"name": "gemini_flash"}

    @property
    def _llm_type(self):
        return "gemini_flash"


genai.configure(api_key=config.GEMINI_API_KEY or "")
gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")
llm = GeminiLLM(gemini_model)
main_agent = MainAgent(llm)

# --------------------------------------------------------------------------
# Models (unchanged + small additions for auth)
# --------------------------------------------------------------------------
class LoginRequest(BaseModel):
    role: str
    employee_id: Optional[str] = None


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    success: bool
    response: str
    error: Optional[str] = None


class PolicyQuestion(BaseModel):
    question: str
    return_raw: Optional[bool] = False


class PolicyAnswer(BaseModel):
    success: bool
    bullets: List[str]
    error: Optional[str] = None


class LeaveApply(BaseModel):
    employee_id: int
    start_date: str  # DD-MM-YYYY or YYYY-MM-DD
    end_date: str
    days: Optional[int] = None
    reason: Optional[str] = None


class LeaveDecision(BaseModel):
    request_id: int
    decision: str  # APPROVED | REJECTED
    hr_actor: Optional[str] = "HR Portal"


# NEW: OTP payloads
class OTPRequest(BaseModel):
    role: str
    employee_id: Optional[int] = None  # required for employee role


class OTPVerify(BaseModel):
    role: str
    employee_id: Optional[int] = None
    code: str


# --------------------------------------------------------------------------
# SQLite helpers (unchanged + auth table)
# --------------------------------------------------------------------------
DB_PATH = config.DB_PATH  # e.g., "hr_employees.db"


def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def _fetchone(query, args=()):
    with _conn() as con:
        cur = con.execute(query, args)
        return cur.fetchone()


def _fetchall(query, args=()):
    with _conn() as con:
        cur = con.execute(query, args)
        return cur.fetchall()


def _execute(query, args=()):
    with _conn() as con:
        cur = con.execute(query, args)
        con.commit()
        return cur.lastrowid


def _add_column_if_missing(table: str, col: str, col_type: str):
    with _conn() as con:
        cur = con.execute(f"PRAGMA table_info({table})")
        cols = {r[1] for r in cur.fetchall()}
        if col not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            con.commit()


def _ensure_leave_tables():
    """Create baseline tables if needed and ensure flexible columns exist."""
    with _conn() as con:
        # leave_requests
        con.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            days INTEGER NOT NULL,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            decided_at TEXT
        )
        """)
        # notifications (be flexible with audience columns downstream)
        con.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # keep both 'role' and 'audience' optional and add if missing
        con.commit()

    # Add optional columns that might be required by older schemas
    _add_column_if_missing("notifications", "role", "TEXT")
    _add_column_if_missing("notifications", "audience", "TEXT")
    _add_column_if_missing("notifications", "target_role", "TEXT")

    # audit_log (context column can be nullable to avoid errors)
    with _conn() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            context TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        con.commit()


_ensure_leave_tables()


# ---- notifications: robust audience handling -------------------------------
def _notif_columns_state():
    """
    Inspect notifications table and return:
      - present audience-like columns (subset of ['role','audience','target_role'])
      - meta map of column -> {'notnull': bool}
    """
    with _conn() as con:
        cur = con.execute("PRAGMA table_info(notifications)")
        rows = cur.fetchall()  # cid, name, type, notnull, dflt_value, pk
    cols_meta = {r[1]: {"notnull": bool(r[3])} for r in rows}
    present = [c for c in ("role", "audience", "target_role") if c in cols_meta]
    if not present:
        _add_column_if_missing("notifications", "role", "TEXT")
        present = ["role"]
        cols_meta["role"] = {"notnull": False}
    return present, cols_meta


def _notify(employee_id: int, audience: str, title: str, body: str) -> None:
    """
    Insert a notification that satisfies any NOT NULL constraint on
    ['role','audience','target_role'] by setting all present columns.
    """
    present, _ = _notif_columns_state()
    insert_cols = ["employee_id", "title", "body"] + present
    placeholders = ",".join(["?"] * len(insert_cols))
    values = [employee_id, title, body] + [audience for _ in present]
    with _conn() as con:
        con.execute(
            f"INSERT INTO notifications ({','.join(insert_cols)}) VALUES ({placeholders})",
            values,
        )
        con.commit()


# --------------------------------------------------------------------------
# NEW: leaves_summary table + helpers
# --------------------------------------------------------------------------
def _ensure_leaves_summary_table():
    """Create leaves_summary if missing. This table tracks monthly leave usage per employee."""
    with _conn() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS leaves_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            total_quota INTEGER NOT NULL DEFAULT 2,
            used_leaves INTEGER NOT NULL DEFAULT 0,
            remaining_leaves INTEGER NOT NULL DEFAULT 2,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(employee_id, month, year)
        )
        """)
        con.commit()


_ensure_leaves_summary_table()


def _get_month_year(dt: datetime):
    return dt.month, dt.year


def _ensure_summary_row(employee_id: int, month: int, year: int, total_quota: int = 2):
    """
    Ensure a summary row exists for the employee/month/year.
    Default monthly quota is 2 (you can change here).
    """
    row = _fetchone(
        "SELECT id FROM leaves_summary WHERE employee_id = ? AND month = ? AND year = ?",
        (employee_id, month, year),
    )
    if not row:
        _execute(
            "INSERT INTO leaves_summary (employee_id, month, year, total_quota, used_leaves, remaining_leaves) VALUES (?, ?, ?, ?, 0, ?)",
            (employee_id, month, year, total_quota, total_quota),
        )


def _recompute_leaves_summary(employee_id: int, month: int, year: int):
    """
    Recompute used & remaining leaves for employee/month/year based on approved leaves table.
    Approved leaves are those with status = 'APPROVED' in leave_requests.
    """
    # count days from approved leave_requests overlapping that month
    rows = _fetchall(
        "SELECT start_date, end_date FROM leave_requests WHERE employee_id = ? AND status = 'APPROVED'",
        (employee_id,),
    )
    used_days = 0
    for s, e in rows:
        try:
            ds = _parse_date(s)
            de = _parse_date(e)
        except Exception:
            continue
        cur = ds
        while cur <= de:
            if cur.month == month and cur.year == year:
                used_days += 1
            cur = cur + timedelta(days=1)

    row = _fetchone("SELECT total_quota FROM leaves_summary WHERE employee_id = ? AND month = ? AND year = ?",
                    (employee_id, month, year))
    if row:
        total_quota = row[0]
    else:
        total_quota = 2
        _ensure_summary_row(employee_id, month, year, total_quota)

    remaining = max(total_quota - used_days, 0)
    with _conn() as con:
        con.execute(
            "UPDATE leaves_summary SET used_leaves = ?, remaining_leaves = ?, updated_at = CURRENT_TIMESTAMP WHERE employee_id = ? AND month = ? AND year = ?",
            (used_days, remaining, employee_id, month, year),
        )
        con.commit()


def _get_remaining_leaves(employee_id: int, month: int = None, year: int = None):
    """Return (remaining, used, quota) for given employee and month/year (defaults to current month)."""
    now = datetime.utcnow()
    if month is None or year is None:
        month, year = _get_month_year(now)
    _ensure_summary_row(employee_id, month, year)
    _recompute_leaves_summary(employee_id, month, year)
    row = _fetchone("SELECT remaining_leaves, used_leaves, total_quota FROM leaves_summary WHERE employee_id = ? AND month = ? AND year = ?",
                    (employee_id, month, year))
    if not row:
        return {"remaining": 0, "used": 0, "quota": 2}
    return {"remaining": row[0], "used": row[1], "quota": row[2]}


# --------------------------------------------------------------------------
# date utils (unchanged)
# --------------------------------------------------------------------------
def _parse_date(d: str) -> datetime:
    d = d.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(d, fmt)
        except ValueError:
            pass
    raise ValueError("Invalid date format. Use DD-MM-YYYY or YYYY-MM-DD.")


def _calc_days(s: str, e: str) -> int:
    ds = _parse_date(s)
    de = _parse_date(e)
    if de < ds:
        raise ValueError("End date is before start date.")
    return (de - ds).days + 1


def _employee_info(emp_id: int):
    row = _fetchone(
        "SELECT Name, Email, Department FROM employees WHERE EmpId = ?",
        (emp_id,),
    )
    if not row:
        return None
    name, email, dept = row
    return {"name": name, "email": email, "dept": dept}


def _mask_email(addr: str) -> str:
    try:
        local, domain = addr.split("@", 1)
        if len(local) <= 2:
            local_mask = local[0] + "*"
        else:
            local_mask = local[0] + "*" * (len(local) - 2) + local[-1]
        return f"{local_mask}@{domain}"
    except Exception:
        return addr


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "HR Agent System API",
        "status": "running",
        "database": check_database_exists(),
    }


# ================== NEW: OTP AUTH ENDPOINTS (non-breaking) =================
@app.post("/api/auth/request-otp")
async def auth_request_otp(payload: OTPRequest):
    """
    Step 1: request OTP.
    - employee role: looks up email by EmpId and sends OTP there.
    - hr role: sends OTP to configured HR mailbox (config.EMAIL_USER).
    """
    role = (payload.role or "").lower()
    if role not in ("hr", "employee"):
        raise HTTPException(status_code=400, detail="Invalid role")

    if role == "employee":
        if not payload.employee_id:
            raise HTTPException(status_code=400, detail="Employee ID required")
        info = _employee_info(int(payload.employee_id))
        if not info or not info.get("email"):
            raise HTTPException(status_code=404, detail="Employee or email not found")
        to_email = info["email"]
        display_name = info["name"] or f"Employee {payload.employee_id}"
    else:
        # HR OTP goes to configured HR mailbox
        to_email = config.EMAIL_USER
        display_name = "HR"

    # generate 6-digit code, valid 10 mins
    code = f"{random.randint(100000, 999999)}"
    expires = (datetime.utcnow() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

    _execute(
        "INSERT INTO login_otps (role, employee_id, email, code, expires_at) VALUES (?, ?, ?, ?, ?)",
        (role.upper(), payload.employee_id, to_email, code, expires),
    )

    send_res = _send_login_otp_email(to_email, display_name, code, role)
    mask = _mask_email(to_email)

    # If EMAIL_DISABLE_SEND=true, include dev-only code to help testing
    dev_hint = os.getenv("EMAIL_DISABLE_SEND", "").lower() == "true"
    return {
        "success": True,
        "message": f"OTP sent to {mask}",
        **({"dev_code": code} if dev_hint else {}),  # appears only in dev mode
    }


@app.post("/api/auth/verify-otp")
async def auth_verify_otp(payload: OTPVerify):
    """
    Step 2: verify OTP. If valid, frontend proceeds to call /api/login
    to set context (kept unchanged).
    """
    role = (payload.role or "").lower()
    if role not in ("hr", "employee"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if not payload.code or len(payload.code.strip()) < 4:
        raise HTTPException(status_code=400, detail="Invalid code")

    if role == "employee":
        if not payload.employee_id:
            raise HTTPException(status_code=400, detail="Employee ID required")
        args = (role.upper(), payload.employee_id, payload.code.strip())
        row = _fetchone(
            "SELECT id, expires_at, tries, used FROM login_otps "
            "WHERE role = ? AND employee_id = ? AND code = ? "
            "ORDER BY id DESC LIMIT 1",
            args,
        )
    else:
        args = (role.upper(), config.EMAIL_USER, payload.code.strip())
        row = _fetchone(
            "SELECT id, expires_at, tries, used FROM login_otps "
            "WHERE role = ? AND email = ? AND code = ? "
            "ORDER BY id DESC LIMIT 1",
            args,
        )

    if not row:
        raise HTTPException(status_code=400, detail="Code not found")

    otp_id, expires_at, tries, used = row
    if used:
        raise HTTPException(status_code=400, detail="Code already used")

    # expiry check
    try:
        if datetime.utcnow() > datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S"):
            raise HTTPException(status_code=400, detail="Code expired")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid code expiry")

    # increment tries and mark used
    with _conn() as con:
        con.execute("UPDATE login_otps SET tries = tries + 1, used = 1 WHERE id = ?", (otp_id,))
        con.commit()

    return {"success": True, "message": "OTP verified"}


# ================== /NEW =================

@app.post("/api/login")
async def login(request: LoginRequest):
    if request.role not in ["hr", "employee"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    if request.role == "employee" and not request.employee_id:
        raise HTTPException(status_code=400, detail="Employee ID required")
    main_agent.set_user(
        user_id=request.employee_id if request.role == "employee" else None,
        user_role=request.role,
    )
    return {
        "success": True,
        "message": f"Logged in as {request.role}",
        "user_id": request.employee_id,
        "role": request.role,
    }


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    if not request.question:
        raise HTTPException(status_code=400, detail="Question is required")
    try:
        response = main_agent.query(request.question)
        return QueryResponse(success=True, response=response)
    except Exception as e:
        return QueryResponse(success=False, response="", error=str(e))


@app.post("/api/upload/csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")
    try:
        file_path = os.path.join(config.UPLOAD_DIR, file.filename)
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        init_database(file_path)
        return {
            "success": True,
            "message": "CSV uploaded and database initialized",
            "filename": file.filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    try:
        file_path = os.path.join(config.UPLOAD_DIR, file.filename)
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        result = main_agent.policy_agent.load_pdf(file_path)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return {
            "success": True,
            "message": "PDF uploaded and processed",
            "filename": file.filename,
            "chunks": result.get("chunks", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------- Policy (bulleted) --------
@app.post("/api/policy/ask", response_model=PolicyAnswer)
async def policy_ask(payload: PolicyQuestion):
    try:
        res = main_agent.policy_agent.query(
            payload.question, return_raw=payload.return_raw or False
        )
        if "error" in res:
            return PolicyAnswer(success=False, bullets=[], error=res["error"])
        text = (res.get("answer") or "").strip()
        # remove trailing "Source:" or similar source blocks (keep answer only)
        if "Source:" in text:
            text = text.split("Source:")[0].strip()
        bullets = [ln for ln in text.splitlines() if ln.strip()]
        return PolicyAnswer(success=True, bullets=bullets)
    except Exception as e:
        return PolicyAnswer(success=False, bullets=[], error=str(e))


@app.post("/api/policy/load")
async def policy_load_existing():
    result = main_agent.policy_agent.load_existing_index()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "message": result.get("message", "Loaded")}


@app.get("/api/status")
async def status():
    return {
        "database_initialized": check_database_exists(),
        "policy_loaded": bool(getattr(main_agent.policy_agent, "is_loaded", False)),
        "current_user": main_agent.current_user_id,
        "current_role": main_agent.current_user_role,
    }


# -------- Leave module (unchanged, with small safe additions) --------
@app.post("/api/leave/apply")
async def leave_apply(payload: LeaveApply, bg: BackgroundTasks):
    try:
        emp = _employee_info(payload.employee_id)
        if not emp:
            raise HTTPException(status_code=400, detail="Employee not found")

        days = payload.days if payload.days and payload.days > 0 else _calc_days(
            payload.start_date, payload.end_date
        )

        # insert leave
        leave_id = _execute(
            "INSERT INTO leave_requests (employee_id, start_date, end_date, days, reason, status) "
            "VALUES (?, ?, ?, ?, ?, 'PENDING')",
            (payload.employee_id, payload.start_date, payload.end_date, days, payload.reason or None),
        )

        # DB notification for HR (robust audience)
        _notify(
            payload.employee_id,
            "HR",
            "New leave request",
            f"Employee {payload.employee_id} requested {days} day(s) "
            f"from {payload.start_date} to {payload.end_date}.",
        )

        # audit
        _execute(
            "INSERT INTO audit_log (action, actor, context) VALUES ('LEAVE_APPLY', ?, ?)",
            (f"EMP:{payload.employee_id}",
             f"id={leave_id}; period={payload.start_date}->{payload.end_date}; days={days}"),
        )

        # Email HR (background) — goes to configured HR mailbox
        hr_email = config.EMAIL_USER
        bg.add_task(
            send_leave_request_to_hr,
            hr_email,
            emp["name"] or f"Employee {payload.employee_id}",
            str(payload.employee_id),
            emp["dept"] or "-",
            payload.start_date,
            payload.end_date,
            days,
            payload.reason or "-",
        )

        # keep leaves_summary in sync (recompute for this month)
        try:
            s_dt = _parse_date(payload.start_date)
            month, year = _get_month_year(s_dt)
            _ensure_summary_row(payload.employee_id, month, year)
            _recompute_leaves_summary(payload.employee_id, month, year)
        except Exception:
            # don't block request on summary update — log silently
            pass

        return {"success": True, "id": leave_id, "message": "Leave request submitted"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except sqlite3.OperationalError as oe:
        raise HTTPException(status_code=400, detail=f"database error: {oe}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leave/pending")
async def leave_pending():
    rows = _fetchall(
        """
        SELECT lr.id, lr.employee_id, lr.start_date, lr.end_date, lr.days, lr.reason, e.Name, e.Department
        FROM leave_requests lr
        LEFT JOIN employees e ON e.EmpId = lr.employee_id
        WHERE lr.status = 'PENDING'
        ORDER BY lr.created_at DESC
        """
    )
    result = []
    for r in rows:
        result.append(
            {
                "id": r[0],
                "employee_id": r[1],
                "start_date": r[2],
                "end_date": r[3],
                "days": r[4],
                "reason": r[5],
                "Name": r[6],
                "Department": r[7],
            }
        )
    return result


@app.get("/api/leave/mine/{emp_id}")
async def leave_mine(emp_id: int):
    rows = _fetchall(
        """
        SELECT id, start_date, end_date, days, reason, status, created_at, decided_at
        FROM leave_requests
        WHERE employee_id = ?
        ORDER BY created_at DESC
        """,
        (emp_id,),
    )
    result = []
    for r in rows:
        result.append(
            {
                "id": r[0],
                "start_date": r[1],
                "end_date": r[2],
                "days": r[3],
                "reason": r[4],
                "status": r[5],
                "created_at": r[6],
                "decided_at": r[7],
            }
        )
    return result


@app.post("/api/leave/decide")
async def leave_decide(payload: LeaveDecision, bg: BackgroundTasks):
    try:
        decision = payload.decision.upper()
        if decision not in ("APPROVED", "REJECTED"):
            raise HTTPException(status_code=400, detail="decision must be APPROVED or REJECTED")

        row = _fetchone(
            "SELECT employee_id, start_date, end_date, days, reason, status "
            "FROM leave_requests WHERE id = ?",
            (payload.request_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")
        if row[5] != "PENDING":
            raise HTTPException(status_code=400, detail="Already decided")

        employee_id, s, e, d, reason, _ = row
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        _execute(
            "UPDATE leave_requests SET status = ?, decided_at = ? WHERE id = ?",
            (decision, now, payload.request_id),
        )

        emp = _employee_info(employee_id) or {"name": f"Emp {employee_id}", "email": None, "dept": "-"}

        # DB notification for employee (robust audience)
        _notify(
            employee_id,
            "EMPLOYEE",
            f"Leave {decision}",
            f"Your leave ({s} to {e}) has been {decision.lower()}.",
        )

        # audit
        _execute(
            "INSERT INTO audit_log (action, actor, context) VALUES ('LEAVE_DECIDE', ?, ?)",
            (payload.hr_actor or "HR", f"id={payload.request_id}; emp={employee_id}; decision={decision}"),
        )

        # email employee (background)
        if emp.get("email"):
            bg.add_task(
                send_leave_decision_to_employee,
                emp["email"],
                emp["name"],
                decision,
                s, e, d,
                reason or "-",
            )

        # update leaves_summary after decision if approved
        try:
            if decision == "APPROVED":
                s_dt = _parse_date(s)
                month, year = _get_month_year(s_dt)
                _ensure_summary_row(employee_id, month, year)
                _recompute_leaves_summary(employee_id, month, year)
        except Exception:
            pass

        return {"success": True, "message": f"Request {payload.request_id} {decision.lower()}"}
    except sqlite3.OperationalError as oe:
        raise HTTPException(status_code=400, detail=f"database error: {oe}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------- Notifications (employee or HR) --------
@app.get("/api/notifications/{emp_id}")
async def notifications(emp_id: int, role: str = Query("EMPLOYEE")):
    role = role.upper()
    if role not in ("EMPLOYEE", "HR"):
        raise HTTPException(status_code=400, detail="role must be EMPLOYEE or HR")
    if role == "HR":
        rows = _fetchall(
            "SELECT id, title, body, created_at FROM notifications "
            "WHERE (role = 'HR' OR audience = 'HR' OR target_role = 'HR' OR role IS NULL) "
            "ORDER BY id DESC LIMIT 20"
        )
    else:
        rows = _fetchall(
            "SELECT id, title, body, created_at FROM notifications "
            "WHERE employee_id = ? AND (role = 'EMPLOYEE' OR audience = 'EMPLOYEE' OR target_role = 'EMPLOYEE' OR role IS NULL) "
            "ORDER BY id DESC LIMIT 20",
            (emp_id,),
        )
    return [{"id": r[0], "title": r[1], "body": r[2], "created_at": r[3]} for r in rows]


# -------------------- NEW: chat endpoint for simple intents --------------------
@app.post("/api/chat/message")
async def chat_message(
    message: dict = Body(...),
    bg: BackgroundTasks = None
):
    """
    Body: { "role": "employee" | "hr", "employee_id": 123, "text": "..." }
    Recognized intents:
     - "how many leaves left" => returns monthly remaining leaves
     - "apply leave from YYYY-MM-DD to YYYY-MM-DD for <reason>" => attempts to create leave
    This is deterministic, safe, and uses your existing DB logic / email hooks.
    """
    try:
        role = (message.get("role") or "").lower()
        text = (message.get("text") or "").strip()
        emp_id = message.get("employee_id")

        if role not in ("employee", "hr"):
            return {"success": False, "message": "role must be 'employee' or 'hr'"}

        # Intent: leaves left
        if "how many leave" in text.lower() or "how many leaves left" in text.lower():
            if not emp_id:
                return {"success": False, "message": "employee_id required for leave queries"}
            res = _get_remaining_leaves(int(emp_id))
            return {
                "success": True,
                "type": "leaves_info",
                "message": f"You have {res['remaining']} leave(s) left this month (used {res['used']} of {res['quota']}).",
                "data": res
            }

        # Intent: apply leave via chat (very tolerant pattern)
        import re
        m = re.search(r"apply\s+leave\s+(?:from\s*)?([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}-[0-9]{2}-[0-9]{4})\s*(?:to|-)\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}-[0-9]{2}-[0-9]{4})(?:\s+for\s+(.*))?", text, flags=re.I)
        if m:
            if not emp_id:
                return {"success": False, "message": "employee_id required to apply leave"}
            start = m.group(1).strip()
            end = m.group(2).strip()
            reason = (m.group(3) or "").strip() or "Requested via chat"

            # compute days
            days = None
            try:
                days = _calc_days(start, end)
            except Exception as e:
                return {"success": False, "message": f"Date parse error: {e}"}

            # insert leave request
            try:
                leave_id = _execute(
                    "INSERT INTO leave_requests (employee_id, start_date, end_date, days, reason, status) VALUES (?, ?, ?, ?, ?, 'PENDING')",
                    (emp_id, start, end, days, reason)
                )
                # DB notification and audit (same as leave_apply)
                _notify(emp_id, "HR", "New leave request", f"Employee {emp_id} requested {days} day(s) from {start} to {end}")
                _execute("INSERT INTO audit_log (action, actor, context) VALUES ('LEAVE_APPLY_CHAT', ?, ?)",
                         (f"EMP:{emp_id}", f"id={leave_id}; period={start}->{end}; days={days}"))

                # email HR in background if bg provided
                hr_email = config.EMAIL_USER
                emp_info = _employee_info(int(emp_id)) or {"name": f"Employee {emp_id}", "dept": "-"}
                if bg is not None:
                    bg.add_task(send_leave_request_to_hr, hr_email, emp_info.get("name"), str(emp_id), emp_info.get("dept"), start, end, days, reason)
                else:
                    try:
                        send_leave_request_to_hr(hr_email, emp_info.get("name"), str(emp_id), emp_info.get("dept"), start, end, days, reason)
                    except Exception:
                        pass

                # recompute summary row safely
                try:
                    s_dt = _parse_date(start)
                    month, year = _get_month_year(s_dt)
                    _ensure_summary_row(emp_id, month, year)
                    _recompute_leaves_summary(emp_id, month, year)
                except Exception:
                    pass

                return {"success": True, "type": "leave_applied", "message": f"Leave submitted (id={leave_id}) and pending approval."}
            except Exception as e:
                return {"success": False, "message": f"Error applying leave: {e}"}

        # default: fallback to main_agent.query for general chat
        try:
            ans = main_agent.query(text)
            # strip any "Source:" trailing content if present
            if isinstance(ans, str) and "Source:" in ans:
                ans = ans.split("Source:")[0].strip()
            return {"success": True, "type": "general", "message": ans}
        except Exception as e:
            return {"success": False, "message": f"Agent error: {e}"}

    except Exception as e:
        return {"success": False, "message": str(e)}


# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    print("🚀 Starting HR Agent System API...")
    print(f"📊 Database: {config.DB_PATH}")
    print(f"📁 Uploads:  {config.UPLOAD_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
