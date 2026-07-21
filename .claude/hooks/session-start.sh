#!/usr/bin/env bash
set -euo pipefail

# Only run in Claude Code on the web; local macOS setups manage their own env.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

# System tools: zsh (required for every script + the test suite),
# ffmpeg (audio slicing/analysis), expect (download automation).
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends zsh ffmpeg expect

# Python venv with numpy (the only third-party import in Scripts/*.py).
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade --quiet pip
.venv/bin/pip install --quiet numpy

echo "session-start hook: zsh/ffmpeg/expect installed, .venv ready (numpy)."
