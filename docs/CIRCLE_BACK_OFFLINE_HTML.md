# Circle-Back R4: Offline Visual Review

R4 gives the existing R3 Circle-Back review board a visual, static HTML format that you can open in a local browser **without running a web server**.

It is a one-time snapshot, not a live dashboard. It cannot poll for changes, run actions, approve tasks or attest completion, and it does not assert independent verification. Refresh it by explicitly rerunning the command.

## Try it

Install TMC locally and use a **non-sensitive evaluation database**.

```bash
python -m pip install -e ".[dev]"
python -m app.tools.circle_back_html --db data/tmc.db --limit 20 --stale-days 30
```

The command prints a file path such as `/tmp/tmc-circle-back-.../review.html`. Open it directly in your browser, with no `uvicorn` or local network port. The default destination is a temporary **owner-only directory**; the file is owner-readable/writable on POSIX systems. The browser does not need network access.

For a chosen location, use an **unused path outside the checked-out TMC repository**, for example:

```bash
python -m app.tools.circle_back_html --db data/tmc.db --output ../private-review.circle-back.html
```

The tool refuses existing filenames, symlink destinations, and explicit destinations resolving inside the source checkout. It never overwrites a report. The parent directory must already exist.

## What you see

- Project names, workspace IDs, and project IDs.
- Read-only review priority and suggested human next step.
- Visible memory counts, review flags and staleness age.
- Local operator action IDs and their states, including aggregate evidence-drift signals.
- Explicit warnings if only 100 projects were considered, or the chosen output limit hides some cards.

The HTML intentionally **does not include** capsule bodies, raw evidence IDs, action titles, rationales, completion notes, source paths, stored fingerprints, embedded data blobs or network fetch URLs. It uses HTML escaping for every dynamic field, includes a restrictive Content Security Policy, and loads no external scripts, fonts, images or CSS.

## Privacy and limits

**The report still contains local project names and IDs. Treat it as private data.** Do not commit it, attach it to issues, email it, put it on GitHub Pages, sync it to a public share, or upload it to a remote renderer. Remove the temporary file when no longer needed. On some platforms, file permissions and backup/indexing behavior differ from POSIX; protect the folder with your OS account permissions.

R4 does not introduce an API endpoint or work around TMC's missing outer HTTP authentication and insecure legacy vault XOR. Never expose the existing service beyond trusted loopback. Matching local evidence digests does not establish factual truth or completion.

TMC service startup may initialize defaults or seed **synthetic** local memory records; the review/rendering calls themselves are read-only.
