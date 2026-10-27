// ===========================================================================
// Aura Social — dm.js
// Owns: DM list, thread view, send/receive
// Thread skeleton is built once; polling asks only for messages newer than
// the last one we have (?since=) and stops when you leave the thread/page or
// hide the tab. The input is never rebuilt while you type.
// ===========================================================================

window.aura.dmCurrentPersona = null;
window.aura.dmPollTimer = null;
window.aura.dmLastTs = 0;
let dmListCache = '';

async function loadDmList() {
  const el = document.getElementById('dmList');
  if (!dmListCache) el.innerHTML = '<div class="sk"><div class="sk-bar"></div><div class="sk-bar"></div><div class="sk-bar"></div></div>';
  try {
    const list = await api('/api/dm');
    const html = list.map(d => {
      const preview = d.has_thread
        ? (d.last_sender === 'me' ? `Kamu: ${esc(d.last_message || '')}` : esc(d.last_message || ''))
        : 'Mulai percakapan…';
      return `<div class="dm-i" role="button" tabindex="0" onclick="openDmThread('${esc(d.username)}')">
        <div class="av-wrap">
          <div class="av" style="background:${esc(d.color)}">${esc(d.avatar)}</div>
          ${d.online ? '<span class="online-dot"></span>' : ''}
        </div>
        <div class="dm-i-m">
          <div class="dm-i-n">${esc(d.display)}</div>
          <div class="dm-i-p">${preview}</div>
        </div>
        ${d.last_at ? `<div class="dm-i-t">${tsSpan(d.last_at)}</div>` : ''}
      </div>`;
    }).join('');
    if (html !== dmListCache) { dmListCache = html; el.innerHTML = html; }
  } catch {
    if (!dmListCache) el.innerHTML = '<div class="empty"><span>⚠️</span>Gagal memuat</div>';
  }
}
window.loadDmList = loadDmList;

async function openDmThread(persona) {
  const a = window.aura;
  a.dmCurrentPersona = persona;
  document.getElementById('dmList').style.display = 'none';
  const tEl = document.getElementById('dmThread');
  tEl.style.display = 'flex';
  tEl.innerHTML = '<div class="sk"><div class="sk-bar"></div><div class="sk-bar"></div><div class="sk-bar"></div></div>';
  try {
    const d = await api('/api/dm/' + encodeURIComponent(persona));
    if (a.dmCurrentPersona !== persona) return;
    tEl.innerHTML = `
      <div class="dm-th-head">
        <button class="dm-th-back" onclick="closeDmThread()" aria-label="Kembali">←</button>
        <div class="av-wrap tap" onclick="openProfile('${esc(d.persona.username)}')">
          <div class="av" style="background:${esc(d.persona.color)}">${esc(d.persona.avatar)}</div>
          ${d.persona.online ? '<span class="online-dot"></span>' : ''}
        </div>
        <div class="tap" style="flex:1" onclick="openProfile('${esc(d.persona.username)}')">
          <div class="dm-th-name">${esc(d.persona.display)}</div>
          <div class="dm-th-sub">${d.persona.online ? '<span class="on-txt">● online</span>' : '@' + esc(d.persona.username)}</div>
        </div>
      </div>
      <div class="dm-th-msgs" id="dmMsgs" aria-live="polite"></div>
      <div class="dm-input">
        <input class="dm-inp" id="dmInput" placeholder="Tulis pesan…" maxlength="1000" enterkeyhint="send"
          onkeydown="if(event.key==='Enter'&&!event.isComposing)sendDm()" autocomplete="off" aria-label="Tulis pesan">
        <button class="dm-send" onclick="sendDm()" id="dmSendBtn" aria-label="Kirim"><svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg></button>
      </div>`;
    populateMessages(d.messages);
    document.getElementById('dmInput').focus();
    startDmPolling();
  } catch {
    tEl.innerHTML = '<div class="empty"><span>⚠️</span>Gagal memuat percakapan</div>';
  }
}
window.openDmThread = openDmThread;

function bubble(msg, animate) {
  const b = document.createElement('div');
  b.className = `bub ${msg.is_me ? 'me' : 'them'}${animate ? ' bub-in' : ''}`;
  b.textContent = msg.content;
  b.title = timeAgo(msg.created_at);
  return b;
}

function populateMessages(msgs) {
  const m = document.getElementById('dmMsgs');
  if (!m) return;
  m.innerHTML = '';
  if (!msgs.length) {
    m.innerHTML = '<div class="dm-empty">Sapa dia dulu 👋</div>';
    window.aura.dmLastTs = 0;
    return;
  }
  const frag = document.createDocumentFragment();
  msgs.forEach(msg => frag.appendChild(bubble(msg, false)));
  m.appendChild(frag);
  window.aura.dmLastTs = msgs[msgs.length - 1].created_at || 0;
  m.scrollTop = m.scrollHeight;
}

function startDmPolling() {
  stopDmPolling();
  window.aura.dmPollTimer = setInterval(() => { if (!document.hidden) pollDmThread(); }, 3000);
}
function stopDmPolling() {
  clearInterval(window.aura.dmPollTimer);
  window.aura.dmPollTimer = null;
}
window.stopDmPolling = stopDmPolling;

async function pollDmThread() {
  const a = window.aura;
  const persona = a.dmCurrentPersona;
  if (!persona) return stopDmPolling();
  try {
    const d = await api(`/api/dm/${encodeURIComponent(persona)}?since=${a.dmLastTs || 0}`);
    if (a.dmCurrentPersona !== persona) return;
    const m = document.getElementById('dmMsgs');
    if (!m) return;
    // Pesan dari kita sudah tampil (optimistic) → hanya tambahkan yang dari dia.
    const incoming = d.messages.filter(x => !x.is_me);
    if (d.messages.length) a.dmLastTs = d.messages[d.messages.length - 1].created_at || a.dmLastTs;
    if (!incoming.length) return;
    m.querySelector('.dm-typing')?.remove();
    m.querySelector('.dm-empty')?.remove();
    const wasAtBottom = m.scrollTop + m.clientHeight >= m.scrollHeight - 80;
    incoming.forEach(msg => m.appendChild(bubble(msg, true)));
    if (wasAtBottom) m.scrollTop = m.scrollHeight;
  } catch {}
}

async function sendDm() {
  const a = window.aura;
  const inp = document.getElementById('dmInput');
  const txt = (inp?.value || '').trim();
  if (!txt) return;
  inp.value = '';
  const m = document.getElementById('dmMsgs');
  const mine = bubble({ is_me: true, content: txt, created_at: Date.now() / 1000 }, true);
  if (m) {
    m.querySelector('.dm-empty')?.remove();
    m.appendChild(mine);
    m.scrollTop = m.scrollHeight;
  }
  try {
    const d = await api('/api/dm/' + encodeURIComponent(a.dmCurrentPersona), { json: { content: txt } });
    if (d.created_at) a.dmLastTs = Math.max(a.dmLastTs || 0, d.created_at);
    if (m && d.will_reply && !m.querySelector('.dm-typing')) {
      const typing = document.createElement('div');
      typing.className = 'dm-typing';
      typing.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
      m.appendChild(typing);
      m.scrollTop = m.scrollHeight;
      // Kalau balasan tidak datang (mis. gagal), titik-titik jangan selamanya.
      setTimeout(() => typing.remove(), 60000);
    }
  } catch {
    mine.classList.add('failed');
    mine.title = 'Gagal terkirim';
    inp.value = txt;
    showToast('Pesan gagal terkirim');
  }
  inp.focus();
}
window.sendDm = sendDm;

function closeDmThread() {
  window.aura.dmCurrentPersona = null;
  stopDmPolling();
  document.getElementById('dmThread').style.display = 'none';
  document.getElementById('dmList').style.display = '';
  loadDmList();
}
window.closeDmThread = closeDmThread;
