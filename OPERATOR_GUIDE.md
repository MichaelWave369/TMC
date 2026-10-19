# Operator quick start

1. Create a local Python environment and install `.[dev]`.
2. Run `python -m pytest -q` to verify the installed dependency set.
3. Run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
4. Browse `http://127.0.0.1:8000/ui` for diagnostics and local memory tools.
5. Use non-sensitive test records, review policy decisions and check audit outputs.

Before import/export, sync, backup or restore, inspect the selected scope and destination. Do not assume vault content is cryptographically protected; see [SECURITY.md](SECURITY.md). Do not expose the local service to other devices.
