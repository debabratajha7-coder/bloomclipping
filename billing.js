// Plans + Google / demo login for BloomClipping.
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (t) => String(t == null ? '' : t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  let state = { plans: [], me: null, google_ready: false, demo: true };

  async function api(path, body) {
    const opts = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    const r = await fetch(path, opts);
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || j.message || 'Request failed');
    return j;
  }

  function paintAuth() {
    const box = $('auth-card');
    const pill = $('account-pill');
    if (!box) return;
    const me = state.me;
    if (pill) {
      if (me) {
        pill.hidden = false;
        pill.textContent = me.name ? me.name.split(' ')[0] : (me.email || 'Account');
        pill.title = me.email || 'Signed in';
      } else {
        pill.hidden = false;
        pill.textContent = 'Sign in';
        pill.title = 'Plans & login';
      }
    }
    if (!me) {
      box.innerHTML =
        '<h3>Sign in</h3>' +
        '<p class="muted">Sign in with Google to pick a plan and track your daily clip limit.</p>' +
        (state.google_ready
          ? '<a class="primary google-btn" href="/auth/google">Continue with Google</a>'
          : '<p class="billing-note">Google OAuth is not configured yet. Add <code>data/google_oauth.json</code> with <code>client_id</code> and <code>client_secret</code> from Google Cloud Console (redirect URI <code>http://127.0.0.1:8770/auth/google/callback</code>).</p>') +
        (state.demo
          ? '<button type="button" class="secondary" id="auth-demo">Continue locally (demo)</button>'
          : '') +
        '<p class="muted tiny">Instagram <a href="https://instagram.com/bloomgtavi" target="_blank" rel="noopener">@bloomgtavi</a></p>';
      const d = $('auth-demo');
      if (d) d.onclick = async () => {
        try {
          const r = await api('/auth/demo', {});
          state.me = r.me;
          paint();
        } catch (e) {
          note(e.message);
        }
      };
      return;
    }
    const left = me.clips_per_day == null ? 'Unlimited' : (me.clips_left_today + ' left today');
    box.innerHTML =
      '<div class="auth-row">' +
      (me.picture ? '<img class="auth-av" src="' + esc(me.picture) + '" alt="">' : '<span class="auth-av placeholder">✂</span>') +
      '<div><b>' + esc(me.name || 'Signed in') + '</b><small>' + esc(me.email) + '</small>' +
      '<small>' + (me.plan_name ? esc(me.plan_name) + ' · ' + esc(left) + ' · ' + esc(me.clips_used_today || 0) + ' used' : 'No plan yet') + '</small></div></div>' +
      '<button type="button" class="secondary" id="auth-logout">Sign out</button>';
    const out = $('auth-logout');
    if (out) out.onclick = async () => {
      try {
        await api('/auth/logout', {});
        state.me = null;
        paint();
      } catch (e) {
        note(e.message);
      }
    };
  }

  function paintPlans() {
    const host = $('plans-grid');
    if (!host) return;
    const active = state.me && state.me.plan;
    host.innerHTML = state.plans.map((p) => {
      const on = active === p.id;
      const limit = p.clips_per_day == null ? 'Unlimited clips' : p.clips_per_day + ' clips a day';
      return (
        '<article class="plan-card' + (p.highlight ? ' featured' : '') + (on ? ' on' : '') + '" data-plan="' + esc(p.id) + '">' +
        (p.highlight ? '<span class="plan-badge">Popular</span>' : '') +
        '<h3>' + esc(p.name) + '</h3>' +
        '<div class="plan-price"><b>₹' + p.price_inr + '</b><span>/ month</span></div>' +
        '<p>' + esc(p.blurb) + '</p>' +
        '<ul><li>' + esc(limit) + '</li><li>Local rendering on your Mac</li><li>Cancel anytime</li></ul>' +
        '<button type="button" class="' + (on ? 'secondary' : 'primary') + '" data-buy="' + esc(p.id) + '">' +
        (on ? 'Current plan' : 'Choose ' + esc(p.name)) + '</button></article>'
      );
    }).join('');
    host.querySelectorAll('[data-buy]').forEach((btn) => {
      btn.onclick = () => buy(btn.getAttribute('data-buy'));
    });
  }

  function note(t) {
    const n = $('plans-note');
    if (n) n.textContent = t || '';
  }

  async function buy(planId) {
    if (!state.me) {
      note('Sign in first, then choose a plan.');
      $('auth-card')?.scrollIntoView({ block: 'center', behavior: 'smooth' });
      return;
    }
    note('Activating…');
    try {
      const r = await api('/billing/activate', { plan: planId, confirm_demo: true });
      if (r.needs_payment && r.checkout_url) {
        window.open(r.checkout_url, '_blank', 'noopener');
        note(r.message || 'Complete payment, then choose the plan again.');
        return;
      }
      state.me = r.me;
      paint();
      note(r.message || 'Plan active.');
    } catch (e) {
      note(e.message);
    }
  }

  function paint() {
    paintAuth();
    paintPlans();
  }

  async function refresh() {
    try {
      const r = await api('/billing/plans');
      state.plans = r.plans || [];
      state.me = r.me;
      state.google_ready = !!r.google_ready;
      state.demo = !!r.demo;
      paint();
    } catch (e) {
      note(e.message);
    }
  }

  function showPlans() {
    const btn = document.querySelector('[data-view="plans"]');
    if (btn) btn.click();
    else {
      for (const key of ['editor', 'library', 'youtube', 'creators', 'plans']) {
        const el = $(key + '-view');
        if (el) el.hidden = key !== 'plans';
      }
      refresh();
    }
  }

  function init() {
    const account = $('account-pill');
    if (account) account.onclick = () => showPlans();
    document.querySelectorAll('[data-view="plans"]').forEach((b) => {
      b.addEventListener('click', () => setTimeout(refresh, 0));
    });
    if (new URLSearchParams(location.search).get('view') === 'plans') {
      setTimeout(showPlans, 200);
    }
    refresh();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  window.bloomBilling = { refresh, showPlans };
})();
