#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export $(grep -v '^\s*#' .env | xargs)
DATE=$(python3 - <<'PY'
from datetime import date, timedelta
d = date.today()
while d.weekday() > 4: d -= timedelta(days=1)
print(d.isoformat())
PY
)
echo "Using DATE=$DATE"
python -m sbwatch.cli.main levels build --date "$DATE"
python -m sbwatch.cli.main replay run   --date "$DATE" --no-wick-only
echo "---- trades (head) ----"
[ -f "out/trades_${DATE}.csv" ] && column -s, -t "out/trades_${DATE}.csv" | sed -n '1,20p' || echo "no trades file"
