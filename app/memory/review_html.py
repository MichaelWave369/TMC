"""Offline HTML renderer for the existing, policy-filtered Circle-Back R3 board.

No HTTP, scripts, external fonts/assets, remote URLs, model calls, or state
mutations. The rendered file still contains local project/action metadata
and should not be published or uploaded.
"""
from __future__ import annotations

from html import escape

EXPECTED_MODE = "local_read_only_review_board"

_CSS = """
:root{color-scheme:dark;--bg:#0d1320;--panel:#172234;--line:#35445b;--text:#eff4fb;--muted:#b0bdd0;--accent:#8ed9c5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,Arial,sans-serif}
.wrap{max-width:1060px;margin:0 auto;padding:38px 22px 60px}
header{border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:22px}
.eyebrow{font-size:.8rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}
h1{font-size:clamp(1.8rem,4.5vw,3rem);line-height:1.1;margin:.3rem 0 1rem}
.lead{max-width:800px;color:var(--muted);margin:0}
.notice{background:#203049;border-left:4px solid var(--accent);padding:14px 18px;border-radius:5px;margin:20px 0}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:20px 0 24px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.stat strong{font-size:1.55rem;display:block}.stat span{color:var(--muted);font-size:.8rem}
.board{display:grid;gap:14px}.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:22px}
.card h2{font-size:1.22rem;margin:0 0 5px;overflow-wrap:anywhere}
.signal{display:inline-block;color:var(--accent);font-size:.78rem;font-weight:700;letter-spacing:.045em;text-transform:uppercase}
.step{font-size:.94rem;color:var(--text);margin:8px 0 12px}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}.pill{border:1px solid var(--line);border-radius:999px;padding:4px 10px;color:var(--muted);font-size:.79rem}
.small{color:var(--muted);font-size:.8rem;overflow-wrap:anywhere}ul{padding-left:20px}li{margin:6px 0;overflow-wrap:anywhere}
.action{border-top:1px solid var(--line);padding-top:9px;margin-top:9px}
footer{border-top:1px solid var(--line);margin-top:30px;padding-top:18px;color:var(--muted);font-size:.78rem}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
@media print{body{color:#111;background:white}.card,.stat,.notice{background:white;color:#111;border-color:#777}.small,.lead,.pill,footer{color:#444}}
"""


def _escape(value: object) -> str:
    return escape(str(value), quote=True)


def _label(value: object) -> str:
    return _escape(str(value).replace("_", " ").capitalize())


def render_review_board_html(board: dict) -> str:
    """Render only known, sanitized board fields as fully offline static HTML.

    This rejects unexpected input modes, as well as any suggestion that an
    automated action or independent verification was performed.
    """
    if not isinstance(board, dict) or board.get("mode") != EXPECTED_MODE:
        raise ValueError("Expected a local read-only Circle-Back review board")
    if board.get("auto_actions") is not False or board.get("independent_verification") is not False:
        raise ValueError("Cannot display a board claiming auto-actions or verification")
    cards = board.get("cards")
    if not isinstance(cards, list) or len(cards) > 100:
        raise ValueError("Board cards must be a bounded list")

    count = len(cards)
    summary = (
        '<div class="stats">'
        f'<div class="stat"><strong>{_escape(board.get("total_projects", 0))}</strong><span>Registered projects</span></div>'
        f'<div class="stat"><strong>{_escape(board.get("projects_considered", 0))}</strong><span>Projects considered</span></div>'
        f'<div class="stat"><strong>{count}</strong><span>Cards displayed</span></div>'
        '</div>'
    )
    warnings = []
    if board.get("coverage_complete") is not True:
        warnings.append("Coverage incomplete: the underlying queue considered at most 100 projects.")
    if board.get("cards_truncated") is True:
        warnings.append("Result limit reached: some considered projects are not displayed.")
    if not warnings:
        warnings.append("Coverage flags indicate all registered projects were considered and the cards are untruncated.")
    notices = "".join(f'<p>{_escape(w)}</p>' for w in warnings)

    blocks = []
    for index, card in enumerate(cards, 1):
        if not isinstance(card, dict):
            raise ValueError("A project card is not an object")
        actions = card.get("operator_actions", [])
        if not isinstance(actions, list) or len(actions) > 8:
            raise ValueError("Action preview must be bounded")
        action_rows = []
        for action in actions:
            if not isinstance(action, dict):
                raise ValueError("An action row is not an object")
            action_rows.append(
                '<li class="action">'
                f'<strong>{_label(action.get("status", "unknown"))}</strong> '
                f'<span class="small">Action {_escape(action.get("action_id", ""))}</span>'
                '<div class="small">'
                f'Evidence: {_label(action.get("evidence_review", "not_assessed"))} · '
                f'Updated: {_escape(action.get("updated_at", "unknown"))}'
                '</div></li>'
            )
        action_list = (
            '<ul aria-label="Operator action states">' + "".join(action_rows) + '</ul>'
            if action_rows else '<p class="small">No local operator actions recorded.</p>'
        )
        if card.get("operator_actions_truncated") is True:
            action_list += '<p class="small">Additional operator actions omitted by the 8-action preview limit.</p>'
        blocks.append(
            '<article class="card">'
            f'<span class="signal">Review {index} · {_label(card.get("review_signal", "general_project_review"))}</span>'
            f'<h2>{_escape(card.get("project_name", "Unnamed project"))}</h2>'
            f'<p class="small">Project {_escape(card.get("project_id", ""))} · Workspace {_escape(card.get("workspace_id", ""))}</p>'
            f'<p class="step">{_escape(card.get("suggested_operator_step", ""))}</p>'
            '<div class="meta">'
            f'<span class="pill">Visible sources: {_escape(card.get("visible_evidence_count", 0))}</span>'
            f'<span class="pill">Review flags: {_escape(card.get("uncertain_visible_record_count", 0))}</span>'
            f'<span class="pill">Recorded actions: {_escape(card.get("operator_action_count", 0))}</span>'
            f'<span class="pill">Visible context age: {_escape(card.get("days_since_visible_activity", 0))} days</span>'
            '</div>'
            '<p class="small">Attestations are operator assertions, not independently verified completion.</p>'
            + action_list + '</article>'
        )
    if not blocks:
        blocks.append('<div class="card"><h2>No project cards available</h2><p class="small">Nothing was selected for this local review.</p></div>')

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="referrer" content="no-referrer">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        'connect-src \'none\'; script-src \'none\'; img-src \'none\'; '
        'font-src \'none\'; form-action \'none\'; base-uri \'none\'; '
        'style-src \'unsafe-inline\'">'
        '<title>TMC · Circle-Back Offline Review</title>'
        f'<style>{_CSS}</style></head><body><main class="wrap">'
        '<header><div class="eyebrow">Total Memory Core · Circle-Back R4</div>'
        '<h1>Local project review board</h1>'
        '<p class="lead">One-time, static operator review generated from local memory. '
        'This page cannot fetch new data, approve actions, or verify task completion.</p></header>'
        '<aside class="notice" aria-label="Privacy and coverage warnings">'
        '<strong>Private local report</strong>'
        '<p>This file may contain your project names and local IDs. Do not upload, share or commit it.</p>'
        + notices + '</aside>'
        + summary
        + f'<p class="small">Generated at {_escape(board.get("generated_at", "unknown"))}. '
        'No remote calls, scripts, or network-backed assets.</p>'
        '<section class="board" aria-label="Project review cards">'
        + "".join(blocks) + '</section>'
        '<footer>Read-only preview. No independent verification, automatic decisions, or signed evidence. '
        'Keep the TMC HTTP runtime on trusted loopback only with non-sensitive data.</footer>'
        '</main></body></html>'
    )
