from app.core.service import MemoryService


def test_event_bus_delivery_and_filtering(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    svc._audit('custom_event', {'x': 1})
    events = svc.events('custom_event')
    assert events and events[-1]['event_type'] == 'custom_event'
