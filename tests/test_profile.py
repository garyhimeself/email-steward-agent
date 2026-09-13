import json
import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from email_steward.profile import OperatorProfile, save_profile, validate_profile


VALID_PROFILE = {
    "name": "Wade Su",
    "email": "wade@example.com",
    "preferred_language": "English",
    "reply_language": "Chinese",
    "reply_tone": "warm and concise",
}


class OperatorProfileTests(unittest.TestCase):
    def test_valid_personal_profile_uses_alibaba_ssl_defaults(self):
        profile = validate_profile(VALID_PROFILE)

        self.assertEqual(
            profile,
            OperatorProfile(
                name="Wade Su",
                email="wade@example.com",
                preferred_language="English",
                reply_language="Chinese",
                reply_tone="warm and concise",
                imap_host="imap.qiye.aliyun.com",
                imap_port=993,
                smtp_host="smtp.qiye.aliyun.com",
                smtp_port=465,
            ),
        )

    def test_profile_is_immutable(self):
        profile = validate_profile(VALID_PROFILE)

        with self.assertRaises(FrozenInstanceError):
            profile.name = "Someone else"

    def test_malformed_email_is_rejected(self):
        data = {**VALID_PROFILE, "email": "not-an-email"}

        with self.assertRaisesRegex(ValueError, "email"):
            validate_profile(data)

    def test_missing_name_is_rejected(self):
        data = {key: value for key, value in VALID_PROFILE.items() if key != "name"}

        with self.assertRaisesRegex(ValueError, "name"):
            validate_profile(data)

    def test_normal_setup_rejects_server_overrides(self):
        data = {**VALID_PROFILE, "imap_host": "mail.example.com"}

        with self.assertRaisesRegex(ValueError, "advanced"):
            validate_profile(data)

    def test_normal_setup_accepts_explicit_alibaba_defaults(self):
        data = {
            **VALID_PROFILE,
            "imap_host": "imap.qiye.aliyun.com",
            "imap_port": 993,
            "smtp_host": "smtp.qiye.aliyun.com",
            "smtp_port": 465,
        }

        profile = validate_profile(data)

        self.assertEqual(profile.imap_host, "imap.qiye.aliyun.com")
        self.assertEqual(profile.smtp_host, "smtp.qiye.aliyun.com")

    def test_advanced_server_overrides_require_explicit_opt_in(self):
        data = {
            **VALID_PROFILE,
            "imap_host": "mail.example.com",
            "imap_port": 993,
            "smtp_host": "send.example.com",
            "smtp_port": 465,
        }

        profile = validate_profile(data, allow_advanced_servers=True)

        self.assertEqual(profile.imap_host, "mail.example.com")
        self.assertEqual(profile.smtp_host, "send.example.com")

    def test_saving_advanced_profile_requires_explicit_opt_in(self):
        profile = OperatorProfile(
            name="Wade Su",
            email="wade@example.com",
            preferred_language="English",
            reply_language="Chinese",
            reply_tone="warm and concise",
            imap_host="mail.example.com",
            smtp_host="send.example.com",
        )
        path = Path(__file__).parent / f"profile-{uuid4().hex}.json"
        try:
            with self.assertRaisesRegex(ValueError, "advanced"):
                save_profile(profile, path)
            save_profile(profile, path, allow_advanced_servers=True)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["imap_host"], "mail.example.com")
        finally:
            path.unlink(missing_ok=True)

    def test_profile_save_is_json_and_contains_no_secret_or_absolute_path(self):
        profile = validate_profile(VALID_PROFILE)
        path = Path(__file__).parent / f"profile-{uuid4().hex}.json"
        try:
            save_profile(profile, path)

            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["email"], "wade@example.com")
            self.assertNotIn("password", saved)
            self.assertNotIn("secret", saved)
            self.assertNotIn(str(path.parent), path.read_text(encoding="utf-8"))
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
