#!/usr/bin/env python3
from __future__ import annotations
import os, sys
from datetime import datetime, timedelta, timezone
from databento import Historical

DATASET = os.getenv("DATASET","GLBX.MDP3")
SCHEMA  = os.getenv("SCHEMA","trades")
SYMBOL  = os.getenv("SYMBOL","NQZ5")

def main():
    key = os.getenv("DATABENTO_API_KEY","").strip()
    if not key:
        print("No DATABENTO_API_KEY in env.")
        sys.exit(1)
    client = Historical(key=key)
    # candidates to test
    s = SYMBOL.upper()
    root = ''.join([c for c in s if c.isalpha()]) or "NQ"
    candidates = list(dict.fromkeys([s, root, f"CME::{s}", f"CME.{s}", f"F.{s}", f"{s}.FUT", "NQ"]))

    print(f"[probe] DATASET={DATASET} SCHEMA={SCHEMA} candidates={candidates}")
    try:
        res = client.symbology.resolve(dataset=DATASET, symbols=candidates)
        print("[probe] symbology.resolve =>")
        for k, v in res.items():
            print(f"  {k} -> {v}")
    except Exception as e:
        print("[probe] resolve error:", e)

    start = datetime.now(timezone.utc) - timedelta(minutes=90)
    end   = datetime.now(timezone.utc)
    for cand in candidates:
        try:
            df = client.timeseries.get_range(
                dataset=DATASET, schema=SCHEMA, symbols=cand,
                start=start.isoformat(), end=end.isoformat()
            ).to_df()
            print(f"[probe] fetch {cand}: rows={0 if df is None else len(df)}")
            if df is not None and len(df) > 0:
                print(df.head().to_string(index=False))
                break
        except Exception as e:
            print(f"[probe] fetch {cand} error: {e}")

if __name__ == "__main__":
    main()
