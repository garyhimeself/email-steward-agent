"""Narrow, read-only IMAP search and message retrieval primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from email import policy
from email.message import Message
from email.parser import BytesParser
import re
from typing import Protocol, TypeAlias


ImapResponse: TypeAlias = tuple[object, object]


class ReadOnlyImapClient(Protocol):
    """The deliberately small subset of an IMAP client this module needs."""

    def select(self, folder: str, readonly: bool = True) -> ImapResponse: ...

    def uid(self, command: str, *arguments: object) -> ImapResponse: ...

    def response(self, code: str) -> ImapResponse: ...


class ImapReadError(RuntimeError):
    """A mailbox could not be safely queried or read."""


class UIDValidityUnavailableError(ImapReadError):
    """UIDVALIDITY is missing or does not match the requested message identity."""


@dataclass(frozen=True)
class MailIdentity:
    """A stable IMAP message identity within one folder incarnation."""

    folder: str
    uidvalidity: int
    uid: int

    def __post_init__(self) -> None:
        _validate_folder(self.folder)
        if isinstance(self.uidvalidity, bool) or not isinstance(self.uidvalidity, int) or self.uidvalidity < 1:
            raise ValueError("uidvalidity must be a positive integer")
        if isinstance(self.uid, bool) or not isinstance(self.uid, int) or self.uid < 1:
            raise ValueError("uid must be a positive integer")


@dataclass(frozen=True)
class AttachmentRecord:
    """Safe metadata about an attachment; the attachment bytes are never retained."""

    filename: str | None
    content_type: str
    size: int


@dataclass(frozen=True)
class MessageRecord:
    """The readable message data needed for on-screen review and drafting."""

    identity: MailIdentity
    sender: str | None
    to: str | None
    cc: str | None
    subject: str | None
    date: str | None
    message_id: str | None
    references: str | None
    plain_text: str
    attachments: tuple[AttachmentRecord, ...]


_STRING_CRITERIA = {"subject": "SUBJECT", "from": "FROM", "to": "TO", "cc": "CC"}
_DATE_CRITERIA = {"since": "SINCE", "before": "BEFORE"}
_ALLOWED_CRITERIA = {*_STRING_CRITERIA, *_DATE_CRITERIA, "unseen"}


def search_mail(
    client: ReadOnlyImapClient,
    folder: str,
    criteria: Mapping[str, object],
) -> list[MailIdentity]:
    """Search a deliberately constrained mailbox scope using IMAP UIDs only."""
    _validate_folder(folder)
    search_scope = _build_search_scope(criteria)
    uidvalidity = _select_and_uidvalidity(client, folder)
    status, data = client.uid("SEARCH", None, search_scope)
    _require_ok(status, "UID SEARCH")
    return [
        MailIdentity(folder=folder, uidvalidity=uidvalidity, uid=uid)
        for uid in _parse_uid_list(data)
    ]


def read_mail(client: ReadOnlyImapClient, identity: MailIdentity) -> MessageRecord:
    """Retrieve one known UID without marking it read or touching attachments."""
    if not isinstance(identity, MailIdentity):
        raise TypeError("identity must be a MailIdentity")

    selected_uidvalidity = _select_and_uidvalidity(client, identity.folder)
    if selected_uidvalidity != identity.uidvalidity:
        raise UIDValidityUnavailableError(
            "The folder UIDVALIDITY changed, so this message identity is no longer safe to read."
        )

    status, data = client.uid("FETCH", str(identity.uid), "(BODY.PEEK[] RFC822.SIZE)")
    _require_ok(status, "UID FETCH")
    raw_message = _extract_raw_message(data, expected_uid=identity.uid)
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    plain_text, attachments = _extract_safe_content(message)
    return MessageRecord(
        identity=identity,
        sender=_header(message, "From"),
        to=_header(message, "To"),
        cc=_header(message, "Cc"),
        subject=_header(message, "Subject"),
        date=_header(message, "Date"),
        message_id=_header(message, "Message-ID"),
        references=_header(message, "References"),
        plain_text=plain_text,
        attachments=attachments,
    )


def _select_and_uidvalidity(client: ReadOnlyImapClient, folder: str) -> int:
    status, _ = client.select(folder, readonly=True)
    _require_ok(status, "readonly folder selection")
    _, data = client.response("UIDVALIDITY")
    uidvalidity = _parse_single_positive_int(data)
    if uidvalidity is None:
        raise UIDValidityUnavailableError(
            "The server did not provide UIDVALIDITY, so the mailbox cannot be read safely."
        )
    return uidvalidity


def _build_search_scope(criteria: Mapping[str, object]) -> str:
    if not isinstance(criteria, Mapping):
        raise TypeError("criteria must be a mapping")
    unknown = set(criteria) - _ALLOWED_CRITERIA
    if unknown:
        raise ValueError(f"unsupported search criterion: {', '.join(sorted(unknown))}")

    terms: list[str] = []
    for field, imap_name in _DATE_CRITERIA.items():
        if field in criteria:
            terms.append(f"{imap_name} {_format_imap_date(criteria[field], field)}")
    for field, imap_name in _STRING_CRITERIA.items():
        if field in criteria:
            terms.append(f'{imap_name} "{_format_imap_string(criteria[field], field)}"')
    if "unseen" in criteria:
        if not isinstance(criteria["unseen"], bool):
            raise ValueError("unseen must be true or false")
        if criteria["unseen"]:
            terms.append("UNSEEN")

    if not terms:
        raise ValueError("at least one search criterion is required; full-folder searches are not allowed")
    return f"({' '.join(terms)})"


def _format_imap_date(value: object, field: str) -> str:
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD)") from error
    if not isinstance(value, date):
        raise ValueError(f"{field} must be a date or ISO date string")
    return value.strftime("%d-%b-%Y")


def _format_imap_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    value = value.strip()
    if any(character in value for character in ("\r", "\n", "\x00")):
        raise ValueError(f"{field} contains an unsafe control character")
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _validate_folder(folder: object) -> None:
    if not isinstance(folder, str) or not folder.strip():
        raise ValueError("folder must be a non-empty string")
    if any(character in folder for character in ("\r", "\n", "\x00")):
        raise ValueError("folder contains an unsafe control character")


def _require_ok(status: object, operation: str) -> None:
    if status not in ("OK", b"OK"):
        raise ImapReadError(f"IMAP {operation} did not succeed")


def _parse_single_positive_int(data: object) -> int | None:
    values = _flatten_imap_data(data)
    for value in values:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None


def _parse_uid_list(data: object) -> list[int]:
    uids: list[int] = []
    for value in _flatten_imap_data(data):
        for token in str(value).split():
            try:
                uid = int(token)
            except ValueError as error:
                raise ImapReadError("UID SEARCH returned an invalid UID") from error
            if uid < 1:
                raise ImapReadError("UID SEARCH returned an invalid UID")
            uids.append(uid)
    return uids


def _flatten_imap_data(data: object) -> list[str]:
    if data is None:
        return []
    if isinstance(data, (bytes, str)):
        values = [data]
    elif isinstance(data, (list, tuple)):
        values = list(data)
    else:
        return []
    return [value.decode("ascii", errors="strict") if isinstance(value, bytes) else str(value) for value in values if value is not None]


def _extract_raw_message(data: object, *, expected_uid: int) -> bytes:
    if not isinstance(data, (list, tuple)):
        raise ImapReadError("UID FETCH returned no message data")
    matching_messages: list[bytes] = []
    for item in data:
        if not isinstance(item, tuple) or len(item) < 2 or not isinstance(item[1], bytes):
            continue
        metadata = item[0]
        if not isinstance(metadata, bytes):
            raise ImapReadError("UID FETCH response did not identify its UID")
        match = re.search(rb"(?:^|[\s(])UID\s+(\d+)(?:\s|\))", metadata)
        if match is None or int(match.group(1)) != expected_uid:
            raise ImapReadError("UID FETCH response UID does not match the requested identity")
        matching_messages.append(item[1])
    if len(matching_messages) != 1:
        raise ImapReadError("UID FETCH returned an unexpected number of matching messages")
    return matching_messages[0]


def _extract_safe_content(message: Message) -> tuple[str, tuple[AttachmentRecord, ...]]:
    plain_text_parts: list[str] = []
    attachments: list[AttachmentRecord] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        if disposition == "attachment" or filename is not None:
            payload = part.get_payload(decode=True) or b""
            attachments.append(
                AttachmentRecord(
                    filename=filename,
                    content_type=part.get_content_type(),
                    size=len(payload),
                )
            )
        elif part.get_content_type() == "text/plain":
            content = part.get_content()
            plain_text_parts.append(content if isinstance(content, str) else str(content))
    return "\n".join(part.strip() for part in plain_text_parts if part.strip()), tuple(attachments)


def _header(message: Message, name: str) -> str | None:
    value = message.get(name)
    return str(value) if value is not None else None
