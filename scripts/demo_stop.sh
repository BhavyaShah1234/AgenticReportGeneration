#!/usr/bin/env bash
# Stops the tunnel first (revokes public access immediately), then the app servers.
set -uo pipefail
PID_DIR="/tmp/agentic-reports-demo"

for name in tunnel frontend backend; do
  f="$PID_DIR/$name.pid"
  if [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null; then
    pid=$(cat "$f")
    # npm/uvicorn spawn children; stop the whole process group of each.
    pkill -TERM -P "$pid" 2>/dev/null
    kill "$pid" 2>/dev/null
    echo "stopped $name (PID $pid)"
  else
    echo "$name not running"
  fi
  rm -f "$f"
done
# next start runs as a grandchild of npm; make sure nothing is left on the ports.
for port in 3000 8000; do
  pids=$(ss -ltnpH "sport = :$port" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u)
  [ -n "$pids" ] && kill $pids 2>/dev/null && echo "freed port $port"
done
rm -f "$PID_DIR/url"
echo "Demo stopped; the public URL no longer works."
