import sys

# Read the existing peer voting backend helper functions we need to reuse
routes_code = '''
# ── Portal: Peer Voting — Grid ────────────────────────────────────────────
@app.get("/portal/vote", response_class=HTMLResponse)
async def portal_vote_grid(request: Request):
    user       = get_current_user(request)
    emp_id     = user.get("employee_id","") if user else ""
    employees  = db_fetch("Employees", "id,Full_name,employee_id,Dept_id,status", filters={"status":"Active"})
    votes      = db_fetch("peer_voting_records", "*")
    depts      = db_fetch("Departments", "id,Department_name")
    dept_map   = {d["id"]: d["Department_name"] for d in depts}
    for e in employees:
        e["dept_name"] = dept_map.get(e.get("Dept_id",""),"—")
    vote_stats = build_vote_stats(votes, employees)
    lb = sorted(vote_stats.values(), key=lambda x: x["total"], reverse=True)[:5]
    return templates.TemplateResponse("portal/vote.html", ctx(request, "portal",
        employees=employees, vote_stats=vote_stats, leaderboard=lb, emp_id=emp_id))

# ── Portal: Peer Voting — Profile ────────────────────────────────────────
@app.get("/portal/vote/{nominee_id}", response_class=HTMLResponse)
async def portal_vote_profile(request: Request, nominee_id: str):
    user       = get_current_user(request)
    emp_id     = user.get("employee_id","") if user else ""
    nominee    = db_fetch_one("Employees", "*", filters={"id": nominee_id})
    if not nominee:
        raise HTTPException(404, "Employee not found")
    depts      = db_fetch("Departments","id,Department_name")
    dept_map   = {d["id"]: d["Department_name"] for d in depts}
    nominee["dept_name"] = dept_map.get(nominee.get("Dept_id",""),"—")
    all_votes  = db_fetch("peer_voting_records", "*", filters={"nominee_id": nominee_id})
    all_emps   = db_fetch("Employees", "id,Full_name")
    emp_name_map = {e["id"]: e.get("Full_name","—") for e in all_emps}
    for v in all_votes:
        v["voter_name"] = emp_name_map.get(v.get("voter_id",""),"Anonymous")
    votes_count = len(all_votes)
    total_score = sum(int(v.get("score") or 0) for v in all_votes)
    avg_score   = round(total_score / votes_count, 1) if votes_count else 0
    cat_raw: dict = {}
    for v in all_votes:
        cat = v.get("category","General")
        cat_raw.setdefault(cat, []).append(int(v.get("score") or 0))
    cat_avgs = {cat: round(sum(sc)/len(sc),1) for cat, sc in cat_raw.items()}
    stats = {"votes": votes_count, "total": total_score, "avg": avg_score, "cat_avgs": cat_avgs}
    return templates.TemplateResponse("portal/vote_profile.html", ctx(request, "portal",
        nominee=nominee, votes=all_votes, categories=VOTE_CATEGORIES,
        stats=stats, emp_id=emp_id))

# ── Portal: Peer Voting — Cast Vote POST ────────────────────────────────
@app.post("/portal/vote/{nominee_id}/submit", response_class=RedirectResponse)
async def portal_vote_cast(request: Request, nominee_id: str,
    category: str = Form(...), score: int = Form(...),
    comment: str = Form(None)):
    user   = get_current_user(request)
    emp_id = user.get("employee_id","") if user else ""
    if not emp_id:
        return redirect_with_msg(f"/portal/vote/{nominee_id}", error="Account+not+linked+to+employee")
    if emp_id == nominee_id:
        return redirect_with_msg(f"/portal/vote/{nominee_id}", error="You+cannot+vote+for+yourself")
    nominee = db_fetch_one("Employees","Full_name",filters={"id":nominee_id})
    name    = nominee.get("Full_name","") if nominee else ""
    db_insert("peer_voting_records", {
        "voter_id": emp_id, "nominee_id": nominee_id,
        "score": score, "category": category, "comment": comment,
        "created_at": datetime.utcnow().isoformat(),
    })
    return redirect_with_msg(f"/portal/vote/{nominee_id}",
        success=f"Vote+submitted+for+{name.replace(' ','+')}")
'''

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove OLD portal_vote routes (the old simple ones injected before)
# Find and remove the old /portal/vote GET and POST blocks
import re

# Remove old portal vote routes that were previously injected
old_patterns = [
    r'# ── Portal: Peer Voting GET ──[^\n]*\n@app\.get\("/portal/vote"[^@]+',
    r'# ── Portal: Peer Voting POST ──[^\n]*\n@app\.post\("/portal/vote/submit"[^@]+',
]
for pat in old_patterns:
    content = re.sub(pat, '', content, flags=re.DOTALL)

# Insert before entry point
MARKER = 'if __name__ == "__main__":'
pos = content.rfind(MARKER)
if pos == -1:
    print("ERROR: entry point marker not found")
    sys.exit(1)

new_content = content[:pos] + routes_code + '\n' + content[pos:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

# Verify
import subprocess
result = subprocess.run(['python', '-c', 'import ast; ast.parse(open("app.py").read()); print("SYNTAX OK")'],
                       capture_output=True, text=True, cwd='.')
print(result.stdout or result.stderr)
print(f"Total lines: {new_content.count(chr(10))}")
