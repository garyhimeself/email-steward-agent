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

    for part in message.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if filename is None:
            continue
        normalized_name, extension = _normalize_filename(filename)
        declared_type = _declared_content_type(part)
        if declared_type not in _ALLOWED_TYPES_BY_EXTENSION.get(extension, set()):
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes) or not _payload_matches_signature(extension, payload):
            continue
        paths.append(_write_unique(temp_dir, normalized_name, payload))
    return paths


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


def _is_ooxml(payload: bytes, required_directory: str) -> bool:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > 256 or any(entry.file_size > 128 * 1024 * 1024 for entry in entries):
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
