"""Exact, current-turn approvals for the agent's only write actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
import secrets
import threading

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
    _token_id: str

    @classmethod
    def for_action(
        cls, action: str, subject: object, current_turn_id: str, *, confirmation: str
    ) -> "ApprovalToken":
        _validate_action(action)
        _validate_turn(current_turn_id)
        if not isinstance(confirmation, str) or confirmation != action.upper():
            raise ApprovalError(f"explicit {action} confirmation is required")
        token = cls(action, _fingerprint_subject(subject), current_turn_id, secrets.token_hex(32))
        with _issued_tokens_lock:
            _issued_tokens[token._token_id] = (
                token.action,
                token.subject_fingerprint,
                token.current_turn_id,
                False,
            )
        return token


def verify_exact_approval(
    token: ApprovalToken, action: str, subject: object, current_turn_id: str
) -> None:
    """Fail closed unless action, subject, and current conversation turn are unchanged."""
    _validate_token_matches(token, action, subject, current_turn_id)
    with _issued_tokens_lock:
        _assert_issued_and_unused(token)


def consume_exact_approval(
    token: ApprovalToken, action: str, subject: object, current_turn_id: str
) -> None:
    """Atomically consume one exact approval immediately before its write command."""
    _validate_token_matches(token, action, subject, current_turn_id)
    with _issued_tokens_lock:
        _assert_issued_and_unused(token)
        _issued_tokens[token._token_id] = (
            token.action,
            token.subject_fingerprint,
            token.current_turn_id,
            True,
        )


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


_issued_tokens_lock = threading.Lock()
_issued_tokens: dict[str, tuple[str, str, str, bool]] = {}


def _validate_token_matches(
    token: ApprovalToken, action: str, subject: object, current_turn_id: str
) -> None:
    if not isinstance(token, ApprovalToken):
        raise ApprovalError("a valid approval token is required")
    _validate_action(action)
    _validate_turn(current_turn_id)
    if token.action != action or token.current_turn_id != current_turn_id:
        raise ApprovalError("approval is stale or for a different action")
    if token.subject_fingerprint != _fingerprint_subject(subject):
        raise ApprovalError("approval no longer matches this exact item")


def _assert_issued_and_unused(token: ApprovalToken) -> None:
    issued = _issued_tokens.get(token._token_id)
    expected = (token.action, token.subject_fingerprint, token.current_turn_id)
    if issued is None or issued[:3] != expected:
        raise ApprovalError("a valid approval token is required")
    if issued[3]:
        raise ApprovalError("approval already used")
