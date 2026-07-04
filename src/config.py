"""Centralized configuration: secrets, model names, and run limits.

Values are read from environment variables. Locally, a `.env` file
(gitignored) supplies them via python-dotenv; in GitHub Actions they
come from repository Secrets injected as env vars.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


# --- Secrets ---
GOOGLE_CLIENT_ID = _require("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _require("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = _require("GOOGLE_REFRESH_TOKEN")
GROQ_API_KEY = _require("GROQ_API_KEY")
DRIVE_FOLDER_ID = _require("DRIVE_FOLDER_ID")

# --- OAuth scopes (PRD Section 11: modify, never send) ---
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive.readonly",
]

# --- Gmail labels (PRD Section 7) ---
LABEL_PROCESSED = "Agent-Processed"
LABEL_NEEDS_HUMAN = "Needs-Human"

# --- LLM models (PRD Section 6, swappable) ---
TRIAGE_MODEL = os.environ.get("TRIAGE_MODEL", "llama-3.1-8b-instant")
DRAFTING_MODEL = os.environ.get("DRAFTING_MODEL", "llama-3.3-70b-versatile")

# --- Run limits (PRD Sections 9-10) ---
PER_RUN_EMAIL_CAP = int(os.environ.get("PER_RUN_EMAIL_CAP", "25"))
FIRST_RUN_MAX_EMAILS = int(os.environ.get("FIRST_RUN_MAX_EMAILS", "15"))
FIRST_RUN_WINDOW_HOURS = int(os.environ.get("FIRST_RUN_WINDOW_HOURS", "2"))

# --- Cache location (PRD Section 8) ---
KNOWLEDGE_CACHE_PATH = os.environ.get("KNOWLEDGE_CACHE_PATH", "cache/knowledge_cache.json")
