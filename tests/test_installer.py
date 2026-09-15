import subprocess
import sys
import tempfile
import unittest
import json
import io
import imaplib
import socket
import ssl
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from installer.install_agent import (
    ALIBABA_THIRD_PARTY_PASSWORD_PATH,
    LUNA_ACCEPTANCE_PROMPT,
    TERRA_ACCEPTANCE_PROMPT,
    IMAP_CONNECT_TIMEOUT_SECONDS,
    parse_profile_prefill,
    run_install,
)
from email_steward.credentials import CredentialStoreUnavailableError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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

    def login(self, email, secret):
        self.calls.append(("login", email, secret))
        return "OK", [b"logged in"]

    def logout(self):
        self.closed = True


class FailingImapClient(FakeImapClient):
    def select(self, folder, readonly=True):
        self.calls.append(("select", folder, readonly))
        return "NO", [b"denied"]


class ImapPostAuthenticationFailure(FakeImapClient):
    def select(self, folder, readonly=True):
        self.calls.append(("select", folder, readonly))
        raise imaplib.IMAP4.error("[SERVERBUG] internal diagnostic must stay private")


class FailingSecondCredentialReadStore(MemoryCredentialStore):
    def __init__(self):
        super().__init__()
        self.get_calls = 0

    def get(self, email):
        self.get_calls += 1
        if self.get_calls == 2:
            raise RuntimeError("credential diagnostic must stay private")
        return super().get(email)


class InstallerTests(unittest.TestCase):
    def test_chat_prefilled_profile_skips_all_nonsecret_terminal_questions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            requested_prompts = []
            secret_prompts = []
            profile_prefill = {
                "name": "Wade Su",
                "email": "wade@example.com",
                "preferred_language": "English",
                "reply_language": "English",
                "reply_tone": "warm and concise",
            }
            answers = iter((str(workspace), "yes", "n"))

            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: requested_prompts.append(prompt) or next(answers),
                secret_prompt=lambda prompt: secret_prompts.append(prompt) or "test-only-secret",
                credential_store=MemoryCredentialStore(),
                imap_factory=lambda profile, secret: FakeImapClient(),
                output_fn=lambda message: None,
                profile_prefill=profile_prefill,
            )

            self.assertIsNotNone(result)
            self.assertEqual(
                requested_prompts,
                [
                    "Where should the Email Steward workspace be created? ",
                    "Create this workspace? [y/N]: ",
                    "Enable daily brief now? [y/N]: ",
                ],
            )
            self.assertEqual(secret_prompts, ["Alibaba third-party client password: "])
            self.assertEqual(result.profile.email, "wade@example.com")

    def test_secure_window_request_never_asks_for_nonsecret_terminal_input(self):
        from installer import install_agent

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            request = install_agent.parse_install_request(
                [
                    "--secure-window",
                    "--workspace", str(workspace),
                    "--daily-brief", "off",
                    "--name", "Wade Su",
                    "--email", "wade@example.com",
                    "--preferred-language", "Chinese",
                    "--reply-language", "English",
                    "--reply-tone", "professional and friendly",
                ]
            )
            secret_prompts = []
            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: self.fail(f"unexpected terminal prompt: {prompt}"),
                secret_prompt=lambda prompt: secret_prompts.append(prompt) or "test-only-secret",
                credential_store=MemoryCredentialStore(),
                imap_factory=lambda profile, secret: FakeImapClient(),
                output_fn=lambda message: None,
                request=request,
            )

            self.assertIsNotNone(result)
            self.assertFalse(result.daily_brief_enabled)
            self.assertEqual(secret_prompts, ["Alibaba third-party client password: "])

    def test_missing_prefill_field_falls_back_only_for_that_nonsecret_field(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            requested_prompts = []
            prefill = {
                "name": "Wade Su",
                "email": "wade@example.com",
                "preferred_language": "English",
                "reply_language": "English",
            }
            answers = iter((str(workspace), "yes", "warm", "n"))

            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: requested_prompts.append(prompt) or next(answers),
                secret_prompt=lambda prompt: "test-only-secret",
                credential_store=MemoryCredentialStore(),
                imap_factory=lambda profile, secret: FakeImapClient(),
                output_fn=lambda message: None,
                profile_prefill=prefill,
            )

            self.assertIsNotNone(result)
            self.assertEqual(requested_prompts[-2:], ["Default reply tone: ", "Enable daily brief now? [y/N]: "])
            self.assertNotIn("Your name: ", requested_prompts)
            self.assertNotIn("Your Alibaba Enterprise Mail address: ", requested_prompts)

    def test_cli_accepts_only_explicit_nonsecret_profile_prefill_flags(self):
        prefill = parse_profile_prefill(
            [
                "--name", "Wade Su",
                "--email", "wade@example.com",
                "--preferred-language", "English",
                "--reply-language", "English",
                "--reply-tone", "warm",
            ]
        )

        self.assertEqual(prefill["email"], "wade@example.com")
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit):
            parse_profile_prefill(["--password", "test-only-secret"])
        self.assertNotIn("test-only-secret", stderr.getvalue())

    def test_secure_credential_read_failure_is_not_misreported_as_an_imap_login_failure(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            messages = []
            answers = iter((str(workspace), "yes"))
            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: "test-only-secret",
                credential_store=FailingSecondCredentialReadStore(),
                imap_factory=lambda profile, secret: self.fail("IMAP must not run"),
                output_fn=messages.append,
                profile_prefill={
                    "name": "Wade Su", "email": "wade@example.com",
                    "preferred_language": "English", "reply_language": "English", "reply_tone": "warm",
                },
            )

            output = "\n".join(messages).lower()
            self.assertIsNone(result)
            self.assertIn("secure credential store", output)
            self.assertNotIn("after login", output)
            self.assertNotIn("test-only-secret", output)

    def test_imap_authentication_rejection_is_not_claimed_as_a_wrong_password_or_leaked(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            messages = []
            answers = iter((str(workspace), "yes", "n"))
            secret = "test-only-secret"

            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: secret,
                credential_store=MemoryCredentialStore(),
                imap_factory=lambda profile, value: (_ for _ in ()).throw(
                    imaplib.IMAP4.error(f"[AUTHENTICATIONFAILED] {secret}")
                ),
                output_fn=messages.append,
                profile_prefill={
                    "name": "Wade Su", "email": "wade@example.com",
                    "preferred_language": "English", "reply_language": "English", "reply_tone": "warm",
                },
            )

            output = "\n".join(messages).lower()
            self.assertIsNone(result)
            self.assertIn("rejected the login", output)
            self.assertIn("does not prove", output)
            self.assertNotIn("wrong password", output)
            self.assertNotIn(secret, output)
            self.assertNotIn("authenticationfailed", output)

    def test_imap_connection_timeout_and_tls_failures_have_safe_distinct_diagnostics(self):
        failures = (
            (TimeoutError("test-only-secret"), "timed out"),
            (ssl.SSLError("test-only-secret"), "secure connection"),
            (socket.gaierror("test-only-secret"), "network connection"),
        )
        for failure, expected_phrase in failures:
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as temporary_directory:
                workspace = Path(temporary_directory) / "marketing-mail"
                messages = []
                answers = iter((str(workspace), "yes", "n"))
                result = run_install(
                    PROJECT_ROOT,
                    input_fn=lambda prompt: next(answers),
                    secret_prompt=lambda prompt: "test-only-secret",
                    credential_store=MemoryCredentialStore(),
                    imap_factory=lambda profile, secret, error=failure: (_ for _ in ()).throw(error),
                    output_fn=messages.append,
                    profile_prefill={
                        "name": "Wade Su", "email": "wade@example.com",
                        "preferred_language": "English", "reply_language": "English", "reply_tone": "warm",
                    },
                )
                output = "\n".join(messages).lower()
                self.assertIsNone(result)
                self.assertIn(expected_phrase, output)
                self.assertNotIn("test-only-secret", output)

    def test_imap_failure_after_login_is_not_reported_as_an_authentication_rejection(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            messages = []
            answers = iter((str(workspace), "yes", "n"))
            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: "test-only-secret",
                credential_store=MemoryCredentialStore(),
                imap_factory=lambda profile, secret: ImapPostAuthenticationFailure(),
                output_fn=messages.append,
                profile_prefill={
                    "name": "Wade Su", "email": "wade@example.com",
                    "preferred_language": "English", "reply_language": "English", "reply_tone": "warm",
                },
            )

            output = "\n".join(messages).lower()
            self.assertIsNone(result)
            self.assertIn("after login", output)
            self.assertNotIn("rejected the login", output)
            self.assertNotIn("serverbug", output)

    def test_default_imap_connection_uses_a_bounded_timeout(self):
        from installer import install_agent
        profile = type("Profile", (), {"imap_host": "imap.example.com", "imap_port": 993, "email": "wade@example.com"})()
        client = FakeImapClient()
        with patch.object(install_agent.imaplib, "IMAP4_SSL", return_value=client) as imap_ssl:
            install_agent._default_imap_factory(profile, "test-only-secret")

        imap_ssl.assert_called_once_with("imap.example.com", 993, timeout=IMAP_CONNECT_TIMEOUT_SECONDS)

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
                PROJECT_ROOT,
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
                ("output", "Daily brief is disabled. You can enable it later after choosing its format and schedule; installation did not create a schedule."),
            ])
            self.assertIn(("output", LUNA_ACCEPTANCE_PROMPT), events)
            self.assertIn(("output", TERRA_ACCEPTANCE_PROMPT), events)
            self.assertNotIn("test-only-secret", (workspace / ".email-steward" / "config" / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(
                json.loads((workspace / ".email-steward" / "config" / "daily-brief.json").read_text(encoding="utf-8")),
                {"enabled": False, "version": 1},
            )

    def test_installer_returns_exact_new_project_acceptance_prompts_for_luna_then_terra(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            answers = iter((str(workspace), "y", "Wade", "wade@example.com", "English", "English", "warm", "n"))

            result = run_install(
                PROJECT_ROOT,
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
        root = PROJECT_ROOT
        windows_launcher = (root / "installer" / "install_agent.bat").read_text(encoding="utf-8")
        macos_launcher = (root / "installer" / "install_agent.command").read_text(encoding="utf-8")

        self.assertIn("%~dp0install_agent.py", windows_launcher)
        self.assertIn("%*", windows_launcher)
        self.assertNotIn("C:\\", windows_launcher)
        self.assertIn('"$SCRIPT_DIR/install_agent.py"', macos_launcher)
        self.assertIn('"$@"', macos_launcher)
        self.assertNotIn("/Users/", macos_launcher)

    def test_windows_secure_window_launcher_uses_a_separate_powershell_without_password_fallback(self):
        launcher = (PROJECT_ROOT / "installer" / "install_agent.bat").read_text(encoding="utf-8")

        self.assertIn("--secure-window", launcher)
        self.assertIn("powershell.exe", launcher.lower())
        self.assertIn("start", launcher.lower())
        self.assertIn("-noprofile", launcher.lower())
        self.assertNotIn("set /p", launcher.lower())
        self.assertNotIn("password", launcher.lower())
        window_script = (PROJECT_ROOT / "installer" / "secure_install_window.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("$PSScriptRoot", window_script)
        self.assertIn("Read-Host", window_script)
        self.assertNotIn("password", window_script.lower())

    def test_launchers_explain_when_python_311_is_not_available(self):
        windows_launcher = (PROJECT_ROOT / "installer" / "install_agent.bat").read_text(encoding="utf-8")
        macos_launcher = (PROJECT_ROOT / "installer" / "install_agent.command").read_text(encoding="utf-8")

        self.assertIn("where py", windows_launcher)
        self.assertIn("Python 3.11", windows_launcher)
        self.assertIn("Python 3.11", macos_launcher)
        self.assertIn("command -v python3", macos_launcher)
        self.assertIn("sys.version_info", macos_launcher)

    def test_installer_copies_only_public_runtime_files_into_new_workspace(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            package = temporary_root / "package"
            workspace = temporary_root / "marketing-mail"
            (package / "src" / "email_steward").mkdir(parents=True)
            (package / "src" / "email_steward" / "marker.py").write_text("PUBLIC = True\n", encoding="utf-8")
            (package / "installer").mkdir()
            (package / "installer" / "install_agent.py").write_text("# public launcher\n", encoding="utf-8")
            (package / ".agents" / "skills" / "mail-read").mkdir(parents=True)
            (package / ".agents" / "skills" / "mail-read" / "SKILL.md").write_text("# public skill\n", encoding="utf-8")
            (package / "docs").mkdir()
            (package / "docs" / "private-plan.md").write_text("do-not-copy", encoding="utf-8")
            for filename in (
                "AGENTS.md",
                "pyproject.toml",
                ".gitignore",
                "README.md",
                "README.zh-CN.md",
                "INSTALL.md",
                "INSTALL.zh-CN.md",
                "TROUBLESHOOTING.md",
                "TROUBLESHOOTING.zh-CN.md",
                "SPEC.md",
            ):
                (package / filename).write_text("public\n", encoding="utf-8")
            (package / ".email-steward" / "config").mkdir(parents=True)
            (package / ".email-steward" / "config" / "config.json").write_text('{"secret":"do-not-copy"}', encoding="utf-8")
            (package / ".env").write_text("PASSWORD=do-not-copy\n", encoding="utf-8")
            (package / "tests" / "tmp").mkdir(parents=True)
            (package / "tests" / "tmp" / "mail.eml").write_text("do-not-copy", encoding="utf-8")
            (package / ".git").mkdir()
            (package / ".git" / "HEAD").write_text("do-not-copy", encoding="utf-8")
            answers = iter((str(workspace), "yes", "Wade", "wade@example.com", "English", "English", "warm", "n"))

            run_install(
                package,
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: "test-only-secret",
                credential_store=MemoryCredentialStore(),
                imap_factory=lambda profile, secret: FakeImapClient(),
                output_fn=lambda message: None,
            )

            self.assertTrue((workspace / "src" / "email_steward" / "marker.py").is_file())
            self.assertTrue((workspace / "installer" / "install_agent.py").is_file())
            self.assertTrue((workspace / ".agents" / "skills" / "mail-read" / "SKILL.md").is_file())
            self.assertFalse((workspace / "docs").exists())
            self.assertTrue((workspace / "AGENTS.md").is_file())
            self.assertTrue((workspace / "pyproject.toml").is_file())
            self.assertFalse((workspace / ".env").exists())
            self.assertFalse((workspace / "tests").exists())
            self.assertFalse((workspace / ".git").exists())
            self.assertNotIn("do-not-copy", (workspace / ".email-steward" / "config" / "config.json").read_text(encoding="utf-8"))

    def test_installer_refuses_to_overwrite_a_nonempty_workspace(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            workspace.mkdir()
            protected = workspace / "keep-me.txt"
            protected.write_text("operator file", encoding="utf-8")
            events = []
            answers = iter((str(workspace), "yes"))

            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: self.fail("secret prompt must not run"),
                credential_store=MemoryCredentialStore(),
                imap_factory=lambda profile, secret: self.fail("IMAP must not run"),
                output_fn=events.append,
            )

            self.assertIsNone(result)
            self.assertEqual(protected.read_text(encoding="utf-8"), "operator file")
            self.assertTrue(any("not empty" in message.lower() for message in events))

    def test_missing_credential_dependency_stops_before_workspace_creation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            events = []
            answers = iter((str(workspace), "yes"))

            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: self.fail("secret prompt must not run"),
                credential_store_factory=lambda: (_ for _ in ()).throw(
                    CredentialStoreUnavailableError("keyring is unavailable")
                ),
                imap_factory=lambda profile, secret: self.fail("IMAP must not run"),
                dependency_runner=lambda command, cwd: 1,
                output_fn=events.append,
            )

            self.assertIsNone(result)
            self.assertFalse(workspace.exists())
            self.assertTrue(any("keyring" in message.lower() for message in events))
            self.assertTrue(any("no workspace was created" in message.lower() for message in events))

    def test_successful_dependency_recovery_precedes_workspace_creation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            events = []
            answers = iter((str(workspace), "yes", "Wade", "wade@example.com", "English", "English", "warm", "n"))
            recovered_store = MemoryCredentialStore()
            factory_calls = 0

            def credential_store_factory():
                nonlocal factory_calls
                factory_calls += 1
                if factory_calls == 1:
                    raise CredentialStoreUnavailableError("keyring is unavailable")
                return recovered_store

            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: "test-only-secret",
                credential_store_factory=credential_store_factory,
                dependency_runner=lambda command, cwd: 0,
                imap_factory=lambda profile, secret: FakeImapClient(),
                output_fn=events.append,
            )

            self.assertIsNotNone(result)
            self.assertTrue(workspace.is_dir())
            self.assertEqual(factory_calls, 2)
            self.assertTrue(any("dependency check completed" in message.lower() for message in events))

    def test_installer_persists_an_enabled_daily_brief_choice_without_claiming_a_schedule_exists(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            messages = []
            answers = iter((str(workspace), "yes", "Wade", "wade@example.com", "English", "English", "warm", "yes"))

            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: "test-only-secret",
                credential_store=MemoryCredentialStore(),
                imap_factory=lambda profile, secret: FakeImapClient(),
                output_fn=messages.append,
            )

            self.assertTrue(result.daily_brief_enabled)
            self.assertEqual(
                json.loads((workspace / ".email-steward" / "config" / "daily-brief.json").read_text(encoding="utf-8")),
                {"enabled": True, "version": 1},
            )
            self.assertTrue(any("schedule" in message.lower() and "before it runs" in message.lower() for message in messages))

    def test_failed_imap_check_removes_incomplete_workspace_and_credential_for_a_safe_retry(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            store = MemoryCredentialStore()
            messages = []
            answers = iter((str(workspace), "yes", "Wade", "wade@example.com", "English", "English", "warm"))

            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: "test-only-secret",
                credential_store=store,
                imap_factory=lambda profile, secret: FailingImapClient(),
                output_fn=messages.append,
            )

            self.assertIsNone(result)
            self.assertFalse(workspace.exists())
            self.assertIsNone(store.get("wade@example.com"))
            self.assertTrue(any("run the installer again" in message.lower() for message in messages))
            self.assertFalse(any("test-only-secret" in message for message in messages))

    def test_failed_imap_check_keeps_an_operator_created_empty_workspace(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "marketing-mail"
            workspace.mkdir()
            store = MemoryCredentialStore()
            answers = iter((str(workspace), "yes", "Wade", "wade@example.com", "English", "English", "warm"))

            result = run_install(
                PROJECT_ROOT,
                input_fn=lambda prompt: next(answers),
                secret_prompt=lambda prompt: "test-only-secret",
                credential_store=store,
                imap_factory=lambda profile, secret: FailingImapClient(),
                output_fn=lambda message: None,
            )

            self.assertIsNone(result)
            self.assertTrue(workspace.is_dir())
            self.assertEqual(list(workspace.iterdir()), [])
            self.assertIsNone(store.get("wade@example.com"))

    def test_install_guides_state_python_prerequisite_and_daily_brief_is_not_scheduled(self):
        english = (PROJECT_ROOT / "INSTALL.md").read_text(encoding="utf-8")
        chinese = (PROJECT_ROOT / "INSTALL.zh-CN.md").read_text(encoding="utf-8")

        self.assertIn("Python 3.11", english)
        self.assertIn("not bundle Python", english)
        self.assertIn("Python 3.11", chinese)
        self.assertIn("不包含 Python", chinese)
        self.assertIn("does not create a schedule", english)
        self.assertIn("不会创建定时任务", chinese)
        self.assertIn("retry", english.lower())
        self.assertIn("重新运行安装器", chinese)

    def test_macos_launcher_is_tracked_as_executable_on_all_platforms(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--stage", "--", "installer/install_agent.command"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertRegex(result.stdout, r"^100755 [0-9a-f]+ 0\tinstaller/install_agent\.command\s*$")


if __name__ == "__main__":
    unittest.main()
