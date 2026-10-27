// ===========================================================================
// Aura Social — daily.js
// Owns: daily check-in banner, throwback banner
// The daily question is fixed for the whole day (server picks it per date),
// and dismissing it hides it until tomorrow instead of popping back up.
// Depends on: main.js (window.aura, api, esc, showToast), compose.js (openC)
// ===========================================================================

window.aura.dailyPromptText = null;
window.aura.dailyPromptPersona = null;

function dismissedDay() {
  try { return localStorage.getItem('auraDailyDismissed') || ''; } catch { return ''; }
}

async function loadDailyBanner() {
  const el = document.getElementById('dailyBanner');
  try {
    const d = await api('/api/me/daily-prompt');
    if (!d.prompt || dismissedDay() === d.prompt.day) {
      el.innerHTML = '';
      window.aura.dailyPromptText = null;
      window.aura.dailyPromptPersona = null;
      return;
    }
    const p = d.prompt;
    if (window.aura.dailyPromptText === p.text && el.innerHTML) return;  // sama → jangan render ulang
    window.aura.dailyPromptText = p.text;
    window.aura.dailyPromptPersona = p.persona.username;
    window.aura.dailyPromptDay = p.day;
    el.innerHTML = `
      <div class="daily-bn" role="button" tabindex="0" onclick="useDailyPrompt()">
        <div class="av" style="background:${esc(p.persona.color)}">${esc(p.persona.avatar)}</div>
        <div class="daily-bn-c">
          <div class="daily-bn-h">${esc(p.persona.display)} nanya:</div>
          <div class="daily-bn-t">${esc(p.text)}</div>
        </div>
        <button class="daily-bn-x" onclick="event.stopPropagation();dismissDaily()" aria-label="Tutup">×</button>
      </div>`;
  } catch {}
}
window.loadDailyBanner = loadDailyBanner;

function useDailyPrompt() {
  openC();
  if (window.aura.dailyPromptPersona) {
    window.aura.answeringPrompt = {
      persona: window.aura.dailyPromptPersona,
      text: window.aura.dailyPromptText,
    };
  }
  const ta = document.getElementById('ct');
  if (window.aura.dailyPromptText) ta.placeholder = window.aura.dailyPromptText;
  setTimeout(() => ta.focus(), 280);
}
window.useDailyPrompt = useDailyPrompt;

function dismissDaily() {
  try { localStorage.setItem('auraDailyDismissed', window.aura.dailyPromptDay || ''); } catch {}
  document.getElementById('dailyBanner').innerHTML = '';
}
window.dismissDaily = dismissDaily;

async function loadThrowback() {
  const el = document.getElementById('throwbackBanner');
  try {
    const d = await api('/api/me/throwback');
    if (!d.throwback) { el.innerHTML = ''; return; }
    const t = d.throwback;
    const moodEm = t.mood && window.MOOD_EMOJI[t.mood] ? ` ${window.MOOD_EMOJI[t.mood]}` : '';
    const preview = t.content ? esc(t.content) : (t.has_image ? '📷 foto' : '');
    el.innerHTML = `
      <div class="thr-bn" role="button" tabindex="0" onclick="openPost(${t.id})">
        <div class="thr-bn-i"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></div>
        <div class="thr-bn-c">
          <div class="thr-bn-h">Hari ini, ${esc(t.label)}${moodEm}</div>
          <div class="thr-bn-t">${preview}</div>
        </div>
      </div>`;
  } catch {}
}
window.loadThrowback = loadThrowback;
