"""
Setup Auth Tables — sys_users, boss_kpi_assignments, announcements
Run once to create tables and default user accounts.
"""
import psycopg2, hashlib, uuid
from datetime import datetime

DB_URL = "postgresql://postgres:PHYOEthuta123!%40%23@db.kcswzfrwpvioaaizfpnk.supabase.co:5432/postgres"

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def run():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    print("Creating sys_users table...")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sys_users (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        username      TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email         TEXT,
        role          TEXT NOT NULL DEFAULT 'employee',
        full_name     TEXT,
        employee_id   UUID REFERENCES "Employees"(id) ON DELETE SET NULL,
        is_active     BOOLEAN DEFAULT TRUE,
        created_at    TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    print("Creating boss_kpi_assignments table...")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS boss_kpi_assignments (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        title           TEXT NOT NULL,
        description     TEXT,
        assigned_to_id  UUID,
        assigned_to_name TEXT,
        target_value    TEXT,
        deadline        DATE,
        status          TEXT DEFAULT 'Pending',
        created_by      TEXT,
        created_at      TIMESTAMPTZ DEFAULT NOW(),
        updated_at      TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    print("Creating announcements table...")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS announcements (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        title       TEXT NOT NULL,
        content     TEXT,
        priority    TEXT DEFAULT 'Medium',
        target_role TEXT DEFAULT 'All',
        is_pinned   BOOLEAN DEFAULT FALSE,
        created_by  TEXT,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # Disable RLS on new tables
    for tbl in ["sys_users", "boss_kpi_assignments", "announcements"]:
        cur.execute(f'ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;')
        cur.execute(f'GRANT ALL ON TABLE {tbl} TO anon, authenticated, service_role;')

    print("Inserting default users...")
    defaults = [
        ("boss",       hash_pw("boss1234"),  "boss",            "Boss / CEO"),
        ("hr_manager", hash_pw("hr1234"),    "hr_manager",      "HR Manager"),
        ("finance_manager", hash_pw("finance1234"), "finance",  "Finance Manager"),
        ("gm",         hash_pw("gm1234"),    "general_manager", "General Manager"),
        ("employee",   hash_pw("emp1234"),   "employee",        "Sample Employee"),
    ]
    for username, pw_hash, role, full_name in defaults:
        cur.execute("""
        INSERT INTO sys_users (username, password_hash, role, full_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (username) DO NOTHING;
        """, (username, pw_hash, role, full_name))
        print(f"  OK {username} ({role})")

    conn.commit()
    cur.close()
    conn.close()
    print("\n✅ Auth tables created and default users inserted.")
    print("\nLogin Credentials:")
    print("  Boss:           boss / boss1234")
    print("  HR Manager:     hr_manager / hr1234")
    print("  Finance Manager:finance_manager / finance1234")
    print("  General Manager:gm / gm1234")
    print("  Employee:       employee / emp1234")

if __name__ == "__main__":
    run()
