def is_sweep(prev_high: float, curr_high: float, tol: float = 0.25) -> bool:
    return curr_high > prev_high and (curr_high - prev_high) <= tol
