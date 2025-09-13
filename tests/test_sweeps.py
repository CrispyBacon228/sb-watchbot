from sbwatch.core.sweeps import is_sweep
def test_is_sweep():
    assert is_sweep(100.0, 100.2, 0.25) is True
    assert is_sweep(100.0, 100.5, 0.25) is False
