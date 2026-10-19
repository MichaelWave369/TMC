from app.memory.models import Capsule, PolicyMode
from app.memory.policies import PolicyEngine


def test_locked_policy_blocked():
    pe = PolicyEngine()
    c = Capsule(source_type='x', source_ref='y', text='z', policy=PolicyMode.locked)
    allow, _ = pe.allow_retrieval(c, {})
    assert not allow
