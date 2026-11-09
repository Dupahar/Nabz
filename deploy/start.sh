#!/bin/sh
# Seed the synthetic demo visits on first start, then run the app.
set -e
if [ ! -d "$NABZ_DATA_DIR/calls" ] && [ -d /app/deploy/seed/calls ]; then
  mkdir -p "$NABZ_DATA_DIR"
  cp -r /app/deploy/seed/calls "$NABZ_DATA_DIR/calls"
  python -c "import sys; sys.path.insert(0, '/app/tools'); from common import audit; audit('demo.seeded', actor='deploy', visits=len(__import__('os').listdir('$NABZ_DATA_DIR/calls')))"
fi
exec python -m uvicorn app.server:app --host 0.0.0.0 --port "${PORT:-8080}" --proxy-headers --forwarded-allow-ips="*"
