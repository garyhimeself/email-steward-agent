from __future__ import annotations

import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class MailRuntimeTests(unittest.TestCase):
    def test_credential_status_reports_ready_without_printing_secret(self):
        from installer import mail_runtime

        output = io.StringIO()
        session = type(
            "Session",
            (),
            {"profile": type("Profile", (), {"email": "eileen@example.com"})(), "secret": "test-only-secret"},
        )()

        exit_code = mail_runtime.main(
            ["credential-status", "--workspace", "C:/mail-workspace"],
            session_loader=lambda workspace: session,
            output_fn=lambda message: print(message, file=output),
        )

        self.assertEqual(exit_code, 0)
        self.assertIn('"status": "credential_ready"', output.getvalue())
        self.assertIn('"mailbox": "eileen@example.com"', output.getvalue())
        self.assertNotIn("test-only-secret", output.getvalue())


if __name__ == "__main__":
    unittest.main()
