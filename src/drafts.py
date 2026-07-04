"""Gmail draft creation. This module — and this codebase — never calls
Gmail's send API; drafts.create is the only mutation performed here
(PRD Section 3: no autonomous send).
"""

import base64
from email.mime.text import MIMEText


def _build_raw_reply(to_address: str, subject: str, body_text: str, in_reply_to: str) -> str:
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    message = MIMEText(body_text)
    message["To"] = to_address
    message["Subject"] = subject
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to

    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def create_draft(gmail_client, message_detail: dict, draft_body: str) -> str:
    raw = _build_raw_reply(
        to_address=message_detail["from"],
        subject=message_detail["subject"],
        body_text=draft_body,
        in_reply_to=message_detail.get("message_id_header", ""),
    )
    result = (
        gmail_client.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw, "threadId": message_detail["thread_id"]}})
        .execute()
    )
    return result["id"]
