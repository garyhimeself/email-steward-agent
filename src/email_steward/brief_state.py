"""Bounded, local state for an optional incremental daily email brief."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4


_RETENTION = timedelta(days=90)
_CARD_KEYS = {"category", "summary", "action_items", "priority"}
_HASH = re.compile(r"^[0-9a-f]{64}$")
_CATEGORIES = {"customer", "finance", "internal", "operations", "partnership", "sales", "supplier"}
_PRIORITIES = {"low", "medium", "high", "urgent"}
_SUMMARY_START = re.compile(r"^(asks|confirms|flags|needs|reports|requests|requires|seeks|shares|updates)\b", re.IGNORECASE)
_ACTION_START = re.compile(r"^(approve|archive|escalate|follow up|no action|prepare|reply|request|review|schedule|send)\b", re.IGNORECASE)
_RAW_MAIL_MARKER = re.compile(r"\b(?:bcc|cc|content-disposition|content-type|from|mime-version|reply-to|subject|to)\s*:", re.IGNORECASE)
_ADDRESS_OR_URL = re.compile(r"(?:\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|https?://)", re.IGNORECASE)
_ENCODED_PAYLOAD = re.compile(r"(?:data:[^\s]+;base64,|\b[A-Za-z0-9+/]{80,}={0,2}\b|\b[0-9a-f]{80,}\b)", re.IGNORECASE)
_DRAFT_GREETING = re.compile(r"^(?:dear|hello|hi)\s+", re.IGNORECASE)


@dataclass
class BriefState:
    """A local de-duplication cache with a success-only watermark."""

    path: Path
    watermark: datetime | None
    _cards: list[dict[str, Any]]

    @classmethod
    def load(cls, path: Path) -> "BriefState":
        """Load persisted state, or return a new empty state when none exists."""
        path = Path(path)
        if not path.exists():
            return cls(path=path, watermark=None, _cards=[])
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or set(data) != {"version", "watermark", "cards"}:
                raise ValueError("brief state has an unsupported shape")
            if data["version"] != 1 or not isinstance(data["cards"], list):
                raise ValueError("brief state has an unsupported version")
            watermark = _parse_timestamp(data["watermark"], "watermark") if data["watermark"] is not None else None
            cards = [_validate_stored_card(card) for card in data["cards"]]
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise ValueError("brief state cannot be safely loaded") from error
        pruned_cards = _prune(cards, _now_utc())
        if len(pruned_cards) != len(cards):
            _atomic_json_write(
                path,
                {
                    "version": 1,
                    "watermark": watermark.isoformat() if watermark is not None else None,
                    "cards": pruned_cards,
                },
            )
        return cls(path=path, watermark=watermark, _cards=pruned_cards)

    def plan(self, identities: Iterable[object]) -> list[object]:
        """Return caller-provided identities that have not been committed before."""
        known = {_identity_key(card["identity"]) for card in self._cards}
        planned: list[object] = []
        for identity in identities:
            if _identity_key(_normalize_identity(identity)) not in known:
                planned.append(identity)
        return planned

    def commit(self, success_at: datetime, cards: Iterable[Mapping[str, object]]) -> None:
        """Atomically store a completed run; invalid work leaves prior state intact."""
        success_at = _require_utc_datetime(success_at, "success_at")
        current_time = _now_utc()
        if success_at > current_time:
            raise ValueError("success_at cannot be in the future")
        prepared = [_prepare_card(card, success_at) for card in cards]
        retained = _prune(self._cards, current_time)
        by_identity = {_identity_key(card["identity"]): card for card in retained}
        for card in prepared:
            by_identity[_identity_key(card["identity"])] = card
        next_cards = list(by_identity.values())
        payload = {
            "version": 1,
            "watermark": success_at.isoformat(),
            "cards": next_cards,
        }
        _atomic_json_write(self.path, payload)
        self.watermark = success_at
        self._cards = next_cards


def _prepare_card(card: Mapping[str, object], recorded_at: datetime) -> dict[str, Any]:
    if not isinstance(card, Mapping) or set(card) != {"identity", "hash", "card"}:
        raise ValueError("each brief entry must contain only identity, hash, and semantic card data")
    identity = _normalize_identity(card["identity"])
    content_hash = card["hash"]
    if not isinstance(content_hash, str) or _HASH.fullmatch(content_hash) is None:
        raise ValueError("brief entry hash must be a SHA-256 hex digest")
    semantic_card = _normalize_semantic_card(card["card"])
    return {
        "identity": identity,
        "hash": content_hash,
        "card": semantic_card,
        "recorded_at": recorded_at.isoformat(),
    }


def _validate_stored_card(card: object) -> dict[str, Any]:
    if not isinstance(card, Mapping) or set(card) != {"identity", "hash", "card", "recorded_at"}:
        raise ValueError("brief state contains non-minimal card data")
    prepared = _prepare_card(
        {"identity": card["identity"], "hash": card["hash"], "card": card["card"]},
        _parse_timestamp(card["recorded_at"], "recorded_at"),
    )
    return prepared


def _normalize_identity(identity: object) -> dict[str, object]:
    if hasattr(identity, "folder") and hasattr(identity, "uidvalidity") and hasattr(identity, "uid"):
        identity = {
            "folder": identity.folder,
            "uidvalidity": identity.uidvalidity,
            "uid": identity.uid,
        }
    if not isinstance(identity, Mapping) or set(identity) != {"folder", "uidvalidity", "uid"}:
        raise ValueError("brief entry identity must be folder, uidvalidity, and uid")
    folder, uidvalidity, uid = identity["folder"], identity["uidvalidity"], identity["uid"]
    if not isinstance(folder, str) or not folder.strip() or any(char in folder for char in "\r\n\x00"):
        raise ValueError("brief entry identity folder is invalid")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in (uidvalidity, uid)):
        raise ValueError("brief entry identity UID values are invalid")
    return {"folder": folder, "uidvalidity": uidvalidity, "uid": uid}


def _identity_key(identity: Mapping[str, object]) -> tuple[object, object, object]:
    return identity["folder"], identity["uidvalidity"], identity["uid"]


def _normalize_semantic_card(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _CARD_KEYS:
        raise ValueError("brief entry semantic card contains unsupported data")
    category = value["category"]
    priority = value["priority"]
    if not isinstance(category, str) or category not in _CATEGORIES:
        raise ValueError("brief entry semantic category is invalid")
    if not isinstance(priority, str) or priority not in _PRIORITIES:
        raise ValueError("brief entry semantic priority is invalid")
    summary = _normalize_semantic_text(value["summary"], max_length=240, field="semantic")
    if _SUMMARY_START.match(summary) is None:
        raise ValueError("brief entry semantic summary must be a short classified statement")
    action_items = value["action_items"]
    if not isinstance(action_items, list) or not action_items or len(action_items) > 5:
        raise ValueError("brief entry action items are invalid")
    normalized_actions = [_normalize_semantic_text(action, max_length=160, field="action") for action in action_items]
    if any(_ACTION_START.match(action) is None for action in normalized_actions):
        raise ValueError("brief entry action items must be short operator actions")
    return {
        "category": category,
        "summary": summary,
        "action_items": normalized_actions,
        "priority": priority,
    }


def _normalize_semantic_text(value: object, *, max_length: int, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"brief entry {field} text is invalid")
    if "\r" in value or "\n" in value:
        raise ValueError(f"brief entry {field} text is invalid")
    normalized = " ".join(value.split())
    if _RAW_MAIL_MARKER.search(normalized) or _ADDRESS_OR_URL.search(normalized) or _ENCODED_PAYLOAD.search(normalized):
        raise ValueError(f"brief entry {field} text is not minimal semantic data")
    if field == "action" and _DRAFT_GREETING.match(normalized):
        raise ValueError("brief entry action text cannot contain a draft greeting")
    return normalized


def _prune(cards: list[dict[str, Any]], reference: datetime) -> list[dict[str, Any]]:
    cutoff = reference - _RETENTION
    return [card for card in cards if _parse_timestamp(card["recorded_at"], "recorded_at") >= cutoff]


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO timestamp") from error
    return _require_utc_datetime(parsed, field)


def _require_utc_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _atomic_json_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
