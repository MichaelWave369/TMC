"""Circle-Back R7: explicit local-only operator focus sessions.

This CLI has no HTTP route, timers, background workers, model calls, sync,
or automatic approvals/completions. Local SQLite notes are NOT encrypted.
"""
from __future__ import annotations

import argparse
import json

from app.core.service import MemoryService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Choose one TMC project, run a local review, record a human decision"
    )
    parser.add_argument("--db", default="data/tmc.db", help="Local SQLite database path")
    operations = parser.add_subparsers(dest="operation", required=True)

    listing = operations.add_parser("list", help="Read active-profile focus sessions")
    listing.add_argument("--limit", type=int, default=30)

    start = operations.add_parser("start", help="Start a local operator focus session")
    start.add_argument("--project-id", required=True)
    start.add_argument("--intent", required=True)
    start.add_argument("--confirm-local-operator", action="store_true", required=True)

    close = operations.add_parser("close", help="Record the session review decision, not task completion")
    close.add_argument("--session-id", required=True)
    close.add_argument(
        "--decision", required=True,
        choices=("revisit_later", "needs_evidence", "next_action_identified"),
    )
    close.add_argument("--note", required=True)
    close.add_argument(
        "--action-id", default="", help="Existing proposed/approved action; for next_action_identified only"
    )
    close.add_argument("--confirm-local-operator", action="store_true", required=True)

    history = operations.add_parser("history", help="Read one local session's events")
    history.add_argument("--session-id", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    service = MemoryService(args.db)
    if args.operation == "list":
        result = service.list_focus_sessions(limit=args.limit)
    elif args.operation == "start":
        result = service.start_focus_session(args.project_id, args.intent)
    elif args.operation == "close":
        result = service.close_focus_session(
            args.session_id, args.decision, args.note, args.action_id
        )
    else:
        result = service.focus_session_history(args.session_id)
    print(json.dumps(result, indent=2))
    if args.operation == "close":
        print("Review recorded. No next-action state or task completion was changed.")


if __name__ == "__main__":
    main()
