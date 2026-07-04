"""Candidate email fetching and filtering (PRD Sections 4, 7, 9).

Combines a server-side Gmail search query (categories + labels) with
client-side guards (owner-sent, thread-has-draft) to produce the final
candidate list, capped per PRD Section 9/10.
"""

import base64
import re
from datetime import datetime, timedelta, timezone

from src import config, labels


def is_first_run(gmail_client) -> bool:
    """No Agent-Processed label yet => nothing has ever been processed."""
    return labels.get_label_id(gmail_client, config.LABEL_PROCESSED) is None


def build_candidate_query(first_run: bool) -> str:
    query = (
        "in:inbox "
        "-category:promotions -category:updates "
        f"-label:{config.LABEL_PROCESSED} -label:{config.LABEL_NEEDS_HUMAN}"
    )
    if first_run:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=config.FIRST_RUN_WINDOW_HOURS)
        query += f" after:{int(cutoff.timestamp())}"
    return query


def _decode_base64url(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^<]+?>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_whitespace(text: str) -> str:
    """Collapse excessive blank lines (common in signature blocks) that
    otherwise confuse the small triage model into misreading a genuine
    query as noise."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_body(payload: dict) -> str:
    if "parts" not in payload:
        data = payload.get("body", {}).get("data")
        return _decode_base64url(data) if data else ""

    for part in payload["parts"]:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return _decode_base64url(part["body"]["data"])

    for part in payload["parts"]:
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            return _strip_html(_decode_base64url(part["body"]["data"]))
        if "parts" in part:
            nested = _extract_body(part)
            if nested:
                return nested

    return ""


def get_message_detail(gmail_client, message_id: str) -> dict:
    msg = gmail_client.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    return {
        "id": msg["id"],
        "thread_id": msg["threadId"],
        "label_ids": msg.get("labelIds", []),
        "subject": headers.get("subject", ""),
        "from": headers.get("from", ""),
        "message_id_header": headers.get("message-id", ""),
        "internal_date": int(msg.get("internalDate", "0")),
        "body": _normalize_whitespace(_extract_body(msg["payload"])),
    }


def is_owner_sent(message_detail: dict, owner_email: str) -> bool:
    return owner_email.lower() in message_detail["from"].lower()


def is_already_labeled(message_detail: dict, skip_label_ids: set) -> bool:
    return bool(set(message_detail["label_ids"]) & skip_label_ids)


def get_draft_thread_ids(gmail_client) -> set:
    """One paginated pass over all drafts, so per-email draft checks are O(1)."""
    thread_ids = set()
    page_token = None
    while True:
        resp = (
            gmail_client.users()
            .drafts()
            .list(userId="me", pageToken=page_token, maxResults=100)
            .execute()
        )
        for draft in resp.get("drafts", []):
            thread_id = draft.get("message", {}).get("threadId")
            if thread_id:
                thread_ids.add(thread_id)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return thread_ids


def get_candidate_emails(gmail_client, owner_email: str) -> list[dict]:
    first_run = is_first_run(gmail_client)
    query = build_candidate_query(first_run)

    listing = gmail_client.users().messages().list(userId="me", q=query, maxResults=100).execute()
    message_ids = [m["id"] for m in listing.get("messages", [])]

    draft_thread_ids = get_draft_thread_ids(gmail_client)
    cap = config.FIRST_RUN_MAX_EMAILS if first_run else config.PER_RUN_EMAIL_CAP

    candidates = []
    for message_id in message_ids:
        detail = get_message_detail(gmail_client, message_id)

        if is_owner_sent(detail, owner_email):
            continue
        if detail["thread_id"] in draft_thread_ids:
            continue

        candidates.append(detail)
        if len(candidates) >= cap:
            break

    return candidates
