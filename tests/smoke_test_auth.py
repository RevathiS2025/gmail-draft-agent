"""Manual smoke test: confirms the refresh token authenticates against
real Gmail and Drive APIs. Not part of the automated (mocked) test suite —
run directly: `python tests/smoke_test_auth.py`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import auth, config


def main():
    gmail = auth.get_gmail_client()
    profile = gmail.users().getProfile(userId="me").execute()
    print(f"Gmail OK — authenticated as {profile['emailAddress']}")

    drive = auth.get_drive_client()
    result = (
        drive.files()
        .list(q=f"'{config.DRIVE_FOLDER_ID}' in parents", pageSize=1, fields="files(id, name)")
        .execute()
    )
    files = result.get("files", [])
    if files:
        print(f"Drive OK — found file: {files[0]['name']}")
    else:
        print("Drive OK — call succeeded, but folder returned 0 files")


if __name__ == "__main__":
    main()
