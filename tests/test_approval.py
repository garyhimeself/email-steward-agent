import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.approval import ApprovalError, ApprovalToken, consume_exact_approval, verify_exact_approval
from email_steward.drafting import Draft
from email_steward.imap_read import MailIdentity


def draft(**changes):
    values = {
        "recipient": ("partner@example.com",),
        "cc": ("team@example.com",),
        "bcc": ("leader@example.com",),
        "subject": "Re: Product discussion",
        "body": "Thanks, we can discuss next week.",
        "source_identity": "wade@example.com",
        "message_id": "<message-1@example.com>",
        "references": "<thread-root@example.com>",
    }
    values.update(changes)
    return Draft(**values)


class ApprovalTests(unittest.TestCase):
    def test_exact_send_approval_rejects_a_changed_turn_or_draft_field(self):
        original = draft()
        token = ApprovalToken.for_action("send", original, "turn-1", confirmation="SEND")

        verify_exact_approval(token, "send", original, "turn-1")
        for changed in (
            draft(body="Changed"),
            draft(recipient=("other@example.com",)),
            draft(cc=("other@example.com",)),
            draft(bcc=("other@example.com",)),
            draft(subject="Changed"),
            draft(source_identity="other@example.com"),
        ):
            with self.assertRaises(ApprovalError):
                verify_exact_approval(token, "send", changed, "turn-1")
        with self.assertRaises(ApprovalError):
            verify_exact_approval(token, "send", original, "turn-2")

    def test_blank_confirmation_and_batch_subjects_are_rejected(self):
        original = draft()
        with self.assertRaisesRegex(ApprovalError, "confirmation"):
            ApprovalToken.for_action("send", original, "turn-1", confirmation="  ")
        with self.assertRaisesRegex(ApprovalError, "one exact"):
            ApprovalToken.for_action("send", (original, draft()), "turn-1", confirmation="SEND")

    def test_confirmation_must_match_the_uppercase_action_exactly(self):
        original = draft()
        for confirmation in (" send", "SEND ", "send", "SEND\n", "SEND\r", "SEND\x00"):
            with self.assertRaisesRegex(ApprovalError, "confirmation"):
                ApprovalToken.for_action("send", original, "turn-1", confirmation=confirmation)
        ApprovalToken.for_action("send", original, "turn-1", confirmation="SEND")

    def test_consumed_token_cannot_be_used_again(self):
        original = draft()
        token = ApprovalToken.for_action("send", original, "turn-1", confirmation="SEND")

        consume_exact_approval(token, "send", original, "turn-1")

        with self.assertRaisesRegex(ApprovalError, "already used"):
            consume_exact_approval(token, "send", original, "turn-1")

    def test_star_token_is_bound_to_exact_mail_identity_and_action(self):
        identity = MailIdentity("INBOX", 801, 11)
        token = ApprovalToken.for_action("star", identity, "turn-1", confirmation="STAR")

        verify_exact_approval(token, "star", identity, "turn-1")
        with self.assertRaises(ApprovalError):
            verify_exact_approval(token, "send", identity, "turn-1")
        with self.assertRaises(ApprovalError):
            verify_exact_approval(token, "star", MailIdentity("INBOX", 801, 12), "turn-1")


if __name__ == "__main__":
    unittest.main()
