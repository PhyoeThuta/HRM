"""
Supabase Table Setup via Direct PostgreSQL Connection
Uses psycopg2 to connect and create all tables + seed data
"""
import psycopg2
from psycopg2 import sql
import time

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

("Departments", """
CREATE TABLE IF NOT EXISTS public."Departments" (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  "Department_name" TEXT NOT NULL,
  "Descriptions"    TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_by        UUID,
  created_by        UUID
)
"""),

("positions", """
CREATE TABLE IF NOT EXISTS public.positions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title       TEXT NOT NULL,
  level       TEXT,
  team        TEXT,
  base_salary NUMERIC(12,2) DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  created_by  UUID,
  updated_by  UUID
)
"""),

("Employees", """
CREATE TABLE IF NOT EXISTS public."Employees" (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id    TEXT UNIQUE NOT NULL,
  "Full_name"    TEXT NOT NULL,
  "Dept_id"      UUID REFERENCES public."Departments"(id) ON DELETE SET NULL,
  position_id    UUID REFERENCES public.positions(id) ON DELETE SET NULL,
  "Manager_id"   UUID,
  "Dept_head_id" UUID,
  hire_date      DATE,
  date_of_birth  DATE,
  status         TEXT DEFAULT 'Active',
  email          TEXT,
  phone          TEXT,
  salary         NUMERIC(12,2) DEFAULT 0,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  created_by     UUID,
  updated_by     UUID
)
"""),

("Profiles", """
CREATE TABLE IF NOT EXISTS public."Profiles" (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID,
  full_name  TEXT,
  phone      TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""),

("biometric_device", """
CREATE TABLE IF NOT EXISTS public.biometric_device (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_name  TEXT NOT NULL,
  ip_address   TEXT,
  port         INT DEFAULT 4370,
  location     TEXT,
  status       TEXT DEFAULT 'Active',
  last_sync_at TIMESTAMPTZ,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  created_by   UUID
)
"""),

("biometric_logs", """
CREATE TABLE IF NOT EXISTS public.biometric_logs (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id           UUID REFERENCES public.biometric_device(id) ON DELETE SET NULL,
  employee_id         UUID REFERENCES public."Employees"(id) ON DELETE SET NULL,
  raw_time            TIMESTAMPTZ,
  type                TEXT CHECK (type IN ('in','out')),
  verification_status TEXT DEFAULT 'pending',
  new_data            BOOLEAN DEFAULT FALSE,
  created_at          TIMESTAMPTZ DEFAULT NOW()
)
"""),

("biometric_employees", """
CREATE TABLE IF NOT EXISTS public.biometric_employees (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id   UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  device_id     UUID REFERENCES public.biometric_device(id) ON DELETE CASCADE,
  biometric_id  TEXT,
  registered    BOOLEAN DEFAULT FALSE,
  registered_by UUID,
  updated_at    TIMESTAMPTZ DEFAULT NOW()
)
"""),

("attendance_records", """
CREATE TABLE IF NOT EXISTS public.attendance_records (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id            UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  check_in               TIMESTAMPTZ,
  check_out              TIMESTAMPTZ,
  check_in_photo_url     TEXT,
  attendance_method      TEXT DEFAULT 'Manual',
  recorded_by            UUID,
  work_hours             NUMERIC(5,2),
  work_from              TIME,
  work_to                TIME,
  is_late                BOOLEAN DEFAULT FALSE,
  late_minutes           INT DEFAULT 0,
  fingerprint_registered BOOLEAN DEFAULT FALSE,
  finger_print_id        TEXT,
  created_at             TIMESTAMPTZ DEFAULT NOW(),
  updated_by             UUID
)
"""),

("Leave_type", """
CREATE TABLE IF NOT EXISTS public."Leave_type" (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type_name    TEXT NOT NULL,
  description  TEXT,
  default_days INT DEFAULT 14,
  is_paid      BOOLEAN DEFAULT TRUE,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  created_by   UUID
)
"""),

("Leave_Request", """
CREATE TABLE IF NOT EXISTS public."Leave_Request" (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id    UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  leave_type_id  UUID REFERENCES public."Leave_type"(id) ON DELETE SET NULL,
  start_date     DATE NOT NULL,
  end_date       DATE NOT NULL,
  total_days     INT,
  reason         TEXT,
  status         TEXT DEFAULT 'Pending',
  approved_by    UUID,
  approved_at    TIMESTAMPTZ,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  cancelled_at   TIMESTAMPTZ,
  cancelled_by   UUID,
  cancel_reason  TEXT,
  attachment_url TEXT
)
"""),

("Leave_balances", """
CREATE TABLE IF NOT EXISTS public."Leave_balances" (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id       UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  leave_type_id     UUID REFERENCES public."Leave_type"(id) ON DELETE SET NULL,
  year              INT DEFAULT DATE_PART('year', NOW())::INT,
  entitled_days     INT DEFAULT 14,
  used_days         INT DEFAULT 0,
  remain_days       INT DEFAULT 14,
  carried_over_from INT,
  carried_over_days INT DEFAULT 0,
  max_carry_over    INT DEFAULT 5,
  updated_at        TIMESTAMPTZ DEFAULT NOW()
)
"""),

("birthday_notification", """
CREATE TABLE IF NOT EXISTS public.birthday_notification (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  message     TEXT,
  channel     TEXT DEFAULT 'in-app',
  is_sent     BOOLEAN DEFAULT FALSE,
  sent_at     TIMESTAMPTZ,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_by  UUID,
  created_by  UUID
)
"""),

("birthday_notification_requests", """
CREATE TABLE IF NOT EXISTS public.birthday_notification_requests (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  notification_id UUID REFERENCES public.birthday_notification(id) ON DELETE CASCADE,
  receipt_user_id UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  is_read         BOOLEAN DEFAULT FALSE,
  read_at         TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_by      UUID,
  created_by      UUID
)
"""),

("kpis", """
CREATE TABLE IF NOT EXISTS public.kpis (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id    UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  recent_period  TEXT,
  target_score   NUMERIC(5,2),
  actual_score   NUMERIC(5,2),
  review_comment TEXT,
  reviewed_by    UUID,
  reviewed_at    TIMESTAMPTZ,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_by     UUID,
  created_by     UUID
)
"""),

("payrolls", """
CREATE TABLE IF NOT EXISTS public.payrolls (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id    UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  kpi_id         UUID REFERENCES public.kpis(id) ON DELETE SET NULL,
  month          TEXT NOT NULL,
  basic_salary   NUMERIC(12,2) DEFAULT 0,
  allowances     NUMERIC(12,2) DEFAULT 0,
  deductions     NUMERIC(12,2) DEFAULT 0,
  bonus          NUMERIC(12,2) DEFAULT 0,
  net_salary     NUMERIC(12,2) DEFAULT 0,
  payment_status TEXT DEFAULT 'Pending',
  paid_date      DATE,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_by     UUID,
  created_by     UUID
)
"""),

("peer_voting_records", """
CREATE TABLE IF NOT EXISTS public.peer_voting_records (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  voter_id     UUID REFERENCES public."Employees"(id) ON DELETE SET NULL,
  nominee_id   UUID REFERENCES public."Employees"(id) ON DELETE SET NULL,
  nominee_name TEXT,
  category     TEXT,
  score        INT CHECK (score BETWEEN 1 AND 5),
  comment      TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW()
)
"""),

("recruitment_candidates", """
CREATE TABLE IF NOT EXISTS public.recruitment_candidates (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name   TEXT NOT NULL,
  email       TEXT,
  phone       TEXT,
  position_id UUID REFERENCES public.positions(id) ON DELETE SET NULL,
  cv_ref      TEXT,
  source      TEXT,
  status      TEXT DEFAULT 'Applied',
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  created_by  UUID,
  updated_by  UUID,
  deleted_by  UUID,
  deleted_at  TIMESTAMPTZ
)
"""),

("job_requirements", """
CREATE TABLE IF NOT EXISTS public.job_requirements (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  position_id  UUID REFERENCES public.positions(id) ON DELETE CASCADE,
  skill_name   TEXT NOT NULL,
  skill_weight NUMERIC(3,2) DEFAULT 1.0,
  is_mandatory BOOLEAN DEFAULT FALSE,
  description  TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  created_by   UUID
)
"""),

("resume_screening", """
CREATE TABLE IF NOT EXISTS public.resume_screening (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id UUID REFERENCES public.recruitment_candidates(id) ON DELETE CASCADE,
  screened_by  UUID,
  result       TEXT,
  feedback     TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW()
)
"""),

("hr_screening_result", """
CREATE TABLE IF NOT EXISTS public.hr_screening_result (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id     UUID REFERENCES public.recruitment_candidates(id) ON DELETE CASCADE,
  screening_date   DATE,
  ai_score         NUMERIC(5,2),
  ai_status        TEXT,
  result_keyword   TEXT,
  experience_years INT,
  ai_summary       TEXT,
  recommendation   TEXT,
  is_unified       BOOLEAN DEFAULT FALSE,
  ai_called        BOOLEAN DEFAULT FALSE,
  created_at       TIMESTAMPTZ DEFAULT NOW()
)
"""),

("interview_schedules", """
CREATE TABLE IF NOT EXISTS public.interview_schedules (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id   UUID REFERENCES public.recruitment_candidates(id) ON DELETE CASCADE,
  interviewer_id UUID REFERENCES public."Employees"(id) ON DELETE SET NULL,
  scheduled_date TIMESTAMPTZ,
  result         TEXT,
  feedback       TEXT,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  created_by     UUID
)
"""),

("recruitment_offers", """
CREATE TABLE IF NOT EXISTS public.recruitment_offers (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id        UUID REFERENCES public.recruitment_candidates(id) ON DELETE CASCADE,
  offered_position_id UUID REFERENCES public.positions(id) ON DELETE SET NULL,
  offer_date          DATE,
  offer_type          TEXT,
  start_date          DATE,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW(),
  created_by          UUID
)
"""),

("recruitment_status_history", """
CREATE TABLE IF NOT EXISTS public.recruitment_status_history (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id UUID REFERENCES public.recruitment_candidates(id) ON DELETE CASCADE,
  status       TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  created_by   UUID
)
"""),

("quality_candidates", """
CREATE TABLE IF NOT EXISTS public.quality_candidates (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id UUID REFERENCES public.recruitment_candidates(id) ON DELETE CASCADE,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  created_by   UUID
)
"""),

("onboarding_tasks", """
CREATE TABLE IF NOT EXISTS public.onboarding_tasks (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_name           TEXT NOT NULL,
  description         TEXT,
  category            TEXT DEFAULT 'General',
  is_preboarding      BOOLEAN DEFAULT FALSE,
  due_days_after_hire INT DEFAULT 1,
  assigned_to_role    TEXT DEFAULT 'HR',
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  created_by          UUID
)
"""),

("employee_onboarding", """
CREATE TABLE IF NOT EXISTS public.employee_onboarding (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id       UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  start_date        DATE,
  expected_end_date DATE,
  status            TEXT DEFAULT 'Pre-boarding',
  buddy_id          UUID REFERENCES public."Employees"(id) ON DELETE SET NULL,
  hr_owner_id       UUID REFERENCES public."Employees"(id) ON DELETE SET NULL,
  notes             TEXT,
  completion_pct    INT DEFAULT 0,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW(),
  created_by        UUID
)
"""),

("onboarding_assignments", """
CREATE TABLE IF NOT EXISTS public.onboarding_assignments (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  onboarding_id UUID REFERENCES public.employee_onboarding(id) ON DELETE CASCADE,
  task_id       UUID REFERENCES public.onboarding_tasks(id) ON DELETE CASCADE,
  status        TEXT DEFAULT 'Pending',
  due_date      DATE,
  completed_at  TIMESTAMPTZ,
  completed_by  UUID,
  notes         TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
)
"""),

("preboarding_documents", """
CREATE TABLE IF NOT EXISTS public.preboarding_documents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id   UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  document_name TEXT NOT NULL,
  document_type TEXT DEFAULT 'Other',
  file_url      TEXT,
  is_signed     BOOLEAN DEFAULT FALSE,
  signed_at     TIMESTAMPTZ,
  due_date      DATE,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  created_by    UUID
)
"""),

("corporate_offboarding", """
CREATE TABLE IF NOT EXISTS public.corporate_offboarding (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id          UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  resignation_date     DATE,
  last_working_date    DATE,
  termination_reason   TEXT DEFAULT 'Resignation',
  exit_type            TEXT DEFAULT 'Voluntary',
  settlement_status    TEXT DEFAULT 'Hold Final Payroll',
  laptop_returned      BOOLEAN DEFAULT FALSE,
  access_card_returned BOOLEAN DEFAULT FALSE,
  nda_signed           BOOLEAN DEFAULT FALSE,
  knowledge_transfer   BOOLEAN DEFAULT FALSE,
  final_payroll_amount NUMERIC(12,2),
  hr_notes             TEXT,
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  updated_at           TIMESTAMPTZ DEFAULT NOW(),
  created_by           UUID,
  updated_by           UUID
)
"""),

("offboarding_tasks", """
CREATE TABLE IF NOT EXISTS public.offboarding_tasks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_name   TEXT NOT NULL,
  description TEXT,
  category    TEXT DEFAULT 'General',
  responsible TEXT DEFAULT 'HR',
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  created_by  UUID
)
"""),

("offboarding_assignments", """
CREATE TABLE IF NOT EXISTS public.offboarding_assignments (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  offboarding_id UUID REFERENCES public.corporate_offboarding(id) ON DELETE CASCADE,
  task_id        UUID REFERENCES public.offboarding_tasks(id) ON DELETE CASCADE,
  status         TEXT DEFAULT 'Pending',
  completed_at   TIMESTAMPTZ,
  completed_by   UUID,
  notes          TEXT,
  created_at     TIMESTAMPTZ DEFAULT NOW()
)
"""),

("exit_interviews", """
CREATE TABLE IF NOT EXISTS public.exit_interviews (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  offboarding_id      UUID REFERENCES public.corporate_offboarding(id) ON DELETE CASCADE,
  employee_id         UUID REFERENCES public."Employees"(id) ON DELETE SET NULL,
  interviewer_id      UUID REFERENCES public."Employees"(id) ON DELETE SET NULL,
  interview_date      DATE,
  reason_for_leaving  TEXT,
  job_satisfaction    INT CHECK (job_satisfaction BETWEEN 1 AND 5),
  management_rating   INT CHECK (management_rating BETWEEN 1 AND 5),
  work_env_rating     INT CHECK (work_env_rating BETWEEN 1 AND 5),
  compensation_rating INT CHECK (compensation_rating BETWEEN 1 AND 5),
  growth_rating       INT CHECK (growth_rating BETWEEN 1 AND 5),
  would_return        BOOLEAN,
  would_recommend     BOOLEAN,
  highlights          TEXT,
  improvements        TEXT,
  additional_comments TEXT,
  status              TEXT DEFAULT 'Scheduled',
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  created_by          UUID
)
"""),

]

SEEDS = [

("Seed: onboarding_tasks", """
INSERT INTO public.onboarding_tasks (task_name, category, is_preboarding, due_days_after_hire, assigned_to_role)
VALUES
  ('Send Welcome Email',              'Pre-boarding',  TRUE,  -5, 'HR'),
  ('Share Employee Handbook',         'Pre-boarding',  TRUE,  -3, 'HR'),
  ('Collect Contract Signature',      'Documentation', TRUE,  -1, 'HR'),
  ('Setup Company Email Account',     'IT Setup',      FALSE,  1, 'IT'),
  ('Create System & App Accounts',    'IT Setup',      FALSE,  1, 'IT'),
  ('Issue Access Card & Keys',        'Introduction',  FALSE,  1, 'Facilities'),
  ('Office Tour & Desk Setup',        'Introduction',  FALSE,  1, 'HR'),
  ('Team Introduction Meeting',       'Introduction',  FALSE,  1, 'Manager'),
  ('Company Policy Training',         'Compliance',    FALSE,  3, 'HR'),
  ('IT Security & Data Training',     'Compliance',    FALSE,  3, 'IT'),
  ('Probation Goals & KPI Setting',   'Training',      FALSE,  7, 'Manager'),
  ('30-Day Check-in with HR',         'Training',      FALSE, 30, 'HR')
ON CONFLICT DO NOTHING
"""),

("Seed: offboarding_tasks", """
INSERT INTO public.offboarding_tasks (task_name, category, responsible)
VALUES
  ('Return Laptop & Equipment',       'IT',                 'IT'),
  ('Return Access Card & Keys',       'Facilities',         'Facilities'),
  ('Revoke All System Access',        'IT',                 'IT'),
  ('Sign NDA Exit Confirmation',      'Legal',              'HR'),
  ('Complete Knowledge Transfer Doc', 'Knowledge Transfer', 'Manager'),
  ('Handover Projects & Tasks',       'Knowledge Transfer', 'Manager'),
  ('Clear Outstanding Expenses',      'Finance',            'Finance'),
  ('Final Payroll Calculation',       'Finance',            'Finance'),
  ('Return Company Documents',        'HR',                 'HR'),
  ('Schedule Exit Interview',         'HR',                 'HR')
ON CONFLICT DO NOTHING
"""),

("Seed: Leave_type", """
INSERT INTO public."Leave_type" (type_name, description, default_days, is_paid)
VALUES
  ('Annual Leave',       'Yearly paid vacation leave',              20, TRUE),
  ('Sick Leave',         'Medical and health related absence',      10, TRUE),
  ('Maternity Leave',    'Leave for new mothers',                   90, TRUE),
  ('Paternity Leave',    'Leave for new fathers',                    5, TRUE),
  ('Emergency Leave',    'For urgent family emergencies',            3, TRUE),
  ('Unpaid Leave',       'Approved leave without pay',              30, FALSE),
  ('Study Leave',        'For approved academic programs',          10, TRUE),
  ('Compassionate Leave','Bereavement or family emergency leave',    3, TRUE)
ON CONFLICT DO NOTHING
"""),

("Seed: Departments", """
INSERT INTO public."Departments" ("Department_name", "Descriptions")
VALUES
  ('Kitchen & Culinary',    'Food preparation and cooking'),
  ('Nutrition & Dietetics', 'Meal planning and diet management'),
  ('Logistics & Delivery',  'Getting the food to the customers'),
  ('Customer Service',      'Handling orders and client feedback'),
  ('Marketing & Sales',     'Promotions and acquiring new clients'),
  ('Human Resources',       'Staff management'),
  ('Finance & Admin',       'Accounting and operations')
ON CONFLICT DO NOTHING
"""),

("Seed: positions", """
INSERT INTO public.positions (title, level, team, base_salary)
VALUES
  ('Head Chef',              'Senior',     'Kitchen & Culinary',    4000),
  ('Sous Chef',              'Mid',        'Kitchen & Culinary',    2500),
  ('Kitchen Assistant',      'Junior',     'Kitchen & Culinary',    1500),
  ('Head Nutritionist',      'Senior',     'Nutrition & Dietetics', 4500),
  ('Dietitian',              'Mid',        'Nutrition & Dietetics', 3000),
  ('Logistics Manager',      'Manager',    'Logistics & Delivery',  3500),
  ('Delivery Driver',        'Junior',     'Logistics & Delivery',  1800),
  ('Customer Service Agent', 'Junior',     'Customer Service',      1800),
  ('HR Manager',             'Manager',    'Human Resources',       3500),
  ('Accountant',             'Mid',        'Finance & Admin',       2500),
  ('General Manager',        'Executive',  'Finance & Admin',       6000),
  ('Internship',             'Intern',     'General',                800),
  ('Daily Wage Worker',      'Contractor', 'General',               1200)
ON CONFLICT DO NOTHING
"""),

]


def main():
    print("=" * 60)
    print("  Corporate HRM - Supabase Direct PostgreSQL Setup")
    print("  Host: db.kcswzfrwpvioaaizfpnk.supabase.co")
    print("=" * 60)

    print("\n[...] Connecting to database...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        print("[OK]  Connected successfully!\n")
    except Exception as e:
        print(f"[ERR] Connection failed: {e}")
        print("\nTip: Check your password and make sure the DB is accessible.")
        return

    ok = 0
    fail = 0

    print("[*] Creating Tables...\n")
    for label, ddl in TABLES:
        try:
            cur.execute(ddl)
            print(f"  [OK] {label}")
            ok += 1
        except Exception as e:
            print(f"  [FAIL] {label}: {e}")
            fail += 1

    print("\n[~] Seeding Default Data...\n")
    for label, dml in SEEDS:
        try:
            cur.execute(dml)
            print(f"  [OK] {label}")
        except Exception as e:
            print(f"  [WARN] {label}: {e}")

    cur.close()
    conn.close()

    print("\n" + "=" * 60)
    print(f"  Tables created : {ok}")
    if fail:
        print(f"  Failed         : {fail}")
    print("  Database setup COMPLETE!")
    print("  Open: http://127.0.0.1:5000")
    print("=" * 60)


if __name__ == "__main__":
    main()
