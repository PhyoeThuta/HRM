import os
from datetime import datetime, timedelta
from app import db_fetch, db_fetch_one, db_insert, db_delete, SUPABASE_URL, SUPABASE_KEY
import random

def main():
    print("=== Payroll Automation Engine Simulation ===")
    
    # 1. Get Employee 'EMP-001' (phyoe thuta)
    employee = db_fetch_one("Employees", "*", filters={"employee_id": "EMP-001"})
    if not employee:
        print("Employee EMP-001 not found.")
        return
        
    emp_uuid = employee["id"]
    base_salary = employee.get("salary") or 3000.0
    print(f"Target: {employee['Full_name']} (Salary: ${base_salary})")
    
    # Month to simulate: May 2026
    month_str = "2026-05"
    start_date = datetime(2026, 5, 1)
    
    # Delete existing sample data for May 2026 to start fresh
    print("\\n1. Cleaning up old test data...")
    old_attendance = db_fetch("attendance_records", "*", filters={"employee_id": emp_uuid})
    for a in old_attendance:
        if str(a.get("check_in", "")).startswith("2026-05"):
            db_delete("attendance_records", a["id"])
            
    old_sops = db_fetch("daily_sops", "*", filters={"employee_id": emp_uuid})
    for s in old_sops:
        if str(s.get("assigned_date", "")).startswith("2026-05"):
            db_delete("daily_sops", s["id"])

    print("\\n2. Generating May 2026 Sample Data...")
    
    # May 2026 has 31 days
    days_in_month = 31
    expected_working_days = 21 # 10 weekend days in May 2026
    attended_days = 19  # Missed 2 days
    
    # Generate Attendance
    attendance_records = []
    attendance_count = 0
    for i in range(days_in_month):
        current_date = start_date + timedelta(days=i)
        # Skip weekends (Saturday=5, Sunday=6)
        if current_date.weekday() >= 5:
            continue
            
        # Simulate attendance
        if attendance_count < attended_days:
            check_in = current_date.replace(hour=9, minute=random.randint(0, 15)).isoformat()
            check_out = current_date.replace(hour=17, minute=random.randint(0, 30)).isoformat()
            db_insert("attendance_records", {
                "employee_id": emp_uuid,
                "check_in": check_in,
                "check_out": check_out
            })
            attendance_count += 1
            attendance_records.append(current_date)
            
    print(f"  -> Generated {len(attendance_records)} attendance logs (out of {expected_working_days} expected working days).")
    
    # Generate SOPs
    completed_sops = 18 # Missed 3 SOPs out of 21
    
    sop_tasks = [
        "Clean the prep stations and sanitize all cutting boards",
        "Wash, peel, and portion daily vegetables",
        "Restock the cooking line",
        "Label and date all prepped food containers",
        "Empty kitchen trash bins and replace liners",
        "Sweep and mop the main kitchen floor"
    ]
    
    sop_count = 0
    for i in range(days_in_month):
        current_date = start_date + timedelta(days=i)
        if current_date.weekday() >= 5:
            continue
            
        is_completed = sop_count < completed_sops
        
        # USE LITERAL NEWLINE CHARACTER SO IT SPLITS PROPERLY IN UI
        tasks_text = '\n'.join(random.sample(sop_tasks, 4))
        
        db_insert("daily_sops", {
            "employee_id": emp_uuid,
            "task_description": tasks_text,
            "assigned_by": emp_uuid, # Simulating Admin UUID
            "assigned_date": current_date.strftime("%Y-%m-%d"),
            "is_completed": is_completed,
            "completed_at": current_date.replace(hour=16).isoformat() if is_completed else None,
            "proof_video_url": "/static/uploads/videos/d5ffadda-93e9-43a0-b8ac-66b36ac61733.mp4" if is_completed else None
        })
        sop_count += 1
        
    print(f"  -> Generated {expected_working_days} SOP tasks ({completed_sops} completed).")
    
    # 3. GENERATE PEER VOTING RECORDS (5 votes per employee)
    print("Generating peer voting records...")
    employees = db_fetch("Employees", "id")
    emp_ids = [e["id"] for e in employees]
    old_votes = db_fetch("peer_voting_records", "id")
    for v in old_votes:
        db_delete("peer_voting_records", v["id"])
        
    import uuid
    for emp_id in emp_ids:
        for _ in range(5):
            score = random.randint(3, 5) # Score between 3 and 5 stars
            db_insert("peer_voting_records", {
                "id": str(uuid.uuid4()),
                "voter_id": random.choice([e for e in emp_ids if e != emp_id]),
                "nominee_id": emp_id,
                "score": score,
                "comment": "Great team player!",
                "created_at": f"2026-05-{random.randint(1, 28):02d}T10:00:00"
            })
            
    print("Test data setup complete!")

if __name__ == "__main__":
    main()
