# Local evaluation only

TMC source is MIT-licensed. The current runtime is for **non-sensitive, local evaluation** only, not public hosting, production secret storage, or a remote shared service.

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/ui` locally. Never bind to `0.0.0.0`, forward the port, or publish this process through a tunnel or reverse proxy.

Place user data and configuration under a private, backed-up operator environment. Do not upload `data/` runtime records, database files, support bundles, credentials, or logs to Git.

See [SECURITY.md](SECURITY.md) and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) before use.
