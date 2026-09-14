"""Guided, local-only first installation for one Email Steward operator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import getpass
import imaplib
from pathlib import Path
import sys
from typing import Protocol


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.credentials import (
    CredentialStore,
    CredentialStoreProtocol,
    collect_profile_and_secret,
)
from email_steward.paths import WorkspacePaths
from email_steward.profile import OperatorProfile, save_profile


ALIBABA_THIRD_PARTY_PASSWORD_PATH = (
    "设置 → 账户与安全 → 账户安全 → 三方客户端登录安全管理 → 生成新密码"
)
LUNA_ACCEPTANCE_PROMPT = (
    "请完成首次验收：查询最近 7 天未读的开发合作邮件，展示一封最相关邮件的摘要和邮件编号。不要发送邮件。"
)
TERRA_ACCEPTANCE_PROMPT = (
    "请根据邮件编号【复制上一步的编号】，生成一份专业、友好的英文回复草稿。不要发送邮件。"
)


class VerificationImapClient(Protocol):
    def select(self, folder: str, readonly: bool = True) -> tuple[object, object]: ...

    def logout(self) -> object: ...


@dataclass(frozen=True)
class InstallResult:
    """The non-secret result of a successful local installation."""

    workspace: Path
    profile: OperatorProfile
    imap_verified: bool
    daily_brief_enabled: bool
    next_step: tuple[str, str]


def run_install(
    root: Path,
    input_fn: Callable[[str], str] = input,
    secret_prompt: Callable[[str], str] = getpass.getpass,
    credential_store: CredentialStoreProtocol | None = None,
    imap_factory: Callable[[OperatorProfile, str], VerificationImapClient] | None = None,
    output_fn: Callable[[str], None] = print,
) -> InstallResult | None:
    """Run the consent-first installer; no workspace is created before consent."""
    del root  # The package location is intentionally not copied into operator data.
    output_fn(ALIBABA_THIRD_PARTY_PASSWORD_PATH)
    output_fn("Generate the password, copy it now, and keep it safe: it is shown only once.")

    workspace = _collect_workspace(input_fn, output_fn)
    if not _confirmed(input_fn("Create this workspace? [y/N]: ")):
        output_fn("Installation cancelled. No workspace or mailbox settings were created.")
        return None

    paths = WorkspacePaths.from_root(workspace)
    paths.ensure_local_directories()
    store = credential_store if credential_store is not None else CredentialStore()
    profile = collect_profile_and_secret(input_fn, secret_prompt, store)
    save_profile(profile, paths.config_file)

    secret = store.get(profile.email)
    if not isinstance(secret, str) or not secret:
        raise RuntimeError("The local credential store did not return the saved mailbox password.")
    _verify_readonly((imap_factory or _default_imap_factory)(profile, secret))
    output_fn("Read-only IMAP verification succeeded. No email was changed.")

    daily_brief_enabled = _daily_brief_enabled(input_fn("Enable daily brief now? [y/N]: "))
    if daily_brief_enabled:
        output_fn("Daily brief is enabled. Configure its format and schedule in your Codex project before it runs.")
    else:
        output_fn("Daily brief is disabled. You can enable it later after choosing its format and schedule.")

    output_fn(f"Create a Codex project for this workspace: 邮件管家 - {profile.name}")
    output_fn("In that new project, open a Luna chat with low reasoning and send:")
    output_fn(LUNA_ACCEPTANCE_PROMPT)
    output_fn("Then open a new Terra chat with low reasoning and send:")
    output_fn(TERRA_ACCEPTANCE_PROMPT)
    return InstallResult(
        workspace=workspace,
        profile=profile,
        imap_verified=True,
        daily_brief_enabled=daily_brief_enabled,
        next_step=(LUNA_ACCEPTANCE_PROMPT, TERRA_ACCEPTANCE_PROMPT),
    )


def _collect_workspace(input_fn: Callable[[str], str], output_fn: Callable[[str], None]) -> Path:
    raw_path = input_fn("Where should the Email Steward workspace be created? ")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("A workspace folder is required")
    workspace = Path(raw_path.strip()).expanduser().resolve(strict=False)
    output_fn(f"Target workspace: {workspace}")
    return workspace


def _confirmed(answer: object) -> bool:
    return isinstance(answer, str) and answer.strip().lower() in {"y", "yes"}


def _daily_brief_enabled(answer: object) -> bool:
    if not isinstance(answer, str):
        raise ValueError("Daily brief choice must be yes or no")
    normalized = answer.strip().lower()
    if normalized in {"", "n", "no"}:
        return False
    if normalized in {"y", "yes"}:
        return True
    raise ValueError("Daily brief choice must be yes or no")


def _verify_readonly(client: VerificationImapClient) -> None:
    try:
        status, _ = client.select("INBOX", readonly=True)
        if status not in ("OK", b"OK"):
            raise RuntimeError("Read-only IMAP verification did not succeed")
    finally:
        client.logout()


def _default_imap_factory(profile: OperatorProfile, secret: str) -> VerificationImapClient:
    client = imaplib.IMAP4_SSL(profile.imap_host, profile.imap_port)
    client.login(profile.email, secret)
    return client


if __name__ == "__main__":
    run_install(Path(__file__).resolve().parents[1])
