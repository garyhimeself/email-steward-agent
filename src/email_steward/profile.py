"""Validation and local persistence for one operator's mailbox profile."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import tempfile


DEFAULT_IMAP_HOST = "imap.qiye.aliyun.com"
DEFAULT_IMAP_PORT = 993
DEFAULT_SMTP_HOST = "smtp.qiye.aliyun.com"
DEFAULT_SMTP_PORT = 465

_PROFILE_FIELDS = {
    "name",
    "email",
    "preferred_language",
    "reply_language",
    "reply_tone",
    "imap_host",
    "imap_port",
    "smtp_host",
    "smtp_port",
}
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class OperatorProfile:
    """The non-secret settings for one personal Alibaba mailbox."""

    name: str
    email: str
    preferred_language: str
    reply_language: str
    reply_tone: str
    imap_host: str = DEFAULT_IMAP_HOST
    imap_port: int = DEFAULT_IMAP_PORT
    smtp_host: str = DEFAULT_SMTP_HOST
    smtp_port: int = DEFAULT_SMTP_PORT


def validate_profile(
    data: Mapping[str, object], *, allow_advanced_servers: bool = False
) -> OperatorProfile:
    """Validate one operator profile, using Alibaba SSL endpoints by default."""
    if not isinstance(data, Mapping):
        raise ValueError("profile must be a mapping")

    unknown_fields = set(data) - _PROFILE_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(str(field) for field in unknown_fields))
        raise ValueError(f"unsupported profile field(s): {fields}")

    values: dict[str, str] = {}
    for field in ("name", "email", "preferred_language", "reply_language", "reply_tone"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required")
        values[field] = value.strip()

    if not _EMAIL_PATTERN.fullmatch(values["email"]):
        raise ValueError("email must be a valid single mailbox address")

    imap_host = _server_host(data.get("imap_host", DEFAULT_IMAP_HOST), "imap_host")
    imap_port = _server_port(data.get("imap_port", DEFAULT_IMAP_PORT), "imap_port")
    smtp_host = _server_host(data.get("smtp_host", DEFAULT_SMTP_HOST), "smtp_host")
    smtp_port = _server_port(data.get("smtp_port", DEFAULT_SMTP_PORT), "smtp_port")
    if not allow_advanced_servers and (
        imap_host != DEFAULT_IMAP_HOST
        or imap_port != DEFAULT_IMAP_PORT
        or smtp_host != DEFAULT_SMTP_HOST
        or smtp_port != DEFAULT_SMTP_PORT
    ):
        raise ValueError("server overrides require allow_advanced_servers=True")

    return OperatorProfile(
        **values,
        imap_host=imap_host,
        imap_port=imap_port,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
    )


def save_profile(
    profile: OperatorProfile,
    path: str | Path,
    *,
    allow_advanced_servers: bool = False,
) -> None:
    """Atomically save only the profile fields as UTF-8 JSON."""
    if not isinstance(profile, OperatorProfile):
        raise TypeError("profile must be an OperatorProfile")
    validated_profile = validate_profile(
        asdict(profile), allow_advanced_servers=allow_advanced_servers
    )

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(asdict(validated_profile), temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, target)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _server_host(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty hostname")
    host = value.strip()
    if any(character.isspace() for character in host) or "://" in host or "/" in host:
        raise ValueError(f"{field} must be a hostname, without a URL or path")
    return host


def _server_port(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ValueError(f"{field} must be an integer from 1 to 65535")
    return value
