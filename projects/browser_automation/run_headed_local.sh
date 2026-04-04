#!/usr/bin/env bash
# Run the full MTG Glue sync on your machine with real browser windows (no Docker / Xvfb).
#
# Prerequisites:
#   - From repo root: poetry install && poetry run playwright install
#     (downloads Playwright’s own Chromium / headless shell into ~/Library/Caches/ms-playwright — not system Chrome)
#   - .env with the same variables as Docker (ECHOMTG_*, MOXFIELD_*, CAPSOLVER_API_KEY, S3_BUCKET, AWS_*, etc.)
#   - CapSolver extension: defaults to .data/capsolver-extension (downloaded automatically on first run).
#     To refresh or install without running the sync:
#       ./projects/browser_automation/fetch_capsolver_extension.sh
#
# Optional:
#   ECHO_MTG_HEADED=1   also show a window for the EchoMTG export step (default is headless for that part).
#
# Usage (from anywhere):
#   ./projects/browser_automation/run_headed_local.sh
#   ./projects/browser_automation/run_headed_local.sh --   # extra args forwarded to Python if added later
#
# If you see "ValueError: bad marshal data (unknown type code)" on import, stale .pyc
# files do not match your current Python. From repo root run:
#   rm -rf projects/*/__pycache__
# Or recreate the env: poetry env remove --all && poetry install

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export PYTHONUNBUFFERED=1
mkdir -p .data .out

CAPSOLVER_DEST="$ROOT/.data/capsolver-extension"
export CAPSOLVER_EXTENSION_PATH="${CAPSOLVER_EXTENSION_PATH:-$CAPSOLVER_DEST}"
if [[ ! -f "$CAPSOLVER_EXTENSION_PATH/assets/config.js" ]]; then
  echo "CapSolver extension not found at $CAPSOLVER_EXTENSION_PATH — fetching..." >&2
  "$SCRIPT_DIR/fetch_capsolver_extension.sh" "$CAPSOLVER_EXTENSION_PATH"
fi

if ! command -v poetry >/dev/null 2>&1; then
  echo "error: poetry not on PATH" >&2
  exit 1
fi

exec poetry run python -u -m browser_automation.echo_moxfield_etl "$@"
