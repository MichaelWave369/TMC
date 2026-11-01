"""R0 positive and negative controls. Never includes real operator memory."""
from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from app.memory.models import Capsule, CapsuleStatus, PolicyMode
from app.memory.polyglot import ReaderGrant, project_capsule, source_fingerprint


@pytest.fixture
def capsule():
    return Capsule(
        id="synthetic-001",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_type="synthetic_fixture",
        source_ref="fixture://one",
        text="Fictional instruction: check your wrist to show the menu.",
        summary="Wrist-check menu gesture",
        profile_id="demo",
        vault_id="demo-vault",
        workspace_ids=["vr-demo"],
        provenance=["fixture://one"],
        tags=["demo", "vr"],
    )


def grant(reader="brainc", **changes):
    fields = dict(
        reader=reader,
        profile_id="demo",
        vault_id="demo-vault",
        workspace_ids=frozenset({"vr-demo"}),
    )
    fields.update(changes)
    return ReaderGrant(**fields)


def test_three_readers_share_identity_and_source_fingerprint(capsule):
    before = capsule.model_dump(mode="json")
    views = {
        r: project_capsule(capsule, reader=r, grant=grant(r))
        for r in ("pocketbrain", "brainc", "sml")
    }
    assert len({x["source_sha256"] for x in views.values()}) == 1
    assert {x["capsule_id"] for x in views.values()} == {capsule.id}
    assert {x["view"]["kind"] for x in views.values()} == {
        "compact_context", "semantic_context", "governance_candidate"
    }
    assert views["pocketbrain"]["view"]["text"] == capsule.summary
    assert views["brainc"]["view"]["text"] == capsule.text
    assert views["sml"]["view"]["candidate"]["state"] == "shadow"
    assert views["sml"]["view"]["candidate"]["collab_state"] == "local_only"
    assert views["sml"]["view"]["disposition"] == "review_only_unverified"
    assert capsule.model_dump(mode="json") == before
    assert json.dumps(views)  # serializable, no runtime objects required


@pytest.mark.parametrize("reader,active_grant", [
    ("unknown", grant("unknown")),
    ("brainc", None),
    ("brainc", grant("pocketbrain")),
    ("brainc", grant(profile_id="other")),
    ("brainc", grant(vault_id="other")),
    ("brainc", grant(workspace_ids=frozenset({"other"}))),
    ("brainc", grant(workspace_ids=frozenset())),
])
def test_unauthorized_readers_get_no_projection(capsule, reader, active_grant):
    with pytest.raises(PermissionError, match="^memory polyglot: access denied$"):
        project_capsule(capsule, reader=reader, grant=active_grant)


@pytest.mark.parametrize("policy", [
    PolicyMode.locked, PolicyMode.private_local_only,
    PolicyMode.session, PolicyMode.ephemeral,
])
def test_nonpersistent_policies_fail_closed(capsule, policy):
    capsule.policy = policy
    with pytest.raises(PermissionError):
        project_capsule(capsule, reader="brainc", grant=grant())


@pytest.mark.parametrize("status", [
    CapsuleStatus.pending_review, CapsuleStatus.uncertain,
    CapsuleStatus.conflicting, CapsuleStatus.archived, CapsuleStatus.superseded,
])
def test_nonactive_memory_cannot_be_promoted_by_projection(capsule, status):
    capsule.status = status
    with pytest.raises(PermissionError):
        project_capsule(capsule, reader="sml", grant=grant("sml"))


def test_unscoped_or_synced_memory_denied(capsule):
    capsule.workspace_ids = []
    with pytest.raises(PermissionError):
        project_capsule(capsule, reader="brainc", grant=grant())
    capsule.workspace_ids = ["vr-demo"]
    capsule.sync_state = "synced"
    with pytest.raises(PermissionError):
        project_capsule(capsule, reader="brainc", grant=grant())


def test_capsule_metadata_cannot_self_grant_reader_access(capsule):
    capsule.metadata["allow_readers"] = ["untrusted"]
    with pytest.raises(PermissionError):
        project_capsule(capsule, reader="untrusted", grant=grant("untrusted"))


def test_integrity_change_detected_but_not_authenticated(capsule):
    first = source_fingerprint(capsule)
    assert first == source_fingerprint(capsule.model_copy(deep=True))
    capsule.text = "A changed synthetic fact"
    assert source_fingerprint(capsule) != first


def test_denial_does_not_echo_synthetic_memory_text(capsule):
    with pytest.raises(PermissionError) as exc:
        project_capsule(capsule, reader="brainc", grant=grant(profile_id="other"))
    assert capsule.text not in str(exc.value)
