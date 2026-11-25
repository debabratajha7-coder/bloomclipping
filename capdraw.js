// Draws every caption style and every opening-heading style on the Create clips preview, the way the finished clip looks.
// Replaces the old captionPreview()/hookPreview() (which drew one white line for most styles). Loaded after app.js.
(function () {
  const F = 'Arial, "Helvetica Neue", sans-serif';
  const LOOKS = {
    karaoke: { w: 800, fill: '#fff', stroke: '#000', sw: .12, active: { fill: '#FFE14A' } },
    tiktok: { w: 900, fill: '#fff', stroke: '#000', sw: .17, active: { fill: '#25F4EE' } },
    pill: { w: 700, fill: '#fff', pill: 'rgba(0,0,0,.68)', activeBg: '#FF3D6E' },
    oneword: { w: 900, fill: '#fff', stroke: '#000', sw: .16, scale: 1.45, one: true },
    cine: { w: 300, fill: '#eee', scale: .66, track: .18, shadow: '#000', active: { fill: '#fff', w: 700 } },
    boxed: { w: 800, fill: '#fff', stroke: '#000', sw: .1, activeBox: '#FFE14A', active: { fill: '#000', nostroke: true } },
    outlined: { w: 900, fill: null, stroke: '#fff', sw: .06, active: { fill: '#FFE14A', stroke: '#000' } },
    comic: { w: 900, italic: true, fill: '#FFE14A', stroke: '#C00000', sw: .18, active: { fill: '#fff' } },
    gta: { w: 900, fill: '#FF4FA3', glow: '#FF4FA3', stroke: '#160b22', sw: .08, active: { fill: '#4FF0FF', glow: '#4FF0FF' } },
    bold: { w: 900, family: 'Impact, Arial Black, sans-serif', upper: true, fill: '#fff', stroke: '#000', sw: .14, active: { fill: '#FFE14A' } },
    hormozi: { w: 900, upper: true, fill: '#fff', stroke: '#000', sw: .12, active: { fill: '#3DDC84' } },
    mrbeast: { w: 900, upper: true, fill: '#fff', stroke: '#000', sw: .24, active: { fill: '#FF3D3D' } },
    clean: { w: 500, fill: '#fff', shadow: 'rgba(0,0,0,.7)', active: { w: 800 } },
  };
  function rr(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }

  // o: { style, words:[string], active:index, cx, cy, fs, maxW }
  function draw(ctx, o) {
    const L = LOOKS[o.style] || LOOKS.karaoke;
    let list = o.words.map((w, i) => ({ t: L.upper ? w.toUpperCase() : w, on: i === o.active }));
    if (L.one) list = list.filter(w => w.on).length ? list.filter(w => w.on) : list.slice(0, 1);
    let fs = o.fs * (L.scale || 1);
    const font = (it, size) => (L.italic ? 'italic ' : '') + ((it.on && L.active && L.active.w) || L.w) + ' ' + size + 'px ' + (L.family || F);
    const measure = size => { ctx.font = font({ on: false }, size); return list.reduce((n, it) => { ctx.font = font(it, size); return n + ctx.measureText(it.t).width + (L.track ? size * L.track * it.t.length : 0); }, 0) + size * .3 * (list.length - 1); };
    let total = measure(fs);
    if (total > o.maxW) { fs *= o.maxW / total; total = measure(fs); }
    ctx.save(); ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round'; ctx.miterLimit = 2;
    let x = o.cx - total / 2; const y = o.cy;
    if (L.pill) { rr(ctx, x - fs * .35, y - fs * .62, total + fs * .7, fs * 1.24, fs * .62); ctx.fillStyle = L.pill; ctx.fill(); }
    list.forEach(it => {
      ctx.font = font(it, fs); if (L.track && 'letterSpacing' in ctx) ctx.letterSpacing = (fs * L.track) + 'px';
      const w = ctx.measureText(it.t).width, st = it.on && L.active ? L.active : {};
      if (it.on && L.activeBg) { rr(ctx, x - fs * .18, y - fs * .55, w + fs * .36, fs * 1.1, fs * .5); ctx.fillStyle = L.activeBg; ctx.fill(); }
      if (it.on && L.activeBox) { ctx.fillStyle = L.activeBox; ctx.fillRect(x - fs * .16, y - fs * .55, w + fs * .32, fs * 1.1); }
      const fill = st.fill !== undefined ? st.fill : L.fill, stroke = st.nostroke ? null : (st.stroke || L.stroke), glow = st.glow || L.glow;
      if (L.shadow) { ctx.shadowColor = L.shadow; ctx.shadowBlur = fs * .18; ctx.shadowOffsetY = fs * .05; }
      if (glow) { ctx.shadowColor = glow; ctx.shadowBlur = fs * .35; }
      if (stroke) { ctx.lineWidth = fs * (L.sw || .1); ctx.strokeStyle = stroke; ctx.strokeText(it.t, x, y); }
      ctx.shadowBlur = glow ? fs * .35 : (L.shadow ? fs * .18 : 0);
      if (fill) { ctx.fillStyle = fill; ctx.fillText(it.t, x, y); }
      ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
      x += w + fs * .3; if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
    });
    ctx.restore();
  }

  // Opening heading: impact (bold pop), neon (glow), banner (colour bar), box (classic black box)
  function drawHeading(ctx, o) {
    const style = o.style || 'impact', lines = o.lines, size = o.size, pad = o.pad, lh = o.lh, W = ctx.canvas.width;
    ctx.save(); ctx.font = '900 ' + size + 'px ' + (style === 'impact' ? 'Impact, Arial Black, sans-serif' : F); ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.lineJoin = 'round';
    const wMax = Math.max(...lines.map(t => ctx.measureText(t).width)), boxW = Math.min(W * .94, wMax + pad * 2), boxH = lh * lines.length + pad * 2, y = o.y, cx = W / 2;
    if (style === 'box' && o.background !== false) { ctx.fillStyle = 'rgba(0,0,0,.88)'; ctx.fillRect(cx - boxW / 2, y, boxW, boxH); }
    if (style === 'banner') { const g = ctx.createLinearGradient(0, 0, W, 0); g.addColorStop(0, '#FF3D6E'); g.addColorStop(1, '#A66BFF'); ctx.fillStyle = g; ctx.fillRect(0, y, W, boxH); }
    lines.forEach((t, i) => {
      const ty = y + pad + i * lh;
      if (style === 'neon') { ctx.shadowColor = '#4FF0FF'; ctx.shadowBlur = size * .5; ctx.fillStyle = '#E8FFFF'; ctx.fillText(t, cx, ty); ctx.shadowBlur = size * .9; ctx.fillText(t, cx, ty); ctx.shadowBlur = 0; }
      else if (style === 'impact') { ctx.lineWidth = size * .2; ctx.strokeStyle = '#000'; ctx.strokeText(t, cx, ty); ctx.fillStyle = i === lines.length - 1 ? '#FFE14A' : '#fff'; ctx.fillText(t, cx, ty); }
      else { ctx.lineWidth = Math.max(2, size * .04); ctx.strokeStyle = '#000'; if (style === 'box') ctx.strokeText(t, cx, ty); ctx.fillStyle = '#fff'; ctx.fillText(t, cx, ty); }
    });
    ctx.restore();
  }

  window.NeonCaption = { draw, drawHeading, LOOKS };

  // ---- replace the page's two preview painters (they use app.js globals: pc, v, still, words, layout, layoutSpecs, style, signature, wordRange)
  window.captionPreview = function () {
    const $ = id => document.getElementById(id);
    if (!$('captions').checked) return;
    const spec = layoutSpecs[layout]; if (!spec) return;
    const st = (typeof style === 'string' && LOOKS[style]) ? style : 'karaoke', per = st === 'oneword' ? 1 : 3;
    let list = 'YOUR NEXT BIG MOMENT'.split(' '), active = Math.floor(Date.now() / 450) % 4;
    if (words && wordRange === signature() && words.length) {
      const time = Math.max(0, v.currentTime - Number($('start').value));
      let i = words.findIndex(w => time >= w.start && time <= w.end); if (i < 0) i = 0;
      const from = Math.floor(i / per) * per; list = words.slice(from, from + per).map(w => w.text); active = i - from;
    } else if (st === 'oneword') { list = 'YOUR NEXT BIG MOMENT'.split(' '); }
    const scale = pc.canvas.width / spec.width, fs = 72 * Math.min(spec.width / 1080, spec.height / 1920) * scale;
    const y = Number($('caption-y').value) === 1450 ? spec.caption_y : Number($('caption-y').value) / 1920 * spec.height;
    draw(pc, { style: st, words: list, active, cx: pc.canvas.width / 2, cy: y * scale, fs: st === 'clean' ? fs * .8 : fs, maxW: pc.canvas.width * .9 });
  };
  window.hookPreview = function () {
    const $ = id => document.getElementById(id), text = $('hook').value.trim();
    if (!text || ($('hook-enabled') && !$('hook-enabled').checked)) return;
    const spec = layoutSpecs[layout]; if (!spec) return;
    const duration = Number($('hook-duration') && $('hook-duration').value || 8);
    if (!still && v.currentTime - Number($('start').value) > duration) return;
    const factor = pc.canvas.width / spec.width, scale = Math.min(spec.width / 1080, spec.height / 1920);
    let lines = [], line = ''; const width = Math.max(12, Math.floor(spec.width / (82 * scale * .6)));
    for (const word of text.slice(0, 60).toUpperCase().split(/\s+/)) { if (line && (line + ' ' + word).length > width) { lines.push(line); line = word; } else line += (line ? ' ' : '') + word; }
    if (line) lines.push(line); lines = lines.slice(0, 3);
    const size = Math.round((lines.length === 1 ? 78 : lines.length === 2 ? 72 : 66) * scale) * factor, pad = Math.max(8, Math.round(26 * scale)) * factor, lh = Math.round(size * 1.22);
    const boxH = lh * lines.length + pad * 2, y = Math.max(pad, Math.min(spec.hook_y * factor, pc.canvas.height - boxH - pad));
    drawHeading(pc, { style: ($('hook-style') && $('hook-style').value) || 'impact', lines, size, pad, lh, y, background: !$('hook-background') || $('hook-background').checked });
  };
})();
