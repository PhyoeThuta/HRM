import psycopg2
conn = psycopg2.connect(host='db.kcswzfrwpvioaaizfpnk.supabase.co',port=5432,dbname='postgres',user='postgres',password='PHYOEthuta123!@#',sslmode='require')
conn.autocommit = True
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS public.qr_attendance_tokens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token       TEXT UNIQUE NOT NULL,
  employee_id UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  expires_at  TIMESTAMPTZ,
  used        BOOLEAN DEFAULT FALSE,
  used_at     TIMESTAMPTZ
)
""")
cur.execute('ALTER TABLE public.qr_attendance_tokens DISABLE ROW LEVEL SECURITY')
cur.execute('GRANT ALL ON public.qr_attendance_tokens TO anon, authenticated, service_role')
print('[OK] qr_attendance_tokens table created')
cur.close()
conn.close()
