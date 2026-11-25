(function () {
  const filters = [
    ['all', 'All platforms'], ['GTA', 'GTA'],
    ['Streams', 'Streams'], ['gaming', 'Gaming'],
  ];
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };

  function affiliateLink(platform, label) {
    const link = element('a', 'campaign-join', label + ' ↗');
    link.href = platform.referral_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer sponsored';
    link.setAttribute('aria-label', link.textContent + ' · ' + platform.name + ' (opens in new tab)');
    const countClick = () => fetch('/campaigns/open', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: platform.id }), keepalive: true,
    }).catch(() => {});
    link.addEventListener('click', countClick);
    link.addEventListener('auxclick', event => { if (event.button === 1) countClick(); });
    return link;
  }

  function cardFor(platform) {
    const card = element('article', 'campaign-card');
    const mark = element('span', 'campaign-mark', platform.name[0]);
    mark.setAttribute('aria-hidden', 'true');
    const heading = element('header', 'campaign-card-title');
    heading.append(mark, element('h3', '', platform.name));
    const tags = element('div', 'campaign-tags');
    platform.good_for.forEach(tag => tags.append(element('span', '', tag)));

    const details = element('dl', 'campaign-details');
    const facts = [
      ['Pays', platform.pays], ['India payout', platform.india ? 'Available' : 'Unconfirmed'],
      ['Method', platform.payout], ['Minimum', platform.min_payout],
    ];
    for (const [label, value] of facts) {
      if (value) details.append(element('dt', '', label), element('dd', '', value));
    }
    const footer = element('footer', 'campaign-card-footer');
    footer.append(element('span', 'campaign-disclosure', 'Affiliate link'));
    footer.append(affiliateLink(platform, platform.action || 'Join'));
    card.append(heading, tags, details);
    if (platform.note) card.append(element('small', 'campaign-note', platform.note));
    card.append(footer);
    return card;
  }

  const usd = new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', minimumFractionDigits: 0,
  });
  const wholeUsd = new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 0,
  });

  function dealCard(deal) {
    const card = element('article', 'campaign-deal');
    const poster = element('div', 'campaign-poster');
    const img = element('img');
    img.src = deal.poster;
    img.alt = '';
    img.decoding = 'async';
    img.referrerPolicy = 'no-referrer';
    poster.append(img);

    const body = element('div', 'campaign-deal-body');
    const amount = element('div', 'campaign-money');
    const pool = deal.kind === 'pool';
    let price = pool ? wholeUsd.format(deal.amount) : usd.format(deal.amount);
    if (deal.variable) price = 'Up to ' + price;
    else if (!pool && deal.minimum < deal.amount) price = usd.format(deal.minimum) + '–' + price;
    amount.append(element('strong', '', price),
      element('span', '', pool ? 'total prize pool' : 'per 1,000 eligible views'));
    body.append(amount, element('h4', '', deal.title));
    const facts = [deal.organizer];
    if (pool && deal.shared_by_views) facts.push('Shared by views');
    else if (deal.budget) facts.push(wholeUsd.format(deal.budget) + ' total budget');
    body.append(element('p', '', facts.filter(Boolean).join(' · ')));
    const copy = element('button', 'mini-btn campaign-copy', 'Copy campaign name');
    copy.type = 'button';
    copy.setAttribute('aria-label', 'Copy campaign name · ' + deal.title);
    copy.onclick = async () => {
      try {
        await navigator.clipboard.writeText(deal.title);
        copy.textContent = 'Copied';
      } catch {
        copy.textContent = 'Copy unavailable';
      }
    };
    const actions = element('div', 'campaign-deal-actions');
    actions.append(copy, element('span', 'campaign-deal-status', 'Accepting clips'));
    body.append(actions);
    card.append(poster, body);
    return card;
  }

  const dialog = element('dialog', 'campaign-dialog');
  dialog.id = 'campaign-dialog';
  dialog.setAttribute('aria-labelledby', 'campaign-title');
  dialog.innerHTML = `<header class="campaign-header">
    <div><h2 id="campaign-title">Campaigns</h2>
      <p>Find a clipping brief and earn on eligible posts.</p>
      <p class="campaign-disclosure" hidden>BloomClipping may earn a commission through links marked Affiliate link.</p>
    </div>
    <button type="button" class="mini-btn" data-campaign-close autofocus>Close</button>
  </header>
  <section class="campaign-featured" aria-labelledby="campaign-featured-title" hidden>
    <div class="campaign-featured-header">
      <div><h3 id="campaign-featured-title">Featured payouts</h3>
        <p>Open clipping campaigns on Content Rewards</p>
      </div>
      <div class="campaign-featured-action"><span class="campaign-disclosure">Affiliate link</span></div>
    </div>
    <div class="campaign-deal-grid"></div>
    <p class="campaign-deal-note" role="status"></p>
  </section>
  <h3 class="campaign-directory-title">Partner platforms</h3>
  <div class="campaign-filters" role="group" aria-label="Campaign filters"></div>
  <div class="campaign-feedback" role="status"></div>
  <div class="campaign-grid"></div>`;
  document.body.append(dialog);

  const chips = dialog.querySelector('.campaign-filters');
  const feedback = dialog.querySelector('.campaign-feedback');
  const grid = dialog.querySelector('.campaign-grid');
  const disclosure = dialog.querySelector('.campaign-disclosure');
  const featured = dialog.querySelector('.campaign-featured');
  const dealsGrid = dialog.querySelector('.campaign-deal-grid');
  const dealNote = dialog.querySelector('.campaign-deal-note');
  const featuredAction = dialog.querySelector('.campaign-featured-action');
  let currentFilter = 'all';
  let platforms = [];
  let loadNumber = 0;

  async function loadDeals(platform, attempt) {
    if (!platform) return;
    featured.hidden = false;
    featuredAction.replaceChildren(element('span', 'campaign-disclosure', 'Affiliate link'),
      affiliateLink(platform, platform.action || 'Join Content Rewards'));
    dealNote.textContent = 'Checking open campaigns…';
    try {
      const reply = await fetch('/campaigns/deals', { cache: 'no-store' });
      if (!reply.ok) throw new Error('Public deals unavailable');
      const data = await reply.json();
      if (attempt !== loadNumber) return;
      dealsGrid.replaceChildren(...data.deals.map(dealCard));
      const checked = data.checked && new Date(data.checked);
      dealNote.textContent = data.deals.length
        ? 'Checked ' + checked.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) +
          ' · USD · Check each brief for eligibility and payout terms.'
        : 'No featured offers are available right now.';
    } catch {
      if (attempt === loadNumber) dealNote.textContent = 'Featured offers are temporarily unavailable.';
    }
  }

  function render() {
    for (const button of chips.children) {
      button.setAttribute('aria-pressed', button.dataset.filter === currentFilter);
    }
    const visible = platforms.filter(platform => {
      if (currentFilter === 'all') return true;
      if (currentFilter === 'gaming') return platform.good_for.some(tag => tag === 'GTA' || tag === 'Streams');
      return platform.good_for.includes(currentFilter);
    });
    feedback.textContent = visible.length ? '' : platforms.length ? 'No platforms match this filter.' :
      'Affiliate campaigns will appear here when their partner links are available.';
    grid.replaceChildren(...visible.map(cardFor));
  }

  for (const [key, label] of filters) {
    const button = element('button', 'campaign-filter', label);
    button.type = 'button';
    button.dataset.filter = key;
    button.addEventListener('click', () => {
      currentFilter = key;
      render();
    });
    chips.append(button);
  }

  async function open(filter = 'all') {
    const attempt = ++loadNumber;
    currentFilter = filter;
    chips.hidden = true;
    disclosure.hidden = true;
    featured.hidden = true;
    dealsGrid.replaceChildren();
    grid.replaceChildren();
    feedback.textContent = 'Loading campaigns…';
    if (!dialog.open) dialog.showModal();
    dialog.scrollTop = 0;
    try {
      const response = await fetch('/campaigns', { cache: 'no-store' });
      if (!response.ok) throw new Error('Campaigns unavailable');
      const data = await response.json();
      if (attempt !== loadNumber) return;
      platforms = data.platforms.filter(platform => platform.referral_url);
      disclosure.hidden = !platforms.length;
      chips.hidden = platforms.length < 2;
      if (chips.hidden) currentFilter = 'all';
      render();
      loadDeals(platforms.find(platform => platform.id === 'contentrewards'), attempt);
    } catch {
      if (attempt !== loadNumber) return;
      feedback.textContent = 'Campaigns could not load. ';
      const retry = element('button', 'mini-btn', 'Retry');
      retry.type = 'button';
      retry.onclick = () => open(currentFilter);
      feedback.append(retry);
    }
  }

  dialog.querySelector('[data-campaign-close]').onclick = () => dialog.close();
  document.getElementById('side-campaigns').onclick = () => open();
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-campaign-clip]');
    if (!trigger) return;
    const game = trigger.dataset.campaignClip;
    open(/\bgta|grand theft auto/i.test(game) ? 'GTA' : game ? 'gaming' : 'all');
  });
})();
