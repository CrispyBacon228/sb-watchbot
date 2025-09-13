_seen = set()
def should_emit(key: str, cooldown: int = 300) -> bool:
    # TODO: include time, cooldowns; placeholder
    if key in _seen: return False
    _seen.add(key); return True
