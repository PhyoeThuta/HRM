import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    response = supabase.table("attendance_records").select("*").execute()
    for row in response.data:
        if row.get("check_in"):
            try:
                dt = datetime.fromisoformat(row["check_in"].replace("Z", "+00:00")).replace(tzinfo=None)
                if dt.hour >= 9 and row.get("is_late") == False:
                    print(f"Updating record {row['id']} to is_late=True")
                    supabase.table("attendance_records").update({"is_late": True}).eq("id", row["id"]).execute()
            except Exception as e:
                print("Error parsing time for row", row["id"], e)
    print("Done fixing existing attendance records.")
else:
    print("No Supabase URL or Key found.")
