import psycopg2
conn = psycopg2.connect(host='db.kcswzfrwpvioaaizfpnk.supabase.co',port=5432,dbname='postgres',user='postgres',password='PHYOEthuta123!@#',sslmode='require')
conn.autocommit = True
cur = conn.cursor()
cur.execute('ALTER TABLE public.daily_sops ADD COLUMN IF NOT EXISTS video_hash TEXT')
cur.execute("NOTIFY pgrst, 'reload schema'")
print('[OK] video_hash column added and schema cache reloaded')
cur.close()
conn.close()
