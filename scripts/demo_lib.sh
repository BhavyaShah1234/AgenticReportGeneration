# Shared by demo_start.sh and demo_restart_app.sh. Source it from the repo root.
# shellcheck shell=bash

PID_DIR="/tmp/agentic-reports-demo"
NODE_BIN="$HOME/.nvm/versions/node/v26.10.0/bin"
export PATH="$NODE_BIN:$PATH"
unset PYTHONPATH  # the global ROS PYTHONPATH leaks into the venv otherwise
mkdir -p "$PID_DIR" backend/storage

demo_env() {
  # Snowflake creds live as `export SNOWFLAKE_*=` lines in ~/.bashrc (which returns early for
  # non-interactive shells), so load just those lines. Values are never printed.
  eval "$(grep -E '^[[:space:]]*export[[:space:]]+SNOWFLAKE_[A-Z_]+=' "$HOME/.bashrc" || true)"
  : "${SNOWFLAKE_ACCOUNT:?SNOWFLAKE_ACCOUNT not set}" "${SNOWFLAKE_USER:?}" "${SNOWFLAKE_API:?}"

  export DEMO_MODE=1
  export FRONTEND_URL="http://127.0.0.1:3000"
  # AI runs on Snowflake Cortex open-weight models when the account allows it, falling back
  # to the local open-weight model in Ollama otherwise (e.g. Cortex is disabled on trials).
  export LLM_PROVIDER="${LLM_PROVIDER:-cortex}"
  export CORTEX_MODEL="${CORTEX_MODEL:-llama3.1-70b}"
  # Left unset on purpose: the backend then uses the persistent backend/storage/.app_secret,
  # shared by the seed and the server across restarts.
  unset APP_SECRET_KEY

  if [ -n "${SNOWFLAKE_DEMO_API:-}" ]; then
    echo "Snowflake: public demo will query as read-only role ${SNOWFLAKE_DEMO_ROLE:-DEMO_READER}"
  else
    echo "WARNING: SNOWFLAKE_DEMO_API is not set, so the public demo will use your main PAT"
    echo "         (role $SNOWFLAKE_ROLE). See README 'Hosting the demo' to add a read-only token."
  fi
  echo "LLM: provider=$LLM_PROVIDER (Cortex model $CORTEX_MODEL, fallback Ollama)"
  if ! curl -s -m 3 -o /dev/null http://127.0.0.1:11434/api/tags; then
    echo "WARNING: Ollama is not responding on :11434, so AI features can't fall back."
  fi
}

seed_and_build() {  # $1 = --no-build to skip the frontend build
  echo "Seeding demo company + reports..."
  (cd backend && .venv/bin/python -m app.seed | sed 's/^/  /')
  if [ "${1:-}" != "--no-build" ]; then
    echo "Building frontend (production)..."
    NEXT_PUBLIC_DEMO_MODE=1 npm --prefix frontend run build > "$PID_DIR/build.log" 2>&1 \
      || { echo "ERROR: frontend build failed, see $PID_DIR/build.log" >&2; return 1; }
  fi
}

start_servers() {
  # setsid + </dev/null fully detach the servers (own session, no inherited stdin/stdout), so
  # they survive the terminal or tool that launched them closing or being killed.
  (cd backend && setsid nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    < /dev/null > "$PID_DIR/backend.log" 2>&1 & echo $! > "$PID_DIR/backend.pid")
  (setsid nohup npm --prefix frontend run start -- -H 127.0.0.1 -p 3000 \
    < /dev/null > "$PID_DIR/frontend.log" 2>&1 & echo $! > "$PID_DIR/frontend.pid")
  wait_for http://127.0.0.1:8000/api/health backend || return 1
  wait_for http://127.0.0.1:3000/login frontend || return 1
  # setsid may fork, so $! can be a short-lived wrapper; record the PIDs that actually listen.
  listener_pid 8000 > "$PID_DIR/backend.pid"
  listener_pid 3000 > "$PID_DIR/frontend.pid"
  echo "Backend and frontend are up."
}

listener_pid() {  # port -> PID of the process listening on it
  ss -ltnpH "sport = :$1" 2>/dev/null | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2 || true
}

stop_servers() {
  # Best-effort cleanup: callers run under `set -euo pipefail`, so every step that may
  # legitimately find nothing to stop is guarded with `|| true`.
  for name in frontend backend; do
    f="$PID_DIR/$name.pid"
    if [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null; then
      pkill -TERM -P "$(cat "$f")" 2>/dev/null || true
      kill "$(cat "$f")" 2>/dev/null || true
      echo "stopped $name"
    fi
    rm -f "$f"
  done
  # next start runs as a grandchild of npm; make sure nothing is left on the ports.
  for port in 3000 8000; do
    pids=$(ss -ltnpH "sport = :$port" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)
    if [ -n "$pids" ]; then kill $pids 2>/dev/null || true; echo "freed port $port"; fi
  done
  for _ in $(seq 1 10); do
    ss -ltnH "sport = :3000 or sport = :8000" 2>/dev/null | grep -q . || return 0
    sleep 1
  done
  echo "WARNING: ports 3000/8000 still busy after 10s" >&2
  return 0
}

wait_for() {  # url, name
  for _ in $(seq 1 40); do curl -s -o /dev/null -m 2 "$1" && return 0; sleep 1; done
  echo "ERROR: $2 did not come up, see $PID_DIR/$2.log" >&2
  return 1
}
