#!/bin/sh
# docker-entrypoint.sh — run health check then dispatch to the requested script.
set -e

# Health gate: verify tools are present before running any command
python /app/skills/cliproof/scripts/health.py --json > /tmp/health.json 2>&1
if ! python -c "import sys,json; d=json.load(open('/tmp/health.json')); sys.exit(0 if d.get('ok') else 1)" 2>/dev/null; then
    echo "cliproof: health check failed at container start" >&2
    cat /tmp/health.json >&2
    exit 1
fi

# Dispatch: first arg is the script name, rest are args
SCRIPT="$1"
shift
exec python "/app/skills/cliproof/scripts/${SCRIPT}.py" "$@"
