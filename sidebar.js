// Left sidebar helpers: Storage (free space, clean-up, data folder) and Supporters as a small toggle.
(function () {
  const $ = id => document.getElementById(id);
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const gb = b => b >= 1073741824 ? (b / 1073741824).toFixed(1) + ' GB' : Math.max(0, Math.round(b / 1048576)) + ' MB';
  async function api(path, body) {
    const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || 'Request failed');
    return j;
  }

  function init() {
    const side = document.querySelector('aside.sidebar');
    if (!side || $('side-storage')) return;
    const anchor = side.querySelector('.side-note');

    // ---- Storage card
    const card = document.createElement('button');
    card.type = 'button';
    card.id = 'side-storage';
    card.className = 'side-card';
    card.innerHTML = '<span class="sc-title">▤ Storage</span><span class="sc-line" id="side-storage-line">checking…</span><span class="sc-bar"><i id="side-storage-bar"></i></span>';
    if (anchor) anchor.before(card); else side.append(card);

    const dlg = document.createElement('dialog');
    dlg.id = 'storage-dialog';
    dlg.innerHTML = '<div class="sd-head"><b>Storage</b><button type="button" id="sd-close" class="mini-btn">Close</button></div>' +
      '<div id="sd-body" class="sd-body">Loading…</div>';
    document.body.append(dlg);
    $('sd-close').onclick = () => dlg.close();
    card.onclick = () => { dlg.showModal(); render(); };

    const ACTIONS = [
      ['temp', 'Clean temporary files', 'Unfinished downloads, temporary audio and previews. Safe: they are created again when needed.', false],
      ['recordings', 'Delete live recordings', 'The big recordings made while live clipping. Clips already cut from them are kept.', false],
      ['orphans', 'Delete unused source videos', 'Downloaded or uploaded videos that no finished clip uses.', false],
      ['sources', 'Delete source videos of finished clips', 'Your clips stay, but you can no longer re-edit them from the saved source.', true],
    ];

    async function line() {
      try {
        const s = await api('/storage');
        $('side-storage-line').textContent = gb(s.total) + ' used · ' + gb(s.free) + ' free';
        const pct = Math.min(100, Math.round(100 * (s.disk_total - s.free) / s.disk_total));
        $('side-storage-bar').style.width = pct + '%';
        card.classList.toggle('low', s.free < 5 * 1073741824);
        return s;
      } catch (e) { $('side-storage-line').textContent = 'unavailable'; return null; }
    }

    async function render() {
      const s = await line();
      if (!s) { $('sd-body').textContent = 'Storage information is not available.'; return; }
      const rows = ACTIONS.map(([key, title, why, warn]) => {
        const a = s.actions[key] || { count: 0, bytes: 0 };
        return '<div class="sd-row"><div><b>' + esc(title) + '</b><small>' + esc(why) + '</small></div>' +
          '<button type="button" class="' + (warn ? 'mini-btn warn' : 'mini-btn') + '" data-clean="' + key + '"' + (a.count ? '' : ' disabled') + (s.busy ? ' title="A job is running"' : '') + '>' +
          (a.count ? 'Free ' + gb(a.bytes) + ' (' + a.count + ')' : 'Nothing to clean') + '</button></div>';
      }).join('');
      $('sd-body').innerHTML =
        '<div class="sd-summary"><div><b>' + gb(s.total) + '</b><small>used by BloomClipping</small></div><div><b>' + gb(s.free) + '</b><small>free on this drive</small></div>' +
        '<div><b>' + s.clips.count + ' clips</b><small>' + gb(s.clips.bytes) + '</small></div><div><b>' + gb(s.models) + '</b><small>AI models</small></div></div>' +
        (s.busy ? '<p class="sd-warn">A job is running. Clean-up is paused until it finishes.</p>' : '') +
        rows +
        '<div class="sd-row"><div><b>Delete old clips</b><small>Removes finished clips (video, captions, cover) older than the days you choose. This cannot be undone. Download the ones you want first.</small></div>' +
        '<div class="sd-inline"><input type="number" id="sd-days" min="1" max="3650" value="30" aria-label="Days"><span>days</span><button type="button" class="mini-btn warn" id="sd-old">Check</button></div></div>' +
        '<div class="sd-row"><div><b>Open the folder</b><small>Show your clips and downloads in the file explorer.</small></div><button type="button" class="mini-btn" id="sd-open">Open folder</button></div>' +
        '<div class="sd-folder"><b>Where BloomClipping saves its files</b><small id="sd-current">' + esc(s.folder) + (s.configured ? '' : ' (default)') + '</small>' +
        '<div class="sd-inline"><input type="text" id="sd-path" placeholder="D:\\BloomClippingData" value="' + esc(s.configured || '') + '" aria-label="Data folder"><button type="button" class="mini-btn" id="sd-folder-save">Save and restart</button></div>' +
        '<small>Use a drive with more free space. BloomClipping restarts to use it. Files already saved stay in the old folder, so delete them above first or copy that folder yourself. Leave empty to go back to the default.</small></div>' +
        '<p id="sd-msg" class="sd-msg" role="status"></p>';
    }

    dlg.addEventListener('click', async e => {
      const msg = t => { const m = $('sd-msg'); if (m) m.textContent = t; };
      const clean = e.target.closest('[data-clean]');
      if (clean) {
        const key = clean.dataset.clean;
        try {
          const p = await api('/storage/plan?action=' + key);
          if (!p.count) { msg('Nothing to clean.'); return; }
          const extra = key === 'sources' ? '\n\nYou will not be able to re-edit those clips afterwards.' : '';
          if (!confirm('Delete ' + p.count + ' item(s) and free ' + gb(p.bytes) + '?' + extra)) return;
          const r = await api('/storage/clean', { action: key, confirm: true });
          msg('Freed ' + gb(r.freed) + ' (' + r.deleted + ' deleted' + (r.failed ? ', ' + r.failed + ' could not be removed' : '') + ').');
          render();
        } catch (err) { msg(err.message); }
        return;
      }
      if (e.target.id === 'sd-old') {
        try {
          const days = Math.max(1, parseInt($('sd-days').value, 10) || 30);
          const p = await api('/storage/plan?action=old_clips&days=' + days);
          if (!p.count) { msg('No clips older than ' + days + ' days.'); return; }
          if (!confirm('Permanently delete the files of clips older than ' + days + ' days? That is ' + p.count + ' files and ' + gb(p.bytes) + '. This cannot be undone.')) return;
          const r = await api('/storage/clean', { action: 'old_clips', days, confirm: true });
          msg('Freed ' + gb(r.freed) + ' (' + r.deleted + ' files).');
          render();
        } catch (err) { msg(err.message); }
        return;
      }
      if (e.target.id === 'sd-open') { try { await api('/storage/open', {}); } catch (err) { msg(err.message); } return; }
      if (e.target.id === 'sd-folder-save') {
        try {
          const path = $('sd-path').value.trim();
          if (!confirm(path ? 'Save new files in ' + path + ' and restart BloomClipping now?' : 'Go back to the default folder and restart BloomClipping now?')) return;
          await api('/storage/folder', { path, restart: true });
          msg('Restarting… this page reloads by itself.');
          for (let i = 0; i < 90; i++) {
            await new Promise(r => setTimeout(r, 2000));
            try { const h = await fetch('/healthz'); if (h.ok && i > 2) { location.reload(); return; } } catch (err) { /* still restarting */ }
          }
        } catch (err) { msg(err.message); }
      }
    });
    line();
    window.__storageLine = line;
    setInterval(() => { if (!document.hidden && !dlg.open) line(); }, 60000);

    // ---- Version card: current version and a one-click update check
    const ver = document.createElement('button');
    ver.type = 'button';
    ver.id = 'side-version';
    ver.className = 'side-card';
    ver.innerHTML = '<span class="sc-title">⟳ Updates</span><span class="sc-line" id="side-version-line">checking…</span>';
    (card.after ? card : side).after(ver);
    async function versionLine(force) {
      try {
        const u = await api('/update/status');
        const line = $('side-version-line');
        if (u.checkout) line.textContent = 'Developer copy (update with git)';
        else if (u.available) { line.textContent = 'New version ready'; ver.classList.add('low'); }
        else line.textContent = 'Up to date' + (u.current ? ' · ' + u.current : '');
      } catch (e) { $('side-version-line').textContent = 'Could not check'; }
    }
    ver.onclick = () => { const bar = $('update-bar'); if (bar && !bar.hidden) bar.scrollIntoView({ block: 'center', behavior: 'smooth' }); else versionLine(); };
    versionLine();

    // ---- Supporters as a small toggle
    const sup = $('supporters');
    if (sup) {
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'side-toggle';
      sup.before(toggle);
      sup.classList.add('collapsed');
      const label = () => {
        const n = sup.querySelectorAll('.supporter').length;
        toggle.innerHTML = '<span>♥ Supporters' + (n ? ' (' + n + ')' : '') + '</span><span class="chev">' + (sup.classList.contains('collapsed') ? '▸' : '▾') + '</span>';
        toggle.hidden = sup.hidden;
      };
      toggle.onclick = () => { sup.classList.toggle('collapsed'); label(); };
      new MutationObserver(label).observe(sup, { attributes: true, attributeFilter: ['hidden'], childList: true, subtree: true });
      label();
    }
  }
  // ---- Hamburger drawer
  function wireDrawer() {
    const btn = $('menu-btn'), drawer = $('nav-drawer'), backdrop = $('nav-backdrop');
    if (!btn || !drawer) return;
    const setOpen = open => {
      document.body.classList.toggle('nav-open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
      if (backdrop) backdrop.hidden = !open;
    };
    btn.addEventListener('click', () => setOpen(!document.body.classList.contains('nav-open')));
    if (backdrop) backdrop.addEventListener('click', () => setOpen(false));
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') setOpen(false);
      if ((e.metaKey || e.ctrlKey) && String(e.key).toLowerCase() === 'k') {
        const url = $('url');
        if (url && !e.target.closest('input,textarea,[contenteditable]')) {
          e.preventDefault();
          url.focus();
          url.select();
        }
      }
    });
    drawer.addEventListener('click', e => {
      if (e.target.closest('[data-view], #side-campaigns, #side-settings, #side-storage, .side-toggle')) setOpen(false);
    });
    const status = $('status-pill');
    if (status) status.addEventListener('click', () => {
      if (typeof window.openBloomSettings === 'function') window.openBloomSettings('system');
      else { const s = $('side-settings'); if (s) s.click(); }
    });
    const vid = $('hero-video'), mute = $('hero-mute');
    if (vid && mute) {
      const sync = () => {
        const muted = !!vid.muted;
        mute.setAttribute('aria-pressed', muted ? 'true' : 'false');
        mute.textContent = muted ? 'Unmute' : 'Mute';
      };
      mute.addEventListener('click', () => {
        vid.muted = !vid.muted;
        if (!vid.muted) vid.play().catch(() => {});
        sync();
      });
      vid.addEventListener('volumechange', sync);
      sync();
      vid.play().catch(() => {});
    }
  }

  if (document.readyState === 'complete') setTimeout(() => { init(); wireDrawer(); }, 400);
  else window.addEventListener('load', () => setTimeout(() => { init(); wireDrawer(); }, 400));
})();
