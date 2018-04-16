import pytest

def f():
    raise SystemExit(1)

def test_mytest():
    import jobmanager
    import jobmanager.client
    with pytest.raises(SystemExit):
        f()
