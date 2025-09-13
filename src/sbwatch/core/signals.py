from dataclasses import dataclass
from typing import Optional

@dataclass
class SweepEvent:
    level_name: str
    price: float
    timestamp: str  # ISO8601

@dataclass
class DisplacementEvent:
    direction: str  # "LONG" or "SHORT"
    entry: float
    stop: float
    tp1: float
    tp2: float
    r_multiple: float
    basis: str      # e.g., "London High", "NY Kill Zone"

def is_valid_sweep(prev_high: float, current_high: float, tolerance: float = 0.25) -> bool:
    # Example placeholder rule; replace with your exact rule
    return current_high > prev_high and (current_high - prev_high) <= tolerance

def format_trade_message(evt: DisplacementEvent) -> str:
    return (
        f"✅ Silver Bullet Entry ({'Displacement' if evt.r_multiple else 'Standard'})\n"
        f"*Side*: **{evt.direction}**\n"
        f"*Entry*: {evt.entry}\n"
        f"*Stop*: {evt.stop}\n"
        f"*TP1*: {evt.tp1}\n"
        f"*TP2*: {evt.tp2}\n"
        f"*R*: {evt.r_multiple}\n"
        f"*Level*: **{evt.basis}**"
    )
