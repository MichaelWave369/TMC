from app.memory.storage import SQLiteStore


def test_migration_loader_accepts_legacy_list(tmp_path):
    st = SQLiteStore(str(tmp_path / 't.db'))
    st.load_legacy_seed([{'id':'c1','source_type':'n','source_ref':'r','text':'x'}])
    assert st.get_capsule('c1') is not None
