"""Background service mode status and pid/lock handling."""
from __future__ import annotations

import os
from pathlib import Path


class ServiceRunner:
    def __init__(self, pid_file: str = "data/tmc_service.pid"):
        self.pid_file = Path(pid_file)

    def status(self) -> dict:
        running = self.pid_file.exists()
        pid = int(self.pid_file.read_text()) if running else None
        return {"running": running, "pid": pid, "mode": "service" if running else "desktop"}

    def start(self) -> dict:
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))
        return {"status": "started", "pid": os.getpid()}

    def stop(self) -> dict:
        if self.pid_file.exists():
            self.pid_file.unlink()
        return {"status": "stopped"}

    def restart(self) -> dict:
        self.stop(); return self.start()
