"""Private local Circle-Back snapshot/compare command, never an HTTP route.

Snapshots are a historical *view* of a local board, not independent
verification. The output contains project names and action IDs. Keep it
private, never commit it, and never publish it through Pages.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from app.memory.review_delta import (
    compare_review_snapshots, snapshot_from_review_board, _check_snapshot,
)

MAX_INPUT_BYTES = 2_000_000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Save and compare private, local Circle-Back review snapshots"
    )
    commands = parser.add_subparsers(dest="operation", required=True)
    snapshot = commands.add_parser("snapshot", help="Save current local board to a new private JSON")
    snapshot.add_argument("--db", default="data/tmc.db")
    snapshot.add_argument("--output", type=Path)
    snapshot.add_argument("--stale-days", type=int, default=30)
    compare = commands.add_parser("compare", help="Compare two previously saved local snapshots")
    compare.add_argument("--before", type=Path, required=True)
    compare.add_argument("--after", type=Path, required=True)
    compare.add_argument("--output", type=Path)
    return parser


def save_private_json(payload: dict, output: Path | None = None) -> Path:
    """Write only new local JSON files, with no source-tree destinations."""
    repo_root = Path(__file__).resolve().parents[2]
    if output is None:
        directory = Path(tempfile.mkdtemp(prefix="tmc-circle-back-delta-"))
        target = directory / "snapshot.json"
    else:
        target = output.expanduser().absolute()
        if target.suffix.lower() != ".json":
            raise ValueError("Private reports require a .json filename")
        if target.resolve().is_relative_to(repo_root):
            raise ValueError("Private reports must be saved outside the repository")
    # O_EXCL refuses existing paths and symlink final components.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(str(target), flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key in saved JSON snapshot")
        result[key] = value
    return result


def load_private_snapshot(path: Path) -> dict:
    """Read an explicitly selected small snapshot; never use a remote URL."""
    if path.is_symlink():
        raise ValueError("Snapshot input symlinks are not accepted")
    if path.suffix.lower() != ".json" or not path.is_file():
        raise ValueError("Select an existing local JSON snapshot file")
    with path.open("rb") as file:
        data = file.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("Snapshot file is too large")
    try:
        payload = json.loads(data.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid UTF-8 JSON snapshot") from exc
    _check_snapshot(payload)
    return payload


def main() -> None:
    args = build_parser().parse_args()
    if args.operation == "snapshot":
        # Service initialization can create local defaults in a new database.
        # The queue and snapshot methods themselves are read-only.
        from app.core.service import MemoryService

        board = MemoryService(args.db).circle_back_review_board(
            limit=100, stale_days=args.stale_days,
        )
        payload = snapshot_from_review_board(board)
    else:
        before = load_private_snapshot(args.before)
        after = load_private_snapshot(args.after)
        payload = compare_review_snapshots(before, after)
    saved = save_private_json(payload, args.output)
    print(f"Private local {args.operation} saved to: {saved}")
    if args.operation == "compare":
        print(
            f"Shared projects examined: {payload['compared_projects']}; "
            f"project reviews with changes/limited action coverage: "
            f"{payload['projects_with_observed_changes_or_limited_actions']}"
        )
        if payload["project_entry_exit_comparison"] != "complete_for_visible_profile":
            print("Partial coverage: project entry/exit claims were suppressed.")
    else:
        if not payload["coverage_complete"] or payload["cards_truncated"]:
            print("Warning: incomplete project coverage; differences may be limited.")
    print("Local state only; no independent verification. Never publish this JSON.")


if __name__ == "__main__":
    main()
