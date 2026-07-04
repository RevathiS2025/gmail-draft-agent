import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import llm


def _mock_completion(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_triage_email_true(monkeypatch):
    monkeypatch.setattr(llm, "_chat_completion", lambda model, messages: '{"is_query": true}')
    assert llm.triage_email("Question", "Can I get a refund?") is True


def test_triage_email_false(monkeypatch):
    monkeypatch.setattr(llm, "_chat_completion", lambda model, messages: '{"is_query": false}')
    assert llm.triage_email("50% off today!", "Sale ends soon") is False


def test_triage_email_defaults_false_on_malformed_json(monkeypatch):
    monkeypatch.setattr(llm, "_chat_completion", lambda model, messages: "not json at all")
    assert llm.triage_email("Subject", "Body") is False


def test_triage_email_defaults_false_on_missing_key(monkeypatch):
    monkeypatch.setattr(llm, "_chat_completion", lambda model, messages: '{"something_else": true}')
    assert llm.triage_email("Subject", "Body") is False


def test_draft_reply_answer_found_true(monkeypatch):
    monkeypatch.setattr(
        llm,
        "_chat_completion",
        lambda model, messages: '{"answer_found": true, "draft_body": "Hi, here is the answer."}',
    )
    result = llm.draft_reply("What are your hours?", "Hours: 9-5 knowledge doc text")
    assert result == {"answer_found": True, "draft_body": "Hi, here is the answer."}


def test_draft_reply_answer_not_found(monkeypatch):
    monkeypatch.setattr(
        llm, "_chat_completion", lambda model, messages: '{"answer_found": false, "draft_body": ""}'
    )
    result = llm.draft_reply("Unrelated legal question", "irrelevant knowledge text")
    assert result == {"answer_found": False, "draft_body": ""}


def test_draft_reply_defaults_to_not_found_on_malformed_json(monkeypatch):
    monkeypatch.setattr(llm, "_chat_completion", lambda model, messages: "```json broken")
    result = llm.draft_reply("Question", "docs")
    assert result == {"answer_found": False, "draft_body": ""}


def test_draft_reply_defaults_to_not_found_on_missing_keys(monkeypatch):
    monkeypatch.setattr(llm, "_chat_completion", lambda model, messages: '{"draft_body": "text only"}')
    result = llm.draft_reply("Question", "docs")
    assert result == {"answer_found": False, "draft_body": ""}


def test_draft_reply_defaults_to_not_found_when_answer_found_true_but_body_wrong_type(monkeypatch):
    monkeypatch.setattr(
        llm, "_chat_completion", lambda model, messages: '{"answer_found": true, "draft_body": 12345}'
    )
    result = llm.draft_reply("Question", "docs")
    assert result == {"answer_found": False, "draft_body": ""}


def test_is_rate_limit_error_detects_429():
    err = MagicMock()
    err.status_code = 429
    assert llm._is_rate_limit_error(err) is True


def test_is_rate_limit_error_ignores_other_errors():
    err = MagicMock()
    err.status_code = 500
    assert llm._is_rate_limit_error(err) is False


def test_chat_completion_retries_on_429_then_succeeds(monkeypatch):
    call_count = {"n": 0}

    class RateLimitError(Exception):
        status_code = 429

    def flaky_create(**kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise RateLimitError("rate limited")
        return _mock_completion('{"is_query": true}')

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = flaky_create
    monkeypatch.setattr(llm, "get_client", lambda: fake_client)
    # avoid real sleeping between retries in the test
    monkeypatch.setattr(llm._chat_completion.retry, "wait", lambda *a, **k: 0)

    result = llm._chat_completion("some-model", [{"role": "user", "content": "hi"}])

    assert result == '{"is_query": true}'
    assert call_count["n"] == 3
