#!/usr/bin/env bash
# Run Commitizen bump from the repo root (updates pyproject version, tag, changelog per
# [tool.commitizen]). Pass through any cz bump flags, e.g.:
#   ./scripts/release_bump.sh --dry-run
#   ./scripts/release_bump.sh --increment PATCH
#   task release:bump -- --dry-run
set -euo pipefail
cd "$(dirname "$0")/.."
exec poetry run cz bump "$@"
