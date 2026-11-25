#!/usr/bin/env bash
# AuriomHQ AI Visibility Analyzer — local runner
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "→ No .env found, copying .env.example (edit it to add secrets)"
  cp .env.example .env
fi

if [ ! -d frontend/node_modules ]; then
  echo "→ Installing frontend dependencies"
  (cd frontend && npm install)
fi

if [ ! -f backend/static/index.html ]; then
  echo "→ Building the frontend into backend/static"
  (cd frontend && npm run build)
fi

if [ ! -f .venv/bin/python ]; then
  echo "→ Creating Python virtualenv"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

echo "→ Starting on http://localhost:${PORT:-8000}"
cd backend
exec ../.venv/bin/python -m uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
