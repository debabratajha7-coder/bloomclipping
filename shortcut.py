"""Come back in one click (9B): a Desktop + Start Menu shortcut, and "Install as app" in the browser.

The Windows one-click installer already makes a Desktop shortcut; people who installed with git or an AI assistant had none. The
shortcut runs open.ps1 (Windows) / open.sh, which only opens the browser when BloomClipping is already running and starts it first
otherwise, so a second click never starts a second copy on another port.
The browser install uses /app.webmanifest (start_url '/', standalone window): Chrome and Edge show "Install BloomClipping".
"""
import os
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OPEN_PS1 = r'''# BloomClipping: open it if it is running, start it if not (used by the Desktop / Start Menu shortcut)
$port = if ($env:BLOOMCLIPPING_PORT) { $env:BLOOMCLIPPING_PORT } else { '8770' }
try { Invoke-WebRequest "http://127.0.0.1:$port/healthz" -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process "http://127.0.0.1:$port"; exit }
catch { & (Join-Path $PSScriptRoot 'run.ps1') }
'''
OPEN_SH = '''#!/bin/sh
# BloomClipping: open it if it is running, start it if not
cd "$(dirname "$0")"
PORT="${BLOOMCLIPPING_PORT:-8770}"
URL="http://127.0.0.1:$PORT"
if curl -fsS "$URL/healthz" >/dev/null 2>&1; then (open "$URL" 2>/dev/null || xdg-open "$URL"); else ./run.sh; fi
'''


def _write(path, text, mode=None):
    path.write_text(text, encoding='utf-8', newline='\n' if path.suffix != '.ps1' else '\r\n')
    if mode:
        os.chmod(path, mode)


def create():
    """Make the shortcuts for this computer. Returns {'made': [paths], 'note': text}."""
    system = platform.system()
    made = []
    if system == 'Windows':
        opener = ROOT / 'open.ps1'
        _write(opener, OPEN_PS1)
        icon = ROOT / 'bloomclipping.ico'
        places = [Path(os.environ.get('USERPROFILE', '~')) / 'Desktop',
                  Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs']
        for place in places:
            if not place.is_dir():
                continue
            link = place / 'BloomClipping.lnk'
            script = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{link}');$s.TargetPath='powershell.exe';"
                      "$s.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized -File \"{opener}\"';$s.WorkingDirectory='{root}';"
                      "$s.Description='BloomClipping: long video to captioned clips';{icon}$s.Save()").format(
                link=str(link).replace("'", "''"), opener=str(opener).replace("'", "''"), root=str(ROOT).replace("'", "''"),
                icon=("$s.IconLocation='" + str(icon).replace("'", "''") + "';") if icon.exists() else '')
            r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and link.exists():
                made.append(str(link))
        return {'made': made, 'note': 'Desktop and Start Menu shortcuts made.' if made else 'Windows did not allow the shortcut.'}
    opener = ROOT / 'open.sh'
    _write(opener, OPEN_SH, 0o755)
    desk = Path.home() / 'Desktop'
    if system == 'Darwin' and desk.is_dir():
        cmd = desk / 'BloomClipping.command'
        _write(cmd, f'#!/bin/sh\n"{opener}"\n', 0o755)
        made.append(str(cmd))
    elif desk.is_dir() or (Path.home() / '.local/share/applications').is_dir():
        entry = ('[Desktop Entry]\nType=Application\nName=BloomClipping\nComment=Long video to captioned clips\n'
                 f'Exec=sh "{opener}"\nTerminal=false\n')
        for place in (desk, Path.home() / '.local/share/applications'):
            if place.is_dir():
                f = place / 'bloomclipping.desktop'
                _write(f, entry, 0o755)
                made.append(str(f))
    return {'made': made, 'note': 'Shortcut made.' if made else 'No Desktop folder found.'}


def manifest():
    return {'name': 'BloomClipping', 'short_name': 'BloomClipping', 'start_url': '/', 'scope': '/', 'display': 'standalone',
            'background_color': '#0b0912', 'theme_color': '#ff3d6e', 'description': 'Long video to captioned 9:16 clips, on your own PC.',
            'icons': [{'src': '/phone-icon.svg', 'sizes': 'any', 'type': 'image/svg+xml', 'purpose': 'any'}]}


def attach(app):
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    @app.post('/shortcut')
    def make_shortcut():
        try:
            return create()
        except Exception as error:      # noqa: BLE001
            raise HTTPException(500, 'Could not make the shortcut: ' + str(error)[:120])

    @app.get('/app.webmanifest')
    def app_manifest():
        return JSONResponse(manifest(), media_type='application/manifest+json')
