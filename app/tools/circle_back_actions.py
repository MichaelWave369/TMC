"""Manual, localhost-only CLI for Circle-Back operator decisions.

No HTTP interface, background execution, scheduler, or automated verification.
"""
from __future__ import annotations

import argparse
import json

from app.core.service import MemoryService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review and record local TMC next actions")
    parser.add_argument("--db", default="data/tmc.db", help="Path to local SQLite DB")
    subs = parser.add_subparsers(dest="operation", required=True)
    subs.add_parser("list", help="Show next actions in the active profile")

    p = subs.add_parser("propose", help="Create an unapproved proposal")
    p.add_argument("--project-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--rationale", default="")
    p.add_argument("--source", action="append", default=[], help="Visible source capsule ID")
    p.add_argument("--confirm-local-operator", action="store_true", required=True)

    for action in ("approve", "reject"):
        p = subs.add_parser(action, help="Explicit local operator decision")
        p.add_argument("--action-id", required=True)
        p.add_argument("--note", default="")
        p.add_argument("--confirm-local-operator", action="store_true", required=True)

    p = subs.add_parser("attest", help="Attest done without independently verifying")
    p.add_argument("--action-id", required=True)
    p.add_argument("--evidence", action="append", required=True, help="Visible capsule ID")
    p.add_argument("--note", required=True)
    p.add_argument("--confirm-local-operator", action="store_true", required=True)

    p = subs.add_parser("history", help="Read an action's stored local decision events")
    p.add_argument("--action-id", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    svc = MemoryService(args.db)
    if args.operation == "list":
        out = svc.list_next_actions()
    elif args.operation == "propose":
        out = svc.propose_next_action(
            args.project_id, args.title, args.rationale, args.source
        )
    elif args.operation in {"approve", "reject"}:
        out = svc.decide_next_action(
            args.action_id, args.operation == "approve", args.note
        )
    elif args.operation == "attest":
        out = svc.attest_next_action_done(
            args.action_id, args.evidence, args.note
        )
    else:
        out = svc.next_action_history(args.action_id)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
