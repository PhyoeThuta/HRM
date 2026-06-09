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
CREATE TABLE IF NOT EXISTS public.daily_sops (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id      UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  task_description TEXT NOT NULL,
  assigned_by      UUID REFERENCES public."Employees"(id) ON DELETE SET NULL,
  assigned_date    DATE DEFAULT CURRENT_DATE,
  is_completed     BOOLEAN DEFAULT FALSE,
  completed_at     TIMESTAMPTZ,
  proof_video_url  TEXT,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);
"""

def main():
    print("[*] Connecting to database...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        print("[OK] Connected successfully.")
        
        print("[*] Creating daily_sops table...")
        cur.execute(DDL)
        print("[OK] Table daily_sops created or already exists.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[FAIL] {e}")

if __name__ == "__main__":
    main()
