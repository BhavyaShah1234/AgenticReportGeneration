#!/usr/bin/env bash
# Hosts Agentic Reports from this machine for the hackathon demo:
#   FastAPI (127.0.0.1:8000) + Next.js production server (127.0.0.1:3000)
#   + a Cloudflare Quick Tunnel to :3000 (Next proxies /api to FastAPI).
# Nothing listens on a public interface. Run demo_stop.sh to revoke access.
#
#   ./scripts/demo_start.sh            # build frontend, seed, start, open tunnel
#   ./scripts/demo_start.sh --no-build # reuse the last production build
# To ship code changes without changing the public URL, use demo_restart_app.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/demo_lib.sh
source scripts/demo_lib.sh

for bin in cloudflared "$NODE_BIN/node" backend/.venv/bin/uvicorn; do
  command -v "$bin" >/dev/null 2>&1 || { echo "ERROR: missing $bin (see README setup)" >&2; exit 1; }
done
if [ -f "$PID_DIR/tunnel.pid" ] && kill -0 "$(cat "$PID_DIR/tunnel.pid")" 2>/dev/null; then
  echo "A demo session is already running. Use demo_status.sh, demo_restart_app.sh, or demo_stop.sh." >&2
  exit 1
fi

demo_env
seed_and_build "${1:-}"
start_servers || { scripts/demo_stop.sh >/dev/null 2>&1; exit 1; }

nohup cloudflared tunnel --no-autoupdate --url http://127.0.0.1:3000 > "$PID_DIR/tunnel.log" 2>&1 &
echo $! > "$PID_DIR/tunnel.pid"

echo "Waiting for the public URL..."
for _ in $(seq 1 30); do
  URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$PID_DIR/tunnel.log" 2>/dev/null | head -1 || true)
  if [ -n "$URL" ]; then
    echo "$URL" > "$PID_DIR/url"
    echo ""
    echo "=============================================================="
    echo " Agentic Reports is live:  $URL"
    echo " Demo logins: designer@classicmodels.com / viewer@classicmodels.com"
    echo "              password demo1234 (or sign up with any email)"
    echo "=============================================================="
    echo " Status: scripts/demo_status.sh    Stop: scripts/demo_stop.sh"
    echo " The URL changes if cloudflared restarts, so keep this machine awake."
    exit 0
  fi
  sleep 1
done
echo "Tunnel didn't report a URL yet, check $PID_DIR/tunnel.log" >&2
exit 1
