"""Safe runtime access to one installed workspace's mailbox credential."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path

from .credentials import CredentialStore, CredentialStoreProtocol
from .paths import WorkspacePaths
from .profile import OperatorProfile, validate_profile


class WorkspaceSessionError(RuntimeError):
    """The workspace cannot safely provide its configured mailbox session."""


class WorkspaceCredentialMissingError(WorkspaceSessionError):
    """No system-stored credential is available for the workspace mailbox."""


@dataclass(frozen=True)
class MailboxSession:
    """A validated profile with its secret held only in process memory."""

    profile: OperatorProfile
    secret: str


def load_workspace_session(
    workspace: str | Path,
    *,
    credential_store: CredentialStoreProtocol | None = None,
) -> MailboxSession:
    """Load a workspace profile and its existing OS-managed credential."""
    config_path = WorkspacePaths.from_root(Path(workspace)).config_file
    profile = load_workspace_profile(workspace)
    secret = (credential_store or CredentialStore()).get(profile.email)
    if not isinstance(secret, str) or not secret:
        raise WorkspaceCredentialMissingError(
            "No saved system credential exists for this workspace mailbox."
        )
    return MailboxSession(profile=profile, secret=secret)


def load_workspace_profile(workspace: str | Path) -> OperatorProfile:
    """Load and validate only the non-secret profile stored in a workspace."""
    config_path = WorkspacePaths.from_root(Path(workspace)).config_file
    try:
        raw_profile = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkspaceSessionError("The workspace mailbox configuration is unavailable.") from error
    if not isinstance(raw_profile, Mapping):
        raise WorkspaceSessionError("The workspace mailbox configuration is invalid.")
    try:
        return validate_profile(raw_profile)
    except (TypeError, ValueError) as error:
        raise WorkspaceSessionError("The workspace mailbox configuration is invalid.") from error
