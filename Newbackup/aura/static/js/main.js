// ===========================================================================
// Aura Social — main.js
// Owns: shared state namespace, init bootstrap, page switching, toast, utils
// Loaded FIRST. Other JS files attach functions to window.* for inline onclick.
// ===========================================================================

window.aura = {
  imgB64: null,
  selectedMood: null,
  liked: new Set(),
  bookmarked: new Set(),
  personas: [],
  allPosts: [],
  myProfile: { display_name: 'Kamu 👤', bio: '', avatar: 'K' },
  // Story state
  storyData: [],
  curStoryUser: -1,
  curSlide: 0,
  storyTimer: null,
  // Story upload state
  storyUploadB64: null,
  // Repost state
  repostOf: null,
  // DM state
  dmCurrentPersona: null,
  dmPollTimer: null,
};

// Mood emoji map — used by feed.js to render mood badge on posts
window.MOOD_EMOJI = {
  senang: '😊',
  sedih: '😢',
  capek: '😴',
  excited: '✨',
  bingung: '🤔',
  tenang: '😌',
};

// ── INIT ──
(async () => {
  try {
    const r = await fetch('/api/personas');
    window.aura.personas = await r.json();
  } catch {}
  try {
    const r = await fetch('/api/me/profile');
    if (r.ok) window.aura.myProfile = await r.json();
  } catch {}
  applyMyProfile();
  renderPL();
  renderNotifs();
  loadFeed();
  loadStories();
  loadDailyBanner();
  loadThrowback();
  loadStreak();
  setInterval(loadFeed, 15000);
  setInterval(loadStories, 30000);
  setInterval(loadDailyBanner, 5 * 60 * 1000);
})();

function applyMyProfile() {
  const p = window.aura.myProfile;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  set('myDisplayName', p.display_name);
  set('myBio', p.bio);
  set('myAvatar', p.avatar);
  set('composeAvatar', p.avatar);
}
window.applyMyProfile = applyMyProfile;

// ── NAV ──
function switchPage(n) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.ni').forEach(ni => ni.classList.remove('active'));
  document.getElementById('page-' + n)?.classList.add('active');
  document.getElementById('nav-' + n)?.classList.add('active');
  // Page-specific load
  if (n === 'dm') {
    document.getElementById('dmThread').style.display = 'none';
    document.getElementById('dmList').style.display = '';
    if (typeof loadDmList === 'function') loadDmList();
  }
  if (n === 'profile') {
    if (typeof loadStreak === 'function') loadStreak();
  }
}
window.switchPage = switchPage;

function shareProfile() {
  const url = window.location.origin + '/?u=' + encodeURIComponent(window.aura.myProfile.display_name);
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(() => showToast('🔗 Link disalin!'));
  } else {
    showToast('🔗 ' + url);
  }
}
window.shareProfile = shareProfile;

// ── UTILS ──
function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
window.esc = esc;

let tT;
function showToast(m) {
  const t = document.getElementById('toast');
  t.textContent = m;
  t.classList.add('show');
  clearTimeout(tT);
  tT = setTimeout(() => t.classList.remove('show'), 2400);
}
window.showToast = showToast;
