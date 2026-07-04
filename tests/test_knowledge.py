import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docx import Document
from pypdf import PdfWriter

from src import knowledge


def _make_docx_bytes(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _make_blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_extract_text_md():
    assert knowledge.extract_text("faq.md", b"# Hello\nWorld") == "# Hello\nWorld"


def test_extract_text_docx():
    raw = _make_docx_bytes("Refunds are processed within 5 business days.")
    assert "Refunds are processed" in knowledge.extract_text("policy.docx", raw)


def test_extract_text_pdf_blank_page_does_not_raise():
    raw = _make_blank_pdf_bytes()
    assert knowledge.extract_text("blank.pdf", raw) == ""


def test_extract_text_unsupported_extension_raises():
    try:
        knowledge.extract_text("notes.txt", b"data")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_list_knowledge_files_filters_by_extension():
    drive_client = MagicMock()
    drive_client.files.return_value.list.return_value.execute.return_value = {
        "files": [
            {"id": "1", "name": "faq.pdf", "mimeType": "application/pdf"},
            {"id": "2", "name": "logo.png", "mimeType": "image/png"},
            {"id": "3", "name": "policy.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ]
    }
    files = knowledge.list_knowledge_files(drive_client)
    assert {f["id"] for f in files} == {"1", "3"}


def test_refresh_knowledge_cache_skips_download_on_cache_hit(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        '{"1": {"name": "faq.md", "version_key": "abc", "extracted_text": "old text"}}',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        knowledge,
        "list_knowledge_files",
        lambda drive_client: [{"id": "1", "name": "faq.md", "md5Checksum": "abc"}],
    )

    def _fail_download(*args, **kwargs):
        raise AssertionError("download_bytes should not be called on a cache hit")

    monkeypatch.setattr(knowledge, "download_bytes", _fail_download)

    result = knowledge.refresh_knowledge_cache(drive_client=MagicMock(), cache_path=str(cache_path))
    assert result["1"]["extracted_text"] == "old text"


def test_refresh_knowledge_cache_redownloads_on_version_change(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        '{"1": {"name": "faq.md", "version_key": "old-checksum", "extracted_text": "old text"}}',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        knowledge,
        "list_knowledge_files",
        lambda drive_client: [{"id": "1", "name": "faq.md", "md5Checksum": "new-checksum"}],
    )
    monkeypatch.setattr(knowledge, "download_bytes", lambda drive_client, file_id: b"new text")

    result = knowledge.refresh_knowledge_cache(drive_client=MagicMock(), cache_path=str(cache_path))
    assert result["1"]["extracted_text"] == "new text"
    assert result["1"]["version_key"] == "new-checksum"


def test_get_knowledge_blob_concatenates_all_docs():
    cache = {
        "1": {"name": "a.md", "version_key": "x", "extracted_text": "Alpha"},
        "2": {"name": "b.md", "version_key": "y", "extracted_text": "Beta"},
    }
    blob = knowledge.get_knowledge_blob(cache)
    assert "Alpha" in blob and "Beta" in blob
