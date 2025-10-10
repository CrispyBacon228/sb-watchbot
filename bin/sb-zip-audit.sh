#!/usr/bin/env bash
set -euo pipefail

ZIP="${1:-}"
if [[ -z "$ZIP" || ! -f "$ZIP" ]]; then
  echo "usage: bin/sb-zip-audit.sh /path/to/sb-watchbot-main.zip"
  exit 1
fi

WORK="/tmp/sbzip.$(date +%s)"
mkdir -p "$WORK"
unzip -q "$ZIP" -d "$WORK"

# if the zip unwraps to a nested folder, grab it
ROOT="$(find "$WORK" -maxdepth 2 -type d -name 'sb-watchbot*' | head -n1 || true)"
ROOT="${ROOT:-$WORK}"

sec(){ echo; printf "\033[33m=== %s ===\033[0m\n" "$*"; }
ok(){  printf "\033[32mOK %s\033[0m\n" "$*"; }
bad(){ printf "\033[31mFAIL %s\033[0m\n" "$*"; }
warn(){ printf "\033[33mWARN %s\033[0m\n" "$*"; }

cd "$ROOT" || exit 1

sec "BASIC STRUCTURE"
test -d src/sbwatch/app && ok "src tree present" || bad "missing src/sbwatch/app"
test -f scripts/live_fetch_nq.sh && ok "fetch script present" || bad "scripts/live_fetch_nq.sh missing"

sec "PYTHON SYNTAX (compileall)"
if python -m compileall -q src; then ok "python compiles"; else bad "python compile errors"; fi

sec "BASH SYNTAX (scripts/*)"
if ls scripts/*.sh >/dev/null 2>&1; then
  if ! bash -n scripts/*.sh 2>/dev/null; then bad "bash syntax error(s) in scripts"; else ok "bash syntax for scripts/*"; fi
else
  warn "no scripts/*.sh found"
fi

sec "SYSTEMD UNITS IN REPO"
for f in systemd/sb-live.service systemd/sb-live-fetch.service; do
  if [[ -f "$f" ]]; then
    echo "-- $f"; sed -n 's/ExecStart=.*/&/p' "$f"
  else
    bad "missing $f"
  fi
done
[[ -f systemd/sb-watchbot.service ]] && bad "legacy combined unit present (uses old CLI)" || ok "no legacy combined unit"

sec "LIVE SERVICE EXECSTART VALIDATION"
grep -q "python -m sbwatch.app.live_sb" systemd/sb-live.service \
  && ok "live uses module CLI" \
  || bad "live unit does not use module CLI"

sec "FETCH SCRIPT AUDIT"
head -n 1 scripts/live_fetch_nq.sh | grep -qE '^#!' && ok "shebang" || bad "missing shebang (#!)"
grep -q "bad scale (skip write)" scripts/live_fetch_nq.sh && ok "bad-scale guard present" || bad "missing 'bad scale (skip write)' guard"
grep -q 'mv -f.*"\$TMP_NORM".*"\$OUT"' scripts/live_fetch_nq.sh && ok "atomic mv present" || bad "atomic mv not found"
# emoji check
if grep -q $'\xEF\xB8\x8F' scripts/live_fetch_nq.sh 2>/dev/null; then warn "unicode emoji present (prefer plain WARN:)"; fi

sec "DATETIME GUARD IN CODE"
grep -Rq "_ensure_datetime(" src/sbwatch/app && ok "datetime guard helper present" || warn "no datetime guard helper found"
echo "-- read_csv callsites (first 3):"
grep -RIn "pd.read_csv(" src/sbwatch/app | head -n 3 || true

sec ".GITIGNORE / TRACKED RUNTIME (as zipped)"
if grep -q "^live/$" .gitignore && grep -q "^out/$" .gitignore; then
  ok ".gitignore excludes live/ and out/"
else
  warn ".gitignore missing live/ or out/"
fi
if git ls-files >/dev/null 2>&1; then
  if git ls-files | grep -E '^(live/|out/|backups/|.*\.(tgz|tar\.gz|log|csv)$)' >/dev/null; then
    bad "runtime files tracked by git in the zip tree:"
    git ls-files | grep -E '^(live/|out/|backups/|.*\.(tgz|tar\.gz|log|csv)$)'
  else
    ok "no tracked runtime artifacts in the zip tree"
  fi
else
  warn "not a git repo inside zip — skipping tracked-file check"
fi

sec "SUGGESTED FIXES (if any FAILs)"
cat <<'TXT'
- Legacy unit present?  -> git rm -f systemd/sb-watchbot.service
- Live unit wrong CLI?  -> ensure ExecStart uses: python -m sbwatch.app.live_sb ...
- Fetch script issues?  -> ensure shebang, bad-scale guard, and atomic mv exist
- Emoji in fetch logs?  -> replace with 'WARN:'
- Missing datetime guard -> wrap pd.read_csv with _ensure_datetime(...)
- Runtime files tracked  -> git rm -r --cached out live backups; update .gitignore
TXT

sec "DONE"
