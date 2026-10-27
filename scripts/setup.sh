#!/usr/bin/env bash
set -euo pipefail

case "$(uname -s)" in
  Linux*) ;;
  *) echo "This script supports Linux. On Windows, run scripts/setup.ps1." >&2; exit 2 ;;
esac

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Install it with your distribution's package manager, then rerun." >&2
  exit 2
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo "Python 3.10 or newer is required." >&2
  exit 2
fi

"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
if [[ "${1:-}" == "--with-pluto" ]]; then
  .venv/bin/python -m pip install -r requirements-pluto.txt
fi
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m sae301 check --mode simulation

echo "Setup complete."
echo "Receiver:    .venv/bin/python -m sae301 receiver --mode simulation"
echo "Transmitter: .venv/bin/python -m sae301 transmitter --mode simulation"
echo "Use --with-pluto only after installing libiio for your distribution."

