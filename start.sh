#!/bin/sh
# InfraPulse startup script (Linux / Unix).
# Starts all services with Docker Compose. Run from anywhere:
#   ./start.sh
set -eu

SCRIPT_DIR="$(dirname "$0")"
cd "$SCRIPT_DIR"

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed or not on PATH. See MANUAL.md (Prerequisites)."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is not available. See MANUAL.md (Prerequisites)."

echo "Starting InfraPulse (this may take a few minutes on first run)..."
docker compose up --build
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo "ERROR: InfraPulse failed to start (exit $STATUS). See MANUAL.md (Troubleshooting)." >&2
fi
exit $STATUS
