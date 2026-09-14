"""One-shot SMTP delivery after an exact current-turn approval."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from .approval import ApprovalToken, consume_exact_approval, verify_exact_approval
from .drafting import Draft


class SmtpClient(Protocol):
    def send_message(
        self, message: EmailMessage, from_addr: str | None = None, to_addrs: tuple[str, ...] | None = None
    ) -> object: ...


@dataclass(frozen=True)
class SendResult:
    sent: bool
    uncertain: bool
    attempts: int
    detail: str | None = None


def send_one(client: SmtpClient, draft: Draft, token: ApprovalToken, current_turn_id: str) -> SendResult:
    """Make exactly one SMTP submission; uncertainty is reported, never retried."""
    if not isinstance(draft, Draft):
        raise TypeError("draft must be a Draft")
    verify_exact_approval(token, "send", draft, current_turn_id)
    message = EmailMessage()
    message["From"] = draft.source_identity
    message["To"] = ", ".join(draft.recipient)
    message["Cc"] = ", ".join(draft.cc)
    message["Subject"] = draft.subject
    if draft.message_id:
        message["In-Reply-To"] = draft.message_id
    if draft.references:
        message["References"] = draft.references
    message.set_content(draft.body)
    recipients = (*draft.recipient, *draft.cc, *draft.bcc)
    consume_exact_approval(token, "send", draft, current_turn_id)
    try:
        refused = client.send_message(message, from_addr=draft.source_identity, to_addrs=recipients)
    except Exception as error:
        return SendResult(sent=False, uncertain=True, attempts=1, detail=str(error))
    if refused:
        return SendResult(sent=False, uncertain=True, attempts=1, detail="SMTP delivery may be partial or refused")
    return SendResult(sent=True, uncertain=False, attempts=1)
