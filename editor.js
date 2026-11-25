// Editor (visual): live 9:16 preview of your cut, filmstrip timeline you drag, camera/game boxes you drag on the frame, caption you drag on the preview.
// Ideas read from SupoClip's editor (sequence timeline with filmstrips, canvas preview, drag-to-frame) and OpenCut (split = two pieces).
// Endpoints used: GET /library, GET /clips/<id>/edit, POST /clips/reedit, GET /status/<job>, GET /media/<id>.
(function () {
  const $ = id => document.getElementById(id);
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  async function req(path, body) {
    const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'Request failed');
    return j;
  }

  // ---------- catalogues (all shown as pictures, not lists)
  const STYLES = {
    karaoke: ['Karaoke', 'color:#fff;font-weight:800', 'color:#ffe14a'], tiktok: ['TikTok', 'color:#fff;font-weight:900;-webkit-text-stroke:2px #000;paint-order:stroke fill', 'color:#25f4ee'],
    pill: ['Pill', 'color:#fff;font-weight:700;background:#000a;border-radius:99px;padding:2px 10px', 'background:#ff3d6e;border-radius:99px;padding:2px 8px'],
    oneword: ['One word', 'color:#fff;font-weight:900;font-size:22px', ''], cine: ['Cinematic', 'color:#eee;font-weight:300;letter-spacing:.25em;font-size:11px', 'color:#fff;font-weight:700'],
    boxed: ['Boxed', 'color:#fff;font-weight:800', 'background:#ffe14a;color:#000;padding:0 5px'], outlined: ['Outlined', 'color:transparent;-webkit-text-stroke:1.5px #fff;font-weight:900', 'color:#ffe14a;-webkit-text-stroke:0'],
    comic: ['Comic', 'color:#ffe14a;font-weight:900;font-style:italic;-webkit-text-stroke:2px #c00;paint-order:stroke fill', 'color:#fff'], gta: ['GTA Neon', 'color:#ff4fa3;font-weight:900;text-shadow:0 0 8px #ff4fa3', 'color:#4ff0ff;text-shadow:0 0 8px #4ff0ff'],
    bold: ['Impact', 'color:#fff;font-weight:900;text-transform:uppercase;font-family:Impact,sans-serif', 'color:#ffe14a'], hormozi: ['Hormozi', 'color:#fff;font-weight:900;text-transform:uppercase', 'color:#3ddc84'],
    mrbeast: ['MrBeast', 'color:#fff;font-weight:900;-webkit-text-stroke:3px #000;paint-order:stroke fill;text-transform:uppercase', 'color:#ff3d3d'], clean: ['Clean', 'color:#fff;font-weight:500', 'font-weight:800'],
  };
  const LAYOUTS = [['stack', 'Face + game'], ['bottom', 'Game + face'], ['blur', 'Blurred'], ['fill', 'Fill'], ['game', 'Game only'], ['pip_tl', 'Cam ↖'], ['pip_tr', 'Cam ↗'], ['pip_bl', 'Cam ↙'], ['pip_br', 'Cam ↘'], ['circle', 'Circle'], ['side', 'Side by side']];
  function layoutSvg(id) {
    const g = '#4a4a5a', c = '#ff3d6e';
    const r = (x, y, w, h, f) => '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="2" fill="' + f + '"/>';
    const body = {
      stack: r(0, 0, 36, 22, c) + r(0, 22, 36, 42, g), bottom: r(0, 0, 36, 42, g) + r(0, 42, 36, 22, c), blur: r(0, 0, 36, 64, '#2a2a38') + r(0, 18, 36, 28, g), fill: r(0, 0, 36, 64, g), game: r(0, 0, 36, 64, g) + '<text x="18" y="36" font-size="9" fill="#fff" text-anchor="middle">🎮</text>',
      pip_tl: r(0, 0, 36, 64, g) + r(3, 3, 14, 14, c), pip_tr: r(0, 0, 36, 64, g) + r(19, 3, 14, 14, c), pip_bl: r(0, 0, 36, 64, g) + r(3, 47, 14, 14, c), pip_br: r(0, 0, 36, 64, g) + r(19, 47, 14, 14, c),
      circle: r(0, 0, 36, 64, g) + '<circle cx="18" cy="48" r="9" fill="' + c + '"/>', side: r(0, 0, 18, 64, c) + r(18, 0, 18, 64, g),
    }[id] || r(0, 0, 36, 64, g);
    return '<svg viewBox="0 0 36 64" width="30" height="53">' + body + '</svg>';
  }
  const ASPECTS = [['vertical', '9:16'], ['square', '1:1'], ['portrait', '4:5'], ['threefour', '3:4'], ['landscape', '16:9']];
  const HOOKS = [['impact', 'Impact'], ['neon', 'Neon'], ['banner', 'Banner'], ['box', 'Box']];
  const PRESETS = [['shorts', 'YouTube Shorts', 180], ['tiktok', 'TikTok', 600], ['reels', 'Instagram Reels', 90]];
  const FONTS = ['Arial', 'Arial Black', 'Impact', 'Verdana', 'Georgia', 'Nirmala UI', 'DejaVu Sans', 'Liberation Sans'];
  const COLORS = ['#FFFFFF', '#FFE14A', '#FF3D6E', '#4FF0FF', '#3DDC84', '#FF8A00', '#A66BFF', '#000000'];
  const SIZES = [['S', 44], ['M', 58], ['L', 74], ['XL', 92]];
  const LOOKS = [['Normal', 0, 1, 1, 0], ['Vivid', .02, 1.15, 1.35, .3], ['Bright', .1, 1.05, 1.1, .1], ['Moody', -.08, 1.2, .85, .2], ['Sharp', 0, 1.1, 1, .9]];
  const VOLUMES = [['Mute', 0], ['50%', .5], ['100%', 1], ['150%', 1.5]];
  const CAPTION_BRAND_KEYS = ['caption_font', 'caption_size', 'caption_color', 'caption_active', 'caption_outline', 'caption_max_words'];
  const RECIPES = {
    gaming: { label: 'Gaming neon', caption_style: 'gta', caption_max_words: 3, hook_style: 'neon' },
    dialogue: { label: 'Clean dialogue', caption_style: 'clean', caption_max_words: 5, hook_style: 'box' },
    reaction: { label: 'Big reaction', caption_style: 'bold', caption_max_words: 2, hook_style: 'impact' },
  };

  // ---------- state: everything editable lives in `st`, so undo/redo is a snapshot
  let sortBest = false, clips = [], file = '', info = null, st = null, original = null, undo = [], redo = [], tab = 'captions';
  let vt = 0, playing = false, curPiece = 0, token = 0, sel = 0;
  let captionProfiles = {}, profilesReady = false;
  const thumbs = new Map();
  const snap = () => JSON.stringify(st);
  const dirty = () => original !== null && snap() !== original;
  const draftKey = () => 'bloom-editor-draft-' + file;
  function draftSave() { try { if (dirty()) localStorage.setItem(draftKey(), snap()); else localStorage.removeItem(draftKey()); } catch (e) { /* ignore */ } }
  function commit(change) { undo.push(snap()); if (undo.length > 80) undo.shift(); redo = []; change(); afterChange(); }
  function jump(stack, other) { if (!stack.length) return; other.push(snap()); st = JSON.parse(stack.pop()); vt = Math.min(vt, length()); afterChange(); }
  function afterChange() { drawPane(); drawTranscript(); drawTimeline(); updateButtons(); draftSave(); paint(); }
  // a drag is one undo step: snapshot at pointer-down, keep it only if something moved
  let dragSnap = null;
  const dragStart = () => { dragSnap = snap(); };
  const dragEnd = () => { if (dragSnap !== null && dragSnap !== snap()) { undo.push(dragSnap); redo = []; if (undo.length > 80) undo.shift(); } dragSnap = null; afterChange(); };

  // ---------- pieces: ordered ranges of the ORIGINAL video; words keep original-video times
  const plen = ps => ps.reduce((n, p) => n + (p.end - p.start), 0);
  const length = () => plen(st.pieces);
  function rel(ps) {
    const out = []; let off = 0;
    ps.forEach((p, piece) => { st.words.forEach((w, i) => { if (w.b > p.start && w.a < p.end) out.push({ i, piece, start: off + Math.max(w.a, p.start) - p.start, end: off + Math.min(w.b, p.end) - p.start, text: w.text }); }); off += p.end - p.start; });
    return out.sort((a, b) => a.start - b.start);
  }
  function locate(t) {
    let off = 0;
    for (let i = 0; i < st.pieces.length; i++) { const l = st.pieces[i].end - st.pieces[i].start; if (t < off + l || i === st.pieces.length - 1) return { i, src: st.pieces[i].start + clamp(t - off, 0, l) }; off += l; }
    return { i: 0, src: st.pieces[0].start };
  }
  const outTime = (i, src) => { let off = 0; for (let k = 0; k < i; k++) off += st.pieces[k].end - st.pieces[k].start; return off + clamp(src - st.pieces[i].start, 0, st.pieces[i].end - st.pieces[i].start); };
  const note = t => { const n = $('ed-note'); if (n) n.textContent = t || ''; };
  const fmt = s => Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0') + '.' + String(Math.floor((s % 1) * 10));

  // ---------- page skeleton
  function build() {
    const sec = document.createElement('section');
    sec.id = 'clip-editor-view'; sec.hidden = true;
    sec.innerHTML = '<section class="library-heading"><h2>Clip editor</h2><span class="ed-note" id="ed-note" role="status"></span></section>' +
      '<div class="ed-grid"><aside class="ed-list panel"><button type="button" class="mini-btn" id="ed-sort">Sort: newest</button><div id="ed-list"></div></aside>' +
      '<div class="ed-center panel"><div class="ed-stage" id="ed-stage"><canvas id="ed-canvas" width="540" height="960"></canvas><div class="ed-safe" id="ed-safe" hidden></div><div class="ed-cap" id="ed-cap" title="Drag up or down to move the captions"></div></div>' +
      '<div class="ed-bar"><button class="mini-btn primary" id="ed-play" aria-label="Play or pause">▶</button><span id="ed-clock" class="muted">0:00.0 / 0:00.0</span><button class="mini-btn" id="ed-undo" disabled>↶</button><button class="mini-btn" id="ed-redo" disabled>↷</button>' +
      '<label class="ed-chk"><input type="checkbox" id="ed-safe-on"> Safe area</label></div></div>' +
      '<div class="ed-side panel"><div class="ed-tabs" id="ed-tabs"></div><div class="ed-pane" id="ed-pane"></div>' +
      '<div class="ed-export"><label class="ed-chk"><input type="radio" name="ed-scope" value="one" checked> Only this clip</label><label class="ed-chk"><input type="radio" name="ed-scope" value="video"> All clips of this video <small id="ed-count"></small></label>' +
      '<button class="mini-btn primary" id="ed-export" disabled>Export changes</button><button class="mini-btn" id="ed-reset" disabled>Reset</button><button class="mini-btn" id="ed-export-tracks" hidden>Download editing tracks</button><button class="mini-btn" id="ed-reaction-gif" disabled>Reaction GIF</button></div></div></div>' +
      '<div class="panel ed-tl"><div class="ed-tools"><button type="button" class="mini-btn" id="ed-split">✂ Split</button><button type="button" class="mini-btn" data-pa="dup">⧉ Duplicate</button><button type="button" class="mini-btn" data-pa="left">◀</button><button type="button" class="mini-btn" data-pa="right">▶</button><button type="button" class="mini-btn warn" data-pa="drop">🗑 Remove</button><span class="muted" id="ed-tl-note"></span></div>' +
      '<div class="ed-tools ed-timing-tools"><label class="ed-chk"><input type="checkbox" id="ed-snap" checked> Snap to words</label><button type="button" id="ed-in" class="mini-btn">Set in</button><button type="button" id="ed-out" class="mini-btn">Set out</button></div>' +
      '<div class="ed-track"><span>Clip</span><div class="ed-lane" id="ed-lane"></div></div><div class="ed-track"><span>Words</span><div class="ed-lane ed-capl" id="ed-capl"></div></div></div>' +
      '<div class="panel ed-words"><h3>Transcript</h3><div id="ed-fixask" class="ed-fixask" hidden></div><div id="ed-words" class="ed-wordlist"></div>' +
      '<div class="ed-gloss"><div class="ed-gloss-head"><b>Your words</b><small>Fixed once, spelled right in every new clip</small></div><div id="ed-gloss" class="ed-gloss-list"></div>' +
      '<div class="ed-gloss-add"><input id="ed-gl-from" placeholder="Written as (pulis)" maxlength="60"><span>→</span><input id="ed-gl-to" placeholder="Should be (police)" maxlength="60"><button type="button" class="mini-btn" id="ed-gl-add">Add</button></div></div></div>' +
      '<video id="ed-src" preload="auto" playsinline style="display:none"></video>';
    $('library-view').after(sec);
    $('ed-tabs').innerHTML = [['captions', 'Captions'], ['framing', 'Framing'], ['audio', 'Audio'], ['effects', 'Effects']].map(([k, n]) => '<button type="button" data-tab="' + k + '">' + n + '</button>').join('');
    $('ed-tabs').onclick = e => { const b = e.target.closest('[data-tab]'); if (b) { tab = b.dataset.tab; drawPane(); paint(); } };
    $('ed-sort').onclick = () => { sortBest = !sortBest; $('ed-sort').textContent = 'Sort: ' + (sortBest ? 'best first' : 'newest'); loadList(); };
    $('ed-undo').onclick = () => jump(undo, redo); $('ed-redo').onclick = () => jump(redo, undo);
    $('ed-reset').onclick = () => commit(() => { st = JSON.parse(original); });
    $('ed-safe-on').onchange = e => { $('ed-safe').hidden = !e.target.checked; };
    $('ed-export').onclick = exportNow; $('ed-export-tracks').onclick = exportTracks; $('ed-play').onclick = togglePlay;
    $('ed-reaction-gif').onclick = async () => {
      if (!file) return;
      if (dirty()) { note('Export your changes first to include them in the GIF.'); return; }
      const button = $('ed-reaction-gif');
      button.disabled = true;
      try {
        const response = await fetch('/reaction-gif/' + encodeURIComponent(file) + '?at=' + vt.toFixed(3));
        if (!response.ok) throw new Error('Could not make the reaction GIF.');
        const objectUrl = URL.createObjectURL(await response.blob());
        const download = document.createElement('a');
        download.href = objectUrl; download.download = 'BloomClipping-reaction.gif'; download.click();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 2000);
      } catch (error) {
        note(error.message);
      } finally {
        button.disabled = false;
      }
    };
    $('ed-list').onclick = e => { const c = e.target.closest('[data-clip]'); if (c) openClip(c.dataset.clip); };
    $('ed-split').onclick = splitHere;
    $('ed-in').onclick = () => setPieceBoundary('start');
    $('ed-out').onclick = () => setPieceBoundary('end');
    sec.addEventListener('click', onClick); sec.addEventListener('change', onChange); drawGloss();
    document.addEventListener('keydown', e => {
      if (sec.hidden || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName || '') || e.target.isContentEditable) return;
      const k = e.key.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && k === 'z') { e.preventDefault(); e.shiftKey ? jump(redo, undo) : jump(undo, redo); }
      else if ((e.ctrlKey || e.metaKey) && k === 'y') { e.preventDefault(); jump(redo, undo); }
      else if (e.key === ' ') { e.preventDefault(); togglePlay(); }
      else if (k === 's' && !e.ctrlKey && !e.metaKey) splitHere();
      else if (e.key === 'ArrowLeft') seekTo(vt - (e.shiftKey ? 1 : 0.1));
      else if (e.key === 'ArrowRight') seekTo(vt + (e.shiftKey ? 1 : 0.1));
    });
    wireStage(); wireLane();
  }

  async function loadList() {
    try {
      const lib = await req('/library');
      clips = (Array.isArray(lib) ? lib : lib.clips || lib.items || []).slice().sort((a, b) => sortBest ? ((b.meta && b.meta.score) || 0) - ((a.meta && a.meta.score) || 0) : (b.created || 0) - (a.created || 0));
    } catch (e) { clips = []; }
    $('ed-list').innerHTML = clips.length ? clips.map(c => '<button type="button" class="ed-clip' + (c.id === file ? ' on' : '') + '" data-clip="' + c.id + '"><img loading="lazy" src="/cover/' + c.id + '" alt=""><span>' + esc(String(c.title).slice(0, 44)) + '</span></button>').join('') : '<p class="muted">No clips yet. Make some first.</p>';
  }

  async function openClip(id) {
    if (dirty() && !confirm('Leave this clip? Your unsaved changes stay as a draft and come back when you reopen it.')) return;
    note('Loading…');
    try { info = await req('/clips/' + id + '/edit'); } catch (e) { note(e.message); return; }
    file = info.file;
    const s = info.settings || {};
    const base = info.origin || info.source;
    st = {
      caption_style: STYLES[s.caption_style] ? s.caption_style : 'karaoke', captions: s.captions !== false, caption_y: s.caption_y || 1450, layout: s.layout || 'stack', aspect: s.aspect || 'vertical',
      resolution: Number(s.resolution || 1080), fps: Number(s.fps || 30), voice_volume: s.voice_volume == null ? 1 : Number(s.voice_volume), caption_font: s.caption_font || '', caption_size: s.caption_size || '',
      caption_color: s.caption_color || '', caption_active: s.caption_active || '', caption_outline: s.caption_outline || '', caption_max_words: s.caption_max_words || '',
      hook: s.hook || '', hook_enabled: s.hook_enabled !== false, hook_style: s.hook_style || 'impact', fade_inout: !!s.fade_inout, top: Number(s.top || 0.32),
      cam: s.cam || { x: 0, y: 0, w: .3, h: .3 }, game: s.game || { x: 0, y: 0, w: 1, h: 1 },
      cam_brightness: s.cam_brightness == null ? 0 : s.cam_brightness, cam_contrast: s.cam_contrast == null ? 1 : s.cam_contrast, cam_saturation: s.cam_saturation == null ? 1 : s.cam_saturation, cam_clarity: s.cam_clarity == null ? 0 : s.cam_clarity,
      censor_mode: s.censor_mode || 'off', censor_words: s.censor_words || '', clip_progress: s.clip_progress === true, loop_end: s.loop_end === true,
      effect_cues: (s.effect_cues || []).map(cue => ({ ...cue })),
      pieces: (s.segments && s.segments.length ? s.segments : [{ start: Number(s.start || 0), end: Number(s.end || 0) }]).map(p => ({ start: Number(p.start), end: Number(p.end) })), words: [], base: base.duration || 0,
    };
    const seen = new Set();
    (s.words || []).forEach(w => { let off = 0; for (const p of st.pieces) { const l = p.end - p.start; if (w.start < off + l) { const a = p.start + (w.start - off), b = p.start + (Math.min(w.end, off + l) - off), k = a.toFixed(2) + w.text; if (!seen.has(k)) { seen.add(k); st.words.push({ a, b, text: w.text }); } break; } off += l; } });
    for (const word of s.context_words || []) {
      if (st.pieces.some(piece => word.start < piece.end && word.end > piece.start)) continue;
      st.words.push({ a: word.start, b: word.end, text: word.text });
    }
    original = snap(); undo = []; redo = []; sel = 0;
    try { const d = localStorage.getItem(draftKey()); if (d) { const dd = JSON.parse(d); if (dd && Array.isArray(dd.pieces) && dd.cam && confirm('Restore your unsaved changes for this clip?')) { st = dd; } else if (!dd || !Array.isArray(dd.pieces) || !dd.cam) localStorage.removeItem(draftKey()); } } catch (e) { /* ignore */ }
    const v = $('ed-src'); v.src = '/media/' + base.id; v.muted = false;
    vt = 0; playing = false; curPiece = 0; $('ed-play').textContent = '▶';
    $('ed-count').textContent = info.video_clips > 1 ? '(' + info.video_clips + ')' : '';
    note(''); loadList();
    v.onloadeddata = () => { seekTo(0); afterChange(); };
    v.onseeked = () => { if (!playing) { paint(); if (tab === 'framing') drawFrame(); } };
    afterChange();
  }

  // ---------- playback: the source video plays piece after piece, so cuts are live
  function seekTo(t) {
    if (!st) return; vt = clamp(t, 0, length());
    const l = locate(vt); curPiece = l.i; const v = $('ed-src'); try { v.currentTime = l.src; } catch (e) { /* not ready */ }
    paint(); markPlayhead();
  }
  function togglePlay() {
    if (!st) return; const v = $('ed-src');
    if (playing) { playing = false; v.pause(); $('ed-play').textContent = '▶'; return; }
    if (vt >= length() - 0.05) seekTo(0);
    playing = true; v.volume = clamp(st.voice_volume, 0, 1); v.play().catch(() => { playing = false; }); $('ed-play').textContent = '❚❚'; loop();
  }
  function loop() {
    if (!playing || !st) return; const v = $('ed-src'), p = st.pieces[curPiece];
    if (v.currentTime >= p.end - 0.03) {
      if (curPiece < st.pieces.length - 1) { curPiece++; v.currentTime = st.pieces[curPiece].start; }
      else { playing = false; v.pause(); $('ed-play').textContent = '▶'; vt = length(); paint(); markPlayhead(); return; }
    }
    vt = outTime(curPiece, v.currentTime); paint(); markPlayhead(); requestAnimationFrame(loop);
  }

  // ---------- canvas compositor (approximate look of the 9:16 result, using your camera and game boxes)
  function cover(ctx, v, r, dx, dy, dw, dh) {
    const sw = v.videoWidth, sh = v.videoHeight; if (!sw) return;
    const sx = r.x * sw, sy = r.y * sh, rw = r.w * sw, rh = r.h * sh, k = Math.max(dw / rw, dh / rh), cw = dw / k, ch = dh / k;
    ctx.drawImage(v, sx + (rw - cw) / 2, sy + (rh - ch) / 2, cw, ch, dx, dy, dw, dh);
  }
  function paint() {
    const c = $('ed-canvas'); if (!c || !st) return; const v = $('ed-src'), ctx = c.getContext('2d'), W = c.width, H = c.height, full = { x: 0, y: 0, w: 1, h: 1 };
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    if (v.readyState >= 2 && v.videoWidth) {
      const top = clamp(st.top, .2, .5) * H, L = st.layout, cam = st.cam, game = st.game, ar = (cam.h * v.videoHeight) / Math.max(1, cam.w * v.videoWidth);
      if (L === 'stack') { cover(ctx, v, cam, 0, 0, W, top); cover(ctx, v, game, 0, top, W, H - top); }
      else if (L === 'bottom') { cover(ctx, v, game, 0, 0, W, H - top); cover(ctx, v, cam, 0, H - top, W, top); }
      else if (L === 'blur') { ctx.save(); ctx.filter = 'blur(14px) brightness(.7)'; cover(ctx, v, full, -20, -20, W + 40, H + 40); ctx.restore(); const h = W * v.videoHeight / v.videoWidth; ctx.drawImage(v, 0, (H - h) / 2, W, h); }
      else if (L === 'fill') cover(ctx, v, full, 0, 0, W, H);
      else if (L === 'game') cover(ctx, v, game, 0, 0, W, H);
      else if (L === 'side') { cover(ctx, v, cam, 0, 0, W / 2, H); cover(ctx, v, game, W / 2, 0, W / 2, H); }
      else if (L === 'circle') { cover(ctx, v, game, 0, 0, W, H); const d = W * .46, cy = H - d / 2 - 90; ctx.save(); ctx.beginPath(); ctx.arc(W / 2, cy, d / 2, 0, 7); ctx.clip(); cover(ctx, v, cam, W / 2 - d / 2, cy - d / 2, d, d); ctx.restore(); ctx.lineWidth = 5; ctx.strokeStyle = '#fff'; ctx.beginPath(); ctx.arc(W / 2, cy, d / 2, 0, 7); ctx.stroke(); }
      else { cover(ctx, v, game, 0, 0, W, H); const w = W * .4, h = Math.min(H * .3, w * ar), m = 24, x = L.endsWith('r') ? W - w - m : m, y = L.startsWith('pip_t') ? m + 120 : H - h - m - 120; cover(ctx, v, cam, x, y, w, h); ctx.lineWidth = 4; ctx.strokeStyle = '#fff'; ctx.strokeRect(x, y, w, h); }
    }
    drawCaption(); markPlayhead();
  }
  function drawCaption() {
    const cap = $('ed-cap'); if (!st.captions || tab === 'framing') { cap.innerHTML = ''; cap.style.display = 'none'; return; }
    const rw = rel(st.pieces), idx = rw.findIndex(w => vt >= w.start && vt < w.end);
    const [, base, hi] = STYLES[st.caption_style] || STYLES.karaoke;
    cap.style.display = ''; cap.style.top = clamp(100 * st.caption_y / 1920, 15, 92) + '%';
    cap.style.fontFamily = st.caption_font ? '"' + st.caption_font + '",sans-serif' : '';
    cap.style.fontSize = ((st.caption_size || 58) / 58) * 0.95 + 'em';
    if (idx < 0) { cap.innerHTML = '<span class="ghost">⇕ drag captions</span>'; return; }
    const per = Number(st.caption_max_words) || (st.caption_style === 'oneword' ? 1 : 4), from = idx - (idx % per);
    cap.innerHTML = rw.slice(from, from + per).map((w, i) => '<span style="' + base + ';' + (st.caption_color ? 'color:' + st.caption_color + ';' : '') + (from + i === idx ? hi + ';' + (st.caption_active ? 'color:' + st.caption_active : '') : '') + '">' + esc(w.text) + '</span>').join(' ');
  }
  function wireStage() {
    const stage = $('ed-stage');
    stage.addEventListener('pointerdown', e => { if (!st || !e.target.closest('#ed-cap')) return; stage.setPointerCapture(e.pointerId); dragStart(); stage._drag = true; });
    stage.addEventListener('pointermove', e => { if (!stage._drag) return; const b = stage.getBoundingClientRect(); st.caption_y = Math.round(clamp((e.clientY - b.top) / b.height * 1920, 400, 1750) / 10) * 10; drawCaption(); });
    const end = () => { if (stage._drag) { stage._drag = false; dragEnd(); } };
    stage.addEventListener('pointerup', end); stage.addEventListener('pointercancel', end);
  }

  // ---------- timeline: source context stays visible beside the edit
  function context() {
    const first = st.pieces[0], last = st.pieces.at(-1);
    return { lead: Math.min(15, first.start), trail: Math.min(15, Math.max(0, st.base - last.end)) };
  }
  function syncContext() {
    const { lead, trail } = context();
    for (const [id, seconds] of [['ed-source-lead', lead], ['ed-source-trail', trail]]) {
      const item = $(id);
      item.hidden = seconds < 0.05;
      item.style.flex = seconds + ' 1 0';
      item.textContent = seconds.toFixed(1) + 's';
    }
    return { lead, span: length() + lead + trail };
  }
  function drawTimeline() {
    const lane = $('ed-lane'); if (!st) { lane.innerHTML = ''; return; }
    sel = clamp(sel, 0, st.pieces.length - 1); const total = length();
    const grey = (id, label) => '<div class="ed-context" id="' + id + '" title="' + label + '"></div>';
    lane.innerHTML = grey('ed-source-lead', 'Available source before the clip') + st.pieces.map((p, i) => '<div class="ed-piece' + (i === sel ? ' on' : '') + '" data-p="' + i + '" style="flex:' + (p.end - p.start) + ' 1 0"><div class="ed-film"></div><i class="ed-h l" data-h="' + i + ':start"></i><i class="ed-h r" data-h="' + i + ':end"></i><b>' + (p.end - p.start).toFixed(1) + 's</b></div>').join('') + grey('ed-source-trail', 'Available source after the clip') + '<div class="ed-ph" id="ed-ph"></div>';
    const { lead, span } = syncContext();
    const r = rel(st.pieces); $('ed-capl').innerHTML = r.map(w => '<span style="left:' + (100 * (lead + w.start) / span) + '%;width:' + Math.max(0.4, 100 * (w.end - w.start) / span) + '%" title="' + esc(w.text) + '">' + esc(w.text) + '</span>').join('');
    $('ed-tl-note').textContent = st.pieces.length + ' piece' + (st.pieces.length > 1 ? 's' : '') + ' · ' + total.toFixed(1) + ' s' + (fits(st.pieces, true) ? '' : ' ⚠ length');
    markPlayhead(); fillFilm();
  }
  function markPlayhead() {
    if (!st) return;
    const { lead, trail } = context(), ph = $('ed-ph');
    if (ph) ph.style.left = (100 * (lead + vt) / Math.max(0.01, length() + lead + trail)) + '%';
    $('ed-clock').textContent = fmt(vt) + ' / ' + fmt(length());
  }
  async function fillFilm() {
    const me = ++token, films = [...document.querySelectorAll('#ed-lane .ed-film')], jobs = [], base = info.origin || info.source;
    films.forEach((f, i) => { const w = f.getBoundingClientRect().width || 120, n = Math.max(1, Math.round(w / 96)), p = st.pieces[i]; for (let k = 0; k < n; k++) { const s = document.createElement('span'); f.append(s); jobs.push([s, p.start + (k + .5) / n * (p.end - p.start)]); } });
    const vid = document.createElement('video'); vid.muted = true; vid.preload = 'auto'; vid.src = '/media/' + base.id;
    await new Promise(r => { vid.onloadeddata = r; vid.onerror = r; setTimeout(r, 5000); });
    if (!vid.videoWidth) return;
    const c = document.createElement('canvas'); c.width = 96; c.height = 54; const x = c.getContext('2d');
    for (const [span, t] of jobs) {
      if (me !== token) return; const key = base.id + ':' + t.toFixed(1); let u = thumbs.get(key);
      if (!u) { vid.currentTime = t; await new Promise(r => { vid.onseeked = r; setTimeout(r, 2500); }); try { x.drawImage(vid, 0, 0, 96, 54); u = c.toDataURL('image/jpeg', .55); thumbs.set(key, u); } catch (e) { u = ''; } }
      if (u && span.isConnected) span.style.backgroundImage = 'url(' + u + ')';
    }
  }
  function fits(ps, quiet) {
    const t = plen(ps), say = m => { if (!quiet) note(m); return false; };
    if (ps.some(p => !(p.end - p.start >= 0.2) || p.start < 0 || p.end > st.base + 0.05)) return say('A piece must be at least 0.2 s and inside the saved video (' + st.base.toFixed(0) + ' s).');
    if (t < 3 || t > 180) return say('The clip must be 3 to 180 seconds in total (now ' + t.toFixed(1) + ' s).');
    if (ps.length > 16) return say('At most 16 pieces.');
    if (!quiet) note(''); return true;
  }
  function splitHere() {
    if (!st) return; const l = locate(vt), p = st.pieces[l.i];
    if (!(l.src > p.start + 0.1 && l.src < p.end - 0.1)) { note('Move the playhead inside a piece first.'); return; }
    commit(() => { st.pieces.splice(l.i, 1, { start: p.start, end: l.src }, { start: l.src, end: p.end }); sel = l.i + 1; });
  }
  function snapTime(value, type) {
    if (!$('ed-snap').checked) return value;
    let closest = value, distance = 0.16;
    for (const word of st.words) {
      const edge = type === 'start' ? word.a : word.b;
      const delta = Math.abs(value - edge);
      if (delta < distance) { closest = edge; distance = delta; }
    }
    return closest;
  }
  function setPieceBoundary(edge) {
    if (!st) return;
    const current = locate(vt);
    const next = st.pieces.map(piece => ({ ...piece }));
    next[current.i][edge] = snapTime(current.src, edge);
    if (!fits(next, false)) return;
    if (playing) togglePlay();
    commit(() => { st.pieces = next; sel = current.i; vt = Math.min(vt, length()); });
    seekTo(vt);
  }
  function wireLane() {
    const lane = $('ed-lane'); let mode = null;
    const xToVt = e => {
      const b = lane.getBoundingClientRect(), { lead, trail } = context();
      return clamp((e.clientX - b.left) / b.width * (length() + lead + trail) - lead, 0, length());
    };
    lane.addEventListener('pointerdown', e => {
      if (!st) return; lane.setPointerCapture(e.pointerId);
      const h = e.target.closest('[data-h]');
      if (h) {
        if (playing) togglePlay();
        const [i, edge] = h.dataset.h.split(':'), { lead, trail } = context();
        mode = { kind: 'trim', i: Number(i), edge, x: e.clientX, p0: { ...st.pieces[Number(i)] },
          rate: (length() + lead + trail) / lane.getBoundingClientRect().width };
        dragStart(); return;
      }
      const pc = e.target.closest('[data-p]'); if (pc) sel = Number(pc.dataset.p);
      mode = { kind: 'scrub' }; seekTo(xToVt(e)); lane.querySelectorAll('.ed-piece').forEach((n, i) => n.classList.toggle('on', i === sel));
    });
    lane.addEventListener('pointermove', e => {
      if (!mode) return;
      if (mode.kind === 'scrub') { seekTo(xToVt(e)); return; }
      const dt = (e.clientX - mode.x) * mode.rate, p = st.pieces[mode.i];
      const time = snapTime(mode.p0[mode.edge] + dt, mode.edge);
      if (mode.edge === 'start') p.start = clamp(time, 0, p.end - 0.2); else p.end = clamp(time, p.start + 0.2, st.base);
      const el = lane.querySelectorAll('.ed-piece')[mode.i]; if (el) { el.style.flex = (p.end - p.start) + ' 1 0'; el.querySelector('b').textContent = (p.end - p.start).toFixed(1) + 's'; }
      syncContext();
    });
    const end = () => { if (!mode) return; const m = mode; mode = null; if (m.kind === 'trim') { if (!fits(st.pieces, false)) { st.pieces[m.i] = m.p0; dragSnap = null; afterChange(); return; } note(''); dragEnd(); seekTo(vt); } };
    lane.addEventListener('pointerup', end); lane.addEventListener('pointercancel', end);
  }
  function pieceAction(act) {
    if (!st) return; const next = st.pieces.map(p => ({ ...p })), i = sel;
    if (act === 'left' && i > 0) { [next[i - 1], next[i]] = [next[i], next[i - 1]]; sel = i - 1; }
    else if (act === 'right' && i < next.length - 1) { [next[i + 1], next[i]] = [next[i], next[i + 1]]; sel = i + 1; }
    else if (act === 'dup') { next.splice(i + 1, 0, { ...next[i] }); sel = i + 1; }
    else if (act === 'drop') { if (next.length < 2) { note('A clip needs at least one piece.'); return; } next.splice(i, 1); sel = Math.max(0, i - 1); }
    else return;
    if (fits(next, false)) commit(() => { st.pieces = next; });
  }

  // ---------- side panel: everything is a picture, a swatch or a chip
  const chip = (attrs, label, on) => '<button type="button" class="ed-chip' + (on ? ' on' : '') + '" ' + attrs + '>' + label + '</button>';
  function swatches(key) {
    return '<div class="ed-sw">' + COLORS.map(c => '<i role="button" tabindex="0" class="ed-swatch' + ((st[key] || '').toUpperCase() === c ? ' on' : '') + '" data-color="' + key + ':' + c + '" style="background:' + c + '" aria-label="' + c + '"></i>').join('') +
      '<input type="color" class="ed-cp" data-key="' + key + '" value="' + (st[key] || '#FFFFFF') + '" title="Any colour"></div>';
  }
  const presetNote = () => { const n = PRESETS.find(p => p[0] === st.preset); if (!n) return '9:16 · 1080p · 30 fps · H.264.'; const l = length(); return n[1] + ': 9:16 · 1080p · 30 fps. ' + (l > n[2] ? '⚠ This clip is ' + Math.round(l) + ' s; limit ' + n[2] + ' s.' : 'Length fine (' + Math.round(l) + ' of ' + n[2] + ' s).'); };
  function drawPane() {
    document.querySelectorAll('#ed-tabs [data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
    const pane = $('ed-pane'); if (!st) { pane.innerHTML = '<p class="muted">Pick a clip on the left.</p>'; return; }
    if (tab === 'captions') {
      pane.innerHTML = '<label class="ed-chk"><input type="checkbox" data-key="captions"' + (st.captions ? ' checked' : '') + '> Captions on</label>' +
        '<div class="ed-styles">' + Object.entries(STYLES).map(([k, [n, base, hi]]) => '<button type="button" class="ed-style' + (st.caption_style === k ? ' on' : '') + '" data-style="' + k + '"><span class="demo"><span style="' + base + '">YOUR </span><span style="' + base + ';' + hi + '">STORY</span></span><small>' + n + '</small></button>').join('') + '</div>' +
        '<h4>Size</h4><div class="ed-row">' + SIZES.map(([n, v]) => chip('data-size="' + v + '"', n, Number(st.caption_size) === v)).join('') + chip('data-size=""', 'Auto', !st.caption_size) + '</div>' +
        '<h4>Words per line</h4><div class="ed-row">' + [1, 2, 3, 4, 5, 6].map(n => chip('data-words="' + n + '"', n, Number(st.caption_max_words) === n)).join('') + '</div>' +
        '<h4>Font</h4><div class="ed-row">' + chip('data-font=""', 'Auto', !st.caption_font) + FONTS.map(f => '<button type="button" class="ed-chip' + (st.caption_font === f ? ' on' : '') + '" data-font="' + f + '" style="font-family:\'' + f + '\'">Aa</button>').join('') + '</div>' +
        '<h4>Text colour</h4>' + swatches('caption_color') + '<h4>Active word</h4>' + swatches('caption_active') + '<h4>Outline</h4>' + swatches('caption_outline') +
        '<h4>Caption profiles</h4><div class="ed-row"><select id="ed-brand-profile" aria-label="Saved caption profile"><option value="">Choose saved profile</option>' +
        Object.keys(captionProfiles).map(name => '<option value="' + esc(name) + '">' + esc(name) + '</option>').join('') + '</select></div>' +
        '<div class="ed-row"><input type="text" id="ed-brand-name" maxlength="60" placeholder="Profile name" aria-label="Caption profile name"><button type="button" id="ed-brand-save" class="mini-btn">Save current look</button></div>' +
        '<p class="muted">Tip: drag the captions on the preview to move them.</p>';
    } else if (tab === 'framing') {
      pane.innerHTML = '<h4>Layout</h4><div class="ed-lays">' + LAYOUTS.map(([k, n]) => '<button type="button" class="ed-lay' + (st.layout === k ? ' on' : '') + '" data-layout="' + k + '">' + layoutSvg(k) + '<small>' + n + '</small></button>').join('') + '</div>' +
        '<h4>Camera and game boxes: drag a box, drag its corner to resize</h4><div class="ed-framewrap"><canvas id="ed-frame" class="ed-frame"></canvas></div>' +
        '<h4>Shape</h4><div class="ed-row">' + ASPECTS.map(([k, n]) => chip('data-aspect="' + k + '"', n, st.aspect === k)).join('') + '</div>' +
        '<h4>Export for</h4><div class="ed-row">' + PRESETS.map(([k, n]) => chip('data-preset="' + k + '"', n, st.preset === k)).join('') + '</div><p class="muted">' + presetNote() + '</p>';
      drawFrame();
    } else if (tab === 'audio') {
      pane.innerHTML = '<h4>Volume</h4><div class="ed-row">' + VOLUMES.map(([n, v]) => chip('data-vol="' + v + '"', (v === 0 ? '🔇 ' : '🔊 ') + n, st.voice_volume === v)).join('') + '</div>' +
        '<label class="ed-chk"><input type="checkbox" data-key="fade_inout"' + (st.fade_inout ? ' checked' : '') + '> Fade in and out</label>';
    } else {
      pane.innerHTML = '<h4>At the playhead</h4><div class="ed-row">' +
        [['hit','Bass hit'],['sweep','Sweep'],['flash','Flash']].map(([value,label]) => chip('data-cue="' + value + '"',label,false)).join('') + '</div>' +
        (st.effect_cues || []).map((cue,i) => '<div class="ed-row"><span>' + fmt(cue.at) + ' · ' + ({hit:'Bass hit',sweep:'Sweep',flash:'Flash'})[cue.kind] +
          '</span><button type="button" class="mini-btn" data-delete-cue="' + i + '">Remove</button></div>').join('') +
        '<h4>Look recipes</h4><div class="ed-row">' +
        Object.entries(RECIPES).map(([value,recipe]) => chip('data-recipe="' + value + '"',recipe.label,st.recipe === value)).join('') + '</div>' +
        '<label class="ed-chk"><input type="checkbox" data-key="clip_progress"' + (st.clip_progress ? ' checked' : '') + '> Clip progress bar</label>' +
        '<label class="ed-chk"><input type="checkbox" data-key="loop_end"' + (st.loop_end ? ' checked' : '') + '> Blend the ending into the opening frame</label>' +
        '<h4>Censor spoken words</h4><div class="ed-row">' + [['off','Off'],['mute','Mute'],['bleep','Bleep'],['bar','Mute + bar'],['blur','Mute + blur']].map(([value,label]) => chip('data-censor="' + value + '"',label,(st.censor_mode || 'off') === value)).join('') + '</div>' +
        '<label>Words to censor<input type="text" data-key="censor_words" maxlength="1000" placeholder="Separate words with commas" value="' + esc(st.censor_words) + '"></label>' +
        '<h4>Heading</h4><label class="ed-chk"><input type="checkbox" data-key="hook_enabled"' + (st.hook_enabled ? ' checked' : '') + '> Opening heading</label>' +
        '<input type="text" data-key="hook" maxlength="65" value="' + esc(st.hook) + '" placeholder="Opening line" class="ed-text">' +
        '<div class="ed-row">' + HOOKS.map(([k, n]) => chip('data-hook="' + k + '"', n, st.hook_style === k)).join('') + '</div>' +
        '<h4>Camera look</h4><div class="ed-row">' + LOOKS.map(([n, b, c, s, k]) => chip('data-look="' + [b, c, s, k].join(',') + '"', n, st.cam_brightness === b && st.cam_contrast === c && st.cam_saturation === s && st.cam_clarity === k)).join('') + '</div>';
    }
  }

  // camera / game boxes on the source frame
  function drawFrame() {
    const c = $('ed-frame'), v = $('ed-src'); if (!c || !st) return;
    const ar = v.videoWidth ? v.videoWidth / v.videoHeight : 16 / 9, w = (c.parentElement.clientWidth || 280); c.width = Math.round(w); c.height = Math.round(w / ar);
    const x = c.getContext('2d'); if (v.readyState >= 2 && v.videoWidth) x.drawImage(v, 0, 0, c.width, c.height); else { x.fillStyle = '#111'; x.fillRect(0, 0, c.width, c.height); }
    [['game', '#ff3d9a', 'GAME'], ['cam', '#18e0ff', 'CAM']].forEach(([k, col, name]) => {
      const r = st[k]; x.lineWidth = 3; x.strokeStyle = col; x.fillStyle = col + '22'; x.fillRect(r.x * c.width, r.y * c.height, r.w * c.width, r.h * c.height); x.strokeRect(r.x * c.width, r.y * c.height, r.w * c.width, r.h * c.height);
      x.fillStyle = col; x.font = 'bold 12px sans-serif'; x.fillText(name, r.x * c.width + 6, r.y * c.height + 15); x.fillRect((r.x + r.w) * c.width - 12, (r.y + r.h) * c.height - 12, 12, 12);
    });
  }
  document.addEventListener('pointerdown', e => {
    const c = e.target.closest && e.target.closest('#ed-frame'); if (!c || !st) return; c.setPointerCapture(e.pointerId);
    const b = c.getBoundingClientRect(), px = (e.clientX - b.left) / b.width, py = (e.clientY - b.top) / b.height;
    for (const k of ['cam', 'game']) {
      const r = st[k], corner = Math.abs(px - (r.x + r.w)) < 16 / b.width && Math.abs(py - (r.y + r.h)) < 16 / b.height, inside = px >= r.x && px <= r.x + r.w && py >= r.y && py <= r.y + r.h;
      if (corner || inside) { c._d = { k, resize: corner, px, py, r0: { ...r } }; dragStart(); return; }
    }
  });
  document.addEventListener('pointermove', e => {
    const c = $('ed-frame'); if (!c || !c._d || !st) return; const d = c._d, b = c.getBoundingClientRect(), px = (e.clientX - b.left) / b.width, py = (e.clientY - b.top) / b.height, r = st[d.k];
    if (d.resize) { r.w = clamp(d.r0.w + px - d.px, .05, 1 - r.x); r.h = clamp(d.r0.h + py - d.py, .05, 1 - r.y); }
    else { r.x = clamp(d.r0.x + px - d.px, 0, 1 - r.w); r.y = clamp(d.r0.y + py - d.py, 0, 1 - r.h); }
    drawFrame(); paint();
  });
  document.addEventListener('pointerup', () => { const c = $('ed-frame'); if (c && c._d) { c._d = null; dragEnd(); } });

  function onClick(e) {
    if (!st) return;
    const q = sel2 => e.target.closest(sel2); let b;
    if ((b = q('[data-style]'))) commit(() => { st.caption_style = b.dataset.style; });
    else if ((b = q('[data-layout]'))) commit(() => { st.layout = b.dataset.layout; });
    else if ((b = q('[data-size]'))) commit(() => { st.caption_size = b.dataset.size ? Number(b.dataset.size) : ''; });
    else if ((b = q('[data-words]'))) commit(() => { st.caption_max_words = Number(b.dataset.words); });
    else if ((b = q('[data-font]'))) commit(() => { st.caption_font = b.dataset.font; });
    else if ((b = q('[data-color]'))) commit(() => { const [k, c] = b.dataset.color.split(':'); st[k] = (st[k] || '').toUpperCase() === c ? '' : c; });
    else if ((b = q('[data-aspect]'))) commit(() => { st.aspect = b.dataset.aspect; });
    else if ((b = q('[data-preset]'))) commit(() => { st.aspect = 'vertical'; st.resolution = 1080; st.fps = 30; st.preset = b.dataset.preset; });
    else if ((b = q('[data-vol]'))) commit(() => { st.voice_volume = Number(b.dataset.vol); });
    else if ((b = q('[data-censor]'))) commit(() => { st.censor_mode = b.dataset.censor; });
    else if ((b = q('[data-cue]'))) {
      if ((st.effect_cues || []).length >= 16) { note('At most 16 effects per clip.'); return; }
      const at = Number(Math.min(vt,Math.max(0,length()-.05)).toFixed(3));
      commit(() => { st.effect_cues = [...(st.effect_cues || []),{ kind:b.dataset.cue,at }]; });
    }
    else if ((b = q('[data-delete-cue]'))) commit(() => { st.effect_cues.splice(Number(b.dataset.deleteCue),1); });
    else if ((b = q('[data-recipe]'))) commit(() => {
      const { label, ...recipe } = RECIPES[b.dataset.recipe];
      Object.assign(st, recipe, { captions: true, recipe: b.dataset.recipe });
    });
    else if (q('#ed-brand-save')) saveCaptionProfile();
    else if ((b = q('[data-hook]'))) commit(() => { st.hook_style = b.dataset.hook; });
    else if ((b = q('[data-look]'))) commit(() => { const [br, co, sa, cl] = b.dataset.look.split(',').map(Number); st.cam_brightness = br; st.cam_contrast = co; st.cam_saturation = sa; st.cam_clarity = cl; });
    else if ((b = q('[data-pa]'))) pieceAction(b.dataset.pa);
    else if ((b = q('[data-seek]'))) seekTo(Number(b.dataset.seek));
    else if ((b = q('[data-del]'))) commit(() => { st.words.splice(Number(b.dataset.del), 1); });
    else if ((b = q('[data-cut-word]'))) cutWord(Number(b.dataset.piece), Number(b.dataset.cutWord));
  }
  function onChange(e) {
    if (!st) return; const t = e.target;
    if (t.id === 'ed-brand-profile') {
      const profile = Object.hasOwn(captionProfiles, t.value) ? captionProfiles[t.value] : null;
      if (profile) {
        commit(() => { for (const key of CAPTION_BRAND_KEYS) st[key] = profile[key] || ''; });
        note('Caption profile applied.');
      }
      return;
    }
    if (t.matches('#ed-words [data-word]')) { const i = Number(t.dataset.word), text = t.value.trim(); if (!text) commit(() => { st.words.splice(i, 1); }); else if (text !== st.words[i].text) { const old = st.words[i].text; commit(() => { st.words[i].text = text; }); askAlways(old, text); } return; }
    const key = t.dataset && t.dataset.key; if (!key) return;
    const value = t.type === 'checkbox' ? t.checked : (t.type === 'color' ? t.value.toUpperCase() : t.value); if (st[key] === value) return; commit(() => { st[key] = value; });
  }

  // ---------- your words (glossary): fix a word once, every future caption, hook and title spells it right
  const strip = t => String(t).replace(/^(?:[^\wऀ-ॿ]|[।॥])+|(?:[^\wऀ-ॿ]|[।॥])+$/g, '');   // ।॥ are punctuation
  let gloss = [];
  function drawGloss() {
    const box = $('ed-gloss'); if (!box) return;
    box.innerHTML = gloss.length ? gloss.map(g => '<span class="gl"><s>' + esc(g.from) + '</s><i>→</i><b>' + esc(g.to) + '</b><button type="button" data-glrm="' + esc(g.from) + '" title="Stop fixing this word">✕</button></span>').join('')
      : '<p class="muted">No words yet. Change a word in the transcript and press <b>Always fix</b>, or add one here.</p>';
  }
  async function loadGloss() { try { gloss = (await req('/glossary')).words || []; } catch (e) { gloss = []; } drawGloss(); }
  async function saveGloss(from, to) {
    try { gloss = (await req('/glossary', { from, to })).words; drawGloss(); return true; }
    catch (e) { const a = $('ed-fixask'); a.hidden = false; a.innerHTML = '<span class="ed-note">' + esc(e.message) + '</span>'; return false; }
  }
  function askAlways(oldText, newText) {
    const from = strip(oldText), to = strip(newText), a = $('ed-fixask'); if (!a || !from || !to || from === to) return;
    const same = st.words.filter(w => strip(w.text).toLowerCase() === from.toLowerCase()).length;
    a.hidden = false; a.dataset.from = from; a.dataset.to = to;
    a.innerHTML = '<span>Always write <s>' + esc(from) + '</s> as <b>' + esc(to) + '</b>?' + (same ? ' <small>(' + same + ' more in this clip)</small>' : '') + '</span>' +
      '<button type="button" class="mini-btn hot" data-fix="always">Always fix</button><button type="button" class="mini-btn" data-fix="once">Only here</button>';
  }
  async function fixAnswer(kind) {
    const a = $('ed-fixask'), from = a.dataset.from, to = a.dataset.to; a.hidden = true; if (kind !== 'always') return;
    if (!(await saveGloss(from, to))) return;
    if (st.words.some(w => strip(w.text).toLowerCase() === from.toLowerCase()))
      commit(() => { st.words.forEach(w => { if (strip(w.text).toLowerCase() === from.toLowerCase()) w.text = w.text.replace(strip(w.text), to); }); });
  }
  document.addEventListener('click', async e => {
    const f = e.target.closest('#ed-fixask [data-fix]'); if (f) { fixAnswer(f.dataset.fix); return; }
    const rm = e.target.closest('[data-glrm]'); if (rm) { try { gloss = (await req('/glossary/remove', { from: rm.dataset.glrm })).words; } catch (x) { } drawGloss(); return; }
    if (e.target.closest('#ed-gl-add')) { const fr = $('ed-gl-from'), to = $('ed-gl-to'); if (fr.value.trim() && to.value.trim() && await saveGloss(fr.value.trim(), to.value.trim())) { fr.value = ''; to.value = ''; } }
  });
  setTimeout(loadGloss, 0);

  // ---------- transcript (words as chips; click to jump, edit, remove)
  function cutWord(pieceIndex, wordIndex) {
    const piece = st.pieces[pieceIndex], word = st.words[wordIndex];
    if (!piece || !word) return;
    const a = Math.max(piece.start, word.a), b = Math.min(piece.end, word.b);
    if (a >= b) return;
    const keep = [];
    if (a - piece.start >= .2) keep.push({ start: piece.start, end: a });
    if (piece.end - b >= .2) keep.push({ start: b, end: piece.end });
    const next = st.pieces.slice();
    next.splice(pieceIndex, 1, ...keep);
    if (!fits(next, false)) return;
    if (playing) togglePlay();
    commit(() => { st.pieces = next; sel = Math.min(pieceIndex, next.length - 1); vt = Math.min(vt, length()); });
    seekTo(vt);
  }
  function drawTranscript() {
    const box = $('ed-words'); if (!st) { box.innerHTML = ''; return; }
    const rw = rel(st.pieces);
    box.innerHTML = rw.length ? rw.map(w => '<span class="w"><button type="button" class="seek" data-seek="' + w.start.toFixed(2) + '" title="Jump here">▸</button><input value="' + esc(w.text) + '" data-word="' + w.i + '" size="' + Math.max(2, w.text.length) + '" aria-label="Word"><button type="button" class="del" data-del="' + w.i + '" title="Remove caption word only">✕</button><button type="button" class="cut-word" data-cut-word="' + w.i + '" data-piece="' + w.piece + '" title="Cut this word from the video" aria-label="Cut ' + esc(w.text) + ' from video">✂</button></span>').join('') : '<p class="muted">This clip has no saved transcript.</p>';
  }

  function updateButtons() {
    $('ed-undo').disabled = !undo.length; $('ed-redo').disabled = !redo.length;
    $('ed-reset').disabled = !dirty(); $('ed-export').disabled = !dirty(); $('ed-export').textContent = dirty() ? 'Export changes' : 'No changes yet';
    const tracks = $('ed-export-tracks');
    tracks.hidden = !info || ['blur', 'fill', 'game'].includes(info.settings?.layout || 'blur');
    $('ed-reaction-gif').disabled = !file;
  }

  async function exportTracks() {
    if (!file) return;
    const button = $('ed-export-tracks');
    if (dirty()) { note('Export your changes first to include them in the editing tracks.'); return; }
    button.disabled = true;
    note('Preparing gameplay, facecam and XML…');
    try {
      const result = await req('/editor-export', { file });
      const download = document.createElement('a');
      download.href = result.download;
      download.download = 'BloomClipping-editing-tracks.zip';
      download.click();
      note('Editing tracks ready. Extract the ZIP and import the XML.');
    } catch (error) {
      note(error.message);
    } finally {
      button.disabled = false;
    }
  }
  async function exportNow() {
    if (!st || !dirty()) return;
    const scope = (document.querySelector('input[name=ed-scope]:checked') || {}).value || 'one', changes = {};
    ['caption_style', 'captions', 'caption_y', 'voice_volume', 'caption_font', 'caption_size', 'caption_color', 'caption_active', 'caption_outline', 'caption_max_words', 'resolution', 'fps', 'layout', 'aspect', 'hook', 'hook_enabled', 'hook_style', 'fade_inout', 'top', 'cam', 'game', 'cam_brightness', 'cam_contrast', 'cam_saturation', 'cam_clarity', 'censor_mode', 'censor_words', 'clip_progress', 'loop_end'].forEach(k => { changes[k] = st[k]; });
    const body = { file, scope, changes }, o = JSON.parse(original);
    const cut = JSON.stringify(o.pieces) !== JSON.stringify(st.pieces);
    const cues = (st.effect_cues || []).filter(cue => cue.at < length());
    if (JSON.stringify(o.effect_cues || []) !== JSON.stringify(cues)) {
      if (scope === 'video') { note('Place timed effects on one clip at a time.'); return; }
      changes.effect_cues = cues;
    }
    if (cut || JSON.stringify(o.words) !== JSON.stringify(st.words)) {
      if (scope === 'video') { note('Transcript edits and cutting work on one clip at a time. Pick "Only this clip".'); return; }
      body.words = rel(st.pieces).map(w => ({ start: Number(w.start.toFixed(3)), end: Number(w.end.toFixed(3)), text: w.text }));
      if (cut) body.segments = st.pieces;
    }
    $('ed-export').disabled = true;
    try {
      const { job, clips: n } = await req('/clips/reedit', body);
      for (;;) {
        note('Exporting ' + n + ' clip(s)…'); await new Promise(r => setTimeout(r, 1500));
        const r = await req('/status/' + job);
        if (r.status === 'error') throw new Error(r.error || 'Export failed');
        if (r.status === 'done') {
          try { localStorage.removeItem(draftKey()); } catch (e) { /* ignore */ }
          const first = (r.clips || []).find(c => c.previous === file) || (r.clips || [])[0];
          note('Done. The new version replaced the old one.');
          if (typeof refreshLibrary === 'function') refreshLibrary().catch(() => {});
          original = null; await openClip(first ? first.file || first.id || file : file); return;
        }
      }
    } catch (e) { note(e.message); updateButtons(); }
  }

  async function loadCaptionProfiles() {
    try { captionProfiles = (await req('/brands')).profiles || {}; profilesReady = true; }
    catch (error) { note(error.message); }
    if (st && tab === 'captions') drawPane();
  }
  async function saveCaptionProfile() {
    const name = $('ed-brand-name').value.trim();
    if (!name) { note('Enter a caption profile name.'); return; }
    const settings = Object.fromEntries(CAPTION_BRAND_KEYS.filter(key => st[key]).map(key => [key, st[key]]));
    try {
      await req('/brands', { name, settings });
      await loadCaptionProfiles();
      note('Caption profile saved.');
    } catch (error) {
      note(error.message);
    }
  }
  async function show() {
    if (!$('clip-editor-view')) return;
    if (!profilesReady) loadCaptionProfiles();
    await loadList();
    if (!file && clips.length) openClip(clips[0].id);
  }
  function init() {
    if ($('clip-editor-view')) return; const nav = document.querySelector('[data-view=library]'); if (!nav) return;
    build();
    const btn = document.createElement('button'); btn.className = 'nav'; btn.type = 'button'; btn.id = 'nav-clip-editor'; btn.innerHTML = '✎ &nbsp; Editor'; nav.after(btn);
    const views = ['editor-view', 'library-view', 'youtube-view', 'creators-view', 'clip-editor-view'];
    btn.onclick = () => { document.querySelectorAll('.nav').forEach(x => x.classList.toggle('active', x === btn)); views.forEach(v => { const el = $(v); if (el) el.hidden = v !== 'clip-editor-view'; }); show(); };
    document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => { $('clip-editor-view').hidden = true; btn.classList.remove('active'); if (playing) togglePlay(); }));
    window.openInEditor = id => { btn.click(); setTimeout(() => openClip(id), 50); };
  }
  if (document.readyState === 'complete') setTimeout(init, 500); else window.addEventListener('load', () => setTimeout(init, 500));
})();
