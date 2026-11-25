// My clips: a trash button on every card, and Select mode to delete many clips at once.
(function () {
  const $ = id => document.getElementById(id);
  async function api(path, body) {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || 'Request failed');
    return j;
  }
  const gb = b => b >= 1073741824 ? (b / 1073741824).toFixed(1) + ' GB' : Math.max(0, Math.round(b / 1048576)) + ' MB';
  const idOf = card => { const v = card.querySelector('video'); const m = v && (v.getAttribute('src') || '').match(/\/media\/([a-f0-9]{32})/); return m ? m[1] : ''; };

  function init() {
    const lib = $('library');
    const heading = document.querySelector('.library-heading');
    if (!lib || !heading || $('lib-tools')) return;
    const tools = document.createElement('div');
    tools.id = 'lib-tools';
    tools.className = 'lib-tools';
    tools.innerHTML = '<button type="button" class="mini-btn" id="lib-select">☑ Select clips</button>' +
      '<span id="lib-selecting" hidden class="lib-tools">' +
      '<button type="button" class="mini-btn" id="lib-all">Select all</button><button type="button" class="mini-btn" id="lib-none">Select none</button>' +
      '<label><input type="checkbox" id="lib-sources"> Also delete the source videos</label>' +
      '<button type="button" class="mini-btn warn" id="lib-delete" disabled>Delete selected</button>' +
      '<button type="button" class="mini-btn" id="lib-done">Done</button><span class="count" id="lib-count"></span></span>' +
      '<span class="count" id="lib-msg" role="status"></span>';
    heading.after(tools);

    let selecting = false;
    const cards = () => [...lib.querySelectorAll('.clip-card')];
    const picked = () => cards().filter(c => c.classList.contains('picked'));
    function refreshCount() {
      const n = picked().length;
      $('lib-delete').disabled = !n;
      $('lib-delete').textContent = n ? 'Delete ' + n + ' selected' : 'Delete selected';
      $('lib-count').textContent = selecting ? n + ' of ' + cards().length + ' selected' : '';
    }
    function setSelecting(on) {
      selecting = on;
      document.getElementById('library-view').classList.toggle('selecting', on);
      $('lib-select').hidden = on;
      $('lib-selecting').hidden = !on;
      if (!on) cards().forEach(c => c.classList.remove('picked'));
      decorate();
      refreshCount();
    }
    function toggle(card, on) {
      const box = card.querySelector('.pick');
      const value = on === undefined ? !card.classList.contains('picked') : on;
      card.classList.toggle('picked', value);
      if (box) box.checked = value;
      refreshCount();
    }
    // checkbox and trash button on every card (cards are rebuilt on each refresh)
    function decorate() {
      cards().forEach(card => {
        if (card.dataset.deco) return;
        const id = idOf(card);
        if (!id) return;
        card.dataset.deco = '1';
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.className = 'pick';
        box.setAttribute('aria-label', 'Select this clip');
        box.onchange = () => toggle(card, box.checked);
        card.prepend(box);
        const links = card.querySelector('.card-links');
        if (links) {
          const trash = document.createElement('button');
          trash.type = 'button';
          trash.className = 'trash';
          trash.title = 'Delete this clip';
          trash.textContent = '🗑';
          trash.onclick = () => remove([id], card.querySelector('h3') ? card.querySelector('h3').textContent : 'this clip');
          links.append(trash);
        }
        card.addEventListener('click', e => { if (selecting && !e.target.closest('a,button,video')) toggle(card); });
      });
    }
    async function remove(ids, label) {
      const withSources = $('lib-sources') && $('lib-sources').checked;
      const what = ids.length === 1 ? '"' + String(label).slice(0, 50) + '"' : ids.length + ' clips';
      if (!confirm('Permanently delete ' + what + (withSources ? ' and their source videos' : '') + '? This cannot be undone. Download anything you want to keep first.')) return;
      try {
        const r = await api('/library/delete', { ids, with_sources: !!withSources, confirm: true });
        $('lib-msg').textContent = 'Deleted ' + r.deleted + ' clip(s), freed ' + gb(r.freed) + '.';
        if (typeof refreshLibrary === 'function') await refreshLibrary();
        if (window.__storageLine) window.__storageLine();
        setTimeout(() => { $('lib-msg').textContent = ''; }, 8000);
        if (selecting) { decorate(); refreshCount(); }
      } catch (e) { $('lib-msg').textContent = e.message; }
    }
    $('lib-select').onclick = () => setSelecting(true);
    $('lib-done').onclick = () => setSelecting(false);
    $('lib-all').onclick = () => cards().forEach(c => toggle(c, true));
    $('lib-none').onclick = () => cards().forEach(c => toggle(c, false));
    $('lib-delete').onclick = () => remove(picked().map(idOf).filter(Boolean), '');
    new MutationObserver(() => { decorate(); refreshCount(); }).observe(lib, { childList: true });
    decorate();
  }
  if (document.readyState === 'complete') setTimeout(init, 500);
  else window.addEventListener('load', () => setTimeout(init, 500));
})();
