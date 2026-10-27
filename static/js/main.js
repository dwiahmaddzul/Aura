// ===========================================================================
// Aura Social — main.js
// Owns: shared state namespace, init bootstrap, page switching, polling
// scheduler, toast, time labels, small utils.
// Loaded FIRST. Other JS files attach functions to window.* for inline onclick.
// ===========================================================================

window.aura = {
  imgB64: null,
  selectedMood: null,
  liked: new Set(),
  bookmarked: new Set(),
  personas: [],
  myProfile: { display_name: 'Kamu', bio: '', avatar: 'K' },
  // Feed state (keyed, never re-rendered wholesale)
  posts: new Map(),       // id -> post
  allPosts: [],           // ordered list (newest first) of loaded posts
  feedCursor: null,       // created_at of the oldest loaded post
  feedDone: false,
  pendingNew: [],         // newer posts waiting behind the "postingan baru" pill
  openComments: new Set(),
  expandedComments: new Set(),
  // Story state
  storyData: [],
  curStoryUser: -1,
  curSlide: 0,
  // Story upload state
  storyUploadB64: null,
  // DM state
  dmCurrentPersona: null,
  dmPollTimer: null,
  // Page scroll memory
  page: 'home',
  pageScroll: {},
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

// ── tiny fetch helper: JSON + error handling ──
async function api(url, opts = {}) {
  const o = { ...opts };
  if (o.json !== undefined) {
    o.method = o.method || 'POST';
    o.headers = { 'Content-Type': 'application/json', ...(o.headers || {}) };
    o.body = JSON.stringify(o.json);
    delete o.json;
  }
  const r = await fetch(url, o);
  let data = null;
  try { data = await r.json(); } catch {}
  if (!r.ok) {
    const err = new Error((data && data.error) || ('HTTP ' + r.status));
    err.status = r.status;
    err.data = data;
    throw err;
  }
  return data;
}
window.api = api;

// ── INIT: start the feed immediately, everything else in parallel ──
// Runs after every <script> has loaded (feed.js etc. define loadFeed & co).
document.addEventListener('DOMContentLoaded', async () => {
  applyTimeAwarePlaceholder();
  loadFeed();
  const [pers, prof, health] = await Promise.allSettled([
    api('/api/personas'), api('/api/me/profile'), api('/api/health'),
  ]);
  if (pers.status === 'fulfilled') window.aura.personas = pers.value;
  if (prof.status === 'fulfilled') window.aura.myProfile = prof.value;
  if (health.status === 'fulfilled' && !health.value.api_key_present) showApiKeyWarning();
  applyMyProfile();
  applyTimeAwarePlaceholder();
  loadStories();
  loadDailyBanner();
  loadThrowback();
  maybeShowOnboarding();
  startPolling();
});

// ── POLLING: one timer, paused while the tab is hidden ──
let pollTick = 0;
let pollTimer = null;
function startPolling() {
  clearTimeout(pollTimer);
  const loop = async () => {
    if (!document.hidden) {
      pollTick++;
      try {
        if (window.aura.page === 'home') await refreshFeedHead();
        if (pollTick % 2 === 0) await loadStories(true);
        if (pollTick % 15 === 0) loadDailyBanner();
      } catch {}
    }
    pollTimer = setTimeout(loop, 20000);
  };
  pollTimer = setTimeout(loop, 20000);
}
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    if (window.aura.page === 'home') refreshFeedHead();
    loadStories(true);
    refreshTimeLabels();
  }
});

// ── TIME LABELS (computed in the viewer's own time zone) ──
function partOfDay(h) {
  if (h >= 4 && h < 11) return 'pagi';
  if (h >= 11 && h < 15) return 'siang';
  if (h >= 15 && h < 19) return 'sore';
  return 'malam';
}
function timeAgo(ts) {
  if (!ts) return '';
  const now = Date.now();
  const d = (now - ts * 1000) / 1000;
  if (d < 60) return 'baru saja';
  if (d < 3600) return Math.floor(d / 60) + ' mnt lalu';
  const then = new Date(ts * 1000);
  const today = new Date(now);
  const day0 = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((day0(today) - day0(then)) / 86400000);
  if (days === 0) return 'tadi ' + partOfDay(then.getHours());
  if (days === 1) return 'kemarin ' + partOfDay(then.getHours());
  if (days < 7) return days + ' hari lalu';
  if (days < 30) return Math.floor(days / 7) + ' minggu lalu';
  if (days < 365) return Math.max(1, Math.floor(days / 30)) + ' bulan lalu';
  return Math.floor(days / 365) + ' tahun lalu';
}
window.timeAgo = timeAgo;
function tsSpan(ts) {
  return `<span class="ts" data-ts="${ts || 0}">${timeAgo(ts)}</span>`;
}
window.tsSpan = tsSpan;
function refreshTimeLabels() {
  document.querySelectorAll('.ts[data-ts]').forEach(el => {
    const t = timeAgo(parseFloat(el.dataset.ts));
    if (el.textContent !== t) el.textContent = t;
  });
}
window.refreshTimeLabels = refreshTimeLabels;
setInterval(() => { if (!document.hidden) refreshTimeLabels(); }, 60000);

function showApiKeyWarning() {
  const home = document.getElementById('page-home');
  if (!home || document.querySelector('.api-warn')) return;
  const el = document.createElement('div');
  el.className = 'api-warn';
  el.innerHTML = `<b>API key belum di-set</b>Teman-temanmu belum bisa membalas. Isi <code>SILICONFLOW_API_KEY</code> di server lalu restart.`;
  const sw = document.getElementById('sw');
  if (sw) home.insertBefore(el, sw);
}
window.showApiKeyWarning = showApiKeyWarning;

function applyMyProfile() {
  const p = window.aura.myProfile;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  set('myDisplayName', p.display_name);
  set('myBio', p.bio);
  set('myAvatar', p.avatar);
  set('composeAvatar', p.avatar);
  set('composeAvatar2', p.avatar);
}
window.applyMyProfile = applyMyProfile;

// Time-aware compose placeholder — different prompt by part of day (local time)
function applyTimeAwarePlaceholder() {
  const pod = partOfDay(new Date().getHours());
  const prompts = {
    pagi: ['Pagi… ada apa di kepala?', 'Mau cerita gimana mulai hari ini?', 'Hal kecil apa yg bikin senyum tadi?'],
    siang: ['Lagi di mana? lagi ngapain?', 'Apa yg kepikir sekarang?', 'Cerita dong bagian terbaik hari ini sejauh ini'],
    sore: ['Hari hampir habis, gimana rasanya?', 'Ada momen yg pengen diingat?', 'Apa yg kamu selesaiin hari ini?'],
    malam: ['Sebelum tidur… mau cerita apa?', 'Hari ini berat atau ringan?', 'Apa yg jadi PR buat besok?'],
  };
  const list = prompts[pod] || prompts.siang;
  const pick = list[Math.floor(Math.random() * list.length)];
  const el = document.querySelector('.cph');
  if (el) el.textContent = pick;
  const ta = document.getElementById('ct');
  if (ta && !ta.value && (window.aura.composeMode || 'note') === 'note') ta.placeholder = pick;
}
window.applyTimeAwarePlaceholder = applyTimeAwarePlaceholder;
setInterval(applyTimeAwarePlaceholder, 30 * 60 * 1000);

// Onboarding banner — shown only if user has no posts yet
function maybeShowOnboarding() {
  if (!window.aura.myProfile.is_first_time) return;
  try { if (localStorage.getItem('auraOnboardSeen') === '1') return; } catch {}
  const greet = window.aura.myProfile.greeting || 'Halo';
  const el = document.createElement('div');
  el.className = 'ob-bn';
  el.innerHTML = `
    <button class="ob-bn-x" onclick="dismissOnboard()" aria-label="Tutup">×</button>
    <div class="ob-bn-h">${esc(greet)} 💜</div>
    <div class="ob-bn-t">Aura ini ruang pribadimu. Tulis apa pun, yang kecil atau yang besar. Beberapa teman di sini bakal menemani lewat komentar, story, dan DM. Mulai dari satu hal kecil: apa yang lagi kamu rasain sekarang?</div>`;
  const home = document.getElementById('page-home');
  const sw = document.getElementById('sw');
  if (home && sw) home.insertBefore(el, sw);
}
window.maybeShowOnboarding = maybeShowOnboarding;

function dismissOnboard() {
  try { localStorage.setItem('auraOnboardSeen', '1'); } catch {}
  document.querySelector('.ob-bn')?.remove();
}
window.dismissOnboard = dismissOnboard;

// ── NAV (remembers scroll position per page) ──
function switchPage(n) {
  const a = window.aura;
  if (a.page === n && n !== 'home') return;
  if (a.page === n && n === 'home') {  // tap Home again → back to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (a.pendingNew.length) showPendingPosts();
    return;
  }
  a.pageScroll[a.page] = window.scrollY;
  if (a.page === 'dm' && n !== 'dm' && typeof stopDmPolling === 'function') stopDmPolling();
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.ni').forEach(ni => ni.classList.remove('active'));
  document.getElementById('page-' + n)?.classList.add('active');
  document.getElementById('nav-' + n)?.classList.add('active');
  a.page = n;
  document.body.dataset.page = n;
  if (n === 'dm') {
    document.getElementById('dmThread').style.display = 'none';
    document.getElementById('dmList').style.display = '';
    if (typeof loadDmList === 'function') loadDmList();
  }
  if (n === 'notif' && typeof renderNotifs === 'function') renderNotifs();
  if (n === 'search' && typeof loadJournal === 'function') loadJournal();
  if (n === 'profile' && typeof loadMyProfilePage === 'function') loadMyProfilePage();
  if (n === 'home') refreshFeedHead();
  window.scrollTo({ top: a.pageScroll[n] || 0 });
}
window.switchPage = switchPage;

function shareProfile() {
  const url = window.location.origin;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(() => showToast('Link disalin'));
  } else {
    showToast(url);
  }
}
window.shareProfile = shareProfile;

// ── UTILS ──
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
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

// ── Simple confirm sheet (no window.confirm: it blocks the page) ──
function askConfirm({ title, text, ok = 'Ya', danger = false }) {
  return new Promise(resolve => {
    const ov = document.getElementById('confirmOv');
    document.getElementById('confirmTitle').textContent = title || 'Yakin?';
    document.getElementById('confirmText').textContent = text || '';
    const okBtn = document.getElementById('confirmOk');
    okBtn.textContent = ok;
    okBtn.classList.toggle('danger', !!danger);
    const done = (v) => { ov.classList.remove('open'); okBtn.onclick = null; cancel.onclick = null; resolve(v); };
    const cancel = document.getElementById('confirmCancel');
    okBtn.onclick = () => done(true);
    cancel.onclick = () => done(false);
    ov.onclick = (e) => { if (e.target === ov) done(false); };
    ov.classList.add('open');
  });
}
window.askConfirm = askConfirm;

// ── KEYBOARD SHORTCUTS ──
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape') {
    const lb = document.getElementById('lightbox');
    if (lb && lb.classList.contains('open')) { closeLightbox(); ev.preventDefault(); return; }
    const sv = document.getElementById('sv');
    if (sv && sv.classList.contains('open') && typeof closeSV === 'function') {
      closeSV(); ev.preventDefault(); return;
    }
    const openModals = document.querySelectorAll('.ov.open');
    if (openModals.length) {
      openModals.forEach(m => m.classList.remove('open'));
      ev.preventDefault();
      return;
    }
    if (document.getElementById('profOv')?.classList.contains('open')) { closeProfOv(); ev.preventDefault(); return; }
    if (window.aura.dmCurrentPersona) { closeDmThread(); ev.preventDefault(); return; }
  }
  const ae = document.activeElement;
  const inField = ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable);
  if (inField || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  if (ev.key === '/') { ev.preventDefault(); switchPage('search'); setTimeout(() => document.getElementById('searchInput')?.focus(), 100); }
  if (ev.key === 'n' && typeof openC === 'function') { ev.preventDefault(); openC(); }
  if (ev.key === 'h') { ev.preventDefault(); switchPage('home'); }
});
