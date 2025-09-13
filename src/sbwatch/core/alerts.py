from dataclasses import dataclass

@dataclass
class TradeAlert:
    side: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    r_multiple: float
    basis: str
    label: str = "Silver Bullet Entry (Displacement)"

def format_discord(a: TradeAlert) -> str:
    return (
        f"✅ {a.label}\n"
        f"*Level*: **{a.basis}**\n"
        f"*Side*: **{a.side}**\n"
        f"*Entry*: {a.entry}\n"
        f"*Stop*: {a.stop}\n"
        f"*TP1*: {a.tp1}\n"
        f"*TP2*: {a.tp2}\n"
        f"*R*: {a.r_multiple}\n"
    )
