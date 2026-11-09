#!/usr/bin/env bash
# Run the project's Python on any OS: ./py tools/<tool>.py ...
here="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$here/.venv/bin/python" ]; then exec "$here/.venv/bin/python" "$@"; fi
if [ -x "$here/.venv/Scripts/python.exe" ]; then exec "$here/.venv/Scripts/python.exe" "$@"; fi
echo "error: no .venv found in $here. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
exit 1
