// ===========================================================================
// Aura Social — daily.js
// Owns: daily check-in banner, throwback banner, streak fetcher
// Depends on: main.js (window.aura, esc, showToast), compose.js (openC)
// ===========================================================================

window.aura.dailyPromptText = null;

async function loadDailyBanner() {
  try {
    const r = await fetch('/api/me/daily-prompt');
    const d = await r.json();
    const el = document.getElementById('dailyBanner');
    if (!d.prompt) {
      el.innerHTML = '';
      window.aura.dailyPromptText = null;
      return;
    }
    const p = d.prompt;
    window.aura.dailyPromptText = p.text;
    el.innerHTML = `
      <div class="daily-bn" onclick="useDailyPrompt()">
        <div class="av" style="background:${p.persona.color}">${p.persona.avatar}</div>
        <div class="daily-bn-c">
          <div class="daily-bn-h">${esc(p.persona.display)} nanya:</div>
          <div class="daily-bn-t">${esc(p.text)}</div>
        </div>
        <button class="daily-bn-x" onclick="event.stopPropagation();dismissDaily()">×</button>
      </div>`;
  } catch {}
}
window.loadDailyBanner = loadDailyBanner;

function useDailyPrompt() {
  openC();
  // Pre-fill placeholder with the prompt — leave textarea empty
  const ta = document.getElementById('ct');
  if (window.aura.dailyPromptText) {
    ta.placeholder = window.aura.dailyPromptText;
  }
  setTimeout(() => ta.focus(), 280);
}
window.useDailyPrompt = useDailyPrompt;

function dismissDaily() {
  document.getElementById('dailyBanner').innerHTML = '';
}
window.dismissDaily = dismissDaily;

async function loadThrowback() {
  try {
    const r = await fetch('/api/me/throwback');
    const d = await r.json();
    const el = document.getElementById('throwbackBanner');
    if (!d.throwback) {
      el.innerHTML = '';
      return;
    }
    const t = d.throwback;
    const moodEm = t.mood && window.MOOD_EMOJI[t.mood] ? ` ${window.MOOD_EMOJI[t.mood]}` : '';
    const preview = t.content ? esc(t.content) : (t.has_image ? '📸 foto' : '');
    el.innerHTML = `
      <div class="thr-bn" onclick="showToast('${esc(t.label)}')">
        <div class="thr-bn-i">📅</div>
        <div class="thr-bn-c">
          <div class="thr-bn-h">${esc(t.label)}${moodEm}</div>
          <div class="thr-bn-t">${preview}</div>
        </div>
      </div>`;
  } catch {}
}
window.loadThrowback = loadThrowback;
