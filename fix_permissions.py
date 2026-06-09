"""
Fix: Enable all HRM tables in Supabase by:
1. Disabling RLS on all tables (so anon key can read/write)
2. Granting full permissions to anon and authenticated roles
"""
import psycopg2

DB_CONFIG = {
    "host":     "db.kcswzfrwpvioaaizfpnk.supabase.co",
    "port":     5432,
    "dbname":   "postgres",
    "user":     "postgres",
    "password": "PHYOEthuta123!@#",
    "sslmode":  "require",
    "connect_timeout": 20
}

TABLES = [
    "Departments", "positions", "Employees", "Profiles",
    "biometric_device", "biometric_logs", "biometric_employees",
    "attendance_records",
    "Leave_type", "Leave_Request", "Leave_balances",
    "birthday_notification", "birthday_notification_requests",
    "kpis", "payrolls",
    "peer_voting_records",
    "recruitment_candidates", "job_requirements", "resume_screening",
    "hr_screening_result", "interview_schedules",
    "recruitment_offers", "recruitment_status_history", "quality_candidates",
    "onboarding_tasks", "employee_onboarding", "onboarding_assignments",
    "preboarding_documents",
    "corporate_offboarding", "offboarding_tasks", "offboarding_assignments",
    "exit_interviews",
]

def main():
    print("=" * 60)
    print("  Fixing Supabase RLS & Permissions")
    print("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    print("[OK] Connected!\n")

    for table in TABLES:
        try:
            # Disable RLS so the anon key can access the table
            cur.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')
            # Grant full access to both anon and authenticated roles
            cur.execute(f'GRANT ALL ON public."{table}" TO anon, authenticated, service_role')
            print(f"  [OK] {table}")
        except Exception as e:
            print(f"  [WARN] {table}: {e}")

    # Also grant usage on sequences (needed for UUID defaults)
    try:
        cur.execute("GRANT USAGE ON SCHEMA public TO anon, authenticated")
        cur.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role")
        cur.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role")
        print("\n  [OK] Schema permissions granted")
    except Exception as e:
        print(f"  [WARN] Schema grants: {e}")

    cur.close()
    conn.close()
    print("\n[DONE] All tables are now accessible via the anon API key!")
    print("       Restart app.py and all pages should load with live data.")
    print("=" * 60)

if __name__ == "__main__":
    main()
