"""Create an operator-requested static, offline HTML Circle-Back review file.

A report contains project names and local action IDs. It must stay on the
operator's own machine. No browser server or network request is started.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile

from app.core.service import MemoryService
from app.memory.review_html import render_review_board_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a static offline TMC Circle-Back review")
    parser.add_argument("--db", default="data/tmc.db", help="Local SQLite database")
    parser.add_argument("--limit", type=int, default=20, help="1..100 displayed project cards")
    parser.add_argument("--stale-days", type=int, default=30, help="1..3650")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Explicit HTML destination. Existing files will NEVER be replaced.",
    )
    return parser


def save_new_local_report(document: str, output: Path | None = None) -> Path:
    """Write as a newly created local file with restrictive POSIX permissions.

    Refuse existing files (including symlinks). Parent must exist when the
    user supplies --output; default creates a private temporary directory.
    """
    if output is None:
        private_dir = Path(tempfile.mkdtemp(prefix="tmc-circle-back-"))
        target = private_dir / "review.html"
    else:
        target = output.expanduser().absolute()
        if target.suffix.lower() != ".html":
            raise ValueError("An explicit output filename must end in .html")
        # A local HTML report can contain project names/IDs. Refuse to place
        # it anywhere inside the checked-out source tree, even through a
        # symlinked parent directory, to prevent accidental git publication.
        repository_root = Path(__file__).resolve().parents[2]
        if target.resolve().is_relative_to(repository_root):
            raise ValueError("HTML reports must be saved outside the repository")
    # O_EXCL + O_CREAT refuses existing files and symlink destinations.
    descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(document)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def main() -> None:
    args = build_parser().parse_args()
    service = MemoryService(args.db)
    board = service.circle_back_review_board(
        limit=args.limit, stale_days=args.stale_days,
    )
    rendered = render_review_board_html(board)
    report_path = save_new_local_report(rendered, args.output)
    print(f"Local-only offline review generated at: {report_path}")
    print("Contains local project metadata. Do not upload, publish, or commit this HTML file.")
    print("Open that file directly in your browser. No HTTP server is needed.")


if __name__ == "__main__":
    main()
