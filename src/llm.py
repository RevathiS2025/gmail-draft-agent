"""Groq LLM integration: two-stage triage + grounded drafting (PRD Section 6).

Stage 1 (triage) and Stage 2 (drafting) each call a swappable model
configured in src/config.py. Both enforce a strict JSON response schema,
defaulting to the safe outcome (not a query / answer not found) on any
parse or validation failure — never guess (PRD Section 3 grounding rule).
"""

import json
import logging

from groq import Groq
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src import config

logger = logging.getLogger(__name__)

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


def _is_rate_limit_error(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 429


@retry(
    retry=retry_if_exception(_is_rate_limit_error),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _chat_completion(model: str, messages: list) -> str:
    response = get_client().chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _parse_json_safely(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


TRIAGE_SYSTEM_PROMPT = """You are a triage classifier for a customer support inbox.
Decide whether the email is a genuine customer/donor/volunteer query that
deserves a human-reviewed reply, as opposed to noise (marketing newsletters,
automated notifications, spam, or personal mail unrelated to the organization).

Judge ONLY the substance of the message: what the sender is asking for or
telling you. Ignore surface formatting — greetings, sign-offs, personal or
religious closings (e.g. "HARI OM", "Regards", "Best"), paragraph breaks,
extra blank lines, or a vague subject line like "Hi". None of these make an
email noise.

Examples:
- Subject: "Hi" / Body: "Could you elaborate on your work? I'd like to
  donate or volunteer. - Jane" => {"is_query": true} (genuine query, despite
  a vague subject and a sign-off)
- Subject: "50% off today!" / Body: promotional sale content => {"is_query": false}
- Subject: "Your invoice is ready" / Body: automated billing notification with
  no question => {"is_query": false}

Respond with strict JSON only, matching exactly this schema:
{"is_query": true} or {"is_query": false}
No other keys, no explanation, no markdown formatting."""


def triage_email(subject: str, body: str) -> bool:
    messages = [
        {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Subject: {subject}\n\nBody:\n{body}"},
    ]
    raw = _chat_completion(config.TRIAGE_MODEL, messages)
    parsed = _parse_json_safely(raw)

    if parsed is None or not isinstance(parsed.get("is_query"), bool):
        logger.warning("Triage response failed schema validation, defaulting to is_query=False: %r", raw)
        return False

    return parsed["is_query"]


DRAFTING_SYSTEM_PROMPT = """You are a customer support drafting assistant. You are given the
full text of the company's knowledge base documents and a customer email. Write a reply
that answers the customer's question using ONLY information explicitly present in the
supplied knowledge documents.

Rules:
- If the answer (or any part of it) requires information not explicitly present in the
  knowledge documents, set "answer_found" to false and leave "draft_body" empty. Do this
  whenever you are unsure or the documents are ambiguous — never guess.
- Never invent facts, numbers, policies, or commitments not present in the documents.
- If answer_found is true, draft_body must be a complete, polite, ready-to-send email reply.

Respond with strict JSON only, matching exactly this schema:
{"answer_found": true, "draft_body": "..."} or {"answer_found": false, "draft_body": ""}
No other keys, no explanation, no markdown formatting."""


def draft_reply(email_body: str, knowledge_blob: str) -> dict:
    messages = [
        {"role": "system", "content": DRAFTING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"KNOWLEDGE DOCUMENTS:\n{knowledge_blob}\n\n---\n\nCUSTOMER EMAIL:\n{email_body}",
        },
    ]
    raw = _chat_completion(config.DRAFTING_MODEL, messages)
    parsed = _parse_json_safely(raw)

    if (
        parsed is None
        or not isinstance(parsed.get("answer_found"), bool)
        or not isinstance(parsed.get("draft_body", ""), str)
    ):
        logger.warning("Drafting response failed schema validation, defaulting to answer_found=False: %r", raw)
        return {"answer_found": False, "draft_body": ""}

    if not parsed["answer_found"]:
        return {"answer_found": False, "draft_body": ""}

    return {"answer_found": True, "draft_body": parsed["draft_body"]}
