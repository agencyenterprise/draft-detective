#!/usr/bin/env bash
# Run a private backend + frontend from this checkout on free ports, for end-to-end checks
# while other servers (the user's :8000/:3000, other worktrees) run on the same machine.
# One instance per checkout: Next allows one `next dev` per build directory.
#
#   scripts/e2e_instance.sh up       start, wait until both answer, print the URLs
#   scripts/e2e_instance.sh status   show ports and PIDs, and whether each port listens
#   scripts/e2e_instance.sh down     stop only what `up` started in this checkout
#
# PIDs, ports and logs go to .e2e/ in this checkout (git-ignored). Shell variables override
# .env and frontend/.env (NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG=false scripts/e2e_instance.sh up).
# E2E_RELOAD=1 starts the backend with auto-reload.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.e2e"
BACKEND_TIMEOUT="${E2E_BACKEND_TIMEOUT:-300}"   # the first `uv run` in a fresh worktree builds .venv
FRONTEND_TIMEOUT="${E2E_FRONTEND_TIMEOUT:-180}" # the first page compile takes ~10 s

die() { echo "e2e_instance: $*" >&2; exit 1; }
listening() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
alive() { [[ -n "${1:-}" ]] && kill -0 "$1" 2>/dev/null; }
saved() { cat "$STATE/$1" 2>/dev/null || true; }
started() { LC_ALL=C TZ=UTC ps -o lstart= -p "$1" 2>/dev/null || true; }
command -v lsof >/dev/null || die "lsof is required to find free ports"

# A random free port in [base, base+899], so concurrent `up`s rarely race for the same one.
free_port() {
  local base=$1 port tries=0
  while ((tries < 200)); do
    port=$((base + RANDOM % 900))
    if ! listening "$port"; then echo "$port"; return; fi
    tries=$((tries + 1))
  done
  die "no free port near $base"
}

# Each server runs as its own process group (job control is on when it starts), so stopping
# the group also stops what it spawned: uv's python, uvicorn's reloader, next-server.
# A live PID whose start time differs from the saved one was reused by an unrelated process.
stop_group() {
  local pid=$1 start=$2 i
  if alive "$pid" && [[ "$(started "$pid")" != "$start" ]]; then return 0; fi
  alive "$pid" || pgrep -g "$pid" >/dev/null 2>&1 || return 0
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  for ((i = 0; i < 50; i++)); do
    alive "$pid" || pgrep -g "$pid" >/dev/null 2>&1 || return 0
    sleep 0.2
  done
  kill -KILL -- "-$pid" 2>/dev/null || true
}

# True when a process in PID's group listens on PORT, so another server can't pass for ours.
owns_port() {
  local listener
  for listener in $(lsof -t -nP -iTCP:"$2" -sTCP:LISTEN 2>/dev/null); do
    [[ "$(ps -o pgid= -p "$listener" | tr -d ' ')" == "$1" ]] && return 0
  done
  return 1
}

# wait_for NAME URL PID TIMEOUT: poll URL until our own server answers it with 2xx/3xx.
wait_for() {
  local name=$1 url=$2 pid=$3 timeout=$4 log="$STATE/$1.log" start=$SECONDS code port
  port=${url##*:}
  port=${port%%/*}
  while ((SECONDS - start < timeout)); do
    alive "$pid" || { tail -n 40 "$log" >&2; die "$name exited while starting (log: $log)"; }
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$url" || true)
    if [[ "$code" =~ ^[23] ]]; then
      owns_port "$pid" "$port" && return 0
      die "another process answers on port $port; run up again"
    fi
    [[ "$name" == backend && "$code" == 503 ]] && echo "backend answers 503: is the database up? (docker compose up -d db)" >&2
    sleep 1
  done
  tail -n 40 "$log" >&2
  die "$name not ready after ${timeout}s at $url (log: $log)"
}

cmd_up() {
  local backend_port frontend_port backend_pid frontend_pid reload=""
  if alive "$(saved backend.pid)" || alive "$(saved frontend.pid)"; then
    die "an instance is already running from this checkout ($0 status, $0 down)"
  fi
  mkdir -p "$STATE"
  [[ -d "$ROOT/frontend/node_modules" ]] || (cd "$ROOT/frontend" && pnpm install --frozen-lockfile)
  [[ "${E2E_RELOAD:-0}" == 1 ]] && reload="--reload"
  trap 'cmd_down >/dev/null' EXIT # a failed or interrupted `up` leaves nothing running
  trap 'exit 1' INT TERM HUP

  backend_port=$(free_port 8100)
  frontend_port=$(free_port 3100)
  set -m
  (cd "$ROOT" && exec env PORT="$backend_port" FRONTEND_URL="http://localhost:$frontend_port" \
    LOG_RICH_HANDLER="${LOG_RICH_HANDLER:-false}" \
    uv run uvicorn lib.api.main:app --host 127.0.0.1 --port "$backend_port" $reload) \
    >"$STATE/backend.log" 2>&1 </dev/null &
  backend_pid=$!
  (cd "$ROOT/frontend" && exec env NEXT_PUBLIC_API_URL="http://localhost:$backend_port" API_INTERNAL_URL="http://localhost:$backend_port" \
    node_modules/.bin/next dev --turbopack --port "$frontend_port") \
    >"$STATE/frontend.log" 2>&1 </dev/null &
  frontend_pid=$!
  set +m
  echo "$backend_pid" >"$STATE/backend.pid"
  echo "$frontend_pid" >"$STATE/frontend.pid"
  started "$backend_pid" >"$STATE/backend.start"
  started "$frontend_pid" >"$STATE/frontend.start"
  echo "$backend_port" >"$STATE/backend.port"
  echo "$frontend_port" >"$STATE/frontend.port"

  wait_for backend "http://localhost:$backend_port/api/health" "$backend_pid" "$BACKEND_TIMEOUT"
  wait_for frontend "http://localhost:$frontend_port/" "$frontend_pid" "$FRONTEND_TIMEOUT"
  trap - EXIT INT TERM HUP
  echo "backend   http://localhost:$backend_port   (log: $STATE/backend.log)"
  echo "frontend  http://localhost:$frontend_port   (log: $STATE/frontend.log)"
  echo "stop with: $0 down"
}

cmd_status() {
  local name pid port state
  for name in backend frontend; do
    pid=$(saved "$name.pid")
    port=$(saved "$name.port")
    if alive "$pid"; then state="running"; else state="stopped"; fi
    [[ -n "$port" ]] && listening "$port" && state="$state, http://localhost:$port listening"
    echo "$name: pid ${pid:-none}, $state"
  done
}

cmd_down() {
  local name pid
  for name in frontend backend; do
    pid=$(saved "$name.pid")
    [[ -n "$pid" ]] && stop_group "$pid" "$(saved "$name.start")"
    rm -f "$STATE/$name.pid" "$STATE/$name.start"
  done
  echo "stopped the instance started from $ROOT"
}

case "${1:-}" in
  up | down | status) "cmd_$1" ;;
  *) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
