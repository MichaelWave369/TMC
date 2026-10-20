# Circle-Back R6: Offline Change Timeline

Circle-Back R5 saves **private local review snapshots** containing project names and local action IDs. R6 makes up to twelve of these into a **single offline, chronological HTML timeline**. It is a static personal report, not a live hosted site or independent audit.

## Quick start (Windows PowerShell)

Save at least two snapshots on different review visits. Copy each printed local file path:

```powershell
python -m app.tools.circle_back_delta snapshot --db data/tmc.db
```

Then build a timeline by passing the saved paths **oldest to newest**:

```powershell
python -m app.tools.circle_back_timeline `
  --snapshot "C:\\private\\review-1.json" `
  --snapshot "C:\\private\\review-2.json" `
  --snapshot "C:\\private\\review-3.json"
```

You can supply **2 to 12 snapshots** and optionally `--output "C:\\private\\timeline.circle-back.html"`. Without an output argument, TMC creates a new private temporary folder and prints the resulting HTML file path. **Open that file directly in a browser.** No `uvicorn`, network port, server, JavaScript, account login or external content is needed.

R6 checks all inputs before creating an output. Invalid snapshots, different profiles, duplicate file paths, nonincreasing timestamps, or unsupported "verified" status claims are rejected. Existing output files and symlinks are never overwritten. The HTML destination must resolve outside the source repository. POSIX reports use owner-only file permissions; Windows file access depends on your account/folder ACLs.

## What the timeline shows

- Each interval between neighboring snapshots, ordered chronologically.
- Project review-signal and policy-visible evidence-count changes.
- Observed operator action status and aggregate evidence-warning changes.
- Newly listed and no-longer-listed project IDs **only when both snapshots had complete project coverage**.
- A warning when either review was limited to 100 projects or omitted some cards; action details are withheld when either action preview was truncated.

Use native expand/collapse controls to inspect each project's changes. All dynamic text is HTML-escaped and a restrictive Content Security Policy blocks scripts, resource loading and network connections. The report has no dynamic remote functionality.

## Private by design

Both input snapshots and the output timeline contain **project names, IDs and sometimes operator action IDs**. These may still be sensitive. They do **not** contain raw capsule text, operator notes, supporting source capsule IDs, paths or stored content digests.

**Do not commit or publish any generated snapshot or timeline.** Do not add them to GitHub Pages, public issues, or a shared web server. Delete local exports when no longer needed. Keep the existing TMC API bound to trusted loopback only, and use non-sensitive demo data: it still lacks outer authentication and has an insecure legacy XOR vault scheme.

This timeline is **a comparison of locally stored review states**, not proof that anything was created, deleted, corrected or independently completed. A change in an operator-attested status remains a human report, not independent verification.
