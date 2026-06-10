import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def run():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get Finance Dept ID
    res = supabase.table("Departments").select("id").eq("Department_name", "Finance & Admin").execute()
    # Insert Finance Manager
    insert_res = supabase.table("positions").insert({
        "title": "Finance Manager",
        "level": "Manager",
        "team": "Finance & Admin",
        "base_salary": 4500
    }).execute()
    
    print("✅ Successfully inserted 'Finance Manager' position!")

if __name__ == "__main__":
    run()
