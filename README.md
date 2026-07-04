# Gmail Customer Query Draft Agent

Monitors a Gmail inbox, triages genuine customer queries, and writes **draft**
replies grounded strictly in a Google Drive knowledge folder. Never sends
email — see `PRD Gmail Agent.md` for full product scope and `tasks.md` for
the build/verification log.

## How it works

1. Hourly (via GitHub Actions), `main.py` runs the pipeline in `src/orchestrator.py`.
2. Knowledge docs (PDF/Word/Markdown) are pulled from one Drive folder, extracted,
   and cached (`cache/knowledge_cache.json`) — re-extracted only when a file changes.
3. Candidate inbox emails are fetched, excluding Promotions/Updates, owner-sent mail,
   already-labeled mail, and threads that already have a draft.
4. Each candidate goes through two Groq calls: a cheap triage model (genuine query?)
   and a stronger drafting model (grounded reply or "not found").
5. Outcome: a real Gmail draft + `Agent-Processed` label, or `Needs-Human` if the
   answer isn't in the docs, or just `Agent-Processed` if it wasn't a real query.

## One-time setup

### 1. Google Cloud OAuth

- Create an OAuth 2.0 Client ID (Desktop app type works for the Playground flow).
- **Publish the OAuth consent screen** (Published / In production, even if unverified).
  If left in "Testing" mode, the refresh token expires after 7 days and the agent
  silently stops working.
- Scopes needed: `gmail.modify` (read, label, create drafts — never send) and
  `drive.readonly`.
- Generate a long-lived refresh token via [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground)
  using your own client ID/secret and the two scopes above.

### 2. Knowledge folder

Create one Google Drive folder containing your PDF/Word/Markdown knowledge docs
(keep test fixtures or unrelated files out of this folder — everything in it is
treated as ground truth for drafting). Note the folder ID from its URL.

### 3. Local environment

Copy the required values into a `.env` file in the project root (gitignored,
never committed):

```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
GROQ_API_KEY=...
DRIVE_FOLDER_ID=...
```

Install dependencies and run the test suite:

```
pip install -r requirements-dev.txt
pytest -q
```

Run the agent manually:

```
python main.py
```

### 4. GitHub Actions deployment

The workflow at `.github/workflows/agent.yml` runs hourly and on manual dispatch.
Add the same five values as repository Secrets (Settings → Secrets and variables →
Actions): `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`,
`GROQ_API_KEY`, `DRIVE_FOLDER_ID`. The workflow needs `contents: write` permission
(already set) so it can commit the refreshed knowledge cache back to the repo.

## Updating knowledge docs

Add, edit, or replace files directly in the Drive folder. The next run detects
the change via Drive's `modifiedTime`/checksum and re-extracts only the changed
file — no other steps needed.

## Safety notes

- There is no send-capable code path anywhere in this repository — grep for
  `.send(` in `src/` to confirm.
- Drafting uses a strict all-or-nothing grounding rule: if any part of a question
  requires information not explicitly in the knowledge docs, no draft is created
  at all and the email is labeled `Needs-Human` instead.
- Labels (`Agent-Processed`, `Needs-Human`) are the only state store — there is no
  database. An email is never drafted twice, even if a run crashes between draft
  creation and labeling (see PRD Section 7).
