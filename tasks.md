# Tasks: Gmail Customer Query Draft Agent

Derived from `PRD Gmail Agent.md`. Tasks are atomic and grouped into phases ordered by dependency — each phase assumes all prior phases are complete. Checkboxes track progress.

Stack assumption: Python (google-api-python-client, google-auth, pypdf, python-docx, groq SDK). Swap if a different stack is preferred.

---

## Phase 0 — Project Scaffolding
*No dependencies.*

- [x] 0.1 Init git repo (`git init`; initial commit deferred until user asks to commit)
- [x] 0.2 Create project structure: `src/`, `tests/`, `.github/workflows/`, `cache/`
- [x] 0.3 Create `.gitignore` — exclude `credentials.txt`, `.env`, `__pycache__/`, `*.pyc`, local cache files not meant to be committed
- [x] 0.4 Create `requirements.txt` (google-api-python-client, google-auth, google-auth-oauthlib, pypdf, python-docx, groq, tenacity, python-dotenv)
- [x] 0.5 Create `src/config.py` — centralized loading of env vars/secrets (client id/secret, refresh token, Groq key, Drive folder id, model names, per-run cap, first-run window)
- [x] 0.6 **Secure `credentials.txt`**: move its values into a local `.env` (gitignored) or directly into GitHub Secrets, then delete the plaintext `credentials.txt` from disk once migrated — it currently holds live, unscoped secrets in the repo working directory

---

## Phase 1 — Google Authentication
*Depends on: Phase 0.*

- [ ] 1.1 Manual check: confirm OAuth consent screen is set to **Published / In production** (not Testing) — PRD 11 critical prerequisite (user action, cannot be verified via API)
- [x] 1.2 Implement `src/auth.py`: build `Credentials` object from stored refresh token + client id/secret (no interactive flow)
- [x] 1.3 Implement Gmail API client builder (`gmail.modify` scope)
- [x] 1.4 Implement Drive API client builder (`drive.readonly` scope)
- [x] 1.5 Smoke test: authenticate and successfully call `users.getProfile` (Gmail) and `files.list` (Drive) with 1 result each — confirmed live against `revathiarjuntnpsc@gmail.com` (see note below if this is the wrong account)

---

## Phase 2 — Knowledge Document Handling
*Depends on: Phase 1 (Drive client).*

- [x] 2.1 Implement Drive folder listing scoped to the configured knowledge folder id
- [x] 2.2 Fetch file metadata needed for change detection (`modifiedTime`, `md5Checksum`)
- [x] 2.3 Implement PDF text extraction (pypdf)
- [x] 2.4 Implement DOCX text extraction (python-docx)
- [x] 2.4b Implement Markdown (.md) text extraction (added beyond PRD scope, per user decision — real folder mixes doc types)
- [x] 2.5 Implement local cache store (`cache/knowledge_cache.json`: file id → `{name, version_key, extracted_text}`)
- [x] 2.6 Implement cache-refresh logic: re-extract only when a file's checksum/modifiedTime differs from cache
- [x] 2.7 Implement concatenation of all cached doc texts into one knowledge blob; log total token/char count
- [x] 2.8 Unit tests: extraction functions (PDF/DOCX/MD) and cache-hit/cache-miss branching — 8 tests passing
- [x] 2.9 **User action:** removed `Sample_Test_Emails.md` from the Drive knowledge folder (deleted) — confirmed via re-run: knowledge blob now contains only the 2 real docs (2,644 approx tokens)

---

## Phase 3 — Candidate Email Fetching & Filtering
*Depends on: Phase 1 (Gmail client).*

- [x] 3.1 Implement inbox message listing via Gmail API search query
- [x] 3.2 Build query string excluding `CATEGORY_PROMOTIONS` and `CATEGORY_UPDATES` at the API-query level
- [x] 3.3 Implement message detail fetch: subject, plain-text body, sender, `threadId`, existing label ids
- [x] 3.4 Implement owner-sent-mail exclusion (compare `From` header against authenticated account email)
- [x] 3.5 Implement label-based skip check (`Agent-Processed` or `Needs-Human` present → skip) — enforced at query level plus `is_already_labeled` guard
- [x] 3.6 Implement "thread already has a draft" check via `drafts.list` filtered by `threadId` (single paginated pass, O(1) per candidate)
- [x] 3.7 Implement first-run mode: cap to latest 10–15 emails within the last 2 hours (first-run detected via absence of `Agent-Processed` label)
- [x] 3.8 Implement steady-state mode: label-based query exclusion naturally limits to new/unhandled mail, no separate "since last run" state needed
- [x] 3.9 Implement per-run cap enforcement (~25 emails max)
- [x] 3.10 Unit tests for the full filter chain using mocked Gmail API responses — 13 tests passing; also dry-run verified against the real inbox (0 candidates, correctly — only 2 old messages exist, both outside the first-run window)

---

## Phase 4 — Label & Draft State Management
*Depends on: Phase 1 (Gmail client).*

- [x] 4.1 Implement get-or-create label lookup for `Agent-Processed` and `Needs-Human`
- [x] 4.2 Implement `apply_label(message_id, label_name)`
- [x] 4.3 Implement `create_draft(thread_id, to, subject, body)` — Gmail `drafts.create` only, no send path anywhere in code
- [x] 4.4 Implement strict-ordering wrapper: create draft → immediately apply `Agent-Processed`, with failure logged distinctly per step (per PRD 7 idempotency ordering)
- [x] 4.5 Unit tests for label/draft functions using mocked Gmail API client — 11 tests passing
- [x] 4.6 Live verification (user-approved): created a real draft + applied `Agent-Processed` on a real inbox message; confirmed label applied, draft correctly threaded, and Phase 3's `get_draft_thread_ids` guard detects it — user may delete the test draft/label from Gmail if desired

---

## Phase 5 — LLM Integration (Groq)
*Depends on: Phase 0 (config).*

- [x] 5.1 Implement Groq client wrapper reading model names from config (triage vs drafting model swappable)
- [x] 5.2 Implement Stage 1 triage: prompt template (subject + body) → parse `is_query: true/false`
- [x] 5.3 Implement Stage 2 drafting: prompt template (email body + full knowledge blob) → parse `{answer_found, draft_body}` JSON
- [x] 5.4 Implement strict JSON-schema validation with default-to-`false`/no-draft on any parse ambiguity (PRD 6 grounding rule)
- [x] 5.5 Implement retry with exponential backoff on Groq 429 responses (both stages)
- [x] 5.6 Unit tests: prompt formatting and response parsing against mocked Groq responses, including malformed-JSON edge case — 12 tests passing
- [x] 5.7 Live verification: confirmed `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` are valid on Groq today, `response_format: json_object` works, and both a grounded question (donation/tax) and a deliberately ungrounded one (FCRA/CSR-1) returned correct `answer_found` values against the real knowledge blob

---

## Phase 6 — Orchestration Pipeline
*Depends on: Phases 2, 3, 4, 5.*

- [x] 6.1 Implement `run()`: load/refresh knowledge blob → fetch candidate emails → iterate pipeline (`src/orchestrator.py`)
- [x] 6.2 Wire per-email Stage 1: reject → `apply_label(Agent-Processed)`, continue to next email
- [x] 6.3 Wire per-email Stage 2: `answer_found=false` → `apply_label(Needs-Human)`; `answer_found=true` → `create_draft` + `apply_label(Agent-Processed)`
- [x] 6.4 Wrap per-email processing in try/except so one email's failure doesn't abort the run; log the error and continue
- [x] 6.5 Implement run summary logging (fetched / triaged-out / drafted / needs-human / errored counts)
- [x] 6.6 Integration test: full run against mocked Gmail + Drive + Groq covering all four outcomes (non-query, grounded answer, ungrounded answer, API error) — 2 tests passing; full suite now 46 tests passing
- [x] 6.7 Live end-to-end verification: user sent a real test email ("Hi" — donation/volunteer inquiry). First live run exposed a real triage bug (see 6.8); after fixing, a clean re-run produced `{'fetched': 1, 'triaged_out': 0, 'drafted': 1, 'needs_human': 0, 'errored': 0}` with a correct, grounded draft
- [x] 6.8 **Bug found & fixed during live testing:** `llama-3.1-8b-instant` triage consistently (5/5) misclassified the genuine test email as noise, specifically due to the combination of multi-line formatting + a devotional sign-off ("HARI OM.. Revathi Shankar"). Fixed two ways: (a) added `_normalize_whitespace` in `src/email_filter.py` to collapse excessive blank lines from signature blocks; (b) rewrote `TRIAGE_SYSTEM_PROMPT` in `src/llm.py` with explicit instructions to ignore sign-offs/greetings/formatting plus few-shot examples. Re-verified 5/5 correct afterward, plus noise-rejection still works. Added regression unit tests for whitespace normalization (2 tests, full suite now 48 passing)

---

## Phase 7 — Scheduling & Deployment
*Depends on: Phase 6.*

- [x] 7.1 Write `.github/workflows/agent.yml`: hourly `cron` trigger (`0 * * * *`) + manual `workflow_dispatch`
- [x] 7.2 Created private repo [RevathiS2025/gmail-draft-agent](https://github.com/RevathiS2025/gmail-draft-agent), pushed initial commit, and set all 5 repo Secrets (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GROQ_API_KEY`, `DRIVE_FOLDER_ID`) via `gh secret set`
- [x] 7.3 Persist knowledge cache across runs: workflow commits `cache/knowledge_cache.json` back to the repo after each run if it changed (requires `permissions: contents: write`, included)
- [x] 7.4 Add workflow-level safeguards: per-run cap already enforced in code (Phase 3); added `timeout-minutes: 10` at the job level
- [x] 7.5 Triggered via `workflow_dispatch` on GitHub Actions — [run succeeded](https://github.com/RevathiS2025/gmail-draft-agent/actions/runs/28704509868): secrets resolved, Gmail/Drive auth succeeded, knowledge cache loaded (2 docs), summary `{'fetched': 0, ...}` (correct — no new unlabeled mail since the Phase 6 test). Note: had to push a second trivial commit before GitHub registered the workflow — the first `gh repo create --push` did not trigger indexing on its own

---

## Phase 8 — Verification & Hardening
*Depends on: Phase 7.*

- [x] 8.1 Code review: confirmed zero `.send(` calls anywhere in `src/` or `main.py` — no send capability exists in the codebase
- [x] 8.2 Manual QA: real grounded email produced a correct doc-sourced draft (Phase 6); stress-tested a partial-knowledge edge case (VAN of Love trip + unstated child-age policy) which surfaced a real product-policy gap — see 8.2b
- [x] 8.2b **Finding + fix:** the drafting model was answering partial-knowledge questions with a hedged partial draft ("here's what I know, contact the team for the rest"), which conflicts with PRD Section 6's literal "any missing info → answer_found=false" rule. Asked the user to confirm the intended policy — chose **strict all-or-nothing**. Rewrote `DRAFTING_SYSTEM_PROMPT` in `src/llm.py` with an explicit all-or-nothing rule + worked example. Re-verified 3/3 correct on the partial case, plus fully-grounded and fully-ungrounded cases unaffected. Full suite still 48 passing
- [x] 8.3 Manual QA (live): simulated the PRD's stated crash scenario (draft created, label never applied) on the real test thread — re-running the pipeline correctly produced 0 candidates (thread-has-draft guard caught it) and draft count stayed at 2 (no duplicate). Confirms PRD Section 7 idempotency guarantee holds even without the label
- [x] 8.4 Live QA: user sent a real out-of-scope test email ("FCRA number" — requesting FCRA registration/CSR-1 details). Full live pipeline run produced `{'fetched': 1, 'triaged_out': 0, 'drafted': 0, 'needs_human': 1, 'errored': 0}`; confirmed `Needs-Human` label applied to the message and no draft created on that thread
- [x] 8.5 Write `README.md`: OAuth consent-screen publishing step, secrets setup, how to add/update knowledge docs in Drive
