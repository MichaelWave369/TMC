# Total Memory Core: Architecture

TMC is a local-first Python memory service with FastAPI interfaces and SQLite storage. Its principal pieces live in:

- `app/memory/`: capsules, models, ingestion, policy filtering, indexes and retrieval
- `app/core/service.py`: operator-level memory, profile, vault and workflow methods
- `app/api/` and `app/ui/`: HTTP interface and local operator UI
- `app/platform/`: compatibility, governance, migration and reporting
- `app/plugins/`, `app/connectors/`, `app/automation/`: extension surfaces
- `app/runtime/`: local operation and diagnostic helpers
- `tests/`: regression and negative-control tests

## Boundaries

Profile and policy checks in the application are **not** substitutes for request authentication. The current API is unauthenticated and must stay on a trusted loopback interface. The existing vault transformation is not secure encryption. See [SECURITY.md](SECURITY.md).

Capabilities and release-related labels in code describe current implementation surfaces, not independent certification, production security, or externally validated accuracy.
