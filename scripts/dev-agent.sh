#!/usr/bin/env bash
# Run the FastAPI agent against the repo's pinned interpreter.
set -euo pipefail

cd "$(dirname "$0")/.."
AGENT_DIR=apps/agent

if [ ! -x "$AGENT_DIR/.venv/bin/python" ]; then
  echo "no venv at $AGENT_DIR/.venv — create one with a 3.11+ interpreter:" >&2
  echo "  python3.13 -m venv $AGENT_DIR/.venv" >&2
  echo "  $AGENT_DIR/.venv/bin/pip install -r $AGENT_DIR/requirements.txt" >&2
  exit 1
fi

if [ -f "$AGENT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$AGENT_DIR/.env"
  set +a
fi

cd "$AGENT_DIR"
exec ./.venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port "${AGENT_PORT:-8788}" --reload
