import psycopg2

DB_URL = "postgresql://postgres:PHYOEthuta123!%40%23@db.kcswzfrwpvioaaizfpnk.supabase.co:5432/postgres"

def run():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()
    print("Creating system_notifications table...")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_notifications (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        recipient_role    TEXT,
        recipient_user_id UUID,
        title             TEXT NOT NULL,
        message           TEXT NOT NULL,
        link_url          TEXT,
        is_read           BOOLEAN DEFAULT FALSE,
        created_at        TIMESTAMPTZ DEFAULT NOW()
    );
    """)
    cur.execute('ALTER TABLE system_notifications DISABLE ROW LEVEL SECURITY;')
    cur.execute('GRANT ALL ON TABLE system_notifications TO anon, authenticated, service_role;')
    conn.commit()
    cur.close()
    conn.close()
    print("system_notifications table created successfully.")

if __name__ == "__main__":
    run()
