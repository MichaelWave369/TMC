# Circle-Back R7: Local Focus Sessions

**One project, one intentional review, one recorded human decision.**

Circle-Back already provides a project review board, evidence drift checks, and an offline change timeline. R7 adds a small **operator-led focus session** to reduce the gap between looking at the review queue and making a deliberate choice.

## Local workflow

With TMC installed on a trusted machine and a **non-sensitive** local test database, first get a project ID from:

```powershell
python -m app.tools.circle_back_actions --db data/tmc.db review
```

Start an explicit session:

```powershell
python -m app.tools.circle_back_focus --db data/tmc.db start `
  --project-id "YOUR_PROJECT_ID" `
  --intent "Review the next test failure and decide what to tackle" `
  --confirm-local-operator
```

Copy the returned session ID. Each profile may have **one active focus session** at a time. Review locally using whatever evidence or tools are appropriate. TMC does **not** perform the review for you and does not start a timer or background job.

When ready, record a review decision:

```powershell
python -m app.tools.circle_back_focus --db data/tmc.db close `
  --session-id "YOUR_FOCUS_ID" `
  --decision needs_evidence `
  --note "Need a fresh local test run before deciding" `
  --confirm-local-operator
```

Supported outcomes:

- `revisit_later`: deliberately return to the project later.
- `needs_evidence`: additional evidence is required before choosing an action.
- `next_action_identified`: refer to an **existing** proposed or approved R1 action in the **same** project. Requires `--action-id "YOUR_ACTION_ID"`. It does *not* create, approve, reject, execute or attest that action.

To review the local records:

```powershell
python -m app.tools.circle_back_focus --db data/tmc.db list
python -m app.tools.circle_back_focus --db data/tmc.db history --session-id "YOUR_FOCUS_ID"
```

The `--confirm-local-operator` flag is an explicit CLI acknowledgment, **not authentication**. It is required for both start and close. Programmatic service methods are intended only for local trusted operator code.

## Integrity and isolation

Focus session records are scoped to the current profile, project ID and workspace. A different profile cannot view or close them. When linking an R1 action, the action must be in the same profile/project/workspace, and must not be rejected or already operator-attested.

Starting and closing a session are atomic SQLite transitions, each accompanied by a locally stored event. Competing starts in one profile and repeated or stale close attempts are rejected. Session history contains only locally recorded operator decisions. These SQLite records are **not signed, immutable, independently verified, or encrypted**.

R7 does not change existing next-action states. Closing a focus session is **not** completing a project. None of its outcomes claim independent verification, and neither the absence nor presence of an action proves that work happened.

## Privacy and deployment

Intent strings and notes may include sensitive information. **Use only synthetic or non-sensitive records.** Do not commit database files, publish CLI outputs, expose an HTTP service, or copy local histories into public reports. TMC's existing HTTP runtime lacks outer authentication and the legacy vault XOR is insecure. Remain on a trusted loopback machine with non-sensitive demo data.

R7 adds no HTTP API routes, network access, scheduler, model inference, or automation worker. Any future visual focus panel requires authentication, privacy review and additional tests.
