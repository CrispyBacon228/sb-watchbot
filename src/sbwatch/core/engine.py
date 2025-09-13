from .execution import Displacement
def decide_trade_example() -> Displacement | None:
    # TODO: real rules (09:30–10, 10–11 SB etc.)
    return Displacement("SHORT", 100.0, 101.0, 98.0, 96.0, "London High")
