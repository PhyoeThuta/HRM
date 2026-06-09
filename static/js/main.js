// ── Toast Notification System ──────────────────────────────
(function() {
  const container = document.createElement('div');
  container.id = 'toast-container';
  document.body.appendChild(container);
})();

function showToast(message, type = 'info', duration = 4000) {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icons = { success:'✅', error:'❌', info:'ℹ️' };
  toast.innerHTML = `<span>${icons[type] || '•'}</span><span>${message}</span>`;
  document.getElementById('toast-container').appendChild(toast);
  setTimeout(() => {
    toast.classList.add('dismiss');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ── Global Modal Helpers ────────────────────────────────────
function openModal(id)  { const m = document.getElementById(id); if(m){ m.classList.remove('hidden'); document.body.style.overflow='hidden'; } }
function closeModal(id) { const m = document.getElementById(id); if(m){ m.classList.add('hidden'); document.body.style.overflow=''; } }

// Close modal on Escape
document.addEventListener('keydown', e => {
  if(e.key === 'Escape') {
    document.querySelectorAll('[id$="-modal"]:not(.hidden)').forEach(m => closeModal(m.id));
  }
});

// ── Auto-dismiss flash messages ─────────────────────────────
setTimeout(() => { const f = document.getElementById('flash-msg'); if(f) f.style.opacity='0', setTimeout(()=>f.remove(),400); }, 4000);
setTimeout(() => { const f = document.getElementById('flash-err'); if(f) f.style.opacity='0', setTimeout(()=>f.remove(),400); }, 5500);

// ── Active nav highlight ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname;
  document.querySelectorAll('aside nav a').forEach(link => {
    if(link.getAttribute('href') === path || (path.startsWith(link.getAttribute('href')) && link.getAttribute('href') !== '/')) {
      link.classList.add('ring-1', 'ring-indigo-500/30');
    }
  });
});
