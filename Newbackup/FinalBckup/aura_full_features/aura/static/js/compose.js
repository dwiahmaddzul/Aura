// ===========================================================================
// Aura Social — compose.js
// Owns: compose modal (open/close), file upload, post submission
// Depends on: main.js (window.aura, showToast), feed.js (loadFeed)
// ===========================================================================

function handleFile(ev) {
  const f = ev.target.files[0];
  if (!f) return;
  if (f.size > 6 * 1024 * 1024) {
    showToast('⚠️ Max 6MB');
    return;
  }
  const rd = new FileReader();
  rd.onload = ev => {
    window.aura.imgB64 = ev.target.result.split(',')[1];
    document.getElementById('iel').src = ev.target.result;
    document.getElementById('iprev').style.display = 'block';
    openC();
  };
  rd.readAsDataURL(f);
}
window.handleFile = handleFile;

function rmImg() {
  window.aura.imgB64 = null;
  document.getElementById('iprev').style.display = 'none';
  document.getElementById('iel').src = '';
  ['fi', 'fi2'].forEach(id => document.getElementById(id).value = '');
}
window.rmImg = rmImg;

function openC() {
  document.getElementById('modal').classList.add('open');
  setTimeout(() => document.getElementById('ct').focus(), 280);
}
window.openC = openC;

function closeC() {
  document.getElementById('modal').classList.remove('open');
  const ep = document.getElementById('emojiPanel');
  if (ep) ep.style.display = 'none';
}
window.closeC = closeC;

function closeO(e) {
  if (e.target === document.getElementById('modal')) closeC();
}
window.closeO = closeO;

function cntCh() {
  document.getElementById('cc2').textContent = 280 - document.getElementById('ct').value.length;
}
window.cntCh = cntCh;

function pickMood(btn, mood) {
  const aura = window.aura;
  // Toggle off if same mood clicked again
  if (aura.selectedMood === mood) {
    btn.classList.remove('on');
    aura.selectedMood = null;
    return;
  }
  document.querySelectorAll('.mc').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  aura.selectedMood = mood;
}
window.pickMood = pickMood;

function resetMood() {
  window.aura.selectedMood = null;
  document.querySelectorAll('.mc').forEach(b => b.classList.remove('on'));
}

function toggleEmoji() {
  const p = document.getElementById('emojiPanel');
  p.style.display = p.style.display === 'none' ? '' : 'none';
}
window.toggleEmoji = toggleEmoji;

function addEmoji(em) {
  const ta = document.getElementById('ct');
  const s = ta.selectionStart || ta.value.length;
  ta.value = ta.value.slice(0, s) + em + ta.value.slice(ta.selectionEnd || s);
  ta.focus();
  ta.setSelectionRange(s + em.length, s + em.length);
  cntCh();
}
window.addEmoji = addEmoji;

async function subPost() {
  const txt = document.getElementById('ct').value.trim();
  if (!txt && !window.aura.imgB64) {
    showToast('⚠️ Tulis atau upload foto!');
    return;
  }
  const btn = document.getElementById('pbtn');
  btn.disabled = true;
  btn.textContent = 'Posting...';
  try {
    const r = await fetch('/api/posts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: txt,
        image_b64: window.aura.imgB64,
        mood: window.aura.selectedMood,
      }),
    });
    if (r.ok) {
      document.getElementById('ct').value = '';
      document.getElementById('ct').placeholder = 'Apa yang lagi kamu pikirin?…';
      cntCh();
      rmImg();
      resetMood();
      closeC();
      showToast('🚀 Posted!');
      loadFeed();
      // Refresh daily banner — should hide now
      if (typeof loadDailyBanner === 'function') loadDailyBanner();
      if (typeof loadStreak === 'function') loadStreak();
    } else {
      showToast('❌ Gagal');
    }
  } catch {
    showToast('❌ Network error');
  }
  btn.disabled = false;
  btn.textContent = 'Post ✦';
}
window.subPost = subPost;

// ── EDIT PROFILE ──
function openEditProfile() {
  const p = window.aura.myProfile;
  document.getElementById('epAvatar').value = p.avatar || 'K';
  document.getElementById('epAvatarPrev').textContent = p.avatar || 'K';
  document.getElementById('epName').value = p.display_name || '';
  document.getElementById('epBio').value = p.bio || '';
  document.getElementById('editModal').classList.add('open');
}
window.openEditProfile = openEditProfile;

function closeEditProfile() {
  document.getElementById('editModal').classList.remove('open');
}
window.closeEditProfile = closeEditProfile;

function closeEditP(e) {
  if (e.target === document.getElementById('editModal')) closeEditProfile();
}
window.closeEditP = closeEditP;

async function saveProfile() {
  const name = document.getElementById('epName').value.trim();
  const bio = document.getElementById('epBio').value.trim();
  const avatar = document.getElementById('epAvatar').value.trim() || 'K';
  if (!name) {
    showToast('⚠️ Nama wajib');
    return;
  }
  try {
    const r = await fetch('/api/me/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, bio, avatar }),
    });
    if (r.ok) {
      window.aura.myProfile = { display_name: name, bio, avatar };
      applyMyProfile();
      closeEditProfile();
      showToast('✅ Profil tersimpan');
      loadFeed();
    } else {
      showToast('❌ Gagal simpan');
    }
  } catch {
    showToast('❌ Network error');
  }
}
window.saveProfile = saveProfile;

// ── STORY UPLOAD (user) ──
function openMyStoryUpload() {
  document.getElementById('suPrev').style.display = 'none';
  document.getElementById('suCaption').value = '';
  document.getElementById('suSubmit').disabled = true;
  window.aura.storyUploadB64 = null;
  document.getElementById('storyUploadModal').classList.add('open');
}
window.openMyStoryUpload = openMyStoryUpload;

function closeStoryUpload() {
  document.getElementById('storyUploadModal').classList.remove('open');
}
window.closeStoryUpload = closeStoryUpload;

function closeStoryUp(e) {
  if (e.target === document.getElementById('storyUploadModal')) closeStoryUpload();
}
window.closeStoryUp = closeStoryUp;

function handleStoryFile(ev) {
  const f = ev.target.files[0];
  if (!f) return;
  if (f.size > 6 * 1024 * 1024) {
    showToast('⚠️ Max 6MB');
    return;
  }
  const rd = new FileReader();
  rd.onload = ev => {
    window.aura.storyUploadB64 = ev.target.result.split(',')[1];
    document.getElementById('suImg').src = ev.target.result;
    document.getElementById('suPrev').style.display = '';
    document.getElementById('suSubmit').disabled = false;
  };
  rd.readAsDataURL(f);
}
window.handleStoryFile = handleStoryFile;

async function submitStory() {
  if (!window.aura.storyUploadB64) return;
  const caption = document.getElementById('suCaption').value.trim();
  const btn = document.getElementById('suSubmit');
  btn.disabled = true;
  btn.textContent = 'Posting...';
  try {
    const r = await fetch('/api/stories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_b64: window.aura.storyUploadB64, caption }),
    });
    if (r.ok) {
      closeStoryUpload();
      showToast('✨ Story posted!');
      loadStories();
    } else {
      showToast('❌ Gagal');
    }
  } catch {
    showToast('❌ Network error');
  }
  btn.disabled = false;
  btn.textContent = 'Post Story ✦';
}
window.submitStory = submitStory;
