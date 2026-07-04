"""Knowledge document handling: list, download, extract, and cache text
from the configured Google Drive folder (PDF, DOCX, and Markdown).

No vector search — all extracted text is cached locally and concatenated
into a single blob injected directly into the drafting prompt (PRD Section 8).
"""

import io
import json
import os
from pathlib import Path

from docx import Document
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader

from src import config

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".md")


def list_knowledge_files(drive_client) -> list[dict]:
    result = (
        drive_client.files()
        .list(
            q=f"'{config.DRIVE_FOLDER_ID}' in parents and trashed = false",
            fields="files(id, name, mimeType, modifiedTime, md5Checksum)",
            pageSize=100,
        )
        .execute()
    )
    files = result.get("files", [])
    return [f for f in files if f["name"].lower().endswith(SUPPORTED_EXTENSIONS)]


def download_bytes(drive_client, file_id: str) -> bytes:
    request = drive_client.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def extract_text(name: str, raw_bytes: bytes) -> str:
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == ".docx":
        document = Document(io.BytesIO(raw_bytes))
        return "\n".join(p.text for p in document.paragraphs)
    if ext == ".md":
        return raw_bytes.decode("utf-8")
    raise ValueError(f"Unsupported file type: {name}")


def load_cache(path: str = None) -> dict:
    path = path or config.KNOWLEDGE_CACHE_PATH
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache: dict, path: str = None) -> None:
    path = path or config.KNOWLEDGE_CACHE_PATH
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def _version_key(file_meta: dict) -> str:
    return file_meta.get("md5Checksum") or file_meta.get("modifiedTime", "")


def refresh_knowledge_cache(drive_client, cache_path: str = None) -> dict:
    """Re-extract only files whose version key (checksum or modifiedTime)
    changed since the last cached run; reuse cached text otherwise."""
    cache_path = cache_path or config.KNOWLEDGE_CACHE_PATH
    cache = load_cache(cache_path)
    files = list_knowledge_files(drive_client)

    updated_cache = {}
    dirty = set(cache.keys()) != {f["id"] for f in files}

    for file_meta in files:
        file_id = file_meta["id"]
        version_key = _version_key(file_meta)
        cached_entry = cache.get(file_id)

        if cached_entry and cached_entry.get("version_key") == version_key:
            updated_cache[file_id] = cached_entry
            continue

        raw_bytes = download_bytes(drive_client, file_id)
        text = extract_text(file_meta["name"], raw_bytes)
        updated_cache[file_id] = {
            "name": file_meta["name"],
            "version_key": version_key,
            "extracted_text": text,
        }
        dirty = True

    if dirty:
        save_cache(updated_cache, cache_path)

    return updated_cache


def get_knowledge_blob(cache: dict) -> str:
    parts = [f"=== {entry['name']} ===\n{entry['extracted_text']}" for entry in cache.values()]
    blob = "\n\n".join(parts)
    approx_tokens = len(blob) // 4
    print(f"Knowledge blob: {len(cache)} docs, {len(blob)} chars, ~{approx_tokens} tokens (approx)")
    return blob
