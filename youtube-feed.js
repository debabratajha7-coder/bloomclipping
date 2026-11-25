(function () {
  const refreshNote = document.getElementById('youtube-refresh-note');
  const liveGrid = document.getElementById('youtube-live');
  const videoGrid = document.getElementById('youtube-videos');
  const sort = document.getElementById('youtube-sort');
  const scope = document.getElementById('youtube-scope');
  const sidebarCount = document.getElementById('youtube-live-count');
  const status = document.getElementById('youtube-feed-status');
  const compact = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 });
  const dateLabel = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' });
  let payload;
  let timer;
  let running = false;
  let queued = false;
  const rendered = {};

  function node(tag, css, text) {
    const element = document.createElement(tag);
    if (css) element.className = css;
    if (text) element.textContent = text;
    return element;
  }

  function isSaved(item) {
    return (payload.saved_channels || []).includes(item.channel?.toLowerCase()) ||
      (payload.saved_ids || []).includes(item.channel_id);
  }

  function card(item) {
    const url = 'https://www.youtube.com/watch?v=' + item.id;
    const article = node('article', 'youtube-card');
    const watch = node('a', 'youtube-thumb');
    watch.href = url;
    watch.target = '_blank';
    watch.rel = 'noopener noreferrer';
    watch.setAttribute('aria-label', 'Watch on YouTube: ' + item.title);
    const thumb = node('img');
    thumb.src = 'https://i.ytimg.com/vi/' + item.id + '/mqdefault.jpg';
    thumb.loading = 'lazy';
    thumb.referrerPolicy = 'no-referrer';
    thumb.alt = '';
    watch.append(thumb);
    if (item.live) watch.append(node('span', 'youtube-live-label', '● LIVE'));
    const details = node('div', 'youtube-card-details');
    details.append(node('h3', '', item.title));
    const meta = [item.creator];
    if (item.replay) meta.push('Replay');
    if (Number.isFinite(item.views)) meta.push(compact.format(item.views) + (item.live ? ' watching' : ' views'));
    if (item.published && !item.live) meta.push(dateLabel.format(item.published * 1000));
    details.append(node('p', '', meta.join(' · ')));
    const use = node('button', 'mini-btn youtube-use', item.live ? 'Use live link' : 'Use in Create clips');
    use.type = 'button';
    use.onclick = () => {
      if (item.live) showLiveControls();
      else document.querySelector('[data-view="editor"]').click();
      const input = document.getElementById(item.live ? 'live-url' : 'url');
      const panel = input.closest('details');
      if (panel) panel.open = true;
      input.value = url;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.focus();
    };
    const saved = isSaved(item);
    const save = node('button', 'mini-btn', saved ? 'Manage creator' : 'Add to Creators');
    save.type = 'button';
    save.hidden = !item.channel;
    save.onclick = async () => {
      if (saved || isSaved(item)) {
        document.querySelector('[data-view="creators"]').click();
        return;
      }
      save.disabled = true;
      try {
        await saveTrackedCreator('https://www.youtube.com/' + item.channel, false);
        payload.saved_channels = [...(payload.saved_channels || []), item.channel.toLowerCase()];
        status.textContent = item.creator + ' added. Enable auto-clipping in Creators.';
        render();
      } catch (error) {
        status.textContent = error.message;
      } finally {
        save.disabled = false;
      }
    };
    const actions = node('div', 'youtube-card-actions');
    actions.append(use, save);
    details.append(actions);
    article.append(watch, details);
    return article;
  }

  function setText(element, message) {
    if (element.textContent !== message) element.textContent = message;
  }

  function updateGrid(grid, entries, message) {
    const signature = JSON.stringify([entries, message, entries.map(isSaved)]);
    if (rendered[grid.id] === signature) return;
    rendered[grid.id] = signature;
    grid.replaceChildren(...(entries.length ? entries.map(card) : [node('p', 'youtube-empty', message)]));
  }

  function render() {
    const { updated, refreshing, channels, live_checked: liveChecked, failures } = payload;
    const watchingSaved = scope.value === 'saved';
    const selected = watchingSaved ? payload.saved_feed || { live: [], latest: [], popular: [] } : payload;
    const { live, latest, popular } = selected;
    const noSaved = watchingSaved && !(payload.saved_channels || []).length;
    const checked = updated && new Date(updated * 1000).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    const note = refreshing ? 'Checking YouTube…' :
      !updated ? 'YouTube is temporarily unavailable. Retrying automatically.' :
      'Updated ' + checked + ' · ' + liveChecked + '/' + channels + ' live feeds checked' +
        (failures ? ' · Some sources unavailable' : '');
    setText(refreshNote, note);
    sidebarCount.hidden = !payload.live.length;
    setText(sidebarCount, payload.live.length ? String(payload.live.length) + ' LIVE' : '');
    updateGrid(liveGrid, live, noSaved ? 'Add a YouTube channel in Creators or save one from this feed.' :
      refreshing ? 'Checking for live streams…' :
      liveChecked ? 'No live streams found among the checked creators.' : 'Live status is temporarily unavailable.');
    updateGrid(videoGrid, sort.value === 'latest' ? latest : popular,
      noSaved ? 'Saved YouTube channels will appear here.' :
        refreshing ? 'Finding videos…' : 'No videos available here yet.');
  }

  async function poll() {
    clearTimeout(timer);
    if (document.hidden || running) return;
    running = true;
    try {
      const response = await fetch('/youtube-feed', { cache: 'no-store' });
      if (!response.ok) throw new Error('Feed unavailable');
      payload = await response.json();
      render();
    } catch {
      setText(refreshNote, 'Could not update the feed. Retrying automatically.');
    } finally {
      running = false;
      timer = setTimeout(poll, queued ? 0 : payload?.refreshing ? 2500 : 45000);
      queued = false;
    }
  }

  sort.onchange = () => { if (payload) render(); };
  scope.onchange = () => { if (payload) render(); };
  document.addEventListener('creator-watchlist-change', () => {
    if (running) queued = true;
    else poll();
  });
  document.addEventListener('visibilitychange', poll);
  poll();
})();
