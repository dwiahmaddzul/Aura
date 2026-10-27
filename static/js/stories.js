// ===========================================================================
// Aura Social — stories.js
// Owns: stories rail, story viewer (multi-slide, tap/hold, preload), seen
// state, highlights, story reply.
// Depends on: main.js (window.aura, api, esc, timeAgo, showToast)
// ===========================================================================

const STORY_MS = 5000;
let railSig = '';

function seenSet() {
  try { return new Set(JSON.parse(localStorage.getItem('auraSeenStories') || '[]')); } catch { return new Set(); }
}
function markSeen(id) {
  try {
    const s = seenSet();
    if (s.has(id)) return;
    const arr = [...s, id].slice(-400);
    localStorage.setItem('auraSeenStories', JSON.stringify(arr));
  } catch {}
}

async function loadStories(silent = false) {
  try {
    window.aura.storyData = await api('/api/stories');
  } catch {
    if (!silent) window.aura.storyData = [];
  }
  renderStories();
}
window.loadStories = loadStories;

function renderStories() {
  const w = document.getElementById('sw');
  const a = window.aura;
  const seen = seenSet();
  const byUser = new Map((a.storyData || []).map(s => [s.username, s]));
  const unseenOf = (s) => s ? s.slides.filter(x => !seen.has(x.id)).length : 0;
  const people = (a.personas || []).filter(p => p.active !== false || byUser.has(p.username)).map(p => {
    const s = byUser.get(p.username);
    return { p, s, unseen: unseenOf(s), latest: s ? s.latest : 0 };
  });
  people.sort((x, y) => (y.unseen > 0) - (x.unseen > 0) || (!!y.s) - (!!x.s) || y.latest - x.latest);
  const meStory = byUser.get('me');
  const sig = JSON.stringify([meStory ? meStory.slides.map(x => x.id) : 0,
    people.map(x => [x.p.username, x.s ? x.s.slides.map(y => y.id) : 0, x.unseen]), (a.myProfile || {}).avatar]);
  if (sig === railSig) return;  // tidak ada yang berubah → jangan sentuh DOM
  railSig = sig;
  const meAv = (a.myProfile && a.myProfile.avatar) || 'K';
  let h;
  if (meStory && meStory.slides.length) {
    h = `<div class="si" role="button" tabindex="0" onclick="openSVUser('me')">
      <div class="sr ${unseenOf(meStory) ? 'has-story' : 'seen'}">
        <div class="sav av-me">${esc(meAv)}</div>
        <button class="si-add" onclick="event.stopPropagation();openMyStoryUpload()" aria-label="Tambah story">+</button>
      </div>
      <div class="slbl">Kamu</div></div>`;
  } else {
    h = `<div class="si" role="button" tabindex="0" onclick="openMyStoryUpload()">
      <div class="sr seen"><div class="sav add">+</div></div>
      <div class="slbl">Story-mu</div></div>`;
  }
  people.forEach(({ p, s, unseen }) => {
    const ring = s ? (unseen ? 'has-story' : 'seen viewed') : 'seen none';
    h += `<div class="si" role="button" tabindex="0" onclick="openSVUser('${esc(p.username)}')" aria-label="${s ? 'Story' : 'Profil'} ${esc(p.display)}">
      <div class="sr ${ring}"><div class="sav" style="background:${esc(p.color)}">${esc(p.avatar)}</div></div>
      <div class="slbl">${esc(p.username)}</div></div>`;
  });
  w.innerHTML = h;
}
window.renderStories = renderStories;

// ── viewer ──
const sv = { list: [], ui: -1, si: 0, raf: 0, start: 0, elapsed: 0, paused: false, mode: 'rail' };

function openSVUser(username) {
  const a = window.aura;
  const idx = (a.storyData || []).findIndex(s => s.username === username);
  if (idx < 0 || !a.storyData[idx].slides.length) {
    if (username === 'me') return openMyStoryUpload();
    return openProfile(username);  // tidak ada story → buka profilnya, bukan layar kosong
  }
  sv.list = a.storyData;
  sv.mode = 'rail';
  sv.ui = idx;
  // mulai dari slide pertama yang belum dilihat
  const seen = seenSet();
  const firstUnseen = a.storyData[idx].slides.findIndex(x => !seen.has(x.id));
  sv.si = firstUnseen >= 0 ? firstUnseen : 0;
  openViewer();
}
window.openSVUser = openSVUser;

function openStoryFromProfile(username, slideIdx) {
  const a = window.aura;
  const idx = (a.storyData || []).findIndex(s => s.username === username);
  if (idx < 0) return showToast('Story belum dimuat, coba lagi');
  sv.list = a.storyData;
  sv.mode = 'rail';
  sv.ui = idx;
  sv.si = Math.min(slideIdx || 0, a.storyData[idx].slides.length - 1);
  openViewer();
}
window.openStoryFromProfile = openStoryFromProfile;

function openHighlightStory(storyId, username) {
  const a = window.aura;
  const slide = (window._hl || {})[storyId];
  const p = (a.personas || []).find(x => x.username === username) || {};
  if (!slide) return;
  sv.list = [{ username, display: p.display || 'Sorotan', avatar: p.avatar || '✨', color: p.color || '#333', slides: [slide] }];
  sv.mode = 'highlight';
  sv.ui = 0;
  sv.si = 0;
  openViewer();
}
window.openHighlightStory = openHighlightStory;

function openViewer() {
  const el = document.getElementById('sv');
  el.classList.add('open');
  el.setAttribute('aria-hidden', 'false');
  document.body.classList.add('noscroll');
  showSlide();
}

function curUser() { return sv.list[sv.ui]; }
function curSlideObj() { const u = curUser(); return u ? u.slides[sv.si] : null; }

function showSlide() {
  const u = curUser();
  const s = curSlideObj();
  if (!u || !s) return closeSV();
  document.getElementById('svav').textContent = u.avatar;
  document.getElementById('svav').style.background = u.color;
  document.getElementById('svun').textContent = u.display;
  document.getElementById('sv-time').textContent = sv.mode === 'highlight' ? '✨ Sorotan' : timeAgo(s.created_at);
  document.getElementById('sv-bars').innerHTML = u.slides.map((_, i) =>
    `<div class="svbr"><div class="svf" id="svf-${i}" style="width:${i < sv.si ? 100 : 0}%"></div></div>`).join('');
  const caption = s.caption ? `<div class="sv-caption">${esc(s.caption)}</div>` : '';
  document.getElementById('sve').innerHTML = `
    <div class="sv-bgimg" style="background-image:url('${s.img}')"></div>
    <img class="sv-img" src="${s.img}" alt="Story ${esc(u.display)}" decoding="async">
    ${caption}
    <div class="sv-tap sv-tap-left" aria-label="Sebelumnya"></div>
    <div class="sv-tap sv-tap-right" aria-label="Berikutnya"></div>`;
  bindTapZones();
  const reply = document.getElementById('svReplyInput');
  const own = u.username === 'me';
  document.querySelector('.svbot').style.visibility = own ? 'hidden' : 'visible';
  if (reply) reply.placeholder = own ? '' : `Balas ${u.display}…`;
  const likeBtn = document.getElementById('svLikeBtn');
  if (likeBtn) { likeBtn.dataset.liked = '0'; likeBtn.textContent = '🤍'; }
  markSeen(s.id);
  // preload slide berikutnya supaya tidak ada jeda hitam
  const next = u.slides[sv.si + 1] || (sv.list[sv.ui + 1] && sv.list[sv.ui + 1].slides[0]);
  if (next) { const im = new Image(); im.src = next.img; }
  startProgress();
}

function bindTapZones() {
  const left = document.querySelector('#sve .sv-tap-left');
  const right = document.querySelector('#sve .sv-tap-right');
  [left, right].forEach((z, i) => {
    let downAt = 0;
    z.addEventListener('pointerdown', () => { downAt = Date.now(); pauseProgress(); });
    z.addEventListener('pointerup', () => {
      const held = Date.now() - downAt > 250;
      resumeProgress();
      if (!held) (i === 0 ? storyPrev : storyNext)();
    });
    z.addEventListener('pointerleave', () => { if (sv.paused) resumeProgress(); });
  });
}

function startProgress() {
  cancelAnimationFrame(sv.raf);
  sv.elapsed = 0;
  sv.start = performance.now();
  sv.paused = false;
  const tick = (now) => {
    if (!document.getElementById('sv').classList.contains('open')) return;
    if (!sv.paused) {
      const t = sv.elapsed + (now - sv.start);
      const fill = document.getElementById('svf-' + sv.si);
      if (fill) fill.style.width = Math.min(100, (t / STORY_MS) * 100) + '%';
      if (t >= STORY_MS) return storyNext();
    }
    sv.raf = requestAnimationFrame(tick);
  };
  sv.raf = requestAnimationFrame(tick);
}
function pauseProgress() {
  if (sv.paused) return;
  sv.elapsed += performance.now() - sv.start;
  sv.paused = true;
}
function resumeProgress() {
  if (!sv.paused) return;
  sv.start = performance.now();
  sv.paused = false;
}

function storyNext() {
  const u = curUser();
  if (!u) return closeSV();
  if (sv.si < u.slides.length - 1) { sv.si++; return showSlide(); }
  if (sv.mode === 'rail' && sv.ui < sv.list.length - 1) { sv.ui++; sv.si = 0; return showSlide(); }
  closeSV();
}
window.storyNext = storyNext;

function storyPrev() {
  if (sv.si > 0) { sv.si--; return showSlide(); }
  if (sv.mode === 'rail' && sv.ui > 0) { sv.ui--; sv.si = sv.list[sv.ui].slides.length - 1; return showSlide(); }
  startProgress();
}
window.storyPrev = storyPrev;

function closeSV() {
  cancelAnimationFrame(sv.raf);
  const el = document.getElementById('sv');
  el.classList.remove('open');
  el.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('noscroll');
  document.getElementById('sve').innerHTML = '';
  railSig = '';
  renderStories();  // perbarui cincin "sudah dilihat"
}
window.closeSV = closeSV;

// Pause while typing a reply
document.addEventListener('focusin', (e) => { if (e.target && e.target.id === 'svReplyInput') pauseProgress(); });
document.addEventListener('focusout', (e) => { if (e.target && e.target.id === 'svReplyInput') resumeProgress(); });

// ── Story reply: DM to that friend, with the story caption as context ──
async function sendStoryReply() {
  const inp = document.getElementById('svReplyInput');
  const txt = (inp?.value || '').trim();
  if (!txt) return;
  const u = curUser();
  const s = curSlideObj();
  if (!u || u.username === 'me') return;
  const ctx = sv.mode === 'highlight'
    ? `[balas sorotan] ${txt}`
    : (s && s.caption ? `[balas story: "${s.caption}"] ${txt}` : `[balas story] ${txt}`);
  inp.value = '';
  try {
    await api('/api/dm/' + u.username, { json: { content: ctx } });
    showToast(`Pesan terkirim ke ${u.display}`);
    const target = u.username;
    closeSV();
    setTimeout(() => { switchPage('dm'); setTimeout(() => openDmThread(target), 150); }, 250);
  } catch {
    showToast('Gagal mengirim');
  }
}
window.sendStoryReply = sendStoryReply;

// Quick like for a story (visual feedback only — no backend table for story likes)
function likeStory() {
  const btn = document.getElementById('svLikeBtn');
  if (!btn) return;
  const liked = btn.dataset.liked === '1';
  btn.dataset.liked = liked ? '0' : '1';
  btn.textContent = liked ? '🤍' : '❤️';
  btn.classList.add('pop');
  setTimeout(() => btn.classList.remove('pop'), 220);
}
window.likeStory = likeStory;
