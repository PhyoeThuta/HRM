import psycopg2

conn = psycopg2.connect('host=db.kcswzfrwpvioaaizfpnk.supabase.co port=5432 dbname=postgres user=postgres password=PHYOEthuta123!@# sslmode=require')
cur = conn.cursor()
cur.execute("INSERT INTO public.system_notifications (recipient_role, title, message, link_url) VALUES ('boss', 'Signature Required', 'A new document (Promotion) for phyoe thuta requires your signature.', '/documents')")
conn.commit()
print('Notification inserted')
