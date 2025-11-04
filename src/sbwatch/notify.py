from __future__ import annotations
import os, math, json, pathlib
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore

# ---------- webhook posting ----------
def _default_post_discord(msg: str) -> None:
    url = (
        os.getenv("DISCORD_WEBHOOK")
        or os.getenv("SB_DISCORD_WEBHOOK")
        or os.getenv("WEBHOOK_URL")
        or ""
    )
    if not url:
        return
    try:
        import requests  # type: ignore
        requests.post(url, json={"content": msg[:1900]}, timeout=8)
    except Exception:
        try:
            import urllib.request
            req = urllib.request.Request(url, data=json.dumps({"content": msg[:1900]}).encode(), headers={"Content-Type":"application/json"})
            urllib.request.urlopen(req, timeout=8).read()
        except Exception:
            pass

try:
    post_discord  # type: ignore
except NameError:
    post_discord = _default_post_discord  # type: ignore

# ---------- time helpers ----------
_ET = ZoneInfo("America/New_York") if ZoneInfo else None

def _to_dt(v: Optional[Union[int,float,str,datetime]]) -> datetime:
    if v is None:
        return datetime.now(timezone.utc)
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, (int,float)):
        ts=float(v)
        if ts>1e12: return datetime.fromtimestamp(ts/1000.0, tz=timezone.utc)  # ms
        if ts>1e10: return datetime.fromtimestamp(ts/1e6,    tz=timezone.utc)  # µs
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(v,str):
        s=v.strip().replace("Z","+00:00")
        try:
            dt=datetime.fromisoformat(s)
        except Exception:
            try: return _to_dt(float(s))
            except Exception: return datetime.now(timezone.utc)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime.now(timezone.utc)

def _fmt_et(when: Optional[Union[int,float,str,datetime]], *, seconds: bool) -> str:
    dt=_to_dt(when)
    if not _ET:
        return dt.strftime("%H:%M:%S UTC") if seconds else dt.strftime("%H:%M UTC")
    et=dt.astimezone(_ET)
    return et.strftime("%H:%M:%S ET") if seconds else et.strftime("%H:%M ET")

# ---------- string helpers ----------
def _fmt_price(x: Optional[float]) -> str:
    if x is None or (isinstance(x,float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    s=f"{x:.5f}".rstrip("0").rstrip(".")
    if "." in s and len(s.split(".",1)[1])<2:
        s=f"{x:.2f}"
    if "." not in s:
        s=f"{x:.2f}"
    return s

def _join(parts: list[str]) -> str:
    return " ".join([p for p in parts if p and p.strip()])

# ---------- optional: daily entry flag so run_live can know if an entry fired ----------
def _entry_flag_path(ts: Optional[Union[int,float,str,datetime]]) -> pathlib.Path:
    dt=_to_dt(ts).astimezone(_ET) if _ET else _to_dt(ts)
    tag=dt.strftime("%Y%m%d")
    return pathlib.Path(os.getenv("SB_STATE_DIR", "/tmp"))/f"sb_entry_{tag}.flag"

def mark_entry_flag(ts: Optional[Union[int,float,str,datetime]]) -> None:
    try:
        _entry_flag_path(ts).touch()
    except Exception:
        pass

def check_entry_flag(ts: Optional[Union[int,float,str,datetime]]) -> bool:
    try:
        return _entry_flag_path(ts).exists()
    except Exception:
        return False

# ---------- PUBLIC ALERTS (single-line, NO symbol) ----------
def post_levels_scan(levels: Dict[str, Any], when: Optional[Union[int,float,str,datetime]]=None) -> None:
    # 📊 SESSION LEVELS (09:45 ET) PDH: 101.50 | PDL: 100.10 ASIA: 100.80–100.05 | LONDON: 100.60–100.20
    L = levels if "levels" not in levels else (levels.get("levels") or {})
    pdh=L.get("pdh"); pdl=L.get("pdl")
    asia_hi,asia_lo=L.get("asia_high"),L.get("asia_low")
    lon_hi,lon_lo  =L.get("london_high"),L.get("london_low")
    t=_fmt_et(when, seconds=False)
    seg=[]
    if (pdh is not None) or (pdl is not None): seg.append(f"PDH: {_fmt_price(pdh)} | PDL: {_fmt_price(pdl)}")
    if (asia_hi is not None) or (asia_lo is not None): seg.append(f"ASIA: {_fmt_price(asia_hi)}–{_fmt_price(asia_lo)}")
    if (lon_hi is not None) or (lon_lo is not None):   seg.append(f"LONDON: {_fmt_price(lon_hi)}–{_fmt_price(lon_lo)}")
    post_discord(f"📊 SESSION LEVELS ({t}) {_join(seg)}".strip())

def post_system_armed(when: Optional[Union[int,float,str,datetime]]=None) -> None:
    # 🟢 SB-WATCHBOT ARMED (10:00:00 ET) Waiting for Silver Bullet setup...
    post_discord(f"🟢 SB-WATCHBOT ARMED ({_fmt_et(when, seconds=True)}) Waiting for Silver Bullet setup...")

def post_entry(side: str, entry: float, sl: float, tp: Optional[float], sweep_label: str,
               when: Optional[Union[int,float,str,datetime]]=None) -> None:
    # 🟩 SB-ENTRY (10:03:00 ET) LONG — sweep of ASIA LOW Entry 101.25 | SL 99.85 | TP~25113.25
    side_txt = "LONG" if str(side).lower().startswith("l") else "SHORT"
    t  = _fmt_et(when, seconds=True)
    es = _fmt_price(entry); sls=_fmt_price(sl); tps=_fmt_price(tp) if tp is not None else "—"
    post_discord(f"🟩 SB-ENTRY ({t}) {side_txt} — sweep of {sweep_label} Entry {es} | SL {sls} | TP~{tps}")
    # --- contract sizing info ---
    try:
        TICK_SIZE = 0.25
        TICK_VALUE = 5.0          # NQ $/tick (use 0.50 for MNQ)
        RISK_PER_TRADE = 1500.0
        stop_ticks = abs(float(entry) - float(sl)) / TICK_SIZE
        risk_per_contract = stop_ticks * TICK_VALUE
        contracts = int(RISK_PER_TRADE // risk_per_contract) if risk_per_contract > 0 else 1
        if contracts < 1: contracts = 1
        post_discord(f"⚙️ Risk model ➜ {stop_ticks:.1f} ticks | ${risk_per_contract:.2f}/ct | {contracts} contracts")
    except Exception as e:
        post_discord(f"[contract calc error: {e}]")
    # --- end contract sizing ---

    mark_entry_flag(when)

def post_tp_hit(price: float, when: Optional[Union[int,float,str,datetime]]=None,
                note: Optional[str]="TP1 reached — runner optional") -> None:
    # ✅ SB-TP HIT (10:21:15 ET) TP1 reached at 25113.25 — runner optional
    p=_fmt_price(price)
    t=_fmt_et(when, seconds=True)
    post_discord(f"✅ SB-TP HIT ({t}) TP1 reached at {p}" + (f" — {note}" if note else ""))

def post_sl_hit(price: float, when: Optional[Union[int,float,str,datetime]]=None) -> None:
    # 🟥 SB-STOP LOSS (10:14:02 ET) Stopped at 99.85 — setup invalidated
    p=_fmt_price(price); t=_fmt_et(when, seconds=True)
    post_discord(f"🟥 SB-STOP LOSS ({t}) Stopped at {p} — setup invalidated")

def post_no_sb(when: Optional[Union[int,float,str,datetime]]=None) -> None:
    # ⚪ NO VALID SB TODAY (11:01 ET) No qualifying sweep + displacement found.
    t=_fmt_et(when, seconds=False)
    post_discord(f"⚪ NO VALID SB TODAY ({t}) No qualifying sweep + displacement found.")

# thin aliases
def levels_scan(levels: Dict[str, Any], when=None): post_levels_scan(levels, when)
def system_armed(when=None): post_system_armed(when)
def entry_long(entry: float, sl: float, tp: Optional[float], sweep_label: str, when=None): post_entry("long", entry, sl, tp, sweep_label, when)
def entry_short(entry: float, sl: float, tp: Optional[float], sweep_label: str, when=None): post_entry("short", entry, sl, tp, sweep_label, when)
def tp_hit(price: float, when=None, note: Optional[str]="TP1 reached — runner optional"): post_tp_hit(price, when, note)
def sl_hit(price: float, when=None): post_sl_hit(price, when)
def no_sb(when=None): post_no_sb(when)

# expose the flag helpers for run_live
def has_entry_today(now: Optional[Union[int,float,str,datetime]]=None) -> bool:
    return check_entry_flag(now)
