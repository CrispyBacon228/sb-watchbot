from __future__ import annotations
import os, yaml
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class Settings:
    instrument: str
    tick_size: float
    timezone_et: str
    us_session: Dict[str,str]
    sb_window: Dict[str,str]
    alerts: Dict[str,bool]
    level_tolerance_ticks: int
    stop_buffer_ticks: int
    execution: Dict[str,Any]
    sweep_cooldown_min: int
    global_entry_cooldown_min: int
    levels_path: str
    state_path: str
    log_path: str
    discord_webhook: str
    databento_key: str

def load_settings() -> Settings:
    cfg_path = "/opt/sb-watchbot/configs/settings.yaml"
    with open(cfg_path, "r") as f:
        raw = yaml.safe_load(f)
    env = {
        "discord_webhook": os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
        "databento_key": os.getenv("DATABENTO_API_KEY", "").strip(),
    }
    for k in ("instrument","tick_size","timezone_et","us_session","sb_window","alerts",
              "level_tolerance_ticks","stop_buffer_ticks","execution",
              "sweep_cooldown_min","global_entry_cooldown_min","levels_path",
              "state_path","log_path"):
        if k not in raw:
            raise ValueError(f"Missing config key: {k}")
    return Settings(
        instrument=raw["instrument"],
        tick_size=float(raw["tick_size"]),
        timezone_et=raw["timezone_et"],
        us_session=raw["us_session"],
        sb_window=raw["sb_window"],
        alerts=raw["alerts"],
        level_tolerance_ticks=int(raw["level_tolerance_ticks"]),
        stop_buffer_ticks=int(raw["stop_buffer_ticks"]),
        execution=raw["execution"],
        sweep_cooldown_min=int(raw["sweep_cooldown_min"]),
        global_entry_cooldown_min=int(raw["global_entry_cooldown_min"]),
        levels_path=raw["levels_path"],
        state_path=raw["state_path"],
        log_path=raw["log_path"],
        discord_webhook=env["discord_webhook"],
        databento_key=env["databento_key"],
    )
