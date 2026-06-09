from app import supabase, db_insert, datetime
import sys

def run():
    print("Deleting old positions...")
    res = supabase.table('positions').select('id').execute()
    for row in res.data:
        supabase.table('positions').delete().eq('id', row['id']).execute()

    print("Deleting old departments...")
    res = supabase.table('Departments').select('id').execute()
    for row in res.data:
        supabase.table('Departments').delete().eq('id', row['id']).execute()

    departments = [
        "Kitchen & Culinary",
        "Nutrition & Dietetics",
        "Logistics & Delivery",
        "Customer Service",
        "Marketing & Sales",
        "Human Resources",
        "Finance & Admin"
    ]
    
    for dept in departments:
        db_insert("Departments", {
            "Department_name": dept,
            "created_at": datetime.utcnow().isoformat()
        })
    print(f"Inserted {len(departments)} departments.")

    positions = [
        {"title": "Head Chef", "level": "Senior", "team": "Kitchen & Culinary", "base_salary": 4000},
        {"title": "Sous Chef", "level": "Mid", "team": "Kitchen & Culinary", "base_salary": 2500},
        {"title": "Kitchen Assistant", "level": "Junior", "team": "Kitchen & Culinary", "base_salary": 1500},
        {"title": "Head Nutritionist", "level": "Senior", "team": "Nutrition & Dietetics", "base_salary": 4500},
        {"title": "Dietitian", "level": "Mid", "team": "Nutrition & Dietetics", "base_salary": 3000},
        {"title": "Logistics Manager", "level": "Manager", "team": "Logistics & Delivery", "base_salary": 3500},
        {"title": "Delivery Driver", "level": "Junior", "team": "Logistics & Delivery", "base_salary": 1800},
        {"title": "Customer Service Agent", "level": "Junior", "team": "Customer Service", "base_salary": 1800},
        {"title": "HR Manager", "level": "Manager", "team": "Human Resources", "base_salary": 3500},
        {"title": "Accountant", "level": "Mid", "team": "Finance & Admin", "base_salary": 2500},
        {"title": "General Manager", "level": "Executive", "team": "Finance & Admin", "base_salary": 6000},
        {"title": "Internship", "level": "Intern", "team": "General", "base_salary": 800},
        {"title": "Daily Wage Worker", "level": "Contractor", "team": "General", "base_salary": 1200}
    ]

    for p in positions:
        db_insert("positions", {
            "title": p["title"],
            "level": p["level"],
            "team": p["team"],
            "base_salary": p["base_salary"],
            "created_at": datetime.utcnow().isoformat()
        })
    print(f"Inserted {len(positions)} positions.")

if __name__ == "__main__":
    run()
