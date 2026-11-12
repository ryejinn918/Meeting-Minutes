import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.errors import AppError

ALLOWED_TYPES = {
    ".mp3": {"audio/mpeg"},
    ".m4a": {"audio/mp4", "audio/x-m4a"},
    ".wav": {"audio/wav", "audio/x-wav"},
    ".txt": {"text/plain"},
    ".pdf": {"application/pdf"},
}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav"}
DOCUMENT_EXTENSIONS = {".txt", ".pdf"}


@dataclass(frozen=True)
class ValidatedFile:
    extension: str
    source_type: str
    job_type: str
    canonical_mime: str
    sha256: str


def validate_upload_metadata(
    filename: str,
    content_type: str,
    size_bytes: int,
    *,
    max_audio_bytes: int,
    max_document_bytes: int,
) -> tuple[str, str, str]:
    extension = Path(filename).suffix.lower()
    allowed_mimes = ALLOWED_TYPES.get(extension)
    if allowed_mimes is None or content_type.lower() not in allowed_mimes:
        raise AppError(415, "FILE_TYPE_NOT_ALLOWED", "지원하지 않는 파일 형식입니다.")
    if extension in AUDIO_EXTENSIONS:
        if size_bytes > max_audio_bytes:
            limit_mb = max_audio_bytes // (1024 * 1024)
            raise AppError(
                413,
                "FILE_TOO_LARGE",
                f"음성파일은 {limit_mb}MB 이하만 업로드할 수 있습니다.",
            )
        return extension, "audio", "transcribe"
    if size_bytes > max_document_bytes:
        raise AppError(413, "FILE_TOO_LARGE", "문서 파일은 10MB 이하만 업로드할 수 있습니다.")
    return extension, extension.removeprefix("."), "extract"


def validate_file_bytes(
    content: bytes,
    *,
    filename: str,
    claimed_mime: str,
    expected_size: int,
    expected_sha256: str,
    max_audio_bytes: int,
    max_document_bytes: int,
) -> ValidatedFile:
    if not content:
        raise AppError(422, "FILE_EMPTY", "빈 파일은 처리할 수 없습니다.")
    extension, source_type, job_type = validate_upload_metadata(
        filename,
        claimed_mime,
        len(content),
        max_audio_bytes=max_audio_bytes,
        max_document_bytes=max_document_bytes,
    )
    if len(content) != expected_size:
        raise AppError(422, "FILE_SIZE_MISMATCH", "업로드된 파일 크기가 일치하지 않습니다.")
    digest = hashlib.sha256(content).hexdigest()
    if digest != expected_sha256:
        raise AppError(422, "FILE_HASH_MISMATCH", "업로드된 파일을 확인하지 못했습니다.")
    valid_signature = {
        ".pdf": content.startswith(b"%PDF-"),
        ".txt": b"\x00" not in content[:8192],
        ".wav": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE",
        ".m4a": len(content) >= 12 and content[4:8] == b"ftyp",
        ".mp3": content.startswith(b"ID3")
        or (len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0),
    }[extension]
    if not valid_signature:
        raise AppError(415, "FILE_CONTENT_INVALID", "파일 형식과 실제 내용이 일치하지 않습니다.")
    return ValidatedFile(
        extension=extension,
        source_type=source_type,
        job_type=job_type,
        canonical_mime=claimed_mime.lower(),
        sha256=digest,
    )


def validate_file_path(
    path: Path,
    *,
    filename: str,
    claimed_mime: str,
    expected_size: int,
    expected_sha256: str,
    max_audio_bytes: int,
    max_document_bytes: int,
) -> ValidatedFile:
    actual_size = path.stat().st_size
    if actual_size == 0:
        raise AppError(422, "FILE_EMPTY", "빈 파일은 처리할 수 없습니다.")
    extension, source_type, job_type = validate_upload_metadata(
        filename,
        claimed_mime,
        actual_size,
        max_audio_bytes=max_audio_bytes,
        max_document_bytes=max_document_bytes,
    )
    if actual_size != expected_size:
        raise AppError(422, "FILE_SIZE_MISMATCH", "업로드된 파일 크기가 일치하지 않습니다.")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        signature = handle.read(8192)
        digest.update(signature)
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise AppError(422, "FILE_HASH_MISMATCH", "업로드된 파일을 확인하지 못했습니다.")
    valid_signature = {
        ".pdf": signature.startswith(b"%PDF-"),
        ".txt": b"\x00" not in signature,
        ".wav": len(signature) >= 12
        and signature[:4] == b"RIFF"
        and signature[8:12] == b"WAVE",
        ".m4a": len(signature) >= 12 and signature[4:8] == b"ftyp",
        ".mp3": signature.startswith(b"ID3")
        or (
            len(signature) >= 2
            and signature[0] == 0xFF
            and signature[1] & 0xE0 == 0xE0
        ),
    }[extension]
    if not valid_signature:
        raise AppError(
            415,
            "FILE_CONTENT_INVALID",
            "파일 형식과 실제 내용이 일치하지 않습니다.",
        )
    return ValidatedFile(
        extension=extension,
        source_type=source_type,
        job_type=job_type,
        canonical_mime=claimed_mime.lower(),
        sha256=digest.hexdigest(),
    )


def extract_document_text(content: bytes, extension: str, *, max_pdf_pages: int) -> str:
    if extension == ".txt":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise AppError(
                422,
                "TEXT_ENCODING_INVALID",
                "TXT 파일은 UTF-8 형식으로 저장해 주세요.",
            ) from exc
    elif extension == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise AppError(422, "PDF_ENCRYPTED", "암호화된 PDF는 처리할 수 없습니다.")
            if len(reader.pages) > max_pdf_pages:
                raise AppError(413, "PDF_TOO_MANY_PAGES", "PDF 페이지 수가 너무 많습니다.")
            text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)
        except AppError:
            raise
        except (PdfReadError, ValueError, TypeError) as exc:
            raise AppError(422, "PDF_DAMAGED", "손상된 PDF는 처리할 수 없습니다.") from exc
    else:
        raise AppError(415, "FILE_TYPE_NOT_ALLOWED", "지원하지 않는 문서 형식입니다.")
    normalized = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n").replace("\r", "\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        message = (
            "이 PDF에서는 텍스트를 읽을 수 없어요. 텍스트가 포함된 PDF를 업로드해 주세요."
            if extension == ".pdf"
            else "TXT 파일에 회의 내용이 없습니다."
        )
        raise AppError(422, "DOCUMENT_TEXT_EMPTY", message)
    return normalized
