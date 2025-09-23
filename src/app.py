
# --- Back-adjust hack for continuous alignment with NQ1! ---
ROLL_OFFSET=-200.0

df["open"]  = df["open"]  + ROLL_OFFSET
df["high"]  = df["high"]  + ROLL_OFFSET
df["low"]   = df["low"]   + ROLL_OFFSET
df["close"] = df["close"] + ROLL_OFFSET
