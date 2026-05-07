// ===========================================================================
// Aura Social — dm.js
// Owns: DM list, thread view, send + receive messages
// Depends on: main.js (window.aura, esc, showToast)
// ===========================================================================

window.aura.dmCurrentPersona = null;
window.aura.dmPollTimer = null;

async function loadDmList() {
  const el = document.getElementById('dmList');
  el.innerHTML = '<div class="empty"><span>💬</span>Loading...</div>';
  try {
    const r = await fetch('/api/dm');
    const list = await r.json();
    if (!list.length) {
      el.innerHTML = '<div class="empty"><span>💬</span>Belum ada percakapan</div>';
      return;
    }
    el.innerHTML = list.map(d => {
      const preview = d.has_thread
        ? (d.last_sender === 'me' ? `Kamu: ${esc(d.last_message || '')}` : esc(d.last_message || ''))
        : 'Mulai percakapan...';
      return `<div class="dm-i" onclick="openDmThread('${d.username}')">
        <div class="av" style="background:${d.color}">${d.avatar}</div>
        <div class="dm-i-m">
          <div class="dm-i-n">${d.display}</div>
          <div class="dm-i-p">${preview}</div>
        </div>
        ${d.last_time ? `<div class="dm-i-t">${d.last_time}</div>` : ''}
      </div>`;
    }).join('');
  } catch {
    el.innerHTML = '<div class="empty"><span>⚠️</span>Gagal load</div>';
  }
}
window.loadDmList = loadDmList;

async function openDmThread(persona) {
  window.aura.dmCurrentPersona = persona;
  document.getElementById('dmList').style.display = 'none';
  const tEl = document.getElementById('dmThread');
  tEl.style.display = 'flex';
  tEl.innerHTML = '<div class="empty"><span>💬</span>Loading...</div>';
  await renderDmThread();
  // Poll for AI replies every 3s while thread is open
  clearInterval(window.aura.dmPollTimer);
  window.aura.dmPollTimer = setInterval(() => {
    if (window.aura.dmCurrentPersona === persona) renderDmThread(true);
  }, 3000);
}
window.openDmThread = openDmThread;

async function renderDmThread(silent) {
  const persona = window.aura.dmCurrentPersona;
  if (!persona) return;
  try {
    const r = await fetch('/api/dm/' + persona);
    const d = await r.json();
    const tEl = document.getElementById('dmThread');
    const wasAtBottom = tEl.scrollTop + tEl.clientHeight >= tEl.scrollHeight - 50;

    const msgs = d.messages.map(m => `
      <div class="bub ${m.is_me ? 'me' : 'them'}">${esc(m.content)}</div>
    `).join('') || '<div style="text-align:center;color:var(--mu);font-size:13px;padding:30px">Sapa dia dulu 👋</div>';

    tEl.innerHTML = `
      <div class="dm-th-head">
        <button class="dm-th-back" onclick="closeDmThread()">←</button>
        <div class="av" style="background:${d.persona.color}" onclick="openProfile('${d.persona.username}')">${d.persona.avatar}</div>
        <div style="flex:1;cursor:pointer" onclick="openProfile('${d.persona.username}')">
          <div style="font-size:14px;font-weight:600;font-family:'Clash Display',sans-serif">${d.persona.display}</div>
          <div style="font-size:11px;color:var(--mu)">@${d.persona.username}</div>
        </div>
      </div>
      <div class="dm-th-msgs" id="dmMsgs">${msgs}</div>
      <div class="dm-input">
        <input class="dm-inp" id="dmInput" placeholder="Tulis pesan..." onkeydown="if(event.key==='Enter')sendDm()">
        <button class="dm-send" onclick="sendDm()">➤</button>
      </div>
    `;
    const msgsEl = document.getElementById('dmMsgs');
    if (msgsEl && (wasAtBottom || !silent)) msgsEl.scrollTop = msgsEl.scrollHeight;
    if (!silent) document.getElementById('dmInput').focus();
  } catch (e) {
    console.error(e);
  }
}

async function sendDm() {
  const inp = document.getElementById('dmInput');
  const txt = (inp?.value || '').trim();
  if (!txt) return;
  inp.value = '';
  // Optimistic append
  const msgsEl = document.getElementById('dmMsgs');
  if (msgsEl) {
    msgsEl.insertAdjacentHTML('beforeend', `<div class="bub me">${esc(txt)}</div>`);
    msgsEl.insertAdjacentHTML('beforeend', `<div class="dm-typing"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>`);
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }
  try {
    await fetch('/api/dm/' + window.aura.dmCurrentPersona, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: txt }),
    });
  } catch {
    showToast('❌ Gagal kirim');
  }
}
window.sendDm = sendDm;

function closeDmThread() {
  window.aura.dmCurrentPersona = null;
  clearInterval(window.aura.dmPollTimer);
  document.getElementById('dmThread').style.display = 'none';
  document.getElementById('dmList').style.display = '';
  loadDmList();
}
window.closeDmThread = closeDmThread;
