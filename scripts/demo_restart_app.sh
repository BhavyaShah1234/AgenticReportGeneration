#!/usr/bin/env bash
# Redeploys code changes to a running demo WITHOUT touching the tunnel, so the public
# trycloudflare URL stays the same. Rebuilds the frontend, reseeds, restarts both servers.
#
#   ./scripts/demo_restart_app.sh            # rebuild + restart
#   ./scripts/demo_restart_app.sh --no-build # restart only
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/demo_lib.sh
source scripts/demo_lib.sh

demo_env
# Build before stopping, so the site is only down for the restart itself.
seed_and_build "${1:-}"
stop_servers
start_servers
URL=$(cat "$PID_DIR/url" 2>/dev/null || true)
echo "Redeployed. Public URL unchanged: ${URL:-<no tunnel running, use demo_start.sh>}"
