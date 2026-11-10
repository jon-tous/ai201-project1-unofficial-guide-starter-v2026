#!/usr/bin/env bash
# Week 9 capstone — the one command that starts The Unofficial Guide as a service.
#
#   ./run.sh
#
# Builds the search index if this checkout doesn't have one yet (chroma_db/ is
# not committed), then serves POST /ask and GET /health with gunicorn.
# Every /ask request is logged to logs/requests.jsonl.
set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
if [ ! -x "$PY" ]; then
  echo "No .venv here. Do the one-time setup in RUNNING.md first." >&2
  exit 1
fi
if [ ! -f .env ]; then
  echo "No .env here. cp .env.example .env and paste your GEMINI_API_KEY in." >&2
  exit 1
fi

if ! "$PY" -c "import config, store, sys; sys.exit(0 if store.index_exists(config.CORPUS) else 1)" 2>/dev/null; then
  echo "No index for this corpus yet — building it (one time, ~30s)…"
  "$PY" app.py index
fi

PORT="${PORT:-5001}"   # not 5000: macOS's AirPlay Receiver already listens there
echo "Serving on http://127.0.0.1:${PORT}   (Ctrl-C to stop; log: logs/requests.jsonl)"
# --timeout 60: a request may legitimately spend up to REQUEST_DEADLINE_S (30s)
#   retrying the model; gunicorn's default 30s would kill the worker mid-retry.
# --threads 4: more than one request at a time on one process.
exec .venv/bin/gunicorn serve:app \
  --bind "0.0.0.0:${PORT}" --workers 1 --threads 4 --timeout 60 \
  --access-logfile -
