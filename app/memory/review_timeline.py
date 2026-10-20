"""R6: offline, bounded, historical Circle-Back review timeline.

Input is already policy-filtered, local R5 snapshot data. It is NOT a record
of independently verified real-world events, signed evidence, or completion.
This module neither writes storage nor runs a service or remote request.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

from app.memory.review_delta import _check_snapshot, _timestamp, compare_review_snapshots

MAX_TIMELINE_SNAPSHOTS = 12
PROJECT_CHANGE_FIELDS = {
    "project_name": "Project label",
    "review_signal": "Review priority",
    "visible_evidence_count": "Visible source count",
    "uncertain_visible_record_count": "Visible review flags",
    "operator_action_count": "Recorded action count",
}
ACTION_CHANGE_FIELDS = {
    "status": "Recorded action state",
    "evidence_review": "Local evidence state",
}

_CSS = """
:root{color-scheme:dark;--bg:#0c1220;--panel:#16243a;--surface:#1d3048;--line:#38506b;--ink:#f0f5fc;--muted:#adbed5;--mint:#97e0cc;--amber:#efc88b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,Segoe UI,Arial,sans-serif}
main{max-width:1050px;margin:auto;padding:36px 22px 70px}h1{font-size:clamp(2rem,5vw,3rem);line-height:1.15;margin:.4rem 0 1rem}h2{font-size:1.2rem}h3{font-size:1rem}
.eyebrow{font-size:.8rem;text-transform:uppercase;letter-spacing:.15em;color:var(--mint)}
.lead,.muted,footer{color:var(--muted)}.lead{max-width:800px}
.alert{background:var(--surface);border-left:4px solid var(--amber);padding:14px 18px;border-radius:6px;margin:18px 0}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin:25px 0}
.metric,.panel{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:19px}
.metric strong{display:block;font-size:1.65rem}.metric small{color:var(--muted)}
.timeline{list-style:none;padding:0 0 0 26px;margin:20px 0;border-left:2px solid var(--line)}
.timeline>li{position:relative;margin:0 0 20px;padding-left:20px}
.timeline>li:before{content:"";position:absolute;width:12px;height:12px;background:var(--mint);border:3px solid var(--bg);border-radius:50%;left:-34px;top:20px;box-sizing:content-box}
.panel h2{margin:0 0 .5rem}.interval{color:var(--mint);font-weight:600;overflow-wrap:anywhere}
.pills{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.pill{border:1px solid var(--line);padding:4px 10px;border-radius:999px;font-size:.8rem}
details{background:var(--surface);border:1px solid var(--line);border-radius:8px;margin-top:11px;padding:11px 14px}
summary{cursor:pointer;font-weight:650;overflow-wrap:anywhere}details p,details ul{margin:10px 0 4px}
.entry{padding:9px 0;border-top:1px solid var(--line);overflow-wrap:anywhere}
.entry:first-child{border:0}.value{color:var(--mint)}.warning{color:var(--amber)}
li{overflow-wrap:anywhere}footer{border-top:1px solid var(--line);padding-top:18px;font-size:.82rem;margin-top:25px}
@media print{body{background:#fff;color:#111}.metric,.panel,details,.alert{background:#fff;color:#111;border-color:#999}.muted,.lead,footer{color:#444}}
"""


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _display(value: object) -> str:
    return _e(str(value).replace("_", " "))


def build_review_timeline(snapshots: list[dict]) -> dict:
    """Make a compare-only timeline. No database access or side effects.

    An interval exists solely between adjacent snapshots. Every R5 comparison
    independently enforces identical profiles, strict scopes and incomplete
    coverage suppression; we also require a strictly increasing clock.
    """
    if not isinstance(snapshots, list) or not 2 <= len(snapshots) <= MAX_TIMELINE_SNAPSHOTS:
        raise ValueError("Timeline requires 2 through 12 local snapshots")
    for item in snapshots:
        _check_snapshot(item)
    timestamps = [_timestamp(item["generated_at"]) for item in snapshots]
    if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError("Timeline snapshots require strictly increasing timestamps")
    comparisons = [
        compare_review_snapshots(a, b)
        for a, b in zip(snapshots, snapshots[1:])
    ]
    return {
        "format": "tmc.circle_back.timeline.v1",
        "profile_id": snapshots[0]["profile_id"],
        "automatic_actions": False,
        "independently_verified": False,
        "snapshot_count": len(snapshots),
        "interval_count": len(comparisons),
        "intervals": comparisons,
        "caveat": (
            "Only locally observed review states were compared; no independent "
            "verification, proof of completion, or proof of project creation/deletion."
        ),
    }


def _changes(fields: dict, known: dict[str, str]) -> str:
    # Display only explicitly known comparison keys, not arbitrary injected
    # keys or unexpected fields from snapshot/delta objects.
    parts = []
    for key, title in known.items():
        row = fields.get(key)
        if isinstance(row, dict) and "before" in row and "after" in row:
            parts.append(
                '<li class="entry"><strong>' + _e(title) + '</strong>: '
                '<span class="muted">' + _display(row["before"]) + '</span> → '
                '<span class="value">' + _display(row["after"]) + '</span></li>'
            )
    return "<ul>" + "".join(parts) + "</ul>" if parts else ""


def render_review_timeline_html(timeline: dict) -> str:
    """Generate one static report with no scripts, links or network requests.

    Rendering is based only on whitelisted fields in the delta structure.
    Never render the entire serialized snapshot/delta object into HTML.
    """
    if not isinstance(timeline, dict) or timeline.get("format") != "tmc.circle_back.timeline.v1":
        raise ValueError("Expected an R6 Circle-Back timeline")
    if timeline.get("automatic_actions") is not False or timeline.get("independently_verified") is not False:
        raise ValueError("Timeline cannot claim automatic actions or verification")
    intervals = timeline.get("intervals")
    if not isinstance(intervals, list) or not 1 <= len(intervals) <= MAX_TIMELINE_SNAPSHOTS - 1:
        raise ValueError("Invalid bounded timeline intervals")
    if timeline.get("interval_count") != len(intervals) or timeline.get("snapshot_count") != len(intervals) + 1:
        raise ValueError("Inconsistent timeline lengths")
    cards = []
    partial_count = 0
    review_count = 0
    for idx, delta in enumerate(intervals, 1):
        if not isinstance(delta, dict) or delta.get("format") != "tmc.circle_back.delta.v1":
            raise ValueError("Invalid R5 comparison")
        if delta.get("automatic_actions") is not False or delta.get("independently_verified") is not False:
            raise ValueError("Invalid verification claim in comparison")
        if delta.get("profile_id") != timeline.get("profile_id"):
            raise ValueError("Timeline profile scope mismatch")
        projects = delta.get("project_deltas")
        if not isinstance(projects, list) or len(projects) > 100:
            raise ValueError("Unbounded project deltas")
        complete = delta.get("project_entry_exit_comparison") == "complete_for_visible_profile"
        if delta.get("project_entry_exit_comparison") not in (
            "complete_for_visible_profile", "suppressed_due_to_incomplete_project_coverage"
        ):
            raise ValueError("Unsupported comparison coverage status")
        if not complete:
            partial_count += 1
        review_count += len(projects)
        project_rows = []
        for project in projects:
            if not isinstance(project, dict):
                raise ValueError("Malformed project delta")
            details = _changes(project.get("changes", {}), PROJECT_CHANGE_FIELDS)
            actions = project.get("action_changes", [])
            if not isinstance(actions, list) or len(actions) > 16:
                raise ValueError("Unbounded action comparison")
            action_rows = []
            for action in actions:
                if not isinstance(action, dict):
                    raise ValueError("Malformed action comparison")
                observation = action.get("observation")
                if observation not in (None, "newly_listed", "no_longer_listed"):
                    raise ValueError("Unsupported action observation")
                text = _changes(action.get("changes", {}), ACTION_CHANGE_FIELDS)
                if observation:
                    text += "<p class=\"muted\">Observation: " + _display(observation) + "</p>"
                action_rows.append(
                    '<li class="entry">Action ' + _e(action.get("action_id", "")) + text + '</li>'
                )
            action_note = (
                '<p class="warning">Detailed action comparison suppressed: '
                'one of the local action previews was incomplete.</p>'
                if project.get("action_comparison") == "suppressed_due_to_action_preview_limit"
                else ""
            )
            if project.get("action_comparison") not in (
                "complete_for_listed_actions", "suppressed_due_to_action_preview_limit"
            ):
                raise ValueError("Unsupported action comparison coverage")
            project_rows.append(
                '<details><summary>' + _e(project.get("project_name", "")) +
                ' <span class="muted">(' + _e(project.get("project_id", "")) + ')</span></summary>'
                + details + ("<ul>" + "".join(action_rows) + "</ul>" if action_rows else "")
                + action_note + "</details>"
            )
        if not project_rows:
            project_rows.append(
                '<p class="muted">No comparable changes observed in shared listed projects.</p>'
            )
        added = delta.get("newly_listed_projects", [])
        missing = delta.get("no_longer_listed_projects", [])
        if not isinstance(added, list) or not isinstance(missing, list) or len(added) > 100 or len(missing) > 100:
            raise ValueError("Invalid project observations")
        if not complete and (added or missing):
            raise ValueError("Partial comparison cannot claim project entries or exits")
        listing = ""
        if complete and (added or missing):
            listing = '<details><summary>Project list observations</summary><p class="muted">Listed status is not proof of creation or deletion.</p>'
            if added:
                listing += '<p>Newly listed project IDs: ' + ", ".join(_e(a) for a in added) + '</p>'
            if missing:
                listing += '<p>No longer listed project IDs: ' + ", ".join(_e(a) for a in missing) + '</p>'
            listing += '</details>'
        notice = (
            '<p class="warning">Partial coverage: project additions and removals '
            'cannot be determined from these bounded views.</p>'
            if not complete else ""
        )
        cards.append(
            '<li><section class="panel"><span class="eyebrow">Comparison ' + str(idx) + '</span>'
            '<h2 class="interval">' + _e(delta.get("before_generated_at", "")) +
            ' → ' + _e(delta.get("after_generated_at", "")) + '</h2>'
            '<div class="pills"><span class="pill">Shared projects: ' +
            _e(delta.get("compared_projects", 0)) + '</span><span class="pill">Review entries: ' +
            str(len(projects)) + '</span></div>' + notice
            + "".join(project_rows) + listing + '</section></li>'
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="referrer" content="no-referrer">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        'connect-src \'none\'; script-src \'none\'; img-src \'none\'; '
        'font-src \'none\'; form-action \'none\'; base-uri \'none\'; '
        'style-src \'unsafe-inline\'">'
        '<title>TMC Circle-Back · Offline Change Timeline</title><style>' + _CSS +
        '</style></head><body><main><header><p class="eyebrow">Total Memory Core · R6</p>'
        '<h1>Circle-Back change timeline</h1><p class="lead">Locally recorded review changes '
        'across saved sessions. This does not prove work was completed, verified or deleted.</p></header>'
        '<aside class="alert"><strong>Private local report</strong>'
        '<p>Contains project names and local action IDs. Never upload, publish, or commit this file.</p>'
        '<p>No scripts, HTTP server, remote fonts, forms, or external assets.</p></aside>'
        '<section class="metrics" aria-label="Timeline metrics">'
        '<div class="metric"><strong>' + str(len(intervals) + 1) + '</strong><small>Snapshots</small></div>'
        '<div class="metric"><strong>' + str(len(intervals)) + '</strong><small>Intervals</small></div>'
        '<div class="metric"><strong>' + str(review_count) + '</strong><small>Review entries</small></div>'
        '<div class="metric"><strong>' + str(partial_count) + '</strong><small>Intervals with limited project coverage</small></div>'
        '</section><ol class="timeline" aria-label="Chronological review comparisons">'
        + "".join(cards) + '</ol>'
        '<footer>All changes describe local review state and visibility only. '
        'Snapshots are not signed, and operator attestation is not independent proof. '
        'TMC HTTP runtime remains local-only for non-sensitive evaluation.</footer>'
        '</main></body></html>'
    )
