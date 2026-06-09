import psycopg2
from psycopg2 import sql

DB_CONFIG = {
    "host":     "db.kcswzfrwpvioaaizfpnk.supabase.co",
    "port":     5432,
    "dbname":   "postgres",
    "user":     "postgres",
    "password": "PHYOEthuta123!@#",
    "sslmode":  "require",
    "connect_timeout": 20
}

DDL = """
CREATE TABLE IF NOT EXISTS public.payroll_payslips (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id      UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
    month            VARCHAR(7) NOT NULL, -- e.g. '2026-05'
    base_salary      NUMERIC NOT NULL,
    attendance_score NUMERIC NOT NULL,
    sop_score        NUMERIC NOT NULL,
    final_kpi_score  NUMERIC NOT NULL,
    deductions       NUMERIC DEFAULT 0,
    bonuses          NUMERIC DEFAULT 0,
    net_pay          NUMERIC NOT NULL,
    status           VARCHAR(50) DEFAULT 'Pending', -- 'Pending', 'Approved', 'Paid'
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(employee_id, month)
);
"""

def main():
    print("[*] Connecting to database...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        print("[OK] Connected successfully.")
        
        print("[*] Creating payroll_payslips table...")
        cur.execute(DDL)
        print("[OK] Table payroll_payslips created or already exists.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[FAIL] {e}")

if __name__ == "__main__":
    main()
