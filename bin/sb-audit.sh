#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

red(){ printf "\033[31m%s\033[0m\n" "$*"; }
grn(){ printf "\033[32m%s\033[0m\n" "$*"; }
ylw(){ printf "\033[33m%s\033[0m\n" "$*"; }
sec(){ echo; ylw "=== $* ==="; }

sec "BASIC STRUCTURE"
test -d src/sbwatch/app && grn "OK src tree present" || red "FAIL missing src/sbwatch/app"
test -f scripts/live_fetch_nq.sh && grn "OK fetch script present" || red "FAIL scripts/live_fetch_nq.sh missing"

sec "PYTHON SYNTAX (compile all)"
if python -m compileall -q src; then grn "OK python compiles"; else red "FAIL python compile errors"; fi

sec "BASH SYNTAX (scripts/*)"
if ls scripts/*.sh >/dev/null 2>&1; then
  bad=0
  while read -r f; do
    if ! bash -n "$f" 2>/dev/null; then red "FAIL bash syntax: $f"; bad=1; fi
  done < <(ls scripts/*.sh)
  [[ $bad -eq 0 ]] && grn "OK bash syntax for scripts/*"
else
  ylw "WARN no scripts/*.sh found"
fi

sec "SYSTEMD UNITS IN REPO"
for f in systemd/sb-live.service systemd/sb-live-fetch.service; do
  if [[ -f "$f" ]]; then
    echo "-- $f"
    sed -n 's/ExecStart=.*/&/p' "$f"
  else
    red "FAIL missing $f"
  fi
done
[[ -f systemd/sb-watchbot.service ]] && red "FAIL legacy unit present: systemd/sb-watchbot.service (remove it)" || grn "OK no legacy combined unit"

sec "LIVE SERVICE EXECSTART VALIDATION"
if grep -q "python -m sbwatch.app.live_sb" systemd/sb-live.service; then
  grn "OK live uses module CLI"
else
  red "FAIL live unit does not use module CLI (python -m sbwatch.app.live_sb)"
fi

sec "FETCH SCRIPT AUDIT"
head -n 1 scripts/live_fetch_nq.sh | grep -qE '^#!' && grn "OK shebang" || red "FAIL missing shebang (#!)"
grep -n "bad scale (skip write)" scripts/live_fetch_nq.sh >/dev/null && grn "OK bad-scale guard present" || red "FAIL missing 'bad scale (skip write)' guard"
grep -n 'mv -f.*"\$TMP_NORM".*"\$OUT"' scripts/live_fetch_nq.sh >/dev/null && grn "OK atomic mv present" || red "FAIL atomic mv not found"
if grep -q $'\xEF\xB8\x8F' scripts/live_fetch_nq.sh 2>/dev/null; then ylw "WARN unicode emoji in fetch script (may break some shells)"; fi

sec "DATETIME GUARD IN CODE"
if grep -Rq "_ensure_datetime(" src/sbwatch/app; then
  grn "OK datetime guard helper present"
else
  ylw "WARN no datetime guard helper function found"
fi
# show first 3 read_csv callsites
echo "-- read_csv callsites (first 3):"
grep -RIn "pd.read_csv(" src/sbwatch/app | head -n 3 || true

sec ".GITIGNORE / TRACKED RUNTIME"
if grep -q "^live/$" .gitignore && grep -q "^out/$" .gitignore; then
  grn "OK .gitignore excludes live/ and out/"
else
  ylw "WARN .gitignore missing live/ or out/"
fi
if git ls-files | grep -E '^(live/|out/|backups/|.*\.(tgz|tar\.gz|log)$)' >/dev/null; then
  red "FAIL runtime files tracked by git:"
  git ls-files | grep -E '^(live/|out/|backups/|.*\.(tgz|tar\.gz|log)$)'
else
  grn "OK no tracked runtime artifacts"
fi

sec "ENV / CONFIG SNAPSHOT"
[[ -f /etc/sb-watchbot/env ]] && grn "OK /etc/sb-watchbot/env exists" || ylw "WARN /etc/sb-watchbot/env missing (create it)"
grep -E '^(TZ=|SYM=|DATABENTO_API_KEY=|DISCORD_WEBHOOK=)' /etc/sb-watchbot/env 2>/dev/null || ylw "WARN important env vars not shown (check manually)"

sec "OPTIONAL RUNTIME CHECKS (if services installed)"
if systemctl is-enabled sb-live.service >/dev/null 2>&1; then
  systemctl is-active sb-live.service >/dev/null && grn "OK sb-live.service running" || ylw "WARN sb-live.service not running"
fi
if systemctl is-enabled sb-live-fetch.service >/dev/null 2>&1; then
  systemctl is-active sb-live-fetch.service >/dev/null && grn "OK sb-live-fetch.service running" || ylw "WARN sb-live-fetch.service not running"
fi

sec "DONE"
