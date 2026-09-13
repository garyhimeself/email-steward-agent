import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.brief_state import BriefState
from email_steward.imap_read import MailIdentity


UTC = timezone.utc


def card_for(identity, content_hash, summary="Needs a product catalogue"):
    return {
        "identity": identity,
        "hash": content_hash,
        "card": {
            "category": "partnership",
            "summary": summary,
            "action_items": ["Reply by Friday"],
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

    def test_state_stores_only_identity_hash_and_minimal_semantic_card_data(self):
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
                        "summary": "Needs a product catalogue",
                        "action_items": ["Reply by Friday"],
                        "priority": "high",
                    },
                    "recorded_at": run_at.isoformat(),
                }
            ],
        )
        saved_text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("private email body", saved_text)
        self.assertNotIn("attachment", saved_text)

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


if __name__ == "__main__":
    unittest.main()
