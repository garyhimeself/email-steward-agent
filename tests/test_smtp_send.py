import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.approval import ApprovalToken
from email_steward.drafting import Draft
from email_steward.smtp_send import send_one


class FakeSmtpClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def send_message(self, message, from_addr=None, to_addrs=None):
        self.calls.append((message, from_addr, to_addrs))
        if self.error:
            raise self.error
        return self.result


def draft():
    return Draft(
        recipient=("partner@example.com",),
        cc=("team@example.com",),
        bcc=("leader@example.com",),
        subject="Re: Product discussion",
        body="Thanks, we can discuss next week.",
        source_identity="wade@example.com",
        message_id="<message-1@example.com>",
        references="<thread-root@example.com>",
    )


class SmtpSendTests(unittest.TestCase):
    def test_send_uses_one_exact_approval_and_does_not_put_bcc_in_headers(self):
        message_draft = draft()
        token = ApprovalToken.for_action("send", message_draft, "turn-1", confirmation="SEND")
        client = FakeSmtpClient(result={})

        result = send_one(client, message_draft, token, "turn-1")

        self.assertTrue(result.sent)
        self.assertFalse(result.uncertain)
        self.assertEqual(len(client.calls), 1)
        message, from_addr, to_addrs = client.calls[0]
        self.assertEqual(from_addr, "wade@example.com")
        self.assertEqual(to_addrs, ("partner@example.com", "team@example.com", "leader@example.com"))
        self.assertEqual(message["To"], "partner@example.com")
        self.assertEqual(message["Cc"], "team@example.com")
        self.assertIsNone(message["Bcc"])

    def test_uncertain_smtp_failure_is_returned_without_a_retry(self):
        message_draft = draft()
        token = ApprovalToken.for_action("send", message_draft, "turn-1", confirmation="SEND")
        client = FakeSmtpClient(error=TimeoutError("network timed out"))

        result = send_one(client, message_draft, token, "turn-1")

        self.assertFalse(result.sent)
        self.assertTrue(result.uncertain)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(len(client.calls), 1)


if __name__ == "__main__":
    unittest.main()
