"""Local command-line preview of the Circle-Back project queue."""
from __future__ import annotations

import argparse
import json

from app.core.service import MemoryService


def main() -> None:
    parser = argparse.ArgumentParser(description="Show TMC project re-entry suggestions locally")
    parser.add_argument("--db", default="data/tmc.db", help="Local TMC SQLite database")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--stale-days", type=int, default=30)
    args = parser.parse_args()
    # Service initialization can create local defaults; queue generation itself
    # performs no writes and makes no completion or provenance truth claims.
    service = MemoryService(args.db)
    print(json.dumps(
        service.circle_back_queue(limit=args.limit, stale_days=args.stale_days),
        indent=2,
    ))


if __name__ == "__main__":
    main()
