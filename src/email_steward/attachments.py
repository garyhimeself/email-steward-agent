"""Fail-closed temporary materialization for safe email attachments."""

from __future__ import annotations

from email.message import Message
from io import BytesIO
from pathlib import Path
import re
import shutil
import unicodedata
from zipfile import BadZipFile, ZipFile


_ALLOWED_TYPES_BY_EXTENSION = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".csv": {"text/csv"},
    ".txt": {"text/plain"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
    ".bmp": {"image/bmp"},
    ".tif": {"image/tiff"},
    ".tiff": {"image/tiff"},
}
_MIME_TOKEN = r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+"
_MIME_PARAMETER_VALUE = rf'(?:{_MIME_TOKEN}|"(?:[^"\\\r\n]|\\.)*")'
_DECLARED_MIME = re.compile(
    rf"^{_MIME_TOKEN}/{_MIME_TOKEN}(?:\s*;\s*{_MIME_TOKEN}\s*=\s*{_MIME_PARAMETER_VALUE})*\s*$"
)

# These are intentionally conservative local-viewing limits.  The complete
# encoded payload is bounded before decoding, and the decoded bytes are bounded
# again before any file is created.  They protect both a single message and the
# operator's temporary workspace from accidental or hostile large attachments.
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_TOTAL_ATTACHMENT_BYTES = 50 * 1024 * 1024
MAX_OOXML_DECLARED_BYTES = 64 * 1024 * 1024
MAX_OOXML_ENTRIES = 256


def safe_attachment_paths(message: Message, temp_dir: Path) -> list[Path]:
    """Materialize only explicitly allowed attachment types in ``temp_dir``.

    The source message remains untouched.  Every accepted part must have both an
    allowlisted extension and the matching MIME type; all other parts are simply
    left in the message and are never written to disk.
    """
    if not isinstance(message, Message):
        raise TypeError("message must be an email Message")
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    total_bytes = 0
    try:
        candidates = list(_allowed_attachment_parts(message))
        _preflight_attachment_sizes(candidates)
        for part, normalized_name, extension in candidates:
            payload = part.get_payload(decode=True)
            if not isinstance(payload, bytes):
                continue
            if len(payload) > MAX_ATTACHMENT_BYTES:
                raise ValueError("single attachment exceeds the safe size limit")
            if total_bytes + len(payload) > MAX_TOTAL_ATTACHMENT_BYTES:
                raise ValueError("total attachment size exceeds the safe limit")
            if not _payload_matches_signature(extension, payload):
                continue
            paths.append(_write_unique(temp_dir, normalized_name, payload))
            total_bytes += len(payload)
    except Exception:
        for path in paths:
            path.unlink(missing_ok=True)
        raise
    return paths


def _allowed_attachment_parts(message: Message):
    """Yield allowlisted candidates without decoding their transfer bodies."""
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if filename is None:
            continue
        normalized_name, extension = _normalize_filename(filename)
        declared_type = _declared_content_type(part)
        if declared_type in _ALLOWED_TYPES_BY_EXTENSION.get(extension, set()):
            yield part, normalized_name, extension


def _preflight_attachment_sizes(candidates) -> None:
    """Reject unsafe messages before decoding or writing any candidate body."""
    total_upper_bound = 0
    for part, _, _ in candidates:
        upper_bound = _decoded_payload_upper_bound(part)
        if upper_bound is None or upper_bound > MAX_ATTACHMENT_BYTES:
            raise ValueError("single attachment exceeds the safe size limit")
        total_upper_bound += upper_bound
        if total_upper_bound > MAX_TOTAL_ATTACHMENT_BYTES:
            raise ValueError("total attachment size exceeds the safe limit")


def cleanup_temp_files(temp_dir: Path) -> None:
    """Remove a temporary attachment directory and every byte beneath it."""
    temp_dir = Path(temp_dir)
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def _normalize_filename(value: object) -> tuple[str, str]:
    """Return a portable basename made only of safe filename characters."""
    if not isinstance(value, str):
        raise TypeError("attachment filename must be text")
    basename = unicodedata.normalize("NFKC", value).replace("\\", "/").rsplit("/", 1)[-1]
    basename = basename.replace("\x00", "")
    stem, separator, suffix = basename.rpartition(".")
    extension = f".{suffix.lower()}" if separator and stem else ""
    safe_stem = re.sub(r"[^\w]+", "_", stem if separator else basename, flags=re.UNICODE).strip("._")
    if not safe_stem:
        safe_stem = "attachment"
    return f"{safe_stem}{extension}", extension


def _declared_content_type(part: Message) -> str | None:
    """Return an explicitly and syntactically declared MIME type, or nothing."""
    raw_value = part.get("Content-Type")
    if raw_value is None:
        return None
    raw_text = str(raw_value).strip()
    if _DECLARED_MIME.fullmatch(raw_text) is None:
        return None
    declared_type = raw_text.split(";", 1)[0].strip().lower()
    if part.get_content_type().lower() != declared_type:
        return None
    return declared_type


def _payload_matches_signature(extension: str, payload: bytes) -> bool:
    """Validate the minimum safe signature for an explicitly allowed format."""
    if extension == ".pdf":
        return payload.startswith(b"%PDF-")
    if extension == ".docx":
        return _is_ooxml(payload, "word/")
    if extension == ".xlsx":
        return _is_ooxml(payload, "xl/")
    if extension in {".csv", ".txt"}:
        return _is_plain_utf8_text(payload)
    if extension == ".png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return payload.startswith(b"\xff\xd8\xff") and payload.endswith(b"\xff\xd9")
    if extension == ".gif":
        return payload.startswith((b"GIF87a", b"GIF89a"))
    if extension == ".webp":
        return len(payload) >= 12 and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP"
    if extension == ".bmp":
        return payload.startswith(b"BM")
    if extension in {".tif", ".tiff"}:
        return payload.startswith((b"II*\x00", b"MM\x00*"))
    return False


def _decoded_payload_upper_bound(part: Message) -> int | None:
    """Return a conservative decoded-byte upper bound without decoding a body."""
    encoded = part.get_payload(decode=False)
    if not isinstance(encoded, (str, bytes)):
        return None
    encoded_bytes = encoded.encode("utf-8") if isinstance(encoded, str) else encoded
    encoded_length = len(encoded_bytes)
    transfer_encoding = str(part.get("Content-Transfer-Encoding", "")).strip().lower()
    if transfer_encoding == "base64":
        base64_length = len(encoded_bytes.translate(None, b" \t\r\n"))
        return ((base64_length + 3) // 4) * 3
    return encoded_length


def _is_ooxml(payload: bytes, required_directory: str) -> bool:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_OOXML_ENTRIES or any(entry.file_size > MAX_OOXML_DECLARED_BYTES for entry in entries):
                return False
            if sum(entry.file_size for entry in entries) > MAX_OOXML_DECLARED_BYTES:
                return False
            names = {entry.filename for entry in entries}
    except (BadZipFile, OSError):
        return False
    return "[Content_Types].xml" in names and any(name.startswith(required_directory) for name in names)


def _is_plain_utf8_text(payload: bytes) -> bool:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return "\x00" not in text and all(character >= " " or character in "\t\r\n" for character in text)


def _write_unique(temp_dir: Path, filename: str, payload: bytes) -> Path:
    base = temp_dir / filename
    candidate = base
    counter = 2
    while candidate.exists():
        candidate = base.with_name(f"{base.stem}_{counter}{base.suffix}")
        counter += 1
    with candidate.open("xb") as output:
        output.write(payload)
    return candidate
