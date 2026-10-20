"""R7 focus sessions: operator-controlled, scoped, atomic, never completion."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.service import MemoryService
from app.memory.models import FocusSessionStatus, FocusReviewDecision
from app.tools.circle_back_focus import build_parser


def setup(tmp_path):
    path = str(tmp_path / "focus.db")
    svc = MemoryService(path)
    p = svc.create_project("focus-workspace", "Synthetic Focus Project")
    return svc, p, path


def open_session(svc, project):
    return svc.start_focus_session(project.id, "Review one synthetic next step")


def test_start_creates_active_session_with_explicit_intent_and_event(tmp_path):
    svc, project, _ = setup(tmp_path)
    audits = len(svc.store.get_audits())
    jobs = len(svc.list_jobs())
    row = open_session(svc, project)
    assert row["status"] == "active"
    assert row["decision"] is None
    assert row["intent"] == "Review one synthetic next step"
    assert row["completion_verified"] is False
    assert row["automatic_actions"] is False
    assert row["profile_id"] == svc.active_profile_id
    assert row["project_id"] == project.id
    assert [x["transition"] for x in svc.focus_session_history(row["id"])] == ["started"]
    assert len(svc.store.get_audits()) == audits
    assert len(svc.list_jobs()) == jobs


def test_only_one_active_session_per_profile(tmp_path):
    svc, project, _ = setup(tmp_path)
    open_session(svc, project)
    with pytest.raises(ValueError, match="already active"):
        open_session(svc, project)
    assert len([s for s in svc.store.get_focus_sessions() if s.status == FocusSessionStatus.active]) == 1


def test_atomic_competing_focus_starts_use_sqlite_guard(tmp_path):
    svc, project, db = setup(tmp_path)
    def start_again(_):
        other = MemoryService(db)
        try:
            return ("ok", other.start_focus_session(project.id, "Synthetic focus")["id"])
        except ValueError as exc:
            return ("error", str(exc))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(start_again, range(2)))
    assert sorted(x[0] for x in results) == ["error", "ok"]
    assert len([x for x in svc.store.get_focus_sessions() if x.status == FocusSessionStatus.active]) == 1


@pytest.mark.parametrize("decision", [
    "revisit_later", "needs_evidence",
])
def test_close_writes_operator_choice_without_mutating_actions(tmp_path, decision):
    svc, project, _ = setup(tmp_path)
    previous_audits = len(svc.store.get_audits())
    session = open_session(svc, project)
    action = svc.propose_next_action(project.id, "Synthetic next action")
    before_action = svc.store.get_next_action(action["id"]).model_dump(mode="json")
    result = svc.close_focus_session(session["id"], decision, "Review was recorded")
    assert result["status"] == "closed"
    assert result["decision"] == decision
    assert result["closed_at"] is not None
    assert result["completion_verified"] is False
    assert result["automatic_actions"] is False
    assert svc.store.get_next_action(action["id"]).model_dump(mode="json") == before_action
    assert [x["transition"] for x in svc.focus_session_history(session["id"])] == ["started", "closed"]
    assert len(svc.store.get_audits()) == previous_audits


def test_next_action_link_is_existing_same_project_and_not_approved(tmp_path):
    svc, project, _ = setup(tmp_path)
    action = svc.propose_next_action(project.id, "Operator may look at this")
    session = open_session(svc, project)
    result = svc.close_focus_session(
        session["id"], "next_action_identified", "Look at the proposed task", action["id"]
    )
    assert result["decision"] == "next_action_identified"
    assert result["linked_action_id"] == action["id"]
    assert svc.store.get_next_action(action["id"]).status.value == "proposed"
    assert svc.focus_session_history(session["id"])[-1]["linked_action_id"] == action["id"]


def test_close_does_not_allow_unlinked_next_action_identified(tmp_path):
    svc, project, _ = setup(tmp_path)
    s = open_session(svc, project)
    with pytest.raises(ValueError, match="existing next-action"):
        svc.close_focus_session(s["id"], "next_action_identified", "Need real next action")
    assert svc.store.get_focus_session(s["id"]).status.value == "active"
    assert len(svc.focus_session_history(s["id"])) == 1


def test_cross_project_action_reference_is_rejected(tmp_path):
    svc, p, _ = setup(tmp_path)
    other = svc.create_project("other-workspace", "Another")
    action = svc.propose_next_action(other.id, "Different project action")
    s = open_session(svc, p)
    with pytest.raises(ValueError, match="outside the focus project"):
        svc.close_focus_session(s["id"], "next_action_identified", "Incorrect project", action["id"])
    assert svc.store.get_focus_session(s["id"]).status.value == "active"


def test_rejected_and_operator_attested_links_are_rejected(tmp_path):
    svc, project, _ = setup(tmp_path)
    rejected = svc.propose_next_action(project.id, "Rejected")
    svc.decide_next_action(rejected["id"], False)
    session = open_session(svc, project)
    with pytest.raises(ValueError, match="not available for future review"):
        svc.close_focus_session(session["id"], "next_action_identified", "Blocked choice", rejected["id"])
    action = svc.propose_next_action(project.id, "Attested")
    svc.decide_next_action(action["id"], True)
    # Evidence is required to attest, but a previously attested task must not
    # be presented as another fresh next-action link.
    from app.memory.models import IngestRequest
    cap = svc.ingest_text(IngestRequest(
        source_type="test", source_ref="synthetic",
        text="Synthetic note", workspace_ids=[project.workspace_id],
    ))[0]
    svc.attest_next_action_done(action["id"], [cap.id], "I checked locally")
    with pytest.raises(ValueError, match="not available for future review"):
        svc.close_focus_session(session["id"], "next_action_identified", "Blocked choice", action["id"])


def test_unexpected_link_for_other_decision_is_rejected(tmp_path):
    svc, p, _ = setup(tmp_path)
    s = open_session(svc, p)
    with pytest.raises(ValueError, match="only allowed"):
        svc.close_focus_session(s["id"], "needs_evidence", "Need another check", "fake-action")


@pytest.mark.parametrize("invalid", ["done", "verified", "complete", "auto_execute", "", None])
def test_unsupported_outcomes_cannot_claim_completion(tmp_path, invalid):
    svc, p, _ = setup(tmp_path)
    s = open_session(svc, p)
    with pytest.raises(ValueError, match="Unsupported"):
        svc.close_focus_session(s["id"], invalid, "A note")
    assert len(svc.focus_session_history(s["id"])) == 1


def test_second_close_is_rejected_and_no_duplicate_event(tmp_path):
    svc, p, _ = setup(tmp_path)
    s = open_session(svc, p)
    svc.close_focus_session(s["id"], "revisit_later", "Return another day")
    with pytest.raises(ValueError, match="Only active"):
        svc.close_focus_session(s["id"], "needs_evidence", "No second close")
    assert len(svc.focus_session_history(s["id"])) == 2


def test_stale_transition_guard_prevents_writes(tmp_path):
    svc, p, _ = setup(tmp_path)
    s = open_session(svc, p)
    old = svc.store.get_focus_session(s["id"])
    old.status = FocusSessionStatus.closed
    old.decision = FocusReviewDecision.needs_evidence
    from app.memory.models import FocusSessionEvent
    event = FocusSessionEvent(
        session_id=s["id"], profile_id=svc.active_profile_id,
        transition="closed", decision="needs_evidence",
    )
    with pytest.raises(ValueError, match="Stale"):
        svc.store.save_focus_transition(old, event, expected_status="closed")
    assert len(svc.focus_session_history(s["id"])) == 1


def test_one_active_session_per_profile_not_globally(tmp_path):
    svc, p, _ = setup(tmp_path)
    original = open_session(svc, p)
    second_profile = svc.create_profile("Second operator", "vault-default")
    svc.switch_profile(second_profile.profile_id)
    other_project = svc.create_project("second-focus-workspace", "Other synthetic project")
    second_session = open_session(svc, other_project)
    assert original["profile_id"] != second_session["profile_id"]
    assert len(svc.list_focus_sessions()["sessions"]) == 1
    assert svc.list_focus_sessions()["sessions"][0]["id"] == second_session["id"]


def test_cross_profile_session_close_history_and_project_are_hidden(tmp_path):
    svc, p, _ = setup(tmp_path)
    owned = open_session(svc, p)
    other = svc.create_profile("Second profile", "vault-default")
    svc.switch_profile(other.profile_id)
    assert owned["id"] not in str(svc.list_focus_sessions())
    with pytest.raises(ValueError, match="not available"):
        svc.focus_session_history(owned["id"])
    with pytest.raises(ValueError, match="not available"):
        svc.close_focus_session(owned["id"], "needs_evidence", "Not my session")
    with pytest.raises(ValueError, match="Project is not available"):
        svc.start_focus_session(p.id, "Not my project")


def test_unknown_session_and_missing_project_not_disclosed(tmp_path):
    svc, p, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="not available"):
        svc.focus_session_history("unknown-focus")
    session = open_session(svc, p)
    with svc.store._connect() as conn:
        conn.execute("DELETE FROM projects WHERE id=?", (p.id,))
    with pytest.raises(ValueError, match="Project is not available"):
        svc.close_focus_session(session["id"], "revisit_later", "Project removed")
    assert svc.list_focus_sessions()["sessions"] == []


def test_input_limits_are_enforced_without_write(tmp_path):
    svc, p, _ = setup(tmp_path)
    for intent in (" ", "x" * 201, 3):
        with pytest.raises(ValueError):
            svc.start_focus_session(p.id, intent)
    assert svc.store.get_focus_sessions() == []
    s = open_session(svc, p)
    for note in ("", " ", "a" * 501):
        with pytest.raises(ValueError):
            svc.close_focus_session(s["id"], "revisit_later", note)
    assert len(svc.focus_session_history(s["id"])) == 1


def test_list_order_limit_and_nonmutating_behavior(tmp_path):
    svc, p, db = setup(tmp_path)
    first = open_session(svc, p)
    svc.close_focus_session(first["id"], "revisit_later", "Not today")
    second = open_session(svc, p)
    audits = len(svc.store.get_audits())
    count = len(svc.focus_session_history(second["id"]))
    result = svc.list_focus_sessions(limit=1)
    assert result["truncated"] is True
    assert result["total_sessions"] == 2
    assert len(result["sessions"]) == 1
    assert result["sessions"][0]["id"] == second["id"]
    assert result["completion_verified"] is False
    assert result["automatic_actions"] is False
    assert svc.list_focus_sessions(limit=1) == result
    assert len(svc.store.get_audits()) == audits
    assert len(svc.focus_session_history(second["id"])) == count
    # Session and its decision survive a service restart.
    restarted = MemoryService(db)
    assert len(restarted.list_focus_sessions()["sessions"]) == 2


@pytest.mark.parametrize("limit", [0, 101, True, "2"])
def test_list_rejects_out_of_bounds(tmp_path, limit):
    svc, _, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="limit"):
        svc.list_focus_sessions(limit=limit)


def test_cli_requires_explicit_operator_acknowledgment():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["start", "--project-id", "p", "--intent", "Review"])
    with pytest.raises(SystemExit):
        parser.parse_args(["close", "--session-id", "s", "--decision", "revisit_later", "--note", "reviewed"])
    parsed = parser.parse_args([
        "--db", "local.db", "start", "--project-id", "p",
        "--intent", "Review locally", "--confirm-local-operator",
    ])
    assert parsed.confirm_local_operator is True
    close = parser.parse_args([
        "--db", "local.db", "close", "--session-id", "s",
        "--decision", "next_action_identified", "--note", "Look up task",
        "--action-id", "a", "--confirm-local-operator",
    ])
    assert close.decision == "next_action_identified"
    assert close.action_id == "a"


def test_local_only_focus_cli_does_not_accept_http_flags():
    parser = build_parser()
    for arguments in (
        ["list", "--url", "https://example.com"],
        ["start", "--project-id", "x", "--intent", "Review", "--network"],
    ):
        with pytest.raises(SystemExit):
            parser.parse_args(arguments)
