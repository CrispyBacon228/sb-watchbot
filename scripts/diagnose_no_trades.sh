#!/usr/bin/env bash
set -euo pipefail

# Days to check (weekdays)
DATES=("2025-09-25" "2025-09-24" "2025-09-23")

summarize() {
  local tag="$1"
  local d="$2"
  local trades="out/trades_${d}${tag}.csv"
  local entries="out/replay_entries_${d}${tag}.csv"

  echo "---- ${d}${tag} summary ----"
  local ecount=0 tcount=0
  local oline="(no trades file)"

  if [[ -f "$entries" ]]; then
    ecount="$(tail -n +2 "$entries" | wc -l || true)"
  fi

  if [[ -f "$trades" ]]; then
    tcount="$(tail -n +2 "$trades" | wc -l || true)"
    # Outcome histogram by last column
    oline="$(awk -F, 'NR>1{c[$NF]++} END{for(k in c) printf "%s=%d ",k,c[k]; print ""}' "$trades")"
  fi

  echo "entries=${ecount}  trades=${tcount}  outcomes: ${oline}"
}

run_baseline() {
  local d="$1"
  echo "== Baseline (${d}) =="
  python -m sbwatch.cli.main levels build --date "$d" >/dev/null
  python -m sbwatch.cli.main replay run   --date "$d" >/dev/null

  [[ -f "out/trades_${d}.csv" ]]          && cp "out/trades_${d}.csv"          "out/trades_${d}.csv"          || true
  [[ -f "out/replay_entries_${d}.csv" ]]  && cp "out/replay_entries_${d}.csv"  "out/replay_entries_${d}.csv"  || true
}

run_variant_allow_wick() {
  local d="$1"
  local tag="_allowwick"
  echo "== Variant A: ALLOW wick-only (${d}${tag}) =="
  # No --no-wick-only flag
  python -m sbwatch.cli.main levels build --date "$d" >/dev/null
  python -m sbwatch.cli.main replay run   --date "$d" >/dev/null

  [[ -f "out/trades_${d}.csv" ]]          && cp "out/trades_${d}.csv"         "out/trades_${d}${tag}.csv"         || true
  [[ -f "out/replay_entries_${d}.csv" ]]  && cp "out/replay_entries_${d}.csv" "out/replay_entries_${d}${tag}.csv" || true
}

run_variant_looser_hygiene() {
  local d="$1"
  local tag="_loose"
  echo "== Variant B: LOOSER hygiene (${d}${tag}) =="
  (
    # Loosened filters for this subshell only
    export ENTRY_GATE_MIN_SECS=180
    export ENTRY_GATE_MIN_PTS=6
    export ENTRY_COOLDOWN_SEC=600
    export SWEEP_TOL_TICKS=3
    export MIN_GAP_TICKS=2
    export NO_OPPOSITE_WITHIN_COOLDOWN=0

    python -m sbwatch.cli.main levels build --date "$d" >/dev/null
    python -m sbwatch.cli.main replay run   --date "$d" >/dev/null
  )
  [[ -f "out/trades_${d}.csv" ]]          && cp "out/trades_${d}.csv"         "out/trades_${d}${tag}.csv"         || true
  [[ -f "out/replay_entries_${d}.csv" ]]  && cp "out/replay_entries_${d}.csv" "out/replay_entries_${d}${tag}.csv" || true
}

for d in "${DATES[@]}"; do
  echo
  echo "================  ${d}  ================"

  # Baseline
  run_baseline "$d"
  summarize "" "$d"

  # If no trades on baseline, try the 2 variants
  if [[ ! -f "out/trades_${d}.csv" ]] || [[ "$(tail -n +2 "out/trades_${d}.csv" | wc -l || true)" -eq 0 ]]; then
    run_variant_allow_wick "$d"
    summarize "_allowwick" "$d"

    run_variant_looser_hygiene "$d"
    summarize "_loose" "$d"
  fi

  # Show how many ICT entry rows existed in the replay entries file
  if [[ -f "out/replay_entries_${d}.csv" ]]; then
    printf "ICT entries present: "
    (grep -c 'ICT_.*ENTRY' "out/replay_entries_${d}.csv" || true)
  else
    echo "ICT entries present: 0 (no entries file)"
  fi
done

echo
echo "Compare:"
echo "  out/trades_YYYY-MM-DD.csv (baseline)"
echo "  out/trades_YYYY-MM-DD_allowwick.csv (wick-only allowed)"
echo "  out/trades_YYYY-MM-DD_loose.csv (looser gate/cooldown/dedupe)"
