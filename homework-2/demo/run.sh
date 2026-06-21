#!/usr/bin/env bash
# Start the customer support API on http://localhost:3000
# Creates a virtualenv and installs dependencies on first run.
set -euo pipefail

# Resolve repo root (this script lives in demo/)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

echo "Installing dependencies..."
./.venv/bin/pip install -q -r requirements.txt

echo "Starting API on http://localhost:3000 (Ctrl+C to stop)..."
exec ./.venv/bin/python -m src.app
