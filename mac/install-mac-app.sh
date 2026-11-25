#!/bin/bash
# Build / refresh BloomClipping.app with icon and install to ~/Applications (and /Applications if writable).
set -euo pipefail
MAC="$(cd "$(dirname "$0")" && pwd)"
APP_SRC="$(cd "$MAC/.." && pwd)"
DEST="$HOME/Applications/BloomClipping.app"
ICONSET="$MAC/icon.iconset"
PY="$APP_SRC/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

mkdir -p "$MAC/BloomClipping.app/Contents/MacOS" "$MAC/BloomClipping.app/Contents/Resources" "$ICONSET"

# Keep launcher + Info.plist next to this script (create if missing).
if [ ! -f "$MAC/BloomClipping.app/Contents/Info.plist" ]; then
  cat > "$MAC/BloomClipping.app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key><string>en</string>
  <key>CFBundleDisplayName</key><string>BloomClipping</string>
  <key>CFBundleExecutable</key><string>BloomClipping</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundleIdentifier</key><string>com.bloomclipping.desktop</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleName</key><string>BloomClipping</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
fi

cat > "$MAC/BloomClipping.app/Contents/MacOS/BloomClipping" <<'LAUNCH'
#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RESOURCES="$(cd "$HERE/../Resources" && pwd)"
if [ -f "$RESOURCES/app_home" ]; then
  APP_HOME="$(tr -d '[:space:]' < "$RESOURCES/app_home")"
else
  APP_HOME="$HOME/BloomClipping/app"
fi
PORT="${BLOOMCLIPPING_PORT:-8770}"
URL="http://127.0.0.1:${PORT}"
LABEL="gui/$(id -u)/com.bloomclipping.app"
LOG="$(dirname "$APP_HOME")/bloomclipping.log"
PYTHON="${APP_HOME}/.venv/bin/python"

ensure_server() {
  if curl -fsS "${URL}/healthz" >/dev/null 2>&1; then return 0; fi
  if launchctl print "$LABEL" >/dev/null 2>&1; then
    launchctl kickstart -k "$LABEL" >/dev/null 2>&1 || true
  elif [ -x "$PYTHON" ]; then
    mkdir -p "$(dirname "$LOG")"
    nohup "$PYTHON" -u "${APP_HOME}/app.py" >>"$LOG" 2>&1 &
  else
    osascript -e 'display alert "BloomClipping" message "Engine not found. Re-run mac/install-mac-app.sh from the BloomClipping folder."' >/dev/null 2>&1 || true
    exit 1
  fi
  for _ in $(seq 1 40); do
    if curl -fsS "${URL}/healthz" >/dev/null 2>&1; then return 0; fi
    sleep 0.25
  done
  osascript -e 'display notification "Could not start the local engine." with title "BloomClipping"' >/dev/null 2>&1 || true
  exit 1
}

open_window() {
  if [ -d "/Applications/Google Chrome.app" ]; then
    open -na "Google Chrome" --args --new-window --app="$URL" && return 0
  fi
  if [ -d "/Applications/Brave Browser.app" ]; then
    open -na "Brave Browser" --args --new-window --app="$URL" && return 0
  fi
  if [ -d "/Applications/Microsoft Edge.app" ]; then
    open -na "Microsoft Edge" --args --new-window --app="$URL" && return 0
  fi
  open "$URL"
}

ensure_server
open_window
LAUNCH
chmod +x "$MAC/BloomClipping.app/Contents/MacOS/BloomClipping"

"$PY" - <<PY
from PIL import Image, ImageDraw
from pathlib import Path
out = Path(r"$MAC")
iconset = out / "icon.iconset"
iconset.mkdir(parents=True, exist_ok=True)

def make(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (8, 8, 10, 255))
    d = ImageDraw.Draw(img)
    pad = max(1, int(size * 0.06))
    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=max(4, int(size * 0.22)), fill=(16, 16, 18, 255))
    cut = max(4, int(size * 0.22))
    d.polygon([(size - pad, pad), (size - pad, pad + cut), (size - pad - cut, pad)], fill=(200, 245, 58, 255))
    cx, cy = size * 0.5, size * 0.48
    s = size * 0.38
    acid = (200, 245, 58, 255)
    ink = (12, 12, 14, 255)
    def blade(sign):
        tip_x = cx + sign * s * 0.78
        tip_y = cy - s * 0.72
        base_x = cx + sign * s * 0.08
        base_y = cy + s * 0.08
        mid_x = cx + sign * s * 0.42
        mid_y = cy - s * 0.18
        half = s * 0.11
        d.polygon([
            (base_x, base_y - half * 0.2),
            (mid_x - sign * half * 0.3, mid_y - half),
            (tip_x, tip_y),
            (mid_x + sign * half * 0.5, mid_y + half * 0.6),
            (base_x + sign * half * 0.4, base_y + half * 0.5),
        ], fill=acid)
    blade(-1); blade(1)
    pr = max(2, int(s * 0.16))
    d.ellipse([cx - pr, cy - pr * 0.2, cx + pr, cy + pr * 1.4], fill=ink)
    d.ellipse([cx - pr * 0.55, cy + pr * 0.15, cx + pr * 0.55, cy + pr * 0.95], fill=acid)
    rr = max(3, int(s * 0.28))
    stroke = max(2, size // 28)
    for hx, hy in ((cx - s * 0.42, cy + s * 0.62), (cx + s * 0.42, cy + s * 0.62)):
        d.ellipse([hx - rr, hy - rr, hx + rr, hy + rr], outline=acid, width=stroke)
        ir = rr * 0.42
        d.ellipse([hx - ir, hy - ir, hx + ir, hy + ir], fill=(16, 16, 18, 255))
    spark = max(1, int(size * 0.018))
    d.ellipse([cx - spark, cy - s * 0.55 - spark, cx + spark, cy - s * 0.55 + spark], fill=acid)
    return img

make(1024).save(out / "bloomclipping-1024.png")
at = chr(64)
for base_px, retina in [(16, False), (16, True), (32, False), (32, True), (128, False), (128, True), (256, False), (256, True), (512, False), (512, True)]:
    px = base_px * (2 if retina else 1)
    name = f"icon_{base_px}x{base_px}" + (f"{at}2x.png" if retina else ".png")
    make(px).save(iconset / name)
print("icons ready")
PY

iconutil -c icns "$ICONSET" -o "$MAC/BloomClipping.app/Contents/Resources/AppIcon.icns"
printf '%s\n' "$APP_SRC" > "$MAC/BloomClipping.app/Contents/Resources/app_home"

mkdir -p "$HOME/Applications"
rm -rf "$DEST"
cp -R "$MAC/BloomClipping.app" "$DEST"
echo "Installed: $DEST"
if [ -w /Applications ]; then
  rm -rf /Applications/BloomClipping.app
  cp -R "$MAC/BloomClipping.app" /Applications/BloomClipping.app
  echo "Installed: /Applications/BloomClipping.app"
fi
open "$DEST"
