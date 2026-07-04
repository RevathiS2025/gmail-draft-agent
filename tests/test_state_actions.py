import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src import state_actions


def test_draft_then_mark_processed_calls_draft_before_label(monkeypatch):
    call_order = []

    monkeypatch.setattr(
        state_actions.drafts,
        "create_draft",
        lambda gmail_client, detail, body: call_order.append("draft") or "draft-1",
    )
    monkeypatch.setattr(
        state_actions.labels,
        "apply_label",
        lambda gmail_client, message_id, label_name: call_order.append(("label", label_name)),
    )

    draft_id = state_actions.draft_then_mark_processed(
        gmail_client=object(), message_detail={"id": "m1"}, draft_body="Answer"
    )

    assert draft_id == "draft-1"
    assert call_order == ["draft", ("label", state_actions.config.LABEL_PROCESSED)]


def test_draft_failure_prevents_label_application(monkeypatch):
    label_calls = []

    def _fail_draft(gmail_client, detail, body):
        raise RuntimeError("Gmail API error")

    monkeypatch.setattr(state_actions.drafts, "create_draft", _fail_draft)
    monkeypatch.setattr(
        state_actions.labels,
        "apply_label",
        lambda *a, **k: label_calls.append(1),
    )

    with pytest.raises(RuntimeError):
        state_actions.draft_then_mark_processed(
            gmail_client=object(), message_detail={"id": "m1"}, draft_body="Answer"
        )

    assert label_calls == []


def test_label_failure_after_successful_draft_still_raises(monkeypatch):
    monkeypatch.setattr(state_actions.drafts, "create_draft", lambda *a, **k: "draft-1")

    def _fail_label(*a, **k):
        raise RuntimeError("label API error")

    monkeypatch.setattr(state_actions.labels, "apply_label", _fail_label)

    with pytest.raises(RuntimeError):
        state_actions.draft_then_mark_processed(
            gmail_client=object(), message_detail={"id": "m1"}, draft_body="Answer"
        )
