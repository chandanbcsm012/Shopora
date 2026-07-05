#!/usr/bin/env bash
# Starts Postgres (if not already up) plus the backend and frontend dev
# servers, and streams both logs to this terminal. Ctrl+C stops both app
# processes (Postgres keeps running — use `docker compose down` to stop it
# too).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_LOG="$ROOT_DIR/.backend-dev.log"
FRONTEND_LOG="$ROOT_DIR/.frontend-dev.log"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

[ -d "$BACKEND_DIR/.venv" ] || die "Backend virtualenv not found. Run ./scripts/setup.sh first."
[ -d "$FRONTEND_DIR/node_modules" ] || die "Frontend dependencies not installed. Run ./scripts/setup.sh first."

log "Ensuring Postgres is running"
cd "$ROOT_DIR"
docker compose up -d db

BACKEND_PID=""
FRONTEND_PID=""
TAIL_PID=""
cleanup() {
  log "Shutting down..."
  [ -n "$TAIL_PID" ] && kill "$TAIL_PID" 2>/dev/null || true
  if [ -n "$FRONTEND_PID" ]; then
    pkill -P "$FRONTEND_PID" 2>/dev/null || true   # vite is a child of npm
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

log "Starting backend (FastAPI) on http://127.0.0.1:8000"
(
  cd "$BACKEND_DIR"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

log "Starting frontend (Vite) on http://localhost:5173"
(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --host
) > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

cat <<'EOF'

  Frontend:  http://localhost:5173
  Backend:   http://127.0.0.1:8000
  API docs:  http://127.0.0.1:8000/docs

  First time? Visit http://localhost:5173/admin/setup to create the admin account.

  Press Ctrl+C to stop. Logs below (also written to .backend-dev.log / .frontend-dev.log):

EOF

tail -f -n +1 "$BACKEND_LOG" "$FRONTEND_LOG" &
TAIL_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
