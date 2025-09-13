from dataclasses import dataclass

@dataclass
class TradeAlert:
    side: str             # "LONG" | "SHORT"
    entry: float
    stop: float
    tp1: float
    tp2: float
    r_multiple: float
    basis: str            # e.g., "London High"
    label: str = "Silver Bullet Entry (Displacement)"

def format_discord(alert: TradeAlert) -> str:
    return (
        f"✅ {alert.label}\n"
        f"*Level*: **{alert.basis}**\n"
        f"*Side*: **{alert.side}**\n"
        f"*Entry*: {alert.entry}\n"
        f"*Stop*: {alert.stop}\n"
        f"*TP1*: {alert.tp1}\n"
        f"*TP2*: {alert.tp2}\n"
        f"*R*: {alert.r_multiple}\n"
    )
