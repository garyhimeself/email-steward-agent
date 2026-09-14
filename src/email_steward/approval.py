"""Exact, current-turn approvals for the agent's only write actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json

from .drafting import Draft
from .imap_read import MailIdentity


class ApprovalError(ValueError):
    """The operator has not approved this exact, current action."""


_ACTIONS = {"send", "star"}


@dataclass(frozen=True)
class ApprovalToken:
    action: str
    subject_fingerprint: str
    current_turn_id: str

    @classmethod
    def for_action(
        cls, action: str, subject: object, current_turn_id: str, *, confirmation: str
    ) -> "ApprovalToken":
        _validate_action(action)
        _validate_turn(current_turn_id)
        if not isinstance(confirmation, str) or confirmation.strip().upper() != action.upper():
            raise ApprovalError(f"explicit {action} confirmation is required")
        return cls(action, _fingerprint_subject(subject), current_turn_id)


def verify_exact_approval(
    token: ApprovalToken, action: str, subject: object, current_turn_id: str
) -> None:
    """Fail closed unless action, subject, and current conversation turn are unchanged."""
    if not isinstance(token, ApprovalToken):
        raise ApprovalError("a valid approval token is required")
    _validate_action(action)
    _validate_turn(current_turn_id)
    if token.action != action or token.current_turn_id != current_turn_id:
        raise ApprovalError("approval is stale or for a different action")
    if token.subject_fingerprint != _fingerprint_subject(subject):
        raise ApprovalError("approval no longer matches this exact item")


def _fingerprint_subject(subject: object) -> str:
    if isinstance(subject, (tuple, list, set, frozenset)):
        raise ApprovalError("approval can cover one exact item, never a batch")
    if not isinstance(subject, (Draft, MailIdentity)):
        raise ApprovalError("approval subject must be one Draft or MailIdentity")
    if not is_dataclass(subject):
        raise ApprovalError("approval subject must be immutable")
    payload = json.dumps(asdict(subject), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_action(action: object) -> None:
    if action not in _ACTIONS:
        raise ApprovalError("action must be send or star")


def _validate_turn(value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ApprovalError("current_turn_id is required")
