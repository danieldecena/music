#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root (works both as a registered hook and when run by hand).
cd "${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# System tools this toolkit needs:
#   zsh    - every script + the test suite (tests/test-core.sh) are zsh
#   ffmpeg - audio slicing/analysis (chop, chop_stems, analyze, slice_drums)
#   expect - drives gamdl's prompt on the Apple Music download path
missing=()
for tool in zsh ffmpeg expect; do
  command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
done

if [ "${#missing[@]}" -gt 0 ]; then
  case "$(uname -s)" in
    Darwin)
      # Local macOS session: install via Homebrew (most Macs already have zsh).
      if command -v brew >/dev/null 2>&1; then
        brew install "${missing[@]}"
      else
        echo "session-start hook: Homebrew not found; install manually: brew install ${missing[*]}" >&2
      fi
      ;;
    Linux)
      # Web/Linux session: install via apt (root in the web container, else sudo).
      export DEBIAN_FRONTEND=noninteractive
      sudo=""
      if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
        sudo="sudo -n"
      fi
      $sudo apt-get update -qq
      $sudo apt-get install -y --no-install-recommends "${missing[@]}"
      ;;
    *)
      echo "session-start hook: unsupported OS; install manually: ${missing[*]}" >&2
      ;;
  esac
fi

# Python venv with numpy (the only third-party import in Scripts/*.py).
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade --quiet pip
.venv/bin/pip install --quiet numpy

echo "session-start hook: toolchain ready (zsh/ffmpeg/expect + .venv with numpy)."
