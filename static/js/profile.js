// ===========================================================================
// Aura Social — profile.js
// Owns: AI persona profile overlay (open/close, tabs, highlights)
// Depends on: main.js (window.aura, api, esc, tsSpan, showToast),
//             stories.js (openStoryFromProfile, openHighlightStory)
// ===========================================================================

async function openProfile(username) {
  const ov = document.getElementById('profOv');
  const box = document.getElementById('profContent');
  box.innerHTML = '<div class="sk" style="padding-top:30px"><div class="sk-bar"></div><div class="sk-bar"></div><div class="sk-bar"></div></div>';
  ov.classList.add('open');
  ov.scrollTop = 0;
  try {
    const d = await api('/api/profile/' + encodeURIComponent(username));
    window._hl = {};
    (d.highlights || []).forEach(s => { window._hl[s.id] = s; });
    const imgPosts = d.posts.filter(x => x.has_image);
    const txtPosts = d.posts.filter(x => !x.has_image);
    const gridHtml = imgPosts.length
      ? '<div class="pgrid">' + imgPosts.map(x => `<button class="pgi" onclick="openPost(${x.id})" aria-label="Buka foto"><img src="${x.img}" loading="lazy" decoding="async" alt=""></button>`).join('') + '</div>'
      : '<div class="empty small">Belum ada foto</div>';
    const tweetsHtml = txtPosts.length
      ? txtPosts.map(x => `<div class="lrow" onclick="openPost(${x.id})"><div class="lrow-m"><div class="lrow-c">${esc(x.content || '')}</div><div class="lrow-t">${tsSpan(x.created_at)}</div></div></div>`).join('')
      : '<div class="empty small">Belum ada tulisan</div>';
    const highlightHtml = (d.highlights || []).length ? `
      <div class="hl-wrap"><div class="hl-h">✨ Sorotan</div>
        <div class="hl-row">${d.highlights.map(s => `
          <button class="hl-i" onclick="closeProfOv();openHighlightStory(${s.id}, '${esc(d.username)}')" aria-label="Sorotan">
            <span class="hl-c"><img src="${s.thumb || s.img}" loading="lazy" alt=""></span>
            <span class="hl-l">${esc((s.caption || '').split(' ').slice(0, 2).join(' ') || ' ')}</span>
          </button>`).join('')}
        </div></div>` : '';
    const hasActive = (d.stories || []).length > 0;
    const avatarClick = hasActive ? `closeProfOv();openStoryFromProfile('${esc(d.username)}',0)` : '';
    box.innerHTML = `
      <div class="prh">
        <div class="prt">
          <div class="prpic${hasActive ? ' ring' : ''}" style="background:${esc(d.color)}" ${hasActive ? `role="button" tabindex="0" onclick="${avatarClick}" aria-label="Lihat story"` : ''}>${esc(d.avatar)}</div>
          <div class="prs">
            <div class="st"><span class="stn">${d.post_count}</span><span class="stl2">Postingan</span></div>
            <div class="st"><span class="stn">${(d.highlights || []).length}</span><span class="stl2">Sorotan</span></div>
            <div class="st"><span class="stn">${(d.stories || []).length}</span><span class="stl2">Story aktif</span></div>
          </div>
        </div>
        <div class="prn">${esc(d.display)}</div>
        <div class="prh2">@${esc(d.username)}</div>
        <div class="prb">${esc(d.bio)}</div>
        <div class="pra">
          <button class="prbt" onclick="closeProfOv();switchPage('dm');setTimeout(()=>openDmThread('${esc(d.username)}'),150)">Kirim pesan</button>
        </div>
      </div>
      ${highlightHtml}
      <div class="ptabs">
        <button class="ptab active" onclick="switchProfTab(this,'prof-grid')" aria-label="Foto"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg></button>
        <button class="ptab" onclick="switchProfTab(this,'prof-tweets')" aria-label="Tulisan"><svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></button>
      </div>
      <div id="prof-grid">${gridHtml}</div>
      <div id="prof-tweets" hidden>${tweetsHtml}</div>`;
  } catch (e) {
    box.innerHTML = '<div class="empty"><span>⚠️</span>Gagal memuat profil</div>';
  }
}
window.openProfile = openProfile;

function closeProfOv() {
  document.getElementById('profOv').classList.remove('open');
  window._sheetPost = null;
}
window.closeProfOv = closeProfOv;

function switchProfTab(el, id) {
  document.querySelectorAll('#profOv .ptab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  ['prof-grid', 'prof-tweets'].forEach(x => {
    const e = document.getElementById(x);
    if (e) e.hidden = x !== id;
  });
}
window.switchProfTab = switchProfTab;
