"""Credential-safe runtime status command for an installed Email Steward workspace."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
from pathlib import Path
import sys
from typing import Sequence


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.credentials import CredentialStoreUnavailableError
from email_steward.workspace_session import (
    MailboxSession,
    WorkspaceCredentialMissingError,
    WorkspaceSessionError,
    load_workspace_session,
)


SessionLoader = Callable[[str | Path], MailboxSession]
Output = Callable[[str], None]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check an installed Email Steward workspace credential without exposing it."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    status = subcommands.add_parser("credential-status")
    status.add_argument("--workspace", required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    session_loader: SessionLoader = load_workspace_session,
    output_fn: Output = print,
) -> int:
    """Report whether this OS user can access the workspace credential."""
    parsed = _parser().parse_args(argv)
    if parsed.command != "credential-status":
        return 2
    try:
        session = session_loader(parsed.workspace)
    except WorkspaceCredentialMissingError:
        _write_status(output_fn, "credential_missing")
        return 3
    except CredentialStoreUnavailableError:
        _write_status(output_fn, "credential_unavailable")
        return 4
    except WorkspaceSessionError:
        _write_status(output_fn, "workspace_invalid")
        return 5
    _write_status(output_fn, "credential_ready", mailbox=session.profile.email)
    return 0


def _write_status(output_fn: Output, status: str, *, mailbox: str | None = None) -> None:
    """Emit only non-secret state, never the loaded credential."""
    payload: dict[str, str] = {"status": status}
    if mailbox is not None:
        payload["mailbox"] = mailbox
    output_fn(json.dumps(payload, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
