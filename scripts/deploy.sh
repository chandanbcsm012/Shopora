#!/usr/bin/env bash
# Triggers a redeploy of the backend and/or frontend on Render via Deploy
# Hooks, without needing git push access from this machine. Render always
# deploys the latest commit already on the connected branch — this script
# just asks Render to build+deploy it now.
#
# One-time setup (per service, in the Render dashboard):
#   Service > Settings > Deploy Hook > copy the URL, then:
#     export RENDER_BACKEND_DEPLOY_HOOK=<url>
#     export RENDER_FRONTEND_DEPLOY_HOOK=<url>
#   (or put them in a .env.deploy file next to this script's repo root)
#
# Usage:
#   ./scripts/deploy.sh              # deploy backend + frontend
#   ./scripts/deploy.sh backend      # deploy backend only
#   ./scripts/deploy.sh frontend     # deploy frontend only
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

if [ -f "$ROOT_DIR/.env.deploy" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env.deploy"
fi

command -v curl >/dev/null 2>&1 || die "curl is required but not found on PATH."

case "$TARGET" in
  all|backend|frontend) ;;
  *) die "Unknown target '$TARGET'. Use: all | backend | frontend" ;;
esac

trigger() {
  local name="$1" hook="$2"
  [ -n "$hook" ] || die "$name deploy hook is not set. See the comment at the top of this script."

  log "Triggering $name deploy"
  status="$(curl -s -o /tmp/render-deploy-response.json -w '%{http_code}' -X POST "$hook")"
  [ "$status" = "200" ] || [ "$status" = "201" ] || die "$name deploy hook returned HTTP $status: $(cat /tmp/render-deploy-response.json)"
  echo "  $name deploy queued."
}

if [ "$TARGET" = "all" ] || [ "$TARGET" = "backend" ]; then
  trigger "Backend" "${RENDER_BACKEND_DEPLOY_HOOK:-}"
fi

if [ "$TARGET" = "all" ] || [ "$TARGET" = "frontend" ]; then
  trigger "Frontend" "${RENDER_FRONTEND_DEPLOY_HOOK:-}"
fi

log "Done. Watch progress in the Render dashboard (Service > Events)."
