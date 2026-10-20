# Total Memory Core (TMC)

**An independent, local-first memory platform for AI systems.**

[MIT License](LICENSE) · Python 3.10+ · Operator-controlled storage

TMC explores structured memory capsules, identity and project context, policy-aware retrieval, local attachments, audits, snapshots, integration interfaces, and explainable memory operations. The source is open for inspection, learning, reuse, and contributions under MIT.

## Security notice

**Source availability does not mean remote-deployment readiness.** The current HTTP API has no outer authentication/authorization middleware and its legacy XOR-based vault transformation is **not secure encryption**. TMC must be evaluated on a trusted machine, bound to `127.0.0.1` only, with **non-sensitive demo data**. Do not publish it as a network service, store secrets in its vaults, or commit private runtime files.

## Development quick start

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/ui` for the local operator interface, or `/docs` for the API documentation.

## Features

- Capsule-based memory and local ingestion
- Profile-scoped identity and workspace organization
- Retrieval ranking, provenance fields, and policy decisions
- Local SQLite-backed storage with operator audits
- Import/export, snapshots, plugins, connectors, and rule foundations
- Diagnostic, migration, and release-readiness utilities

## Second Brain: Circle-Back (experimental)

TMC can now generate a **local, read-only project re-entry queue** from linked memory records without claiming completion or treating stored text as independently verified. It exposes capsule IDs for operator review, not the raw memory text, and deliberately does not add a remote HTTP endpoint.

See [the Circle-Back guide](docs/SECOND_BRAIN_CIRCLE_BACK.md) and run `python -m app.tools.circle_back_preview --db data/tmc.db` after local setup.

**Circle-Back R1:** Opt-in, local operator decisions can also be recorded as proposed, approved, rejected, or operator-attested (not independently verified). See [the operator decision guide](docs/CIRCLE_BACK_OPERATOR_ACTIONS.md) for the local-only CLI and evidence requirements. R2 adds a read-only [Evidence Drift Gate](docs/CIRCLE_BACK_EVIDENCE_DRIFT.md) so previously linked evidence changes cannot quietly masquerade as unchanged.

**Circle-Back R3:** The [local review board](docs/CIRCLE_BACK_REVIEW_BOARD.md) ranks project suggestions together with operator action statuses and evidence-change warnings. Run `python -m app.tools.circle_back_actions --db data/tmc.db review`. It never independently verifies completion or triggers actions.

**Circle-Back R4:** Generate a [static, offline visual review board](docs/CIRCLE_BACK_OFFLINE_HTML.md), with no server, scripts, or external assets. Run `python -m app.tools.circle_back_html --db data/tmc.db` to create a private local HTML file. Do not publish generated reports.

**Circle-Back R5:** Save and compare two [private local review snapshots](docs/CIRCLE_BACK_SNAPSHOT_DELTA.md) with `python -m app.tools.circle_back_delta snapshot` and `python -m app.tools.circle_back_delta compare --before OLD.json --after NEW.json`. Changed records are review clues, never independent verification.

**Circle-Back R6:** Render a [private offline visual change timeline](docs/CIRCLE_BACK_TIMELINE.md) from 2–12 saved local snapshots with `python -m app.tools.circle_back_timeline --snapshot OLDEST.json --snapshot NEWEST.json`. No public server, scripts, or proof-of-completion claims.

## Project status

This is a **source-publication candidate**, not a security-certified or production-ready memory service. See [SECURITY.md](SECURITY.md), [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md), and [docs/RELEASE_READINESS.md](docs/RELEASE_READINESS.md) for current limitations and verification gates.

Copyright © 2026 Michael Hughes. Released under the [MIT License](LICENSE).
