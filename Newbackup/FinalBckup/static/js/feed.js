// ===========================================================================
// Aura Social — feed.js
// Owns: feed rendering, post card, likes, comments, persona list, search, notifications
// Depends on: main.js (window.aura, esc, showToast)
// ===========================================================================

async function loadFeed() {
  try {
    const r = await fetch('/api/posts');
    window.aura.allPosts = await r.json();
    // Sync liked + bookmarked sets from server state
    window.aura.liked = new Set(window.aura.allPosts.filter(p => p.is_liked).map(p => p.id));
    window.aura.bookmarked = new Set(window.aura.allPosts.filter(p => p.bookmarked).map(p => p.id));
    renderFeed(window.aura.allPosts);
    const myPosts = window.aura.allPosts.filter(p => p.username === 'me');
    document.getElementById('sp').textContent = myPosts.length;
    renderPG(window.aura.allPosts);
  } catch {}
}
window.loadFeed = loadFeed;

function renderFeed(posts) {
  const el = document.getElementById('feed');
  if (!posts.length) {
    el.innerHTML = '<div class="empty"><span>🌱</span>Jadilah yang pertama posting!</div>';
    return;
  }
  el.innerHTML = posts.map((p, i) => pCard(p, i)).join('');
}

function pCard(p, i) {
  const lk = p.is_liked || window.aura.liked.has(p.id);
  const bm = p.bookmarked || window.aura.bookmarked.has(p.id);
  const isAI = p.username !== 'me';
  let m = '';
  // Repost wrapper — show original embedded
  if (p.original) {
    const o = p.original;
    let oImg = o.has_image ? `<img src="/api/posts/${o.id}/image" class="rp-img">` : '';
    m += `<div class="rp-w" onclick="showToast('Original post')">
      <div class="rp-h">
        <div class="av" style="background:${o.color}">${o.avatar}</div>
        <div class="rp-u">${esc(o.display)}</div>
        <div class="rp-t">· ${o.time_ago}</div>
      </div>
      ${o.content ? `<div class="rp-c">${esc(o.content)}</div>` : ''}
      ${oImg}
    </div>`;
  }
  if (p.has_image) {
    m += `<img src="/api/posts/${p.id}/image" class="pimg" loading="lazy" alt="">`;
  }
  if (p.content) m += `<div class="pbody ${p.has_image ? 'cap' : ''}">${esc(p.content)}</div>`;
  const cms = p.comments.map(c => `
    <div class="ci">
      <div class="cav" style="background:${c.color}">${c.avatar}</div>
      <div class="cb">
        <span class="cu" onclick="${c.is_ai ? `openProfile('${c.username}')` : 'void(0)'}">${esc(c.display)}</span>${c.is_ai ? '<span class="ait">AI</span>' : ''}
        <span class="ct">${esc(c.content)}</span>
        <div class="ctm">${c.time_ago}</div>
      </div>
    </div>`).join('');
  return `<div class="pc" style="animation-delay:${i * .04}s" id="pc${p.id}">
    <div class="ph">
      <div class="av" style="background:${p.color}">${p.avatar}</div>
      <div class="pm">
        <div class="pu" onclick="${isAI ? `openProfile('${p.username}')` : 'void(0)'}">${esc(p.display)}</div>
        <div class="pt">${p.time_ago}${p.mood && window.MOOD_EMOJI[p.mood] ? ` · <span class="pmood" title="${p.mood}">${window.MOOD_EMOJI[p.mood]}</span>` : ''}${p.repost_of ? ' · 🔁' : ''}${isAI ? ' · <span class="ait">AI</span>' : ''}</div>
      </div>
      <div style="color:var(--mu);cursor:pointer" onclick="showToast('···')">···</div>
    </div>
    ${m}
    <div class="pacts">
      <button class="ab ${lk ? 'liked' : ''}" onclick="doLike(${p.id},this)">
        <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
        <span id="lc${p.id}">${p.likes}</span>
      </button>
      <button class="ab" onclick="tgCm(${p.id})">
        <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span>${p.comment_count}</span>
      </button>
      <button class="ab" onclick="openRepost(${p.id})">
        <svg viewBox="0 0 24 24"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
      </button>
      <div class="sp"></div>
      <button class="ab ${bm ? 'saved' : ''}" onclick="doBookmark(${p.id},this)">
        <svg viewBox="0 0 24 24"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
      </button>
    </div>
    <div id="cm${p.id}" style="display:${p.comments.length ? 'block' : 'none'}">
      <div class="cw">
        <div id="cml${p.id}">${cms}</div>
        <div class="cir">
          <input class="cinp" id="ci${p.id}" placeholder="Tulis komentar..." onkeydown="if(event.key==='Enter')doCm(${p.id})">
          <button class="csend" onclick="doCm(${p.id})">➤</button>
        </div>
      </div>
    </div>
  </div>`;
}

function tgCm(id) {
  const el = document.getElementById('cm' + id);
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
  if (el.style.display === 'block') document.getElementById('ci' + id)?.focus();
}
window.tgCm = tgCm;

async function doLike(id, btn) {
  const r = await fetch(`/api/posts/${id}/like`, { method: 'POST' });
  const d = await r.json();
  btn.classList.toggle('liked', d.liked);
  document.getElementById('lc' + id).textContent = d.likes;
  d.liked ? window.aura.liked.add(id) : window.aura.liked.delete(id);
  if (d.liked) {
    btn.style.transform = 'scale(1.3)';
    setTimeout(() => btn.style.transform = '', 200);
  }
}
window.doLike = doLike;

async function doBookmark(id, btn) {
  const r = await fetch(`/api/posts/${id}/bookmark`, { method: 'POST' });
  const d = await r.json();
  btn.classList.toggle('saved', d.bookmarked);
  d.bookmarked ? window.aura.bookmarked.add(id) : window.aura.bookmarked.delete(id);
  showToast(d.bookmarked ? '🔖 Disimpan!' : '🗑️ Hapus');
}
window.doBookmark = doBookmark;

function openRepost(id) {
  const p = window.aura.allPosts.find(x => x.id === id);
  if (!p) return;
  window.aura.repostOf = id;
  document.getElementById('rpExtra').value = '';
  // Render original preview
  const origImg = p.has_image ? `<img src="/api/posts/${p.id}/image" class="rp-img">` : '';
  document.getElementById('rpOrig').innerHTML = `
    <div class="rp-orig-h">
      <div class="av" style="background:${p.color}">${p.avatar}</div>
      <div style="font-size:12px;font-weight:600">${esc(p.display)}</div>
    </div>
    <div class="rp-orig-c">${esc(p.content || '')}</div>
    ${origImg}
  `;
  document.getElementById('repostModal').classList.add('open');
}
window.openRepost = openRepost;

function closeRepost(e) {
  if (!e || e.target === document.getElementById('repostModal')) {
    document.getElementById('repostModal').classList.remove('open');
    window.aura.repostOf = null;
  }
}
window.closeRepost = closeRepost;

async function submitRepost() {
  const id = window.aura.repostOf;
  if (!id) return;
  const extra = document.getElementById('rpExtra').value.trim();
  try {
    const r = await fetch(`/api/posts/${id}/repost`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: extra }),
    });
    if (r.ok) {
      closeRepost();
      showToast('🔁 Reposted!');
      loadFeed();
    } else {
      showToast('❌ Gagal');
    }
  } catch {
    showToast('❌ Network error');
  }
}
window.submitRepost = submitRepost;

async function doCm(id) {
  const inp = document.getElementById('ci' + id);
  const txt = inp.value.trim();
  if (!txt) return;
  inp.value = '';
  const list = document.getElementById('cml' + id);
  list.insertAdjacentHTML('beforeend', `
    <div class="ci"><div class="cav" style="background:linear-gradient(135deg,var(--acc),var(--a2))">K</div>
    <div class="cb"><span class="cu">Kamu 👤</span><span class="ct">${esc(txt)}</span><div class="ctm">Baru saja</div></div></div>`);
  await fetch(`/api/posts/${id}/comment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: txt }),
  });
}
window.doCm = doCm;

// ── PROFILE GRID (own profile) ──
function renderPG(posts) {
  const mine = posts.filter(p => p.username === 'me');
  const imgPosts = mine.filter(p => p.has_image).slice(0, 9);
  const el = document.getElementById('pg');
  if (!imgPosts.length) {
    el.innerHTML = '<div style="padding:40px;text-align:center;color:var(--mu);grid-column:span 3">Belum ada foto</div>';
    return;
  }
  el.innerHTML = imgPosts.map(p => `<div class="pgi"><img src="/api/posts/${p.id}/image" loading="lazy"></div>`).join('');
}

function switchPT(el, t) {
  document.querySelectorAll('#page-profile .ptab').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  const c = document.getElementById('pc2');
  const allPosts = window.aura.allPosts;
  if (t === 'grid') {
    const mine = allPosts.filter(p => p.username === 'me' && p.has_image).slice(0, 9);
    c.innerHTML = '<div class="pgrid" id="pg">' +
      (mine.length
        ? mine.map(p => `<div class="pgi"><img src="/api/posts/${p.id}/image" loading="lazy"></div>`).join('')
        : '<div style="padding:40px;text-align:center;color:var(--mu);grid-column:span 3">Belum ada foto</div>') +
      '</div>';
  } else if (t === 'tweets') {
    const mine = allPosts.filter(p => p.username === 'me' && !p.has_image);
    c.innerHTML = mine.length
      ? mine.map(p => `<div style="padding:14px 18px;border-bottom:1px solid var(--bd);font-size:14px;line-height:1.6">${esc(p.content || '')}<div style="font-size:11px;color:var(--mu);margin-top:4px">${p.time_ago}${p.mood && window.MOOD_EMOJI[p.mood] ? ' · ' + window.MOOD_EMOJI[p.mood] : ''}</div></div>`).join('')
      : '<div class="empty"><span>💬</span>Belum ada tweet</div>';
  } else if (t === 'liked') {
    c.innerHTML = '<div class="empty"><span>❤️</span>Loading...</div>';
    fetch('/api/me/liked').then(r => r.json()).then(posts => {
      document.getElementById('likedCount').textContent = posts.length;
      if (!posts.length) {
        c.innerHTML = '<div class="empty"><span>❤️</span>Belum ada post yg di-like</div>';
        return;
      }
      c.innerHTML = posts.map(p => `<div style="padding:13px 18px;border-bottom:1px solid var(--bd);display:flex;gap:11px;align-items:flex-start">
        <div class="av" style="background:${p.color};width:36px;height:36px;font-size:13px">${p.avatar}</div>
        <div style="flex:1;min-width:0">
          <div style="font-size:13px;font-weight:600">${esc(p.display)}</div>
          <div style="font-size:11px;color:var(--mu);margin-bottom:5px">${p.time_ago}${p.mood && window.MOOD_EMOJI[p.mood] ? ' · ' + window.MOOD_EMOJI[p.mood] : ''}</div>
          ${p.content ? `<div style="font-size:13.5px;line-height:1.5">${esc(p.content)}</div>` : ''}
          ${p.has_image ? `<img src="/api/posts/${p.id}/image" style="width:100%;border-radius:8px;margin-top:6px;max-height:240px;object-fit:cover">` : ''}
        </div>
      </div>`).join('');
    });
  } else if (t === 'saved') {
    c.innerHTML = '<div class="empty"><span>🔖</span>Loading...</div>';
    fetch('/api/me/bookmarks').then(r => r.json()).then(posts => {
      if (!posts.length) {
        c.innerHTML = '<div class="empty"><span>🔖</span>Belum ada post yg disimpan</div>';
        return;
      }
      c.innerHTML = posts.map(p => `<div style="padding:13px 18px;border-bottom:1px solid var(--bd);display:flex;gap:11px;align-items:flex-start">
        <div class="av" style="background:${p.color};width:36px;height:36px;font-size:13px">${p.avatar}</div>
        <div style="flex:1;min-width:0">
          <div style="font-size:13px;font-weight:600">${esc(p.display)}</div>
          <div style="font-size:11px;color:var(--mu);margin-bottom:5px">${p.time_ago}${p.mood && window.MOOD_EMOJI[p.mood] ? ' · ' + window.MOOD_EMOJI[p.mood] : ''}</div>
          ${p.content ? `<div style="font-size:13.5px;line-height:1.5">${esc(p.content)}</div>` : ''}
          ${p.has_image ? `<img src="/api/posts/${p.id}/image" style="width:100%;border-radius:8px;margin-top:6px;max-height:240px;object-fit:cover">` : ''}
        </div>
      </div>`).join('');
    });
  } else if (t === 'mood') {
    c.innerHTML = '<div class="empty"><span>📊</span>Loading...</div>';
    fetch('/api/me/mood-timeline').then(r => r.json()).then(days => {
      const cells = days.map(d => {
        const em = d.mood && window.MOOD_EMOJI[d.mood] ? window.MOOD_EMOJI[d.mood] : '';
        return `<div class="mht-c ${d.mood ? 'has' : ''}" title="${d.label}${d.mood ? ' · ' + d.mood : ''}">${em}</div>`;
      }).join('');
      const legend = Object.entries(window.MOOD_EMOJI).map(([k, v]) => `<span>${v} ${k}</span>`).join('');
      c.innerHTML = `<div class="mht">
        <div class="mht-h">📊 Mood 30 Hari Terakhir</div>
        <div class="mht-grid">${cells}</div>
        <div class="mht-leg">${legend}</div>
      </div>`;
    });
  }
}
window.switchPT = switchPT;

// ── PERSONAS LIST + SEARCH + NOTIFICATIONS ──
function renderPL() {
  document.getElementById('pl').innerHTML = window.aura.personas.map(p => `
    <div class="sit">
      <div class="sav2" style="background:${p.color}" onclick="openProfile('${p.username}')">${p.avatar}</div>
      <div class="sm" style="cursor:pointer" onclick="openProfile('${p.username}')">
        <div class="sn">${p.display}</div>
        <div class="ss"><span class="mono">${p.text_model}</span></div></div>
      <button class="fb" onclick="tgFollow(this)">Follow</button>
    </div>`).join('');
}
window.renderPL = renderPL;

function renderNotifs() {
  const acts = ['menyukai postinganmu', 'mengomentari fotomu', 'me-repost tweetmu', 'mulai mengikutimu', 'melihat storymu'];
  const ems = ['❤️', '💬', '🔁', '✨', '👀'];
  document.getElementById('nl').innerHTML = window.aura.personas.slice(0, 5).map((p, i) => `
    <div class="sit">
      <div class="sav2" style="background:${p.color}" onclick="openProfile('${p.username}')">${p.avatar}</div>
      <div class="sm"><div class="sn">${p.display} <span style="font-weight:400;color:var(--mu)">${acts[i]}</span></div>
        <div class="ss">${(i + 1) * 7} menit lalu</div></div>
      <span style="font-size:18px">${ems[i]}</span>
    </div>`).join('');
}
window.renderNotifs = renderNotifs;

function doSearch(v) {
  if (!v.trim()) {
    renderPL();
    return;
  }
  const f = window.aura.personas.filter(p =>
    p.username.includes(v.toLowerCase()) ||
    p.display.toLowerCase().includes(v.toLowerCase())
  );
  document.getElementById('pl').innerHTML = f.map(p => `
    <div class="sit">
      <div class="sav2" style="background:${p.color}" onclick="openProfile('${p.username}')">${p.avatar}</div>
      <div class="sm" style="cursor:pointer" onclick="openProfile('${p.username}')">
        <div class="sn">${p.display}</div><div class="ss">${p.text_model}</div></div>
      <button class="fb" onclick="tgFollow(this)">Follow</button>
    </div>`).join('') || '<div style="padding:20px;color:var(--mu)">Tidak ditemukan</div>';
}
window.doSearch = doSearch;

function tgFollow(b) {
  b.classList.toggle('on');
  b.textContent = b.classList.contains('on') ? 'Following' : 'Follow';
  showToast(b.classList.contains('on') ? '✅ Following!' : '👋 Unfollow');
}
window.tgFollow = tgFollow;
