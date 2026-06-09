import psycopg2

conn = psycopg2.connect('host=db.kcswzfrwpvioaaizfpnk.supabase.co port=5432 dbname=postgres user=postgres password=PHYOEthuta123!@# sslmode=require')
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE public.recruitment_candidates ADD COLUMN resume_content TEXT;")
    print("Added resume_content")
except Exception as e:
    print(e)
    conn.rollback()

try:
    cur.execute("ALTER TABLE public.recruitment_candidates ADD COLUMN ai_score INTEGER;")
    print("Added ai_score")
except Exception as e:
    print(e)
    conn.rollback()

try:
    cur.execute("ALTER TABLE public.recruitment_candidates ADD COLUMN ai_reasoning TEXT;")
    print("Added ai_reasoning")
except Exception as e:
    print(e)
    conn.rollback()

try:
    cur.execute("ALTER TABLE public.recruitment_candidates ADD COLUMN interview_guide TEXT;")
    print("Added interview_guide")
except Exception as e:
    print(e)
    conn.rollback()

conn.commit()
cur.close()
conn.close()
print("Done.")
