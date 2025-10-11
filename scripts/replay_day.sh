# auto-load .env
if [ -f .env ]; then set -a; . ./.env; set +a; fi
#!/usr/bin/env bash
set -euo pipefail

cd /opt/sb-watchbot
source .venv/bin/activate

# --- args: --date YYYY-MM-DD OR positional YYYY-MM-DD, else default to today ET
DATE_ET=""
if [[ "${1:-}" == "--date" && -n "${2:-}" ]]; then
  DATE_ET="$2"; shift 2
elif [[ "${1:-}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  DATE_ET="$1"; shift 1
else
  DATE_ET="$(TZ=America/New_York date +%F)"
fi

OUT_DIR="./out"
mkdir -p "$OUT_DIR"

echo "Running replay for ${DATE_ET}..."

# Prefer legacy Oct-4 runner if present; otherwise use current CLI
if [[ -f "src/sbwatch/app/replay_day.py" ]]; then
  python src/sbwatch/app/replay_day.py --date "$DATE_ET"
elif python -c "import sbwatch.cli.main" >/dev/null 2>&1; then
  python -m sbwatch.cli.main replay run --date "$DATE_ET" --out "$OUT_DIR"
else
  echo "No replay entrypoint found." >&2
  exit 1
fi

CSV="${OUT_DIR}/replay_${DATE_ET}.csv"
if [[ -f "$CSV" ]]; then
  echo "Replay finished. Alerts (if any):"
  column -t -s, "$CSV" | sed -n '1,200p'
else
  echo "Replay finished but no CSV found at $CSV"
fi
