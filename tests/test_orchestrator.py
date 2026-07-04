import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, orchestrator


def _detail(msg_id, subject, body):
    return {
        "id": msg_id,
        "subject": subject,
        "body": body,
        "thread_id": f"t-{msg_id}",
        "from": "customer@example.com",
        "message_id_header": "",
    }


def test_run_handles_all_four_outcomes(monkeypatch):
    candidates = [
        _detail("m1", "Non-query newsletter", "promo body"),
        _detail("m2", "Grounded question", "grounded body"),
        _detail("m3", "Ungrounded question", "ungrounded body"),
        _detail("m4", "Triggers an error", "error body"),
    ]

    monkeypatch.setattr(orchestrator.auth, "get_gmail_client", lambda: MagicMock())
    monkeypatch.setattr(orchestrator.auth, "get_drive_client", lambda: MagicMock())
    monkeypatch.setattr(orchestrator, "_get_owner_email", lambda gmail_client: "owner@example.com")
    monkeypatch.setattr(orchestrator.knowledge, "refresh_knowledge_cache", lambda drive_client: {})
    monkeypatch.setattr(orchestrator.knowledge, "get_knowledge_blob", lambda cache: "KB TEXT")
    monkeypatch.setattr(
        orchestrator.email_filter, "get_candidate_emails", lambda gmail_client, owner_email: candidates
    )

    def fake_triage(subject, body):
        if body == "promo body":
            return False
        if body == "error body":
            raise RuntimeError("Groq exploded")
        return True

    def fake_draft_reply(body, knowledge_blob):
        if body == "grounded body":
            return {"answer_found": True, "draft_body": "Answer"}
        if body == "ungrounded body":
            return {"answer_found": False, "draft_body": ""}
        raise AssertionError(f"draft_reply should not be called for body={body!r}")

    applied_labels = []
    drafted_calls = []

    monkeypatch.setattr(orchestrator.llm, "triage_email", fake_triage)
    monkeypatch.setattr(orchestrator.llm, "draft_reply", fake_draft_reply)
    monkeypatch.setattr(
        orchestrator.labels,
        "apply_label",
        lambda gmail_client, message_id, label_name: applied_labels.append((message_id, label_name)),
    )
    monkeypatch.setattr(
        orchestrator.state_actions,
        "draft_then_mark_processed",
        lambda gmail_client, message_detail, draft_body: drafted_calls.append(message_detail["id"])
        or "draft-id",
    )

    summary = orchestrator.run()

    assert summary == {"fetched": 4, "triaged_out": 1, "drafted": 1, "needs_human": 1, "errored": 1}
    assert ("m1", config.LABEL_PROCESSED) in applied_labels
    assert ("m3", config.LABEL_NEEDS_HUMAN) in applied_labels
    assert drafted_calls == ["m2"]
    # the errored email must not have triggered any label or draft action
    assert all(msg_id != "m4" for msg_id, _ in applied_labels)
    assert "m4" not in drafted_calls


def test_run_with_no_candidates_returns_zeroed_summary(monkeypatch):
    monkeypatch.setattr(orchestrator.auth, "get_gmail_client", lambda: MagicMock())
    monkeypatch.setattr(orchestrator.auth, "get_drive_client", lambda: MagicMock())
    monkeypatch.setattr(orchestrator, "_get_owner_email", lambda gmail_client: "owner@example.com")
    monkeypatch.setattr(orchestrator.knowledge, "refresh_knowledge_cache", lambda drive_client: {})
    monkeypatch.setattr(orchestrator.knowledge, "get_knowledge_blob", lambda cache: "")
    monkeypatch.setattr(
        orchestrator.email_filter, "get_candidate_emails", lambda gmail_client, owner_email: []
    )

    summary = orchestrator.run()

    assert summary == {"fetched": 0, "triaged_out": 0, "drafted": 0, "needs_human": 0, "errored": 0}
