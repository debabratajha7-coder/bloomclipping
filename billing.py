"""Plans + Google login + clip credits for BloomClipping.

Plans:
  free      — ₹0   — 5 clip credits (one-time pool)
  daily10   — ₹19  — 10 clips / day
  fifty     — ₹99  — 50 clips / day
  unlimited — ₹199 — unlimited clips

Google OAuth needs BLOOMCLIPPING_GOOGLE_CLIENT_ID + BLOOMCLIPPING_GOOGLE_CLIENT_SECRET
(or data/google_oauth.json). Without them, demo local sign-in is available so the UI works.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

FREE_CREDITS = 5

PLANS = {
    'free': {
        'id': 'free',
        'name': 'Free',
        'price_inr': 0,
        'clips_per_day': None,
        'credits': FREE_CREDITS,
        'credit_mode': 'pool',
        'blurb': '5 free clip credits — try BloomClipping with no payment.',
        'highlight': False,
    },
    'daily10': {
        'id': 'daily10',
        'name': 'Daily 10',
        'price_inr': 19,
        'clips_per_day': 10,
        'credits': 0,
        'credit_mode': 'daily',
        'blurb': '10 clips a day — for light posting.',
        'highlight': False,
    },
    'fifty': {
        'id': 'fifty',
        'name': 'Fifty',
        'price_inr': 99,
        'clips_per_day': 50,
        'credits': 0,
        'credit_mode': 'daily',
        'blurb': '50 clips a day — for serious creators.',
        'highlight': True,
    },
    'unlimited': {
        'id': 'unlimited',
        'name': 'Unlimited',
        'price_inr': 199,
        'clips_per_day': None,
        'credits': 0,
        'credit_mode': 'unlimited',
        'blurb': 'Unlimited clips — no daily cap.',
        'highlight': False,
    },
}

COOKIE = 'bc_session'
SESSION_DAYS = 30
PLAN_DAYS = 30


def _now() -> float:
    return time.time()


def _today() -> str:
    return date.today().isoformat()


def _cfg(data: Path) -> dict:
    out = {
        'client_id': (os.environ.get('BLOOMCLIPPING_GOOGLE_CLIENT_ID') or '').strip(),
        'client_secret': (os.environ.get('BLOOMCLIPPING_GOOGLE_CLIENT_SECRET') or '').strip(),
        'razorpay_key': (os.environ.get('BLOOMCLIPPING_RAZORPAY_KEY') or '').strip(),
        'razorpay_link': (os.environ.get('BLOOMCLIPPING_RAZORPAY_LINK') or '').strip(),
        'demo': (os.environ.get('BLOOMCLIPPING_BILLING_DEMO') or '1').strip() not in ('0', 'false', 'no'),
    }
    p = data / 'google_oauth.json'
    if p.is_file():
        try:
            j = json.loads(p.read_text(encoding='utf-8'))
            out['client_id'] = str(j.get('client_id') or out['client_id']).strip()
            out['client_secret'] = str(j.get('client_secret') or out['client_secret']).strip()
        except Exception:
            pass
    p2 = data / 'billing.json'
    if p2.is_file():
        try:
            j = json.loads(p2.read_text(encoding='utf-8'))
            if j.get('razorpay_key'):
                out['razorpay_key'] = str(j['razorpay_key']).strip()
            if j.get('razorpay_link'):
                out['razorpay_link'] = str(j['razorpay_link']).strip()
            if 'demo' in j:
                out['demo'] = bool(j['demo'])
        except Exception:
            pass
    return out


def _secret(data: Path) -> bytes:
    p = data / 'session.secret'
    if p.is_file():
        return p.read_bytes()
    raw = secrets.token_bytes(32)
    p.write_bytes(raw)
    try:
        p.chmod(0o600)
    except Exception:
        pass
    return raw


def _sign(data: Path, payload: str) -> str:
    sig = hmac.new(_secret(data), payload.encode(), hashlib.sha256).hexdigest()
    return payload + '.' + sig


def _unsign(data: Path, token: str) -> str | None:
    if not token or '.' not in token:
        return None
    payload, sig = token.rsplit('.', 1)
    expect = hmac.new(_secret(data), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return None
    return payload


def _users_dir(data: Path) -> Path:
    d = data / 'users'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sessions_path(data: Path) -> Path:
    return data / 'sessions.json'


def _load_sessions(data: Path) -> dict:
    p = _sessions_path(data)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_sessions(data: Path, sessions: dict) -> None:
    _sessions_path(data).write_text(json.dumps(sessions, indent=2), encoding='utf-8')


def _user_path(data: Path, uid: str) -> Path:
    return _users_dir(data) / (uid + '.json')


def _load_user(data: Path, uid: str) -> dict | None:
    p = _user_path(data, uid)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def _save_user(data: Path, user: dict) -> None:
    uid = user['id']
    _user_path(data, uid).write_text(json.dumps(user, indent=2), encoding='utf-8')


def _public_user(user: dict | None) -> dict | None:
    if not user:
        return None
    plan = PLANS.get(user.get('plan') or '')
    usage = (user.get('usage') or {}).get(_today(), 0)
    mode = (plan or {}).get('credit_mode')
    limit = plan['clips_per_day'] if plan else 0
    credits = int(user.get('credits') or 0)
    if mode == 'pool':
        left_today = credits
        left_label = 'credits'
    elif mode == 'unlimited':
        left_today = None
        left_label = 'unlimited'
    elif mode == 'daily':
        left_today = max(0, (limit or 0) - usage)
        left_label = 'today'
    else:
        left_today = credits
        left_label = 'credits'
    return {
        'id': user['id'],
        'email': user.get('email') or '',
        'name': user.get('name') or '',
        'picture': user.get('picture') or '',
        'provider': user.get('provider') or 'local',
        'plan': user.get('plan'),
        'plan_name': plan['name'] if plan else None,
        'plan_until': user.get('plan_until'),
        'credit_mode': mode,
        'credits': credits,
        'clips_per_day': limit if mode == 'daily' else None,
        'clips_used_today': usage if mode == 'daily' else 0,
        'clips_left_today': left_today,
        'left_label': left_label,
    }


def session_user(data: Path, request: Request) -> dict | None:
    token = request.cookies.get(COOKIE)
    sid = _unsign(data, token or '')
    if not sid:
        return None
    sessions = _load_sessions(data)
    row = sessions.get(sid)
    if not row or row.get('exp', 0) < _now():
        return None
    return _load_user(data, row['uid'])


def _set_cookie(response: Response, data: Path, uid: str) -> None:
    sid = secrets.token_urlsafe(24)
    sessions = _load_sessions(data)
    sessions[sid] = {'uid': uid, 'exp': _now() + SESSION_DAYS * 86400}
    # prune
    cut = _now()
    sessions = {k: v for k, v in sessions.items() if v.get('exp', 0) > cut}
    _save_sessions(data, sessions)
    response.set_cookie(
        COOKIE,
        _sign(data, sid),
        httponly=True,
        samesite='lax',
        max_age=SESSION_DAYS * 86400,
        path='/',
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path='/')


def _upsert_google_user(data: Path, profile: dict) -> dict:
    sub = str(profile.get('sub') or '')
    email = str(profile.get('email') or '').lower()
    users = list(_users_dir(data).glob('*.json'))
    for p in users:
        try:
            u = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        if u.get('google_sub') == sub or (email and u.get('email') == email):
            u['email'] = email or u.get('email')
            u['name'] = profile.get('name') or u.get('name') or ''
            u['picture'] = profile.get('picture') or u.get('picture') or ''
            u['google_sub'] = sub or u.get('google_sub')
            u['provider'] = 'google'
            u['updated'] = _now()
            if not u.get('plan'):
                activate_plan(u, 'free')
            _save_user(data, u)
            return u
    uid = 'g_' + hashlib.sha256((sub or email or secrets.token_hex(8)).encode()).hexdigest()[:16]
    user = {
        'id': uid,
        'email': email,
        'name': profile.get('name') or '',
        'picture': profile.get('picture') or '',
        'google_sub': sub,
        'provider': 'google',
        'plan': None,
        'plan_until': None,
        'credits': 0,
        'usage': {},
        'created': _now(),
        'updated': _now(),
    }
    activate_plan(user, 'free')
    _save_user(data, user)
    return user


def _demo_user(data: Path) -> dict:
    uid = 'local_demo'
    user = _load_user(data, uid)
    if user:
        if not user.get('plan'):
            activate_plan(user, 'free')
            _save_user(data, user)
        return user
    user = {
        'id': uid,
        'email': 'you@local',
        'name': 'Local account',
        'picture': '',
        'provider': 'demo',
        'plan': None,
        'plan_until': None,
        'credits': 0,
        'usage': {},
        'created': _now(),
        'updated': _now(),
    }
    activate_plan(user, 'free')
    _save_user(data, user)
    return user


def activate_plan(user: dict, plan_id: str) -> dict:
    plan = PLANS.get(plan_id)
    if not plan:
        raise HTTPException(400, 'Unknown plan.')
    user['plan'] = plan_id
    user['updated'] = _now()
    mode = plan.get('credit_mode')
    if mode == 'pool':
        user['plan_until'] = None
        if not user.get('free_credits_granted'):
            user['credits'] = int(plan.get('credits') or FREE_CREDITS)
            user['free_credits_granted'] = True
        else:
            user.setdefault('credits', 0)
    elif mode == 'unlimited':
        user['plan_until'] = datetime.now(timezone.utc).timestamp() + PLAN_DAYS * 86400
    else:
        user['plan_until'] = datetime.now(timezone.utc).timestamp() + PLAN_DAYS * 86400
    return user


def plan_active(user: dict | None) -> dict | None:
    if not user or not user.get('plan'):
        return None
    plan = PLANS.get(user['plan'])
    if not plan:
        return None
    if plan.get('credit_mode') == 'pool' or plan.get('price_inr') == 0:
        return plan
    until = user.get('plan_until') or 0
    if until and until < _now():
        return None
    return plan


def guard_make(data: Path, request: Request, clip_count: int = 1) -> None:
    """Guests stay unlimited (local studio). Signed-in plans spend credits or daily quota.
    Set BLOOMCLIPPING_BILLING_REQUIRED=1 to require sign-in + plan before Make clips."""
    user = session_user(data, request)
    required = (os.environ.get('BLOOMCLIPPING_BILLING_REQUIRED') or '').strip() in ('1', 'true', 'yes')
    plan = plan_active(user)
    if required and (not user or not plan):
        raise HTTPException(
            402,
            'Sign in and pick a plan under Plans. Free = 5 credits · Daily 10 ₹19 · Fifty ₹99 · Unlimited ₹199.',
        )
    if not user or not plan:
        return
    need = max(1, int(clip_count or 1))
    mode = plan.get('credit_mode')
    if mode == 'unlimited':
        return
    if mode == 'pool':
        credits = int(user.get('credits') or 0)
        if credits < need:
            raise HTTPException(
                402,
                f'No clip credits left ({credits} remaining). Free includes {FREE_CREDITS} clips — upgrade under Plans for more.',
            )
        user['credits'] = credits - need
        user['updated'] = _now()
        _save_user(data, user)
        return
    limit = plan.get('clips_per_day')
    if limit is None:
        return
    today = _today()
    usage = dict(user.get('usage') or {})
    used = int(usage.get(today) or 0)
    if used + need > limit:
        left = max(0, limit - used)
        raise HTTPException(
            402,
            f'Plan limit reached: {used}/{limit} clips used today. {left} left. Upgrade under Plans, or wait until tomorrow.',
        )
    usage[today] = used + need
    keys = sorted(usage.keys())
    for k in keys[:-14]:
        usage.pop(k, None)
    user['usage'] = usage
    user['updated'] = _now()
    _save_user(data, user)


def _http_json(url: str, data: dict | None = None, headers: dict | None = None) -> dict:
    body = None
    hdrs = {'User-Agent': 'BloomClipping-auth', 'Accept': 'application/json'}
    if headers:
        hdrs.update(headers)
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
    req = urllib.request.Request(url, data=body, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors='ignore')[:300]
        raise HTTPException(502, 'Google auth failed: ' + detail) from e
    except Exception as e:
        raise HTTPException(502, 'Google auth failed: ' + str(e)[-160:]) from e


def attach(app: FastAPI, data: Path) -> None:
    @app.get('/billing/plans')
    def billing_plans(request: Request):
        cfg = _cfg(data)
        user = session_user(data, request)
        return {
            'currency': 'INR',
            'plans': list(PLANS.values()),
            'google_ready': bool(cfg['client_id'] and cfg['client_secret']),
            'demo': cfg['demo'],
            'razorpay_ready': bool(cfg['razorpay_key'] or cfg['razorpay_link']),
            'me': _public_user(user),
        }

    @app.get('/auth/me')
    def auth_me(request: Request):
        cfg = _cfg(data)
        return {
            'me': _public_user(session_user(data, request)),
            'google_ready': bool(cfg['client_id'] and cfg['client_secret']),
            'demo': cfg['demo'],
        }

    @app.get('/auth/google')
    def auth_google(request: Request):
        cfg = _cfg(data)
        if not (cfg['client_id'] and cfg['client_secret']):
            raise HTTPException(400, 'Google login is not configured. Add client_id/secret in data/google_oauth.json or env vars.')
        state = secrets.token_urlsafe(16)
        # stash state in a short-lived cookie
        redirect_uri = str(request.base_url).rstrip('/') + '/auth/google/callback'
        params = urllib.parse.urlencode({
            'client_id': cfg['client_id'],
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'online',
            'include_granted_scopes': 'true',
            'state': state,
            'prompt': 'select_account',
        })
        resp = RedirectResponse('https://accounts.google.com/o/oauth2/v2/auth?' + params)
        resp.set_cookie('bc_oauth_state', state, httponly=True, samesite='lax', max_age=600, path='/')
        return resp

    @app.get('/auth/google/callback')
    def auth_google_callback(request: Request, code: str = '', state: str = ''):
        cfg = _cfg(data)
        if not code:
            raise HTTPException(400, 'Google did not return a code.')
        if state != request.cookies.get('bc_oauth_state'):
            raise HTTPException(400, 'Google login state mismatch. Try again.')
        redirect_uri = str(request.base_url).rstrip('/') + '/auth/google/callback'
        tok = _http_json('https://oauth2.googleapis.com/token', {
            'code': code,
            'client_id': cfg['client_id'],
            'client_secret': cfg['client_secret'],
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        })
        access = tok.get('access_token')
        if not access:
            raise HTTPException(502, 'Google did not return an access token.')
        profile = _http_json(
            'https://openidconnect.googleapis.com/v1/userinfo',
            headers={'Authorization': 'Bearer ' + access},
        )
        user = _upsert_google_user(data, profile)
        resp = RedirectResponse('/?view=plans&login=1')
        _set_cookie(resp, data, user['id'])
        resp.delete_cookie('bc_oauth_state', path='/')
        return resp

    @app.post('/auth/demo')
    def auth_demo(request: Request):
        cfg = _cfg(data)
        if not cfg['demo']:
            raise HTTPException(403, 'Demo login is off. Configure Google OAuth.')
        user = _demo_user(data)
        resp = JSONResponse({'ok': True, 'me': _public_user(user)})
        _set_cookie(resp, data, user['id'])
        return resp

    @app.post('/auth/logout')
    def auth_logout():
        resp = JSONResponse({'ok': True})
        _clear_cookie(resp)
        return resp

    @app.post('/billing/activate')
    def billing_activate(body: dict, request: Request):
        user = session_user(data, request)
        if not user:
            raise HTTPException(401, 'Sign in with Google first.')
        plan_id = str((body or {}).get('plan') or '')
        if plan_id not in PLANS:
            raise HTTPException(400, 'Pick Free, Daily 10, Fifty, or Unlimited.')
        cfg = _cfg(data)
        plan = PLANS[plan_id]
        # Free never needs payment
        if plan.get('price_inr', 0) > 0:
            if cfg['razorpay_link'] and not (body or {}).get('confirm_demo'):
                return {
                    'ok': False,
                    'needs_payment': True,
                    'checkout_url': cfg['razorpay_link'],
                    'plan': plan,
                    'message': 'Pay on Razorpay, then return and choose the plan again — or use demo billing locally.',
                }
            if not cfg['demo'] and not cfg['razorpay_link']:
                raise HTTPException(400, 'Payments are not configured. Set BLOOMCLIPPING_RAZORPAY_LINK or enable demo billing.')
        activate_plan(user, plan_id)
        _save_user(data, user)
        if plan.get('credit_mode') == 'pool':
            msg = f'Free plan active — {int(user.get("credits") or 0)} clip credits left.'
        elif plan.get('credit_mode') == 'unlimited':
            msg = f'{plan["name"]} is active for {PLAN_DAYS} days (unlimited clips).'
        else:
            msg = f'{plan["name"]} is active for {PLAN_DAYS} days.'
        return {'ok': True, 'me': _public_user(user), 'message': msg}
