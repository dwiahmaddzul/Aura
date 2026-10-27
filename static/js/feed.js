// ===========================================================================
// Aura Social — feed.js
// Owns: feed (keyed rendering, incremental refresh, infinite scroll),
// post card, likes, comments, bookmarks, post menu, lightbox, single-post
// view, own-profile tabs, Aktivitas (notifications) and Jurnal.
//
// The feed is NEVER rebuilt wholesale. Polling only patches what changed
// (counts, new comments) and new posts wait behind a "postingan baru" pill,
// so typing a comment, scroll position and open threads are never disturbed.
// Depends on: main.js (window.aura, api, esc, tsSpan, timeAgo, showToast)
// ===========================================================================

const FEED_PAGE = 15;
const ICON = {
  heart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
  chat: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  bookmark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>',
  send: '<svg viewBox="0 0 24 24" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
  dots: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg>',
};

// ── data helpers ──
function feedEl() { return document.getElementById('feed'); }

function rememberPost(p) {
  const a = window.aura;
  a.posts.set(p.id, p);
  if (p.is_liked) a.liked.add(p.id); else a.liked.delete(p.id);
  if (p.bookmarked) a.bookmarked.add(p.id); else a.bookmarked.delete(p.id);
}

function sortFeed() {
  window.aura.allPosts.sort((x, y) => (y.created_at || 0) - (x.created_at || 0));
}

// ── initial load ──
async function loadFeed() {
  const a = window.aura;
  const el = feedEl();
  try {
    const posts = await api(`/api/posts?limit=${FEED_PAGE}`);
    a.posts.clear();
    a.allPosts = [];
    a.pendingNew = [];
    el.innerHTML = '';
    if (!posts.length) {
      el.innerHTML = '<div class="empty"><span>🌱</span>Feed-mu masih kosong.<div class="empty-tip">Mulai cerita apa aja, sekecil apa pun. Ada yang bakal dengar.</div></div>';
    }
    appendPosts(posts);
    a.feedDone = posts.length < FEED_PAGE;
    updateFeedFooter();
    setupFeedSentinel();
  } catch {
    el.innerHTML = '<div class="empty"><span>⚠️</span>Feed gagal dimuat.<div class="empty-tip"><button class="linkbtn" onclick="loadFeed()">Coba lagi</button></div></div>';
  }
}
window.loadFeed = loadFeed;

function appendPosts(list) {
  const a = window.aura;
  const el = feedEl();
  const frag = document.createDocumentFragment();
  for (const p of list) {
    if (a.posts.has(p.id)) continue;
    rememberPost(p);
    a.allPosts.push(p);
    frag.appendChild(cardNode(p));
  }
  el.querySelector('.empty')?.remove();
  el.appendChild(frag);
  sortFeed();
  const last = a.allPosts[a.allPosts.length - 1];
  a.feedCursor = last ? last.created_at : null;
}

function prependPosts(list) {
  const a = window.aura;
  const el = feedEl();
  el.querySelector('.empty')?.remove();
  // oldest first so the newest ends up on top
  [...list].sort((x, y) => (x.created_at || 0) - (y.created_at || 0)).forEach(p => {
    if (a.posts.has(p.id)) { patchCard(p); return; }
    rememberPost(p);
    a.allPosts.push(p);
    const node = cardNode(p);
    node.classList.add('enter');
    el.insertBefore(node, el.firstChild);
  });
  sortFeed();
}
window.prependPosts = prependPosts;

function cardNode(p) {
  const t = document.createElement('template');
  t.innerHTML = pCard(p).trim();
  return t.content.firstElementChild;
}

// ── incremental refresh (polling) ──
let refreshing = false;
async function refreshFeedHead() {
  const a = window.aura;
  if (refreshing) return;
  if (!a.allPosts.length && !feedEl().querySelector('.pc')) return loadFeed();
  refreshing = true;
  try {
    const posts = await api(`/api/posts?limit=${FEED_PAGE}`);
    const newest = a.allPosts.length ? a.allPosts[0].created_at : 0;
    const fresh = [];
    for (const p of posts) {
      if (a.posts.has(p.id)) patchCard(p);
      else if ((p.created_at || 0) > newest && !a.pendingNew.some(x => x.id === p.id)) fresh.push(p);
    }
    if (fresh.length) {
      if (window.scrollY < 140 && !userIsTypingInFeed() && a.page === 'home') prependPosts(fresh);
      else {
        a.pendingNew = fresh.concat(a.pendingNew);
        updateNewPill();
      }
    }
  } catch {} finally { refreshing = false; }
}
window.refreshFeedHead = refreshFeedHead;

function userIsTypingInFeed() {
  const ae = document.activeElement;
  return !!(ae && ae.closest && ae.closest('#feed') && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA'));
}

function updateNewPill() {
  const pill = document.getElementById('newPill');
  if (!pill) return;
  const n = window.aura.pendingNew.length;
  pill.hidden = !n;
  pill.querySelector('span').textContent = n === 1 ? '1 postingan baru' : `${n} postingan baru`;
}

function showPendingPosts() {
  const a = window.aura;
  const list = a.pendingNew;
  a.pendingNew = [];
  updateNewPill();
  if (list.length) prependPosts(list);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
window.showPendingPosts = showPendingPosts;

// ── infinite scroll ──
let feedObserver = null;
let loadingMore = false;
function setupFeedSentinel() {
  const s = document.getElementById('feedMore');
  if (!s || feedObserver || !('IntersectionObserver' in window)) return;
  feedObserver = new IntersectionObserver((entries) => {
    if (entries.some(e => e.isIntersecting)) loadMoreFeed();
  }, { rootMargin: '700px 0px' });
  feedObserver.observe(s);
}

async function loadMoreFeed() {
  const a = window.aura;
  if (loadingMore || a.feedDone || !a.feedCursor) return;
  loadingMore = true;
  updateFeedFooter();
  try {
    const posts = await api(`/api/posts?limit=${FEED_PAGE}&before=${a.feedCursor}`);
    appendPosts(posts);
    if (posts.length < FEED_PAGE) a.feedDone = true;
  } catch {
    showToast('Gagal memuat postingan lama');
  } finally {
    loadingMore = false;
    updateFeedFooter();
  }
}
window.loadMoreFeed = loadMoreFeed;

function updateFeedFooter() {
  const s = document.getElementById('feedMore');
  if (!s) return;
  const a = window.aura;
  if (!a.allPosts.length) { s.innerHTML = ''; return; }
  s.innerHTML = loadingMore
    ? '<div class="sk-card sk-short"></div>'
    : a.feedDone
      ? '<div class="feed-end">Sudah sampai ujung 🌙</div>'
      : '<button class="linkbtn" onclick="loadMoreFeed()">Muat lebih banyak</button>';
}

// ── card markup ──
function avatarHTML(p, cls = 'av') {
  const isAI = p.username && p.username !== 'me';
  const attrs = isAI ? `role="button" tabindex="0" onclick="openProfile('${esc(p.username)}')" aria-label="Profil ${esc(p.display)}"` : '';
  return `<div class="${cls}${isAI ? ' tap' : ' av-me'}" style="background:${esc(p.color)}" ${attrs}>${esc(p.avatar)}</div>`;
}

function imageHTML(p, cls = 'pimg') {
  if (!p.has_image) return '';
  const w = p.img_w || 1, h = p.img_h || 1;
  const srcset = (p.img_w || 0) > 700 && p.img_full
    ? ` srcset="${p.img} 640w, ${p.img_full} 1280w" sizes="(max-width: 430px) 100vw, 430px"` : '';
  return `<div class="pimg-w" style="aspect-ratio:${w}/${h}">
    <img class="${cls}" src="${p.img}"${srcset} loading="lazy" decoding="async" alt="Foto dari ${esc(p.display)}"
      onclick="openLightbox('${p.img_full || p.img}')" onload="this.parentNode.classList.add('ok')" onerror="this.parentNode.classList.add('ok','err')">
  </div>`;
}

function pCard(p) {
  const a = window.aura;
  const lk = a.liked.has(p.id);
  const bm = a.bookmarked.has(p.id);
  const isAI = p.username !== 'me';
  const isGrat = p.post_type === 'gratitude';
  let m = isGrat ? '<div class="grat-tag">🙏 Catatan syukur</div>' : '';
  if (p.original) {
    const o = p.original;
    m += `<div class="rp-w">
      <div class="rp-h"><div class="av" style="background:${esc(o.color)}">${esc(o.avatar)}</div>
      <div class="rp-u">${esc(o.display)}</div><div class="rp-t">· ${tsSpan(o.created_at)}</div></div>
      ${o.content ? `<div class="rp-c">${esc(o.content)}</div>` : ''}
      ${o.has_image ? `<img src="${o.img}" class="rp-img" loading="lazy" alt="">` : ''}
    </div>`;
  }
  m += imageHTML(p);
  if (p.content) m += `<div class="pbody ${p.has_image ? 'cap' : ''}">${esc(p.content)}</div>`;
  const comments = p.comments || [];
  const open = comments.length > 0 || a.openComments.has(p.id);
  const mood = p.mood && window.MOOD_EMOJI[p.mood] ? ` · <span class="pmood" title="${esc(p.mood)}">${window.MOOD_EMOJI[p.mood]}</span>` : '';
  return `<article class="pc${isGrat ? ' grat' : ''}" id="pc${p.id}" data-id="${p.id}">
    <div class="ph">
      ${avatarHTML(p)}
      <div class="pm">
        <div class="pu${isAI ? ' tap' : ''}"${isAI ? ` onclick="openProfile('${esc(p.username)}')"` : ''}>${esc(p.display)}</div>
        <div class="pt">${tsSpan(p.created_at)}${mood}</div>
      </div>
      <button class="pmenu" onclick="postMenu(${p.id})" aria-label="Opsi postingan">${ICON.dots}</button>
    </div>
    ${m}
    <div class="pacts">
      <button class="ab${lk ? ' liked' : ''}" data-like="${p.id}" onclick="doLike(${p.id})" aria-pressed="${lk}" aria-label="Suka">
        ${ICON.heart}<span class="lc">${p.likes || 0}</span>
      </button>
      <button class="ab" onclick="tgCm(${p.id})" aria-label="Komentar">
        ${ICON.chat}<span class="ccount">${p.comment_count || 0}</span>
      </button>
      <div class="sp"></div>
      <button class="ab${bm ? ' saved' : ''}" data-bm="${p.id}" onclick="doBookmark(${p.id})" aria-pressed="${bm}" aria-label="Simpan">
        ${ICON.bookmark}
      </button>
    </div>
    <div class="cw" id="cm${p.id}"${open ? '' : ' hidden'}>
      <div id="cml${p.id}" class="cml">${commentsHTML(p)}</div>
      <div class="cir">
        <input class="cinp" id="ci${p.id}" placeholder="Tulis komentar…" maxlength="600" enterkeyhint="send"
          onkeydown="if(event.key==='Enter'&&!event.isComposing)doCm(${p.id})" aria-label="Tulis komentar">
        <button class="csend" onclick="doCm(${p.id})" aria-label="Kirim">${ICON.send}</button>
      </div>
    </div>
  </article>`;
}
window.pCard = pCard;

// ── Threaded comments (1 level), preview = 2 latest threads ──
function cmtRow(c, postId, root, isReply) {
  const isAI = c.username !== 'me';
  return `<div class="ci${isReply ? ' ci-reply' : ''}${c.pending ? ' pending' : ''}" data-cid="${c.id || ''}">
    <div class="cav${isAI ? ' tap' : ''}" style="background:${esc(c.color)}"${isAI ? ` onclick="openProfile('${esc(c.username)}')"` : ''}>${esc(c.avatar)}</div>
    <div class="cb">
      <span class="cu${isAI ? ' tap' : ''}"${isAI ? ` onclick="openProfile('${esc(c.username)}')"` : ''}>${esc(c.display)}</span>
      <span class="ct">${esc(c.content)}</span>
      <div class="ctm">${c.pending ? 'mengirim…' : tsSpan(c.created_at)}${c.pending ? '' : ` · <button class="creply" onclick="replyTo(${postId},${root},this)">Balas</button>`}</div>
    </div>
  </div>`;
}

function commentsHTML(p) {
  const comments = p.comments || [];
  const tops = comments.filter(c => !c.parent_id);
  const byParent = {};
  comments.filter(c => c.parent_id).forEach(c => { (byParent[c.parent_id] = byParent[c.parent_id] || []).push(c); });
  let shown = tops;
  let more = '';
  if (!window.aura.expandedComments.has(p.id) && tops.length > 2) {
    shown = tops.slice(-2);
    more = `<button class="cmore" onclick="expandComments(${p.id})">Lihat semua ${comments.length} komentar</button>`;
  }
  return more + shown.map(t => {
    const reps = (byParent[t.id] || []).map(r => cmtRow(r, p.id, t.id, true)).join('');
    return `<div class="cthread" id="cth${p.id}_${t.id}">${cmtRow(t, p.id, t.id, false)}${reps}</div>`;
  }).join('');
}
window.commentsHTML = commentsHTML;

function renderComments(id) {
  const p = window.aura.posts.get(id);
  if (!p) return;
  document.querySelectorAll(`#cml${id}`).forEach(el => { el.innerHTML = commentsHTML(p); });
  document.querySelectorAll(`#pc${id} .ccount, .psheet[data-id="${id}"] .ccount`).forEach(el => { el.textContent = (p.comments || []).length; });
}

function expandComments(id) {
  window.aura.expandedComments.add(id);
  renderComments(id);
}
window.expandComments = expandComments;

// Patch an existing card with fresh server data (no rebuild).
function patchCard(p) {
  const a = window.aura;
  const old = a.posts.get(p.id);
  const pendingC = old ? (old.comments || []).filter(c => c.pending) : [];
  if (old && old._likeBusy) { p.likes = old.likes; p.is_liked = old.is_liked; p._likeBusy = true; }
  if (pendingC.length) p.comments = (p.comments || []).concat(pendingC);
  a.posts.set(p.id, p);
  const i = a.allPosts.findIndex(x => x.id === p.id);
  if (i >= 0) a.allPosts[i] = p;
  if (!p._likeBusy) {
    if (p.is_liked) a.liked.add(p.id); else a.liked.delete(p.id);
    setLikeUI(p.id, p.is_liked, p.likes);
  }
  const oldIds = old ? (old.comments || []).map(c => c.id).join(',') : '';
  const newIds = (p.comments || []).map(c => c.id).join(',');
  if (oldIds !== newIds) {
    renderComments(p.id);
    const cw = document.getElementById('cm' + p.id);
    if (cw && (p.comments || []).length) cw.hidden = false;
  }
}
window.patchCard = patchCard;

function replyTo(postId, root, btn) {
  const inp = document.getElementById('ci' + postId);
  if (!inp) return;
  const name = btn?.closest('.ci')?.querySelector('.cu')?.textContent || 'dia';
  inp.dataset.parent = root;
  inp.placeholder = 'Balas ' + name + '…';
  inp.focus();
  const bar = inp.closest('.cir');
  if (bar && !document.getElementById('rc' + postId)) {
    const chip = document.createElement('button');
    chip.id = 'rc' + postId;
    chip.className = 'reply-cancel';
    chip.type = 'button';
    chip.textContent = '✕';
    chip.title = 'Batal balas';
    chip.setAttribute('aria-label', 'Batal balas');
    chip.onclick = () => cancelReply(postId);
    bar.insertBefore(chip, inp);
  }
}
window.replyTo = replyTo;

function cancelReply(postId) {
  const inp = document.getElementById('ci' + postId);
  if (inp) { delete inp.dataset.parent; inp.placeholder = 'Tulis komentar…'; }
  document.getElementById('rc' + postId)?.remove();
}
window.cancelReply = cancelReply;

function tgCm(id) {
  const el = document.getElementById('cm' + id);
  if (!el) return;
  const a = window.aura;
  if (el.hidden) {
    el.hidden = false;
    a.openComments.add(id);
    document.getElementById('ci' + id)?.focus();
  } else {
    const hasComments = (a.posts.get(id)?.comments || []).length > 0;
    const inp = document.getElementById('ci' + id);
    if (hasComments) { inp?.focus(); return; }
    el.hidden = true;
    a.openComments.delete(id);
  }
}
window.tgCm = tgCm;

// ── likes / bookmarks (optimistic) ──
function setLikeUI(id, liked, count) {
  document.querySelectorAll(`[data-like="${id}"]`).forEach(btn => {
    btn.classList.toggle('liked', !!liked);
    btn.setAttribute('aria-pressed', !!liked);
    const c = btn.querySelector('.lc');
    if (c) c.textContent = count;
  });
}

async function doLike(id) {
  const a = window.aura;
  const p = a.posts.get(id) || { id, likes: 0 };
  const btn = document.querySelector(`[data-like="${id}"]`);
  const wasLiked = btn ? btn.classList.contains('liked') : a.liked.has(id);
  const was = btn ? parseInt(btn.querySelector('.lc')?.textContent || '0', 10) : (p.likes || 0);
  const now = wasLiked ? Math.max(0, was - 1) : was + 1;
  p._likeBusy = true;
  setLikeUI(id, !wasLiked, now);
  document.querySelectorAll(`[data-like="${id}"]`).forEach(b => { if (!wasLiked) { b.classList.add('pop'); setTimeout(() => b.classList.remove('pop'), 260); } });
  try {
    const d = await api(`/api/posts/${id}/like`, { method: 'POST' });
    p.likes = d.likes; p.is_liked = d.liked;
    d.liked ? a.liked.add(id) : a.liked.delete(id);
    setLikeUI(id, d.liked, d.likes);
  } catch {
    setLikeUI(id, wasLiked, was);
    showToast('Gagal, coba lagi');
  } finally {
    p._likeBusy = false;
  }
}
window.doLike = doLike;

async function doBookmark(id) {
  const a = window.aura;
  const was = a.bookmarked.has(id);
  const set = (v) => document.querySelectorAll(`[data-bm="${id}"]`).forEach(b => {
    b.classList.toggle('saved', v); b.setAttribute('aria-pressed', v);
  });
  set(!was);
  try {
    const d = await api(`/api/posts/${id}/bookmark`, { method: 'POST' });
    d.bookmarked ? a.bookmarked.add(id) : a.bookmarked.delete(id);
    set(d.bookmarked);
    showToast(d.bookmarked ? 'Disimpan' : 'Dihapus dari simpanan');
  } catch {
    set(was);
    showToast('Gagal, coba lagi');
  }
}
window.doBookmark = doBookmark;

// ── comments (optimistic) ──
async function doCm(id) {
  const inp = document.getElementById('ci' + id);
  const txt = (inp?.value || '').trim();
  if (!txt) return;
  const a = window.aura;
  const parent = inp.dataset.parent ? parseInt(inp.dataset.parent, 10) : null;
  const me = a.myProfile || {};
  const p = a.posts.get(id);
  const temp = {
    id: 'tmp' + Date.now(), post_id: id, username: 'me', content: txt, is_ai: 0, parent_id: parent,
    created_at: Date.now() / 1000, display: me.display_name || 'Kamu', avatar: me.avatar || 'K',
    color: 'linear-gradient(140deg,var(--acc),#b98a52)', pending: true,
  };
  inp.value = '';
  cancelReply(id);
  if (p) {
    p.comments = (p.comments || []).concat(temp);
    if (parent == null) a.expandedComments.add(id);  // make sure the new one is visible
    renderComments(id);
  }
  try {
    const d = await api(`/api/posts/${id}/comment`, { json: { text: txt, parent_id: parent } });
    if (p) {
      p.comments = p.comments.filter(c => c.id !== temp.id).concat(d.comment ? [d.comment] : []);
      renderComments(id);
    }
  } catch {
    if (p) { p.comments = p.comments.filter(c => c.id !== temp.id); renderComments(id); }
    inp.value = txt;
    showToast('Komentar gagal terkirim');
  }
}
window.doCm = doCm;

// ── post menu (···) ──
function postMenu(id) {
  const a = window.aura;
  const p = a.posts.get(id) || (window._sheetPost && window._sheetPost.id === id ? window._sheetPost : null);
  if (!p) return;
  const items = [];
  if (p.content) items.push(`<button class="menu-i" onclick="copyPostText(${id})">Salin teks</button>`);
  if (p.username === 'me') {
    items.push(`<button class="menu-i danger" onclick="deletePost(${id})">Hapus tulisan ini</button>`);
  } else {
    items.push(`<button class="menu-i" onclick="closeMenu();openProfile('${esc(p.username)}')">Lihat profil ${esc(p.display)}</button>`);
    items.push(`<button class="menu-i" onclick="closeMenu();switchPage('dm');setTimeout(()=>openDmThread('${esc(p.username)}'),150)">Kirim pesan</button>`);
  }
  document.getElementById('menuItems').innerHTML = items.join('');
  document.getElementById('menuOv').classList.add('open');
}
window.postMenu = postMenu;

function closeMenu() { document.getElementById('menuOv').classList.remove('open'); }
window.closeMenu = closeMenu;

function copyPostText(id) {
  const p = window.aura.posts.get(id) || window._sheetPost;
  closeMenu();
  if (p && navigator.clipboard) navigator.clipboard.writeText(p.content || '').then(() => showToast('Teks disalin'));
}
window.copyPostText = copyPostText;

async function deletePost(id) {
  closeMenu();
  const ok = await askConfirm({ title: 'Hapus tulisan ini?', text: 'Komentar dan fotonya ikut terhapus. Tidak bisa dibatalkan.', ok: 'Hapus', danger: true });
  if (!ok) return;
  try {
    await api(`/api/posts/${id}`, { method: 'DELETE' });
    const a = window.aura;
    a.posts.delete(id);
    a.allPosts = a.allPosts.filter(x => x.id !== id);
    document.querySelectorAll(`#pc${id}`).forEach(el => el.remove());
    if (document.getElementById('profOv')?.classList.contains('open') && window._sheetPost?.id === id) closeProfOv();
    showToast('Terhapus');
    if (a.page === 'profile') loadMyProfilePage();
  } catch (e) {
    if (e.status === 401) {
      const go = await askConfirm({ title: 'Perlu masuk dulu', text: 'Menghapus tulisan butuh password Pengaturan, supaya orang lain yang membuka link Aura tidak bisa menghapus jurnalmu.', ok: 'Buka Pengaturan' });
      if (go) location.href = '/kelola';
    } else {
      showToast('Gagal menghapus');
    }
  }
}
window.deletePost = deletePost;

// ── lightbox ──
function openLightbox(src) {
  const lb = document.getElementById('lightbox');
  if (!lb) return;
  lb.querySelector('img').src = src;
  lb.classList.add('open');
}
window.openLightbox = openLightbox;
function closeLightbox() {
  const lb = document.getElementById('lightbox');
  lb.classList.remove('open');
  lb.querySelector('img').removeAttribute('src');
}
window.closeLightbox = closeLightbox;

// ── single post view (from Aktivitas / Jurnal / throwback) ──
async function openPost(id) {
  const card = document.getElementById('pc' + id);
  if (card && card.closest('#feed')) {
    if (window.aura.page !== 'home') switchPage('home');
    setTimeout(() => {
      card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      card.classList.add('flash');
      setTimeout(() => card.classList.remove('flash'), 1400);
    }, 120);
    return;
  }
  try {
    const p = await api(`/api/posts/${id}`);
    rememberPost(p);
    window._sheetPost = p;
    document.getElementById('profContent').innerHTML =
      `<div class="psheet" data-id="${p.id}">${pCard(p)}</div>`;
    document.getElementById('profOv').classList.add('open');
  } catch {
    showToast('Postingan sudah tidak ada');
  }
}
window.openPost = openPost;

// ── own PROFILE page ──
async function loadMyProfilePage() {
  try {
    const s = await api('/api/me/stats');
    document.getElementById('sp').textContent = s.entries;
    document.getElementById('thisMonth').textContent = s.this_month;
    const ph = document.getElementById('photoCount');
    if (ph) ph.textContent = s.photos;
  } catch {}
  const active = document.querySelector('#page-profile .ptab.active');
  switchPT(active || document.querySelector('#page-profile .ptab'), active?.dataset.tab || 'grid');
}
window.loadMyProfilePage = loadMyProfilePage;

function listRowHTML(p) {
  const mood = p.mood && window.MOOD_EMOJI[p.mood] ? ' · ' + window.MOOD_EMOJI[p.mood] : '';
  return `<div class="lrow" onclick="openPost(${p.id})">
    <div class="av" style="background:${esc(p.color)}">${esc(p.avatar)}</div>
    <div class="lrow-m">
      <div class="lrow-n">${esc(p.display)}</div>
      <div class="lrow-t">${tsSpan(p.created_at)}${mood}</div>
      ${p.content ? `<div class="lrow-c">${esc(p.content)}</div>` : ''}
      ${p.has_image ? `<img src="${p.img}" class="lrow-img" loading="lazy" alt="">` : ''}
    </div>
  </div>`;
}

function gridHTML(posts, empty) {
  if (!posts.length) return `<div class="empty small">${empty}</div>`;
  return '<div class="pgrid">' + posts.map(p =>
    `<button class="pgi" onclick="openPost(${p.id})" aria-label="Buka foto"><img src="${p.img}" loading="lazy" decoding="async" alt=""></button>`
  ).join('') + '</div>';
}

let ptSeq = 0;
async function switchPT(el, t) {
  document.querySelectorAll('#page-profile .ptab').forEach(x => x.classList.remove('active'));
  if (el) el.classList.add('active');
  const c = document.getElementById('pc2');
  const seq = ++ptSeq;
  c.innerHTML = '<div class="sk"><div class="sk-bar"></div><div class="sk-bar"></div></div>';
  const done = (html) => { if (seq === ptSeq) c.innerHTML = html; };
  try {
    if (t === 'grid') {
      const posts = await api('/api/posts?mine=1&photos=1&limit=45&comments=0');
      done(gridHTML(posts, 'Belum ada foto'));
    } else if (t === 'tweets') {
      const posts = (await api('/api/posts?mine=1&limit=50&comments=0')).filter(p => !p.has_image);
      done(posts.length ? posts.map(listRowHTML).join('') : '<div class="empty"><span>💬</span>Belum ada catatan teks</div>');
    } else if (t === 'liked') {
      const posts = await api('/api/me/liked');
      const lcEl = document.getElementById('likedCount');
      if (lcEl) lcEl.textContent = posts.length;
      done(posts.length ? posts.map(listRowHTML).join('') : '<div class="empty"><span>❤️</span>Belum ada yang kamu sukai</div>');
    } else if (t === 'saved') {
      const posts = await api('/api/me/bookmarks');
      done(posts.length ? posts.map(listRowHTML).join('') : '<div class="empty"><span>🔖</span>Belum ada yang kamu simpan</div>');
    } else if (t === 'mood') {
      const [days, stats] = await Promise.all([api('/api/me/mood-timeline'), api('/api/me/stats')]);
      const filled = days.filter(d => d.mood);
      const moodCounts = {};
      filled.forEach(d => { moodCounts[d.mood] = (moodCounts[d.mood] || 0) + 1; });
      const dominant = Object.entries(moodCounts).sort((a, b) => b[1] - a[1])[0];
      const cells = days.map(d => {
        const em = d.mood && window.MOOD_EMOJI[d.mood] ? window.MOOD_EMOJI[d.mood] : '';
        return `<div class="mht-c ${d.mood ? 'has' : ''}" title="${d.label}${d.mood ? ' · ' + d.mood : ''}">${em}</div>`;
      }).join('');
      const insightLine = filled.length === 0
        ? 'Mulai tandai mood di tulisanmu. Polanya bakal kelihatan setelah beberapa hari.'
        : dominant ? `Mood paling sering 30 hari ini: ${window.MOOD_EMOJI[dominant[0]]} <b>${dominant[0]}</b> (${dominant[1]} hari)` : '';
      done(`
        <div class="ins-stat">
          <div class="ins-c"><div class="ins-n">${stats.this_month}</div><div class="ins-l">Entri bulan ini</div></div>
          <div class="ins-c"><div class="ins-n">${filled.length}</div><div class="ins-l">Hari ber-mood</div></div>
          <div class="ins-c"><div class="ins-n">${Object.keys(moodCounts).length}</div><div class="ins-l">Variasi mood</div></div>
        </div>
        <div class="mht">
          <div class="mht-h">30 hari terakhir</div>
          <div class="mht-grid">${cells}</div>
          ${insightLine ? `<div class="ins-line">${insightLine}</div>` : ''}
          <div class="mht-leg">${Object.entries(window.MOOD_EMOJI).map(([k, v]) => `<span>${v} ${k}</span>`).join('')}</div>
        </div>`);
    }
  } catch {
    done('<div class="empty"><span>⚠️</span>Gagal memuat</div>');
  }
}
window.switchPT = switchPT;

// ── AKTIVITAS (notifications) ──
async function renderNotifs() {
  const el = document.getElementById('nl');
  if (!el) return;
  if (!el.children.length) el.innerHTML = '<div class="sk"><div class="sk-bar"></div><div class="sk-bar"></div><div class="sk-bar"></div></div>';
  try {
    const events = await api('/api/notifications');
    if (!events.length) {
      el.innerHTML = '<div class="empty"><span>🔔</span>Belum ada kabar baru</div>';
      return;
    }
    const verbs = { like: 'menyukai tulisanmu', comment: 'berkomentar di tulisanmu', dm: 'mengirim pesan' };
    const ems = { like: '❤️', comment: '💬', dm: '✉️' };
    el.innerHTML = events.map(e => {
      const click = e.kind === 'dm'
        ? `switchPage('dm');setTimeout(()=>openDmThread('${esc(e.username)}'),150)`
        : `openPost(${e.post_id})`;
      return `<div class="nf-i" onclick="${click}">
        <div class="av-wrap"><div class="av" style="background:${esc(e.color)}">${esc(e.avatar)}</div></div>
        <div class="nf-i-c">
          <div class="nf-i-h"><span class="nf-kind ${e.kind}">${ems[e.kind]}</span><b>${esc(e.display)}</b> ${verbs[e.kind]}</div>
          ${e.content ? `<div class="nf-i-p">“${esc(e.content)}”</div>` : ''}
          ${e.post_preview ? `<div class="nf-i-p muted">→ ${esc(e.post_preview)}</div>` : ''}
        </div>
        <div class="nf-i-t">${tsSpan(e.created_at)}</div>
      </div>`;
    }).join('');
  } catch {
    el.innerHTML = '<div class="empty"><span>⚠️</span>Gagal memuat</div>';
  }
}
window.renderNotifs = renderNotifs;

// ── JURNAL (archive of your own entries, server-side search + paging) ──
const ID_MONTHS = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
  'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
const journal = { q: '', items: [], cursor: null, done: false, busy: false, seq: 0 };

function arcEntryHTML(p) {
  const d = new Date((p.created_at || 0) * 1000);
  const mon = ID_MONTHS[d.getMonth()].slice(0, 3);
  const moodEm = p.mood && window.MOOD_EMOJI[p.mood] ? window.MOOD_EMOJI[p.mood] : '';
  const preview = p.content ? esc(p.content) : (p.has_image ? 'Foto' : '—');
  return `<div class="arc-i" onclick="openPost(${p.id})">
    <div class="arc-d"><span>${d.getDate()} ${mon} · ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}</span>${moodEm ? `<span>· ${moodEm}</span>` : ''}${p.post_type === 'gratitude' ? '<span>· 🙏</span>' : ''}${p.has_image ? '<span>· 📷</span>' : ''}</div>
    <div class="arc-t">${preview}</div>
  </div>`;
}

function renderJournal() {
  const out = document.getElementById('searchResults');
  if (!out) return;
  if (!journal.items.length) {
    out.innerHTML = journal.busy ? '<div class="sk"><div class="sk-bar"></div><div class="sk-bar"></div></div>'
      : journal.q
        ? '<div class="empty"><span>🔎</span>Nggak ada entri yang cocok</div>'
        : '<div class="empty"><span>🪶</span>Jurnalmu masih kosong.<div class="empty-tip">Tiap yang kamu tulis bakal ngumpul di sini, biar gampang dibaca lagi nanti.</div></div>';
    return;
  }
  let html = '', lastKey = '';
  journal.items.forEach(p => {
    const d = new Date((p.created_at || 0) * 1000);
    const key = ID_MONTHS[d.getMonth()] + ' ' + d.getFullYear();
    if (key !== lastKey) { html += `<div class="arc-mon">${key}</div>`; lastKey = key; }
    html += arcEntryHTML(p);
  });
  if (!journal.done) html += `<div class="feed-foot"><button class="linkbtn" onclick="loadJournal(null, true)">${journal.busy ? 'Memuat…' : 'Muat lebih banyak'}</button></div>`;
  out.innerHTML = html;
}

async function loadJournal(q = null, more = false) {
  if (q !== null) journal.q = q;
  if (!more) { journal.items = []; journal.cursor = null; journal.done = false; }
  if (journal.busy && more) return;
  const seq = ++journal.seq;
  journal.busy = true;
  renderJournal();
  try {
    let url = '/api/posts?mine=1&comments=0&limit=40';
    if (journal.q) url += '&q=' + encodeURIComponent(journal.q);
    if (more && journal.cursor) url += '&before=' + journal.cursor;
    const posts = await api(url);
    if (seq !== journal.seq) return;
    journal.items = journal.items.concat(posts);
    journal.cursor = posts.length ? posts[posts.length - 1].created_at : journal.cursor;
    journal.done = posts.length < 40;
  } catch {
    if (seq === journal.seq) showToast('Gagal memuat jurnal');
  } finally {
    if (seq === journal.seq) { journal.busy = false; renderJournal(); }
  }
}
window.loadJournal = loadJournal;
window.renderArsip = () => loadJournal();  // nama lama, dipakai di tempat lain

let searchTimer = null;
function doSearch(v) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadJournal(v.trim()), 280);
}
window.doSearch = doSearch;
