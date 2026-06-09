import psycopg2
import sys

try:
    conn = psycopg2.connect(
        host='db.kcswzfrwpvioaaizfpnk.supabase.co',
        port=5432,
        dbname='postgres',
        user='postgres',
        password='PHYOEthuta123!@#',
        sslmode='require'
    )
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS public.employee_documents (
      id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      employee_id UUID REFERENCES public."Employees"(id) ON DELETE CASCADE,
      doc_type    TEXT NOT NULL,
      title       TEXT NOT NULL,
      content     TEXT,
      status      TEXT DEFAULT 'Pending Signature',
      created_by  UUID,
      created_at  TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS public.document_signatures (
      id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      document_id    UUID REFERENCES public.employee_documents(id) ON DELETE CASCADE,
      signer_id      TEXT NOT NULL,
      signer_role    TEXT,
      signature_data TEXT NOT NULL,
      signed_at      TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    cur.execute('ALTER TABLE public.employee_documents DISABLE ROW LEVEL SECURITY')
    cur.execute('GRANT ALL ON public.employee_documents TO anon, authenticated, service_role')
    
    cur.execute('ALTER TABLE public.document_signatures DISABLE ROW LEVEL SECURITY')
    cur.execute('GRANT ALL ON public.document_signatures TO anon, authenticated, service_role')

    print('[OK] Documents tables created successfully')
    cur.close()
    conn.close()
except Exception as e:
    print(f'[ERROR] {e}')
    sys.exit(1)
