#!/usr/bin/env bash
set -euo pipefail
# Virtual framebuffer for Chromium + extensions (headless cannot load extensions).
echo "etl: starting xvfb + python (PYTHONUNBUFFERED=${PYTHONUNBUFFERED:-})" >&2
# exec xvfb-run -a -s "-screen 0 1920x1080x24" python -u -m etl.echo_moxfield_etl "$@"
xvfb-run -a -s "-screen 0 1920x1080x24" python -u -m etl.echo_moxfield_etl
