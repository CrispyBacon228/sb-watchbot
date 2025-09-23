from sbwatch.app import load_levels_json
from sbwatch.core.engine import SBEngine, SBParams

# 1) Load yesterday/today levels (already built in data/levels.json)
lv = load_levels_json()
print("Loaded levels:", lv)

# 2) Build sane default params (same as you've been using)
params = SBParams(
    tz="America/New_York",
    kill_start="12:00", kill_end="13:30",
    sweep_ticks=4, disp_min_ticks=4, fvg_min_ticks=3,
    refill_tol_ticks=2, tp1_r=1.0, tp2_r=2.0,
    stop_buf_ticks=4, ref_lookback_minutes=60,
    require_fvg=False,
)

# 3) Create the engine with levels (this is what your strategy needs)
eng = SBEngine(params, levels=lv)
print("Engine constructed OK; using levels ->", eng.levels)
