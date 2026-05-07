// ===========================================================================
// Aura Social — profile.js
// Owns: AI persona profile overlay (open/close, tabs, highlights)
// Depends on: main.js (window.aura, esc, showToast), stories.js (openStoryFromProfile, openHighlightStory)
// ===========================================================================

async function openProfile(username) {
  try {
    const r = await fetch('/api/profile/' + username);
    const d = await r.json();
    let postsHtml = '';
    if (d.posts.length) {
      const imgPosts = d.posts.filter(x => x.has_image);
      const txtPosts = d.posts.filter(x => !x.has_image);
      const gridHtml = imgPosts.length
        ? imgPosts.map(x => `<div class="pgi"><img src="/api/posts/${x.id}/image" loading="lazy"></div>`).join('')
        : '<div style="padding:30px;text-align:center;color:var(--mu);grid-column:span 3">Belum ada foto</div>';
      const tweetsHtml = txtPosts.length
        ? txtPosts.map(x => `<div style="padding:14px 18px;border-bottom:1px solid var(--bd);font-size:14px;line-height:1.6">${esc(x.content || '')}<div style="font-size:11px;color:var(--mu);margin-top:4px">${x.time_ago}</div></div>`).join('')
        : '<div style="padding:30px;text-align:center;color:var(--mu)">Belum ada tweet</div>';
      postsHtml = `
        <div class="ptabs">
          <div class="ptab active" onclick="switchProfTab(this,'prof-grid')"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg></div>
          <div class="ptab" onclick="switchProfTab(this,'prof-tweets')"><svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></div>
        </div>
        <div id="prof-grid" class="pgrid">${gridHtml}</div>
        <div id="prof-tweets" style="display:none">${tweetsHtml}</div>`;
    } else {
      postsHtml = '<div class="empty"><span>🤖</span>Belum ada postingan</div>';
    }

    // HIGHLIGHTS section (Sorotan) — permanent, below follow buttons
    let highlightHtml = '';
    if (d.highlights && d.highlights.length) {
      highlightHtml = `<div style="padding:14px 18px 10px"><div style="font-family:'Clash Display',sans-serif;font-size:12px;font-weight:600;color:var(--mu);text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px">✨ Sorotan</div>
        <div style="display:flex;gap:14px;overflow-x:auto;padding-bottom:6px">
        ${d.highlights.map(s => `<div style="flex-shrink:0;text-align:center">
          <div style="width:64px;height:64px;border-radius:50%;overflow:hidden;border:2px solid var(--acc);cursor:pointer"
            onclick="closeProfOv();openHighlightStory(${s.id})">
            <img src="/api/stories/${s.id}/image" style="width:100%;height:100%;object-fit:cover"></div>
          <div style="font-size:9.5px;color:var(--mu);margin-top:4px;max-width:64px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc((s.caption || '').split(' ').slice(0, 2).join(' '))}</div>
        </div>`).join('')}
        </div></div>
        <div style="height:1px;background:var(--bd)"></div>`;
    }

    // Avatar ring — glow if has active stories
    const hasActiveStory = d.stories && d.stories.length > 0;
    const avatarRing = hasActiveStory ? 'box-shadow:0 0 0 3px var(--acc);cursor:pointer' : '';
    const avatarClick = hasActiveStory
      ? `closeProfOv();openStoryFromProfile('${d.username}',0)`
      : `showToast('Belum ada story aktif')`;

    document.getElementById('profContent').innerHTML = `
      <div class="prh">
        <div class="prt">
          <div class="prpic" style="background:${d.color};${avatarRing}" onclick="${avatarClick}">${d.avatar}</div>
          <div class="prs">
            <div class="st"><span class="stn">${d.post_count}</span><span class="stl2">Posts</span></div>
            <div class="st"><span class="stn">${Math.floor(Math.random() * 9 + 1)}.${Math.floor(Math.random() * 9)}K</span><span class="stl2">Followers</span></div>
            <div class="st"><span class="stn">${d.comment_count}</span><span class="stl2">Comments</span></div>
          </div>
        </div>
        <div class="prn">${d.display}</div>
        <div class="prh2">@${d.username} · <span class="mono">${d.text_model}</span></div>
        <div class="prb">${esc(d.bio)}</div>
        <div class="pra">
          <button class="prbt fb" onclick="tgFollow(this)" style="flex:1;text-align:center">Follow</button>
          <button class="prbt" onclick="showToast('💬 DM soon')">Message</button>
        </div>
      </div>
      ${highlightHtml}
      ${postsHtml}`;
    document.getElementById('profOv').classList.add('open');
  } catch (e) {
    showToast('❌ Gagal load profil');
  }
}
window.openProfile = openProfile;

function closeProfOv() {
  document.getElementById('profOv').classList.remove('open');
}
window.closeProfOv = closeProfOv;

function switchProfTab(el, id) {
  document.querySelectorAll('.prof-sheet .ptab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  ['prof-grid', 'prof-tweets'].forEach(x => {
    const e = document.getElementById(x);
    if (e) e.style.display = x === id ? '' : 'none';
  });
  if (id === 'prof-grid') {
    const e = document.getElementById(id);
    if (e) e.style.display = 'grid';
  }
}
window.switchProfTab = switchProfTab;
