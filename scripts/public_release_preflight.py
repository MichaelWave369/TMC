#!/usr/bin/env python3
"""Conservative public-source preflight for a full local Git checkout.

Does NOT certify absence of secrets or production runtime security.
Outputs finding paths only (never the matching credential value).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = "scripts/public_release_preflight.py"
ALLOWED_DATA = {"data/sample_capsules.json", "data/.gitkeep"}
SENSITIVE_BASENAMES = {
    ".env", "credentials.json", "service-account.json",
    "id_rsa", "id_ed25519", "id_ecdsa", "secrets.json",
}
SENSITIVE_SUFFIXES = (
    ".db", ".sqlite", ".sqlite3", ".pem", ".key",
    ".p12", ".pfx", ".jks", ".kdbx", ".bak", ".backup",
)
# High-confidence forms only. No "password = ..." heuristic: false positives
# would be both common and unhelpful for this source tree.
SIGNATURES = (
    r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    r"ghp_[A-Za-z0-9]{36}",
    r"github_pat_[A-Za-z0-9_]{40,}",
    r"AKIA[0-9A-Z]{16}",
    r"AIza[0-9A-Za-z_-]{35}",
    r"sk-[A-Za-z0-9]{40,}",
    r"xox[baprs]-[A-Za-z0-9-]{25,}",
)


def git(*args: str, allow_no_match: bool = False) -> str:
    process = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if process.returncode == 0 or (allow_no_match and process.returncode == 1):
        return process.stdout
    raise RuntimeError(
        "git command failed: " + " ".join(args[:3]) +
        f" (exit {process.returncode})"
    )


def risky_path(name: str) -> str | None:
    name = name.replace("\\", "/").lower()
    parts = name.split("/")
    basename = parts[-1]
    if name in ALLOWED_DATA:
        return None
    if name.startswith("data/"):
        return "tracked runtime data"
    if basename in SENSITIVE_BASENAMES:
        return "sensitive filename"
    if basename.startswith(".env.") and basename != ".env.example":
        return "environment configuration"
    if basename.endswith(SENSITIVE_SUFFIXES) or ".sqlite-" in basename:
        return "sensitive file extension"
    if "private-key" in basename or "service_account" in basename:
        return "key/credential filename"
    return None


def run() -> int:
    findings: set[str] = set()
    try:
        shallow = git("rev-parse", "--is-shallow-repository").strip()
        if shallow != "false":
            print("FAIL: shallow checkout cannot audit reachable history")
            return 2
        revisions = git("rev-list", "--all").splitlines()
        if not revisions:
            print("FAIL: no Git commits found")
            return 2
        paths = set(git("ls-files").splitlines())
        for rev in revisions:
            paths.update(git("ls-tree", "-r", "--name-only", rev).splitlines())
        for name in sorted(paths):
            reason = risky_path(name)
            if reason:
                findings.add(f"PATH {reason}: {name}")
        args = ["grep", "-I", "-l", "-E"]
        for signature in SIGNATURES:
            args.extend(("-e", signature))
        for rev in revisions:
            matched = git(*args, rev, "--", allow_no_match=True)
            for line in matched.splitlines():
                _revision, _, path = line.partition(":")
                if path and path != SELF:
                    findings.add(f"TEXT possible credential: {path} (commit {_revision[:12]})")
    except (RuntimeError, OSError) as error:
        print("FAIL: could not complete Git history scan:", error)
        return 2
    if findings:
        print("FAIL: publication preflight findings (matching values are NOT printed):")
        for finding in sorted(findings):
            print(" -", finding)
        print("Review locally; do not disclose findings that include private paths.")
        return 1
    print(f"PASS: no flagged paths or selected text signatures in {len(revisions)} reachable commits.")
    print("MANUAL REVIEW REQUIRED: pass is NOT authorization to publish.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
