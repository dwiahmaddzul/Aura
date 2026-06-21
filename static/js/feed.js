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
    const now = new Date();
    const tm = myPosts.filter(p => {
      const d = new Date((p.created_at || 0) * 1000);
      return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
    }).length;
    const tmEl = document.getElementById('thisMonth');
    if (tmEl) tmEl.textContent = tm;
    renderPG(window.aura.allPosts);
  } catch {}
}
window.loadFeed = loadFeed;

function renderFeed(posts) {
  const el = document.getElementById('feed');
  if (!posts.length) {
    el.innerHTML = '<div class="empty"><span>🌱</span>Feed-mu masih kosong.<div class="empty-tip">Mulai cerita apa aja — sekecil apapun, ada yg bakal denger.</div></div>';
    return;
  }
  el.innerHTML = posts.map((p, i) => pCard(p, i)).join('');
}
window.renderFeed = renderFeed;

function pCard(p, i) {
  const lk = p.is_liked || window.aura.liked.has(p.id);
  const bm = p.bookmarked || window.aura.bookmarked.has(p.id);
  const isAI = p.username !== 'me';
  const isGrat = p.post_type === 'gratitude';
  let m = isGrat ? '<div class="grat-tag">🙏 Catatan syukur</div>' : '';
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
  const cms = buildComments(p);
  return `<div class="pc${isGrat ? ' grat' : ''}" style="animation-delay:${i * .04}s" id="pc${p.id}">
    <div class="ph">
      <div class="av" style="background:${p.color}">${p.avatar}</div>
      <div class="pm">
        <div class="pu" onclick="${isAI ? `openProfile('${p.username}')` : 'void(0)'}">${esc(p.display)}</div>
        <div class="pt">${p.time_ago}${p.mood && window.MOOD_EMOJI[p.mood] ? ` · <span class="pmood" title="${p.mood}">${window.MOOD_EMOJI[p.mood]}</span>` : ''}${p.repost_of ? ' · 🔁' : ''}</div>
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
          <button class="csend" onclick="doCm(${p.id})" aria-label="Kirim"><svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg></button>
        </div>
      </div>
    </div>
  </div>`;
}

// ── Threaded comments (1 level) ──
function cmtRow(c, postId, root, isReply) {
  return `<div class="ci${isReply ? ' ci-reply' : ''}">
    <div class="cav" style="background:${c.color}">${c.avatar}</div>
    <div class="cb">
      <span class="cu" onclick="${c.is_ai ? `openProfile('${c.username}')` : 'void(0)'}">${esc(c.display)}</span>
      <span class="ct">${esc(c.content)}</span>
      <div class="ctm">${c.time_ago} · <button class="creply" onclick="replyTo(${postId},${root},this)">Balas</button></div>
    </div>
  </div>`;
}

function buildComments(p) {
  const tops = p.comments.filter(c => !c.parent_id);
  const byParent = {};
  p.comments.filter(c => c.parent_id).forEach(c => {
    (byParent[c.parent_id] = byParent[c.parent_id] || []).push(c);
  });
  return tops.map(t => {
    const reps = (byParent[t.id] || []).map(r => cmtRow(r, p.id, t.id, true)).join('');
    return `<div class="cthread" id="cth${p.id}_${t.id}">${cmtRow(t, p.id, t.id, false)}${reps}</div>`;
  }).join('');
}
window.buildComments = buildComments;

function replyTo(postId, root, btn) {
  const inp = document.getElementById('ci' + postId);
  if (!inp) return;
  const name = btn.closest('.ci').querySelector('.cu').textContent;
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
    chip.onclick = () => cancelReply(postId);
    bar.insertBefore(chip, inp);
  }
}
window.replyTo = replyTo;

function cancelReply(postId) {
  const inp = document.getElementById('ci' + postId);
  if (inp) { delete inp.dataset.parent; inp.placeholder = 'Tulis komentar...'; }
  document.getElementById('rc' + postId)?.remove();
}
window.cancelReply = cancelReply;

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

// Repost was removed (doesn't fit a single-user diary). Existing reposts from
// the backend still render read-only via the .rp-w block in pCard().

async function doCm(id) {
  const inp = document.getElementById('ci' + id);
  const txt = inp.value.trim();
  if (!txt) return;
  const parent = inp.dataset.parent ? parseInt(inp.dataset.parent) : null;
  inp.value = '';
  const meAv = (window.aura.myProfile && window.aura.myProfile.avatar) || 'K';
  const meName = (window.aura.myProfile && window.aura.myProfile.display_name) || 'Kamu';
  const row = `<div class="ci${parent ? ' ci-reply' : ''}">
    <div class="cav av-me">${esc(meAv)}</div>
    <div class="cb"><span class="cu">${esc(meName)}</span><span class="ct">${esc(txt)}</span><div class="ctm">Baru saja</div></div></div>`;
  if (parent) {
    const th = document.getElementById('cth' + id + '_' + parent);
    (th || document.getElementById('cml' + id)).insertAdjacentHTML('beforeend', row);
  } else {
    document.getElementById('cml' + id).insertAdjacentHTML('beforeend', `<div class="cthread">${row}</div>`);
  }
  cancelReply(id);
  await fetch(`/api/posts/${id}/comment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: txt, parent_id: parent }),
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
      : '<div class="empty"><span>💬</span>Belum ada cerita pendek di sini</div>';
  } else if (t === 'liked') {
    c.innerHTML = '<div class="sk"><div class="sk-bar"></div><div class="sk-bar"></div></div>';
    fetch('/api/me/liked').then(r => r.json()).then(posts => {
      const lcEl = document.getElementById('likedCount');
      if (lcEl) lcEl.textContent = posts.length;
      if (!posts.length) {
        c.innerHTML = '<div class="empty"><span>❤️</span>Belum ada yang lo sukai</div>';
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
    c.innerHTML = '<div class="sk"><div class="sk-bar"></div><div class="sk-bar"></div></div>';
    fetch('/api/me/bookmarks').then(r => r.json()).then(posts => {
      if (!posts.length) {
        c.innerHTML = '<div class="empty"><span>🔖</span>Belum ada yang lo simpan</div>';
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
    c.innerHTML = '<div class="sk sk-insights"><div class="sk-bar"></div><div class="sk-bar"></div><div class="sk-grid"></div></div>';
    fetch('/api/me/mood-timeline').then(r => r.json()).then(days => {
      // Stats
      const filled = days.filter(d => d.mood);
      const moodCounts = {};
      filled.forEach(d => { moodCounts[d.mood] = (moodCounts[d.mood] || 0) + 1; });
      const dominant = Object.entries(moodCounts).sort((a, b) => b[1] - a[1])[0];
      const myPosts30 = window.aura.allPosts.filter(p =>
        p.username === 'me' && (Date.now() / 1000 - p.created_at) < 30 * 86400
      );

      const cells = days.map(d => {
        const em = d.mood && window.MOOD_EMOJI[d.mood] ? window.MOOD_EMOJI[d.mood] : '';
        return `<div class="mht-c ${d.mood ? 'has' : ''}" title="${d.label}${d.mood ? ' · ' + d.mood : ''}">${em}</div>`;
      }).join('');

      const insightLine = filled.length === 0
        ? 'Mulai tag mood di post-mu — pola bakal muncul setelah beberapa hari.'
        : dominant
          ? `Mood paling sering bulan ini: ${window.MOOD_EMOJI[dominant[0]]} <b>${dominant[0]}</b> (${dominant[1]} hari)`
          : '';

      c.innerHTML = `
        <div class="ins-stat">
          <div class="ins-c"><div class="ins-n">${myPosts30.length}</div><div class="ins-l">Post 30 hari</div></div>
          <div class="ins-c"><div class="ins-n">${filled.length}</div><div class="ins-l">Hari aktif</div></div>
          <div class="ins-c"><div class="ins-n">${moodCounts ? Object.keys(moodCounts).length : 0}</div><div class="ins-l">Variasi mood</div></div>
        </div>
        <div class="mht">
          <div class="mht-h">📅 30 Hari Terakhir</div>
          <div class="mht-grid">${cells}</div>
          ${insightLine ? `<div class="ins-line">${insightLine}</div>` : ''}
          <div class="mht-leg">${Object.entries(window.MOOD_EMOJI).map(([k, v]) => `<span>${v} ${k}</span>`).join('')}</div>
        </div>`;
    }).catch(() => {
      c.innerHTML = '<div class="empty"><span>⚠️</span>Gagal load insights</div>';
    });
  }
}
window.switchPT = switchPT;

// ── ACTIVITY (notifications) ──
async function renderNotifs() {
  const el = document.getElementById('nl');
  if (!el) return;
  el.innerHTML = '<div class="sk"><div class="sk-bar"></div><div class="sk-bar"></div><div class="sk-bar"></div></div>';
  try {
    const r = await fetch('/api/notifications');
    const events = await r.json();
    if (!events.length) {
      el.innerHTML = '<div class="empty"><span>🔔</span>Belum ada kabar baru</div>';
      // Clear topbar pip
      const pip = document.querySelector('.npip');
      if (pip) pip.style.display = 'none';
      return;
    }
    const verbs = {
      like: 'me-like postinganmu',
      comment: 'komen di postinganmu',
      dm: 'kirim pesan',
    };
    const ems = { like: '❤️', comment: '💬', dm: '✉️' };
    el.innerHTML = events.map(e => {
      const click = e.kind === 'dm'
        ? `switchPage('dm');setTimeout(()=>openDmThread('${e.username}'),200)`
        : `switchPage('home');setTimeout(()=>document.getElementById('pc${e.post_id}')?.scrollIntoView({behavior:'smooth'}),200)`;
      return `<div class="nf-i" onclick="${click}">
        <div class="av-wrap">
          <div class="av" style="background:${e.color}">${e.avatar}</div>
        </div>
        <div class="nf-i-c">
          <div class="nf-i-h"><span class="nf-kind ${e.kind}">${ems[e.kind]} ${e.kind}</span><b>${esc(e.display)}</b> ${verbs[e.kind]}</div>
          ${e.content ? `<div class="nf-i-p">"${esc(e.content)}"</div>` : ''}
          ${e.post_preview ? `<div class="nf-i-p" style="color:var(--mu);font-style:italic">→ ${esc(e.post_preview)}</div>` : ''}
        </div>
        <div class="nf-i-t">${e.time_ago}</div>
      </div>`;
    }).join('');
  } catch {
    el.innerHTML = '<div class="empty"><span>⚠️</span>Gagal load</div>';
  }
}
window.renderNotifs = renderNotifs;

// ── JURNAL (archive of your own entries) ──
const ID_MONTHS = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
  'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];

function arcEntryHTML(p) {
  const d = new Date((p.created_at || 0) * 1000);
  const mon = ID_MONTHS[d.getMonth()].slice(0, 3);
  const moodEm = p.mood && window.MOOD_EMOJI[p.mood] ? window.MOOD_EMOJI[p.mood] : '';
  const preview = p.content ? esc(p.content) : (p.has_image ? 'Foto' : '—');
  const go = `switchPage('home');setTimeout(()=>document.getElementById('pc${p.id}')?.scrollIntoView({behavior:'smooth',block:'center'}),250)`;
  return `<div class="arc-i" onclick="${go}">
    <div class="arc-d"><span>${d.getDate()} ${mon}</span>${moodEm ? `<span>· ${moodEm}</span>` : ''}${p.post_type === 'gratitude' ? '<span>· 🙏</span>' : ''}${p.has_image && p.content ? '<span>· 📷</span>' : ''}</div>
    <div class="arc-t">${preview}</div>
  </div>`;
}

function renderArsip(filter) {
  const out = document.getElementById('searchResults');
  if (!out) return;
  let mine = (window.aura.allPosts || []).filter(p => p.username === 'me');
  if (filter) {
    const f = filter.toLowerCase();
    mine = mine.filter(p => (p.content || '').toLowerCase().includes(f));
  }
  mine.sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
  if (!mine.length) {
    out.innerHTML = filter
      ? '<div class="empty"><span>🔎</span>Nggak ada entri yang cocok</div>'
      : '<div class="empty"><span>🪶</span>Jurnalmu masih kosong.<div class="empty-tip">Tiap yang kamu tulis bakal ngumpul di sini — biar gampang dibaca lagi nanti.</div></div>';
    return;
  }
  let html = '', lastKey = '';
  mine.forEach(p => {
    const d = new Date((p.created_at || 0) * 1000);
    const key = ID_MONTHS[d.getMonth()] + ' ' + d.getFullYear();
    if (key !== lastKey) { html += `<div class="arc-mon">${key}</div>`; lastKey = key; }
    html += arcEntryHTML(p);
  });
  out.innerHTML = html;
}
window.renderArsip = renderArsip;

let searchTimer = null;
function doSearch(v) {
  clearTimeout(searchTimer);
  const q = v.trim();
  if (!q) { renderArsip(); return; }
  searchTimer = setTimeout(() => renderArsip(q), 200);
}
window.doSearch = doSearch;

function tgFollow(b) {
  b.classList.toggle('on');
  b.textContent = b.classList.contains('on') ? 'Following' : 'Follow';
  showToast(b.classList.contains('on') ? '✅ Following!' : '👋 Unfollow');
}
window.tgFollow = tgFollow;
