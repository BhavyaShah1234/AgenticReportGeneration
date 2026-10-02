#!/usr/bin/env bash
# Shows whether the demo is live and prints the public URL. Read-only.
set -uo pipefail
PID_DIR="/tmp/agentic-reports-demo"

running() { [ -f "$PID_DIR/$1.pid" ] && kill -0 "$(cat "$PID_DIR/$1.pid")" 2>/dev/null; }

echo "=== Processes ==="
for name in backend frontend tunnel; do
  if running "$name"; then
    pid=$(cat "$PID_DIR/$name.pid")
    printf "  %-9s running (PID %s, up %s)\n" "$name" "$pid" "$(ps -p "$pid" -o etime= | tr -d ' ')"
  else
    printf "  %-9s NOT RUNNING\n" "$name"
  fi
done

echo
echo "=== Local ==="
curl -s -o /dev/null -m 5 http://127.0.0.1:8000/api/health && echo "  backend  OK  (127.0.0.1:8000)" || echo "  backend  DOWN, see $PID_DIR/backend.log"
curl -s -o /dev/null -m 5 http://127.0.0.1:3000/login && echo "  frontend OK  (127.0.0.1:3000)" || echo "  frontend DOWN, see $PID_DIR/frontend.log"
curl -s -o /dev/null -m 3 http://127.0.0.1:11434/api/tags && echo "  ollama   OK" || echo "  ollama   DOWN (AI features fall back)"

URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$PID_DIR/tunnel.log" 2>/dev/null | tail -1 || true)
echo
echo "=== Public URL ==="
if [ -z "$URL" ]; then
  echo "  none, run scripts/demo_start.sh"
else
  echo "  $URL"
  code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$URL/api/health" || echo "000")
  case "$code" in
    200) echo "  reachable (API health 200)" ;;
    000) echo "  NOT reachable from here yet (a fresh hostname's DNS can lag a minute)" ;;
    *)   echo "  unexpected status $code" ;;
  esac
fi

echo
echo "=== Things that would kill the tunnel (and change the URL) ==="
lid=$(grep -i "^HandleLidSwitch" /etc/systemd/logind.conf 2>/dev/null | head -1)
[ -z "$lid" ] && echo "  WARNING: closing the lid suspends this laptop. Keep it open during judging." \
             || echo "  lid close: ${lid#*=}"
for src in ac battery; do
  val=$(gsettings get org.gnome.settings-daemon.plugins.power "sleep-inactive-${src}-type" 2>/dev/null || echo unknown)
  [ "$val" = "'nothing'" ] && echo "  idle-suspend on $src: disabled" \
                           || echo "  WARNING: idle-suspend on $src is $val, so the laptop may sleep mid-judging."
done
