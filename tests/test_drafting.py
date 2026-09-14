import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.drafting import Draft, ReplyDraftError, humanization_request, reply_draft
from email_steward.imap_read import MailIdentity, MessageRecord


class DraftingTests(unittest.TestCase):
    def test_draft_is_immutable_and_explicitly_unsent(self):
        draft = Draft(
            recipient=("partner@example.com",),
            cc=("team@example.com",),
            bcc=("leader@example.com",),
            subject="Re: Product discussion",
            body="Thanks, we can discuss next week.",
            source_identity="wade@example.com",
            message_id="<message-1@example.com>",
            references="<thread-root@example.com>",
        )

        self.assertEqual(draft.status, "unsent")
        self.assertFalse(draft.sent)
        with self.assertRaisesRegex(Exception, "cannot assign"):
            draft.body = "changed"

    def test_reply_draft_requires_message_id_and_supports_reply_all(self):
        message = MessageRecord(
            identity=MailIdentity("INBOX", 801, 11),
            sender="Partner <partner@example.com>",
            to="Wade <wade@example.com>, colleague@example.com",
            cc="Team <team@example.com>",
            subject="Product discussion",
            date=None,
            message_id=None,
            references="<thread-root@example.com>",
            plain_text="Hello",
            attachments=(),
        )

        with self.assertRaisesRegex(ReplyDraftError, "Message-ID"):
            reply_draft(message, "Thanks.", "wade@example.com", reply_all=True)

        draft = reply_draft(
            message.__class__(**{**message.__dict__, "message_id": "<message-1@example.com>"}),
            "Thanks.",
            "wade@example.com",
            reply_all=True,
            bcc=("audit@example.com",),
        )
        self.assertEqual(draft.recipient, ("partner@example.com",))
        self.assertEqual(draft.cc, ("colleague@example.com", "team@example.com"))
        self.assertEqual(draft.bcc, ("audit@example.com",))
        self.assertEqual(draft.subject, "Re: Product discussion")
        self.assertEqual(draft.references, "<thread-root@example.com> <message-1@example.com>")

    def test_humanization_request_preserves_immutable_business_facts(self):
        draft = Draft(
            recipient=("partner@example.com",),
            cc=(),
            bcc=(),
            subject="Budget and launch date",
            body="We can commit USD 5,000 by 15 October.",
            source_identity="wade@example.com",
            message_id="<message-1@example.com>",
            references=None,
        )

        request = humanization_request(draft, writing_sample="Short and direct.")

        for fact in ("facts", "money", "dates", "commitments", "recipient", "language"):
            self.assertIn(fact, request.lower())
        self.assertIn(draft.body, request)
        self.assertIn("Short and direct.", request)
        self.assertIn("humanizer", request.lower())

    def test_draft_allows_normal_multiline_body_but_not_header_newlines(self):
        draft = Draft(
            recipient=("partner@example.com",),
            cc=(),
            bcc=(),
            subject="Update",
            body="Hello,\n\nWe can meet next week.\n",
            source_identity="wade@example.com",
            message_id=None,
            references=None,
        )

        self.assertIn("\n", draft.body)
        with self.assertRaisesRegex(ValueError, "subject"):
            Draft(
                recipient=("partner@example.com",), cc=(), bcc=(), subject="Update\nBcc: bad@example.com",
                body="Hello", source_identity="wade@example.com", message_id=None, references=None,
            )

    def test_draft_preserves_local_part_case_and_normalizes_only_ascii_domain(self):
        draft = Draft(
            recipient=("Partner.Team+EU@example.COM",),
            cc=(), bcc=(), subject="Update", body="Hello",
            source_identity="Wade.Sales@example.COM", message_id=None, references=None,
        )

        self.assertEqual(draft.recipient, ("Partner.Team+EU@example.com",))
        self.assertEqual(draft.source_identity, "Wade.Sales@example.com")

    def test_draft_rejects_unicode_and_whitespace_mutated_addresses(self):
        for value in ("groß@example.com", " partner@example.com", "partner@example.com "):
            with self.assertRaisesRegex(ValueError, "email address"):
                Draft(
                    recipient=(value,), cc=(), bcc=(), subject="Update", body="Hello",
                    source_identity="wade@example.com", message_id=None, references=None,
                )

    def test_draft_rejects_non_bare_or_structurally_invalid_addresses(self):
        invalid_addresses = (
            "Partner <partner@example.com>",
            "<partner@example.com>",
            '"partner"@example.com',
            "partner @example.com",
            "partner\t@example.com",
            "partner..team@example.com",
            ".partner@example.com",
            "partner.@example.com",
            "partner@example..com",
            "partner@-example.com",
            "partner@example-.com",
            "partner@exam_ple.com",
            "partner@example.com.",
            "partner@example.com\nBcc: injected@example.com",
            "partner@example.com\x00",
        )
        for value in invalid_addresses:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "email address"):
                Draft(
                    recipient=(value,), cc=(), bcc=(), subject="Update", body="Hello",
                    source_identity="wade@example.com", message_id=None, references=None,
                )

    def test_draft_preserves_allowed_ascii_local_part_exactly(self):
        draft = Draft(
            recipient=("A!#$%&'*+-/=?^_`{|}~Z@example.COM",),
            cc=(), bcc=(), subject="Update", body="Hello",
            source_identity="Sales+EU@example.COM", message_id=None, references=None,
        )

        self.assertEqual(draft.recipient, ("A!#$%&'*+-/=?^_`{|}~Z@example.com",))
        self.assertEqual(draft.source_identity, "Sales+EU@example.com")


if __name__ == "__main__":
    unittest.main()
