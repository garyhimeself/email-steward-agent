import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.approval import ApprovalError, ApprovalToken
from email_steward.imap_flag import star_one
from email_steward.imap_read import MailIdentity


class FakeImapClient:
    def __init__(self, uidvalidity=b"801"):
        self.uidvalidity = uidvalidity
        self.calls = []

    def select(self, folder, readonly=False):
        self.calls.append(("select", folder, readonly))
        return "OK", [b"1"]

    def response(self, code):
        self.calls.append(("response", code))
        return code, [self.uidvalidity]

    def uid(self, command, *arguments):
        self.calls.append(("uid", command, *arguments))
        return "OK", [b"1"]


class ImapFlagTests(unittest.TestCase):
    def test_star_rejects_unconfirmed_or_different_mail_before_mutation(self):
        client = FakeImapClient()
        identity = MailIdentity("INBOX", 801, 11)
        token = ApprovalToken.for_action("star", identity, "turn-1", confirmation="STAR")

        with self.assertRaises(ApprovalError):
            star_one(client, MailIdentity("INBOX", 801, 12), token, "turn-1")

        self.assertFalse(any(call[1] == "STORE" for call in client.calls if call[0] == "uid"))

    def test_star_uses_one_flagged_store_after_exact_confirmation(self):
        client = FakeImapClient()
        identity = MailIdentity("INBOX", 801, 11)
        token = ApprovalToken.for_action("star", identity, "turn-1", confirmation="STAR")

        result = star_one(client, identity, token, "turn-1")

        self.assertTrue(result.starred)
        store_calls = [call for call in client.calls if call[:2] == ("uid", "STORE")]
        self.assertEqual(store_calls, [("uid", "STORE", "11", "+FLAGS.SILENT", "(\\Flagged)")])

    def test_star_encodes_a_chinese_folder_for_the_real_imap_argument_path(self):
        client = FakeImapClient()
        identity = MailIdentity("收件箱", 801, 11)
        token = ApprovalToken.for_action("star", identity, "turn-1", confirmation="STAR")

        star_one(client, identity, token, "turn-1")

        self.assertEqual(client.calls[0], ("select", b"&ZTZO9nux-", False))

    def test_star_token_cannot_be_reused_after_store_is_attempted(self):
        client = FakeImapClient()
        identity = MailIdentity("INBOX", 801, 11)
        token = ApprovalToken.for_action("star", identity, "turn-1", confirmation="STAR")

        star_one(client, identity, token, "turn-1")

        with self.assertRaisesRegex(ApprovalError, "already used"):
            star_one(client, identity, token, "turn-1")
        store_calls = [call for call in client.calls if call[:2] == ("uid", "STORE")]
        self.assertEqual(len(store_calls), 1)


if __name__ == "__main__":
    unittest.main()
