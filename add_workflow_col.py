import psycopg2

conn = psycopg2.connect('host=db.kcswzfrwpvioaaizfpnk.supabase.co port=5432 dbname=postgres user=postgres password=PHYOEthuta123!@# sslmode=require')
cur = conn.cursor()
cur.execute("ALTER TABLE public.employee_documents ADD COLUMN IF NOT EXISTS signature_workflow TEXT DEFAULT 'hr_then_employee'")
conn.commit()
print('Added signature_workflow column')
