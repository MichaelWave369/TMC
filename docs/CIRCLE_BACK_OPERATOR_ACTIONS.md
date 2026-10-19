# Circle-Back R1: Operator Decisions

Circle-Back v0 generates **local suggestions** for projects. R1 adds optional, locally stored next-action proposals with explicit operator decisions.

These records are **not** evidence that a project's work has actually been performed or independently verified. They are operator workflow notes with policy-scoped capsule-ID pointers.

## State machine

`proposed → approved → operator_attested` or `proposed → rejected`.

- **Proposed**: operator requests a proposed action attached to an active-profile project. Optional evidence capsule IDs must belong to that project and remain policy-visible.
- **Approved/rejected**: requires an explicit local operator CLI decision. Proposals do not auto-approve, launch jobs or synchronize.
- **Operator attested**: requires prior approval, at least one still-visible capsule ID linked to that project and an operator note. The attestation is **a human claim, not independently verified completion**.
- Rejected and attested records are terminal in R1.
- Transitions create separate locally stored SQLite event rows, atomically with the status change. They are **not signed or tamper-proof**; anyone with database write access may alter them.

## Local CLI examples

Run from the repository root after `python -m pip install -e ".[dev]"`:

```bash
python -m app.tools.circle_back_preview --db data/tmc.db
python -m app.tools.circle_back_actions --db data/tmc.db list
python -m app.tools.circle_back_actions --db data/tmc.db propose \
  --project-id YOUR_PROJECT_ID --title "Review a real next step" \
  --source YOUR_CAPSULE_ID --confirm-local-operator
python -m app.tools.circle_back_actions --db data/tmc.db approve \
  --action-id YOUR_ACTION_ID --note "Reviewed locally" --confirm-local-operator
python -m app.tools.circle_back_actions --db data/tmc.db attest \
  --action-id YOUR_ACTION_ID --evidence YOUR_CAPSULE_ID \
  --note "I checked this locally; independent verification remains pending" \
  --confirm-local-operator
python -m app.tools.circle_back_actions --db data/tmc.db history --action-id YOUR_ACTION_ID
```

Use the returned IDs from a proposal or preview, not invented sample IDs. An operator must consciously type `--confirm-local-operator` for mutations; **this is not authentication**.

## Scoping and evidence limitations

Only the active profile's project actions are visible. Evidence pointers are accepted only for that active profile, linked project workspace, persistent non-private policy, unarchived/unsuperseded capsule, unlocked vault, and successful policy engine retrieval. Approval re-checks evidence visibility. Completion attestation requires a new explicit evidence check. If evidence becomes policy-hidden, returned action lists and history redact its IDs.

R1 stores no raw capsule text and creates no new HTTP route. Action titles and operator notes are locally persisted and may still be sensitive; enter only synthetic or non-sensitive content. Local SQLite records are **not cryptographically verified**, and existing TMC vault encryption is not secure. The unauthenticated TMC HTTP runtime remains loopback-only.

## Next safety work

Full authenticated operator identities, durable evidence attestations, tamper-evident receipts, project lifecycle reconciliation, consent-based schedule integration and audited local encryption require separate designs/tests before remote or production use.

## R2: Evidence drift

See [the Evidence Drift Gate](CIRCLE_BACK_EVIDENCE_DRIFT.md) for local capsule snapshot comparisons, changed-source approval blocking, and the read-only `check` CLI command. Matches are not independent proof of truth or task completion.
