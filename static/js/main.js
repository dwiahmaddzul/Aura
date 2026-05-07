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
  applyTimeAwarePlaceholder();
  renderPL();
  loadFeed();
  loadStories();
  loadDailyBanner();
  loadThrowback();
  loadStreak();
  maybeShowOnboarding();
  setInterval(loadFeed, 15000);
  setInterval(loadStories, 30000);
  setInterval(loadDailyBanner, 5 * 60 * 1000);
  setInterval(applyTimeAwarePlaceholder, 30 * 60 * 1000);
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

// Time-aware compose placeholder — different prompt by part of day
function applyTimeAwarePlaceholder() {
  const pod = window.aura.myProfile.part_of_day || 'siang';
  const prompts = {
    pagi: ['Pagi… ada apa di kepala?', 'Mau cerita gimana mulai hari ini?', 'Hal kecil apa yg bikin senyum tadi?'],
    siang: ['Lagi di mana? lagi ngapain?', 'Apa yg kepikir sekarang?', 'Cerita dong bagian terbaik hari ini sejauh ini'],
    sore: ['Hari hampir habis — gimana rasanya?', 'Ada momen yg pengen diingat?', 'Apa yg lo selesaiin hari ini?'],
    malam: ['Sebelum tidur… mau cerita apa?', 'Hari ini berat atau ringan?', 'Apa yg jadi PR buat besok?'],
  };
  const list = prompts[pod] || prompts.siang;
  const pick = list[Math.floor(Math.random() * list.length)];
  const el = document.querySelector('.cph');
  if (el) el.textContent = pick;
  const ta = document.getElementById('ct');
  if (ta && !ta.value) ta.placeholder = pick;
}
window.applyTimeAwarePlaceholder = applyTimeAwarePlaceholder;

// Onboarding banner — shown only if user has no posts yet
function maybeShowOnboarding() {
  if (!window.aura.myProfile.is_first_time) return;
  if (localStorage.getItem('auraOnboardSeen') === '1') return;
  const greet = window.aura.myProfile.greeting || 'Halo';
  const el = document.createElement('div');
  el.className = 'ob-bn';
  el.innerHTML = `
    <button class="ob-bn-x" onclick="dismissOnboard()">×</button>
    <div class="ob-bn-h">${greet} 💜</div>
    <div class="ob-bn-t">Aura ini ruang pribadi-mu. Tulis apapun — yg kecil, yg besar, yg cuma lo yg ngerti. Beberapa temen di sini bakal nemenin lewat komen, story, dan DM. Mulai dari satu hal kecil aja: apa yg lagi lo rasain sekarang?</div>
  `;
  // Insert above stories container
  const home = document.getElementById('page-home');
  const sw = document.getElementById('sw');
  if (home && sw) home.insertBefore(el, sw);
}
window.maybeShowOnboarding = maybeShowOnboarding;

function dismissOnboard() {
  localStorage.setItem('auraOnboardSeen', '1');
  document.querySelector('.ob-bn')?.remove();
}
window.dismissOnboard = dismissOnboard;

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
  if (n === 'notif') {
    if (typeof renderNotifs === 'function') renderNotifs();
  }
  if (n === 'search') {
    document.getElementById('searchInput')?.focus();
  }
  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
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

// ── KEYBOARD SHORTCUTS ──
document.addEventListener('keydown', (ev) => {
  // Esc closes any open modal/overlay
  if (ev.key === 'Escape') {
    const openModals = document.querySelectorAll('.ov.open');
    if (openModals.length) {
      openModals.forEach(m => m.classList.remove('open'));
      ev.preventDefault();
      return;
    }
    // Close DM thread if open
    if (window.aura.dmCurrentPersona) {
      closeDmThread();
      ev.preventDefault();
      return;
    }
    // Close story viewer if open
    const sv = document.getElementById('sv');
    if (sv && sv.classList.contains('open') && typeof closeSV === 'function') {
      closeSV();
      ev.preventDefault();
      return;
    }
  }

  // Ignore if typing in input/textarea
  const ae = document.activeElement;
  const inField = ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA');
  if (inField) return;

  // / focuses search
  if (ev.key === '/') {
    ev.preventDefault();
    switchPage('search');
    setTimeout(() => document.getElementById('searchInput')?.focus(), 100);
  }
  // n opens new post
  if (ev.key === 'n' && typeof openC === 'function') {
    ev.preventDefault();
    openC();
  }
  // h home
  if (ev.key === 'h') {
    ev.preventDefault();
    switchPage('home');
  }
});
