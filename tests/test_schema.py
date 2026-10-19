from app.memory.models import Capsule, CapsuleKind, PolicyMode


def test_capsule_schema_v04_fields():
    c = Capsule(source_type='note', source_ref='x', text='hello')
    assert c.kind == CapsuleKind.standard
    assert c.policy == PolicyMode.persistent
    assert isinstance(c.workspace_ids, list)
