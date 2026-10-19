from app.runtime.config import ConfigManager


def test_config_validation(tmp_path):
    cm = ConfigManager(str(tmp_path / 'cfg.json'))
    ok, errs = cm.validate({'result_cap': 0, 'context_budget': 100, 'vault_auto_lock_idle_min': -1})
    assert not ok and errs
