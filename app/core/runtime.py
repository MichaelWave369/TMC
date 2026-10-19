"""Runtime cadence coordinator."""
from __future__ import annotations

from app.core.consolidation import consolidate

DIAGNOSTICS_INTERVAL = 3
REFRESH_INTERVAL = 6
CONSOLIDATION_INTERVAL = 9


class RuntimeCadence:
    def __init__(self) -> None:
        self.tick = 0
        self.last_consolidation_run = 0
        self.last_reindex_run = 0

    def step(self, capsules: list, run_refresh, run_diagnostics) -> dict:
        self.tick += 1
        events: dict = {"tick": self.tick}
        if self.tick % DIAGNOSTICS_INTERVAL == 0:
            events["diagnostics"] = run_diagnostics()
        if self.tick % REFRESH_INTERVAL == 0:
            run_refresh()
            self.last_reindex_run = self.tick
            events["graph_refresh"] = True
        if self.tick % CONSOLIDATION_INTERVAL == 0:
            updated, stats = consolidate(capsules)
            events["consolidation"] = stats
            events["capsules"] = updated
            self.last_consolidation_run = self.tick
        return events
