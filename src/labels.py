"""Gmail label lookup. Labels are the sole state store (PRD Section 7).

Lookup-only for now (used by first-run detection and candidate filtering
in Phase 3). Create/apply operations are added in Phase 4.
"""


def list_labels(gmail_client) -> dict:
    result = gmail_client.users().labels().list(userId="me").execute()
    return {label["name"]: label["id"] for label in result.get("labels", [])}


def get_label_id(gmail_client, name: str) -> str | None:
    return list_labels(gmail_client).get(name)


def create_label(gmail_client, name: str) -> str:
    body = {
        "name": name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    result = gmail_client.users().labels().create(userId="me", body=body).execute()
    return result["id"]


def get_or_create_label_id(gmail_client, name: str) -> str:
    label_id = get_label_id(gmail_client, name)
    if label_id:
        return label_id
    return create_label(gmail_client, name)


def apply_label(gmail_client, message_id: str, label_name: str) -> None:
    label_id = get_or_create_label_id(gmail_client, label_name)
    gmail_client.users().messages().modify(
        userId="me", id=message_id, body={"addLabelIds": [label_id]}
    ).execute()
