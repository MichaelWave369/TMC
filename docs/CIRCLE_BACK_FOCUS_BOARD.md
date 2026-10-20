# Circle-Back R8: Focus Sessions in the Offline Review Board

R8 adds a **read-only Focus Session section** to each project card in the local offline Circle-Back HTML board. It extends the existing R4 visual view without adding an HTTP endpoint, cloud API, scheduler, or automatic decisions.

## Try it (local PowerShell)

```powershell
python -m app.tools.circle_back_html --db data/tmc.db
```

Open the printed private `.html` file path directly in your browser. It contains local project names and IDs, review signals, and now the **three most recent** Focus Session summaries for each displayed project.

The focus section shows:

- Active or closed human review status.
- Local focus session ID and start timestamp.
- A supported operator review decision, if the session is closed.
- Count of focus sessions attached to the displayed project, with an explicit truncation warning when older sessions are hidden.

**The HTML deliberately omits** focus intent, human note text, linked next-action IDs, raw memory text, source capsule IDs, stored hashes and full session events. Every dynamic value is HTML-escaped; CSP continues to prohibit JavaScript and network/resource loads.

To generate the previous board without focus summaries:

```powershell
python -m app.tools.circle_back_html --db data/tmc.db --without-focus
```

## Important boundaries

- Focus rows are included **only** when their project and workspace appear among the active profile's *displayed* R3 review cards. If the board is truncated, hidden project sessions stay off the page.
- An active review means a local operator has opened a session. A closed review means a person recorded a decision. **Neither indicates the project or its tasks have been completed or independently verified.**
- The R3 review model and the R5/R6 snapshot/delta/timeline formats have not been extended or changed by the focus overlay. Saved review snapshots **do not silently start containing focus metadata**.
- R8 reads existing sessions; it never creates or closes one, approves actions, or updates the SQLite event history.
- Existing output protections remain: private new local HTML file, refusal to overwrite or save inside checked-out source code. Do not publish, upload, share, commit or GitHub Pages-host generated reports.

TMC still has no verified outer HTTP authentication and its legacy vault XOR is not secure encryption. Run only on trusted loopback with non-sensitive demo data. The local CLI confirmation flags are not authentication.
