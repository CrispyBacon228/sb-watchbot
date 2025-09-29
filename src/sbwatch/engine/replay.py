from pathlib import Path
import json
import os
import csv as csv_mod  # avoid shadowing param name "csv"

def run_replay(*, date=None, date_et=None,
               csv=None, csv_path=None,
               out=None, out_dir=None,
               wick_only=True, **kwargs):
    """
    Compatibility wrapper used by the CLI:
      - date or date_et (CLI uses date_et)
      - csv or csv_path for the output file
      - out_dir or out for the output directory
    Minimal behavior: read data/levels.json and write CSV [time, price].
    """
    # Choose the date string
    date_str = date_et or date or "unknown"

    # Resolve output directory
    out_base = Path(out_dir or out or "./out")
    out_base.mkdir(parents=True, exist_ok=True)

    # Resolve output CSV path
    out_csv = csv_path or csv
    if out_csv:
        out_csv = Path(out_csv)
        if not out_csv.is_absolute():
            out_csv = out_base / out_csv
    else:
        out_csv = out_base / f"replay_{date_str}.csv"

    # Input levels
    levels_file = Path("data/levels.json")
    if not levels_file.exists():
        raise FileNotFoundError(f"{levels_file} not found. Run 'sbwatch levels build' first.")

    try:
        payload = json.loads(levels_file.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"{levels_file} invalid JSON: {e}")

    rows = payload.get("levels", [])

    # Write CSV
    with out_csv.open("w", newline="") as fh:
        w = csv_mod.writer(fh)
        w.writerow(["time", "price"])
        for r in rows:
            w.writerow([r.get("time"), r.get("price")])

    return str(out_csv)
