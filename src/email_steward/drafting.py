"""Immutable email drafts and a hand-off prompt for the Codex humanizer Skill."""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import getaddresses

from .imap_read import MessageRecord


class ReplyDraftError(ValueError):
    """A reply cannot be safely tied to its source email."""


_LOCAL_ALLOWED = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'*+-/=?^_`{|}~.")


@dataclass(frozen=True)
class Draft:
    """One reviewable, unsent message.  This object never sends itself."""

    recipient: tuple[str, ...]
    cc: tuple[str, ...]
    bcc: tuple[str, ...]
    subject: str
    body: str
    source_identity: str
    message_id: str | None
    references: str | None
    status: str = "unsent"
    sent: bool = False

    def __post_init__(self) -> None:
        recipients = {
            "recipient": self.recipient,
            "cc": self.cc,
            "bcc": self.bcc,
        }
        normalized: dict[str, tuple[str, ...]] = {}
        for field, values in recipients.items():
            if not isinstance(values, tuple) or (field == "recipient" and not values):
                raise ValueError(f"{field} must be a tuple of email addresses; recipient cannot be empty")
            normalized[field] = tuple(_normalize_address(value, field) for value in values)
            object.__setattr__(self, field, normalized[field])
        all_recipients = (*normalized["recipient"], *normalized["cc"], *normalized["bcc"])
        if len(set(all_recipients)) != len(all_recipients):
            raise ValueError("recipient, cc, and bcc addresses must not be duplicated")
        if not isinstance(self.subject, str) or not self.subject.strip() or _unsafe_text(self.subject):
            raise ValueError("subject must be non-empty plain header text")
        if not isinstance(self.body, str) or not self.body.strip():
            raise ValueError("body must be non-empty text")
        if "\x00" in self.body:
            raise ValueError("body contains an unsafe control character")
        object.__setattr__(self, "source_identity", _normalize_address(self.source_identity, "source_identity"))
        for field in ("message_id", "references"):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, str) or not value.strip() or _unsafe_text(value)):
                raise ValueError(f"{field} must be safe text or None")
        if self.status != "unsent" or self.sent is not False:
            raise ValueError("a Draft must remain unsent")


def reply_draft(
    message: MessageRecord,
    body: str,
    source_identity: str,
    *,
    reply_all: bool = False,
    bcc: tuple[str, ...] = (),
) -> Draft:
    """Build a reply from one read-only message; never infer a thread without Message-ID."""
    if not isinstance(message, MessageRecord):
        raise TypeError("message must be a MessageRecord")
    if not message.message_id:
        raise ReplyDraftError("The source email has no Message-ID, so a reply cannot be linked safely.")
    sender = _addresses(message.sender)
    if not sender:
        raise ReplyDraftError("The source email has no usable sender address.")
    source_identity = _normalize_address(source_identity, "source_identity")
    recipient = (sender[0],)
    cc: tuple[str, ...] = ()
    if reply_all:
        cc = tuple(
            address
            for address in (*_addresses(message.to), *_addresses(message.cc))
            if address not in {source_identity, *recipient}
        )
        cc = tuple(dict.fromkeys(cc))
    subject = message.subject.strip() if isinstance(message.subject, str) and message.subject.strip() else "(no subject)"
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    reference_items = [item for item in (message.references, message.message_id) if item]
    references = " ".join(dict.fromkeys(reference_items))
    return Draft(
        recipient=recipient,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        source_identity=source_identity,
        message_id=message.message_id,
        references=references,
    )


def humanization_request(draft: Draft, writing_sample: str | None = None) -> str:
    """Return instructions for Codex's humanizer Skill; Python does no rewriting."""
    if not isinstance(draft, Draft):
        raise TypeError("draft must be a Draft")
    sample_section = ""
    if writing_sample is not None:
        if not isinstance(writing_sample, str) or not writing_sample.strip():
            raise ValueError("writing_sample must be non-empty text when provided")
        sample_section = f"\nWriting sample to match when appropriate:\n{writing_sample}\n"
    return (
        "Use the Codex humanizer Skill to revise only the wording of this email draft. "
        "Preserve all facts, money, dates, commitments, recipient lists, source identity, "
        "subject meaning, thread identifiers, and language. Do not add promises, change a "
        "business decision, translate the message, or send it. Return a revised draft for "
        "fresh operator approval.\n"
        f"To: {', '.join(draft.recipient)}\nCc: {', '.join(draft.cc)}\nBcc: {', '.join(draft.bcc)}\n"
        f"Subject: {draft.subject}\nBody:\n{draft.body}\n{sample_section}"
    )


def _addresses(header: str | None) -> tuple[str, ...]:
    if not header:
        return ()
    return tuple(
        normalized
        for _, address in getaddresses([header])
        if address and (normalized := _normalize_address(address, "message address"))
    )


def _normalize_address(value: object, field: str) -> str:
    if not isinstance(value, str) or _unsafe_text(value):
        raise ValueError(f"{field} must be a safe email address")
    if value != value.strip() or not value.isascii() or value.count("@") != 1:
        raise ValueError(f"{field} must be a valid single email address")
    local_part, domain = value.rsplit("@", 1)
    if (
        not local_part
        or len(local_part) > 64
        or local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
        or any(character not in _LOCAL_ALLOWED for character in local_part)
    ):
        raise ValueError(f"{field} must be a valid single email address")

    labels = domain.split(".")
    if len(domain) > 253 or len(labels) < 2 or any(not _valid_domain_label(label) for label in labels):
        raise ValueError(f"{field} must be a valid single email address")

    # ASCII-only lowercasing is deterministic and cannot change the local part.
    return f"{local_part}@{domain.lower()}"


def _valid_domain_label(label: str) -> bool:
    return (
        bool(label)
        and len(label) <= 63
        and not label.startswith("-")
        and not label.endswith("-")
        and all(character.isascii() and (character.isalnum() or character == "-") for character in label)
    )


def _unsafe_text(value: str) -> bool:
    return any(character in value for character in ("\r", "\n", "\x00"))
