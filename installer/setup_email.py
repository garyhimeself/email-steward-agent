"""Local, first-time collection of an Alibaba Enterprise Mail profile and secret."""

from __future__ import annotations

import getpass
from pathlib import Path
import sys
from typing import Callable


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.credentials import (
    CredentialStore,
    CredentialStoreProtocol,
    collect_profile_and_secret,
)
from email_steward.profile import OperatorProfile


ALIBABA_THIRD_PARTY_PASSWORD_PATH = (
    "设置 → 账户与安全 → 账户安全 → 三方客户端登录安全管理 → 生成新密码"
)


def run_setup(
    *,
    input_fn: Callable[[str], str] = input,
    secret_prompt: Callable[[str], str] = getpass.getpass,
    store: CredentialStoreProtocol | None = None,
    output_fn: Callable[[str], None] = print,
) -> OperatorProfile:
    """Guide local setup without ever printing or persisting the secret in a file."""
    output_fn(ALIBABA_THIRD_PARTY_PASSWORD_PATH)
    output_fn("Generate the password, copy it now, and keep it safe: it is shown only once.")
    profile = collect_profile_and_secret(
        input_fn, secret_prompt, store if store is not None else CredentialStore()
    )
    output_fn(f"Secure email setup is complete for {profile.email}.")
    return profile


if __name__ == "__main__":
    run_setup()
