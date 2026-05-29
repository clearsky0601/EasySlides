#!/usr/bin/env bash
# Launch the EasySlides TUI previewer (browse slides, Enter opens /public,
# switch databases). Manages its own daphne server on port 10001.
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m slide_tui "$@"
