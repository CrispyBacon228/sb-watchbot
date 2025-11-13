import os

# Make sure we don't hit a real webhook by accident
os.environ["DISCORD_WEBHOOK"] = ""

from sbwatch import notify

def fake_post_discord(msg: str) -> None:
    print("DISCORD:", msg)

# Monkey-patch the real Discord poster
notify.post_discord = fake_post_discord

def run():
    cases = [
        # side,  entry,    sl,      tp,       sweep_label, when
        ("long", 100.0,   98.0,   104.0,   "TEST-2pt",      0),
        ("long", 25000.0, 24835.0, 25165.0, "TEST-165ticks", 0),
    ]

    for side, entry, sl, tp, label, when in cases:
        print(f"\n--- CASE {label} ---")
        notify.post_entry(side, entry, sl, tp, label, when)

if __name__ == "__main__":
    run()
