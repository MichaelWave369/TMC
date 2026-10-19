from app.core.runtime import RuntimeCadence


def test_runtime_tick_events():
    rt = RuntimeCadence()
    caps = []
    for _ in range(2):
        rt.step(caps, lambda: None, lambda: {})
    ev = rt.step(caps, lambda: None, lambda: {'x': 1})
    assert 'diagnostics' in ev
