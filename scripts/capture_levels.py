#!/usr/bin/env python3
import runpy, sys
sys.exit(runpy.run_path("scripts/build_levels.py", run_name="__main__") or 0)
