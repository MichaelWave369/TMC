from app.core.consolidation import consolidate
from app.memory.models import Capsule, PolicyMode


def test_locked_capsule_not_auto_summarized():
    a = Capsule(source_type='n', source_ref='r', text='same', summary='same', tags=['t'], policy=PolicyMode.locked)
    b = Capsule(source_type='n', source_ref='r', text='same', summary='same', tags=['t'])
    caps, stats = consolidate([a, b])
    assert stats['merged'] == 0
    assert all(c.summary != 'Theme bridge: t' for c in caps)
