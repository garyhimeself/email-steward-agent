import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.imap_read import (
    ImapReadError,
    MailIdentity,
    UIDValidityUnavailableError,
    read_mail,
    search_mail,
)


RAW_MESSAGE = b"""From: partner@example.com\r
To: wade@example.com\r
Cc: team@example.com\r
Subject: Product discussion\r
Date: Mon, 13 Sep 2026 10:00:00 +0000\r
Message-ID: <message-1@example.com>\r
References: <thread-root@example.com>\r
MIME-Version: 1.0\r
Content-Type: multipart/mixed; boundary=boundary\r
\r
--boundary\r
Content-Type: text/plain; charset=utf-8\r
\r
Hello from the plain-text body.\r
--boundary\r
Content-Type: text/html; charset=utf-8\r
\r
<p>This HTML body must not be returned.</p>\r
--boundary\r
Content-Type: application/pdf\r
Content-Disposition: attachment; filename=proposal.pdf\r
Content-Transfer-Encoding: base64\r
\r
YWJj\r
--boundary--\r
"""


HTML_ONLY_MESSAGE = b"""From: partner@example.com\r
To: wade@example.com\r
Subject: HTML-only update\r
MIME-Version: 1.0\r
Content-Type: text/html; charset=utf-8\r
\r
<html><head><style>body { display:none }</style><script>steal()</script></head><body><p>Hello <strong>partner</strong>.</p><img src="https://tracker.example/pixel" alt="tracker"><a href="https://remote.example">Read details</a></body></html>\r
"""


class FakeImapClient:
    def __init__(
        self,
        *,
        uidvalidity=b"801",
        search_uids=b"11 29",
        raw_message=RAW_MESSAGE,
        fetched_uid=b"11",
    ):
        self.uidvalidity = uidvalidity
        self.search_uids = search_uids
        self.raw_message = raw_message
        self.fetched_uid = fetched_uid
        self.calls = []

    def select(self, folder, readonly=False):
        self.calls.append(("select", folder, readonly))
        return "OK", [b"2"]

    def response(self, code):
        self.calls.append(("response", code))
        if code == "UIDVALIDITY" and self.uidvalidity is not None:
            return "UIDVALIDITY", [self.uidvalidity]
        return code, [None]

    def uid(self, command, *arguments):
        self.calls.append(("uid", command, *arguments))
        if command == "SEARCH":
            return "OK", [self.search_uids]
        if command == "FETCH":
            return "OK", [
                (b"11 (UID " + self.fetched_uid + b" RFC822.SIZE 123)", self.raw_message)
            ]
        raise AssertionError(f"unexpected UID command: {command}")


class ImapReadTests(unittest.TestCase):
    def test_search_selects_folder_readonly_and_returns_exact_identities(self):
        client = FakeImapClient()

        results = search_mail(
            client,
            "INBOX",
            {"since": date(2026, 9, 1), "from": "partner@example.com"},
        )

        self.assertEqual(
            results,
            [
                MailIdentity(folder="INBOX", uidvalidity=801, uid=11),
                MailIdentity(folder="INBOX", uidvalidity=801, uid=29),
            ],
        )
        self.assertEqual(client.calls[0], ("select", "INBOX", True))
        self.assertIn(
            ("uid", "SEARCH", "UTF-8", b'(SINCE 01-Sep-2026 FROM "partner@example.com")'),
            client.calls,
        )
        self.assertNotIn(("search",), client.calls)

    def test_search_rejects_an_unconstrained_scope(self):
        client = FakeImapClient()

        with self.assertRaisesRegex(ValueError, "at least one"):
            search_mail(client, "INBOX", {})

        self.assertEqual(client.calls, [])

    def test_missing_uidvalidity_fails_closed_before_search(self):
        client = FakeImapClient(uidvalidity=None)

        with self.assertRaises(UIDValidityUnavailableError):
            search_mail(client, "INBOX", {"subject": "proposal"})

        self.assertFalse(any(call[:2] == ("uid", "SEARCH") for call in client.calls))

    def test_read_uses_uid_fetch_peek_and_extracts_only_plain_text_and_inventory(self):
        client = FakeImapClient()
        identity = MailIdentity(folder="INBOX", uidvalidity=801, uid=11)

        record = read_mail(client, identity)

        self.assertEqual(client.calls[0], ("select", "INBOX", True))
        self.assertIn(("uid", "FETCH", "11", "(BODY.PEEK[] RFC822.SIZE)"), client.calls)
        self.assertEqual(record.identity, identity)
        self.assertEqual(record.sender, "partner@example.com")
        self.assertEqual(record.to, "wade@example.com")
        self.assertEqual(record.cc, "team@example.com")
        self.assertEqual(record.subject, "Product discussion")
        self.assertEqual(record.message_id, "<message-1@example.com>")
        self.assertEqual(record.references, "<thread-root@example.com>")
        self.assertIn("Hello from the plain-text body.", record.plain_text)
        self.assertNotIn("HTML body", record.plain_text)
        self.assertEqual(record.attachments[0].filename, "proposal.pdf")
        self.assertEqual(record.attachments[0].content_type, "application/pdf")
        self.assertEqual(record.attachments[0].size, 3)

    def test_read_fails_closed_when_selected_uidvalidity_changes(self):
        client = FakeImapClient(uidvalidity=b"802")
        identity = MailIdentity(folder="INBOX", uidvalidity=801, uid=11)

        with self.assertRaisesRegex(UIDValidityUnavailableError, "changed"):
            read_mail(client, identity)

        self.assertFalse(any(call[:2] == ("uid", "FETCH") for call in client.calls))

    def test_read_fails_closed_when_fetch_response_uid_does_not_match_identity(self):
        client = FakeImapClient(fetched_uid=b"12")
        identity = MailIdentity(folder="INBOX", uidvalidity=801, uid=11)

        with self.assertRaisesRegex(ImapReadError, "UID"):
            read_mail(client, identity)

    def test_read_module_never_issues_mutating_or_seen_flag_commands(self):
        client = FakeImapClient()

        search_mail(client, "INBOX", {"unseen": True})
        read_mail(client, MailIdentity(folder="INBOX", uidvalidity=801, uid=11))

        forbidden = {"STORE", "MOVE", "COPY", "EXPUNGE", "FETCH"}
        for call in client.calls:
            if call[0] == "uid":
                self.assertFalse(call[1] in forbidden - {"FETCH"})
                self.assertNotIn("\\\\Seen", " ".join(map(str, call)))
                if call[1] == "FETCH":
                    self.assertIn("BODY.PEEK", " ".join(map(str, call)))

    def test_read_html_only_message_falls_back_to_safe_readable_plain_text(self):
        client = FakeImapClient(raw_message=HTML_ONLY_MESSAGE)

        record = read_mail(client, MailIdentity(folder="INBOX", uidvalidity=801, uid=11))

        self.assertIn("Hello partner.", record.plain_text)
        self.assertIn("Read details", record.plain_text)
        self.assertNotIn("steal", record.plain_text)
        self.assertNotIn("display:none", record.plain_text)
        self.assertNotIn("tracker.example", record.plain_text)
        self.assertNotIn("remote.example", record.plain_text)

    def test_search_uses_utf8_charset_bytes_for_a_chinese_subject(self):
        client = FakeImapClient()

        search_mail(client, "INBOX", {"subject": "开发合作"})

        self.assertIn(
            ("uid", "SEARCH", "UTF-8", b'(SUBJECT "\xe5\xbc\x80\xe5\x8f\x91\xe5\x90\x88\xe4\xbd\x9c")'),
            client.calls,
        )

    def test_select_encodes_a_chinese_folder_as_modified_utf7_bytes(self):
        client = FakeImapClient()

        search_mail(client, "收件箱", {"unseen": True})

        self.assertEqual(client.calls[0], ("select", b"&ZTZO9nux-", True))


if __name__ == "__main__":
    unittest.main()
