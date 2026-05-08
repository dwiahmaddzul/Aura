// ===========================================================================
// Aura Social — stories.js
// Owns: stories rail render, story viewer (multi-slide nav), highlights
// Depends on: main.js (window.aura, esc, showToast)
// ===========================================================================

async function loadStories() {
  try {
    const r = await fetch('/api/stories');
    window.aura.storyData = await r.json();
  } catch {
    window.aura.storyData = [];
  }
  renderStories();
}
window.loadStories = loadStories;

function renderStories() {
  const w = document.getElementById('sw');
  let h = `<div class="si" onclick="openMyStoryUpload()">
    <div class="sr seen"><div class="sav" style="background:var(--s2);font-size:22px">+</div></div>
    <div class="slbl">Kamu</div></div>`;
  const withStory = new Set(window.aura.storyData.map(s => s.username));
  window.aura.personas.forEach((p) => {
    const has = withStory.has(p.username);
    h += `<div class="si" onclick="openSVUser('${p.username}')">
      <div class="sr ${has ? 'has-story' : 'seen'}"><div class="sav" style="background:${p.color}">${p.avatar}</div></div>
      <div class="slbl">${p.username}</div></div>`;
  });
  w.innerHTML = h;
}

function openSVUser(username) {
  const aura = window.aura;
  const idx = aura.storyData.findIndex(s => s.username === username);
  const p = aura.personas.find(x => x.username === username);
  if (idx >= 0 && aura.storyData[idx].slides.length > 0) {
    aura.curStoryUser = idx;
    aura.curSlide = 0;
    showStorySlide();
    document.getElementById('sv').classList.add('open');
  } else if (p) {
    // No real story — show emoji placeholder
    aura.curStoryUser = -1;
    aura.curSlide = 0;
    const sv = document.getElementById('sv');
    document.getElementById('svav').textContent = p.avatar;
    document.getElementById('svav').style.background = p.color;
    document.getElementById('svun').textContent = p.display;
    document.getElementById('sv-time').textContent = '';
    document.getElementById('sv-bars').innerHTML = '<div class="svbr"><div class="svf" id="svf-0"></div></div>';
    document.getElementById('sve').innerHTML = `<div class="sv-tap sv-tap-left" onclick="storyPrev()"></div>
      <span class="story-emoji">✨</span>
      <div class="sv-tap sv-tap-right" onclick="storyNext()"></div>`;
    sv.classList.add('open');
    startStoryTimer(0, 1);
  }
}
window.openSVUser = openSVUser;

function showStorySlide() {
  const aura = window.aura;
  if (aura.curStoryUser < 0) return;
  const user = aura.storyData[aura.curStoryUser];
  const slides = user.slides;
  const slide = slides[aura.curSlide];
  document.getElementById('svav').textContent = user.avatar;
  document.getElementById('svav').style.background = user.color;
  document.getElementById('svun').textContent = user.display;
  document.getElementById('sv-time').textContent = slide.time_ago;
  // Progress bars
  let bars = '';
  slides.forEach((_, i) => {
    bars += `<div class="svbr"><div class="svf ${i < aura.curSlide ? 'done' : ''}" id="svf-${i}"></div></div>`;
  });
  document.getElementById('sv-bars').innerHTML = bars;
  // Content
  document.getElementById('sve').innerHTML = `
    <div class="sv-tap sv-tap-left" onclick="storyPrev()"></div>
    <img src="/api/stories/${slide.id}/image" style="width:100%;height:100%;object-fit:cover">
    <div class="sv-caption">${esc(slide.caption || '')}</div>
    <div class="sv-tap sv-tap-right" onclick="storyNext()"></div>`;
  startStoryTimer(aura.curSlide, slides.length);
}

function startStoryTimer(idx, total) {
  clearTimeout(window.aura.storyTimer);
  const fill = document.getElementById('svf-' + idx);
  if (fill) {
    fill.style.transition = 'none';
    fill.style.width = '0%';
    setTimeout(() => {
      fill.style.transition = 'width 5s linear';
      fill.style.width = '100%';
    }, 30);
  }
  window.aura.storyTimer = setTimeout(() => {
    const aura = window.aura;
    if (aura.curStoryUser >= 0 && aura.curSlide < aura.storyData[aura.curStoryUser].slides.length - 1) {
      storyNext();
    } else {
      closeSV();
    }
  }, 5100);
}

function storyNext() {
  const aura = window.aura;
  if (aura.curStoryUser < 0) {
    closeSV();
    return;
  }
  const slides = aura.storyData[aura.curStoryUser].slides;
  if (aura.curSlide < slides.length - 1) {
    aura.curSlide++;
    showStorySlide();
  } else {
    // Next user's story
    let nextIdx = aura.curStoryUser + 1;
    while (nextIdx < aura.storyData.length && aura.storyData[nextIdx].slides.length === 0) nextIdx++;
    if (nextIdx < aura.storyData.length) {
      aura.curStoryUser = nextIdx;
      aura.curSlide = 0;
      showStorySlide();
    } else {
      closeSV();
    }
  }
}
window.storyNext = storyNext;

function storyPrev() {
  const aura = window.aura;
  if (aura.curSlide > 0) {
    aura.curSlide--;
    showStorySlide();
  }
}
window.storyPrev = storyPrev;

function closeSV() {
  clearTimeout(window.aura.storyTimer);
  document.getElementById('sv').classList.remove('open');
}
window.closeSV = closeSV;

function openStoryFromProfile(username, slideIdx) {
  const aura = window.aura;
  const idx = aura.storyData.findIndex(s => s.username === username);
  if (idx >= 0 && aura.storyData[idx].slides.length > slideIdx) {
    aura.curStoryUser = idx;
    aura.curSlide = slideIdx;
    showStorySlide();
    document.getElementById('sv').classList.add('open');
  } else {
    showToast('Story belum dimuat, coba refresh');
  }
}
window.openStoryFromProfile = openStoryFromProfile;

function openHighlightStory(storyId) {
  const sv = document.getElementById('sv');
  document.getElementById('sv-bars').innerHTML = '<div class="svbr"><div class="svf" id="svf-0"></div></div>';
  document.getElementById('sve').innerHTML = `
    <div class="sv-tap sv-tap-left" onclick="closeSV()"></div>
    <img src="/api/stories/${storyId}/image" style="width:100%;height:100%;object-fit:cover">
    <div class="sv-tap sv-tap-right" onclick="closeSV()"></div>`;
  document.getElementById('svun').textContent = 'Sorotan';
  document.getElementById('sv-time').textContent = '✨';
  window.aura.curStoryUser = -1;
  sv.classList.add('open');
  startStoryTimer(0, 1);
}
window.openHighlightStory = openHighlightStory;

// ── Story reply: send as DM to that friend, with story caption as context
async function sendStoryReply() {
  const inp = document.getElementById('svReplyInput');
  const txt = (inp?.value || '').trim();
  if (!txt) return;
  const userIdx = window.aura.curStoryUser;
  if (userIdx < 0 || !window.aura.storyData[userIdx]) {
    showToast('Story dari highlight, gak bisa balas');
    return;
  }
  const friend = window.aura.storyData[userIdx];
  if (friend.username === 'me') {
    showToast('Gak bisa balas story sendiri');
    return;
  }
  const slide = friend.slides[window.aura.curSlide];
  // Compose context: include story caption as quoted prefix
  const ctx = slide?.caption
    ? `[balas story: "${slide.caption}"] ${txt}`
    : `[balas story-mu] ${txt}`;
  inp.value = '';
  try {
    const r = await fetch('/api/dm/' + friend.username, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: ctx }),
    });
    if (r.ok) {
      showToast(`💬 Pesan dikirim ke ${friend.display}`);
      // Close story viewer + jump into DM thread for continuity
      closeSV();
      setTimeout(() => {
        switchPage('dm');
        setTimeout(() => openDmThread(friend.username), 200);
      }, 400);
    } else {
      showToast('❌ Gagal kirim');
    }
  } catch {
    showToast('❌ Network error');
  }
}
window.sendStoryReply = sendStoryReply;

// Quick like for a story (visual feedback only — no backend table for story likes)
function likeStory() {
  const btn = document.getElementById('svLikeBtn');
  if (!btn) return;
  const liked = btn.dataset.liked === '1';
  btn.dataset.liked = liked ? '0' : '1';
  btn.textContent = liked ? '🤍' : '❤️';
  btn.style.transform = 'scale(1.4)';
  setTimeout(() => { btn.style.transform = ''; }, 200);
  if (!liked) showToast('❤️');
}
window.likeStory = likeStory;
