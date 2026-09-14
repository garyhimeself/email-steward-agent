import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from installer.install_agent import (
    ALIBABA_THIRD_PARTY_PASSWORD_PATH,
    LUNA_ACCEPTANCE_PROMPT,
    TERRA_ACCEPTANCE_PROMPT,
    run_install,
)


class MemoryCredentialStore:
    def __init__(self):
        self.values = {}

    def get(self, email):
        return self.values.get(email)

    def set(self, email, secret):
        self.values[email] = secret

    def delete(self, email):
        self.values.pop(email, None)


class FakeImapClient:
    def __init__(self):
        self.calls = []
        self.closed = False

    def select(self, folder, readonly=True):
        self.calls.append(("select", folder, readonly))
        return "OK", [b"0"]

    def logout(self):
        self.closed = True


class InstallerTests(unittest.TestCase):
    def test_installer_displays_target_and_waits_for_confirmation_before_creating_workspace(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            events = []
            answers = iter((str(workspace), "no"))

            result = run_install(
                Path(temporary_directory) / "package",
                input_fn=lambda prompt: events.append(("input", prompt)) or next(answers),
                secret_prompt=lambda prompt: self.fail("secret prompt must not run"),
                credential_store=MemoryCredentialStore(),
                imap_factory=lambda profile, secret: self.fail("IMAP must not run"),
                output_fn=lambda message: events.append(("output", message)),
            )

            self.assertIsNone(result)
            self.assertFalse(workspace.exists())
            self.assertIn(("output", f"Target workspace: {workspace}"), events)
            self.assertIn(("input", "Create this workspace? [y/N]: "), events)

    def test_installer_saves_only_non_secret_profile_then_verifies_imap_readonly_and_defaults_brief_off(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            events = []
            answers = iter(
                (
                    str(workspace),
                    "yes",
                    "Wade Su",
                    "wade@example.com",
                    "English",
                    "English",
                    "warm and concise",
                    "",
                )
            )
            store = MemoryCredentialStore()
            client = FakeImapClient()
            factory_calls = []

            result = run_install(
                Path(temporary_directory) / "package",
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: events.append(("secret", prompt)) or "test-only-secret",
                credential_store=store,
                imap_factory=lambda profile, secret: factory_calls.append((profile, secret)) or client,
                output_fn=lambda message: events.append(("output", message)),
            )

            self.assertTrue(workspace.is_dir())
            self.assertEqual(result.workspace, workspace)
            self.assertEqual(result.profile.email, "wade@example.com")
            self.assertTrue(result.imap_verified)
            self.assertFalse(result.daily_brief_enabled)
            self.assertEqual(client.calls, [("select", "INBOX", True)])
            self.assertTrue(client.closed)
            self.assertEqual(factory_calls[0][0], result.profile)
            self.assertEqual(factory_calls[0][1], "test-only-secret")
            self.assertEqual(store.get("wade@example.com"), "test-only-secret")
            self.assertEqual(events[:6], [
                ("output", ALIBABA_THIRD_PARTY_PASSWORD_PATH),
                ("output", "Generate the password, copy it now, and keep it safe: it is shown only once."),
                ("output", f"Target workspace: {workspace}"),
                ("secret", "Alibaba third-party client password: "),
                ("output", "Read-only IMAP verification succeeded. No email was changed."),
                ("output", "Daily brief is disabled. You can enable it later after choosing its format and schedule."),
            ])
            self.assertIn(("output", LUNA_ACCEPTANCE_PROMPT), events)
            self.assertIn(("output", TERRA_ACCEPTANCE_PROMPT), events)
            self.assertNotIn("test-only-secret", (workspace / ".email-steward" / "config" / "config.json").read_text(encoding="utf-8"))

    def test_installer_returns_exact_new_project_acceptance_prompts_for_luna_then_terra(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            answers = iter((str(workspace), "y", "Wade", "wade@example.com", "English", "English", "warm", "n"))

            result = run_install(
                Path(temporary_directory) / "package",
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: "test-only-secret",
                credential_store=MemoryCredentialStore(),
                imap_factory=lambda profile, secret: FakeImapClient(),
                output_fn=lambda message: None,
            )

            self.assertEqual(result.next_step, (LUNA_ACCEPTANCE_PROMPT, TERRA_ACCEPTANCE_PROMPT))
            self.assertEqual(
                LUNA_ACCEPTANCE_PROMPT,
                "请完成首次验收：查询最近 7 天未读的开发合作邮件，展示一封最相关邮件的摘要和邮件编号。不要发送邮件。",
            )
            self.assertEqual(
                TERRA_ACCEPTANCE_PROMPT,
                "请根据邮件编号【复制上一步的编号】，生成一份专业、友好的英文回复草稿。不要发送邮件。",
            )

    def test_cross_platform_launchers_resolve_python_from_their_own_directory(self):
        root = Path(__file__).resolve().parents[1]
        windows_launcher = (root / "installer" / "install_agent.bat").read_text(encoding="utf-8")
        macos_launcher = (root / "installer" / "install_agent.command").read_text(encoding="utf-8")

        self.assertIn("%~dp0install_agent.py", windows_launcher)
        self.assertNotIn("C:\\", windows_launcher)
        self.assertIn('"$SCRIPT_DIR/install_agent.py"', macos_launcher)
        self.assertNotIn("/Users/", macos_launcher)


if __name__ == "__main__":
    unittest.main()
