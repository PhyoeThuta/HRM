import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the new helper function
helper_func = '''
def get_voting_categories(position_level: str, position_title: str) -> list:
    lvl = str(position_level or "").lower()
    title = str(position_title or "").lower()
    
    if "intern" in title or "trainee" in title or "junior" in lvl:
        cats = [("Fast Learner", "🚀"), ("Eagerness", "🔥"), ("Teamwork", "🤝"), ("Adaptability", "🦎"), ("Communication", "🗣️")]
    elif "manager" in lvl or "manager" in title or "executive" in lvl or "senior" in lvl:
        cats = [("Leadership", "👑"), ("Mentoring", "🎓"), ("Strategic Thinking", "🧠"), ("Empathy", "❤️"), ("Decision Making", "⚖️")]
    elif "hr" in title or "human resources" in title:
        cats = [("Empathy", "❤️"), ("Conflict Resolution", "🕊️"), ("Culture Building", "🏢"), ("Communication", "🗣️"), ("Supportiveness", "🤗")]
    elif "engineer" in title or "tech" in title:
        cats = [("Code Quality", "💻"), ("Problem Solving", "🔧"), ("Innovation", "💡"), ("Teamwork", "🤝"), ("Reliability", "🛡️")]
    elif "sales" in title or "marketing" in title:
        cats = [("Client Focus", "🎯"), ("Creativity", "🎨"), ("Target Achievement", "📈"), ("Communication", "🗣️"), ("Negotiation", "🤝")]
    elif "finance" in title or "admin" in title or "accountant" in title:
        cats = [("Attention to Detail", "🔍"), ("Organization", "📋"), ("Reliability", "🛡️"), ("Teamwork", "🤝"), ("Efficiency", "⚡")]
    else:
        cats = [("Teamwork", "🤝"), ("Dedication", "💪"), ("Communication", "🗣️"), ("Reliability", "🛡️"), ("Initiative", "🚀")]
    
    return [{"name": c[0], "icon": c[1]} for c in cats]
'''

# We will remove all occurrences of VOTE_CATEGORIES = [...]
content = re.sub(r'VOTE_CATEGORIES\s*=\s*\[.*?\]\n', '', content)

# Inject the helper function before the first build_vote_stats
content = re.sub(r'def build_vote_stats\(', helper_func.strip() + r'\n\ndef build_vote_stats(', content, count=1)

# Now update peer_voting_profile logic
# Admin route
admin_route_target = r'''    cat_avgs = {cat: round(sum(sc)/len(sc),1) for cat, sc in cat_raw.items()}
    stats = {"votes": votes_count, "total": total_score, "avg": avg_score, "cat_avgs": cat_avgs}
    return templates.TemplateResponse("peer_voting_profile.html", ctx(request, "peer_voting",
        nominee=nominee, votes=all_votes, voters=voters,
        categories=VOTE_CATEGORIES, stats=stats))'''

admin_route_replacement = r'''    cat_avgs = {cat: round(sum(sc)/len(sc),1) for cat, sc in cat_raw.items()}
    stats = {"votes": votes_count, "total": total_score, "avg": avg_score, "cat_avgs": cat_avgs}
    
    pos_id = nominee.get("position_id")
    pos = db_fetch_one("positions", "*", filters={"id": pos_id}) if pos_id else {}
    lvl = pos.get("level", "")
    title = pos.get("title", "")
    categories = get_voting_categories(lvl, title)
    
    return templates.TemplateResponse("peer_voting_profile.html", ctx(request, "peer_voting",
        nominee=nominee, votes=all_votes, voters=voters,
        categories=categories, stats=stats))'''

content = content.replace(admin_route_target, admin_route_replacement)

# Portal route
portal_route_target = r'''    cat_avgs = {cat: round(sum(sc)/len(sc),1) for cat, sc in cat_raw.items()}
    stats = {"votes": votes_count, "total": total_score, "avg": avg_score, "cat_avgs": cat_avgs}
    return templates.TemplateResponse("portal/vote_profile.html", ctx(request, "portal",
        nominee=nominee, votes=all_votes, categories=VOTE_CATEGORIES,
        stats=stats, emp_id=emp_id))'''

portal_route_replacement = r'''    cat_avgs = {cat: round(sum(sc)/len(sc),1) for cat, sc in cat_raw.items()}
    stats = {"votes": votes_count, "total": total_score, "avg": avg_score, "cat_avgs": cat_avgs}
    
    pos_id = nominee.get("position_id")
    pos = db_fetch_one("positions", "*", filters={"id": pos_id}) if pos_id else {}
    lvl = pos.get("level", "")
    title = pos.get("title", "")
    categories = get_voting_categories(lvl, title)
    
    return templates.TemplateResponse("portal/vote_profile.html", ctx(request, "portal",
        nominee=nominee, votes=all_votes, categories=categories,
        stats=stats, emp_id=emp_id))'''

content = content.replace(portal_route_target, portal_route_replacement)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

import ast
try:
    ast.parse(content)
    print("app.py successfully modified and valid!")
except Exception as e:
    print(f"app.py is invalid: {e}")
