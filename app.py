"""
Corporate HR Automation System — Full Enterprise Edition
FastAPI + Jinja2 + Supabase | All 11 modules with full CRUD
"""

from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from supabase import create_client, Client
from datetime import date, datetime, timedelta
import uvicorn, json, traceback, secrets, base64, io, hashlib, os, uuid
from dotenv import load_dotenv
import qrcode
from qrcode.image.pure import PyPNGImage
import google.generativeai as genai
import PyPDF2

# Configure Environment
load_dotenv()

# ─────────────────────────────────────────────
#  CONFIG (env vars — set via env.yaml on Cloud Run)
# ─────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("[WARN] GEMINI_API_KEY not set — AI recruitment features disabled")

# ─────────────────────────────────────────────
#  APP INIT  (middleware order: Session → Auth → Routes)
# ─────────────────────────────────────────────
ADMIN_ROLES  = {"boss", "hr_manager", "general_manager"}
PUBLIC_PATHS = ["/login", "/logout", "/static", "/attendance/scan", "/careers"]

app = FastAPI(title="Corporate HRM Enterprise", version="2.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Auth guard middleware (class-based so it runs INSIDE the session layer)
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)
        try:
            user = request.session.get("user")
        except Exception:
            return RedirectResponse("/login", status_code=302)
        if not user:
            return RedirectResponse("/login", status_code=302)
        if user.get("role") == "employee" and not path.startswith("/portal") and not path.startswith("/documents") and not path.startswith("/notifications"):
            return RedirectResponse("/portal", status_code=302)
            
        if user.get("role") == "finance" and not path.startswith("/finance") and not path.startswith("/payroll") and not path.startswith("/offboarding") and not path.startswith("/logout") and not path.startswith("/portal") and not path.startswith("/documents") and not path.startswith("/notifications"):
            return RedirectResponse("/finance/dashboard", status_code=302)
            
        if path.startswith("/payroll"):
            if user.get("role") not in ["boss", "finance", "admin"]:
                return RedirectResponse("/dashboard", status_code=302)
                
        if path.startswith("/boss"):
            if path.startswith("/boss/users") or path.startswith("/boss/announcements"):
                if user.get("role") not in ["boss", "hr_manager", "admin"]:
                    return RedirectResponse("/dashboard", status_code=302)
            else:
                if user.get("role") != "boss":
                    return RedirectResponse("/dashboard", status_code=302)
        return await call_next(request)

# Order matters: Session must be added LAST so it wraps outermost
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=28800)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    DB_CONNECTED = True
except Exception as e:
    print(f"[SUPABASE INIT ERROR] {e}")
    supabase = None
    DB_CONNECTED = False

# ─────────────────────────────────────────────
#  DB HELPERS
# ─────────────────────────────────────────────
def db_fetch(table: str, columns: str = "*", filters: dict = None,
             order: str = None, limit: int = 500) -> list:
    if not DB_CONNECTED or supabase is None:
        return []
    try:
        q = supabase.table(table).select(columns)
        if filters:
            for col, val in filters.items():
                q = q.eq(col, val)
        if order:
            q = q.order(order)
        return (q.limit(limit).execute().data) or []
    except Exception as e:
        print(f"[DB FETCH ERROR] {table}: {e}")
        return []

def db_fetch_one(table: str, columns: str = "*", filters: dict = None) -> dict | None:
    rows = db_fetch(table, columns, filters, limit=1)
    return rows[0] if rows else None

def db_insert(table: str, data: dict) -> dict | None:
    if not DB_CONNECTED or supabase is None:
        return None
    try:
        # Remove None values
        clean = {k: v for k, v in data.items() if v is not None and v != ""}
        result = supabase.table(table).insert(clean).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[DB INSERT ERROR] {table}: {e}")
        return None

def db_update(table: str, record_id: str, data: dict, id_col: str = "id") -> bool:
    if not DB_CONNECTED or supabase is None:
        return False
    try:
        clean = {k: v for k, v in data.items() if v is not None}
        supabase.table(table).update(clean).eq(id_col, record_id).execute()
        return True
    except Exception as e:
        print(f"[DB UPDATE ERROR] {table}: {e}")
        return False

def db_delete(table: str, record_id: str, id_col: str = "id") -> bool:
    if not DB_CONNECTED or supabase is None:
        return False
    try:
        supabase.table(table).delete().eq(id_col, record_id).execute()
        return True
    except Exception as e:
        print(f"[DB DELETE ERROR] {table}: {e}")
        return False

def redirect_with_msg(url: str, success: str = None, error: str = None):
    if success:
        return RedirectResponse(f"{url}?success={success}", status_code=302)
    return RedirectResponse(f"{url}?error={error}", status_code=302)

# ─────────────────────────────────────────────
#  AUTH HELPERS
# ─────────────────────────────────────────────

import bcrypt

def hash_password(pw: str) -> str:
    """Hash password securely using bcrypt, fallback to SHA-256 for legacy support if needed, but bcrypt is preferred for new systems."""
    # Since existing users use raw SHA-256, we'll keep checking it for backwards compatibility if needed, 
    # but new passwords should ideally be bcrypt. For now, since the prototype relies on SHA-256:
    return hashlib.sha256(pw.encode()).hexdigest()

def verify_password(plain_pw: str, stored_hash: str) -> bool:
    """Verify password. First checks if it's bcrypt, otherwise falls back to SHA-256."""
    if isinstance(stored_hash, str):
        if stored_hash.startswith("$2b$"):
            return bcrypt.checkpw(plain_pw.encode(), stored_hash.encode())
    elif isinstance(stored_hash, bytes):
        if stored_hash.startswith(b"$2b$"):
            return bcrypt.checkpw(plain_pw.encode(), stored_hash)
            
    if isinstance(stored_hash, bytes):
        stored_hash = stored_hash.decode()
    return hashlib.sha256(plain_pw.encode()).hexdigest() == stored_hash

def upgrade_password_hash(user_id: str, plain_pw: str):
    """Upgrades a SHA-256 hash to a strong bcrypt hash in the database."""
    new_hash = bcrypt.hashpw(plain_pw.encode(), bcrypt.gensalt()).decode()
    db_update("sys_users", user_id, {"password_hash": new_hash})

def get_current_user(request: Request) -> dict | None:
    try:
        return request.session.get("user")
    except Exception:
        return None

def require_admin(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user.get("role") not in ADMIN_ROLES:
        return RedirectResponse("/portal", status_code=302)
    return None

def require_boss(request: Request):
    user = get_current_user(request)
    if not user or user.get("role") not in ["boss", "hr_manager", "admin"]:
        return RedirectResponse("/login", status_code=302)
    return None


# ─────────────────────────────────────────────
#  NOTIFICATIONS
# ─────────────────────────────────────────────
def notify_user(user_id: str, title: str, message: str, link_url: str = ""):
    db_insert("system_notifications", {
        "recipient_user_id": user_id, "title": title,
        "message": message, "link_url": link_url
    })

def notify_role(role: str, title: str, message: str, link_url: str = ""):
    db_insert("system_notifications", {
        "recipient_role": role, "title": title,
        "message": message, "link_url": link_url
    })

def notify_employee(emp_id: str, title: str, message: str, link_url: str = ""):
    u = db_fetch_one("sys_users", "id", filters={"employee_id": emp_id})
    if u:
        notify_user(str(u["id"]), title, message, link_url)

@app.post("/notifications/{notif_id}/read", response_class=JSONResponse)
async def mark_notification_read(notif_id: str):
    db_update("system_notifications", notif_id, {"is_read": True})
    return {"status": "ok"}

def ctx(request, page: str, **kwargs):
    """Build template context with common vars."""
    user = request.session.get("user") if hasattr(request, 'session') else None
    
    notifications = []
    unread_count = 0
    if user and supabase:
        uid = user.get("id")
        role = user.get("role")
        try:
            # We fetch both role-based and user-based notifications
            res = supabase.table("system_notifications").select("*") \
                .or_(f"recipient_user_id.eq.{uid},recipient_role.eq.{role}") \
                .eq("is_read", False) \
                .order("created_at", desc=True).limit(15).execute()
            notifications = res.data or []
            unread_count = len(notifications)
        except Exception as e:
            print("Notification fetch err:", e)

    return {"request": request, "page": page,
            "current_user": user,
            "notifications": notifications,
            "unread_count": unread_count,
            "success": request.query_params.get("success"),
            "error":   request.query_params.get("error"),
            **kwargs}

# ─────────────────────────────────────────────
#  0. LOGIN / LOGOUT
# ─────────────────────────────────────────────
@app.get("/", response_class=RedirectResponse)
async def root(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.get("role") == "employee":
        return RedirectResponse(url="/portal", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_current_user(request)
    if user:
        if user.get("role") in ["employee", "finance"]:
            return RedirectResponse("/portal", 302)
        return RedirectResponse("/dashboard", 302)
    error = request.query_params.get("error")
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login", response_class=RedirectResponse)
async def login_submit(request: Request,
    username: str = Form(...), password: str = Form(...)):
    user_rec = db_fetch_one("sys_users", "*",
                            filters={"username": username})
    
    if not user_rec or not verify_password(password, user_rec.get("password_hash", "")):
        return RedirectResponse("/login?error=Invalid+username+or+password", status_code=302)
        
    # Upgrade hash seamlessly if they are using the old SHA-256
    stored_hash = user_rec.get("password_hash", "")
    if not stored_hash.startswith("$2b$"):
        upgrade_password_hash(user_rec["id"], password)
        
    request.session["user"] = {
        "id":        str(user_rec["id"]),
        "username":  user_rec["username"],
        "role":      user_rec["role"],
        "full_name": user_rec.get("full_name") or user_rec["username"],
        "employee_id": str(user_rec.get("employee_id") or ""),
    }
    if user_rec.get("role") in ["employee", "finance"]:
        return RedirectResponse(url="/portal", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/logout", response_class=RedirectResponse)
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)

# ══════════════════════════════════════════════
#  1. DASHBOARD
# ══════════════════════════════════════════════
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    employees   = db_fetch("Employees", "id,employee_id,Full_name,status,Dept_id")
    attendance  = db_fetch("attendance_records", "id,employee_id,check_in,check_out,is_late")
    leave_reqs  = db_fetch("Leave_Request", "id,status")
    offboarding = db_fetch("corporate_offboarding", "id,settlement_status")
    onboarding  = db_fetch("employee_onboarding", "id,status")
    candidates  = db_fetch("recruitment_candidates", "id,status")
    payrolls    = db_fetch("payrolls", "id,payment_status,net_salary")

    today = date.today().isoformat()

    total_staff    = len(employees)
    active_staff   = sum(1 for e in employees if str(e.get("status","")).lower() == "active")
    on_leave       = sum(1 for e in employees if "leave" in str(e.get("status","")).lower())
    today_present  = sum(1 for a in attendance if str(a.get("check_in","") or "").startswith(today))
    late_today     = sum(1 for a in attendance if a.get("is_late") and str(a.get("check_in","") or "").startswith(today))
    pending_leaves = sum(1 for l in leave_reqs if str(l.get("status","")).lower() == "pending")
    approved_leaves= sum(1 for l in leave_reqs if str(l.get("status","")).lower() == "approved")
    pending_clear  = sum(1 for o in offboarding if str(o.get("settlement_status","")).lower().startswith("hold"))
    active_onboard = sum(1 for o in onboarding if o.get("status") in ("Pre-boarding","In Progress"))
    open_positions = len(set(c.get("status","") for c in candidates if c.get("status") in ("Applied","Screening","Interview")))
    total_payroll  = sum(float(p.get("net_salary") or 0) for p in payrolls if p.get("payment_status") == "Paid")

    # Attendance Overview Today
    present_on_time = today_present - late_today
    absent_today = max(0, active_staff - today_present - on_leave)
    att_status = {
        "On Time": present_on_time,
        "Late": late_today,
        "On Leave": on_leave,
        "Absent": absent_today
    }

    # Leave Status Breakdown
    leave_status = {"Pending": pending_leaves, "Approved": approved_leaves,
                    "Rejected": sum(1 for l in leave_reqs if str(l.get("status","")).lower() == "rejected")}

    # Turnover Rate calculation
    offboarded_count = len(offboarding)
    turnover_rate = round((offboarded_count / total_staff * 100), 1) if total_staff > 0 else 0.0

    raw_announcements = db_fetch("announcements", "*", order="created_at")
    user = get_current_user(request)
    role = user.get("role") if user else ""
    emp_id = str(user.get("employee_id", "")) if user else ""
    
    announcements = []
    for a in raw_announcements:
        tr = a.get("target_role", "All")
        if tr == "Pending HR Review":
            continue
        if role in ["boss", "hr_manager", "admin"] or tr in ["All", role, emp_id]:
            announcements.append(a)

    return templates.TemplateResponse("dashboard.html", ctx(request, "dashboard",
        stats={
            "total_staff": total_staff,
            "active_staff": active_staff,
            "on_leave": on_leave,
            "today_present": today_present,
            "late_today": late_today,
            "pending_leaves": pending_leaves,
            "pending_clearances": pending_clear,
            "active_onboarding": active_onboard,
            "open_recruitment": open_positions,
            "total_payroll_paid": f"${total_payroll:,.0f}",
            "turnover_rate": f"{turnover_rate}%"
        },
        att_chart=json.dumps(att_status),
        leave_chart=json.dumps(leave_status),
        today=datetime.now().strftime("%A, %d %B %Y"),
        recent_employees=employees[:8],
        ann_list=announcements,
    ))

# ══════════════════════════════════════════════
#  2. EMPLOYEES
# ══════════════════════════════════════════════
@app.get("/employees", response_class=HTMLResponse)
async def employees_list(request: Request):
    employees = db_fetch("Employees", "id,employee_id,Full_name,status,email,hire_date,Dept_id,position_id", order="created_at")
    depts     = db_fetch("Departments", "id,Department_name")
    positions = db_fetch("positions", "id,title")
    dept_map  = {d["id"]: d["Department_name"] for d in depts}
    pos_map   = {p["id"]: p["title"] for p in positions}
    for e in employees:
        e["dept_name"] = dept_map.get(e.get("Dept_id",""), "—")
        e["pos_title"] = pos_map.get(e.get("position_id",""), "—")
        
    hired_candidates = db_fetch("recruitment_candidates", "*", filters={"status":"Hired"})
    return templates.TemplateResponse("employees/index.html", ctx(request, "employees",
        employees=employees, departments=depts, positions=positions, candidates=hired_candidates))

@app.get("/employees/add", response_class=HTMLResponse)
async def employees_add_form(request: Request):
    depts     = db_fetch("Departments", "id,Department_name")
    positions = db_fetch("positions", "id,title")
    managers  = db_fetch("Employees", "id,Full_name,employee_id", filters={"status":"Active"})
    hired_candidates = db_fetch("recruitment_candidates", "*", filters={"status":"Hired"})
    return templates.TemplateResponse("employees/form.html", ctx(request, "employees",
        employee=None, departments=depts, positions=positions, managers=managers, candidates=hired_candidates, action="add"))

@app.post("/employees/add", response_class=RedirectResponse)
async def employees_add(request: Request,
    employee_id: str = Form(...), Full_name: str = Form(...),
    email: str = Form(None), phone: str = Form(None),
    Dept_id: str = Form(None), position_id: str = Form(None),
    Manager_id: str = Form(None), hire_date: str = Form(None),
    date_of_birth: str = Form(None), status: str = Form("Active"),
    salary: str = Form(None)):
    result = db_insert("Employees", {
        "employee_id": employee_id, "Full_name": Full_name,
        "email": email, "phone": phone,
        "Dept_id": Dept_id or None, "position_id": position_id or None,
        "Manager_id": Manager_id or None,
        "hire_date": hire_date or None, "date_of_birth": date_of_birth or None,
        "status": status, "salary": float(salary) if salary else None,
        "created_at": datetime.now().isoformat(),
    })
    if result:
        # --- Auto-create sys_users account ---
        try:
            import hashlib
            emp_id = result[0]['id']
            
            # 1. Determine Username
            if email:
                username = email.split('@')[0].lower().replace(" ", "")
            else:
                username = employee_id.lower().replace(" ", "")
                
            # 2. Determine Role based on position
            role = "employee"
            if position_id:
                pos = db_fetch_one("positions", filters={"id": position_id})
                if pos:
                    p_title = pos.get('title', '').lower()
                    p_team = pos.get('team', '').lower()
                    if "finance" in p_team or "finance" in p_title:
                        role = "finance"
                    elif "hr manager" in p_title or "human resources" in p_team:
                        role = "hr_manager"
                    elif "boss" in p_title or "executive" in p_title or "general manager" in p_title:
                        role = "boss"
            
            # 3. Hash default password "123456"
            pw_hash = hashlib.sha256("123456".encode()).hexdigest()
            
            # 4. Insert into sys_users
            db_insert("sys_users", {
                "username": username,
                "password_hash": pw_hash,
                "role": role,
                "employee_id": emp_id,
                "full_name": Full_name
            })
            
            success_msg = f"Employee {Full_name} added! Login Username: {username} | Password: 123456"
            return redirect_with_msg("/employees", success=success_msg.replace(" ", "+"))
        except Exception as e:
            print("Auto-create user failed:", e)
            return redirect_with_msg("/employees", success=f"Employee+{Full_name}+added+successfully")
            
    return redirect_with_msg("/employees", error="Failed+to+add+employee")

@app.get("/employees/{emp_id}/edit", response_class=HTMLResponse)
async def employees_edit_form(request: Request, emp_id: str):
    employee  = db_fetch_one("Employees", filters={"id": emp_id})
    depts     = db_fetch("Departments", "id,Department_name")
    positions = db_fetch("positions", "id,title")
    managers  = db_fetch("Employees", "id,Full_name,employee_id", filters={"status":"Active"})
    if not employee:
        raise HTTPException(404, "Employee not found")
    return templates.TemplateResponse("employees/form.html", ctx(request, "employees",
        employee=employee, departments=depts, positions=positions, managers=managers, action="edit"))

@app.post("/employees/{emp_id}/edit", response_class=RedirectResponse)
async def employees_edit(request: Request, emp_id: str,
    Full_name: str = Form(...), email: str = Form(None),
    phone: str = Form(None), Dept_id: str = Form(None),
    position_id: str = Form(None), Manager_id: str = Form(None),
    hire_date: str = Form(None), date_of_birth: str = Form(None),
    status: str = Form("Active"), salary: str = Form(None)):
    ok = db_update("Employees", emp_id, {
        "Full_name": Full_name, "email": email, "phone": phone,
        "Dept_id": Dept_id or None, "position_id": position_id or None,
        "Manager_id": Manager_id or None,
        "hire_date": hire_date or None, "date_of_birth": date_of_birth or None,
        "status": status, "salary": float(salary) if salary else None,
        "updated_at": datetime.now().isoformat(),
    })
    if ok:
        return redirect_with_msg("/employees", success=f"{Full_name}+updated+successfully")
    return redirect_with_msg("/employees", error="Update+failed")

@app.post("/employees/{emp_id}/delete", response_class=RedirectResponse)
async def employees_delete(emp_id: str):
    db_delete("Employees", emp_id)
    return redirect_with_msg("/employees", success="Employee+record+deleted")

@app.get("/employees/{emp_id}", response_class=HTMLResponse)
async def employee_profile(request: Request, emp_id: str):
    emp = db_fetch_one("Employees", "*", filters={"id": emp_id})
    if not emp:
        raise HTTPException(404, "Employee not found")
    # Lookup tables
    depts    = {d["id"]: d["Department_name"] for d in db_fetch("Departments", "id,Department_name")}
    pos_map  = {p["id"]: p["title"] for p in db_fetch("positions", "id,title")}
    mgr_map  = {e["id"]: e["Full_name"] for e in db_fetch("Employees", "id,Full_name")}
    lt_map   = {lt["id"]: lt["type_name"] for lt in db_fetch("Leave_type", "id,type_name")}
    emp["dept_name"]    = depts.get(emp.get("Dept_id",""), "—")
    emp["pos_title"]    = pos_map.get(emp.get("position_id",""), "—")
    emp["manager_name"] = mgr_map.get(emp.get("Manager_id",""), None)
    # Attendance
    att_recs = db_fetch("attendance_records", "*", filters={"employee_id": emp_id}, order="check_in")
    for r in att_recs:
        ci, co = r.get("check_in"), r.get("check_out")
        if ci and co:
            try:
                dt_in  = datetime.fromisoformat(ci.replace("Z",""))
                dt_out = datetime.fromisoformat(co.replace("Z",""))
                r["work_hours_calc"] = max(0, round((dt_out - dt_in).total_seconds() / 3600, 2))
            except:
                r["work_hours_calc"] = 0
        else:
            r["work_hours_calc"] = 0
    # Leave requests
    leave_reqs = db_fetch("Leave_Request", "*", filters={"employee_id": emp_id}, order="created_at")
    for lr in leave_reqs:
        lr["type_name"] = lt_map.get(lr.get("leave_type_id",""), "—")
    # Leave balances
    leave_bals = db_fetch("Leave_balances", "*", filters={"employee_id": emp_id})
    for bal in leave_bals:
        bal["type_name"] = lt_map.get(bal.get("leave_type_id",""), "—")
    # Payroll
    payrolls = db_fetch("payrolls", "*", filters={"employee_id": emp_id}, order="month")
    total_paid = sum(float(p.get("net_salary") or 0) for p in payrolls if p.get("payment_status") == "Paid")
    # KPIs
    kpis = db_fetch("kpis", "*", filters={"employee_id": emp_id}, order="created_at")
    # Votes
    all_votes    = db_fetch("peer_voting_records", "*", filters={"nominee_id": emp_id})
    vote_count   = len(all_votes)
    vote_total   = sum(int(v.get("score") or 0) for v in all_votes)
    vote_avg     = round(vote_total / vote_count, 1) if vote_count else 0
    vote_stats   = {"votes": vote_count, "total": vote_total, "avg": vote_avg}
    # Onboarding
    onboarding   = db_fetch_one("employee_onboarding", filters={"employee_id": emp_id})
    ob_tasks     = []
    if onboarding:
        ob_tasks = db_fetch("onboarding_assignments", "*", filters={"onboarding_id": onboarding["id"]})
        for t in ob_tasks:
            task_def = db_fetch_one("onboarding_tasks", "task_name", filters={"id": t.get("task_id","")})
            t["task_name"] = task_def.get("task_name","—") if task_def else "—"
    # Recruitment (look up by name match as candidate email or name)
    all_cands    = db_fetch("recruitment_candidates", "*")
    rec_record   = next((c for c in all_cands if
                         c.get("candidate_name","").lower() == emp.get("Full_name","").lower()
                         or c.get("email") == emp.get("email")), None)
    if rec_record:
        rec_record["position_title"] = pos_map.get(rec_record.get("position_id",""), "—")
    return templates.TemplateResponse("employees/profile.html", ctx(request, "employees",
        emp=emp,
        attendance_records=att_recs,     attendance_count=len(att_recs),
        leave_requests=leave_reqs,       leave_count=len(leave_reqs),
        leave_balances=leave_bals,       leave_year=date.today().year,
        payroll_records=payrolls,        payroll_count=len(payrolls),   total_paid=total_paid,
        kpi_records=kpis,               kpi_count=len(kpis),
        vote_stats=vote_stats,
        onboarding=onboarding,          onboarding_tasks=ob_tasks,
        recruitment_record=rec_record,
    ))

# ══════════════════════════════════════════════
#  3. DEPARTMENTS
# ══════════════════════════════════════════════
@app.get("/departments", response_class=HTMLResponse)
async def departments_list(request: Request):
    depts = db_fetch("Departments", "*", order="Department_name")
    employees = db_fetch("Employees", "id,Dept_id")
    count_map: dict = {}
    for e in employees:
        did = e.get("Dept_id","")
        count_map[did] = count_map.get(did, 0) + 1
    for d in depts:
        d["emp_count"] = count_map.get(d["id"], 0)
    return templates.TemplateResponse("departments.html", ctx(request, "departments", departments=depts))

@app.post("/departments/add", response_class=RedirectResponse)
async def departments_add(Department_name: str = Form(...), Descriptions: str = Form(None)):
    db_insert("Departments", {"Department_name": Department_name, "Descriptions": Descriptions,
                               "created_at": datetime.now().isoformat()})
    return redirect_with_msg("/departments", success=f"Department+{Department_name}+created")

@app.post("/departments/{dept_id}/delete", response_class=RedirectResponse)
async def departments_delete(dept_id: str):
    db_delete("Departments", dept_id)
    return redirect_with_msg("/departments", success="Department+deleted")

# ══════════════════════════════════════════════
#  3.5 POSITIONS
# ══════════════════════════════════════════════
@app.get("/positions", response_class=HTMLResponse)
async def positions_list(request: Request):
    positions = db_fetch("positions", "*", order="title")
    employees = db_fetch("Employees", "id,position_id")
    count_map: dict = {}
    for e in employees:
        pid = e.get("position_id","")
        count_map[pid] = count_map.get(pid, 0) + 1
    for p in positions:
        p["emp_count"] = count_map.get(p["id"], 0)
    return templates.TemplateResponse("positions.html", ctx(request, "positions", positions=positions))

@app.post("/positions/add", response_class=RedirectResponse)
async def positions_add(title: str = Form(...), level: str = Form("Junior"), base_salary: float = Form(0.0)):
    db_insert("positions", {"title": title, "level": level, "base_salary": base_salary,
                               "created_at": datetime.now().isoformat()})
    return redirect_with_msg("/positions", success=f"Position+{title}+created")

@app.post("/positions/{pos_id}/edit", response_class=RedirectResponse)
async def positions_edit(pos_id: str, title: str = Form(...), level: str = Form("Junior"), base_salary: float = Form(0.0)):
    db_update("positions", pos_id, {"title": title, "level": level, "base_salary": base_salary, "updated_at": datetime.now().isoformat()})
    return redirect_with_msg("/positions", success="Position+updated+successfully")

@app.post("/positions/{pos_id}/delete", response_class=RedirectResponse)
async def positions_delete(pos_id: str):
    db_delete("positions", pos_id)
    return redirect_with_msg("/positions", success="Position+deleted")

# ══════════════════════════════════════════════
#  4. ATTENDANCE
# ══════════════════════════════════════════════
def enrich_attendance_records(records: list, emp_map: dict) -> list:
    """Attach employee name/code and calculate work hours to attendance records."""
    for r in records:
        emp = emp_map.get(r.get("employee_id",""), {})
        r["Full_name"]     = emp.get("Full_name", "—")
        r["employee_code"] = emp.get("employee_id", "—")
        ci, co = r.get("check_in"), r.get("check_out")
        if ci and co:
            try:
                dt_in  = datetime.fromisoformat(ci.replace("Z",""))
                dt_out = datetime.fromisoformat(co.replace("Z",""))
                r["work_hours_calc"] = max(0, round((dt_out - dt_in).total_seconds() / 3600, 2))
            except:
                r["work_hours_calc"] = None
        else:
            r["work_hours_calc"] = None
    return records

@app.get("/attendance", response_class=HTMLResponse)
async def attendance_list(request: Request):
    employees   = db_fetch("Employees", "id,Full_name,employee_id", filters={"status":"Active"})
    emp_map     = {e["id"]: e for e in employees}
    records     = enrich_attendance_records(db_fetch("attendance_records", "*", order="check_in"), emp_map)
    bio_devices = db_fetch("biometric_device", "*", order="created_at")
    bio_regs    = db_fetch("biometric_employees", "*")
    bio_logs    = db_fetch("biometric_logs", "*", order="created_at")
    tokens      = db_fetch("qr_attendance_tokens", "*", order="created_at")
    for reg in bio_regs:
        emp = emp_map.get(reg.get("employee_id",""), {})
        reg["Full_name"] = emp.get("Full_name","—")
    for log in bio_logs:
        emp = emp_map.get(log.get("employee_id",""), {})
        log["Full_name"] = emp.get("Full_name","—")
    for t in tokens:
        emp = emp_map.get(t.get("employee_id",""), {})
        t["Full_name"] = emp.get("Full_name","—")
        t["emp_code"]  = emp.get("employee_id","—")
    today_str = datetime.now().strftime("%A, %d %B %Y")
    return templates.TemplateResponse("attendance.html", ctx(request, "attendance",
        records=records, employees=employees, today=today_str,
        biometric_devices=bio_devices, biometric_registrations=bio_regs,
        biometric_logs=bio_logs, active_tokens=tokens, qr_data=None))

@app.post("/attendance/add", response_class=RedirectResponse)
async def attendance_add(
    employee_id: str = Form(...),
    attendance_method: str = Form("Manual"),
    check_in: str = Form(None),
    check_out: str = Form(None),
    overtime_hours: str = Form("0"),
    is_late: str = Form("false")):
    now = datetime.now().isoformat()
    ci = check_in or now
    if check_out and ci:
        try:
            if datetime.fromisoformat(check_out) < datetime.fromisoformat(ci):
                return redirect_with_msg("/attendance", error="Check-out time cannot be before check-in time")
        except:
            pass
    db_insert("attendance_records", {
        "employee_id": employee_id,
        "check_in": ci,
        "check_out": check_out or None,
        "overtime_hours": float(overtime_hours) if overtime_hours else 0,
        "attendance_method": attendance_method,
        "is_late": is_late.lower() == "true",
        "created_at": now,
    })
    return redirect_with_msg("/attendance", success="Attendance+record+added")

@app.post("/attendance/{rec_id}/checkout", response_class=RedirectResponse)
async def attendance_checkout(rec_id: str):
    now = datetime.now().isoformat()
    db_update("attendance_records", rec_id, {"check_out": now, "updated_by": None})
    return redirect_with_msg("/attendance", success="Check-out+recorded")

@app.post("/attendance/generate-qr", response_class=HTMLResponse)
async def attendance_generate_qr(request: Request, employee_id: str = Form(...)):
    emp = db_fetch_one("Employees", "id,Full_name,employee_id", filters={"id": employee_id})
    if not emp:
        return redirect_with_msg("/attendance", error="Employee+not+found")
    # Generate a unique secure token
    token     = secrets.token_urlsafe(32)
    now       = datetime.now()
    expires   = (now + timedelta(hours=8)).isoformat()
    db_insert("qr_attendance_tokens", {
        "token": token, "employee_id": employee_id,
        "created_at": now.isoformat(), "expires_at": expires, "used": False,
    })
    # Build scan URL
    base_url = str(request.base_url).rstrip("/")
    scan_url  = f"{base_url}/attendance/scan/{token}"
    # Generate QR image as base64
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(scan_url)
    qr.make(fit=True)
    img    = qr.make_image(fill_color="black", back_color="white")
    buf    = io.BytesIO()
    img.save(buf, format="PNG")
    b64    = base64.b64encode(buf.getvalue()).decode()
    # Gather rest of page data
    records   = db_fetch("attendance_records", "*", order="check_in")
    employees = db_fetch("Employees", "id,Full_name,employee_id", filters={"status":"Active"})
    emp_map   = {e["id"]: e for e in employees}
    tokens    = db_fetch("qr_attendance_tokens", "*", order="created_at")
    for r in records:
        e = emp_map.get(r.get("employee_id",""), {})
        r["Full_name"] = e.get("Full_name","—")
        r["employee_code"] = e.get("employee_id","—")
        ci, co = r.get("check_in"), r.get("check_out")
        if ci and co:
            try:
                dt_in  = datetime.fromisoformat(ci.replace("Z",""))
                dt_out = datetime.fromisoformat(co.replace("Z",""))
                r["work_hours_calc"] = max(0, round((dt_out - dt_in).total_seconds() / 3600, 2))
            except:
                r["work_hours_calc"] = r.get("work_hours", 0)
        else:
            r["work_hours_calc"] = r.get("work_hours", 0)
    for t in tokens:
        e2 = emp_map.get(t.get("employee_id",""), {})
        t["Full_name"]  = e2.get("Full_name","—")
        t["emp_code"]   = e2.get("employee_id","—")
    today_str = datetime.now().strftime("%A, %d %B %Y")
    return templates.TemplateResponse("attendance.html", ctx(request, "attendance",
        records=records, employees=employees, active_tokens=tokens, today=today_str,
        qr_data={
            "image_b64": b64,
            "emp_name": emp.get("Full_name","—"),
            "emp_code": emp.get("employee_id","—"),
            "expires_at": expires[:16].replace("T"," ") + " UTC",
            "scan_url": scan_url,
        }
    ))

@app.get("/attendance/scan/{token}", response_class=HTMLResponse)
async def attendance_scan_qr(request: Request, token: str):
    rec = db_fetch_one("qr_attendance_tokens", filters={"token": token})
    if not rec:
        return templates.TemplateResponse("qr_checkin.html", ctx(request, "attendance",
            success=False, error_msg="QR token not found."))
    # Check expiry
    try:
        exp = datetime.fromisoformat(str(rec["expires_at"]).replace("Z", "+00:00")).replace(tzinfo=None)
        if datetime.now() > exp:
            return templates.TemplateResponse("qr_checkin.html", ctx(request, "attendance",
                success=False, error_msg="QR code has expired. Ask HR to generate a new one."))
    except:
        pass
    # Record check-in or check-out
    emp_id  = rec["employee_id"]
    now_str = datetime.now().isoformat()
    today_prefix = now_str[:10]
    records = db_fetch("attendance_records", "*", filters={"employee_id": emp_id})
    today_rec = next((r for r in records if r.get("check_in", "").startswith(today_prefix)), None)
    
    if today_rec:
        db_update("attendance_records", today_rec["id"], {"check_out": now_str})
        action_msg = "Check-Out recorded successfully"
    else:
        db_insert("attendance_records", {
            "employee_id": emp_id, "check_in": now_str,
            "attendance_method": "QR", "is_late": False, "created_at": now_str,
        })
        action_msg = "Check-In recorded successfully"
    db_update("qr_attendance_tokens", rec["id"], {"used": True, "used_at": now_str})
    emp = db_fetch_one("Employees", "Full_name,employee_id", filters={"id": emp_id})
    return templates.TemplateResponse("qr_checkin.html", ctx(request, "attendance",
        success=True,
        action_msg=action_msg,
        emp_name=emp.get("Full_name","—") if emp else "—",
        emp_code=emp.get("employee_id","—") if emp else "—",
        check_in_time=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
    ))

@app.post("/attendance/{rec_id}/delete", response_class=RedirectResponse)
async def attendance_delete(rec_id: str):
    db_delete("attendance_records", rec_id)
    return redirect_with_msg("/attendance", success="Record+deleted")

# ── Photo Check-In ──────────────────────────────────────────────────────────
@app.post("/attendance/add-photo", response_class=RedirectResponse)
async def attendance_add_photo(
    employee_id: str = Form(...),
    photo_b64: str = Form(...),
    notes: str = Form(None),
    is_late: str = Form("false"),
    attendance_method: str = Form("Photo")):
    now = datetime.now().isoformat()
    # Store base64 photo as data-URL in the check_in_photo_url field
    photo_url = photo_b64 if photo_b64.startswith("data:image") else None
    # Smart check-in/out logic
    today_prefix = now[:10]
    records = db_fetch("attendance_records", "*", filters={"employee_id": employee_id})
    today_rec = next((r for r in records if r.get("check_in", "").startswith(today_prefix)), None)
    
    if today_rec:
        db_update("attendance_records", today_rec["id"], {
            "check_out": now,
            "check_out_photo_url": photo_url
        })
        msg = "Photo Check-Out recorded successfully"
    else:
        db_insert("attendance_records", {
            "employee_id":        employee_id,
            "check_in":           now,
            "attendance_method":  attendance_method,
            "is_late":            is_late.lower() == "true",
            "check_in_photo_url": photo_url,
            "created_at":         now,
        })
        msg = "Photo Check-In recorded successfully"
        
    return redirect_with_msg("/attendance", success=msg.replace(" ", "+"))

# ── Biometric Device Management ─────────────────────────────────────────
@app.post("/attendance/biometric/device/add", response_class=RedirectResponse)
async def biometric_device_add(
    device_name: str = Form(...),
    ip_address: str = Form(None),
    port: str = Form("4370"),
    location: str = Form(None)):
    db_insert("biometric_device", {
        "device_name": device_name,
        "ip_address":  ip_address or None,
        "port":        int(port) if port else 4370,
        "location":    location or None,
        "status":      "Active",
        "created_at":  datetime.now().isoformat(),
    })
    return RedirectResponse(url="/attendance?tab=biometric&success=Device+added+successfully", status_code=302)

# ── Biometric Employee Registration ────────────────────────────────────
@app.post("/attendance/biometric/register", response_class=RedirectResponse)
async def biometric_register(
    employee_id: str = Form(...),
    device_id: str = Form(...),
    biometric_id: str = Form(...)):
    db_insert("biometric_employees", {
        "employee_id":  employee_id,
        "device_id":    device_id,
        "biometric_id": biometric_id,
        "registered":   True,
        "updated_at":   datetime.now().isoformat(),
    })
    emp = db_fetch_one("Employees", "Full_name", filters={"id": employee_id})
    name = emp.get("Full_name","Employee") if emp else "Employee"
    return RedirectResponse(url=f"/attendance?tab=biometric&success={name}+biometric+ID+registered", status_code=302)

# ── Biometric Check-In Simulation ──────────────────────────────────────
@app.post("/attendance/biometric/checkin", response_class=RedirectResponse)
async def biometric_checkin(
    device_id: str = Form(...),
    employee_id: str = Form(...),
    scan_type: str = Form("in"),
    scan_time: str = Form(None)):
    now_str   = datetime.now().isoformat()
    raw_time  = scan_time or now_str
    # Log to biometric_logs
    db_insert("biometric_logs", {
        "device_id":           device_id,
        "employee_id":         employee_id,
        "raw_time":            raw_time,
        "type":                scan_type,
        "verification_status": "verified",
        "new_data":            True,
        "created_at":          now_str,
    })
    # Record in attendance_records
    if scan_type == "in":
        db_insert("attendance_records", {
            "employee_id":       employee_id,
            "check_in":          raw_time,
            "attendance_method": "Biometric",
            "is_late":           False,
            "created_at":        now_str,
        })
    else:
        # Find today's open record and close it
        today = date.today().isoformat()
        all_recs = db_fetch("attendance_records", "*", filters={"employee_id": employee_id})
        open_rec = next((r for r in all_recs
                        if r.get("check_in","").startswith(today) and not r.get("check_out")), None)
        if open_rec:
            db_update("attendance_records", open_rec["id"], {"check_out": raw_time})
    emp = db_fetch_one("Employees", "Full_name", filters={"id": employee_id})
    name = emp.get("Full_name","Employee") if emp else "Employee"
    action = "checked+in" if scan_type == "in" else "checked+out"
    return RedirectResponse(url=f"/attendance?tab=biometric&success=Biometric+{action}+for+{name}", status_code=302)

# ══════════════════════════════════════════════
#  5. LEAVE MANAGEMENT
# ══════════════════════════════════════════════
@app.get("/leave", response_class=HTMLResponse)
async def leave_list(request: Request):
    requests  = db_fetch("Leave_Request", "*", order="created_at")
    balances  = db_fetch("Leave_balances", "*")
    employees = db_fetch("Employees", "id,Full_name,employee_id", filters={"status":"Active"})
    leave_types = db_fetch("Leave_type", "id,type_name,default_days,is_paid")
    emp_map   = {e["id"]: e for e in employees}
    lt_map    = {lt["id"]: lt for lt in leave_types}
    for r in requests:
        emp = emp_map.get(r.get("employee_id",""), {})
        lt  = lt_map.get(r.get("leave_type_id",""), {})
        r["Full_name"]  = emp.get("Full_name", "—")
        r["emp_code"]   = emp.get("employee_id", "—")
        r["leave_type"] = lt.get("type_name", "—")
    for b in balances:
        emp = emp_map.get(b.get("employee_id",""), {})
        lt  = lt_map.get(b.get("leave_type_id",""), {})
        b["Full_name"]  = emp.get("Full_name", "—")
        b["leave_type"] = lt.get("type_name", "—")
    stats = {
        "pending":  sum(1 for r in requests if str(r.get("status","")).lower() == "pending"),
        "approved": sum(1 for r in requests if str(r.get("status","")).lower() == "approved"),
        "rejected": sum(1 for r in requests if str(r.get("status","")).lower() == "rejected"),
    }
    return templates.TemplateResponse("leave/index.html", ctx(request, "leave",
        leave_requests=requests, leave_balances=balances,
        employees=employees, leave_types=leave_types, stats=stats))

# ── Leave Balance Helpers ─────────────────────────────────────────────────
def get_or_create_balance(employee_id: str, leave_type_id: str) -> dict:
    """Fetch existing balance or create a fresh one from the leave type defaults."""
    bal = db_fetch_one("Leave_balances",
        filters={"employee_id": employee_id, "leave_type_id": leave_type_id})
    if not bal:
        lt = db_fetch_one("Leave_type", filters={"id": leave_type_id})
        entitled = int(lt.get("default_days", 14)) if lt else 14
        bal = db_insert("Leave_balances", {
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "year": date.today().year,
            "entitled_days": entitled,
            "used_days": 0,
            "remain_days": entitled,
            "updated_at": datetime.now().isoformat(),
        })
    return bal or {}

def deduct_balance(employee_id: str, leave_type_id: str, days: int) -> bool:
    """Subtract days from remaining balance. Returns False if insufficient."""
    bal = get_or_create_balance(employee_id, leave_type_id)
    remain = int(bal.get("remain_days") or 0)
    if days > remain:
        return False
    db_update("Leave_balances", bal["id"], {
        "used_days":   int(bal.get("used_days", 0)) + days,
        "remain_days": remain - days,
        "updated_at":  datetime.now().isoformat(),
    })
    return True

def restore_balance(employee_id: str, leave_type_id: str, days: int):
    """Add days back to remaining balance (on reject / delete of approved leave)."""
    bal = db_fetch_one("Leave_balances",
        filters={"employee_id": employee_id, "leave_type_id": leave_type_id})
    if not bal:
        return
    used   = max(0, int(bal.get("used_days", 0)) - days)
    remain = int(bal.get("entitled_days", 0)) - used
    db_update("Leave_balances", bal["id"], {
        "used_days":   used,
        "remain_days": remain,
        "updated_at":  datetime.now().isoformat(),
    })

# ── Leave CRUD ────────────────────────────────────────────────────────────
@app.post("/leave/add", response_class=RedirectResponse)
async def leave_add(
    employee_id: str = Form(...), leave_type_id: str = Form(...),
    start_date: str = Form(...), end_date: str = Form(...),
    reason: str = Form(None)):
    d1    = date.fromisoformat(start_date)
    d2    = date.fromisoformat(end_date)
    total = (d2 - d1).days + 1

    # ── Balance Check ──────────────────────────────────────────
    bal    = get_or_create_balance(employee_id, leave_type_id)
    remain = int(bal.get("remain_days") or 0)
    lt     = db_fetch_one("Leave_type", filters={"id": leave_type_id})
    lt_name = lt.get("type_name", "Leave") if lt else "Leave"

    if total > remain:
        msg = (f"Cannot+submit+{total}+days+of+{lt_name}.+"
               f"Only+{remain}+day(s)+remaining+out+of+"
               f"{bal.get('entitled_days',0)}+entitled+days."
               f"+Already+used:+{bal.get('used_days',0)}+days.")
        return redirect_with_msg("/leave", error=msg)
    # ── Insert as Pending (balance deducted only on Approve) ───
    db_insert("Leave_Request", {
        "employee_id": employee_id, "leave_type_id": leave_type_id,
        "start_date": start_date, "end_date": end_date,
        "total_days": total, "reason": reason,
        "status": "Pending", "created_at": datetime.now().isoformat(),
    })
    emp = db_fetch_one("Employees", "Full_name", filters={"id": employee_id})
    emp_name = emp.get("Full_name", "An employee") if emp else "An employee"
    notify_role("hr_manager", "New Leave Request", f"{emp_name} requested {total} day(s) of {lt_name}.", "/leave")
    notify_role("boss", "New Leave Request", f"{emp_name} requested {total} day(s) of {lt_name}.", "/leave")
    return redirect_with_msg("/leave",
        success=f"Leave+request+submitted.+{remain - total}+day(s)+will+remain+if+approved.")

@app.post("/leave/{req_id}/approve", response_class=RedirectResponse)
async def leave_approve(req_id: str):
    req = db_fetch_one("Leave_Request", filters={"id": req_id})
    if not req:
        return redirect_with_msg("/leave", error="Request+not+found")
    if req.get("status") == "Approved":
        return redirect_with_msg("/leave", error="Already+approved")

    emp_id  = req["employee_id"]
    lt_id   = req["leave_type_id"]
    days    = int(req.get("total_days") or 0)

    # ── Balance enforcement at approval time ────────────────────
    bal    = get_or_create_balance(emp_id, lt_id)
    remain = int(bal.get("remain_days") or 0)
    lt     = db_fetch_one("Leave_type", filters={"id": lt_id})
    lt_name = lt.get("type_name", "Leave") if lt else "Leave"

    if days > remain:
        emp = db_fetch_one("Employees", "Full_name", filters={"id": emp_id})
        name = emp.get("Full_name", "Employee") if emp else "Employee"
        msg = (f"Cannot+approve:+{name}+has+only+{remain}+day(s)+of+{lt_name}+remaining"
               f"+but+requested+{days}+days+(already+used+{bal.get('used_days',0)}+of+"
               f"{bal.get('entitled_days',0)}+days).")
        return redirect_with_msg("/leave", error=msg)

    # Deduct and approve
    deduct_balance(emp_id, lt_id, days)
    db_update("Leave_Request", req_id, {
        "status": "Approved",
        "approved_at": datetime.now().isoformat()
    })
    notify_employee(emp_id, "Leave Approved", f"Your request for {days} day(s) of {lt_name} was approved.", "/portal/leaves")
    return redirect_with_msg("/leave",
        success=f"Leave+approved.+{remain - days}+day(s)+of+{lt_name}+remaining.")

@app.post("/leave/{req_id}/reject", response_class=RedirectResponse)
async def leave_reject(req_id: str):
    req = db_fetch_one("Leave_Request", filters={"id": req_id})
    if req and req.get("status") == "Approved":
        # Restore balance if was previously approved
        restore_balance(
            req["employee_id"], req["leave_type_id"],
            int(req.get("total_days") or 0)
        )
    db_update("Leave_Request", req_id, {
        "status": "Rejected",
        "cancelled_at": datetime.now().isoformat()
    })
    notify_employee(req["employee_id"], "Leave Rejected", "Your leave request was rejected.", "/portal/leaves")
    return redirect_with_msg("/leave", success="Leave+rejected+and+balance+restored")

@app.post("/leave/{req_id}/delete", response_class=RedirectResponse)
async def leave_delete(req_id: str):
    req = db_fetch_one("Leave_Request", filters={"id": req_id})
    if req and req.get("status") == "Approved":
        # Restore balance before deleting
        restore_balance(
            req["employee_id"], req["leave_type_id"],
            int(req.get("total_days") or 0)
        )
    db_delete("Leave_Request", req_id)
    return redirect_with_msg("/leave", success="Request+deleted")

@app.post("/leave-balance/{bal_id}/delete", response_class=RedirectResponse)
async def leave_balance_delete(bal_id: str):
    db_delete("Leave_balances", bal_id)
    return redirect_with_msg("/leave", success="Leave+balance+deleted")

# Leave Types CRUD
@app.get("/leave-types", response_class=HTMLResponse)
async def leave_types_page(request: Request):
    leave_types = db_fetch("Leave_type", "*", order="type_name")
    return templates.TemplateResponse("leave/types.html", ctx(request, "leave", leave_types=leave_types))

@app.post("/leave-types/add", response_class=RedirectResponse)
async def leave_types_add(
    type_name: str = Form(...), description: str = Form(None),
    default_days: str = Form("14"), is_paid: str = Form("true")):
    db_insert("Leave_type", {
        "type_name": type_name, "description": description,
        "default_days": int(default_days), "is_paid": is_paid.lower() == "true",
        "created_at": datetime.now().isoformat(),
    })
    return redirect_with_msg("/leave-types", success=f"Leave+type+{type_name}+created")

@app.post("/leave-types/{lt_id}/edit", response_class=RedirectResponse)
async def leave_types_edit(lt_id: str,
    type_name: str = Form(...), description: str = Form(None),
    default_days: str = Form("14"), is_paid: str = Form("true")):
    db_update("Leave_type", lt_id, {
        "type_name": type_name, "description": description,
        "default_days": int(default_days), "is_paid": is_paid.lower() == "true",
    })
    return redirect_with_msg("/leave-types", success=f"Leave+type+{type_name}+updated")

@app.post("/leave-types/{lt_id}/delete", response_class=RedirectResponse)
async def leave_types_delete(lt_id: str):
    db_delete("Leave_type", lt_id)
    return redirect_with_msg("/leave-types", success="Leave+type+deleted")

# ══════════════════════════════════════════════
#  6. PAYROLL & KPIs
# ══════════════════════════════════════════════
@app.get("/payroll", response_class=HTMLResponse)
async def payroll_list(request: Request):
    payrolls  = db_fetch("payrolls", "*", order="created_at")
    kpis      = db_fetch("kpis", "*", order="created_at")
    employees = db_fetch("Employees", "id,Full_name,employee_id,salary", filters={"status":"Active"})
    emp_map   = {e["id"]: e for e in employees}
    kpi_map   = {k["id"]: k for k in kpis}
    
    # Pre-calculate most recent KPI per employee (since kpis are ordered by created_at asc)
    emp_recent_kpi = {}
    for k in kpis:
        if k.get("employee_id"):
            emp_recent_kpi[k["employee_id"]] = k.get("actual_score")

    for p in payrolls:
        emp = emp_map.get(p.get("employee_id",""), {})
        p["Full_name"]    = emp.get("Full_name", "—")
        p["employee_code"]= emp.get("employee_id", "—")
        
        explicit_kpi = kpi_map.get(p.get("kpi_id",""), {})
        if explicit_kpi:
            p["kpi_score"] = explicit_kpi.get("actual_score", "—")
        else:
            score = emp_recent_kpi.get(p.get("employee_id"))
            p["kpi_score"] = f"{score}%" if score is not None else "—"
    for k in kpis:
        emp = emp_map.get(k.get("employee_id",""), {})
        k["Full_name"] = emp.get("Full_name", "—")
    stats = {
        "total_paid": sum(float(p.get("net_salary") or 0) for p in payrolls if p.get("payment_status") == "Paid"),
        "pending":    sum(1 for p in payrolls if p.get("payment_status") == "Pending"),
        "on_hold":    sum(1 for p in payrolls if p.get("payment_status") == "On Hold"),
    }
    return templates.TemplateResponse("payroll.html", ctx(request, "payroll",
        payrolls=payrolls, kpis=kpis, employees=employees, stats=stats))

@app.post("/payroll/add", response_class=RedirectResponse)
async def payroll_add(
    employee_id: str = Form(...), month: str = Form(...),
    basic_salary: str = Form("0"), allowances: str = Form("0"),
    deductions: str = Form("0"), bonus: str = Form("0")):
    b, a, d, bn = float(basic_salary), float(allowances), float(deductions), float(bonus)
    net = b + a - d + bn
    db_insert("payrolls", {
        "employee_id": employee_id, "month": month,
        "basic_salary": b, "allowances": a, "deductions": d, "bonus": bn,
        "net_salary": net, "payment_status": "Pending",
        "created_at": datetime.now().isoformat(),
    })
    return redirect_with_msg("/payroll", success="Payroll+record+added")

@app.post("/payroll/{pay_id}/mark-paid", response_class=RedirectResponse)
async def payroll_mark_paid(pay_id: str):
    db_update("payrolls", pay_id, {"payment_status": "Paid", "paid_date": date.today().isoformat()})
    return redirect_with_msg("/payroll", success="Payment+marked+as+paid")

@app.post("/payroll/{pay_id}/delete", response_class=RedirectResponse)
async def payroll_delete(pay_id: str):
    db_delete("payrolls", pay_id)
    return redirect_with_msg("/payroll", success="Payroll+record+deleted")

@app.post("/kpi/add", response_class=RedirectResponse)
async def kpi_add(
    employee_id: str = Form(...), recent_period: str = Form(...),
    target_score: str = Form("100"), actual_score: str = Form("0"),
    review_comment: str = Form(None)):
    db_insert("kpis", {
        "employee_id": employee_id, "recent_period": recent_period,
        "target_score": float(target_score), "actual_score": float(actual_score),
        "review_comment": review_comment, "reviewed_at": datetime.now().isoformat(),
        "created_at": datetime.now().isoformat(),
    })
    return redirect_with_msg("/payroll", success="KPI+record+added")

@app.post("/kpi/{kpi_id}/delete", response_class=RedirectResponse)
async def kpi_delete(kpi_id: str):
    db_delete("kpis", kpi_id)
    return redirect_with_msg("/payroll", success="KPI+record+deleted")

# --- KPI Settings Logic ---
def get_kpi_settings():
    try:
        with open("kpi_settings.json", "r") as f:
            return json.load(f)
    except:
        return {
            "auto_weights": {
                "attendance": 40,
                "punctuality": 0,
                "sops": 40,
                "peer_voting": 20
            },
            "manual_metrics": [],
            "target_bonus_percentage": 15
        }

@app.get("/api/kpi/settings")
async def api_get_kpi_settings():
    return get_kpi_settings()

@app.post("/api/kpi/settings")
async def api_save_kpi_settings(request: Request):
    data = await request.json()
    with open("kpi_settings.json", "w") as f:
        json.dump(data, f, indent=2)
    return {"success": True}
# --------------------------

@app.get("/payroll/calculate/{employee_id}/{month}")
async def calculate_payroll(employee_id: str, month: str):
    # Fetch employee to get base salary
    employee = db_fetch_one("Employees", "salary", filters={"id": employee_id})
    if not employee:
        return {"error": "Employee not found"}
        
    base_salary = float(employee.get("salary") or 0.0)
    
    # Let's assume 21 working days for May 2026, or generically 21
    working_days = 21
    
    settings = get_kpi_settings()
    auto_weights = settings.get("auto_weights", {})
    w_att = float(auto_weights.get("attendance", 40))
    w_punct = float(auto_weights.get("punctuality", 0))
    w_sops = float(auto_weights.get("sops", 40))
    w_peer = float(auto_weights.get("peer_voting", 20))
    
    # 1. Fetch Attendance
    all_attendance = db_fetch("attendance_records", "*", filters={"employee_id": employee_id})
    monthly_attendance = [a for a in all_attendance if str(a.get("check_in", "")).startswith(month)]
    actual_attendance = len(monthly_attendance)
    attendance_score = min(100.0, (actual_attendance / working_days) * 100)
    
    on_time_count = 0
    for a in monthly_attendance:
        check_in_time = a.get("check_in", "")
        if check_in_time and "T" in check_in_time:
            time_part = check_in_time.split("T")[1]
            if time_part <= "09:15:00":
                on_time_count += 1
    
    punctuality_score = (on_time_count / actual_attendance * 100) if actual_attendance > 0 else 0.0
    
    # 2. Fetch SOPs
    all_sops = db_fetch("daily_sops", "*", filters={"employee_id": employee_id})
    monthly_sops = [s for s in all_sops if s.get("assigned_date", "").startswith(month)]
    completed_sops = [s for s in monthly_sops if s.get("is_completed")]
    
    sop_score = 0.0
    if len(monthly_sops) > 0:
        sop_score = (len(completed_sops) / len(monthly_sops)) * 100
        
    # 3. Fetch Peer Voting
    all_votes = db_fetch("peer_voting_records", "*", filters={"nominee_id": employee_id})
    peer_score = 0.0
    if all_votes:
        avg_stars = sum(float(v.get("score", 0)) for v in all_votes) / len(all_votes)
        peer_score = (avg_stars / 5.0) * 100
        
    # 4. Calculate Final KPI
    auto_kpi_contribution = (attendance_score * (w_att/100)) + (punctuality_score * (w_punct/100)) + (sop_score * (w_sops/100)) + (peer_score * (w_peer/100))
    
    manual_metrics = settings.get("manual_metrics", [])
    target_bonus_pct = float(settings.get("target_bonus_percentage", 15))
    
    return {
        "success": True,
        "base_salary": round(base_salary, 2),
        "attendance_score": round(attendance_score, 2),
        "punctuality_score": round(punctuality_score, 2),
        "sop_score": round(sop_score, 2),
        "peer_score": round(peer_score, 2),
        "auto_kpi_contribution": round(auto_kpi_contribution, 2),
        "manual_metrics": manual_metrics,
        "auto_weights": auto_weights,
        "target_bonus_percentage": target_bonus_pct,
        
        # Detailed math breakdown
        "actual_attendance": actual_attendance,
        "on_time_count": on_time_count,
        "expected_working_days": working_days,
        "completed_sops_count": len(completed_sops),
        "total_sops_count": len(monthly_sops),
        "peer_votes_count": len(all_votes) if all_votes else 0
    }


# ══════════════════════════════════════════════
#  6B. PUBLIC CAREERS & AI RECRUITMENT
# ══════════════════════════════════════════════

def process_resume_with_ai(cand_id: str, resume_text: str, job_title: str):
    print(f"--- Starting AI processing for {cand_id} ({job_title}) ---")
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        Act as an expert technical HR recruiter. You are evaluating a candidate for the position of '{job_title}'.
        Analyze the following resume and score the candidate from 1 to 10 on how well they match the role.
        Return ONLY valid JSON in exactly this format:
        {{"score": <integer 1-10>, "reasoning": "<brief justification>"}}

        Candidate Resume:
        {resume_text}
        """
        response = model.generate_content(prompt)
        # Parse JSON
        resp_text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(resp_text)
        score = data.get("score", 1)
        reasoning = data.get("reasoning", "No reasoning provided.")
        
        # Update db
        db_update("recruitment_candidates", cand_id, {"ai_score": score, "ai_reasoning": reasoning})
        
        # Auto-route and notify if score >= 8
        if score >= 8:
            db_update("recruitment_candidates", cand_id, {"status": "Screening"})
            db_insert("recruitment_status_history", {
                "candidate_id": cand_id,
                "status": "Screening",
                "created_at": datetime.now().isoformat()
            })
            notify_role("hr_manager", "High-Scoring Candidate Alert!", f"An AI scan found a high-scoring candidate ({score}/10) for {job_title}. Moved to Screening.", "/recruitment")
            
    except Exception as e:
        print("Gemini AI error:", e)

def generate_interview_guide(cand_id: str, resume_text: str, job_title: str):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        Act as an expert technical HR recruiter for a company in Myanmar.
        You are preparing an interview guide for a candidate interviewing for the role of '{job_title}'.
        Based on the resume provided below, generate a custom interview guide.
        The output MUST be written entirely in Burmese (Myanmar language).
        
        Include:
        1. 5 to 7 specific interview questions based on their experience.
        2. Potential red flags or weak areas to ask about.
        3. Overall advice for the interviewer.
        
        Candidate Resume:
        {resume_text}
        """
        response = model.generate_content(prompt)
        guide_text = response.text.strip()
        
        db_update("recruitment_candidates", cand_id, {"interview_guide": guide_text})
        notify_role("hr_manager", "Interview Guide Ready", f"The AI Interview Guide for {job_title} is ready.", "/recruitment")
    except Exception as e:
        print("Gemini Guide error:", e)

@app.get("/careers", response_class=HTMLResponse)
async def careers_list(request: Request):
    positions = db_fetch("positions", "*")
    success = request.query_params.get("success")
    return templates.TemplateResponse("careers.html", {"request": request, "positions": positions, "success": success})

@app.get("/careers/apply/{pos_id}", response_class=HTMLResponse)
async def careers_apply(request: Request, pos_id: str):
    pos = db_fetch_one("positions", "*", {"id": pos_id})
    if not pos:
        return RedirectResponse("/careers")
    return templates.TemplateResponse("apply.html", {"request": request, "position": pos})

@app.post("/careers/submit", response_class=RedirectResponse)
async def careers_submit(
    background_tasks: BackgroundTasks,
    position_id: str = Form(...),
    job_title: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    notes: str = Form(""),
    resume: UploadFile = File(...)
):
    resume_text = ""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(await resume.read()))
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                resume_text += text + "\n"
    except Exception as e:
        print("PDF parse error:", e)
        resume_text = "Failed to parse PDF."

    full_name = f"{first_name} {last_name}"
    cand_row = db_insert("recruitment_candidates", {
        "full_name": full_name,
        "email": email,
        "position_id": position_id,
        "status": "Applied",
        "notes": notes,
        "resume_content": resume_text,
        "created_at": datetime.now().isoformat()
    })
    cand_id = cand_row.get("id") if cand_row else None
    
    if cand_id and resume_text and "Failed" not in resume_text:
        print("Submitting background task for cand_id:", cand_id)
        background_tasks.add_task(process_resume_with_ai, cand_id, resume_text, job_title)
        print("Background task queued")
    else:
        print("Skipped background task:", bool(cand_id), bool(resume_text))

    return RedirectResponse(url="/careers?success=Application+submitted+successfully!+We+will+be+in+touch.", status_code=302)

# ══════════════════════════════════════════════
#  7. RECRUITMENT
# ══════════════════════════════════════════════
CANDIDATE_STAGES = ["Applied", "Screening", "Interview", "Offer", "Hired", "Rejected"]
PIPELINE_STAGES  = ["Applied", "Screening", "Interview", "Offer"]

@app.get("/recruitment", response_class=HTMLResponse)
async def recruitment_list(request: Request):
    candidates = db_fetch("recruitment_candidates", "*", order="created_at")
    positions  = db_fetch("positions", "id,title,level")
    pos_map    = {p["id"]: p for p in positions}
    for c in candidates:
        pos = pos_map.get(c.get("position_id",""), {})
        c["position_title"] = pos.get("title", "—")
    # Separate into clear buckets
    pipeline   = [c for c in candidates if c.get("status","Applied") in PIPELINE_STAGES]
    hired      = [c for c in candidates if c.get("status") == "Hired"]
    rejected   = [c for c in candidates if c.get("status") == "Rejected"]
    shortlisted= [c for c in candidates if c.get("status") in ["Interview","Offer"]]
    # Stage groups for kanban
    stage_groups: dict = {s: [] for s in CANDIDATE_STAGES}
    for c in candidates:
        s = c.get("status","Applied")
        if s in stage_groups:
            stage_groups[s].append(c)
        else:
            stage_groups["Applied"].append(c)
    return templates.TemplateResponse("recruitment.html", ctx(request, "recruitment",
        candidates=candidates, positions=positions,
        pipeline=pipeline, hired=hired, rejected=rejected, shortlisted=shortlisted,
        stage_groups=stage_groups, stages=CANDIDATE_STAGES))

@app.post("/recruitment/add", response_class=RedirectResponse)
async def recruitment_add(
    full_name: str = Form(...), email: str = Form(None),
    phone: str = Form(None), position_id: str = Form(None),
    source: str = Form(None), notes: str = Form(None)):
    db_insert("recruitment_candidates", {
        "full_name": full_name, "email": email, "phone": phone,
        "position_id": position_id or None, "source": source,
        "notes": notes or None,
        "status": "Applied", "created_at": datetime.now().isoformat(),
    })
    return redirect_with_msg("/recruitment", success=f"{full_name}+added+to+pipeline")

@app.post("/recruitment/{cand_id}/status", response_class=RedirectResponse)
async def recruitment_update_status(background_tasks: BackgroundTasks, cand_id: str, status: str = Form(...)):
    cand = db_fetch_one("recruitment_candidates", "*", {"id": cand_id})
    if not cand:
        return redirect_with_msg("/recruitment", error="Candidate+not+found")

    db_update("recruitment_candidates", cand_id, {
        "status": status, "updated_at": datetime.now().isoformat()
    })
    
    db_insert("recruitment_status_history", {
        "candidate_id": cand_id, "status": status,
        "created_at": datetime.now().isoformat()
    })
    
    # 1. Automated Interview Guide
    if status == "Interview" and cand.get("resume_content"):
        pos = db_fetch_one("positions", "*", {"id": cand.get("position_id")}) if cand.get("position_id") else None
        job_title = pos.get("title", "Unknown Role") if pos else "Unknown Role"
        background_tasks.add_task(generate_interview_guide, cand_id, cand.get("resume_content"), job_title)
        
    # 2. Automated Offer Letter
    if status == "Offer":
        pos = db_fetch_one("positions", "*", {"id": cand.get("position_id")}) if cand.get("position_id") else None
        job_title = pos.get("title", "Unknown Role") if pos else "Unknown Role"
        salary = pos.get("base_salary", 0) if pos else 0
        
        # Create Offer Letter Document
        doc_id = db_insert("employee_documents", {
            "title": f"Offer Letter - {cand.get('full_name')}",
            "type": "Offer Letter",
            "content": f"Dear {cand.get('full_name')},\n\nWe are thrilled to offer you the position of {job_title} with a starting salary of {int(salary)} MMK/year.\n\nPlease sign below to accept this offer.\n\nBest,\nHR Team",
            "status": "Pending Boss Signature",
            "signature_workflow": "boss_then_hr_then_employee",
            "issued_by": "System Auto-Generated",
            "created_at": datetime.now().isoformat()
        })
        if doc_id:
            notify_role("boss", "Signature Required", f"An auto-generated Offer Letter for {cand.get('full_name')} ({job_title}) requires your signature.", "/documents")

    if status == "Rejected":
        return RedirectResponse(url="/recruitment?tab=rejected&success=Candidate+moved+to+Talent+Pool", status_code=302)
    if status == "Hired":
        return RedirectResponse(url="/recruitment?tab=hired&success=Candidate+marked+as+Hired", status_code=302)
    return redirect_with_msg("/recruitment", success=f"Stage+updated+to+{status}")

@app.post("/recruitment/{cand_id}/reconsider", response_class=RedirectResponse)
async def recruitment_reconsider(cand_id: str, position_id: str = Form(None)):
    """Move a rejected candidate back into the Active Pipeline for a new role."""
    update_data = {
        "status": "Applied",
        "updated_at": datetime.now().isoformat(),
    }
    if position_id:
        update_data["position_id"] = position_id
    db_update("recruitment_candidates", cand_id, update_data)
    db_insert("recruitment_status_history", {
        "candidate_id": cand_id, "status": "Applied (Reconsidered)",
        "created_at": datetime.now().isoformat()
    })
    return RedirectResponse(url="/recruitment?success=Candidate+moved+back+to+Active+Pipeline", status_code=302)

@app.post("/recruitment/{cand_id}/delete", response_class=RedirectResponse)
async def recruitment_delete(cand_id: str):
    db_delete("recruitment_candidates", cand_id)
    return redirect_with_msg("/recruitment", success="Candidate+removed")


# ════════════════════════════════════════════
#  8. PEER VOTING (Per-Employee Profiles)
# ════════════════════════════════════════════

def get_voting_categories(position_level: str, position_title: str) -> list:
    lvl = str(position_level or "").lower()
    title = str(position_title or "").lower()
    
    if "intern" in title or "trainee" in title or "junior" in lvl:
        cats = [("Fast Learner", "🚀"), ("Eagerness", "🔥"), ("Teamwork", "🤝"), ("Adaptability", "🦎"), ("Communication", "🗣️")]
    elif "manager" in lvl or "manager" in title or "executive" in lvl or "senior" in lvl:
        cats = [("Leadership", "👑"), ("Mentoring", "🎓"), ("Strategic Thinking", "🧠"), ("Empathy", "❤️"), ("Decision Making", "⚖️")]
    elif "hr" in title or "human resources" in title:
        cats = [("Empathy", "❤️"), ("Conflict Resolution", "🕊️"), ("Culture Building", "🏢"), ("Communication", "🗣️"), ("Supportiveness", "🤗")]
    elif "engineer" in title or "tech" in title:
        cats = [("Code Quality", "💻"), ("Problem Solving", "🔧"), ("Innovation", "💡"), ("Teamwork", "🤝"), ("Reliability", "🛡️")]
    elif "sales" in title or "marketing" in title:
        cats = [("Client Focus", "🎯"), ("Creativity", "🎨"), ("Target Achievement", "📈"), ("Communication", "🗣️"), ("Negotiation", "🤝")]
    elif "finance" in title or "admin" in title or "accountant" in title:
        cats = [("Attention to Detail", "🔍"), ("Organization", "📋"), ("Reliability", "🛡️"), ("Teamwork", "🤝"), ("Efficiency", "⚡")]
    else:
        cats = [("Teamwork", "🤝"), ("Dedication", "💪"), ("Communication", "🗣️"), ("Reliability", "🛡️"), ("Initiative", "🚀")]
    
    return [{"name": c[0], "icon": c[1]} for c in cats]

def build_vote_stats(votes: list, employees: list) -> dict:
    """Build per-employee vote stats dict keyed by employee id."""
    stats: dict = {}
    emp_name_map = {e["id"]: e.get("Full_name","—") for e in employees}
    for v in votes:
        nid = v.get("nominee_id","")
        if not nid:
            continue
        if nid not in stats:
            stats[nid] = {"votes": 0, "total": 0, "cats": {}, "emp_id": nid,
                          "name": emp_name_map.get(nid,"—")}
        score = int(v.get("score") or 0)
        stats[nid]["votes"]  += 1
        stats[nid]["total"]  += score
        cat = v.get("category","General")
        stats[nid]["cats"].setdefault(cat, []).append(score)
    for nid, s in stats.items():
        s["avg"] = round(s["total"]/s["votes"],1) if s["votes"] else 0
    return stats

@app.get("/peer-voting", response_class=HTMLResponse)
async def peer_voting_page(request: Request):
    employees = db_fetch("Employees", "id,Full_name,employee_id,Dept_id,status", filters={"status":"Active"})
    votes     = db_fetch("peer_voting_records", "*")
    depts     = db_fetch("Departments", "id,Department_name")
    dept_map  = {d["id"]: d["Department_name"] for d in depts}
    for e in employees:
        e["dept_name"] = dept_map.get(e.get("Dept_id",""),"—")
    votes_enriched = []
    emp_map = {e["id"]: e for e in employees}
    for v in votes:
        nom = emp_map.get(v.get("nominee_id",""), {})
        vtr = emp_map.get(v.get("voter_id",""), {})
        v["nominee_name"] = nom.get("Full_name", v.get("nominee_name","—"))
        v["voter_name"]   = vtr.get("Full_name", "—")
        votes_enriched.append(v)
    votes_enriched.sort(key=lambda x: x.get("created_at",""), reverse=True)
    vote_stats = build_vote_stats(votes, employees)
    lb = sorted(vote_stats.values(), key=lambda x: x["total"], reverse=True)[:5]
    for entry in lb:
        entry["emp_id"] = entry.get("emp_id","")
    categories = ["Leadership","Teamwork","Innovation","Communication","Problem Solving"]
    return templates.TemplateResponse("peer_voting.html", ctx(request, "peer_voting",
        employees=employees, vote_stats=vote_stats, leaderboard=lb,
        votes=votes_enriched, categories=categories))

@app.post("/peer-voting/submit", response_class=RedirectResponse)
async def peer_voting_submit(
    voter_id: str = Form(...), nominee_id: str = Form(...),
    category: str = Form(...), score: str = Form(...),
    comment: str = Form(None)):
    if voter_id == nominee_id:
        return redirect_with_msg("/peer-voting", error="You+cannot+recognize+yourself")
    emp = db_fetch_one("Employees", "Full_name", filters={"id": nominee_id})
    db_insert("peer_voting_records", {
        "voter_id": voter_id, "nominee_id": nominee_id,
        "nominee_name": emp.get("Full_name","") if emp else "",
        "category": category, "score": int(score),
        "comment": comment, "created_at": datetime.now().isoformat(),
    })
    return redirect_with_msg("/peer-voting", success="Kudos+posted+successfully+🎉")

@app.get("/peer-voting/{emp_id}", response_class=HTMLResponse)
async def peer_voting_profile(request: Request, emp_id: str):
    nominee = db_fetch_one("Employees", "*", filters={"id": emp_id})
    if not nominee:
        raise HTTPException(404, "Employee not found")
    depts    = db_fetch("Departments","id,Department_name")
    dept_map = {d["id"]: d["Department_name"] for d in depts}
    nominee["dept_name"] = dept_map.get(nominee.get("Dept_id",""),"—")
    all_votes = db_fetch("peer_voting_records", "*", filters={"nominee_id": emp_id})
    voters    = [e for e in db_fetch("Employees","id,Full_name",filters={"status":"Active"})
                 if e["id"] != emp_id]
    all_emps  = db_fetch("Employees", "id,Full_name")
    emp_name_map = {e["id"]: e.get("Full_name","—") for e in all_emps}
    for v in all_votes:
        v["voter_name"] = emp_name_map.get(v.get("voter_id",""),"Anonymous")
    votes_count = len(all_votes)
    total_score = sum(int(v.get("score") or 0) for v in all_votes)
    avg_score   = round(total_score / votes_count, 1) if votes_count else 0
    cat_raw: dict = {}
    for v in all_votes:
        cat = v.get("category","General")
        cat_raw.setdefault(cat, []).append(int(v.get("score") or 0))
    cat_avgs = {cat: round(sum(sc)/len(sc),1) for cat, sc in cat_raw.items()}
    stats = {"votes": votes_count, "total": total_score, "avg": avg_score, "cat_avgs": cat_avgs}
    
    pos_id = nominee.get("position_id")
    pos = db_fetch_one("positions", "*", filters={"id": pos_id}) if pos_id else {}
    lvl = pos.get("level", "")
    title = pos.get("title", "")
    categories = get_voting_categories(lvl, title)
    
    return templates.TemplateResponse("peer_voting_profile.html", ctx(request, "peer_voting",
        nominee=nominee, votes=all_votes, voters=voters,
        categories=categories, stats=stats))

@app.post("/peer-voting/{emp_id}/vote", response_class=RedirectResponse)
async def peer_voting_cast(emp_id: str,
    voter_id: str = Form(...), category: str = Form(...),
    score: str = Form(...), comment: str = Form(None)):
    if voter_id == emp_id:
        return redirect_with_msg(f"/peer-voting/{emp_id}", error="You+cannot+vote+for+yourself")
    nominee = db_fetch_one("Employees", "Full_name", filters={"id": emp_id})
    db_insert("peer_voting_records", {
        "voter_id": voter_id, "nominee_id": emp_id,
        "nominee_name": nominee.get("Full_name","") if nominee else "",
        "category": category, "score": int(score),
        "comment": comment, "created_at": datetime.now().isoformat(),
    })
    name = nominee.get("Full_name","employee") if nominee else "employee"
    return redirect_with_msg(f"/peer-voting/{emp_id}", success=f"Vote+submitted+for+{name}")

@app.get("/attendance/qr/generate", response_class=HTMLResponse)
async def attendance_qr_gen(request: Request):
    data = f"ATTEND:{date.today().isoformat()}"
    img = qrcode.make(data)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_b64 = base64.b64encode(buffered.getvalue()).decode()
    return templates.TemplateResponse("attendance_qr.html", ctx(request, "attendance", qr_img=qr_b64))

@app.post("/attendance/qr/scan")
async def attendance_qr_scan(data: str = Form(...)):
    if not data.startswith("ATTEND:"):
        return {"status": "error", "message": "Invalid QR"}
    return {"status": "success", "message": "Attendance marked"}

# Positions
@app.post("/positions/add", response_class=RedirectResponse)
async def position_add(
    title: str = Form(...), level: str = Form(None),
    team: str = Form(None), base_salary: str = Form("0")):
    db_insert("positions", {
        "title": title, "level": level, "team": team,
        "base_salary": float(base_salary) if base_salary else 0,
        "created_at": datetime.now().isoformat()
    })
    return redirect_with_msg("/recruitment", success=f"Position+{title}+created")

# ════════════════════════════════════════════
#  9. BIRTHDAYS
# ════════════════════════════════════════════
@app.get("/birthdays", response_class=HTMLResponse)
async def birthdays_page(request: Request):
    today    = date.today()
    today_md = today.strftime("%m-%d")
    employees = db_fetch("Employees", "id,employee_id,Full_name,date_of_birth,Dept_id,status")
    depts     = db_fetch("Departments","id,Department_name")
    dept_map  = {d["id"]: d["Department_name"] for d in depts}
    birthday_emps = []
    for e in employees:
        dob = e.get("date_of_birth","")
        if not dob:
            continue
        try:
            dob_date = datetime.strptime(dob[:10], "%Y-%m-%d")
            if dob_date.strftime("%m-%d") == today_md:
                e["dept_name"] = dept_map.get(e.get("Dept_id",""), "—")
                birthday_emps.append(e)
        except:
            pass
    log_entries = []
    for bday_emp in birthday_emps:
        bday_id = bday_emp["id"]
        recipients = [e["id"] for e in employees if e["id"] != bday_id]
        # Create birthday notification
        notif = db_insert("birthday_notification", {
            "employee_id": bday_id,
            "message": f"🎉 Today is {bday_emp['Full_name']}'s Birthday! Wishing them a wonderful day!",
            "channel": "in-app", "is_sent": True,
            "sent_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
        })
        if notif:
            for rid in recipients:
                db_insert("birthday_notification_requests", {
                    "notification_id": notif["id"],
                    "receipt_user_id": rid, "is_read": False,
                    "created_at": datetime.now().isoformat(),
                })
        log_entries.append({
            "name": bday_emp["Full_name"], "id": bday_emp.get("employee_id",""),
            "dept": bday_emp.get("dept_name","—"),
            "dob": bday_emp.get("date_of_birth","—"),
            "recipient_count": len(recipients),
            "message": f"Today is {bday_emp['Full_name']}'s Birthday! 🎉 System generated alert for {len(recipients)} staff members (except receipt_user_id = {bday_emp.get('employee_id','')}).",
        })
    # Upcoming 30 days
    upcoming = []
    for e in employees:
        dob = e.get("date_of_birth","")
        if not dob:
            continue
        try:
            dob_date = datetime.strptime(dob[:10], "%Y-%m-%d")
            this_year = dob_date.replace(year=today.year)
            if this_year.date() < today:
                this_year = this_year.replace(year=today.year+1)
            days_until = (this_year.date() - today).days
            if 0 < days_until <= 30:
                e["days_until"] = days_until
                e["birthday_date"] = this_year.strftime("%d %B %Y")
                e["dept_name"] = dept_map.get(e.get("Dept_id",""), "—")
                upcoming.append(e)
        except:
            pass
    upcoming.sort(key=lambda x: x["days_until"])
    return templates.TemplateResponse("birthdays.html", ctx(request, "birthdays",
        log_entries=log_entries, upcoming=upcoming,
        today=today.strftime("%A, %d %B %Y"), today_raw=today.isoformat(),
        birthday_count=len(birthday_emps)))

# ══════════════════════════════════════════════
#  10. ONBOARDING & PRE-BOARDING
# ══════════════════════════════════════════════
@app.get("/onboarding", response_class=HTMLResponse)
async def onboarding_list(request: Request):
    onboarding = db_fetch("employee_onboarding", "*", order="created_at")
    employees  = db_fetch("Employees", "id,Full_name,employee_id,hire_date,Dept_id", filters={"status":"Active"})
    emp_map    = {e["id"]: e for e in employees}
    depts      = db_fetch("Departments","id,Department_name")
    dept_map   = {d["id"]: d["Department_name"] for d in depts}
    tasks_all  = db_fetch("onboarding_tasks", "id,task_name,is_preboarding")
    for ob in onboarding:
        emp = emp_map.get(ob.get("employee_id",""), {})
        ob["Full_name"]    = emp.get("Full_name", "—")
        ob["employee_code"]= emp.get("employee_id","—")
        ob["dept_name"]    = dept_map.get(emp.get("Dept_id",""), "—")
        # Completion %
        assignments = db_fetch("onboarding_assignments", "id,status", filters={"onboarding_id": ob["id"]})
        if assignments:
            done = sum(1 for a in assignments if a.get("status") == "Completed")
            ob["completion_pct"] = int(done / len(assignments) * 100)
            ob["tasks_done"]     = done
            ob["tasks_total"]    = len(assignments)
        else:
            ob["completion_pct"] = 0
            ob["tasks_done"]     = 0
            ob["tasks_total"]    = 0
    # New hires without onboarding
    onboarded_ids = {ob.get("employee_id") for ob in onboarding}
    new_hires = [e for e in employees if e["id"] not in onboarded_ids]
    stats = {
        "pre_boarding":  sum(1 for o in onboarding if o.get("status") == "Pre-boarding"),
        "in_progress":   sum(1 for o in onboarding if o.get("status") == "In Progress"),
        "completed":     sum(1 for o in onboarding if o.get("status") == "Completed"),
    }
    return templates.TemplateResponse("onboarding/index.html", ctx(request, "onboarding",
        onboarding=onboarding, new_hires=new_hires, stats=stats, tasks_all=tasks_all))

@app.post("/onboarding/start/{emp_id}", response_class=RedirectResponse)
async def onboarding_start(emp_id: str, start_date: str = Form(None), buddy_id: str = Form(None)):
    emp = db_fetch_one("Employees", "id,hire_date,Full_name", filters={"id": emp_id})
    if not emp:
        return redirect_with_msg("/onboarding", error="Employee+not+found")
    sd   = start_date or emp.get("hire_date") or date.today().isoformat()
    end  = (date.fromisoformat(sd[:10]) + timedelta(days=90)).isoformat()
    ob   = db_insert("employee_onboarding", {
        "employee_id": emp_id, "start_date": sd,
        "expected_end_date": end, "status": "Pre-boarding",
        "buddy_id": buddy_id or None, "completion_pct": 0,
        "created_at": datetime.now().isoformat(),
    })
    if ob:
        # Auto-assign all default tasks
        default_tasks = db_fetch("onboarding_tasks", "id,due_days_after_hire")
        for task in default_tasks:
            due = (date.fromisoformat(sd[:10]) + timedelta(days=int(task.get("due_days_after_hire") or 1))).isoformat()
            db_insert("onboarding_assignments", {
                "onboarding_id": ob["id"], "task_id": task["id"],
                "status": "Pending", "due_date": due,
                "created_at": datetime.now().isoformat(),
            })
        return redirect_with_msg(f"/onboarding/{ob['id']}", success="Onboarding+started+with+all+tasks+assigned")
    return redirect_with_msg("/onboarding", error="Failed+to+start+onboarding")

@app.get("/onboarding/{ob_id}", response_class=HTMLResponse)
async def onboarding_detail(request: Request, ob_id: str):
    ob = db_fetch_one("employee_onboarding", "*", filters={"id": ob_id})
    if not ob:
        raise HTTPException(404)
    emp  = db_fetch_one("Employees", "*", filters={"id": ob.get("employee_id","")})
    assignments = db_fetch("onboarding_assignments", "*", filters={"onboarding_id": ob_id})
    tasks_map = {t["id"]: t for t in db_fetch("onboarding_tasks", "*")}
    buddy  = db_fetch_one("Employees", "Full_name", filters={"id": ob.get("buddy_id","")}) if ob.get("buddy_id") else None
    docs   = db_fetch("preboarding_documents", "*", filters={"employee_id": ob.get("employee_id","")})
    employees = db_fetch("Employees","id,Full_name",filters={"status":"Active"})
    for a in assignments:
        task = tasks_map.get(a.get("task_id",""), {})
        a["task_name"]     = task.get("task_name", "—")
        a["category"]      = task.get("category", "—")
        a["is_preboarding"]= task.get("is_preboarding", False)
        a["assigned_to"]   = task.get("assigned_to_role", "HR")
    done  = sum(1 for a in assignments if a.get("status") == "Completed")
    total = len(assignments)
    pct   = int(done/total*100) if total else 0
    # Group by category
    cat_groups: dict = {}
    for a in assignments:
        cat = a.get("category","General")
        cat_groups.setdefault(cat, []).append(a)
    return templates.TemplateResponse("onboarding/detail.html", ctx(request, "onboarding",
        ob=ob, emp=emp, assignments=assignments, cat_groups=cat_groups,
        buddy=buddy, docs=docs, employees=employees,
        done=done, total=total, pct=pct))

@app.post("/onboarding/{ob_id}/task/{assign_id}/complete", response_class=RedirectResponse)
async def onboarding_complete_task(ob_id: str, assign_id: str, notes: str = Form(None)):
    db_update("onboarding_assignments", assign_id, {
        "status": "Completed", "completed_at": datetime.now().isoformat(), "notes": notes
    })
    # Recalculate %
    assignments = db_fetch("onboarding_assignments", "id,status", filters={"onboarding_id": ob_id})
    done  = sum(1 for a in assignments if a.get("status") == "Completed")
    total = len(assignments)
    pct   = int(done/total*100) if total else 0
    new_status = "Completed" if pct == 100 else "In Progress"
    db_update("employee_onboarding", ob_id, {"completion_pct": pct, "status": new_status})
    return redirect_with_msg(f"/onboarding/{ob_id}", success="Task+marked+complete")

@app.post("/onboarding/{ob_id}/doc/add", response_class=RedirectResponse)
async def onboarding_add_doc(ob_id: str,
    document_name: str = Form(...), document_type: str = Form("Other"),
    due_date: str = Form(None), employee_id: str = Form(...)):
    db_insert("preboarding_documents", {
        "employee_id": employee_id, "document_name": document_name,
        "document_type": document_type, "is_signed": False,
        "due_date": due_date or None, "created_at": datetime.now().isoformat(),
    })
    return redirect_with_msg(f"/onboarding/{ob_id}", success="Document+added")

@app.post("/onboarding/{ob_id}/doc/{doc_id}/sign", response_class=RedirectResponse)
async def onboarding_sign_doc(ob_id: str, doc_id: str):
    db_update("preboarding_documents", doc_id, {"is_signed": True, "signed_at": datetime.now().isoformat()})
    return redirect_with_msg(f"/onboarding/{ob_id}", success="Document+marked+as+signed")

# ══════════════════════════════════════════════
#  11. OFFBOARDING & EXIT INTERVIEW
# ══════════════════════════════════════════════
@app.get("/offboarding", response_class=HTMLResponse)
async def offboarding_list(request: Request):
    records   = db_fetch("corporate_offboarding", "*", order="created_at")
    employees = db_fetch("Employees", "id,Full_name,employee_id,Dept_id")
    depts     = db_fetch("Departments","id,Department_name")
    emp_map   = {e["id"]: e for e in employees}
    dept_map  = {d["id"]: d["Department_name"] for d in depts}
    all_emps  = db_fetch("Employees","id,Full_name,employee_id",filters={"status":"Active"})
    offboarded_ids = {r.get("employee_id") for r in records}
    available_emps = [e for e in employees if e["id"] not in offboarded_ids]
    for r in records:
        emp = emp_map.get(r.get("employee_id",""), {})
        r["Full_name"]    = emp.get("Full_name","—")
        r["employee_code"]= emp.get("employee_id","—")
        r["dept_name"]    = dept_map.get(emp.get("Dept_id",""), "—")
        # Task completion
        assignments = db_fetch("offboarding_assignments", "id,status", filters={"offboarding_id": r["id"]})
        done  = sum(1 for a in assignments if a.get("status") == "Completed")
        total = len(assignments)
        r["tasks_done"]  = done
        r["tasks_total"] = total
        r["task_pct"]    = int(done/total*100) if total else 0
        # Check exit interview
        ei = db_fetch_one("exit_interviews", "id,status", filters={"offboarding_id": r["id"]})
        r["exit_interview"] = ei
    stats = {
        "total":    len(records),
        "cleared":  sum(1 for r in records if str(r.get("settlement_status","")).lower().startswith("release")),
        "on_hold":  sum(1 for r in records if str(r.get("settlement_status","")).lower().startswith("hold")),
    }
    return templates.TemplateResponse("offboarding/index.html", ctx(request, "offboarding",
        records=records, available_emps=available_emps, stats=stats))

@app.post("/offboarding/start", response_class=RedirectResponse)
async def offboarding_start(
    employee_id: str = Form(...),
    resignation_date: str = Form(None),
    last_working_date: str = Form(None),
    termination_reason: str = Form("Resignation"),
    exit_type: str = Form("Voluntary"),
    hr_notes: str = Form(None)):
    ob = db_insert("corporate_offboarding", {
        "employee_id": employee_id,
        "resignation_date": resignation_date or None,
        "last_working_date": last_working_date or None,
        "termination_reason": termination_reason,
        "exit_type": exit_type,
        "settlement_status": "Hold Final Payroll",
        "laptop_returned": False, "access_card_returned": False,
        "nda_signed": False, "knowledge_transfer": False,
        "hr_notes": hr_notes, "created_at": datetime.now().isoformat(),
    })
    if ob:
        # Update employee status
        db_update("Employees", employee_id, {"status": "Offboarding", "updated_at": datetime.now().isoformat()})
        # Auto-assign default offboarding tasks
        default_tasks = db_fetch("offboarding_tasks", "id")
        for task in default_tasks:
            db_insert("offboarding_assignments", {
                "offboarding_id": ob["id"], "task_id": task["id"],
                "status": "Pending", "created_at": datetime.now().isoformat(),
            })
        return redirect_with_msg(f"/offboarding/{ob['id']}", success="Offboarding+process+started")
    return redirect_with_msg("/offboarding", error="Failed+to+start+offboarding")

@app.get("/offboarding/{ob_id}", response_class=HTMLResponse)
async def offboarding_detail(request: Request, ob_id: str):
    ob = db_fetch_one("corporate_offboarding", "*", filters={"id": ob_id})
    if not ob:
        raise HTTPException(404)
    emp  = db_fetch_one("Employees", "*", filters={"id": ob.get("employee_id","")})
    assignments = db_fetch("offboarding_assignments", "*", filters={"offboarding_id": ob_id})
    tasks_map   = {t["id"]: t for t in db_fetch("offboarding_tasks", "*")}
    for a in assignments:
        task = tasks_map.get(a.get("task_id",""), {})
        a["task_name"]  = task.get("task_name","—")
        a["category"]   = task.get("category","—")
        a["responsible"]= task.get("responsible","HR")
    done  = sum(1 for a in assignments if a.get("status") == "Completed")
    total = len(assignments)
    pct   = int(done/total*100) if total else 0
    ei    = db_fetch_one("exit_interviews", "*", filters={"offboarding_id": ob_id})
    employees = db_fetch("Employees","id,Full_name",filters={"status":"Active"})
    cat_groups: dict = {}
    for a in assignments:
        cat = a.get("category","General")
        cat_groups.setdefault(cat, []).append(a)
    return templates.TemplateResponse("offboarding/detail.html", ctx(request, "offboarding",
        ob=ob, emp=emp, assignments=assignments, cat_groups=cat_groups,
        done=done, total=total, pct=pct, ei=ei, employees=employees))

@app.post("/offboarding/{ob_id}/task/{assign_id}/complete", response_class=RedirectResponse)
async def offboarding_complete_task(ob_id: str, assign_id: str, notes: str = Form(None)):
    db_update("offboarding_assignments", assign_id, {
        "status": "Completed", "completed_at": datetime.now().isoformat(), "notes": notes
    })
    return redirect_with_msg(f"/offboarding/{ob_id}", success="Task+completed")

@app.post("/api/offboarding/toggle", response_class=JSONResponse)
async def offboarding_toggle(request: Request):
    body  = await request.json()
    ob_id = body.get("id")
    field = body.get("field")
    value = body.get("value")
    allowed = {"laptop_returned","access_card_returned","nda_signed","knowledge_transfer"}
    if field not in allowed:
        raise HTTPException(400, "Invalid field")
    db_update("corporate_offboarding", ob_id, {field: value, "updated_at": datetime.now().isoformat()})
    # Re-fetch and check all clearance fields
    ob = db_fetch_one("corporate_offboarding", "id,laptop_returned,access_card_returned,nda_signed,knowledge_transfer", filters={"id": ob_id})
    all_checks = body.get("all_checks", {})
    all_checks[field] = value
    all_cleared = (
        all_checks.get("laptop_returned", ob.get("laptop_returned", False) if ob else False) and
        all_checks.get("access_card_returned", ob.get("access_card_returned", False) if ob else False) and
        all_checks.get("nda_signed", ob.get("nda_signed", False) if ob else False)
    )
    new_status = "Release Final Settlement" if all_cleared else "Hold Final Payroll"
    db_update("corporate_offboarding", ob_id, {"settlement_status": new_status})
    return {"success": True, "settlement_status": new_status, "all_cleared": all_cleared}

@app.get("/offboarding/{ob_id}/exit-interview", response_class=HTMLResponse)
async def exit_interview_form(request: Request, ob_id: str):
    ob  = db_fetch_one("corporate_offboarding", "*", filters={"id": ob_id})
    emp = db_fetch_one("Employees", "*", filters={"id": ob.get("employee_id","")}) if ob else None
    ei  = db_fetch_one("exit_interviews", "*", filters={"offboarding_id": ob_id})
    interviewers = db_fetch("Employees","id,Full_name",filters={"status":"Active"})
    return templates.TemplateResponse("offboarding/exit_interview.html", ctx(request, "offboarding",
        ob=ob, emp=emp, ei=ei, interviewers=interviewers))

@app.post("/offboarding/{ob_id}/exit-interview", response_class=RedirectResponse)
async def exit_interview_save(ob_id: str,
    interviewer_id: str = Form(None),
    interview_date: str = Form(None),
    reason_for_leaving: str = Form(None),
    job_satisfaction: str = Form("3"),
    management_rating: str = Form("3"),
    work_env_rating: str = Form("3"),
    compensation_rating: str = Form("3"),
    growth_rating: str = Form("3"),
    would_return: str = Form("false"),
    would_recommend: str = Form("false"),
    highlights: str = Form(None),
    improvements: str = Form(None),
    additional_comments: str = Form(None)):
    ob = db_fetch_one("corporate_offboarding","employee_id",filters={"id":ob_id})
    ei = db_fetch_one("exit_interviews","id",filters={"offboarding_id":ob_id})
    data = {
        "offboarding_id": ob_id,
        "employee_id": ob.get("employee_id") if ob else None,
        "interviewer_id": interviewer_id or None,
        "interview_date": interview_date or None,
        "reason_for_leaving": reason_for_leaving,
        "job_satisfaction": int(job_satisfaction),
        "management_rating": int(management_rating),
        "work_env_rating": int(work_env_rating),
        "compensation_rating": int(compensation_rating),
        "growth_rating": int(growth_rating),
        "would_return": would_return.lower() == "true",
        "would_recommend": would_recommend.lower() == "true",
        "highlights": highlights,
        "improvements": improvements,
        "additional_comments": additional_comments,
        "status": "Completed",
        "created_at": datetime.now().isoformat(),
    }
    if ei:
        db_update("exit_interviews", ei["id"], data)
    else:
        db_insert("exit_interviews", data)
    return redirect_with_msg(f"/offboarding/{ob_id}", success="Exit+interview+saved+successfully")

# ════════════════════════════════════════════
#  BOSS PANEL
# ════════════════════════════════════════════

@app.get("/boss", response_class=HTMLResponse)
async def boss_dashboard(request: Request):
    # Company-wide analytics
    employees   = db_fetch("Employees", "id,Full_name,Dept_id,status,salary", filters={"status":"Active"})
    depts       = db_fetch("Departments", "id,Department_name")
    dept_map    = {d["id"]: d["Department_name"] for d in depts}
    payrolls    = db_fetch("payrolls", "basic_salary,net_salary,payment_status,employee_id")
    att_records = db_fetch("attendance_records", "employee_id,check_in,is_late")
    kpi_assigns = db_fetch("boss_kpi_assignments", "*", order="created_at")
    announcements = db_fetch("announcements", "*", order="created_at")
    sys_users   = db_fetch("sys_users", "id,username,role,full_name,is_active")
    # Stats
    total_headcount = len(employees)
    total_payroll   = sum(float(p.get("net_salary") or 0) for p in payrolls if p.get("payment_status") == "Paid")
    this_month      = date.today().strftime("%Y-%m")
    month_att       = [a for a in att_records if str(a.get("check_in","")).startswith(this_month)]
    late_pct        = round(sum(1 for a in month_att if a.get("is_late")) / len(month_att) * 100, 1) if month_att else 0
    # Dept headcount
    dept_counts = {}
    for e in employees:
        dn = dept_map.get(e.get("Dept_id",""), "Other")
        dept_counts[dn] = dept_counts.get(dn, 0) + 1
    # Pending KPIs
    pending_kpis = [k for k in kpi_assigns if k.get("status") == "Pending"]
    return templates.TemplateResponse("boss/dashboard.html", ctx(request, "boss",
        total_headcount=total_headcount, total_payroll=total_payroll,
        late_pct=late_pct, month_att_count=len(month_att),
        dept_counts=dept_counts, kpi_assigns=kpi_assigns, pending_kpis=pending_kpis,
        announcements=announcements[:5], sys_users=sys_users))

@app.get("/boss/kpi", response_class=HTMLResponse)
async def boss_kpi(request: Request):
    kpi_assigns = db_fetch("boss_kpi_assignments", "*", order="created_at")
    sys_users   = db_fetch("sys_users", "id,username,role,full_name",
                           filters={"is_active": True})
    managers    = [u for u in sys_users if u.get("role") in ["hr_manager","general_manager"]]
    return templates.TemplateResponse("boss/kpi.html", ctx(request, "boss",
        kpi_assigns=kpi_assigns, managers=managers))

@app.post("/boss/kpi/add", response_class=RedirectResponse)
async def boss_kpi_add(request: Request,
    title: str = Form(...), description: str = Form(None),
    assigned_to_id: str = Form(None), assigned_to_name: str = Form(None),
    target_value: str = Form(None), deadline: str = Form(None)):
    user = get_current_user(request)
    db_insert("boss_kpi_assignments", {
        "title": title, "description": description,
        "assigned_to_id": assigned_to_id or None,
        "assigned_to_name": assigned_to_name,
        "target_value": target_value,
        "deadline": deadline or None,
        "status": "Pending",
        "created_by": user.get("full_name","Boss") if user else "Boss",
        "created_at": datetime.now().isoformat(),
    })
    return redirect_with_msg("/boss/kpi", success=f"KPI+'{title}'+assigned")

@app.post("/boss/kpi/{kpi_id}/update", response_class=RedirectResponse)
async def boss_kpi_update(kpi_id: str, status: str = Form(...)):
    db_update("boss_kpi_assignments", kpi_id, {
        "status": status, "updated_at": datetime.now().isoformat()
    })
    return redirect_with_msg("/boss/kpi", success=f"KPI+updated+to+{status}")

@app.post("/boss/users/{user_id}/delete", response_class=RedirectResponse)
async def boss_users_delete(user_id: str):
    db_delete("sys_users", user_id)
    return redirect_with_msg("/boss/users", success="User+deleted")

@app.post("/boss/request-document", response_class=RedirectResponse)
async def boss_request_document(request: Request, employee_id: str = Form(...), instructions: str = Form(...)):
    user = get_current_user(request)
    if not user or user.get("role") != "boss":
        return redirect_with_msg("/employees", error="Unauthorized")
    emp = db_fetch_one("Employees", "Full_name", filters={"id": employee_id})
    emp_name = emp.get("Full_name", "An employee") if emp else "An employee"
    notify_role("hr_manager", "Document Request from Boss", f"Boss requested a document for {emp_name}: {instructions}", "/documents")
    return redirect_with_msg("/employees", success="Request+sent+to+HR")

@app.post("/boss/kpi/{kpi_id}/delete", response_class=RedirectResponse)
async def boss_kpi_delete(kpi_id: str):
    db_delete("boss_kpi_assignments", kpi_id)
    return redirect_with_msg("/boss/kpi", success="KPI+removed")

@app.post("/boss/users/{user_id}/edit", response_class=RedirectResponse)
async def boss_users_edit(request: Request, user_id: str,
    full_name: str = Form(...), username: str = Form(...)):
    user = get_current_user(request)
    if not user or user.get("role") != "boss":
        raise HTTPException(403, "Access denied")
    
    try:
        db_update("sys_users", user_id, {"full_name": full_name, "username": username})
        return redirect_with_msg("/boss/users", success="User+account+updated")
    except Exception as e:
        return redirect_with_msg("/boss/users", error="Failed+to+update+user+(username+might+exist)")

@app.get("/boss/announcements", response_class=HTMLResponse)
async def boss_announcements(request: Request):
    announcements = db_fetch("announcements", "*", order="created_at")
    employees = db_fetch("Employees", "id,Full_name", filters={"status":"Active"}, order="Full_name")
    
    emp_dict = {str(e.get("id")): e.get("Full_name") for e in employees}
    for a in announcements:
        if a.get("target_role") in emp_dict:
            a["target_name"] = emp_dict[a.get("target_role")]
            
    return templates.TemplateResponse("boss/announcements.html", ctx(request, "boss",
        announcements=announcements, employees=employees))

@app.post("/boss/announcements/add", response_class=RedirectResponse)
async def boss_announcement_add(request: Request,
    title: str = Form(...), content: str = Form(...),
    priority: str = Form("Medium"), target_role: str = Form("All"),
    is_pinned: str = Form("false")):
    user = get_current_user(request)
    
    if user and user.get("role") == "boss":
        target_role = "Pending HR Review"
        
    db_insert("announcements", {
        "title": title, "content": content,
        "priority": priority, "target_role": target_role,
        "is_pinned": is_pinned.lower() == "true",
        "created_by": user.get("full_name","Boss") if user else "Boss",
        "created_at": datetime.now().isoformat(),
    })
    return redirect_with_msg("/boss/announcements", success="Announcement+posted")

@app.post("/boss/announcements/{ann_id}/delete", response_class=RedirectResponse)
async def boss_announcement_delete(ann_id: str):
    db_delete("announcements", ann_id)
    return redirect_with_msg("/boss/announcements", success="Announcement+deleted")

@app.post("/boss/announcements/{ann_id}/publish", response_class=RedirectResponse)
async def boss_announcement_publish(ann_id: str):
    db_update("announcements", ann_id, {"target_role": "All"})
    return redirect_with_msg("/boss/announcements", success="Announcement+published")

@app.get("/boss/users", response_class=HTMLResponse)
async def boss_users(request: Request):
    sys_users   = db_fetch("sys_users", "*", order="created_at")
    employees   = db_fetch("Employees", "id,Full_name,employee_id", filters={"status":"Active"})
    return templates.TemplateResponse("boss/users.html", ctx(request, "boss",
        sys_users=sys_users, employees=employees))

@app.post("/boss/users/add", response_class=RedirectResponse)
async def boss_user_add(
    username: str = Form(...), password: str = Form(...),
    role: str = Form("employee"), full_name: str = Form(None),
    employee_id: str = Form(None)):
    pw_hash = hash_password(password)
    result = db_insert("sys_users", {
        "username": username, "password_hash": pw_hash,
        "role": role, "full_name": full_name or username,
        "employee_id": employee_id or None,
        "is_active": True, "created_at": datetime.now().isoformat(),
    })
    if result:
        return redirect_with_msg("/boss/users", success=f"User+{username}+created")
    return redirect_with_msg("/boss/users", error="Username+already+exists")

@app.post("/boss/users/{user_id}/toggle", response_class=RedirectResponse)
async def boss_user_toggle(user_id: str, is_active: str = Form(...)):
    active = is_active.lower() == "true"
    db_update("sys_users", user_id, {"is_active": active})
    status = "activated" if active else "deactivated"
    return redirect_with_msg("/boss/users", success=f"User+{status}")

@app.post("/boss/users/{user_id}/reset-password", response_class=RedirectResponse)
async def boss_reset_password(user_id: str, new_password: str = Form(...)):
    new_pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    db_update("sys_users", user_id, {"password_hash": new_pw_hash})
    return redirect_with_msg("/boss/users", success="Password+reset+successfully")

@app.post("/boss/users/{user_id}/delete", response_class=RedirectResponse)
async def boss_user_delete(user_id: str):
    db_delete("sys_users", user_id)
    return redirect_with_msg("/boss/users", success="User+account+deleted")
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  EMPLOYEE SELF-SERVICE PORTAL
def get_portal_employee(request: Request) -> dict | None:
    """Get the Employees record linked to the logged-in portal user."""
    user = get_current_user(request)
    if not user or not user.get("employee_id"):
        return None
    return db_fetch_one("Employees", "*", filters={"id": user["employee_id"]})

@app.get("/portal", response_class=HTMLResponse)
async def portal_home(request: Request):
    user = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    emp    = db_fetch_one("Employees", "*", filters={"id": emp_id}) if emp_id else None
    # Quick stats
    att_count   = len(db_fetch("attendance_records", "id", filters={"employee_id": emp_id})) if emp_id else 0
    leave_count = len(db_fetch("Leave_Request", "id", filters={"employee_id": emp_id})) if emp_id else 0
    payslip_cnt = len(db_fetch("payrolls", "id", filters={"employee_id": emp_id})) if emp_id else 0
    # Announcements (all + role-targeted)
    all_ann = db_fetch("announcements", "*", order="created_at")
    ann_list = [a for a in all_ann
                if a.get("target_role") in ["All", user.get("role","employee"), emp_id] if user]
    # My KPI score
    votes = db_fetch("peer_voting_records", "score", filters={"nominee_id": emp_id}) if emp_id else []
    vote_avg = round(sum(int(v.get("score",0)) for v in votes)/len(votes),1) if votes else 0
    # Leave balances
    lt_map = {lt["id"]: lt["type_name"] for lt in db_fetch("Leave_type","id,type_name")}
    leave_bals = db_fetch("Leave_balances","*",filters={"employee_id":emp_id}) if emp_id else []
    for b in leave_bals:
        b["type_name"] = lt_map.get(b.get("leave_type_id",""),"Leave")
    return templates.TemplateResponse("portal/home.html", ctx(request, "portal",
        emp=emp, att_count=att_count, leave_count=leave_count,
        payslip_count=payslip_cnt, ann_list=ann_list,
        vote_avg=vote_avg, vote_count=len(votes), leave_bals=leave_bals))

@app.get("/portal/attendance", response_class=HTMLResponse)
async def portal_attendance(request: Request):
    user = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    records = enrich_attendance_records(
        db_fetch("attendance_records","*",filters={"employee_id":emp_id},order="check_in"),
        {emp_id: db_fetch_one("Employees","id,Full_name,employee_id",filters={"id":emp_id}) or {}}
    ) if emp_id else []
    return templates.TemplateResponse("portal/attendance.html", ctx(request, "portal",
        records=records, emp_id=emp_id))

@app.get("/portal/attendance/photo", response_class=HTMLResponse)
async def portal_photo_page(request: Request):
    return templates.TemplateResponse("portal/photo_checkin.html", ctx(request, "portal"))

@app.get("/portal/leaves", response_class=HTMLResponse)
async def portal_leaves(request: Request):
    user = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    lt_map     = {lt["id"]: lt["type_name"] for lt in db_fetch("Leave_type","id,type_name")}
    leave_reqs = db_fetch("Leave_Request","*",filters={"employee_id":emp_id},order="created_at") if emp_id else []
    leave_bals = db_fetch("Leave_balances","*",filters={"employee_id":emp_id}) if emp_id else []
    leave_types= db_fetch("Leave_type","id,type_name")
    for lr in leave_reqs:
        lr["type_name"] = lt_map.get(lr.get("leave_type_id",""),"Leave")
    for b in leave_bals:
        b["type_name"] = lt_map.get(b.get("leave_type_id",""),"Leave")
    return templates.TemplateResponse("portal/leaves.html", ctx(request, "portal",
        leave_requests=leave_reqs, leave_balances=leave_bals,
        leave_types=leave_types, emp_id=emp_id,
        today_date=date.today().isoformat()))

@app.get("/portal/payslips", response_class=HTMLResponse)
async def portal_payslips(request: Request):
    user = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    payrolls = db_fetch("payrolls","*",filters={"employee_id":emp_id},order="month") if emp_id else []
    total_earned = sum(float(p.get("net_salary") or 0) for p in payrolls if p.get("payment_status")=="Paid")
    return templates.TemplateResponse("portal/payslips.html", ctx(request, "portal",
        payrolls=payrolls, total_earned=total_earned))

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  ENTRY POINT
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

# ── Portal: Leave Submit ──────────────────────────────────────────────
@app.post("/portal/leaves/add", response_class=RedirectResponse)
async def portal_leave_add(request: Request,
    leave_type_id: str = Form(...),
    start_date: str = Form(...), end_date: str = Form(...),
    reason: str = Form(None)):
    user   = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    if not emp_id:
        return redirect_with_msg("/portal/leaves", error="Account+not+linked+to+employee+record")
    d1    = date.fromisoformat(start_date)
    d2    = date.fromisoformat(end_date)
    total = (d2 - d1).days + 1
    bal   = get_or_create_balance(emp_id, leave_type_id)
    remain = int(bal.get("remain_days") or 0)
    lt     = db_fetch_one("Leave_type", filters={"id": leave_type_id})
    lt_name = lt.get("type_name","Leave") if lt else "Leave"
    if total > remain:
        return redirect_with_msg("/portal/leaves",
            error=f"Only+{remain}+day(s)+of+{lt_name}+remaining")
    db_insert("Leave_Request", {
        "employee_id": emp_id, "leave_type_id": leave_type_id,
        "start_date": start_date, "end_date": end_date,
        "total_days": total, "reason": reason,
        "status": "Pending", "created_at": datetime.now().isoformat(),
    })
    
    emp = db_fetch_one("Employees", "Full_name", filters={"id": emp_id})
    emp_name = emp.get("Full_name", "An employee") if emp else "An employee"
    
    notify_role("hr_manager", "New Leave Request", f"{emp_name} submitted a leave request for {total} day(s) of {lt_name}.", "/leave")
    notify_role("boss", "New Leave Request", f"{emp_name} submitted a leave request for {total} day(s) of {lt_name}.", "/leave")
    return redirect_with_msg("/portal/leaves",
        success="Leave+request+submitted.+Awaiting+HR+approval.")

# ── Portal: Photo Check-In POST ──────────────────────────────────────────
@app.post("/portal/attendance/photo-checkin", response_class=RedirectResponse)
async def portal_photo_checkin(request: Request,
    photo_data: str = Form(...)):
    user   = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    if not emp_id:
        return redirect_with_msg("/portal/attendance/photo", error="Account+not+linked+to+employee")
    today    = date.today().isoformat()
    existing = db_fetch("attendance_records", "id,check_in", filters={"employee_id": emp_id})
    already  = any(str(r.get("check_in","")).startswith(today) for r in existing)
    if already:
        return redirect_with_msg("/portal/attendance/photo", error="Already+checked+in+today")
    now_str = datetime.now().isoformat()
    is_late = datetime.now().hour >= 9
    db_insert("attendance_records", {
        "employee_id": emp_id, "check_in": now_str,
        "attendance_method": "Photo", "is_late": is_late,
        "created_at": now_str,
    })
    return redirect_with_msg("/portal/attendance", success="Photo+check-in+successful!")

# ── Portal: QR Check-In page ──────────────────────────────────────────────
@app.get("/portal/qr-checkin", response_class=HTMLResponse)
async def portal_qr_checkin(request: Request):
    user   = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    tokens = db_fetch("qr_attendance_tokens", "*", filters={"employee_id": emp_id}) if emp_id else []
    now    = datetime.now()
    active_token = None
    for t in tokens:
        if t.get("used"):
            continue
        try:
            exp = datetime.fromisoformat(str(t["expires_at"]).replace("Z", "+00:00")).replace(tzinfo=None)
            if now < exp:
                active_token = t
                break
        except Exception:
            pass
    scan_url = None
    if active_token:
        base_url = str(request.base_url).rstrip("/")
        scan_url = f"{base_url}/attendance/scan/{active_token['token']}"
        qr  = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(scan_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        active_token["qr_b64"] = base64.b64encode(buf.getvalue()).decode()
    has_checked_in = False
    if emp_id:
        today_prefix = now.isoformat()[:10]
        records = db_fetch("attendance_records", "*", filters={"employee_id": emp_id})
        if any(r.get("check_in", "").startswith(today_prefix) for r in records):
            has_checked_in = True

    return templates.TemplateResponse("portal/qr_checkin.html", ctx(request, "portal",
        active_token=active_token, scan_url=scan_url, emp_id=emp_id, has_checked_in=has_checked_in))

# ── Portal: My Profile ────────────────────────────────────────────────────
@app.get("/portal/profile", response_class=HTMLResponse)
async def portal_profile(request: Request):
    user   = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    emp    = db_fetch_one("Employees", "*", filters={"id": emp_id}) if emp_id else None
    dept   = None
    if emp and emp.get("Dept_id"):
        dept = db_fetch_one("Departments", "Department_name", filters={"id": emp["Dept_id"]})
    return templates.TemplateResponse("portal/profile.html", ctx(request, "portal",
        emp=emp, dept=dept))

@app.post("/portal/vote/submit", response_class=RedirectResponse)
async def portal_vote_submit(request: Request,
    nominee_id: str = Form(...), score: int = Form(...),
    comment: str = Form(None)):
    user   = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    if not emp_id:
        return redirect_with_msg("/portal/vote", error="Account+not+linked")
    today    = date.today().isoformat()
    existing = db_fetch("peer_voting_records", "id,created_at",
                        filters={"voter_id": emp_id, "nominee_id": nominee_id})
    for v in existing:
        if str(v.get("created_at","")).startswith(today):
            return redirect_with_msg("/portal/vote", error="Already+voted+for+this+colleague+today")
    db_insert("peer_voting_records", {
        "voter_id": emp_id, "nominee_id": nominee_id,
        "score": score, "comment": comment,
        "created_at": datetime.now().isoformat(),
    })
    return redirect_with_msg("/portal/vote", success="Vote+submitted!")


# ── Portal: Peer Voting — Grid ────────────────────────────────────────────
@app.get("/portal/vote", response_class=HTMLResponse)
async def portal_vote_grid(request: Request):
    user       = get_current_user(request)
    emp_id     = user.get("employee_id","") if user else ""
    employees  = db_fetch("Employees", "id,Full_name,employee_id,Dept_id,status", filters={"status":"Active"})
    votes      = db_fetch("peer_voting_records", "*")
    depts      = db_fetch("Departments", "id,Department_name")
    dept_map   = {d["id"]: d["Department_name"] for d in depts}
    for e in employees:
        e["dept_name"] = dept_map.get(e.get("Dept_id",""),"—")
    vote_stats = build_vote_stats(votes, employees)
    lb = sorted(vote_stats.values(), key=lambda x: x["total"], reverse=True)[:5]
    return templates.TemplateResponse("portal/vote.html", ctx(request, "portal",
        employees=employees, vote_stats=vote_stats, leaderboard=lb, emp_id=emp_id))

# ── Portal: Peer Voting — Profile ────────────────────────────────────────
@app.get("/portal/vote/{nominee_id}", response_class=HTMLResponse)
async def portal_vote_profile(request: Request, nominee_id: str):
    user       = get_current_user(request)
    emp_id     = user.get("employee_id","") if user else ""
    nominee    = db_fetch_one("Employees", "*", filters={"id": nominee_id})
    if not nominee:
        raise HTTPException(404, "Employee not found")
    depts      = db_fetch("Departments","id,Department_name")
    dept_map   = {d["id"]: d["Department_name"] for d in depts}
    nominee["dept_name"] = dept_map.get(nominee.get("Dept_id",""),"—")
    all_votes  = db_fetch("peer_voting_records", "*", filters={"nominee_id": nominee_id})
    all_emps   = db_fetch("Employees", "id,Full_name")
    emp_name_map = {e["id"]: e.get("Full_name","—") for e in all_emps}
    for v in all_votes:
        v["voter_name"] = emp_name_map.get(v.get("voter_id",""),"Anonymous")
    votes_count = len(all_votes)
    total_score = sum(int(v.get("score") or 0) for v in all_votes)
    avg_score   = round(total_score / votes_count, 1) if votes_count else 0
    cat_raw: dict = {}
    for v in all_votes:
        cat = v.get("category","General")
        cat_raw.setdefault(cat, []).append(int(v.get("score") or 0))
    cat_avgs = {cat: round(sum(sc)/len(sc),1) for cat, sc in cat_raw.items()}
    stats = {"votes": votes_count, "total": total_score, "avg": avg_score, "cat_avgs": cat_avgs}
    
    pos_id = nominee.get("position_id")
    pos = db_fetch_one("positions", "*", filters={"id": pos_id}) if pos_id else {}
    lvl = pos.get("level", "")
    title = pos.get("title", "")
    categories = get_voting_categories(lvl, title)
    
    return templates.TemplateResponse("portal/vote_profile.html", ctx(request, "portal",
        nominee=nominee, votes=all_votes, categories=categories,
        stats=stats, emp_id=emp_id))

# ── Portal: Peer Voting — Cast Vote POST ────────────────────────────────
@app.post("/portal/vote/{nominee_id}/submit", response_class=RedirectResponse)
async def portal_vote_cast(request: Request, nominee_id: str,
    category: str = Form(...), score: int = Form(...),
    comment: str = Form(None)):
    user   = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    if not emp_id:
        return redirect_with_msg(f"/portal/vote/{nominee_id}", error="Account+not+linked+to+employee")
    if emp_id == nominee_id:
        return redirect_with_msg(f"/portal/vote/{nominee_id}", error="You+cannot+vote+for+yourself")
    nominee = db_fetch_one("Employees","Full_name",filters={"id":nominee_id})
    name    = nominee.get("Full_name","") if nominee else ""
    db_insert("peer_voting_records", {
        "voter_id": emp_id, "nominee_id": nominee_id,
        "score": score, "category": category, "comment": comment,
        "created_at": datetime.now().isoformat(),
    })
    return redirect_with_msg(f"/portal/vote/{nominee_id}",
        success=f"Vote+submitted+for+{name.replace(' ','+')}")

# ── DOCUMENTS VAULT ─────────────────────────────────────────────
@app.get("/documents", response_class=HTMLResponse)
async def documents_list(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", 302)
    
    is_hr_or_boss = user.get("role") in ["boss", "hr_manager", "admin"]
    filters = {} if is_hr_or_boss else {"employee_id": user.get("employee_id")}
    
    docs = db_fetch("employee_documents", "*", filters=filters, order="created_at")
    
    # Filter out internal states for employees
    if not is_hr_or_boss:
        docs = [d for d in docs if d.get("status") not in ["Pending Boss Signature", "Pending Boss Signature (Final)", "Pending HR Signature"]]

    employees = db_fetch("Employees", "id,Full_name", filters={"status":"Active"})
    emp_map = {e["id"]: e.get("Full_name", "—") for e in employees}
    
    for d in docs:
        d["employee_name"] = emp_map.get(d.get("employee_id"), "—")
        
    return templates.TemplateResponse("documents/index.html", ctx(request, "documents", docs=docs, employees=employees, is_hr_or_boss=is_hr_or_boss))

@app.post("/documents/add", response_class=RedirectResponse)
async def documents_add(request: Request,
    employee_id: str = Form(...), doc_type: str = Form(...),
    title: str = Form(...), content: str = Form(...),
    signature_workflow: str = Form("hr_then_employee")):
    user = get_current_user(request)
    if not user or user.get("role") not in ["boss", "hr_manager", "admin"]:
        return redirect_with_msg("/documents", error="Unauthorized")
        
    if signature_workflow.startswith("boss_then"):
        status = "Pending Boss Signature"
    else:
        status = "Pending HR Signature"
    
    db_insert("employee_documents", {
        "employee_id": employee_id,
        "doc_type": doc_type,
        "title": title,
        "content": content,
        "status": status,
        "signature_workflow": signature_workflow,
        "created_by": user.get("id"),
        "created_at": datetime.now().isoformat()
    })
    
    emp = db_fetch_one("Employees", "Full_name", filters={"id": employee_id})
    emp_name = emp.get("Full_name", "An employee") if emp else "An employee"
    
    if status == "Pending Boss Signature":
        notify_role("boss", "Signature Required", f"A new document ({title}) for {emp_name} requires your signature.", "/documents")
    else:
        notify_role("hr_manager", "Signature Required", f"A new document ({title}) for {emp_name} requires your signature.", "/documents")
    
    return redirect_with_msg("/documents", success="Document+issued+successfully")

@app.get("/documents/{doc_id}", response_class=HTMLResponse)
async def document_view(request: Request, doc_id: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", 302)
        
    doc = db_fetch_one("employee_documents", "*", filters={"id": doc_id})
    if not doc:
        return redirect_with_msg("/documents", error="Document+not+found")
        
    is_hr_or_boss = user.get("role") in ["boss", "hr_manager", "admin"]
    if not is_hr_or_boss and str(doc.get("employee_id")) != str(user.get("employee_id")):
        return redirect_with_msg("/documents", error="Unauthorized")

    emp = db_fetch_one("Employees", "Full_name", filters={"id": doc.get("employee_id")})
    doc["employee_name"] = emp.get("Full_name", "—") if emp else "—"
    
    sigs = db_fetch("document_signatures", "*", filters={"document_id": doc_id})
    return templates.TemplateResponse("documents/view.html", ctx(request, "documents", doc=doc, signatures=sigs, is_hr_or_boss=is_hr_or_boss))

@app.post("/documents/{doc_id}/sign", response_class=RedirectResponse)
async def document_sign(request: Request, doc_id: str, signature_data: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", 302)
        
    doc = db_fetch_one("employee_documents", "*", filters={"id": doc_id})
    if not doc:
        return redirect_with_msg("/documents", error="Document+not+found")

    db_insert("document_signatures", {
        "document_id": doc_id,
        "signer_id": user.get("id"),
        "signer_role": user.get("role"),
        "signature_data": signature_data,
        "signed_at": datetime.now().isoformat()
    })
    
    emp = db_fetch_one("Employees", "Full_name", filters={"id": doc.get("employee_id")})
    emp_name = emp.get("Full_name", "An employee") if emp else "An employee"

    doc_status = doc.get("status")
    workflow = doc.get("signature_workflow", "hr_then_employee")

    if doc_status == "Pending HR Signature":
        if workflow == "hr_then_employee":
            db_update("employee_documents", doc_id, {"status": "Pending Signature"})
            notify_employee(str(doc.get("employee_id")), "Signature Required", f"A new document ({doc.get('title')}) requires your signature.", "/documents")
        elif workflow == "boss_then_hr":
            db_update("employee_documents", doc_id, {"status": "Signed"})
            notify_employee(str(doc.get("employee_id")), "New Document Issued", f"A new document ({doc.get('title')}) has been issued to you.", "/documents")
        elif workflow == "boss_then_hr_then_employee":
            db_update("employee_documents", doc_id, {"status": "Pending Signature"})
            notify_employee(str(doc.get("employee_id")), "Signature Required", f"A new document ({doc.get('title')}) requires your signature.", "/documents")

    elif doc_status == "Pending Boss Signature":
        db_update("employee_documents", doc_id, {"status": "Pending HR Signature"})
        notify_role("hr_manager", "Signature Required", f"Boss has signed. Document ({doc.get('title')}) for {emp_name} requires your final signature.", "/documents")
        
    else:
        db_update("employee_documents", doc_id, {"status": "Signed"})
        notify_role("hr_manager", "Employee Signed Document", f"{emp_name} has signed their document ({doc.get('title')}).", "/documents")
        notify_role("boss", "Employee Signed Document", f"{emp_name} has signed their document ({doc.get('title')}).", "/documents")
    
    return redirect_with_msg(f"/documents/{doc_id}", success="Document+signed+successfully")

@app.post("/documents/{doc_id}/edit", response_class=RedirectResponse)
async def document_edit(request: Request, doc_id: str, 
    title: str = Form(...), content: str = Form(...)):
    user = get_current_user(request)
    if not user or user.get("role") not in ["boss", "hr_manager", "admin"]:
        return redirect_with_msg("/documents", error="Unauthorized")
        
    # Only allow editing if not signed
    doc = db_fetch_one("employee_documents", "*", filters={"id": doc_id})
    if not doc:
        return redirect_with_msg("/documents", error="Document+not+found")
        
    if doc.get("status") == "Signed":
        return redirect_with_msg(f"/documents/{doc_id}", error="Cannot+edit+a+signed+document")
        
    db_update("employee_documents", doc_id, {
        "title": title,
        "content": content
    })
    
    return redirect_with_msg(f"/documents/{doc_id}", success="Document+updated+successfully")

@app.get("/documents/{doc_id}/delete", response_class=RedirectResponse)
async def document_delete(request: Request, doc_id: str):
    user = get_current_user(request)
    if not user or user.get("role") not in ["boss", "hr_manager", "admin"]:
        return redirect_with_msg("/documents", error="Unauthorized")
        
    db_delete("employee_documents", doc_id)
    return redirect_with_msg("/documents", success="Document+deleted+successfully")

# ══════════════════════════════════════════════
#  DAILY SOPS & VIDEOS
# ══════════════════════════════════════════════
@app.get("/sops", response_class=HTMLResponse)
async def admin_sops_list(request: Request):
    user = get_current_user(request)
    if not user or user.get("role") not in ["boss", "hr_manager", "admin"]:
        return redirect_with_msg("/dashboard", error="Unauthorized")
    
    sops = db_fetch("daily_sops", "*", order="created_at")
    employees = db_fetch("Employees", "id,Full_name,employee_id,position_id", filters={"status":"Active"})
    departments = db_fetch("Departments", "id,Department_name", order="Department_name")
    positions = db_fetch("positions", "id,title,level", order="title")
    emp_map = {str(e["id"]): e for e in employees}
    pos_map = {str(p["id"]): p for p in positions}
    
    for sop in sops:
        emp = emp_map.get(sop.get("employee_id"), {})
        sop["employee_name"] = emp.get("Full_name", "Unknown")
        pos_id = emp.get("position_id")
        sop["position_title"] = pos_map.get(str(pos_id), {}).get("title", "No Position") if pos_id else "No Position"
        sop["assigned_by_name"] = emp_map.get(sop.get("assigned_by"), {}).get("Full_name", "System")
        
    return templates.TemplateResponse("sops/index.html", ctx(request, "sops",
        sops=sops, employees=employees, departments=departments, positions=positions))

@app.post("/sops/assign", response_class=RedirectResponse)
async def admin_assign_sop(request: Request,
    position_id: str = Form(...),
    department_id: str = Form(None),
    task_description: str = Form(...),
    assigned_date: str = Form(...)):
    user = get_current_user(request)
    if not user or user.get("role") not in ["boss", "hr_manager", "admin"]:
        return redirect_with_msg("/dashboard", error="Unauthorized")
        
    filters = {"status": "Active"}
    if position_id and position_id != "all":
        filters["position_id"] = position_id
    if department_id and department_id != "all":
        filters["Dept_id"] = department_id
        
    employees = db_fetch("Employees", "id", filters=filters)
    if not employees:
        import urllib.parse
        error_msg = urllib.parse.quote(f"No active employees. Filters used: {filters}")
        return redirect_with_msg("/sops", error=error_msg)
        
    count = 0
    for emp in employees:
        db_insert("daily_sops", {
            "employee_id": str(emp["id"]),
            "task_description": task_description,
            "assigned_by": user.get("employee_id"),
            "assigned_date": assigned_date,
            "is_completed": False
        })
        notify_employee(str(emp["id"]), "New Daily SOP Assigned", "You have a new Daily SOP assigned. Please complete it and upload your video proof.", "/portal/sops")
        count += 1
        
    return redirect_with_msg("/sops", success=f"SOP+assigned+successfully+to+{count}+employees")

@app.get("/sops/{sop_id}/delete", response_class=RedirectResponse)
async def admin_delete_sop(request: Request, sop_id: str):
    user = get_current_user(request)
    if not user or user.get("role") not in ["boss", "hr_manager", "admin"]:
        return redirect_with_msg("/dashboard", error="Unauthorized")
        
    db_delete("daily_sops", sop_id)
    return redirect_with_msg("/sops", success="SOP+deleted+successfully")

@app.get("/portal/sops", response_class=HTMLResponse)
async def portal_sops_list(request: Request):
    user = get_current_user(request)
    if not user:
        return redirect_with_msg("/login", error="Please+login")
        
    sops = db_fetch("daily_sops", "*", filters={"employee_id": user.get("employee_id")}, order="assigned_date")
    return templates.TemplateResponse("portal/sops.html", ctx(request, "portal_sops", sops=sops))

def update_sops_kpi(employee_id: str):
    current_period = datetime.now().strftime("%Y-%m")
    all_sops = db_fetch("daily_sops", "*", filters={"employee_id": employee_id})
    month_sops = [s for s in all_sops if s.get("assigned_date", "").startswith(current_period)]
    if not month_sops:
        return
        
    total_assigned = len(month_sops)
    total_completed = len([s for s in month_sops if s.get("is_completed")])
    
    existing_kpis = db_fetch("kpis", "*", filters={"employee_id": employee_id, "recent_period": current_period})
    
    if existing_kpis:
        db_update("kpis", existing_kpis[0]["id"], {
            "target_score": float(total_assigned),
            "actual_score": float(total_completed),
            "review_comment": f"Auto-calculated: {total_completed}/{total_assigned} SOPs completed."
        })
    else:
        db_insert("kpis", {
            "employee_id": employee_id,
            "recent_period": current_period,
            "target_score": float(total_assigned),
            "actual_score": float(total_completed),
            "review_comment": f"Auto-calculated: {total_completed}/{total_assigned} SOPs completed."
        })

@app.post("/portal/sops/{sop_id}/complete", response_class=RedirectResponse)
async def portal_complete_sop(request: Request, sop_id: str, video_file: UploadFile = File(...)):
    user = get_current_user(request)
    if not user:
        return redirect_with_msg("/login", error="Please+login")
        
    # Check if SOP belongs to user
    sop = db_fetch_one("daily_sops", "*", filters={"id": sop_id, "employee_id": user.get("employee_id")})
    if not sop:
        return redirect_with_msg("/portal/sops", error="SOP+not+found")
        
    if video_file.filename:
        content = await video_file.read()
        if not content:
            return redirect_with_msg("/portal/sops", error="Uploaded+video+is+empty")
            
        # Calculate SHA-256 hash of the video to prevent duplicate uploads
        video_hash = hashlib.sha256(content).hexdigest()
        
        # Check if this exact video was already uploaded
        existing_sop = db_fetch_one("daily_sops", "id", filters={"video_hash": video_hash})
        if existing_sop:
            return redirect_with_msg("/portal/sops", error="Duplicate+video+detected.+Please+record+a+new+video.")
            
        # Save file to static/uploads/videos
        ext = os.path.splitext(video_file.filename)[1] or ".mp4"
        unique_name = f"{uuid.uuid4()}{ext}"
        save_path = os.path.join("static", "uploads", "videos", unique_name)
        
        # Ensure dir exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, "wb") as buffer:
            buffer.write(content)
            
        file_url = f"/static/uploads/videos/{unique_name}"
        
        db_update("daily_sops", sop_id, {
            "is_completed": True,
            "completed_at": datetime.now().isoformat(),
            "proof_video_url": file_url,
            "video_hash": video_hash
        })
        
        # Automatically recalculate KPI for this month
        update_sops_kpi(user.get("employee_id"))
        
        return redirect_with_msg("/portal/sops", success="SOP+completed+and+video+uploaded!")
        
    return redirect_with_msg("/portal/sops", error="Please+provide+a+video+file")

@app.post("/portal/sops/{sop_id}/absent", response_class=RedirectResponse)
async def portal_absent_sop(request: Request, sop_id: str):
    user = get_current_user(request)
    if not user:
        return redirect_with_msg("/login", error="Please+login")
        
    # Check if SOP belongs to user
    sop = db_fetch_one("daily_sops", "*", filters={"id": sop_id, "employee_id": user.get("employee_id")})
    if not sop:
        return redirect_with_msg("/portal/sops", error="SOP+not+found")
        
    db_update("daily_sops", sop_id, {
        "is_absent": True,
        "is_completed": False
    })
    
    # Automatically recalculate KPI for this month
    update_sops_kpi(user.get("employee_id"))
    
    return redirect_with_msg("/portal/sops", success="SOP+marked+as+missed+due+to+absence")

# ── Boss Chatbot RAG ────────────────────────────────────────────────────────
@app.get("/boss/chat", response_class=HTMLResponse)
async def boss_chat_page(request: Request):
    user = get_current_user(request)
    if not user or user.get("role") != "boss":
        return redirect_with_msg("/dashboard", error="Unauthorized")
    return templates.TemplateResponse("boss/chat.html", ctx(request, "boss_chat"))

@app.post("/api/boss/chat", response_class=JSONResponse)
async def api_boss_chat(request: Request):
    user = get_current_user(request)
    if not user or user.get("role") != "boss":
        return JSONResponse({"error": "Unauthorized"}, status_code=403)
    
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
        
    message = data.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "Empty message"}, status_code=400)
    
    try:
        # Fetch Context Data for RAG
        # 1. Employees & Core Lookup
        employees = db_fetch("Employees", "id,employee_id,Full_name,status,Dept_id,position_id")
        depts = {d["id"]: d.get("Department_name", "") for d in db_fetch("Departments", "id,Department_name")}
        pos = {p["id"]: p.get("title", "") for p in db_fetch("positions", "id,title")}
        
        # 2. Existing modules
        kpis = db_fetch("kpis", "employee_id,recent_period,target_score,actual_score,review_comment")
        votes = db_fetch("peer_voting_records", "nominee_id,score")
        attendance = db_fetch("attendance_records", "employee_id,check_in,is_late")
        
        # 3. Leave Management
        leave_reqs = db_fetch("Leave_Request", "employee_id,start_date,end_date,status,reason")
        leave_bals = db_fetch("Leave_balances", "employee_id,remain_days,leave_type_id")
        leave_types = {t["id"]: t.get("type_name", "") for t in db_fetch("Leave_type", "id,type_name")}
        
        # 4. Payrolls
        payrolls = db_fetch("payrolls", "employee_id,month,net_salary,payment_status")
        
        # 5. SOPs
        sops = db_fetch("daily_sops", "employee_id,assigned_date,is_completed,is_absent")
        
        # Build Employee Stats
        vote_stats = {}
        for v in votes:
            nid = v.get("nominee_id")
            if nid: vote_stats.setdefault(nid, []).append(int(v.get("score") or 0))
            
        att_stats = {}
        for a in attendance:
            eid = a.get("employee_id")
            if eid: att_stats.setdefault(eid, []).append(a)
            
        context_lines = ["--- HR DATABASE CONTEXT ---"]
        context_lines.append("\n== EMPLOYEES ==")
        
        for emp in employees:
            eid = emp.get("id")
            if not eid: continue
            
            dname = depts.get(emp.get("Dept_id"), "None")
            pname = pos.get(emp.get("position_id"), "None")
            status = emp.get("status", "Unknown")
            
            # KPIs
            emp_kpis = [k for k in kpis if k.get("employee_id") == str(eid)]
            kpi_str = f"KPI: {emp_kpis[-1].get('actual_score')}/{emp_kpis[-1].get('target_score')}" if emp_kpis else "No KPI"
            
            # Votes
            emp_votes = vote_stats.get(str(eid), [])
            vote_str = f"Votes Avg: {sum(emp_votes)/len(emp_votes):.1f} ({len(emp_votes)} votes)" if emp_votes else "No votes"
            
            # Attendance
            emp_att = att_stats.get(str(eid), [])
            months = {}
            for a in emp_att:
                ci = a.get("check_in")
                if ci and len(ci) >= 7:
                    month = ci[:7]
                    months[month] = months.get(month, 0) + 1
            att_summary = ", ".join([f"{m}: {c} days" for m, c in months.items()])
            late_count = sum(1 for a in emp_att if a.get("is_late"))
            att_str = f"Att: {att_summary} (Late: {late_count})" if emp_att else "No att"
            
            # Leave
            emp_reqs = [l for l in leave_reqs if l.get("employee_id") == str(eid)]
            req_str = ", ".join([f"{r.get('start_date')} to {r.get('end_date')} ({r.get('status')})" for r in emp_reqs[-2:]]) if emp_reqs else "No leaves"
            emp_bals = [b for b in leave_bals if b.get("employee_id") == str(eid)]
            bal_str = ", ".join([f"{leave_types.get(b.get('leave_type_id'), '?')}: {b.get('remain_days')} left" for b in emp_bals]) if emp_bals else "No balances"
            
            # Payroll
            emp_pays = [p for p in payrolls if p.get("employee_id") == str(eid)]
            pay_str = ", ".join([f"{p.get('month')}: ${p.get('net_salary')} ({p.get('payment_status')})" for p in emp_pays[-2:]]) if emp_pays else "No payroll"
            
            # SOPs
            emp_sops = [s for s in sops if s.get("employee_id") == str(eid)]
            completed = sum(1 for s in emp_sops if s.get("is_completed"))
            sop_str = f"SOPs: {completed}/{len(emp_sops)} done" if emp_sops else "No SOPs"
            
            line = f"- {emp.get('Full_name')} ({emp.get('employee_id')}) | Dept:{dname} | Pos:{pname} | Status:{status} || {kpi_str} | {vote_str} || {att_str} || Leaves:{req_str} [{bal_str}] || Pay:{pay_str} || {sop_str}"
            context_lines.append(line)

        # 6. Recruitment
        candidates = db_fetch("recruitment_candidates", "full_name,position_id,status,created_at")
        context_lines.append("\n== RECRUITMENT CANDIDATES ==")
        for c in candidates:
            pname = pos.get(c.get("position_id"), "None")
            context_lines.append(f"- {c.get('full_name')} applied for {pname} | Status: {c.get('status')}")
            
        # 7. Onboarding & Offboarding
        onboard = db_fetch("employee_onboarding", "employee_id,status,completion_pct")
        offboard = db_fetch("corporate_offboarding", "employee_id,resignation_date,last_working_date,settlement_status")
        
        context_lines.append("\n== ONBOARDING / OFFBOARDING ==")
        emp_names = {str(e.get("id")): e.get("Full_name") for e in employees}
        for o in onboard:
            name = emp_names.get(o.get("employee_id"), "Unknown")
            context_lines.append(f"- {name} Onboarding | Status: {o.get('status')} | Progress: {o.get('completion_pct')}%")
        for o in offboard:
            name = emp_names.get(o.get("employee_id"), "Unknown")
            context_lines.append(f"- {name} Offboarding | Resigned: {o.get('resignation_date')} | Settlement: {o.get('settlement_status')}")

        context_text = "\n".join(context_lines)
        
        # Construct Prompt
        system_prompt = (
            "You are an AI HR Assistant for the Boss. You must answer questions based strictly on the provided HR Database Context. "
            "You support answering in both Burmese and English, matching the language of the user's prompt. "
            "If the user asks in Burmese, reply in natural, professional Burmese. If in English, reply in English. "
            "Do not invent data; if the information is not in the context, say so gracefully. "
            "Use Markdown for formatting if helpful (e.g., bold names, bullet points)."
        )
        
        full_prompt = f"{system_prompt}\n\n{context_text}\n\nBoss asks: {message}"
        
        # Call Gemini
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(full_prompt)
        reply = response.text
        
        return JSONResponse({"reply": reply})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

# ── Finance Manager Panel ───────────────────────────────────────────────────
@app.get("/finance/dashboard", response_class=HTMLResponse)
async def finance_dashboard(request: Request):
    user = get_current_user(request)
    if not user or user.get("role") not in ["boss", "finance"]:
        return redirect_with_msg("/dashboard", error="Unauthorized")
        
    # Get payroll summary
    payrolls = db_fetch("payrolls", "*")
    total_disbursed = sum(float(p.get("net_salary") or 0) for p in payrolls if p.get("payment_status") == "Paid")
    pending_count = sum(1 for p in payrolls if p.get("payment_status") == "Pending")
    
    # Get offboarding settlements
    offboarding = db_fetch("corporate_offboarding", "*", filters={"settlement_status": "Hold Final Payroll"})
    pending_settlements = len(offboarding)
    
    stats = {
        "total_disbursed": total_disbursed,
        "pending_payrolls": pending_count,
        "pending_settlements": pending_settlements
    }
    
    return templates.TemplateResponse("finance/dashboard.html", ctx(request, "finance_dashboard", stats=stats))
if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
