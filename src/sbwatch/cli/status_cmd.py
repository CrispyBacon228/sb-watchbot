from __future__ import annotations
import os, json
import typer
from datetime import datetime
from zoneinfo import ZoneInfo

app = typer.Typer(help="Show sb-watchbot health/status")
TZ_ET = ZoneInfo("America/New_York")

@app.command("show")
def show():
    # ET time + killzone vars
    now_et = datetime.now(TZ_ET).strftime("%Y-%m-%d %H:%M:%S %Z")
    kz = os.getenv("ENABLE_KILLZONE","true").lower() in ("1","true","yes","y")
    kz1s,kz1e = os.getenv("KZ1_START","09:30"), os.getenv("KZ1_END","11:00")
    kz2s,kz2e = os.getenv("KZ2_START","13:30"), os.getenv("KZ2_END","15:30")

    # levels
    lvl_path = os.getenv("LEVELS_PATH","./data/levels.json")
    try:
        with open(lvl_path) as f: lv = json.load(f)
        levels_ok = True
    except Exception as e:
        lv, levels_ok = {"error": str(e)}, False

    # logging
    print(f"ET now: {now_et}")
    print(f"Killzones enabled: {kz}  ->  {kz1s}-{kz1e}, {kz2s}-{kz2e}")
    print(f"Levels file: {lvl_path}  exists={levels_ok}")
    if levels_ok:
        print(f"  date_et={lv.get('date_et')}  PDH={lv.get('pdh')}  PDL={lv.get('pdl')}")
        print(f"  Asia {lv.get('asia_low')}–{lv.get('asia_high')}  London {lv.get('london_low')}–{lv.get('london_high')}")
    print(f"ALERTS_LOG={os.getenv('ALERTS_LOG','./out/alerts_live.csv')}")
    print(f"MARGIN_SEC={os.getenv('MARGIN_SEC','(default)')}  POLL_SECONDS={os.getenv('POLL_SECONDS','5')}  COOLDOWN_SEC={os.getenv('COOLDOWN_SEC','300')}")
