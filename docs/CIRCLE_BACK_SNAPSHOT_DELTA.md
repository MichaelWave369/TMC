# Circle-Back R5: What Changed Since Last Visit?

R5 compares **two saved local Circle-Back review snapshots**. It helps an operator notice changed review signals, action states, or evidence warnings, without treating a difference as verified progress, project deletion, or real-world truth.

## Local commands

From the checked-out TMC repository, after installing the Python dependencies:

```bash
# Save today's private, local, minimal review snapshot
python -m app.tools.circle_back_delta snapshot --db data/tmc.db

# Repeat on a later day, recording the TWO printed private paths
python -m app.tools.circle_back_delta snapshot --db data/tmc.db

# Compare the earlier file with the later file
python -m app.tools.circle_back_delta compare --before "/path/to/older/snapshot.json" --after "/path/to/newer/snapshot.json"
```

By default, each operation creates a **new private temporary directory** and a new `.json` file, and prints only its local path and a modest count summary. You can instead specify an unused file path outside the TMC source tree with `--output /your/private/location/review-2026-10-19.json`.

**Do not commit, upload, share, or GitHub Pages-host either snapshot or diff.** Although they don't include raw capsule bodies, they do include local project names, workspace/project IDs, and operator action IDs, and thus remain private operator data. Each file is created without overwriting an existing destination. The CLI refuses output inside the source tree and rejects final symlink destinations. On POSIX it uses owner-only files (mode `0600`); OS protections vary on Windows.

## What is compared?

For each project present in **both** snapshots, R5 compares review signal, project display name, counts of policy-visible memory and uncertainty flags, and local operator action counts. When both snapshots include full action previews, it also compares visible action statuses and aggregate drift warnings.

Snapshots are whitelisted from R3's **already policy-filtered** review board. No raw memory text, source capsule IDs, file paths, operator note text, action titles, or stored fingerprints are copied into the snapshot. Each new snapshot contains at most 100 reviewed projects and at most eight actions per project.

If **either** snapshot has incomplete project coverage or truncated cards, R5 deliberately **suppresses all claims that a project newly appeared or disappeared**. If either project action preview is truncated, detailed action-state comparisons for that project are suppressed and reported as limited.

The snapshot format is `tmc.circle_back.snapshot.v1`. Each file must have the same active profile ID, valid time offsets, a chronological order, unique project/action IDs, and internally consistent coverage flags. Deliberately unsupported formats or cross-profile comparisons fail closed.

## What R5 does not claim

R5 **does not** establish that a project was built, a defect was fixed, a task was completed, a source was truthful, or a disappeared project was deleted. A match or change reflects **locally recorded and currently visible review state** only. Neither file is cryptographically signed or tamper-proof. Both may be manually edited by someone who can access the local filesystem.

No HTTP endpoint, browser upload, remote connection, model call, background monitoring, or automatic action is added. The existing TMC API remains unauthenticated and local-loopback-only, and the old vault XOR scheme is not secure encryption.

## Optional next rung

A future entirely offline visual *change timeline* could render the resulting private delta JSON to a local HTML page, following R4's same no-network boundary.
