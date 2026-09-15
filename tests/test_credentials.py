import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.credentials import (
    CredentialStore,
    CredentialStoreUnavailableError,
    collect_profile_and_secret,
)
from email_steward import credentials


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


class UnavailableCredentialStore:
    def get(self, email):
        raise CredentialStoreUnavailableError("credential provider is unavailable")

    def set(self, email, secret):
        raise AssertionError("setup must not store a secret after a failed preflight")

    def delete(self, email):
        raise AssertionError("not used during setup")


WindowsCredentialManagerKeyring = type(
    "WinVaultKeyring",
    (RecordingKeyring,),
    {"__module__": "keyring.backends.Windows"},
)


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

    def test_memory_store_is_an_injected_setup_seam_not_a_credential_store_backend(self):
        store = MemoryCredentialStore()

        self.assertIsNone(store.get("wade@example.com"))
        store.set("wade@example.com", TEST_SECRET)
        self.assertEqual(store.get("wade@example.com"), TEST_SECRET)
        store.delete("wade@example.com")
        self.assertIsNone(store.get("wade@example.com"))

    def test_credential_store_does_not_allow_an_arbitrary_backend_to_be_injected(self):
        with self.assertRaises(TypeError):
            CredentialStore(backend=RecordingKeyring())

    def test_only_the_platform_credential_manager_backend_is_accepted(self):
        secure_backend = WindowsCredentialManagerKeyring()

        credentials._validate_system_backend(secure_backend, platform_name="Windows")

        with self.assertRaisesRegex(CredentialStoreUnavailableError, "not supported"):
            credentials._validate_system_backend(
                RecordingKeyring(), platform_name="Windows"
            )

    def test_unavailable_operating_system_credential_provider_is_recoverably_blocked(self):
        with self.assertRaisesRegex(
            CredentialStoreUnavailableError,
            "Credential storage is unavailable.*Install or enable",
        ):
            with patch.object(
                credentials,
                "_load_verified_system_backend",
                side_effect=CredentialStoreUnavailableError(
                    "Credential storage is unavailable. Install or enable"
                ),
                create=True,
            ):
                CredentialStore()

    def test_unavailable_provider_blocks_before_the_hidden_secret_prompt(self):
        answers = iter(("Wade Su", "wade@example.com", "English", "Chinese", "warm"))
        secret_prompt_calls = []

        with self.assertRaisesRegex(CredentialStoreUnavailableError, "unavailable"):
            collect_profile_and_secret(
                lambda prompt: next(answers),
                lambda prompt: secret_prompt_calls.append(prompt) or TEST_SECRET,
                UnavailableCredentialStore(),
            )

        self.assertEqual(secret_prompt_calls, [])


if __name__ == "__main__":
    unittest.main()
