"""Guided, local-only first installation for one Email Steward operator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import getpass
import imaplib
import json
from pathlib import Path
import shutil
import sys
from typing import Protocol
from uuid import uuid4


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

_PUBLIC_RUNTIME_DIRECTORIES = ("src", "installer", ".agents")
_PUBLIC_RUNTIME_FILES = (
    "AGENTS.md",
    ".gitignore",
    "pyproject.toml",
    "README.md",
    "README.zh-CN.md",
    "INSTALL.md",
    "INSTALL.zh-CN.md",
    "TROUBLESHOOTING.md",
    "TROUBLESHOOTING.zh-CN.md",
    "SPEC.md",
)
_EXCLUDED_RUNTIME_NAMES = {".email-steward", ".git", "__pycache__", "cache", "logs", "tests", "tmp"}


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
    output_fn(ALIBABA_THIRD_PARTY_PASSWORD_PATH)
    output_fn("Generate the password, copy it now, and keep it safe: it is shown only once.")

    workspace = _collect_workspace(input_fn, output_fn)
    if not _confirmed(input_fn("Create this workspace? [y/N]: ")):
        output_fn("Installation cancelled. No workspace or mailbox settings were created.")
        return None

    if not _install_public_runtime(Path(root), workspace, output_fn):
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
    _save_daily_brief_preference(paths.config_file.parent / "daily-brief.json", daily_brief_enabled)
    if daily_brief_enabled:
        output_fn("Daily brief preference is enabled. Configure its format and schedule in your Codex project before it runs; installation did not create a schedule.")
    else:
        output_fn("Daily brief is disabled. You can enable it later after choosing its format and schedule; installation did not create a schedule.")

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


def _install_public_runtime(source_root: Path, workspace: Path, output_fn: Callable[[str], None]) -> bool:
    """Copy only the public runtime into an empty, confirmed operator workspace."""
    try:
        source_root = source_root.resolve(strict=True)
        _validate_public_package(source_root)
    except (OSError, ValueError) as error:
        output_fn(f"Installation stopped: the Agent package is incomplete or unsafe ({error}).")
        return False

    if workspace.exists():
        if not workspace.is_dir() or any(workspace.iterdir()):
            output_fn("Installation stopped: the target workspace is not empty, so no files were overwritten.")
            return False
    else:
        workspace.mkdir(parents=True, exist_ok=False)

    try:
        for directory_name in _PUBLIC_RUNTIME_DIRECTORIES:
            _copy_public_directory(source_root / directory_name, workspace / directory_name)
        for file_name in _PUBLIC_RUNTIME_FILES:
            shutil.copy2(source_root / file_name, workspace / file_name)
    except OSError as error:
        output_fn(f"Installation stopped while copying the public Agent files ({error}).")
        return False
    return True


def _validate_public_package(source_root: Path) -> None:
    for directory_name in _PUBLIC_RUNTIME_DIRECTORIES:
        directory = source_root / directory_name
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError(f"required public directory is missing or unsafe: {directory_name}")
    for file_name in _PUBLIC_RUNTIME_FILES:
        file_path = source_root / file_name
        if not file_path.is_file() or file_path.is_symlink():
            raise ValueError(f"required public file is missing or unsafe: {file_name}")


def _copy_public_directory(source: Path, destination: Path) -> None:
    for candidate in source.rglob("*"):
        relative_parts = candidate.relative_to(source).parts
        if any(part in _EXCLUDED_RUNTIME_NAMES or part.startswith(".env") for part in relative_parts):
            continue
        if candidate.is_symlink():
            raise OSError(f"symbolic links are not supported in the public package: {candidate.name}")
    shutil.copytree(source, destination, ignore=_ignore_nonruntime_files, copy_function=shutil.copy2)


def _ignore_nonruntime_files(directory: str, entries: list[str]) -> set[str]:
    return {
        entry
        for entry in entries
        if entry in _EXCLUDED_RUNTIME_NAMES or entry.startswith(".env") or entry.endswith((".pyc", ".pyo"))
    }


def _save_daily_brief_preference(path: Path, enabled: bool) -> None:
    """Persist only the operator's explicit, non-secret daily-brief preference."""
    payload = {"enabled": enabled, "version": 1}
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


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
