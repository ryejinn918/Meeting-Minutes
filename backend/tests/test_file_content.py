import hashlib

import pytest

from app.core.errors import AppError
from app.services.file_content import (
    extract_document_text,
    validate_file_bytes,
    validate_upload_metadata,
)


@pytest.mark.parametrize(
    ("filename", "mime", "content", "source", "job_type"),
    [
        ("meeting.mp3", "audio/mpeg", b"ID3" + b"x" * 32, "audio", "transcribe"),
        (
            "meeting.m4a",
            "audio/mp4",
            b"\x00\x00\x00\x18ftypM4A " + b"x" * 24,
            "audio",
            "transcribe",
        ),
        (
            "meeting.wav",
            "audio/wav",
            b"RIFF\x24\x00\x00\x00WAVE" + b"x" * 24,
            "audio",
            "transcribe",
        ),
        ("meeting.txt", "text/plain", "회의 내용".encode(), "txt", "extract"),
        ("meeting.pdf", "application/pdf", b"%PDF-1.7\ncontent", "pdf", "extract"),
    ],
)
def test_supported_file_signatures(
    filename: str, mime: str, content: bytes, source: str, job_type: str
) -> None:
    digest = hashlib.sha256(content).hexdigest()

    result = validate_file_bytes(
        content,
        filename=filename,
        claimed_mime=mime,
        expected_size=len(content),
        expected_sha256=digest,
        max_audio_bytes=26_214_400,
        max_document_bytes=10_485_760,
    )

    assert result.source_type == source
    assert result.job_type == job_type


def test_rejects_empty_corrupt_and_hash_mismatch() -> None:
    with pytest.raises(AppError) as empty:
        validate_file_bytes(
            b"",
            filename="empty.txt",
            claimed_mime="text/plain",
            expected_size=0,
            expected_sha256=hashlib.sha256(b"").hexdigest(),
            max_audio_bytes=100,
            max_document_bytes=100,
        )
    assert empty.value.code == "FILE_EMPTY"

    content = b"not-an-mp3"
    with pytest.raises(AppError) as corrupt:
        validate_file_bytes(
            content,
            filename="bad.mp3",
            claimed_mime="audio/mpeg",
            expected_size=len(content),
            expected_sha256=hashlib.sha256(content).hexdigest(),
            max_audio_bytes=100,
            max_document_bytes=100,
        )
    assert corrupt.value.code == "FILE_CONTENT_INVALID"

    with pytest.raises(AppError) as mismatch:
        validate_file_bytes(
            b"hello",
            filename="meeting.txt",
            claimed_mime="text/plain",
            expected_size=5,
            expected_sha256="0" * 64,
            max_audio_bytes=100,
            max_document_bytes=100,
        )
    assert mismatch.value.code == "FILE_HASH_MISMATCH"


def test_metadata_rejects_oversized_and_mismatched_mime() -> None:
    with pytest.raises(AppError) as oversized:
        validate_upload_metadata(
            "meeting.wav",
            "audio/wav",
            101,
            max_audio_bytes=100,
            max_document_bytes=100,
        )
    assert oversized.value.code == "FILE_TOO_LARGE"

    with pytest.raises(AppError) as mismatched:
        validate_upload_metadata(
            "meeting.pdf",
            "text/plain",
            50,
            max_audio_bytes=100,
            max_document_bytes=100,
        )
    assert mismatched.value.code == "FILE_TYPE_NOT_ALLOWED"


def test_metadata_accepts_audio_over_openai_single_request_limit() -> None:
    extension, source_type, job_type = validate_upload_metadata(
        "long-meeting.m4a",
        "audio/mp4",
        30 * 1024 * 1024,
        max_audio_bytes=50 * 1024 * 1024,
        max_document_bytes=10 * 1024 * 1024,
    )

    assert (extension, source_type, job_type) == (".m4a", "audio", "transcribe")


def test_txt_utf8_bom_and_whitespace_are_normalized() -> None:
    text = extract_document_text(
        "\ufeff회의  내용\r\n\r\n\r\n결정".encode(),
        ".txt",
        max_pdf_pages=200,
    )
    assert text == "회의 내용\n\n결정"


def test_pdf_pages_are_joined_and_empty_pdf_has_friendly_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class Reader:
        is_encrypted = False
        pages = [Page("첫 페이지"), Page("둘째 페이지")]

    monkeypatch.setattr("app.services.file_content.PdfReader", lambda _: Reader())
    assert extract_document_text(b"%PDF-", ".pdf", max_pdf_pages=10) == "첫 페이지\n\n둘째 페이지"

    Reader.pages = [Page("")]
    with pytest.raises(AppError) as error:
        extract_document_text(b"%PDF-", ".pdf", max_pdf_pages=10)
    assert error.value.code == "DOCUMENT_TEXT_EMPTY"
    assert "텍스트가 포함된 PDF" in error.value.message
