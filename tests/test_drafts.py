import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import drafts


def test_build_raw_reply_adds_re_prefix_once():
    raw = drafts._build_raw_reply("customer@example.com", "Question about donations", "Body text", "")
    decoded = _decode(raw)
    assert "Subject: Re: Question about donations" in decoded


def test_build_raw_reply_does_not_double_prefix_existing_re():
    raw = drafts._build_raw_reply("customer@example.com", "Re: Question", "Body text", "")
    decoded = _decode(raw)
    assert decoded.count("Re: Re:") == 0
    assert "Subject: Re: Question" in decoded


def test_build_raw_reply_includes_threading_headers_when_present():
    raw = drafts._build_raw_reply("customer@example.com", "Question", "Body", "<abc123@mail.gmail.com>")
    decoded = _decode(raw)
    assert "In-Reply-To: <abc123@mail.gmail.com>" in decoded
    assert "References: <abc123@mail.gmail.com>" in decoded


def test_build_raw_reply_omits_threading_headers_when_absent():
    raw = drafts._build_raw_reply("customer@example.com", "Question", "Body", "")
    decoded = _decode(raw)
    assert "In-Reply-To" not in decoded


def test_create_draft_calls_drafts_create_with_thread_id_and_never_sends():
    client = MagicMock()
    client.users.return_value.drafts.return_value.create.return_value.execute.return_value = {"id": "d1"}

    message_detail = {
        "from": "customer@example.com",
        "subject": "Question",
        "thread_id": "t1",
        "message_id_header": "<abc@mail.gmail.com>",
        "id": "m1",
    }

    draft_id = drafts.create_draft(client, message_detail, "Here is the answer.")

    assert draft_id == "d1"
    _, kwargs = client.users.return_value.drafts.return_value.create.call_args
    assert kwargs["body"]["message"]["threadId"] == "t1"
    client.users.return_value.messages.return_value.send.assert_not_called()


def _decode(raw: str) -> str:
    import base64

    padded = raw + "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
