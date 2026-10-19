from app.desktop.shell import launch


def test_desktop_shell_launch_metadata():
    out = launch()
    assert out['backend_autostart'] is True
