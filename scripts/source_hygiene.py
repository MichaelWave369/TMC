#!/usr/bin/env python3
"""Check that tracked source files are suitable for a public source repository.

Heuristic only: passing does not establish a lack of secrets or private data.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DATA = {"data/sample_capsules.json"}
BLOCKED_NAMES = {
    ".env", "credentials.json", "service-account.json",
    "id_rsa", "id_ed25519", "id_ecdsa",
}
BLOCKED_SUFFIXES = (".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx", ".kdbx")


def main() -> int:
    files = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False
    )
    if files.returncode != 0:
        print("FAIL: unable to inspect tracked source")
        return 2
    findings = []
    for item in files.stdout.split(bytes([0])):
        if not item:
            continue
        name = item.decode("utf-8", "replace")
        clean = name.replace("\\", "/").lower()
        basename = clean.rsplit("/", 1)[-1]
        file = ROOT / name
        if (clean.startswith("data/") and clean not in ALLOWED_DATA
                or basename in BLOCKED_NAMES or basename.endswith(BLOCKED_SUFFIXES)
                or basename.startswith(".env.")):
            findings.append(name)
        if file.is_file() and file.stat().st_size > 5_000_000:
            findings.append(name + " (oversized tracked file)")
    if findings:
        print("FAIL: inspect these tracked files before source publication:")
        for item in sorted(set(findings)):
            print(" -", item)
        return 1
    print("PASS: no forbidden runtime/credential filenames or oversized tracked files")
    print("This check does not certify absence of secrets or security readiness.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
