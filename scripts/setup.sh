#!/usr/bin/env bash
# One-time (but safe to re-run) project setup: backend venv + deps,
# Postgres via Docker, migrations, frontend deps.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 is required but not found on PATH."
command -v node >/dev/null 2>&1 || die "node is required but not found on PATH."
command -v npm >/dev/null 2>&1 || die "npm is required but not found on PATH."
command -v docker >/dev/null 2>&1 || die "docker is required but not found on PATH."
docker info >/dev/null 2>&1 || die "Docker is installed but not running. Start Docker Desktop and re-run."

log "Setting up backend (Python virtualenv + dependencies)"
cd "$BACKEND_DIR"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --disable-pip-version-check --upgrade pip
pip install -q --disable-pip-version-check -r requirements.txt

log "Starting Postgres (docker compose)"
cd "$ROOT_DIR"
docker compose up -d db

log "Waiting for Postgres to be healthy"
for _ in $(seq 1 30); do
  status="$(docker inspect --format='{{.State.Health.Status}}' learn2-db-1 2>/dev/null || echo "starting")"
  [ "$status" = "healthy" ] && break
  sleep 1
done
[ "$status" = "healthy" ] || die "Postgres did not become healthy in time. Check: docker compose logs db"

log "Running database migrations"
cd "$BACKEND_DIR"
source .venv/bin/activate
alembic upgrade head

log "Installing frontend dependencies"
cd "$FRONTEND_DIR"
npm install

log "Setup complete."
cat <<'EOF'

Next steps:
  ./scripts/run.sh          # start the backend + frontend dev servers
  open http://localhost:5173/admin/setup   # create the first admin account

Optional: seed the product catalog with sample data (from backend/, venv active):
  cd backend && source .venv/bin/activate && python -m scripts.seed_products
EOF
