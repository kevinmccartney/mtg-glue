#!/usr/bin/env bash
# Download and unpack the CapSolver Chrome extension into .data (gitignored).
# Keep CAPSOLVER_* in sync with projects/browser_automation/Dockerfile.

set -euo pipefail

VERSION=v.1.17.0
ZIP=CapSolver.Browser.Extension-chrome-v1.17.0.zip
URL="https://github.com/capsolver/capsolver-browser-extension/releases/download/${VERSION}/${ZIP}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="${1:-$ROOT/.data/capsolver-extension}"

for cmd in curl unzip; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: need $cmd on PATH" >&2
    exit 1
  fi
done

mkdir -p "$DEST"
tmp="$(mktemp "${TMPDIR:-/tmp}/capsolver.XXXXXX.zip")"
trap 'rm -f "$tmp"' EXIT

echo "Downloading ${ZIP}..." >&2
curl -fsSL "$URL" -o "$tmp"
echo "Unpacking to ${DEST}..." >&2
unzip -q -o "$tmp" -d "$DEST"

if [[ ! -f "$DEST/assets/config.js" ]]; then
  echo "error: expected ${DEST}/assets/config.js after unzip" >&2
  exit 1
fi

echo "CapSolver extension ready at ${DEST}" >&2
