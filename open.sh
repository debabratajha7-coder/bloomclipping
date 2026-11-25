#!/bin/sh
cd "$(dirname "$0")"
PORT="${BLOOMCLIPPING_PORT:-${BLOOMCLIPPING_PORT:-8770}}"
URL="http://127.0.0.1:$PORT"
if curl -fsS "$URL/healthz" >/dev/null 2>&1; then open "$URL" 2>/dev/null; else ../start.sh; fi
