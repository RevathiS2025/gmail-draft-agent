"""Strict draft-then-label ordering (PRD Section 7 idempotency).

Create the draft first, then apply Agent-Processed immediately after. If
the process crashes between these two steps, the next run's "thread
already has a draft" guard (src/email_filter.get_draft_thread_ids)
prevents a duplicate draft — see PRD Section 7 "Idempotency ordering".
"""

import logging

from src import config, drafts, labels

logger = logging.getLogger(__name__)


def draft_then_mark_processed(gmail_client, message_detail: dict, draft_body: str) -> str:
    try:
        draft_id = drafts.create_draft(gmail_client, message_detail, draft_body)
    except Exception:
        logger.exception("Draft creation failed for message %s", message_detail["id"])
        raise

    try:
        labels.apply_label(gmail_client, message_detail["id"], config.LABEL_PROCESSED)
    except Exception:
        logger.exception(
            "Draft %s created for message %s but applying %s failed — "
            "thread-has-draft guard will prevent a duplicate on the next run",
            draft_id,
            message_detail["id"],
            config.LABEL_PROCESSED,
        )
        raise

    return draft_id
