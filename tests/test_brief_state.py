import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.brief_state import BriefState
from email_steward.imap_read import MailIdentity


UTC = timezone.utc


def card_for(identity, content_hash):
    return {
        "identity": identity,
        "hash": content_hash,
        "card": {
            "category": "partnership",
            "actions": ["reply"],
            "priority": "high",
        },
    }


class BriefStateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "brief-state.json"
        self.first = MailIdentity(folder="INBOX", uidvalidity=801, uid=11)
        self.second = MailIdentity(folder="INBOX", uidvalidity=801, uid=12)

    def test_plan_returns_only_identities_not_already_committed(self):
        state = BriefState.load(self.path)
        first_run = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        self.assertEqual(state.plan([self.first, self.second]), [self.first, self.second])

        state.commit(first_run, [card_for(self.first, "a" * 64)])

        restored = BriefState.load(self.path)
        self.assertEqual(restored.plan([self.first, self.second]), [self.second])

    def test_rejected_commit_preserves_previous_watermark_and_cards(self):
        state = BriefState.load(self.path)
        first_run = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        state.commit(first_run, [card_for(self.first, "a" * 64)])

        with self.assertRaisesRegex(ValueError, "semantic"):
            state.commit(
                first_run + timedelta(days=1),
                [
                    {
                        "identity": self.second,
                        "hash": "b" * 64,
                        "card": {"raw_body": "private email body must never be stored"},
                    }
                ],
            )

        restored = BriefState.load(self.path)
        self.assertEqual(restored.watermark, first_run)
        self.assertEqual(restored.plan([self.first, self.second]), [self.second])

    def test_rejects_any_free_text_field_instead_of_persisting_mail_content(self):
        state = BriefState.load(self.path)
        run_at = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        raw_mail = "From: vendor@example.com\nTo: operator@example.com\nSubject: Confidential\nPlease share the attached contract."

        unsafe = card_for(self.first, "a" * 64)
        unsafe["card"]["summary"] = raw_mail
        with self.assertRaisesRegex(ValueError, "unsupported"):
            state.commit(run_at, [unsafe])

        self.assertFalse(self.path.exists())

    def test_rejects_free_text_draft_instead_of_persisting_it_as_an_action(self):
        state = BriefState.load(self.path)
        run_at = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        draft_card = card_for(self.first, "a" * 64)
        draft_card["card"]["actions"] = ["Dear Marta, thank you for your message. I can send the quotation tomorrow."]

        with self.assertRaisesRegex(ValueError, "action"):
            state.commit(run_at, [draft_card])

        self.assertFalse(self.path.exists())

    def test_rejects_free_text_attachment_payload_instead_of_persisting_it_as_an_action(self):
        state = BriefState.load(self.path)
        run_at = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        encoded_attachment = "data:application/pdf;base64," + ("QUJD" * 40)

        unsafe = card_for(self.first, "a" * 64)
        unsafe["card"]["actions"] = [encoded_attachment]
        with self.assertRaisesRegex(ValueError, "action"):
            state.commit(run_at, [unsafe])

        self.assertFalse(self.path.exists())

    def test_state_stores_only_identity_hash_and_finite_classification_data(self):
        state = BriefState.load(self.path)
        run_at = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        state.commit(run_at, [card_for(self.first, "a" * 64)])

        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(set(stored), {"version", "watermark", "cards"})
        self.assertEqual(
            stored["cards"],
            [
                {
                    "identity": {"folder": "INBOX", "uidvalidity": 801, "uid": 11},
                    "hash": "a" * 64,
                    "card": {
                        "category": "partnership",
                        "actions": ["reply"],
                        "priority": "high",
                    },
                    "recorded_at": run_at.isoformat(),
                }
            ],
        )
        saved_text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("private email body", saved_text)
        self.assertNotIn("summary", saved_text)

    def test_load_clears_a_future_watermark_and_future_card_without_retaining_them(self):
        future = datetime.now(UTC) + timedelta(days=1)
        self.path.write_text(json.dumps({"version": 2, "watermark": future.isoformat(), "cards": [{"identity": {"folder": "INBOX", "uidvalidity": 801, "uid": 11}, "hash": "a" * 64, "card": {"category": "partnership", "actions": ["reply"], "priority": "high"}, "recorded_at": future.isoformat()}]}), encoding="utf-8")

        restored = BriefState.load(self.path)

        self.assertIsNone(restored.watermark)
        self.assertEqual(restored.plan([self.first]), [self.first])
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"version": 2, "watermark": None, "cards": []})

    def test_commit_prunes_cards_older_than_ninety_days(self):
        state = BriefState.load(self.path)
        first_run = datetime.now(UTC) - timedelta(days=91)
        state.commit(first_run, [card_for(self.first, "a" * 64)])

        ninety_one_days_later = first_run + timedelta(days=91)
        state.commit(ninety_one_days_later, [card_for(self.second, "b" * 64)])

        restored = BriefState.load(self.path)
        self.assertEqual(restored.watermark, ninety_one_days_later)
        self.assertEqual(restored.plan([self.first, self.second]), [self.first])
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(len(stored["cards"]), 1)
        self.assertEqual(stored["cards"][0]["identity"]["uid"], 12)

    def test_load_removes_expired_card_data_from_disk(self):
        state = BriefState.load(self.path)
        expired_run = datetime.now(UTC) - timedelta(days=91)
        state.commit(expired_run, [card_for(self.first, "a" * 64)])

        BriefState.load(self.path)

        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["cards"], [])

    def test_commit_rejects_a_future_success_timestamp(self):
        state = BriefState.load(self.path)
        future = datetime.now(UTC) + timedelta(minutes=5)

        with self.assertRaisesRegex(ValueError, "future"):
            state.commit(future, [card_for(self.first, "a" * 64)])

        self.assertFalse(self.path.exists())

    def test_commit_prunes_against_actual_current_utc_not_a_backdated_success_timestamp(self):
        actual_now = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
        state = BriefState.load(self.path)

        with patch("email_steward.brief_state._now_utc", return_value=actual_now):
            state.commit(actual_now - timedelta(days=91), [card_for(self.first, "a" * 64)])
            state.commit(actual_now - timedelta(days=1), [card_for(self.second, "b" * 64)])

        self.assertEqual(state.plan([self.first, self.second]), [self.first])


if __name__ == "__main__":
    unittest.main()
