"""Guided, local-only first installation for one Email Steward operator."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import getpass
import imaplib
import json
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
from typing import Mapping, Protocol, Sequence
from uuid import uuid4


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.credentials import (
    CredentialStore,
    CredentialStoreProtocol,
    collect_profile_and_secret,
)
from email_steward.paths import WorkspacePaths
from email_steward.preflight import format_preflight_messages, run_local_network_preflight
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
_MINIMUM_PYTHON_VERSION = (3, 11)
_KEYRING_REQUIREMENT = "keyring>=25,<27"
IMAP_CONNECT_TIMEOUT_SECONDS = 20.0
_PROFILE_PREFILL_FIELDS = (
    "name",
    "email",
    "preferred_language",
    "reply_language",
    "reply_tone",
)


class VerificationImapClient(Protocol):
    def select(self, folder: str, readonly: bool = True) -> tuple[object, object]: ...

    def logout(self) -> object: ...


CredentialStoreFactory = Callable[[], CredentialStoreProtocol]
DependencyRunner = Callable[[tuple[str, ...], Path], int]


class ImapVerificationError(RuntimeError):
    """A safe, categorized failure that deliberately discards server diagnostics."""

    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


class _SafeArgumentParser(argparse.ArgumentParser):
    """Do not echo rejected command-line values, which could be a pasted password."""

    def error(self, message: str) -> None:
        self.exit(2, "Invalid installer option. Only non-secret profile options are accepted.\n")


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
    credential_store_factory: CredentialStoreFactory = CredentialStore,
    dependency_runner: DependencyRunner | None = None,
    imap_factory: Callable[[OperatorProfile, str], VerificationImapClient] | None = None,
    output_fn: Callable[[str], None] = print,
    profile_prefill: Mapping[str, object] | None = None,
) -> InstallResult | None:
    """Run the consent-first installer; no workspace is created before consent."""
    output_fn(ALIBABA_THIRD_PARTY_PASSWORD_PATH)
    output_fn("Generate the password, copy it now, and keep it safe: it is shown only once.")

    workspace = _collect_workspace(input_fn, output_fn)
    if not _confirmed(input_fn("Create this workspace? [y/N]: ")):
        output_fn("Installation cancelled. No workspace or mailbox settings were created.")
        return None

    store = _preflight_credentials(
        Path(root),
        credential_store=credential_store,
        credential_store_factory=credential_store_factory,
        dependency_runner=dependency_runner or _run_declared_dependency_install,
        output_fn=output_fn,
    )
    if store is None:
        return None

    workspace_existed_before_install = workspace.exists()
    if not _install_public_runtime(Path(root), workspace, output_fn):
        return None

    paths = WorkspacePaths.from_root(workspace)
    paths.ensure_local_directories()
    profile = collect_profile_and_secret(
        input_fn, secret_prompt, store, profile_prefill=profile_prefill
    )
    save_profile(profile, paths.config_file)

    try:
        secret = store.get(profile.email)
        if not isinstance(secret, str) or not secret:
            raise RuntimeError("The local credential store did not return the saved mailbox password.")
    except RuntimeError:
        _report_credential_read_failure(output_fn)
        _remove_failed_installation(
            workspace,
            profile.email,
            store,
            output_fn,
            remove_workspace=not workspace_existed_before_install,
        )
        return None

    try:
        _create_and_verify_readonly((imap_factory or _default_imap_factory), profile, secret)
    except ImapVerificationError as error:
        _report_imap_verification_failure(error, output_fn)
        _remove_failed_installation(
            workspace,
            profile.email,
            store,
            output_fn,
            remove_workspace=not workspace_existed_before_install,
        )
        return None
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


def _preflight_credentials(
    source_root: Path,
    *,
    credential_store: CredentialStoreProtocol | None,
    credential_store_factory: CredentialStoreFactory,
    dependency_runner: DependencyRunner,
    output_fn: Callable[[str], None],
) -> CredentialStoreProtocol | None:
    """Verify the interpreter and secure credential provider before writing a workspace."""
    if sys.version_info[:2] < _MINIMUM_PYTHON_VERSION:
        output_fn("Installation stopped: Python 3.11 or later is required. No workspace was created.")
        output_fn("安装已停止：需要 Python 3.11 或更高版本。未创建任何工作区。")
        return None

    if credential_store is not None:
        return credential_store

    try:
        return credential_store_factory()
    except RuntimeError as initial_error:
        output_fn("Secure credential support is not ready. Installing the declared keyring dependency now.")
        output_fn("安全凭据组件尚未就绪，正在安装项目声明的 keyring 依赖。")
        try:
            return_code = dependency_runner(
                (sys.executable, "-m", "pip", "install", "--disable-pip-version-check", _KEYRING_REQUIREMENT),
                source_root.resolve(strict=True),
            )
        except (OSError, ValueError) as install_error:
            output_fn(f"Dependency installation could not start ({install_error}). No workspace was created.")
            output_fn("依赖安装无法启动。未创建任何工作区；请检查网络和 Python 的 pip 后重试。")
            return None
        if return_code != 0:
            output_fn("Dependency installation failed. No workspace was created; fix the error above and run the installer again.")
            output_fn("依赖安装失败。未创建任何工作区；请修复上方错误后重新运行安装器。")
            return None
        try:
            store = credential_store_factory()
        except RuntimeError as recovery_error:
            output_fn(f"Credential provider is still unavailable ({recovery_error}). No workspace was created.")
            output_fn("凭据提供程序仍不可用。未创建任何工作区；请启用系统凭据库后重试。")
            return None
        output_fn("Credential dependency check completed. The secure operating-system credential provider is ready.")
        return store


def _run_declared_dependency_install(command: tuple[str, ...], cwd: Path) -> int:
    """Run only the fixed dependency command, forwarding pip output to the operator."""
    completed = subprocess.run(command, cwd=cwd, check=False)
    return completed.returncode


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


def _remove_failed_installation(
    workspace: Path,
    email: str,
    store: CredentialStoreProtocol,
    output_fn: Callable[[str], None],
    *,
    remove_workspace: bool,
) -> None:
    """Remove only the just-created workspace and credential after an IMAP check fails."""
    try:
        store.delete(email)
    except RuntimeError:
        pass
    try:
        if remove_workspace:
            shutil.rmtree(workspace)
        else:
            _remove_installer_files_from_existing_workspace(workspace)
    except OSError:
        output_fn("Read-only IMAP verification failed. The incomplete workspace could not be removed; do not reuse it.")
        output_fn("只读 IMAP 验证失败。未完成工作区无法安全删除，请勿复用该文件夹。")
        return
    output_fn("Read-only IMAP verification failed. The incomplete workspace and saved password were removed; check your settings, then run the installer again.")
    output_fn("只读 IMAP 验证失败。未完成工作区和已保存密码已移除；检查设置后请重新运行安装器。")


def _remove_installer_files_from_existing_workspace(workspace: Path) -> None:
    """Undo only reviewed installer output while preserving an operator-created root folder."""
    for directory_name in (*_PUBLIC_RUNTIME_DIRECTORIES, ".email-steward"):
        shutil.rmtree(workspace / directory_name)
    for file_name in _PUBLIC_RUNTIME_FILES:
        (workspace / file_name).unlink()


def _create_and_verify_readonly(
    imap_factory: Callable[[OperatorProfile, str], VerificationImapClient],
    profile: OperatorProfile,
    secret: str,
) -> None:
    """Separate login rejection from a failure after a successful client is created."""
    try:
        client = imap_factory(profile, secret)
    except imaplib.IMAP4.error as error:
        raise ImapVerificationError("authentication_rejected") from error
    except (TimeoutError, socket.timeout) as error:
        raise ImapVerificationError("timeout") from error
    except ssl.SSLError as error:
        raise ImapVerificationError("tls") from error
    except OSError as error:
        raise ImapVerificationError("connection") from error

    try:
        _verify_readonly(client)
    except ImapVerificationError:
        raise
    except (TimeoutError, socket.timeout) as error:
        raise ImapVerificationError("timeout") from error
    except ssl.SSLError as error:
        raise ImapVerificationError("tls") from error
    except (OSError, RuntimeError, imaplib.IMAP4.error) as error:
        raise ImapVerificationError("post_authentication") from error
    finally:
        try:
            client.logout()
        except (OSError, RuntimeError, imaplib.IMAP4.error):
            pass


def _verify_readonly(client: VerificationImapClient) -> None:
    status, _ = client.select("INBOX", readonly=True)
    if status not in ("OK", b"OK"):
        raise RuntimeError("Read-only IMAP verification did not succeed")


def _default_imap_factory(profile: OperatorProfile, secret: str) -> VerificationImapClient:
    client = imaplib.IMAP4_SSL(
        profile.imap_host, profile.imap_port, timeout=IMAP_CONNECT_TIMEOUT_SECONDS
    )
    client.login(profile.email, secret)
    return client


def _report_imap_verification_failure(
    error: ImapVerificationError, output_fn: Callable[[str], None]
) -> None:
    """Give operators an actionable diagnosis without logging a server response or secret."""
    messages = {
        "timeout": (
            "The network connection to the mail server timed out. Check your network or VPN, then retry.",
            "连接邮件服务器超时。请检查网络或 VPN 后重试。",
        ),
        "tls": (
            "A secure connection to the mail server could not be established. Check your network, system date/time, or company security policy, then retry.",
            "无法建立到邮件服务器的安全连接。请检查网络、系统日期时间或公司安全策略后重试。",
        ),
        "connection": (
            "A network connection to the mail server could not be established. Check your network, VPN, and company firewall policy, then retry.",
            "无法连接邮件服务器。请检查网络、VPN 和公司防火墙策略后重试。",
        ),
        "authentication_rejected": (
            "The mail server rejected the login. This does not prove the third-party client password is wrong. Check third-party client login access, the mailbox address, administrator policy, and the saved third-party client password, then retry.",
            "邮件服务器拒绝了登录。这不等于第三方客户端安全密码错误。请检查是否已允许第三方客户端登录、邮箱地址、管理员策略和已保存的第三方客户端安全密码后重试。",
        ),
        "post_authentication": (
            "The read-only mailbox check failed after login. This is not a password diagnosis; check mailbox availability or ask the mail administrator, then retry.",
            "登录后只读邮箱检查失败。这不是密码诊断；请检查邮箱可用性或咨询邮箱管理员后重试。",
        ),
    }
    english, chinese = messages.get(error.category, messages["post_authentication"])
    output_fn(english)
    output_fn(chinese)


def _report_credential_read_failure(output_fn: Callable[[str], None]) -> None:
    """Explain a local credential-store failure without treating it as a mailbox diagnosis."""
    output_fn(
        "The secure credential store could not provide the saved password. No IMAP login was attempted; check the operating-system credential store, then retry."
    )
    output_fn(
        "系统安全凭据库无法读取已保存的密码，因此没有尝试 IMAP 登录。请检查系统凭据库后重试。"
    )


def _build_argument_parser() -> _SafeArgumentParser:
    parser = _SafeArgumentParser(add_help=True)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="show credential-free local network diagnostics, then exit",
    )
    parser.add_argument("--name")
    parser.add_argument("--email")
    parser.add_argument("--preferred-language", dest="preferred_language")
    parser.add_argument("--reply-language", dest="reply_language")
    parser.add_argument("--reply-tone", dest="reply_tone")
    return parser


def parse_profile_prefill(argv: Sequence[str] | None = None) -> dict[str, str]:
    """Parse only non-secret data collected by a Codex chat before launching setup."""
    parsed = _build_argument_parser().parse_args(argv)
    return {
        field: value
        for field in _PROFILE_PREFILL_FIELDS
        if isinstance((value := getattr(parsed, field)), str) and value.strip()
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    preflight_runner: Callable[[], object] = run_local_network_preflight,
    output_fn: Callable[[str], None] = print,
    install_fn: Callable[..., InstallResult | None] = run_install,
) -> int:
    """Run the credential-free preflight before any setup or hidden password prompt."""
    parsed = _build_argument_parser().parse_args(argv)
    observation = preflight_runner()
    for message in format_preflight_messages(observation):
        output_fn(message)
    if parsed.preflight:
        return 0
    profile_prefill = {
        field: value
        for field in _PROFILE_PREFILL_FIELDS
        if isinstance((value := getattr(parsed, field)), str) and value.strip()
    }
    install_fn(
        Path(__file__).resolve().parents[1],
        profile_prefill=profile_prefill,
        output_fn=output_fn,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
