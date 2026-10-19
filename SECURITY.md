# Security policy

TMC is published as **source code for local, non-sensitive evaluation**. No security audit, cryptographic certification, or remote-use authorization is implied by its MIT license, version, tests, or GitHub visibility.

## Current security limitations

- **Unauthenticated HTTP:** `app/main.py` mounts API and UI routes without verified outer request authentication. Bind the service **only to `127.0.0.1`** on a trusted device. Never expose it to a LAN, the internet, a tunnel or public proxy.
- **Vaults are not securely encrypted:** the legacy SHA-256-derived XOR transformation in `app/core/service.py` does not provide modern confidentiality or authenticity. Do not store secrets, personal memories or regulated content expecting protection.
- **Untrusted files:** file-upload paths, limits and parsing need additional validation; do not use the file-ingestion API with untrusted users or sensitive files.
- **Exports and support bundles:** may reveal private runtime records if distributed or saved carelessly. Never check in local `data/`, backups, logs, or support exports.
- **Tests and scanners:** automated green checks are not proof of production security or freedom from all credentials/private information.

## Vulnerability reporting

Use GitHub's private vulnerability reporting flow under **Security → Report a vulnerability** if available. Otherwise contact the project owner through an established private channel. Do not post secrets, sensitive records, or working exploits into public GitHub issues.

See [docs/RELEASE_READINESS.md](docs/RELEASE_READINESS.md) for source-publication gates.
