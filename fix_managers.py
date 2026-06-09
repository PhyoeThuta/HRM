from app import db_fetch, db_insert, db_update
import uuid
from datetime import date

def fix_managers():
    sys_users = db_fetch('sys_users', '*')
    for u in sys_users:
        if not u.get('employee_id'):
            role = u.get('role', 'employee')
            name_map = {
                'boss': 'Boss (CEO)',
                'hr_manager': 'HR Manager',
                'general_manager': 'General Manager'
            }
            full_name = name_map.get(role, u.get('username').capitalize())
            
            # Check if we already created it (e.g. Boss)
            existing = db_fetch('Employees', 'id', filters={'employee_id': f"EMP-{u['username'].upper()}"})
            if existing:
                new_emp_id = existing[0]['id']
            else:
                emp_data = {
                    'employee_id': f"EMP-{u['username'].upper()}",
                    'Full_name': full_name,
                    'email': f"{u['username']}@company.com",
                    'status': 'Active',
                    'hire_date': date.today().isoformat(),
                    'salary': 0
                }
                print(f"Creating employee record for {u['username']}...")
                res = db_insert('Employees', emp_data)
                
                # Depending on the supabase python client version, it might return a list directly, or an object with data
                if isinstance(res, list) and len(res) > 0:
                    new_emp_id = res[0]['id']
                elif hasattr(res, 'data') and res.data and len(res.data) > 0:
                    new_emp_id = res.data[0]['id']
                else:
                    # fallback fetch
                    created = db_fetch('Employees', 'id', filters={'employee_id': f"EMP-{u['username'].upper()}"})
                    new_emp_id = created[0]['id']
            
            # Link to sys_users
            db_update('sys_users', u['id'], {'employee_id': new_emp_id})
            print(f"Linked {u['username']} to Employee ID {new_emp_id}")

if __name__ == '__main__':
    fix_managers()
    print("Done!")
