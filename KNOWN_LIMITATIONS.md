# Known limitations and non-goals

- The FastAPI UI and HTTP routes do **not** currently have a verified outer authentication/authorization boundary.
- The SHA-256-derived XOR vault transform is **not secure encryption** or protection against tampering.
- Untrusted uploads need hardened filename/path handling, size limits and bounded processing before exposure to other users.
- Retrieval and identity labeling are heuristics, not validated factual correctness or identity attestations.
- Imports, snapshots, support bundles, connectors and runtime exports require careful operator handling; no guarantee of safe remote synchronization is made.
- Some module and upgrade endpoints express readiness indicators but do not replace threat modeling or production verification.
- UI and test coverage are incomplete; a green CI suite is not a penetration test.

Source code may be studied and improved under MIT. Deploy only in trusted local environments with synthetic/non-sensitive content.
