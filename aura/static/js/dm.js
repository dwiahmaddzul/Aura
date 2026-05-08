// ===========================================================================
// Aura Social — dm.js
// Owns: DM list, thread view, send/receive
// Architecture: skeleton-once + incremental polling. Input is NEVER rebuilt
// during polling, so the user can keep typing while AI replies stream in.
// ===========================================================================

window.aura.dmCurrentPersona = null;
window.aura.dmPollTimer = null;
window.aura.dmLastMsgCount = 0;

async function loadDmList() {
  const el = document.getElementById('dmList');
  el.innerHTML = '<div class="sk"><div class="sk-bar"></div><div class="sk-bar"></div><div class="sk-bar"></div></div>';
  try {
    const r = await fetch('/api/dm');
    const list = await r.json();
    if (!list.length) {
      el.innerHTML = '<div class="empty"><span>💬</span>Tulis sapaan pertama 👋</div>';
      return;
    }
    el.innerHTML = list.map(d => {
      const preview = d.has_thread
        ? (d.last_sender === 'me' ? `Kamu: ${esc(d.last_message || '')}` : esc(d.last_message || ''))
        : 'Mulai percakapan...';
      const dot = d.online ? '<span class="online-dot"></span>' : '';
      return `<div class="dm-i" onclick="openDmThread('${d.username}')">
        <div class="av-wrap">
          <div class="av" style="background:${d.color}">${d.avatar}</div>
          ${dot}
        </div>
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
  tEl.innerHTML = '<div class="sk"><div class="sk-bar"></div><div class="sk-bar"></div><div class="sk-bar"></div></div>';

  try {
    const r = await fetch('/api/dm/' + persona);
    const d = await r.json();

    // Build skeleton ONCE — header, msgs container, input
    tEl.innerHTML = `
      <div class="dm-th-head">
        <button class="dm-th-back" onclick="closeDmThread()">←</button>
        <div class="av-wrap" onclick="openProfile('${d.persona.username}')" style="cursor:pointer">
          <div class="av" style="background:${d.persona.color}">${d.persona.avatar}</div>
          ${d.persona.online ? '<span class="online-dot"></span>' : ''}
        </div>
        <div style="flex:1;cursor:pointer" onclick="openProfile('${d.persona.username}')">
          <div class="dm-th-name">${esc(d.persona.display)}</div>
          <div class="dm-th-sub">${d.persona.online ? '<span style="color:#4ade80">● online</span>' : '@' + d.persona.username}</div>
        </div>
      </div>
      <div class="dm-th-msgs" id="dmMsgs"></div>
      <div class="dm-input">
        <input class="dm-inp" id="dmInput" placeholder="Tulis pesan..." onkeydown="if(event.key==='Enter')sendDm()" autocomplete="off">
        <button class="dm-send" onclick="sendDm()" id="dmSendBtn">➤</button>
      </div>
    `;

    populateMessages(d.messages);
    window.aura.dmLastMsgCount = d.messages.length;
    document.getElementById('dmInput').focus();

    // Start polling — ONLY mutates the messages container, never the input
    clearInterval(window.aura.dmPollTimer);
    window.aura.dmPollTimer = setInterval(pollDmThread, 2500);
  } catch {
    tEl.innerHTML = '<div class="empty"><span>⚠️</span>Gagal load thread</div>';
  }
}
window.openDmThread = openDmThread;

function populateMessages(msgs) {
  const m = document.getElementById('dmMsgs');
  if (!m) return;
  if (!msgs.length) {
    m.innerHTML = '<div class="dm-empty">Sapa dia dulu 👋</div>';
    return;
  }
  m.innerHTML = msgs.map(msg =>
    `<div class="bub ${msg.is_me ? 'me' : 'them'}">${esc(msg.content)}</div>`
  ).join('');
  m.scrollTop = m.scrollHeight;
}

async function pollDmThread() {
  const persona = window.aura.dmCurrentPersona;
  if (!persona) return;
  try {
    const r = await fetch('/api/dm/' + persona);
    const d = await r.json();
    const m = document.getElementById('dmMsgs');
    if (!m) return;

    // Only act if there are new messages — never disturb existing DOM otherwise
    if (d.messages.length > window.aura.dmLastMsgCount) {
      // Remove typing indicator if present (AI just replied)
      const ti = m.querySelector('.dm-typing');
      if (ti) ti.remove();
      // Clear empty-state if showing
      const emptyEl = m.querySelector('.dm-empty');
      if (emptyEl) emptyEl.remove();

      // Append only the NEW messages
      const wasAtBottom = m.scrollTop + m.clientHeight >= m.scrollHeight - 80;
      const newMsgs = d.messages.slice(window.aura.dmLastMsgCount);
      newMsgs.forEach(msg => {
        const bubble = document.createElement('div');
        bubble.className = `bub ${msg.is_me ? 'me' : 'them'} bub-in`;
        bubble.textContent = msg.content;
        m.appendChild(bubble);
      });
      window.aura.dmLastMsgCount = d.messages.length;
      if (wasAtBottom) m.scrollTop = m.scrollHeight;
    }
  } catch {}
}

async function sendDm() {
  const inp = document.getElementById('dmInput');
  const txt = (inp?.value || '').trim();
  if (!txt) return;
  inp.value = '';
  const m = document.getElementById('dmMsgs');

  if (m) {
    // Clear empty placeholder if first message
    const emptyEl = m.querySelector('.dm-empty');
    if (emptyEl) emptyEl.remove();

    // Optimistic: append user bubble immediately
    const bubble = document.createElement('div');
    bubble.className = 'bub me bub-in';
    bubble.textContent = txt;
    m.appendChild(bubble);

    // Add typing indicator (removed by poll when AI replies)
    if (!m.querySelector('.dm-typing')) {
      const typing = document.createElement('div');
      typing.className = 'dm-typing';
      typing.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
      m.appendChild(typing);
    }

    m.scrollTop = m.scrollHeight;
    window.aura.dmLastMsgCount += 1;
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

  inp.focus();
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
