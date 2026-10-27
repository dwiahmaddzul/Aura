// ===========================================================================
// Aura — Kendali AI (/kelola)
// Every control saves itself (POST /api/kelola/settings) and takes effect on
// the server within ~30 s. Stats refresh every 20 s without touching the form
// you are editing.
// ===========================================================================
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const DEPRECATED = new Set(['moonshotai/Kimi-K2-Instruct', 'Qwen/Qwen2.5-VL-72B-Instruct']);
  let S = null;            // last full state
  let formVersion = -1;    // settings version the form was filled from
  let refreshTimer = null;

  // ── helpers ──
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  async function call(url, opts = {}) {
    const o = { method: opts.method || (opts.json !== undefined ? 'POST' : 'GET'), headers: { 'X-Kelola': '1' } };
    if (opts.json !== undefined) { o.headers['Content-Type'] = 'application/json'; o.body = JSON.stringify(opts.json); }
    const r = await fetch(url, o);
    let d = null;
    try { d = await r.json(); } catch {}
    if (!r.ok) { const e = new Error((d && (d.error || firstErr(d.errors))) || ('HTTP ' + r.status)); e.status = r.status; e.data = d; throw e; }
    return d;
  }
  const firstErr = (errs) => errs ? Object.values(errs)[0] : null;
  let tT;
  function toast(msg, bad = false) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.toggle('bad', bad);
    t.classList.add('show');
    clearTimeout(tT);
    tT = setTimeout(() => t.classList.remove('show'), 2400);
  }
  const kurs = () => (S && S.settings.usd_idr) || 16500;
  function usd(v) {
    v = v || 0;
    if (v === 0) return '$0';
    if (v < 0.0001) return '<$0.0001';
    if (v < 0.01) return '$' + v.toFixed(4);
    if (v < 1) return '$' + v.toFixed(3);
    return '$' + v.toFixed(2);
  }
  const rp = (v) => 'Rp ' + Math.round((v || 0) * kurs()).toLocaleString('id-ID');
  const pct = (v) => Math.round((v || 0) * 100) + '%';
  function ago(ts) {
    if (!ts) return '';
    const d = Date.now() / 1000 - ts;
    if (d < 60) return 'baru saja';
    if (d < 3600) return Math.floor(d / 60) + ' mnt lalu';
    if (d < 86400) return Math.floor(d / 3600) + ' jam lalu';
    return Math.floor(d / 86400) + ' hari lalu';
  }
  const mins = (sec) => sec == null ? '–' : sec <= 60 ? 'sebentar lagi' : '±' + Math.round(sec / 60) + ' mnt';
  const bytes = (b) => b > 1e9 ? (b / 1e9).toFixed(2) + ' GB' : b > 1e6 ? (b / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1e3)) + ' KB';
  function twoClick(btn, label, fn) {
    if (btn.dataset.armed === '1') { btn.dataset.armed = ''; btn.textContent = label; fn(); return; }
    btn.dataset.armed = '1';
    const old = btn.textContent;
    btn.textContent = 'Klik lagi untuk yakin';
    setTimeout(() => { if (btn.dataset.armed === '1') { btn.dataset.armed = ''; btn.textContent = old; } }, 4000);
  }

  // ── auth ──
  window.login = async () => {
    const btn = $('#loginBtn');
    btn.disabled = true;
    $('#loginErr').textContent = '';
    try {
      await call('/api/kelola/login', { json: { password: $('#pw').value } });
      $('#pw').value = '';
      await load();
    } catch (e) {
      $('#loginErr').textContent = e.status === 429 ? 'Terlalu banyak percobaan. Tunggu beberapa menit.' : e.message;
    }
    btn.disabled = false;
  };
  window.logout = async () => {
    try { await call('/api/kelola/logout', { json: {} }); } catch {}
    location.reload();
  };

  async function load() {
    try {
      S = await call('/api/kelola/state');
    } catch (e) {
      if (e.status === 401) {
        $('#dashView').hidden = true;
        $('#loginView').hidden = false;
        $('#logoutBtn').hidden = true;
        if (e.data && e.data.configured === false) {
          $('#loginErr').textContent = 'ADMIN_PASSWORD belum di-set di server, dashboard terkunci.';
          $('#loginBtn').disabled = true;
        } else setTimeout(() => $('#pw').focus(), 50);
        return;
      }
      toast('Gagal memuat: ' + e.message, true);
      return;
    }
    $('#loginView').hidden = true;
    $('#dashView').hidden = false;
    $('#logoutBtn').hidden = false;
    fillForm();
    renderStats();
    clearInterval(refreshTimer);
    refreshTimer = setInterval(refresh, 20000);
  }

  async function refresh() {
    if (document.hidden) return;
    try {
      S = await call('/api/kelola/state');
      const editing = document.activeElement && document.activeElement.closest('.field,.pers,.tbl');
      if (S.version !== formVersion && !editing) fillForm();
      renderStats();
    } catch (e) {
      if (e.status === 401) load();
    }
  }

  // ── form ──
  function setControl(el, v) {
    if (el.type === 'checkbox') el.checked = !!v;
    else el.value = v;
    if (el.type === 'range') showVal(el);
  }
  function showVal(el) {
    const lab = $(`[data-show="${el.dataset.k}"]`);
    if (lab) lab.textContent = pct(parseFloat(el.value));
  }

  function fillForm() {
    const st = S.settings;
    formVersion = S.version;
    // jam tenang
    ['#f-qs', '#f-qe'].forEach(sel => {
      const el = $(sel);
      if (!el.options.length) el.innerHTML = Array.from({ length: 24 }, (_, h) => `<option value="${h}">${String(h).padStart(2, '0')}:00</option>`).join('');
    });
    const tz = $('#f-tz');
    if (st.app_tz && ![...tz.options].some(o => o.value === st.app_tz)) tz.insertAdjacentHTML('beforeend', `<option value="${esc(st.app_tz)}">${esc(st.app_tz)}</option>`);
    $$('[data-k]').forEach(el => {
      const k = el.dataset.k;
      if (k in st) setControl(el, st[k]);
      const b = S.bounds[k];
      if (b && el.type !== 'range') { el.min = b[0]; el.max = b[1]; }
    });
    // presets
    const match = Object.entries(S.presets).find(([, p]) => Object.entries(p).every(([k, v]) => st[k] === v));
    $$('.preset').forEach(b => b.classList.toggle('on', !!match && b.dataset.preset === match[0]));
    $('#presetBadge').textContent = match ? 'Mode ' + match[0] : 'Kustom';
    renderPersonas();
    renderPrices();
    renderEstimates();
  }

  async function save(changes, el) {
    try {
      const d = await call('/api/kelola/settings', { json: changes });
      S.settings = d.settings; S.personas = d.personas; S.version = d.version; formVersion = d.version;
      // nilai yang di-clamp server ditampilkan apa adanya
      Object.keys(d.saved || {}).forEach(k => $$(`[data-k="${k}"]`).forEach(x => { if (x !== document.activeElement || x.type !== 'number') setControl(x, d.saved[k]); }));
      if (el) { el.classList.add('saved'); setTimeout(() => el.classList.remove('saved'), 900); }
      toast('Tersimpan');
      const match = Object.entries(S.presets).find(([, p]) => Object.entries(p).every(([k, v]) => S.settings[k] === v));
      $$('.preset').forEach(b => b.classList.toggle('on', !!match && b.dataset.preset === match[0]));
      $('#presetBadge').textContent = match ? 'Mode ' + match[0] : 'Kustom';
      renderEstimates();
      refreshSoon();
    } catch (e) {
      toast(e.message || 'Gagal menyimpan', true);
      if (el) { el.classList.add('bad'); setTimeout(() => el.classList.remove('bad'), 1500); }
      if (S) fillForm();
    }
  }
  let soonT;
  const refreshSoon = () => { clearTimeout(soonT); soonT = setTimeout(refresh, 1200); };

  const timers = {};
  document.addEventListener('change', (ev) => {
    const el = ev.target.closest('[data-k]');
    if (!el || !S) return;
    const k = el.dataset.k;
    let v = el.type === 'checkbox' ? el.checked : el.value;
    if (el.type === 'number' || el.type === 'range') {
      if (el.value === '') return;
      v = parseFloat(el.value);
    }
    if (el.tagName === 'SELECT' && /^quiet_/.test(k)) v = parseInt(el.value, 10);
    clearTimeout(timers[k]);
    save({ [k]: v }, el);
  });
  document.addEventListener('input', (ev) => {
    const el = ev.target;
    if (el.type === 'range' && el.dataset.k) showVal(el);
    if (el.type === 'range' && el.dataset.pk) $(`[data-pshow="${el.dataset.pk}"]`).textContent = pct(parseFloat(el.value));
  });
  document.addEventListener('click', (ev) => {
    const b = ev.target.closest('.preset');
    if (!b || !S) return;
    applyPreset(b.dataset.preset);
  });

  async function applyPreset(name) {
    try {
      const d = await call('/api/kelola/preset', { json: { name } });
      S.settings = d.settings; S.version = d.version; S.personas = d.personas;
      fillForm();
      toast('Mode ' + name + ' dipakai');
      refreshSoon();
    } catch (e) { toast(e.message, true); }
  }

  // ── persona cards ──
  function renderPersonas() {
    $('#dlText').innerHTML = (S.suggested_text_models || []).map(m => `<option value="${esc(m)}">`).join('');
    $('#dlVision').innerHTML = (S.suggested_vision_models || []).map(m => `<option value="${esc(m)}">`).join('');
    const cost7 = Object.fromEntries((S.usage?.by_persona || []).map(x => [x.persona, x]));
    $('#personas').innerHTML = S.personas.map(p => {
      const u = p.username;
      const c = cost7[u];
      const dep = (m) => DEPRECATED.has(m) ? ' <b class="dep">deprecated</b>' : '';
      return `<div class="pers${p.active ? '' : ' off'}" data-u="${esc(u)}">
        <div class="pers-h">
          <div class="pers-av" style="background:${esc(p.color)}">${esc(p.avatar)}</div>
          <div><div class="pers-n">${esc(p.display)}</div><div class="pers-c">@${esc(u)}${c ? ` · 7 hari: ${usd(c.cost)} · ${c.calls} panggilan · ${c.images} gambar` : ''}</div></div>
          <div class="sp"></div>
          <label class="switch" title="Aktif"><input type="checkbox" data-pk="p.${esc(u)}.active" ${p.active ? 'checked' : ''} aria-label="${esc(p.display)} aktif"><span></span></label>
        </div>
        <label class="check"><input type="checkbox" data-pk="p.${esc(u)}.can_image" ${p.can_image ? 'checked' : ''}> Boleh membuat gambar (post bergambar &amp; story)</label>
        <div class="field">
          <label class="lbl">Peluang ikut berkomentar <b class="val" data-pshow="p.${esc(u)}.reply_prob">${pct(p.reply_prob)}</b></label>
          <input class="range" type="range" min="0" max="1" step="0.05" value="${p.reply_prob}" data-pk="p.${esc(u)}.reply_prob" aria-label="Peluang komentar ${esc(p.display)}">
        </div>
        <div class="field">
          <label class="lbl">Model teks${dep(p.text_model)}</label>
          <div class="mrow">
            <input class="inp" list="dlText" value="${esc(p.text_model)}" data-pk="p.${esc(u)}.text_model" spellcheck="false" aria-label="Model teks ${esc(p.display)}">
            <button class="btn sm" onclick="testModel(this)">Tes</button>
          </div>
          <div class="mtest"></div>
        </div>
        <div class="field">
          <label class="lbl">Model vision (kosong = tidak melihat foto)${dep(p.vision_model)}</label>
          <div class="mrow">
            <input class="inp" list="dlVision" value="${esc(p.vision_model)}" data-pk="p.${esc(u)}.vision_model" spellcheck="false" placeholder="tanpa vision" aria-label="Model vision ${esc(p.display)}">
            <button class="btn sm" onclick="testModel(this)">Tes</button>
          </div>
          <div class="mtest"></div>
        </div>
      </div>`;
    }).join('');
  }
  document.addEventListener('change', (ev) => {
    const el = ev.target.closest('[data-pk]');
    if (!el) return;
    const v = el.type === 'checkbox' ? el.checked : el.type === 'range' ? parseFloat(el.value) : el.value.trim();
    save({ [el.dataset.pk]: v }, el).then(() => {
      if (el.dataset.pk.endsWith('.active')) el.closest('.pers').classList.toggle('off', !el.checked);
    });
  });

  window.testModel = async (btn) => {
    const inp = btn.parentNode.querySelector('input');
    const out = btn.closest('.field').querySelector('.mtest');
    const model = inp.value.trim();
    if (!model) { out.textContent = 'Kosong: persona ini tidak memakai vision.'; out.className = 'mtest'; return; }
    btn.disabled = true;
    out.className = 'mtest';
    out.textContent = 'Mengetes…';
    try {
      const d = await call('/api/kelola/test-model', { json: { model } });
      out.className = 'mtest ' + (d.ok ? 'ok' : 'bad');
      out.textContent = d.ok ? `Jalan (${d.ms} ms)` : `Gagal: ${d.error}`;
    } catch (e) {
      out.className = 'mtest bad';
      out.textContent = 'Gagal: ' + e.message;
    }
    btn.disabled = false;
  };

  // ── prices ──
  function renderPrices() {
    const prices = { ...(S.settings.model_prices || {}) };
    S.personas.forEach(p => {
      [p.text_model, p.vision_model].forEach(m => { if (m && !prices[m]) prices[m] = [0.5, 1.0]; });
    });
    $('#priceTable').innerHTML = '<tr><th>Model</th><th class="r">Input</th><th class="r">Output</th></tr>' +
      Object.entries(prices).map(([m, [a, b]]) => `<tr data-m="${esc(m)}"><td>${esc(m)}</td>
        <td class="r"><input class="inp" type="number" min="0" step="0.01" value="${a}" aria-label="Harga input ${esc(m)}"></td>
        <td class="r"><input class="inp" type="number" min="0" step="0.01" value="${b}" aria-label="Harga output ${esc(m)}"></td></tr>`).join('');
  }
  window.savePrices = () => {
    const out = {};
    $$('#priceTable tr[data-m]').forEach(tr => {
      const [a, b] = $$('input', tr).map(i => parseFloat(i.value) || 0);
      out[tr.dataset.m] = [a, b];
    });
    save({ model_prices: out });
  };

  // ── estimates ──
  function renderEstimates() {
    const st = S.settings;
    const postsH = 60 / ((st.post_interval_min + st.post_interval_max) / 2);
    const imgH = postsH * st.post_image_prob;
    const storyH = 60 / ((st.story_interval_min + st.story_interval_max) / 2) * st.story_prob;
    const fmt = (x) => x >= 1 ? x.toFixed(1) : x.toFixed(2);
    $('#estPost').innerHTML = st.post_enabled
      ? `Saat app dibuka: sekitar <b>${fmt(postsH)} post/jam</b>, ${fmt(imgH)} di antaranya bergambar.`
      : 'Postingan AI mati.';
    $('#estStory').innerHTML = st.story_enabled
      ? `Saat app dibuka: sekitar <b>${fmt(storyH)} story/jam</b>. Total gambar tetap dibatasi ${st.image_daily_limit}/hari.`
      : 'Story AI mati.';
  }

  // ── stats ──
  function meter(el, used, limit) {
    const r = limit > 0 ? Math.min(1, used / limit) : 0;
    el.style.width = (r * 100) + '%';
    el.classList.toggle('warn', r >= 0.7 && r < 1);
    el.classList.toggle('crit', r >= 1);
  }
  function renderStats() {
    const st = S.status, t = S.usage.today, set = S.settings;
    $('#todayDate').textContent = t.day;
    $('#costToday').textContent = usd(st.cost_today);
    $('#costTodayIdr').textContent = '≈ ' + rp(st.cost_today) + ` · ${t.calls} panggilan · ${t.tokens_in + t.tokens_out} token`;
    $('#tImages').textContent = `${st.images_today} / ${st.image_daily_limit}`;
    meter($('#mImages'), st.images_today, st.image_daily_limit);
    $('#tAuto').textContent = `${st.auto_calls_today} / ${st.auto_call_daily_limit}`;
    meter($('#mAuto'), st.auto_calls_today, st.auto_call_daily_limit);
    $('#tInter').textContent = `${st.interactive_calls_today} / ${st.interactive_daily_limit}`;
    meter($('#mInter'), st.interactive_calls_today, st.interactive_daily_limit);
    $('#tBudget').textContent = set.daily_budget_usd > 0 ? `${usd(st.cost_today)} / ${usd(set.daily_budget_usd)}` : 'Tanpa batas';
    meter($('#mBudget'), st.cost_today, set.daily_budget_usd);

    // status pill + scheduler line
    const pill = $('#statusPill');
    pill.hidden = false;
    const sc = S.scheduler;
    if (!set.ai_enabled) { pill.className = 'pill off'; pill.textContent = 'AI dimatikan'; }
    else if (st.auto_block) { pill.className = 'pill hold'; pill.textContent = 'Ditahan'; }
    else { pill.className = 'pill on'; pill.textContent = 'AI aktif'; }
    let line = '';
    if (!set.ai_enabled) line = 'Semua aktivitas AI dimatikan. Tidak ada biaya API.';
    else if (st.auto_block) line = `Aktivitas otomatis ditahan: <b>${esc(st.auto_block)}</b>.` + (st.auto_block.includes('dibuka') ? ' Jalan lagi begitu Aura dibuka.' : '');
    else line = `Post berikutnya ${set.post_enabled ? '<b>' + mins(sc.next_post_in) + '</b>' : '<b>mati</b>'} · story berikutnya ${set.story_enabled ? '<b>' + mins(sc.next_story_in) + '</b>' : '<b>mati</b>'}.`;
    if (st.last_seen_sec != null) line += ` App terakhir dibuka ${ago(Date.now() / 1000 - st.last_seen_sec)}.`;
    $('#schedLine').innerHTML = line;
    const lr = (x, n) => x ? `${n} terakhir: ${x.ok ? '✅' : '—'} ${esc(x.persona || '')} ${esc(x.info)} · ${ago(x.at)}` : '';
    $('#lastRuns').innerHTML = [lr(sc.last_post, 'Post'), lr(sc.last_story, 'Story')].filter(Boolean).join('<br>');

    renderChart(S.usage.history);
    renderHBars('#byKind', t.by_kind.map(k => ({ label: k.label, v: k.cost, sub: `${k.calls}×` })), 'Belum ada panggilan hari ini');
    const pmap = Object.fromEntries(S.personas.map(p => [p.username, p.display]));
    renderHBars('#byPersona', S.usage.by_persona.map(p => ({ label: pmap[p.persona] || (p.persona === '-' ? 'Sistem' : p.persona), v: p.cost, sub: `${p.calls}×` })), 'Belum ada data');
    $('#byModel').innerHTML = S.usage.by_model.length
      ? '<tr><th>Model</th><th class="r">Panggilan</th><th class="r">Gagal</th><th class="r">Token</th><th class="r">Biaya</th></tr>' +
        S.usage.by_model.map(m => `<tr><td>${esc(m.model)}${DEPRECATED.has(m.model) ? ' <b class="dep">deprecated</b>' : ''}</td>
          <td class="r">${m.calls}</td><td class="r">${m.calls - m.ok}</td><td class="r">${(m.tokens_in + m.tokens_out).toLocaleString('id-ID')}</td><td class="r">${usd(m.cost)}</td></tr>`).join('')
      : '<tr><td class="empty-s">Belum ada data 7 hari terakhir.</td></tr>';
    const errs = S.usage.errors || [];
    $('#errBox').innerHTML = errs.length ? `<div class="errs"><b>Error 24 jam terakhir</b><br>${errs.slice(0, 6).map(e =>
      `${esc(e.model)} · ${e.count}× · ${esc(e.err || '')}`).join('<br>')}</div>` : '';
    renderStorage();
  }

  function renderHBars(sel, rows, empty) {
    const el = $(sel);
    if (!rows.length) { el.innerHTML = `<div class="empty-s">${empty}</div>`; return; }
    const max = Math.max(...rows.map(r => r.v), 1e-9);
    el.innerHTML = rows.map(r => `<div class="hb"><div class="hb-l" title="${esc(r.label)}">${esc(r.label)}</div>
      <div class="hb-t"><div class="hb-f" style="width:${Math.max(r.v > 0 ? 3 : 0, (r.v / max) * 100)}%"></div></div>
      <div class="hb-v">${usd(r.v)} <span class="muted">${r.sub}</span></div></div>`).join('');
  }

  // 14-day columns: single series (no legend), value label only on the peak,
  // tooltip on hover/focus for every column, table view for the rest.
  function renderChart(hist) {
    const box = $('#chart');
    const W = box.clientWidth || 600, H = box.clientHeight || 190;
    const padL = 44, padR = 8, padT = 18, padB = 24;
    const iw = W - padL - padR, ih = H - padT - padB;
    const max = Math.max(...hist.map(h => h.cost), 0);
    const top = niceMax(max);
    const band = iw / hist.length;
    const bw = Math.min(24, band * 0.6);
    const y = (v) => padT + ih - (top ? (v / top) * ih : 0);
    let g = '<g class="grid">';
    [0, 0.5, 1].forEach(f => { const yy = padT + ih - f * ih; g += `<line x1="${padL}" x2="${W - padR}" y1="${yy}" y2="${yy}"/>`; });
    g += '</g><g class="axis">';
    [0, 0.5, 1].forEach(f => { const yy = padT + ih - f * ih; g += `<text x="${padL - 8}" y="${yy + 3.5}" text-anchor="end">${usd(top * f)}</text>`; });
    hist.forEach((h, i) => {
      if (i % 2 === (hist.length - 1) % 2) {
        const x = padL + band * i + band / 2;
        g += `<text x="${x}" y="${H - 6}" text-anchor="middle">${h.day.slice(8)}/${h.day.slice(5, 7)}</text>`;
      }
    });
    g += '</g>';
    const peak = hist.reduce((m, h, i) => h.cost > hist[m].cost ? i : m, 0);
    let bars = '';
    hist.forEach((h, i) => {
      const x = padL + band * i + (band - bw) / 2;
      const yy = y(h.cost);
      const hh = Math.max(0, padT + ih - yy);
      const r = Math.min(4, hh, bw / 2);
      const d = hh <= 0.5
        ? `M${x},${padT + ih - 1.5}h${bw}v1.5h-${bw}z`
        : `M${x},${padT + ih}V${yy + r}Q${x},${yy} ${x + r},${yy}H${x + bw - r}Q${x + bw},${yy} ${x + bw},${yy + r}V${padT + ih}Z`;
      bars += `<rect class="hit" x="${padL + band * i}" y="${padT}" width="${band}" height="${ih}" tabindex="0" data-i="${i}" aria-label="${h.day}: ${usd(h.cost)}"/>`;
      bars += `<path class="bar${h.cost > 0 ? '' : ' zero'}" d="${d}"/>`;
      if (i === peak && h.cost > 0) bars += `<text class="vlab" x="${x + bw / 2}" y="${yy - 6}" text-anchor="middle">${usd(h.cost)}</text>`;
    });
    box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${g}${bars}</svg>`;
    const tip = $('#tip');
    const show = (el) => {
      const h = hist[+el.dataset.i];
      const rc = el.getBoundingClientRect();
      tip.innerHTML = `<b>${h.day}</b><br>${usd(h.cost)} (${rp(h.cost)})<br>${h.calls} panggilan · ${h.images} gambar`;
      tip.hidden = false;
      const tw = tip.offsetWidth;
      tip.style.left = Math.min(window.innerWidth - tw - 8, Math.max(8, rc.left + rc.width / 2 - tw / 2)) + 'px';
      tip.style.top = (rc.top + 10) + 'px';
    };
    $$('.hit', box).forEach(el => {
      el.addEventListener('pointerenter', () => show(el));
      el.addEventListener('focus', () => show(el));
      el.addEventListener('pointerleave', () => { tip.hidden = true; });
      el.addEventListener('blur', () => { tip.hidden = true; });
    });
    $('#histTable').innerHTML = '<div class="tbl-wrap"><table class="tbl"><tr><th>Tanggal</th><th class="r">Panggilan</th><th class="r">Gambar</th><th class="r">Biaya</th><th class="r">Rupiah</th></tr>' +
      [...hist].reverse().map(h => `<tr><td>${h.day}</td><td class="r">${h.calls}</td><td class="r">${h.images}</td><td class="r">${usd(h.cost)}</td><td class="r">${rp(h.cost)}</td></tr>`).join('') + '</table></div>';
  }
  function niceMax(v) {
    if (v <= 0) return 0.01;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  }
  window.toggleTable = () => {
    const t = $('#histTable');
    t.hidden = !t.hidden;
    $('#tableBtn').textContent = t.hidden ? 'Lihat tabel' : 'Sembunyikan tabel';
    $('#tableBtn').setAttribute('aria-expanded', String(!t.hidden));
  };
  window.addEventListener('resize', () => { if (S) renderChart(S.usage.history); });

  // ── storage / maintenance ──
  function renderStorage() {
    const s = S.storage, c = S.counts;
    $('#storageKv').innerHTML = `
      <div><small>Database</small><b>${bytes(s.db_bytes + s.wal_bytes)}</b></div>
      <div><small>Gambar (file)</small><b>${bytes(s.media_bytes)}</b></div>
      <div><small>Postingan</small><b>${c.posts}</b> <span class="muted sm">(${c.my_posts} milikmu)</span></div>
      <div><small>Story · Komentar</small><b>${c.stories} · ${c.comments}</b></div>`;
    const m = s.migration || {};
    let html = '';
    if (c.legacy_images > 0 || m.state === 'running') {
      html = `<div class="mig">Memindahkan gambar lama ke file: <b>${m.done || 0}/${m.total || c.legacy_images}</b>${m.state === 'running' ? ' (berjalan)' : ''}.
        ${m.state === 'error' ? `<br>Berhenti: ${esc(m.error)}. <button class="btn sm" onclick="maint('migrate_media')">Coba lagi</button>` : ''}</div>`;
    } else if (s.backup) {
      html = `<div class="mig">Gambar lama sudah dipindah ke file WebP. Salinan database sebelum pemindahan masih disimpan di server:<br><code>${esc(s.backup)}</code><br>
        Kalau Aura sudah terlihat normal, salinan itu boleh dihapus untuk menghemat ruang.
        <div class="row"><button class="btn sm ghost" onclick="twoClickDel(this)">Hapus salinan lama</button></div></div>`;
    }
    $('#migrationBox').innerHTML = html;
  }
  window.twoClickDel = (btn) => twoClick(btn, 'Hapus salinan lama', () => maint('delete_backup'));
  window.maint = async (action) => {
    try {
      await call('/api/kelola/maintenance', { json: { action } });
      toast(action === 'vacuum' ? 'Database dirapikan' : action === 'delete_backup' ? 'Salinan dihapus' : 'Dimulai');
      refreshSoon();
    } catch (e) { toast(e.message, true); }
  };
  window.resetAll = (btn) => {
    twoClick(btn, 'Kembalikan setelan awal', async () => {
      try {
        const d = await call('/api/kelola/reset', { json: {} });
        S.settings = d.settings; S.personas = d.personas; S.version = d.version;
        fillForm();
        toast('Setelan awal dipakai');
      } catch (e) { toast(e.message, true); }
    });
  };
  window.runNow = async (what) => {
    try {
      await call('/api/kelola/run', { json: { what } });
      toast(what === 'post' ? 'Sedang membuat post…' : 'Sedang membuat story…');
      setTimeout(refresh, 15000);
    } catch (e) { toast(e.message, true); }
  };

  document.addEventListener('visibilitychange', () => { if (!document.hidden && S) refresh(); });
  load();
})();
