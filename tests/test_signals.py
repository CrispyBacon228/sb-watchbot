from sbwatch.core.signals import is_valid_sweep, DisplacementEvent, format_trade_message

def test_is_valid_sweep():
    assert is_valid_sweep(100.0, 100.2, 0.25) is True
    assert is_valid_sweep(100.0, 100.4, 0.25) is False

def test_format_trade_message_has_core_fields():
    evt = DisplacementEvent("LONG", 100.0, 99.0, 102.0, 104.0, 2.0, "NY Kill Zone")
    msg = format_trade_message(evt)
    for piece in ["Silver Bullet Entry", "LONG", "Entry", "Stop", "TP1", "TP2", "R", "NY Kill Zone"]:
        assert piece in msg
