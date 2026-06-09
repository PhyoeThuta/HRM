import psycopg2

conn = psycopg2.connect('host=db.kcswzfrwpvioaaizfpnk.supabase.co port=5432 dbname=postgres user=postgres password=PHYOEthuta123!@# sslmode=require')
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE public.recruitment_candidates ADD COLUMN notes TEXT;")
    print("Added notes column")
    # Refresh postgrest schema cache via SQL command if possible
    cur.execute("NOTIFY pgrst, 'reload schema';")
    print("Reloaded schema cache")
except Exception as e:
    print(e)
    conn.rollback()

conn.commit()
cur.close()
conn.close()
print("Done.")
