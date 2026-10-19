# Circle-Back R2: Evidence Drift Gate

**Local-only, read-only comparison. No new HTTP endpoint, worker or autonomous action.**

R1 lets an operator propose, approve or reject a next action and optionally attest to having completed work. R2 introduces **local evidence snapshots**, so the system can warn when a linked memory record was modified or became inaccessible after it was cited.

## What is stored

- When a proposal is created, TMC stores a canonical SHA-256 digest of each eligible, policy-visible source capsule in that local action record.
- At approval, those same source records must still be visible and have unchanged snapshots; otherwise the operator must create a fresh proposal.
- When an operator attests to completion, TMC records a fresh snapshot of its eligible completion-evidence capsules.
- Existing R1 actions have no stored snapshots. They remain readable, but are shown as `snapshot_unavailable` rather than implicitly trusted.

**This is an ordinary local change detector, not independent verification or cryptographic protection.** A user able to rewrite the SQLite database can rewrite both evidence and stored digests. Matching digests do not show that a memory was accurate, that work was completed, or that a proof was signed.

## CLI

```bash
python -m app.tools.circle_back_actions --db data/tmc.db check --action-id YOUR_ACTION_ID
```

The read-only check returns separate states for source and completion references:

| Value | Meaning |
| --- | --- |
| `unchanged_since_snapshot` | Every referenced capsule is visible and matches its local stored digest |
| `attention_required` | A reference changed or became unavailable, policy-hidden or outside the project scope |
| `snapshot_unavailable` | The action predates the snapshot mechanism or lacks a required stored digest |
| `not_applicable` | No references were supplied for that evidence category |

The overall result is `operator_recheck_required`, `consistent_with_local_snapshot`, or `no_evidence_snapshot`. `independent_verification` remains `false` for all of them.

The CLI report deliberately does not return raw capsule content, per-reference digests, inaccessible reference IDs, or counts that distinguish one hidden record from many.

## Safety limits

Only the active profile's project action can be checked. The same project, profile, unlocked-vault, persistent/non-private policy and unarchived rules apply. R2 checks the currently stored capsule state, not an externally authenticated origin, and does not monitor the user's source systems or GitHub automatically.

There is still no outer HTTP authentication boundary and no secure vault encryption in TMC. This feature should only be evaluated locally with non-sensitive demo data.

## R3 follow-up gate

R3 also rechecks original proposal-time source snapshots at **completion attestation**, not just at approval. If they no longer match, the action stays approved and requires operator review. The local [Review Board](CIRCLE_BACK_REVIEW_BOARD.md) summarizes these warnings alongside project suggestions.
