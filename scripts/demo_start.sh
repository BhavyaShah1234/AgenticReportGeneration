#!/usr/bin/env bash
# Hosts Agentic Reports from this machine for the hackathon demo:
#   FastAPI (127.0.0.1:8000) + Next.js production server (127.0.0.1:3000)
#   + a Cloudflare Quick Tunnel to :3000 (Next proxies /api to FastAPI).
# Nothing listens on a public interface. Run demo_stop.sh to revoke access.
#
#   ./scripts/demo_start.sh            # build frontend, seed, start, open tunnel
#   ./scripts/demo_start.sh --no-build # reuse the last production build
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

PID_DIR="/tmp/agentic-reports-demo"
NODE_BIN="$HOME/.nvm/versions/node/v26.10.0/bin"
export PATH="$NODE_BIN:$PATH"
unset PYTHONPATH  # the global ROS PYTHONPATH leaks into the venv otherwise
mkdir -p "$PID_DIR" backend/storage

for bin in cloudflared "$NODE_BIN/node" backend/.venv/bin/uvicorn; do
  command -v "$bin" >/dev/null 2>&1 || { echo "ERROR: missing $bin (see README setup)" >&2; exit 1; }
done
if [ -f "$PID_DIR/tunnel.pid" ] && kill -0 "$(cat "$PID_DIR/tunnel.pid")" 2>/dev/null; then
  echo "A demo session is already running. Use scripts/demo_status.sh, or demo_stop.sh to restart." >&2
  exit 1
fi

# Snowflake creds live as `export SNOWFLAKE_*=` lines in ~/.bashrc (which returns early for
# non-interactive shells), so load just those lines. Values are never printed.
eval "$(grep -E '^[[:space:]]*export[[:space:]]+SNOWFLAKE_[A-Z_]+=' "$HOME/.bashrc" || true)"
: "${SNOWFLAKE_ACCOUNT:?SNOWFLAKE_ACCOUNT not set}" "${SNOWFLAKE_USER:?}" "${SNOWFLAKE_API:?}"

export DEMO_MODE=1
export FRONTEND_URL="http://127.0.0.1:3000"
# APP_SECRET_KEY is left unset on purpose: the backend then uses the persistent
# backend/storage/.app_secret, shared by the seed and the server across restarts.
unset APP_SECRET_KEY

if [ -n "${SNOWFLAKE_DEMO_API:-}" ]; then
  echo "Snowflake: public demo will query as read-only role ${SNOWFLAKE_DEMO_ROLE:-DEMO_READER}"
else
  echo "WARNING: SNOWFLAKE_DEMO_API is not set, so the public demo will use your main PAT"
  echo "         (role $SNOWFLAKE_ROLE). See README 'Hosting the demo' to add a read-only token."
fi

if ! curl -s -m 3 -o /dev/null http://127.0.0.1:11434/api/tags; then
  echo "WARNING: Ollama is not responding on :11434, so 'Ask the agent' and AI narratives will fall back."
fi

echo "Seeding demo company + reports..."
(cd backend && .venv/bin/python -m app.seed | sed 's/^/  /')

if [ "${1:-}" != "--no-build" ]; then
  echo "Building frontend (production)..."
  NEXT_PUBLIC_DEMO_MODE=1 npm --prefix frontend run build > "$PID_DIR/build.log" 2>&1 \
    || { echo "ERROR: frontend build failed, see $PID_DIR/build.log" >&2; exit 1; }
fi

(cd backend && nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$PID_DIR/backend.log" 2>&1 & echo $! > "$PID_DIR/backend.pid")
(nohup npm --prefix frontend run start -- -H 127.0.0.1 -p 3000 > "$PID_DIR/frontend.log" 2>&1 & echo $! > "$PID_DIR/frontend.pid")

wait_for() {  # url, name
  for _ in $(seq 1 40); do curl -s -o /dev/null -m 2 "$1" && return 0; sleep 1; done
  echo "ERROR: $2 did not come up, see $PID_DIR/$2.log" >&2
  "$ROOT/scripts/demo_stop.sh" >/dev/null 2>&1 || true
  exit 1
}
wait_for http://127.0.0.1:8000/api/health backend
wait_for http://127.0.0.1:3000/login frontend
echo "Backend and frontend are up."

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
