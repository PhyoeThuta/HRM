import json
from app import db_fetch

users = db_fetch("sys_users", "*")
employees = db_fetch("Employees", "*")
payrolls = db_fetch("payrolls", "*")

print("Users:")
for u in users:
    print(f"Username: {u.get('username')}, EmpID: {u.get('employee_id')}")

print("\nEmployees:")
for e in employees:
    print(f"Name: {e.get('Full_name')}, UUID: {e.get('id')}, StringID: {e.get('employee_id')}")

print("\nPayrolls:")
for p in payrolls:
    print(f"Month: {p.get('month')}, EmpID in Payroll: {p.get('employee_id')}")
