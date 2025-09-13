from dataclasses import dataclass
@dataclass
class Displacement:
    side: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    basis: str
