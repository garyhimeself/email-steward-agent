"""One explicit, identity-bound IMAP star operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .approval import ApprovalToken, consume_exact_approval, verify_exact_approval
from .imap_read import ImapReadError, MailIdentity, UIDValidityUnavailableError


class FlagImapClient(Protocol):
    def select(self, folder: str, readonly: bool = False) -> tuple[object, object]: ...

    def response(self, code: str) -> tuple[object, object]: ...

    def uid(self, command: str, *arguments: object) -> tuple[object, object]: ...


@dataclass(frozen=True)
class StarResult:
    starred: bool
    uncertain: bool = False


def star_one(client: FlagImapClient, identity: MailIdentity, token: ApprovalToken, current_turn_id: str) -> StarResult:
    """Add exactly one \"\\Flagged\" flag only after exact confirmation."""
    if not isinstance(identity, MailIdentity):
        raise TypeError("identity must be a MailIdentity")
    verify_exact_approval(token, "star", identity, current_turn_id)
    status, _ = client.select(identity.folder, readonly=False)
    _require_ok(status, "folder selection")
    _, values = client.response("UIDVALIDITY")
    if _uidvalidity(values) != identity.uidvalidity:
        raise UIDValidityUnavailableError("The folder UIDVALIDITY changed, so this message cannot be starred safely.")
    consume_exact_approval(token, "star", identity, current_turn_id)
    status, _ = client.uid("STORE", str(identity.uid), "+FLAGS.SILENT", "(\\Flagged)")
    _require_ok(status, "UID STORE")
    return StarResult(starred=True)


def _require_ok(status: object, operation: str) -> None:
    if status not in ("OK", b"OK"):
        raise ImapReadError(f"IMAP {operation} did not succeed")


def _uidvalidity(values: object) -> int | None:
    if not isinstance(values, (tuple, list)):
        values = (values,)
    for value in values:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None
