"""R6: create a static local timeline from 2-12 private R5 review snapshots.

This tool cannot contact websites, create jobs, or attest completion.
The generated HTML contains project names and action IDs. Keep it private.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from app.memory.review_timeline import (
    MAX_TIMELINE_SNAPSHOTS,
    build_review_timeline,
    render_review_timeline_html,
)
from app.tools.circle_back_delta import load_private_snapshot
from app.tools.circle_back_html import save_new_local_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create one offline Circle-Back change timeline from saved local snapshots"
    )
    parser.add_argument(
        "--snapshot", type=Path, action="append", required=True,
        help="Previously saved private R5 snapshot, ordered oldest to newest; repeat 2-12 times",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Optional unused .html destination OUTSIDE the TMC source checkout",
    )
    return parser


def create_offline_timeline(paths: list[Path], output: Path | None = None) -> Path:
    """Validate all snapshot inputs before creating a single output file."""
    if not isinstance(paths, list) or not 2 <= len(paths) <= MAX_TIMELINE_SNAPSHOTS:
        raise ValueError("Supply 2 through 12 snapshots, ordered oldest to newest")
    # Do not quietly compare duplicate input paths. Existing private snapshot
    # loader rejects symlinks and invalid, oversized, malformed snapshot JSON.
    resolved = [path.expanduser().resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("Each timeline snapshot must be a different file")
    snapshots = [load_private_snapshot(path.expanduser()) for path in paths]
    timeline = build_review_timeline(snapshots)
    document = render_review_timeline_html(timeline)
    return save_new_local_report(document, output)


def main() -> None:
    args = build_parser().parse_args()
    output = create_offline_timeline(args.snapshot, args.output)
    print(f"Private offline Circle-Back timeline saved to: {output}")
    print("Open the HTML file directly; no HTTP server, network or scripts are needed.")
    print("Contains local project names and action IDs; never commit, share or upload it.")
    print("Changes reflect recorded review states, not independent verification.")


if __name__ == "__main__":
    main()
