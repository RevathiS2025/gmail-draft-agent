"""End-to-end orchestration: knowledge refresh -> candidate fetch -> per-email
triage/draft pipeline (PRD Section 5). One email's failure never aborts the run.
"""

import logging

from src import auth, config, email_filter, knowledge, labels, llm, state_actions

logger = logging.getLogger(__name__)


def _get_owner_email(gmail_client) -> str:
    return gmail_client.users().getProfile(userId="me").execute()["emailAddress"]


def _process_email(gmail_client, knowledge_blob: str, message_detail: dict) -> str:
    """Returns one of: 'triaged_out', 'drafted', 'needs_human'."""
    is_query = llm.triage_email(message_detail["subject"], message_detail["body"])

    if not is_query:
        labels.apply_label(gmail_client, message_detail["id"], config.LABEL_PROCESSED)
        return "triaged_out"

    result = llm.draft_reply(message_detail["body"], knowledge_blob)

    if not result["answer_found"]:
        labels.apply_label(gmail_client, message_detail["id"], config.LABEL_NEEDS_HUMAN)
        return "needs_human"

    state_actions.draft_then_mark_processed(gmail_client, message_detail, result["draft_body"])
    return "drafted"


def run() -> dict:
    gmail_client = auth.get_gmail_client()
    drive_client = auth.get_drive_client()

    owner_email = _get_owner_email(gmail_client)

    cache = knowledge.refresh_knowledge_cache(drive_client)
    knowledge_blob = knowledge.get_knowledge_blob(cache)

    candidates = email_filter.get_candidate_emails(gmail_client, owner_email)

    summary = {"fetched": len(candidates), "triaged_out": 0, "drafted": 0, "needs_human": 0, "errored": 0}

    for message_detail in candidates:
        try:
            outcome = _process_email(gmail_client, knowledge_blob, message_detail)
            summary[outcome] += 1
        except Exception:
            logger.exception(
                "Failed to process message %s (%s) — continuing with next email",
                message_detail["id"],
                message_detail["subject"],
            )
            summary["errored"] += 1

    logger.info("Run summary: %s", summary)
    return summary
