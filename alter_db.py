import psycopg2

DB_CONFIG = {
    'host':     'db.kcswzfrwpvioaaizfpnk.supabase.co',
    'port':     5432,
    'dbname':   'postgres',
    'user':     'postgres',
    'password': 'PHYOEthuta123!@#',
    'sslmode':  'require',
    'connect_timeout': 10
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('ALTER TABLE public."Employees" ADD COLUMN IF NOT EXISTS national_id TEXT;')
    cur.execute('ALTER TABLE public."Employees" ADD COLUMN IF NOT EXISTS address TEXT;')
    cur.execute("ALTER TABLE public.\"Employees\" ADD COLUMN IF NOT EXISTS employment_type TEXT DEFAULT 'Full-Time';")
    print('Columns added successfully!')
except Exception as e:
    print('Error:', e)
