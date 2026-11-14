#!/bin/sh
# InfraPulse startup script (macOS). Double-click in Finder or run:
#   ./start.command
set -eu

SCRIPT_DIR="$(dirname "$0")"
cd "$SCRIPT_DIR"

fail() {
  echo "ERROR: $1" >&2
  echo "Press Enter to close."
  read -r _dummy
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed or not on PATH. Install Docker Desktop, then see MANUAL.md."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is not available. Update Docker Desktop, then see MANUAL.md."

echo "Starting InfraPulse (this may take a few minutes on first run)..."
echo "App: http://localhost:8092   API: http://localhost:8003/api/docs"
docker compose up --build
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo "ERROR: InfraPulse failed to start (exit $STATUS). See MANUAL.md (Troubleshooting)." >&2
fi
echo "Press Enter to close."
read -r _dummy
exit $STATUS
