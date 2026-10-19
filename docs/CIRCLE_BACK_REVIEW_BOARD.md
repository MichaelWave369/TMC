# Circle-Back R3: Local Review Board

**Status:** local, read-only review preview. No HTTP endpoint, autonomous agent, background job, or independent verification.

R3 combines the existing project rediscovery signals, locally recorded action states and aggregate evidence-change status into **one ranked, operator-reviewable queue**. It does not inspect GitHub, merge code, connect to third-party services, or automatically mark anything complete.

## Run locally

From the TMC project root after installing `.[dev]`:

```bash
python -m app.tools.circle_back_actions --db data/tmc.db review --limit 20 --stale-days 30
```

The command reads the TMC local database. Note that *MemoryService startup* may create local defaults and load **synthetic seed records** into a fresh database; the **review-board method itself** creates no records and launches no tasks. Do not redirect results to public CI logs when using private local memory.

## Ranking logic

The board prioritizes projects in this order:

1. **Evidence recheck required:** a non-rejected action cites changed, unavailable, policy-hidden or unsnapshotted records.
2. **Operator decision needed:** a proposal is waiting for explicit approve/reject.
3. **Approved follow-up needed:** approved work awaits operator review; this is not a job that TMC runs.
4. **Memory review needed:** linked policy-visible capsules are marked uncertain, pending review, or conflicting.
5. **Attach source review:** no eligible visible records support the project.
6. **Stale context review:** latest visible project/capsule update is older than the chosen threshold.
7. **General review**, followed by **operator-attested (not independently verified)** records.

The board includes each project's memory signal, visible-source count, a compact list of operator action IDs/states, and a suggested *human* next step.

It **never returns raw capsule text, source paths, action titles, rationales, operator notes, stored digests, or hidden record IDs**. It only considers project/action records belonging to the active profile and checks actions through R2's policy-scoped evidence reconciliation.

## Bounded coverage

R3 uses the existing Circle-Back v0 ranked preview of **at most 100 projects**. `coverage_complete=false` explicitly warns when there are more projects than the first 100 considered. The output separately indicates when the requested result limit truncates cards or when more than eight actions exist on a displayed card. Summary counts refer only to projects **considered**, not all projects when coverage is incomplete.

## New R3 attestation safeguard

Prior R2 approval blocked proposals whose *source evidence* had changed before approval. R3 also checks those same proposal-time source snapshots **again when an approved action is attested complete**. If source evidence has become unavailable or changed since approval, completion attestation is rejected with no new transition event. Missing snapshots from old records require a fresh proposal rather than being silently accepted.

The check uses ordinary SHA-256 digests of locally stored records. They are not signed, immutable, independent proof, or a guarantee against races or intentional database modification. Matching a snapshot does not establish truth or completion.

## Security boundaries

TMC's HTTP service has no verified outer authentication boundary and its legacy vault XOR is not secure encryption. Use only on a trusted loopback interface with non-sensitive demonstration data. A public GitHub repository is **not** permission to host the service publicly.
