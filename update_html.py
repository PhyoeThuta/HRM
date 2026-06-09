import os

files_to_update = [
    'templates/peer_voting_profile.html',
    'templates/portal/vote_profile.html'
]

target = """            {% for cat in categories %}
            <label class="flex items-center gap-2 bg-white/5 hover:bg-white/8 border border-white/10 rounded-xl px-3 py-2.5 cursor-pointer transition-all duration-150 has-[:checked]:border-indigo-500/50 has-[:checked]:bg-indigo-500/10">
              <input type="radio" name="category" value="{{ cat }}" required class="accent-indigo-500 flex-shrink-0"/>
              <span class="text-xs text-slate-300 font-medium">
                {% if cat == 'Leadership' %}👑 {% elif cat == 'Teamwork' %}🤝 {% elif cat == 'Innovation' %}💡 {% elif cat == 'Communication' %}🗣️ {% elif cat == 'Problem Solving' %}🔧 {% elif cat == 'Dedication' %}💪 {% elif cat == 'Mentoring' %}🎓 {% endif %}{{ cat }}</span>
            </label>
            {% endfor %}"""

replacement = """            {% for cat in categories %}
            <label class="flex items-center gap-2 bg-white/5 hover:bg-white/8 border border-white/10 rounded-xl px-3 py-2.5 cursor-pointer transition-all duration-150 has-[:checked]:border-indigo-500/50 has-[:checked]:bg-indigo-500/10">
              <input type="radio" name="category" value="{{ cat.name }}" required class="accent-indigo-500 flex-shrink-0"/>
              <span class="text-xs text-slate-300 font-medium">
                {{ cat.icon }} {{ cat.name }}</span>
            </label>
            {% endfor %}"""

for path in files_to_update:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if target in content:
        content = content.replace(target, replacement)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {path}")
    else:
        print(f"Target not found in {path}")
