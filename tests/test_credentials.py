import io
import sys
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.credentials import (
    CredentialStore,
    CredentialStoreUnavailableError,
    collect_profile_and_secret,
)
from installer.setup_email import ALIBABA_THIRD_PARTY_PASSWORD_PATH, run_setup


TEST_SECRET = "not-a-real-password"


class MemoryCredentialStore:
    """A test-only stand-in for the operating-system credential provider."""

    def __init__(self):
        self.values = {}

    def get(self, email):
        return self.values.get(email)

    def set(self, email, secret):
        self.values[email] = secret

    def delete(self, email):
        self.values.pop(email, None)


class RecordingKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service_name, email):
        return self.values.get((service_name, email))

    def set_password(self, service_name, email, secret):
        self.values[(service_name, email)] = secret

    def delete_password(self, service_name, email):
        self.values.pop((service_name, email), None)


class UnavailableKeyring:
    def get_password(self, service_name, email):
        raise RuntimeError("no credential provider")


class CredentialSetupTests(unittest.TestCase):
    def test_setup_collects_only_profile_fields_then_uses_hidden_secret_prompt(self):
        answers = iter(("Wade Su", "wade@example.com", "English", "Chinese", "warm"))
        requested_fields = []
        secret_prompts = []
        store = MemoryCredentialStore()

        def input_fn(prompt):
            requested_fields.append(prompt)
            return next(answers)

        def secret_prompt(prompt):
            secret_prompts.append(prompt)
            return TEST_SECRET

        profile = collect_profile_and_secret(input_fn, secret_prompt, store)

        self.assertEqual(
            requested_fields,
            [
                "Your name: ",
                "Your Alibaba Enterprise Mail address: ",
                "Preferred language: ",
                "Default reply language: ",
                "Default reply tone: ",
            ],
        )
        self.assertEqual(secret_prompts, ["Alibaba third-party client password: "])
        self.assertEqual(store.get("wade@example.com"), TEST_SECRET)
        self.assertNotIn(TEST_SECRET, asdict(profile).values())
        self.assertNotIn("password", asdict(profile))
        self.assertNotIn("secret", asdict(profile))

    def test_setup_status_never_echoes_the_secret(self):
        output = io.StringIO()
        store = MemoryCredentialStore()
        answers = iter(("Wade Su", "wade@example.com", "English", "Chinese", "warm"))

        profile = run_setup(
            input_fn=lambda prompt: next(answers),
            secret_prompt=lambda prompt: TEST_SECRET,
            store=store,
            output_fn=lambda message: print(message, file=output),
        )

        status = output.getvalue()
        self.assertEqual(profile.email, "wade@example.com")
        self.assertNotIn(TEST_SECRET, status)
        self.assertNotIn(TEST_SECRET, repr(profile))
        self.assertIn("setup is complete", status)

    def test_installer_prints_alibaba_password_path_before_hidden_prompt(self):
        events = []
        answers = iter(("Wade Su", "wade@example.com", "English", "Chinese", "warm"))

        run_setup(
            input_fn=lambda prompt: events.append(("input", prompt)) or next(answers),
            secret_prompt=lambda prompt: events.append(("secret", prompt)) or TEST_SECRET,
            store=MemoryCredentialStore(),
            output_fn=lambda message: events.append(("output", message)),
        )

        path_index = next(
            index
            for index, event in enumerate(events)
            if event == ("output", ALIBABA_THIRD_PARTY_PASSWORD_PATH)
        )
        secret_index = next(
            index for index, event in enumerate(events) if event[0] == "secret"
        )
        self.assertLess(path_index, secret_index)

    def test_credential_store_uses_injected_keyring_without_a_file_fallback(self):
        backend = RecordingKeyring()
        store = CredentialStore(backend=backend)

        self.assertIsNone(store.get("wade@example.com"))
        store.set("wade@example.com", TEST_SECRET)
        self.assertEqual(store.get("wade@example.com"), TEST_SECRET)
        store.delete("wade@example.com")
        self.assertIsNone(store.get("wade@example.com"))
        self.assertEqual(len(backend.values), 0)

    def test_unavailable_operating_system_credential_provider_is_recoverably_blocked(self):
        store = CredentialStore(backend=UnavailableKeyring())

        with self.assertRaisesRegex(
            CredentialStoreUnavailableError,
            "Credential storage is unavailable.*Install or enable",
        ):
            store.get("wade@example.com")


if __name__ == "__main__":
    unittest.main()
