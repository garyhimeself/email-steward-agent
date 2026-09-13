"""Fail-closed temporary materialization for safe email attachments."""

from __future__ import annotations

from email.message import Message
from pathlib import Path
import re
import shutil
import unicodedata


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
        if part.get_content_type().lower() not in _ALLOWED_TYPES_BY_EXTENSION.get(extension, set()):
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
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
