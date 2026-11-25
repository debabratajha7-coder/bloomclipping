"""Takes the guide screenshots of a running BloomClipping (http://127.0.0.1:8770) and draws numbered markers and arrows on them.

Needs: the app running, Python packages playwright and pillow, Google Chrome installed, and a demo clip made from a fake source
(see build_guides.py header). Output: img/<name>.jpg plus img/shots.json (marker order per shot), used by build_guides.py.
Re-run this whenever the screen changes so the guides do not go stale.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
OUT = HERE / 'img'
OUT.mkdir(exist_ok=True)
BASE = __import__('os').environ.get('GUIDE_BASE', 'http://127.0.0.1:8791')   # a CLEAN instance with its own empty data folder, never your real one
DPR = 1.5
PINK = (255, 61, 110)

DEMO_SOURCE = {'id': 'guidedemo0001', 'w': 1920, 'h': 1080, 'duration': 30}
DEMO_CLIP = sys.argv[1] if len(sys.argv) > 1 else ''

# name -> (setup function name, [(selector, marker note)])  ; markers are numbered in the order listed
SHOTS = {
    'home': ('home', [('[data-view=editor]', 'r'), ('[data-view=library]', 'r'), ('#nav-clip-editor', 'r'), ('#url', 't'), ('#srcq', 'b'), ('#link', 't'), ('#make', 'b'), ('#rb-make', 'l')]),
    'frame': ('frame', [('#source', 'l'), ('#layouts', 'r'), ('#top', 'b')]),
    'captions': ('captions', [('.caption-styles', 'l'), ('#captions', 'r'), ('#language', 'r'), ('#hook', 'b')]),
    'live': ('live', [('#rb-canvas', 'l'), ('#rb-make', 'l'), ('#rb-tabs', 'l'), ('.rb-styles', 'l')]),
    'library': ('library', [('#lib-select', 'b'), ('.clip-card', 'l'), ('.clip-card .trash', 'b')]),
    'editor': ('editor', [('#ed-list', 'b'), ('#ed-stage', 'l'), ('#ed-lane', 'b'), ('#ed-tabs', 't'), ('#ed-export', 'r')]),
    'editor_frame': ('editor_frame', [('.ed-lays', 'l'), ('#ed-frame', 'l')]),
    'editor_split': ('editor_split', [('#ed-split', 't'), ('#ed-lane', 'b'), ('#ed-capl', 'b')]),
    'storage': ('storage', [('#storage-dialog .sd-summary', 'l'), ('#storage-dialog [data-clean]', 'l'), ('#sd-open', 'l')]),
    'updates': ('updates', [('#side-version', 'r'), ('#update-bar', 'b'), ('#side-storage', 'r')]),
}
TALL = {'editor', 'editor_frame', 'editor_split'}


def font(size):
    for f in ('C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/segoeuib.ttf'):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def annotate(path, boxes, sides=None):
    im = Image.open(path).convert('RGB')
    d = ImageDraw.Draw(im, 'RGBA')
    W, H = im.size
    r = int(17 * DPR)
    f = font(int(18 * DPR))
    for n, b in enumerate(boxes, 1):
        x, y, w, h = [v * DPR for v in b]
        d.rounded_rectangle([x - 4, y - 4, x + w + 4, y + h + 4], radius=10, outline=PINK + (255,), width=int(3 * DPR))
        # badge goes to the side of the box that has the most room, an arrow joins it to the box
        room = {'l': x, 'r': W - (x + w), 't': y, 'b': H - (y + h)}
        side = sides[n - 1] if sides and sides[n - 1] in room and room[sides[n - 1]] > r * 4 else max(room, key=room.get)
        gap = r * 3.2
        cx, cy = x + w / 2, y + h / 2
        bx, by = {'l': (x - gap, cy), 'r': (x + w + gap, cy), 't': (cx, y - gap), 'b': (cx, y + h + gap)}[side]
        bx = min(max(bx, r + 4), W - r - 4)
        by = min(max(by, r + 4), H - r - 4)
        tx, ty = {'l': (x - 4, cy), 'r': (x + w + 4, cy), 't': (cx, y - 4), 'b': (cx, y + h + 4)}[side]
        # clamp the arrow target to the box when the badge was clamped
        d.line([bx, by, tx, ty], fill=PINK + (255,), width=int(3 * DPR))
        ang = __import__('math').atan2(ty - by, tx - bx)
        L = 11 * DPR
        d.polygon([(tx, ty), (tx - L * __import__('math').cos(ang - .45), ty - L * __import__('math').sin(ang - .45)),
                   (tx - L * __import__('math').cos(ang + .45), ty - L * __import__('math').sin(ang + .45))], fill=PINK + (255,))
        d.ellipse([bx - r, by - r, bx + r, by + r], fill=PINK + (255,), outline=(255, 255, 255, 255), width=int(2 * DPR))
        d.text((bx, by), str(n), fill=(255, 255, 255), font=f, anchor='mm')
    im.save(path, 'JPEG', quality=84)


def main():
    keep = {}
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1600, 'height': 900}, device_scale_factor=DPR)
        page = ctx.new_page()
        page.on('dialog', lambda d: d.accept())

        def fresh():
            page.goto(BASE)
            page.wait_for_timeout(2500)

        def box(sel):
            loc = page.locator(sel).first
            try:
                if loc.count() == 0 or not loc.is_visible():
                    return None
                return loc.bounding_box()
            except Exception:
                return None

        def source():
            page.evaluate("(j)=>{setSource(j,3); $('hook').value='Paste a link. Get clips.';}", DEMO_SOURCE)
            page.wait_for_timeout(2500)

        def scroll_to(sel, block='start'):
            page.evaluate("([s,b])=>document.querySelector(s).scrollIntoView({block:b})", [sel, block])
            page.wait_for_timeout(500)

        setups = {}
        setups['home'] = lambda: (fresh(), page.evaluate("document.body.classList.add('rb-open')"), page.wait_for_timeout(600))
        def adv(key, then):
            fresh()
            source()
            page.click('#adv-toggle')
            page.wait_for_timeout(400)
            page.click('.tab[data-key=%s]' % key)
            page.wait_for_timeout(800)
            scroll_to(then, 'center')
        setups['frame'] = lambda: adv('frame', '#source')
        setups['captions'] = lambda: adv('captions', '.caption-styles')
        setups['live'] = lambda: (fresh(), source(), page.evaluate("document.body.classList.add('rb-open')"), page.evaluate("document.querySelector('.caption-choice[data-style=mrbeast]').click()"), page.wait_for_timeout(900))
        setups['library'] = lambda: (fresh(), page.click('[data-view=library]'), page.wait_for_timeout(2500))
        setups['editor'] = lambda: (fresh(), page.evaluate("(i)=>window.openInEditor(i)", DEMO_CLIP), page.wait_for_timeout(6500), scroll_to('#clip-editor-view', 'start'))
        setups['editor_frame'] = lambda: (setups['editor'](), page.click('[data-tab=framing]'), page.wait_for_timeout(1000), scroll_to('.ed-lays', 'start'))

        def split():
            setups['editor']()
            page.evaluate("document.getElementById('ed-lane').scrollIntoView({block:'center'})")
            b = box('#ed-lane')
            page.mouse.click(b['x'] + b['width'] * .5, b['y'] + b['height'] / 2)
            page.wait_for_timeout(500)
            page.click('#ed-split')
            page.wait_for_timeout(1500)
        setups['editor_split'] = split
        setups['storage'] = lambda: (fresh(), page.click('#side-storage'), page.wait_for_timeout(1800))

        def updates():
            fresh()
            page.evaluate("()=>{const b=document.getElementById('update-bar'); if(b){b.hidden=false; const t=document.getElementById('update-text'); if(t) t.textContent='A new version of BloomClipping is ready.';}}")
            page.wait_for_timeout(500)
        setups['updates'] = updates

        def mocks(name):
            page.unroute_all()
            if name in ('home', 'live'):
                page.route('**/runtime', lambda r: r.fulfill(json={'active': [{'id': 'job1', 'status': 'running', 'stage': 'Finding the best moments (3 of 8)'}]}))
                page.route('**/make/job1', lambda r: r.fulfill(json={'progress': 0.42, 'title': 'Example video'}))
            if name == 'updates':
                page.route('**/update/status', lambda r: r.fulfill(json={'checkout': False, 'available': True, 'current': 'a1b2c3d', 'latest': 'e4f5a6b', 'stage': '', 'running': False}))

        for name, (setup, sels) in SHOTS.items():
            if name.startswith('editor') and not DEMO_CLIP:
                continue
            mocks(name)
            try:
                page.set_viewport_size({'width': 1600, 'height': 1250 if name in TALL else 900})
                setups[setup]()
                boxes, used, sides = [], [], []
                for s, side in sels:
                    b = box(s)
                    if b:
                        boxes.append((b['x'], b['y'], b['width'], b['height']))
                        used.append(s)
                        sides.append(side)
                    else:
                        print('  missing marker', name, s)
                path = OUT / (name + '.jpg')
                page.screenshot(path=str(path))
                annotate(path, boxes, sides)
                keep[name] = used
                print('ok', name, len(boxes), 'markers')
            except Exception as e:
                print('FAILED', name, e)
        br.close()
    (OUT / 'shots.json').write_text(json.dumps(keep, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
