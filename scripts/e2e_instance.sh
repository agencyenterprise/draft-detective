#!/usr/bin/env bash
# Run a private backend + frontend from this checkout on free ports, for end-to-end checks
# while other servers (the user's :8000/:3000, other worktrees) run on the same machine.
# One instance per checkout: Next allows one `next dev` per build directory.
#
#   scripts/e2e_instance.sh up         start, wait until both answer, print the URLs
#   scripts/e2e_instance.sh restart    restart both servers on the same ports (after a code change)
#   scripts/e2e_instance.sh restart backend|frontend   restart only that server, same port
#   scripts/e2e_instance.sh status     show ports and PIDs, and whether each port listens
#   scripts/e2e_instance.sh down       stop only what `up` started in this checkout
#
# `up` reuses this checkout's last ports when they're still free, and draws new ones when not.
# PIDs, ports and logs go to .e2e/ in this checkout (git-ignored). Shell variables override
# .env and frontend/.env (NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG=false scripts/e2e_instance.sh up).
# E2E_RELOAD=1 starts the backend with auto-reload; `restart` keeps the mode `up` chose.
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

# pick_port NAME BASE: the port NAME used last time if it's still free, else a new free one,
# so the URLs survive a down + up.
pick_port() {
  local port
  port=$(saved "$1.port")
  if [[ "$port" =~ ^[0-9]+$ ]] && ! listening "$port"; then echo "$port"; else free_port "$2"; fi
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

# stop NAME: stop the server NAME started from this checkout, if any. Its port stays saved.
stop() {
  local pid
  pid=$(saved "$1.pid")
  [[ -n "$pid" ]] && stop_group "$pid" "$(saved "$1.start")"
  rm -f "$STATE/$1.pid" "$STATE/$1.start"
}

stop_each() {
  local name
  for name in "$@"; do stop "$name"; done
}

# True when a process in PID's group listens on PORT, so another server can't pass for ours.
owns_port() {
  local listener
  for listener in $(lsof -t -nP -iTCP:"$2" -sTCP:LISTEN 2>/dev/null); do
    [[ "$(ps -o pgid= -p "$listener" | tr -d ' ')" == "$1" ]] && return 0
  done
  return 1
}

# wait_for NAME URL TIMEOUT: poll URL until our own server answers it with 2xx/3xx.
wait_for() {
  local name=$1 url=$2 timeout=$3 log="$STATE/$1.log" start=$SECONDS code port pid
  pid=$(saved "$name.pid")
  port=${url##*:}
  port=${port%%/*}
  while ((SECONDS - start < timeout)); do
    alive "$pid" || { tail -n 40 "$log" >&2; die "$name exited while starting (log: $log)"; }
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$url" || true)
    if [[ "$code" =~ ^[23] ]]; then
      owns_port "$pid" "$port" && return 0
      die "another process answers on port $port; run $0 down, then $0 up for new ports"
    fi
    [[ "$name" == backend && "$code" == 503 ]] && echo "backend answers 503: is the database up? (docker compose up -d db)" >&2
    sleep 1
  done
  tail -n 40 "$log" >&2
  die "$name not ready after ${timeout}s at $url (log: $log)"
}

# record NAME PID PORT: what `down`, `status` and `restart` need to find the server again.
record() {
  echo "$2" >"$STATE/$1.pid"
  started "$2" >"$STATE/$1.start"
  echo "$3" >"$STATE/$1.port"
}

# start_backend PORT FRONTEND_PORT / start_frontend PORT BACKEND_PORT: launch one server as
# its own process group, logging to .e2e/NAME.log, without waiting for it.
start_backend() {
  local reload=""
  [[ "$(saved backend.reload)" == 1 ]] && reload="--reload"
  set -m
  (cd "$ROOT" && exec env PORT="$1" FRONTEND_URL="http://localhost:$2" \
    LOG_RICH_HANDLER="${LOG_RICH_HANDLER:-false}" \
    uv run uvicorn lib.api.main:app --host 127.0.0.1 --port "$1" $reload) \
    >"$STATE/backend.log" 2>&1 </dev/null &
  set +m
  record backend $! "$1"
}

start_frontend() {
  set -m
  (cd "$ROOT/frontend" && exec env NEXT_PUBLIC_API_URL="http://localhost:$2" API_INTERNAL_URL="http://localhost:$2" \
    node_modules/.bin/next dev --turbopack --port "$1") \
    >"$STATE/frontend.log" 2>&1 </dev/null &
  set +m
  record frontend $! "$1"
}

# launch NAME...: start each named server on its saved port and wait until each answers.
launch() {
  local name backend_port frontend_port
  backend_port=$(saved backend.port)
  frontend_port=$(saved frontend.port)
  for name in "$@"; do
    if [[ $name == backend ]]; then start_backend "$backend_port" "$frontend_port"; fi
    if [[ $name == frontend ]]; then start_frontend "$frontend_port" "$backend_port"; fi
  done
  for name in "$@"; do
    if [[ $name == backend ]]; then wait_for backend "http://localhost:$backend_port/api/health" "$BACKEND_TIMEOUT"; fi
    if [[ $name == frontend ]]; then wait_for frontend "http://localhost:$frontend_port/" "$FRONTEND_TIMEOUT"; fi
  done
}

print_urls() {
  echo "backend   http://localhost:$(saved backend.port)   (log: $STATE/backend.log)"
  echo "frontend  http://localhost:$(saved frontend.port)   (log: $STATE/frontend.log)"
  echo "restart with: $0 restart [backend|frontend]    stop with: $0 down"
}

cmd_up() {
  local backend_port frontend_port
  if alive "$(saved backend.pid)" || alive "$(saved frontend.pid)"; then
    die "an instance is already running from this checkout ($0 restart, $0 status, $0 down)"
  fi
  mkdir -p "$STATE"
  [[ -d "$ROOT/frontend/node_modules" ]] || (cd "$ROOT/frontend" && pnpm install --frozen-lockfile)
  echo "${E2E_RELOAD:-0}" >"$STATE/backend.reload"
  trap 'cmd_down >/dev/null' EXIT # a failed or interrupted `up` leaves nothing running
  trap 'exit 1' INT TERM HUP

  backend_port=$(pick_port backend 8100)
  frontend_port=$(pick_port frontend 3100)
  echo "$backend_port" >"$STATE/backend.port"
  echo "$frontend_port" >"$STATE/frontend.port"
  launch backend frontend
  trap - EXIT INT TERM HUP
  print_urls
}

# Stop and start again on the same ports, so the URLs stay valid. A server that isn't running
# is just started. A port another process took in the meantime is an error, never a new port:
# the frontend has the backend's URL baked in, and the user follows the old URLs.
cmd_restart() {
  local names name port
  case "${1:-all}" in
    all) names=(backend frontend) ;;
    backend | frontend) names=("$1") ;;
    *) die "restart takes backend, frontend or nothing (both)" ;;
  esac
  [[ "$(saved backend.port)" =~ ^[0-9]+$ && "$(saved frontend.port)" =~ ^[0-9]+$ ]] ||
    die "no saved ports in $STATE: start the instance with $0 up"
  [[ -n "${E2E_RELOAD:-}" ]] && echo "$E2E_RELOAD" >"$STATE/backend.reload"
  for name in "${names[@]}"; do stop "$name"; done
  # Both ports, not just the restarted ones: the other server's port must be free or still ours,
  # or a restarted frontend would talk to someone else's backend.
  for name in backend frontend; do
    port=$(saved "$name.port")
    listening "$port" || continue
    owns_port "$(saved "$name.pid")" "$port" && continue
    die "port $port ($name) is now taken by another process; run $0 down, then $0 up for new ports"
  done
  # A failed or interrupted restart stops what it started; a server it didn't touch keeps running.
  # The names are expanded now: Bash may drop this function's locals before the trap runs.
  # shellcheck disable=SC2064
  trap "stop_each ${names[*]}" EXIT
  trap 'exit 1' INT TERM HUP
  launch "${names[@]}"
  trap - EXIT INT TERM HUP
  print_urls
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
  stop frontend
  stop backend
  echo "stopped the instance started from $ROOT"
}

case "${1:-}" in
  up | down | status) "cmd_$1" ;;
  restart) cmd_restart "${2:-all}" ;;
  *) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
