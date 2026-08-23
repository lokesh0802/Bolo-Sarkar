#!/usr/bin/env bash
# Set up the venv (first run) and start the dev server.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi

.venv/bin/python -m bolo.main
