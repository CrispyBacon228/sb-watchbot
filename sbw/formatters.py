from __future__ import annotations
from .engine import TradeIdea

def format_trade(idea: TradeIdea) -> str:
    tag = "✅ Silver Bullet Entry (Sweep)" if idea.kind=="SB" else "✅ Trade Alert (Outside SB)"
    return (
        f"{tag}\n"
        f"*Level*: **{idea.level_name}**\n"
        f"*Side*: **{idea.side}**\n"
        f"*Entry*:  {idea.entry:.2f}\n"
        f"*Stop*:   {idea.stop:.2f}\n"
        f"*TP1*:    {idea.tp1:.2f}  (1R)\n"
        f"*TP2*:    {idea.tp2:.2f}  (2R)\n"
        f"*R*:      {idea.R:.2f}\n"
        f"*When*:   {idea.when_et.strftime('%H:%M:%S ET')}\n"
    )

def format_info(level_name: str, bias_side: str, price: float, when_str: str, tol_ticks: int) -> str:
    return (
        "🕒 Sweep Detected\n"
        f"*Level*: **{level_name}** → {bias_side}\n"
        f"*Price*: {price:.2f}  (±{tol_ticks} ticks tolerance)\n"
        f"*When*:  {when_str}\n"
    )
