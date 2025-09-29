#!/bin/bash
set -euo pipefail

# Get last 5 weekdays (Mon–Fri, skip weekends)
days=$(for i in {1..7}; do
  d=$(date -d "-$i day" +%Y-%m-%d)
  wd=$(date -d "$d" +%u)
  if [ "$wd" -le 5 ]; then
    echo "$d"
  fi
done | head -n 5)

echo "Testing market days:"
echo "$days"

for DATE in $days; do
  echo "================  $DATE  ================"
  python -m sbwatch.cli.main levels build --date "$DATE"
  python -m sbwatch.cli.main replay run --date "$DATE"

  if [ -f "out/trades_${DATE}.csv" ]; then
    entries=$(tail -n +2 "out/trades_${DATE}.csv" | wc -l)
    echo "Entries: $entries"
    awk -F, 'NR>1 {c[$NF]++} END{for(k in c) printf "%s=%d ", k, c[k]; print ""}' "out/trades_${DATE}.csv"
  else
    echo "No trades file: out/trades_${DATE}.csv"
  fi
done
