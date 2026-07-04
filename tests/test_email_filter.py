import base64
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, email_filter


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _raw_message(msg_id: str, thread_id: str, from_addr: str, body_text: str, label_ids=None):
    return {
        "id": msg_id,
        "threadId": thread_id,
        "labelIds": label_ids or ["INBOX"],
        "internalDate": "1000000000000",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test subject"},
                {"name": "From", "value": from_addr},
            ],
            "body": {"data": _b64(body_text)},
        },
    }


def _mock_gmail(labels_resp, messages_resp, get_side_effect, drafts_resp):
    client = MagicMock()
    client.users.return_value.labels.return_value.list.return_value.execute.return_value = labels_resp
    client.users.return_value.messages.return_value.list.return_value.execute.return_value = messages_resp
    client.users.return_value.messages.return_value.get.return_value.execute.side_effect = get_side_effect
    client.users.return_value.drafts.return_value.list.return_value.execute.return_value = drafts_resp
    return client


def test_build_candidate_query_excludes_categories_and_labels():
    query = email_filter.build_candidate_query(first_run=False)
    assert "-category:promotions" in query
    assert "-category:updates" in query
    assert f"-label:{config.LABEL_PROCESSED}" in query
    assert f"-label:{config.LABEL_NEEDS_HUMAN}" in query
    assert "after:" not in query


def test_build_candidate_query_first_run_adds_time_window():
    query = email_filter.build_candidate_query(first_run=True)
    assert "after:" in query


def test_extract_body_single_part():
    payload = {"body": {"data": _b64("Hello plain")}}
    assert email_filter._extract_body(payload) == "Hello plain"


def test_extract_body_prefers_plain_over_html():
    payload = {
        "parts": [
            {"mimeType": "text/html", "body": {"data": _b64("<p>Hi</p>")}},
            {"mimeType": "text/plain", "body": {"data": _b64("Hi plain")}},
        ]
    }
    assert email_filter._extract_body(payload) == "Hi plain"


def test_extract_body_falls_back_to_html_stripped():
    payload = {"parts": [{"mimeType": "text/html", "body": {"data": _b64("<p>Hello <b>world</b></p>")}}]}
    assert email_filter._extract_body(payload) == "Hello world"


def test_extract_body_nested_multipart():
    payload = {
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [{"mimeType": "text/plain", "body": {"data": _b64("Nested plain")}}],
            }
        ]
    }
    assert email_filter._extract_body(payload) == "Nested plain"


def test_normalize_whitespace_collapses_excessive_blank_lines():
    noisy = "Line one.\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\nSignature block\r\n"
    assert email_filter._normalize_whitespace(noisy) == "Line one.\n\nSignature block"


def test_get_message_detail_normalizes_body_whitespace():
    raw = _raw_message("m1", "t1", "customer@example.com", "Hello\r\n\r\n\r\n\r\n\r\nWorld\r\n")
    client = MagicMock()
    client.users.return_value.messages.return_value.get.return_value.execute.return_value = raw

    detail = email_filter.get_message_detail(client, "m1")

    assert detail["body"] == "Hello\n\nWorld"


def test_is_owner_sent():
    detail = {"from": "Jane Doe <owner@example.com>"}
    assert email_filter.is_owner_sent(detail, "owner@example.com") is True
    assert email_filter.is_owner_sent(detail, "someone-else@example.com") is False


def test_is_already_labeled():
    detail = {"label_ids": ["INBOX", "L_PROCESSED"]}
    assert email_filter.is_already_labeled(detail, {"L_PROCESSED"}) is True
    assert email_filter.is_already_labeled(detail, {"L_NEEDS_HUMAN"}) is False


def test_is_first_run_true_when_label_missing():
    client = _mock_gmail({"labels": []}, {"messages": []}, [], {"drafts": []})
    assert email_filter.is_first_run(client) is True


def test_is_first_run_false_when_label_exists():
    client = _mock_gmail(
        {"labels": [{"name": config.LABEL_PROCESSED, "id": "L1"}]}, {"messages": []}, [], {"drafts": []}
    )
    assert email_filter.is_first_run(client) is False


def test_get_draft_thread_ids_paginates(monkeypatch):
    client = MagicMock()
    page1 = {"drafts": [{"message": {"threadId": "t1"}}], "nextPageToken": "p2"}
    page2 = {"drafts": [{"message": {"threadId": "t2"}}]}
    client.users.return_value.drafts.return_value.list.return_value.execute.side_effect = [page1, page2]
    assert email_filter.get_draft_thread_ids(client) == {"t1", "t2"}


def test_get_candidate_emails_skips_owner_sent_and_drafted_threads(monkeypatch):
    monkeypatch.setattr(config, "PER_RUN_EMAIL_CAP", 25)
    labels_resp = {"labels": [{"name": config.LABEL_PROCESSED, "id": "L1"}]}
    messages_resp = {"messages": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}, {"id": "m4"}]}
    get_side_effect = [
        _raw_message("m1", "t1", "customer1@example.com", "Question 1"),
        _raw_message("m2", "t2", "owner@example.com", "Should be skipped (owner-sent)"),
        _raw_message("m3", "t3", "customer2@example.com", "Should be skipped (thread has draft)"),
        _raw_message("m4", "t4", "customer3@example.com", "Question 4"),
    ]
    drafts_resp = {"drafts": [{"message": {"threadId": "t3"}}]}
    client = _mock_gmail(labels_resp, messages_resp, get_side_effect, drafts_resp)

    candidates = email_filter.get_candidate_emails(client, owner_email="owner@example.com")

    assert [c["id"] for c in candidates] == ["m1", "m4"]


def test_get_candidate_emails_enforces_per_run_cap(monkeypatch):
    monkeypatch.setattr(config, "PER_RUN_EMAIL_CAP", 1)
    labels_resp = {"labels": [{"name": config.LABEL_PROCESSED, "id": "L1"}]}
    messages_resp = {"messages": [{"id": "m1"}, {"id": "m2"}]}
    get_side_effect = [
        _raw_message("m1", "t1", "customer1@example.com", "Question 1"),
        _raw_message("m2", "t2", "customer2@example.com", "Question 2"),
    ]
    drafts_resp = {"drafts": []}
    client = _mock_gmail(labels_resp, messages_resp, get_side_effect, drafts_resp)

    candidates = email_filter.get_candidate_emails(client, owner_email="owner@example.com")

    assert len(candidates) == 1
